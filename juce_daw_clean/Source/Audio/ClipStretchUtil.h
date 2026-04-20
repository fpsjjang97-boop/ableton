/*
 * MidiGPT DAW — ClipStretchUtil (Sprint 50 OOO2)
 *
 * Offline "Apply Stretch" helper that transforms an AudioClip's buffer
 * in-place via TimeStretchWrapper. Used by UI actions (menu / button)
 * to bake an AudioClip's pitch/time adjustments into its audio data,
 * replacing the coupled playbackRate path with true independent stretch.
 *
 * Not real-time. Call from the main thread (loads/save/edit), never the
 * audio callback. Allocates buffers internally.
 */

#pragma once

struct AudioClip;

namespace midigpt_daw
{

struct StretchResult
{
    bool        success    { false };  // true iff clip.buffer was replaced
    int         outSamples { 0 };       // new buffer length, per channel
    const char* backend    { "" };      // TimeStretchWrapper::backendName()
    const char* reason     { "" };      // short failure reason if !success
};

/** Apply pitch/time stretch to an AudioClip, in-place.

    On success:
      - clip.buffer is replaced with the stretched audio
      - clip.lengthBeats is multiplied by timeRatio
      - clip.pitchSemitones is reset to 0
      - clip.playbackRate   is reset to 1.0
      - clip.sourceSampleRate is unchanged (stretch preserves SR)

    On failure (no backend / bad inputs / backend returned 0 samples),
    the clip is left untouched. Callers can still fall back to the
    coupled clip.playbackRate / pitchSemitones code path. */
StretchResult stretchAudioClip (AudioClip& clip,
                                double    timeRatio,
                                double    pitchScale);

} // namespace midigpt_daw
