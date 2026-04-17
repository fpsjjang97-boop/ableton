"""Dynamic Time Warping for MIDI sequence alignment and similarity.

Port inspired by ACE-Step v1.5 ``acestep/core/scoring/_dtw.py`` (Apache
2.0). The ACE-Step original uses Numba JIT on CPU for audio-scale
sequences (thousands of frames). MidiGPT's per-song token length is
small (typically < 4,000 tokens), so plain NumPy is fast enough and
avoids the Numba install. The algorithm — classical O(N*M) DP with
diagonal + horizontal + vertical transitions — is identical.

Usage (standalone; no dependency on the model):

    from tools.scoring.dtw_score import midi_similarity, dtw_path

    # Compare a generation to a reference MIDI file
    score = midi_similarity("./output/gen.mid", "./reference/target.mid")
    print(f"similarity: {score:.3f}   (1.0 = identical, 0.0 = unrelated)")

Design intent:
  * DPO reward signal — compare two candidates ``chosen`` vs ``rejected``
    against a shared reference to produce preference labels automatically.
  * Regression test — a known-good generation can serve as a golden,
    and we fail a run when similarity drops below a threshold.
  * Debug — ``dtw_path`` returns the alignment itself so we can visualise
    *where* a generation diverged from its intended continuation.

Reference (port target):
  https://github.com/ace-step/ACE-Step-1.5/blob/main/acestep/core/scoring/_dtw.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import numpy as np

if sys.platform == "win32":
    # rules/03-windows-compat.md §3.2 — 한글 파일명 대비 stdout UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Core DTW
# ---------------------------------------------------------------------------
def dtw_cost_matrix(
    a: np.ndarray,
    b: np.ndarray,
    metric: str = "euclidean",
) -> np.ndarray:
    """Pairwise distance matrix of shape (len(a), len(b)).

    Args:
        a, b: 1D arrays of numeric features (e.g. pitch sequence) or
              2D arrays where each row is a feature vector.
        metric: ``"euclidean"`` (L2 on features) or ``"absolute"`` (L1).
                For 1D scalar input both collapse to ``|a_i - b_j|``.

    Memory: O(len(a) * len(b)). For MIDI < 4k tokens both sides this
    stays under ~128MB at float32.
    """
    if a.ndim == 1:
        a = a[:, None].astype(np.float32)
    if b.ndim == 1:
        b = b[:, None].astype(np.float32)
    # Broadcast subtract: (N, 1, D) - (1, M, D) → (N, M, D)
    diff = a[:, None, :] - b[None, :, :]
    if metric == "euclidean":
        return np.sqrt((diff * diff).sum(axis=-1))
    if metric == "absolute":
        return np.abs(diff).sum(axis=-1)
    raise ValueError(f"unknown metric: {metric}")


def dtw_accumulated(cost: np.ndarray) -> np.ndarray:
    """Fill the accumulated-cost matrix D where D[i,j] = min path to (i,j).

    Boundary: D[0,0] = cost[0,0]; first row/col are cumulative sums
    (classical non-constrained DTW). Transitions: (-1,-1), (-1,0), (0,-1).
    """
    N, M = cost.shape
    D = np.full((N, M), np.inf, dtype=np.float32)
    D[0, 0] = cost[0, 0]
    for i in range(1, N):
        D[i, 0] = D[i - 1, 0] + cost[i, 0]
    for j in range(1, M):
        D[0, j] = D[0, j - 1] + cost[0, j]
    for i in range(1, N):
        for j in range(1, M):
            D[i, j] = cost[i, j] + min(D[i - 1, j - 1], D[i - 1, j], D[i, j - 1])
    return D


def dtw_path(cost: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Return the optimal warping path (i_indices, j_indices) + total cost.

    The path starts at (0,0) and ends at (N-1, M-1). Its length is between
    max(N,M) and N+M-1 depending on alignment.
    """
    D = dtw_accumulated(cost)
    N, M = cost.shape
    i, j = N - 1, M - 1
    ii: list[int] = [i]
    jj: list[int] = [j]
    while i > 0 or j > 0:
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            diag = D[i - 1, j - 1]
            up = D[i - 1, j]
            left = D[i, j - 1]
            step = np.argmin([diag, up, left])
            if step == 0:
                i -= 1
                j -= 1
            elif step == 1:
                i -= 1
            else:
                j -= 1
        ii.append(i)
        jj.append(j)
    ii.reverse()
    jj.reverse()
    return np.asarray(ii), np.asarray(jj), float(D[-1, -1])


# ---------------------------------------------------------------------------
# Median filter (ACE-Step port)
# ---------------------------------------------------------------------------
def median_filter(x: np.ndarray, k: int = 3) -> np.ndarray:
    """1D median filter with window ``k`` (odd, >= 1).

    Edges are reflected (``np.pad`` mode ``reflect``) so output length
    matches input. Useful for smoothing velocity curves or timing jitter
    without distorting sharp transitions as much as a mean filter.
    """
    if k < 1:
        raise ValueError("k must be >= 1")
    if k == 1:
        return x.copy()
    if k % 2 == 0:
        k += 1
    pad = k // 2
    padded = np.pad(x, pad, mode="reflect")
    out = np.empty_like(x, dtype=np.float32)
    for i in range(len(x)):
        out[i] = np.median(padded[i : i + k])
    return out


# ---------------------------------------------------------------------------
# MIDI-level similarity
# ---------------------------------------------------------------------------
def _midi_pitch_sequence(midi_path: str | Path) -> np.ndarray:
    """Extract a 1D pitch sequence ordered by (start_time, pitch).

    Returns an empty array if the file has no notes.
    """
    import pretty_midi  # local import — optional dep
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes: list[tuple[float, int]] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            notes.append((n.start, n.pitch))
    notes.sort()
    if not notes:
        return np.array([], dtype=np.int32)
    return np.asarray([p for _t, p in notes], dtype=np.int32)


def midi_similarity(
    path_a: str | Path,
    path_b: str | Path,
    max_len: int = 4096,
) -> float:
    """Similarity score in [0, 1] where 1 = pitch-identical alignment.

    Extracts pitch-ordered-by-time sequences from both files and computes
    DTW cost normalised by path length and the theoretical max pitch
    distance (127). Works for arbitrary-length inputs (clipped to
    ``max_len`` per side to keep the DP under ~16M cells).

    Empty or single-note inputs return ``0.0``.
    """
    a = _midi_pitch_sequence(path_a)
    b = _midi_pitch_sequence(path_b)
    if len(a) < 2 or len(b) < 2:
        return 0.0
    if len(a) > max_len:
        a = a[:max_len]
    if len(b) > max_len:
        b = b[:max_len]
    cost = dtw_cost_matrix(a, b, metric="absolute")
    _ii, _jj, total = dtw_path(cost)
    path_len = max(len(a), len(b))
    mean_cost = total / path_len
    return max(0.0, 1.0 - mean_cost / 127.0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Compute DTW-based pitch similarity between two MIDI files."
    )
    parser.add_argument("a", help="First MIDI file")
    parser.add_argument("b", help="Second MIDI file")
    parser.add_argument("--max_len", type=int, default=4096)
    args = parser.parse_args()

    score = midi_similarity(args.a, args.b, max_len=args.max_len)
    print(f"similarity: {score:.4f}")


if __name__ == "__main__":
    main()
