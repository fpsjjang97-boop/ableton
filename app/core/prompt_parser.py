"""
Prompt Parser — keyword-based natural language parser for music generation.

Extracts generation parameters (key, scale, style, mood, BPM, etc.) from
free-text prompts in both Korean and English.  No LLM dependency — pure
regex / keyword matching.
"""
from __future__ import annotations

import re
from typing import Optional


class PromptParser:
    """Parse a free-text music prompt into structured generation parameters."""

    # ── Flat/sharp normalisation (all mapped to sharps) ──────────────────
    _ENHARMONIC: dict[str, str] = {
        "Bb": "A#", "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#",
        "bb": "A#", "db": "C#", "eb": "D#", "gb": "F#", "ab": "G#",
    }

    # ── English key regex  e.g. "C minor", "Bb major", "Cm", "F#m" ──────
    #    group 1 = root (A-G optionally with # or b)
    #    group 2 = quality hint (m / min / minor / maj / major or empty)
    _EN_KEY_RE = re.compile(
        r'\b([A-Ga-g][#b]?)\s*'
        r'(minor|major|min|maj|m(?!aj|in|ix|ol|oo|on|ar|ut|id))?\b',
        re.IGNORECASE,
    )

    # ── Korean solfege key map ───────────────────────────────────────────
    #  다=C 라=D 마=E 바=F 사=G 가=A 나=B
    _KR_SOLFEGE: dict[str, str] = {
        "다": "C", "라": "D", "마": "E", "바": "F",
        "사": "G", "가": "A", "나": "B",
    }

    # Korean key regex:  e.g. "다장조", "가단조", "라장조"
    _KR_KEY_RE = re.compile(
        r'([다라마바사가나])\s*(장조|단조)',
    )

    # Also match e.g. "D장조" or "C#단조" (western root + Korean quality)
    _MIX_KEY_RE = re.compile(
        r'([A-Ga-g][#b]?)\s*(장조|단조)',
    )

    # ── Style maps ───────────────────────────────────────────────────────
    _STYLE_MAP: dict[str, str] = {
        # English
        "ballad": "ballad", "jazz": "jazz", "classical": "classical",
        "pop": "pop", "edm": "edm", "electronic": "edm",
        "rock": "rock", "r&b": "rnb", "rnb": "rnb",
        "hiphop": "hiphop", "hip-hop": "hiphop", "hip hop": "hiphop",
        "bossa nova": "bossa_nova", "bossa": "bossa_nova",
        "waltz": "waltz", "blues": "blues", "funk": "funk",
        "ambient": "ambient", "lo-fi": "lofi", "lofi": "lofi",
        "cinematic": "cinematic", "new age": "new_age",
        # Korean
        "발라드": "ballad", "재즈": "jazz", "클래식": "classical",
        "팝": "pop", "일렉": "edm", "록": "rock",
        "알앤비": "rnb", "힙합": "hiphop", "보사노바": "bossa_nova",
        "왈츠": "waltz", "블루스": "blues", "펑크": "funk",
        "앰비언트": "ambient", "로파이": "lofi", "시네마틱": "cinematic",
        "뉴에이지": "new_age",
    }

    # ── Mood maps ────────────────────────────────────────────────────────
    _MOOD_MAP: dict[str, str] = {
        # English
        "sad": "sad", "melancholy": "sad", "sorrowful": "sad",
        "bright": "bright", "happy": "bright", "cheerful": "bright",
        "dark": "dark", "gloomy": "dark",
        "energetic": "energetic", "upbeat": "energetic", "lively": "energetic",
        "calm": "calm", "peaceful": "calm", "gentle": "calm", "soft": "calm",
        "dreamy": "dreamy", "ethereal": "dreamy",
        "epic": "epic", "grand": "epic", "majestic": "epic",
        "warm": "warm", "cozy": "warm",
        "tense": "tense", "dramatic": "dramatic",
        "romantic": "romantic",
        # Korean
        "슬픈": "sad", "우울한": "sad",
        "밝은": "bright", "행복한": "bright",
        "어두운": "dark",
        "신나는": "energetic",
        "잔잔한": "calm", "편안한": "calm",
        "몽환적": "dreamy", "몽환적인": "dreamy",
        "웅장한": "epic",
        "따뜻한": "warm",
        "긴장감": "tense", "긴장감있는": "tense",
        "드라마틱": "dramatic", "드라마틱한": "dramatic",
        "로맨틱": "romantic", "로맨틱한": "romantic",
    }

    # ── Density maps ─────────────────────────────────────────────────────
    _DENSITY_MAP: dict[str, float] = {
        # English
        "sparse": 0.2, "thin": 0.3,
        "gentle": 0.4, "light": 0.4, "soft": 0.4,
        "moderate": 0.5, "medium": 0.5,
        "dense": 0.7, "thick": 0.8, "heavy": 0.8, "full": 0.8,
        # Korean
        "가벼운": 0.3, "얇은": 0.3,
        "보통": 0.5,
        "두꺼운": 0.8, "풍성한": 0.8,
    }

    # ── Accompaniment pattern maps ───────────────────────────────────────
    _PATTERN_MAP: dict[str, str] = {
        # English
        "arpeggio": "arpeggio", "arpeggiated": "arpeggio", "broken": "arpeggio",
        "block": "block_chord", "block chord": "block_chord",
        "walking": "walking", "walking bass": "walking",
        "strum": "strum", "strumming": "strum",
        "tremolo": "tremolo", "ostinato": "ostinato",
        "alberti": "alberti",
        # Korean
        "아르페지오": "arpeggio",
        "블록코드": "block_chord", "블록": "block_chord",
        "워킹": "walking", "워킹베이스": "walking",
        "스트럼": "strum",
        "트레몰로": "tremolo", "오스티나토": "ostinato",
        "알베르티": "alberti",
    }

    # ── Reference (composer / artist) maps ───────────────────────────────
    _REFERENCE_MAP: dict[str, str] = {
        # English
        "chopin": "chopin", "debussy": "debussy",
        "beethoven": "beethoven", "mozart": "mozart",
        "bach": "bach", "liszt": "liszt", "rachmaninoff": "rachmaninoff",
        "bill evans": "bill_evans", "keith jarrett": "keith_jarrett",
        "oscar peterson": "oscar_peterson",
        "erik satie": "satie", "satie": "satie",
        "ravel": "ravel", "brahms": "brahms",
        # Korean
        "쇼팽": "chopin", "드뷔시": "debussy",
        "베토벤": "beethoven", "모차르트": "mozart",
        "바흐": "bach", "리스트": "liszt", "라흐마니노프": "rachmaninoff",
        "빌에반스": "bill_evans", "키스자렛": "keith_jarrett",
        "에릭사티": "satie", "사티": "satie",
        "라벨": "ravel", "브람스": "brahms",
    }

    # ── Track type keywords ──────────────────────────────────────────────
    _TRACK_TYPE_MAP: dict[str, str] = {
        "melody": "melody", "멜로디": "melody",
        "chord": "chords", "chords": "chords", "코드": "chords",
        "bass": "bass", "베이스": "bass",
        "pad": "pad", "패드": "pad",
        "string": "strings", "strings": "strings", "스트링": "strings",
    }

    # ── BPM regex ────────────────────────────────────────────────────────
    _BPM_RE = re.compile(r'(\d{2,3})\s*bpm', re.IGNORECASE)
    _BPM_RE_KR = re.compile(r'bpm\s*(\d{2,3})', re.IGNORECASE)

    # ── Tempo keywords ───────────────────────────────────────────────────
    _TEMPO_KEYWORDS: dict[str, int] = {
        "fast": 20, "빠른": 20, "upbeat": 15,
        "slow": -20, "느린": -20,
        "very fast": 40, "매우빠른": 40,
        "very slow": -40, "매우느린": -40,
    }

    # ── Octave keywords ─────────────────────────────────────────────────
    _OCTAVE_MAP: dict[str, int] = {
        "high": 5, "높은": 5,
        "low": 3, "낮은": 3,
        "mid": 4, "중간": 4,
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, prompt: str) -> dict:
        """Extract generation parameters from free-text *prompt*.

        Returns a dict with any subset of:
            key, scale, style, mood, density, bpm,
            accompaniment_pattern, reference, track_type, octave
        """
        result: dict = {}
        text = prompt.strip()
        text_lower = text.lower()

        # 1. Key / scale — Korean first (more specific), then English
        self._parse_key(text, text_lower, result)

        # 2. Style
        self._parse_from_map(text, text_lower, self._STYLE_MAP, "style", result)

        # 3. Mood
        self._parse_from_map(text, text_lower, self._MOOD_MAP, "mood", result)

        # 4. Density
        self._parse_from_map(text, text_lower, self._DENSITY_MAP, "density", result)

        # 5. Accompaniment pattern
        self._parse_from_map(text, text_lower, self._PATTERN_MAP,
                             "accompaniment_pattern", result)

        # 6. Reference
        self._parse_from_map(text, text_lower, self._REFERENCE_MAP,
                             "reference", result)

        # 7. Track type
        self._parse_from_map(text, text_lower, self._TRACK_TYPE_MAP,
                             "track_type", result)

        # 8. BPM (explicit number)
        self._parse_bpm(text, text_lower, result)

        # 9. Octave
        self._parse_from_map(text, text_lower, self._OCTAVE_MAP, "octave", result)

        return result

    def merge_with_ui(self, prompt_params: dict, ui_params: dict) -> dict:
        """Merge prompt-derived params with UI dropdown params.

        Prompt params override UI params where both specify the same key.
        """
        merged = dict(ui_params)
        merged.update({k: v for k, v in prompt_params.items() if v is not None})
        return merged

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise_root(self, root: str) -> str:
        """Normalise a root name to sharp-only representation."""
        # Capitalise first letter
        root = root[0].upper() + root[1:] if len(root) > 1 else root.upper()
        return self._ENHARMONIC.get(root, root)

    def _parse_key(self, text: str, text_lower: str, result: dict) -> None:
        """Extract key and scale from text."""
        # --- Korean solfege: 다장조, 가단조, etc. ---
        m = self._KR_KEY_RE.search(text)
        if m:
            solfege, quality = m.group(1), m.group(2)
            root = self._KR_SOLFEGE.get(solfege, "C")
            result["key"] = self._normalise_root(root)
            result["scale"] = "major" if quality == "장조" else "minor"
            return

        # --- Mixed: Western root + Korean quality: D장조, C#단조 ---
        m = self._MIX_KEY_RE.search(text)
        if m:
            root, quality = m.group(1), m.group(2)
            result["key"] = self._normalise_root(root)
            result["scale"] = "major" if quality == "장조" else "minor"
            return

        # --- English: "in Cm", "Bb major", "F# minor", "D minor" ---
        # Find all matches; prefer ones preceded by "in " or at word boundary
        best = None
        for m in self._EN_KEY_RE.finditer(text):
            root_raw = m.group(1)
            qual_raw = (m.group(2) or "").lower()
            # Skip if root looks like a common English word (a, e, etc.)
            # but allow if followed by a quality indicator or '#'/'b'
            if len(root_raw) == 1 and root_raw.lower() in ("a", "e") and not qual_raw:
                # Only accept bare A/E if preceded by "in " or "key"
                pre = text[max(0, m.start() - 4):m.start()].lower()
                if "in " not in pre and "key" not in pre:
                    continue
            best = m
            # If preceded by "in ", this is almost certainly the key
            pre = text[max(0, m.start() - 4):m.start()].lower()
            if "in " in pre:
                break

        if best:
            root_raw = best.group(1)
            qual_raw = (best.group(2) or "").lower()
            result["key"] = self._normalise_root(root_raw)
            if qual_raw in ("m", "min", "minor"):
                result["scale"] = "minor"
            elif qual_raw in ("maj", "major"):
                result["scale"] = "major"
            else:
                result["scale"] = "major"  # default

    def _parse_from_map(
        self,
        text: str,
        text_lower: str,
        mapping: dict,
        target_key: str,
        result: dict,
    ) -> None:
        """Find the first matching keyword from *mapping* in text."""
        # Sort by length descending so longer phrases match first
        for keyword in sorted(mapping, key=len, reverse=True):
            # Check if keyword contains only ASCII (English)
            if keyword.isascii():
                if keyword in text_lower:
                    result[target_key] = mapping[keyword]
                    return
            else:
                # Korean — check in original text
                if keyword in text:
                    result[target_key] = mapping[keyword]
                    return

    def _parse_bpm(self, text: str, text_lower: str, result: dict) -> None:
        """Extract BPM from text, either explicit number or tempo keyword."""
        # Explicit BPM number
        m = self._BPM_RE.search(text) or self._BPM_RE_KR.search(text)
        if m:
            bpm = int(m.group(1))
            if 30 <= bpm <= 300:
                result["bpm"] = bpm
                return

        # Tempo keywords (apply delta to a default of 120)
        for keyword in sorted(self._TEMPO_KEYWORDS, key=len, reverse=True):
            if keyword.isascii():
                if keyword in text_lower:
                    result["bpm"] = 120 + self._TEMPO_KEYWORDS[keyword]
                    return
            else:
                if keyword in text:
                    result["bpm"] = 120 + self._TEMPO_KEYWORDS[keyword]
                    return
