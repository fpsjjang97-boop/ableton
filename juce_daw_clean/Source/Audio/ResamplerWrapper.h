/*
 * MidiGPT DAW — ResamplerWrapper (Sprint 49 NNN1)
 *
 * Backend-agnostic sample-rate conversion facade. The standalone DAW and
 * the VST plugin both go through this class so the underlying resampler
 * can be swapped without touching call sites.
 *
 * Backends:
 *   - JUCE LagrangeInterpolator   (default, always compiled)
 *   - r8brain-free-src            (opt-in via MIDIGPTDAW_WITH_R8BRAIN)
 *
 * NNN1 scope: scaffold only. Existing audio-clip playback in
 * AudioEngine.cpp (Catmull-Rom inline, U4) and OfflineRenderer are NOT
 * re-wired yet — that migration happens in NNN3/NNN4.
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

#include <memory>
#include <vector>

namespace midigpt_daw
{

class ResamplerWrapper
{
public:
    ResamplerWrapper();
    ~ResamplerWrapper();

    /** Prepare for a new SR conversion. Resets per-channel state so
        successive prepare() calls are safe (does not hold allocations
        across changes in channel count). */
    void prepare (double sourceSr,
                  double destSr,
                  int    numChannels,
                  int    maxBlockSamples);

    /** Resample one block.
        @param src  Input [numChannels][numInSamples].
        @param dst  Output [numChannels][numOutSamples]. Caller sizes it —
                    numOutSamples drives how much is produced.
        @returns    Number of output samples actually written per channel. */
    int process (const juce::AudioBuffer<float>& src,
                 juce::AudioBuffer<float>&       dst);

    /** source/dest ratio (> 1 = upsampling consumes more source per output). */
    double ratio()        const noexcept { return sourceOverDest; }
    bool   isBypass()     const noexcept { return bypass; }
    bool   isPrepared()   const noexcept { return prepared; }
    const char* backendName() const noexcept;

private:
    double sourceOverDest { 1.0 };
    int    channels       { 0 };
    bool   bypass         { true };
    bool   prepared       { false };

    // JUCE fallback backend — compiled unconditionally. Per-channel
    // streaming state so successive process() calls are seamless.
    std::vector<juce::LagrangeInterpolator> lagrange;

   #if MIDIGPTDAW_WITH_R8BRAIN
    // r8brain pimpl — keeps r8brain headers out of this public interface.
    struct R8Impl;
    std::unique_ptr<R8Impl> r8;
   #endif
};

} // namespace midigpt_daw
