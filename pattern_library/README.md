# Pattern Library

Auto-accumulated pattern database for the MIDI AI Workstation.

## Structure

```
pattern_library/
├── chord_progressions.json   — Common chord progression n-grams
├── voicing_examples.json     — Style-specific voicing examples
├── form_templates.json       — Song structure templates
├── bass_patterns.json        — Genre-specific bass patterns
├── rhythm_patterns.json      — Rhythmic pattern library
└── genre_statistics.json     — Cross-corpus genre statistics
```

## Status

| File | Status | Min. Corpus Required |
|------|--------|---------------------|
| chord_progressions.json | Skeleton | 100 analyzed files |
| voicing_examples.json | Skeleton | 100 analyzed files |
| form_templates.json | Skeleton | 100 analyzed files |
| bass_patterns.json | Not started | 200 analyzed files |
| rhythm_patterns.json | Not started | 200 analyzed files |
| genre_statistics.json | Not started | 500 analyzed files |

## Auto-Accumulation

Once `analyzed_chords/` reaches 100+ files, run:
```bash
cd tools && python build_pattern_library.py
```

This extracts patterns from all analyzed files and regenerates this library.
The library is automatically consulted by HarmonyEngine for:
- Chord progression prediction (next-chord suggestion)
- Voicing selection (style-matched examples)
- Song form inference (statistical priors)
