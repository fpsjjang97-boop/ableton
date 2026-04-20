/*
 * MidiGPT DAW — ClipStretchUtil implementation (Sprint 50 OOO2)
 */

#include "ClipStretchUtil.h"
#include "AudioClip.h"
#include "TimeStretchWrapper.h"

#include <cmath>

namespace midigpt_daw
{

StretchResult stretchAudioClip (AudioClip& clip,
                                double    timeRatio,
                                double    pitchScale)
{
    StretchResult r;

    TimeStretchWrapper wrapper;
    r.backend = wrapper.backendName();

    if (clip.isEmpty())                  { r.reason = "empty clip";              return r; }
    if (timeRatio  <= 0.0)               { r.reason = "timeRatio <= 0";          return r; }
    if (pitchScale <= 0.0)               { r.reason = "pitchScale <= 0";         return r; }
    if (clip.sourceSampleRate <= 0.0)    { r.reason = "invalid sourceSampleRate"; return r; }
    if (! wrapper.hasBackend())          { r.reason = "no stretch backend — fall back to playbackRate"; return r; }

    const int numCh = clip.buffer.getNumChannels();
    const int numIn = clip.buffer.getNumSamples();

    // RubberBand R3 can overshoot its theoretical output size by a small
    // amount during tail flush; pad by 2048 samples for safety plus the
    // ratio-scaled length.
    const int numOutCap = (int) std::ceil ((double) numIn * timeRatio) + 2048;

    juce::AudioBuffer<float> dst (numCh, numOutCap);
    dst.clear();

    const int produced = wrapper.stretch (
        clip.buffer, dst,
        clip.sourceSampleRate,
        timeRatio, pitchScale);

    if (produced <= 0)
    {
        r.reason = "stretch() returned 0 samples";
        return r;
    }

    // Trim the overallocated tail. setSize(keepExistingContent=true)
    // preserves what we wrote and releases the rest of the capacity.
    dst.setSize (numCh, produced, /*keep*/ true, /*clearExtra*/ false, /*avoidReallocating*/ false);

    // Commit changes to the clip. sourceOffsetSamples is left alone: its
    // meaning (offset into the buffer where playback begins) still applies,
    // though the caller may want to reset it to 0 if the stretch is
    // intended as a "freeze the trim" step as well.
    clip.buffer          = std::move (dst);
    clip.lengthBeats    *= timeRatio;
    clip.pitchSemitones  = 0.0f;
    clip.playbackRate    = 1.0;

    r.success    = true;
    r.outSamples = produced;
    r.reason     = "";
    return r;
}

} // namespace midigpt_daw
