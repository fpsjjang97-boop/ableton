/*
 * MidiGPT DAW — TimeStretchWrapper (Sprint 50 OOO1)
 *
 * Offline pitch/time-independent stretch facade. The standalone DAW
 * routes AudioClip pitch/time adjustments through this class so the
 * underlying engine (currently RubberBand when opted in) can be swapped.
 *
 * Backends:
 *   - RubberBand v4 (opt-in via MIDIGPTDAW_WITH_RUBBERBAND — GPL!)
 *   - Default: copy passthrough + hasBackend() == false. Callers that
 *     need pitch/time independence should check hasBackend() and fall
 *     back to AudioClip.playbackRate (which couples pitch + time) when
 *     RubberBand is not available.
 *
 * OOO1 scope: scaffold only. AudioClip offline "Apply stretch" UI is
 * NOT wired yet — that lands in OOO2.
 *
 * License note: RubberBand is licensed GPL-v2+ OR commercial (Breakfast
 * Quay). Enabling MIDIGPTDAW_WITH_RUBBERBAND and distributing the resulting
 * binary requires GPL compliance or a paid commercial licence. Leaving
 * the option OFF keeps the default build license-clean.
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

#include <memory>

namespace midigpt_daw
{

class TimeStretchWrapper
{
public:
    TimeStretchWrapper();
    ~TimeStretchWrapper();

    /** Offline pitch + time stretch of a whole buffer.
        @param src         Input [numChannels][inSamples].
        @param dst         Output [numChannels][outSamples]. Caller should
                           size dst.numSamples() to about
                           ceil(inSamples * timeRatio) + backend-pad.
        @param sampleRate  Sample rate of both src and dst.
        @param timeRatio   > 1.0 stretches longer; < 1.0 shorter.
        @param pitchScale  > 1.0 shifts up; < 1.0 shifts down.
        @returns Number of output samples written per channel. 0 if no
                 backend is available (hasBackend() == false) OR inputs
                 are invalid. The passthrough path also returns 0 so
                 callers treat "nothing happened" uniformly. */
    int stretch (const juce::AudioBuffer<float>& src,
                 juce::AudioBuffer<float>&       dst,
                 double sampleRate,
                 double timeRatio,
                 double pitchScale);

    /** Does this build contain a real backend? False = the default build
        where stretch() copies without adjusting anything. */
    bool        hasBackend()  const noexcept;
    const char* backendName() const noexcept;

private:
   #if MIDIGPTDAW_WITH_RUBBERBAND
    // Forward-declared pimpl so rubberband/RubberBandStretcher.h does not
    // leak into this public header.
    struct RBImpl;
    std::unique_ptr<RBImpl> rb;
   #endif
};

} // namespace midigpt_daw
