# MidiGPT Sample Library

This folder ships with the plugin's **built-in MIDI sample library**
(Sprint 36 AAA3).

On first run, `SampleGallery::installIfMissing()` copies all `*.mid` +
`*.txt` files from here into the user's data directory
(`<userAppData>/MidiGPT/samples/`). The plugin UI then exposes them via
**"Load Sample"** in the editor.

## Conventions

- **`<name>.mid`** — the sample MIDI itself. Keep small (< 32 KB, typically
  2–8 bars). Preferred tempo: 90–140 BPM, time signature 4/4 unless the
  style needs otherwise.
- **`<name>.txt`** *(optional)* — a single line (or short paragraph)
  describing the sample. Displayed next to the menu entry.
- Filename becomes the menu label (minus the `.mid` extension).

## Adding a new sample

1. Drop the `.mid` and optional `.txt` into this directory.
2. Commit (see `rules/04-commit-discipline.md` §4.4 — small MIDI files OK,
   but no full-song dumps).
3. Users get it on next plugin launch (the installer runs on first open).

## Suggested starter pack (to be filled in)

| Name | Style | Why |
|------|-------|-----|
| city_pop_4bars.mid | City pop | Showcase the default LoRA |
| jazz_ii_V_I.mid    | Jazz    | Harmonic-aware generation demo |
| metal_riff_2bars.mid | Metal | Stress-test the rhythm section |
| ambient_pad.mid    | Ambient | Sparse texture — easy to continue |
| classical_melody.mid | Classical | No drums — pure melodic continuation |

Placeholder only — actual `.mid` files to be added in a future
pass / external contribution.
