"""
SimilarityEngine -- cosine-similarity search over the MAESTRO embedding matrix.

Loads embeddings/embedding_matrix.npy, embeddings/catalog.json, and
embeddings/metadata.json to support tag-based filtering and track-based
nearest-neighbour retrieval.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # app/core -> app -> repo
_EMBED_DIR = _REPO_ROOT / "embeddings"
_CHORDS_DIR = _REPO_ROOT / "analyzed_chords"

EMBEDDING_DIM = 128

# Duration bucket boundaries in beats (for the 8-bin duration histogram)
_DUR_BOUNDARIES = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]  # 1/32 .. 4+ beats
TICKS_PER_BEAT = 480  # default; overridable


def _load_json(path: str | Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Vectorised cosine similarity of *query* (1-D) against each row of *matrix*."""
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return np.zeros(matrix.shape[0])
    row_norms = np.linalg.norm(matrix, axis=1)
    row_norms = np.where(row_norms == 0, 1.0, row_norms)  # avoid div-by-zero
    return matrix @ query / (row_norms * query_norm)


class SimilarityEngine:
    """Cosine-similarity search over pre-computed MAESTRO embeddings."""

    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None
        self._catalog: list[dict] = []
        self._metadata: dict = {}
        self._file_list: list[str] = []
        self._load()

    # ------------------------------------------------------------------ #
    #  Data loading                                                       #
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        # Embedding matrix (93 x 128)
        npy_path = _EMBED_DIR / "embedding_matrix.npy"
        if npy_path.exists():
            self._matrix = np.load(str(npy_path))
        else:
            self._matrix = np.zeros((0, EMBEDDING_DIM))

        # Catalog with per-file metadata
        cat_data = _load_json(_EMBED_DIR / "catalog.json") or {}
        self._catalog = cat_data.get("catalog", [])

        # Metadata (file ordering)
        self._metadata = _load_json(_EMBED_DIR / "metadata.json") or {}
        self._file_list = self._metadata.get("files", [])

    # ------------------------------------------------------------------ #
    #  Tag-based search                                                   #
    # ------------------------------------------------------------------ #
    def search_by_tags(self, tags: dict, top_k: int = 5) -> list[dict]:
        """Filter catalog entries by tag match, return top-k.

        *tags* example: {"rhythm_type": "moderate", "harmony_type": "triadic"}

        Each result:
            {"filename": ..., "similarity": ..., "category": ..., "tags": {...}}
        """
        if not self._catalog:
            return []

        scored: list[tuple[float, dict]] = []
        for entry in self._catalog:
            composer_tags: dict = entry.get("composer_tags", {})
            match_count = 0
            total_tags = max(len(tags), 1)
            for k, v in tags.items():
                if str(composer_tags.get(k, "")).lower() == str(v).lower():
                    match_count += 1
            score = match_count / total_tags

            scored.append((score, entry))

        # Sort by match score descending, then by filename for stability
        scored.sort(key=lambda x: (-x[0], x[1].get("filename", "")))

        results: list[dict] = []
        for score, entry in scored[:top_k]:
            results.append({
                "filename": entry.get("filename", ""),
                "similarity": round(score, 4),
                "category": entry.get("category", ""),
                "tags": entry.get("composer_tags", {}),
            })
        return results

    # ------------------------------------------------------------------ #
    #  Track-based search                                                 #
    # ------------------------------------------------------------------ #
    def search_by_track(self, track, top_k: int = 5) -> list[dict]:
        """Compute a simple embedding for a live Track and find closest matches.

        *track* must expose a ``.notes`` list of objects with attributes:
        ``pitch``, ``velocity``, ``start_tick``, ``duration_ticks``.
        """
        if self._matrix is None or self._matrix.shape[0] == 0:
            return []

        embedding = self._embed_track(track)
        sims = _cosine_similarity(embedding, self._matrix)

        # top-k indices
        if top_k >= len(sims):
            top_idx = np.argsort(-sims)
        else:
            top_idx = np.argpartition(-sims, top_k)[:top_k]
            top_idx = top_idx[np.argsort(-sims[top_idx])]

        results: list[dict] = []
        for idx in top_idx:
            idx = int(idx)
            filename = self._file_list[idx] if idx < len(self._file_list) else f"idx_{idx}"
            cat_entry = self._catalog[idx] if idx < len(self._catalog) else {}
            results.append({
                "filename": filename,
                "similarity": round(float(sims[idx]), 4),
                "category": cat_entry.get("category", ""),
                "tags": cat_entry.get("composer_tags", {}),
            })
        return results

    # ------------------------------------------------------------------ #
    #  Track embedding                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _embed_track(track) -> np.ndarray:
        """Build a 128-dim feature vector from a Track's notes.

        Layout:
            [0:12]   pitch-class histogram (normalised)
            [12:24]  interval histogram (normalised, clipped to +/-12 -> 25 bins mapped to 12)
            [24:32]  duration histogram (8 buckets)
            [32:40]  velocity histogram (8 bins, 0-127)
            [40:128] zero-padded (or tiled from above features)
        """
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float64)
        notes = getattr(track, "notes", [])
        if not notes:
            return vec

        # Pitch-class histogram (12 bins)
        pc_hist = np.zeros(12)
        pitches = []
        for n in notes:
            pc_hist[n.pitch % 12] += 1
            pitches.append(n.pitch)
        pc_sum = pc_hist.sum()
        if pc_sum > 0:
            pc_hist /= pc_sum
        vec[0:12] = pc_hist

        # Interval histogram -- map intervals to 12 bins (abs value, clipped)
        interval_hist = np.zeros(12)
        sorted_notes = sorted(notes, key=lambda n: n.start_tick)
        for i in range(1, len(sorted_notes)):
            interval = sorted_notes[i].pitch - sorted_notes[i - 1].pitch
            bucket = min(abs(interval), 11)
            interval_hist[bucket] += 1
        iv_sum = interval_hist.sum()
        if iv_sum > 0:
            interval_hist /= iv_sum
        vec[12:24] = interval_hist

        # Duration histogram (8 buckets)
        dur_hist = np.zeros(8)
        for n in notes:
            dur_beats = n.duration_ticks / TICKS_PER_BEAT
            bucket = 7  # 4+ beats
            for bi, boundary in enumerate(_DUR_BOUNDARIES):
                if dur_beats <= boundary:
                    bucket = bi
                    break
            dur_hist[bucket] += 1
        dh_sum = dur_hist.sum()
        if dh_sum > 0:
            dur_hist /= dh_sum
        vec[24:32] = dur_hist

        # Velocity histogram (8 bins from 0-127)
        vel_hist = np.zeros(8)
        for n in notes:
            bucket = min(n.velocity // 16, 7)
            vel_hist[bucket] += 1
        vh_sum = vel_hist.sum()
        if vh_sum > 0:
            vel_hist /= vh_sum
        vec[32:40] = vel_hist

        # Remaining dims: tile the 40-dim feature to fill up to 128
        base = vec[:40].copy()
        pos = 40
        while pos < EMBEDDING_DIM:
            chunk = min(40, EMBEDDING_DIM - pos)
            vec[pos : pos + chunk] = base[:chunk]
            pos += chunk

        return vec

    # ------------------------------------------------------------------ #
    #  Pattern extraction from analyzed_chords                            #
    # ------------------------------------------------------------------ #
    def get_patterns_for_results(self, results: list[dict]) -> list[dict]:
        """Load analyzed_chords/{filename}.json for each result and extract
        chord progressions to use in generation.

        Returns a list of dicts with keys: filename, chords, key_estimate.
        """
        patterns: list[dict] = []
        for r in results:
            filename = r.get("filename", "")
            if not filename:
                continue
            # Derive the JSON filename (strip .midi extension, add .json)
            base = filename
            if base.endswith(".midi"):
                base = base[:-5]
            elif base.endswith(".mid"):
                base = base[:-4]
            json_path = _CHORDS_DIR / (base + ".json")
            data = _load_json(json_path)
            if data is None:
                continue

            harmony = data.get("harmony", {})
            segments = harmony.get("segments", [])
            chords = [seg.get("chord", "") for seg in segments if seg.get("chord")]

            patterns.append({
                "filename": filename,
                "chords": chords,
                "key_estimate": harmony.get("key_estimate", ""),
            })
        return patterns
