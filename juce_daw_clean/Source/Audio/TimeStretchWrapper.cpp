/*
 * MidiGPT DAW — TimeStretchWrapper implementation (Sprint 50 OOO1)
 *
 * See TimeStretchWrapper.h for backend-selection rationale + licence note.
 */

#include "TimeStretchWrapper.h"

#if MIDIGPTDAW_WITH_RUBBERBAND
 #include <rubberband/RubberBandStretcher.h>
 #include <vector>
#endif

namespace midigpt_daw
{

#if MIDIGPTDAW_WITH_RUBBERBAND
struct TimeStretchWrapper::RBImpl
{
    // No persistent state — a RubberBandStretcher is constructed per
    // stretch() call for one-shot offline transforms. If a later sub-sprint
    // adds RT mode, hold a long-lived stretcher (and input/output ring
    // buffers) here.
};
#endif

TimeStretchWrapper::TimeStretchWrapper()  = default;
TimeStretchWrapper::~TimeStretchWrapper() = default;

bool TimeStretchWrapper::stretch (const juce::AudioBuffer<float>& src,
                                   juce::AudioBuffer<float>&       dst,
                                   double sampleRate,
                                   double timeRatio,
                                   double pitchScale)
{
    const int numCh = juce::jmin (src.getNumChannels(), dst.getNumChannels());
    const int numIn = src.getNumSamples();
    if (numCh <= 0 || numIn <= 0) return false;
    if (sampleRate <= 0.0 || timeRatio <= 0.0 || pitchScale <= 0.0) return false;

   #if MIDIGPTDAW_WITH_RUBBERBAND
    using RB = RubberBand::RubberBandStretcher;

    // OptionEngineFiner (R3) — higher quality, higher CPU. For offline
    // clip-level apply this trade-off is fine. For RT use a later sprint
    // will switch to OptionEngineFaster.
    RB stretcher (
        (size_t) sampleRate,
        (size_t) numCh,
        RB::OptionProcessOffline | RB::OptionEngineFiner,
        timeRatio,
        pitchScale);

    stretcher.setExpectedInputDuration ((size_t) numIn);

    std::vector<const float*> inPtrs ((size_t) numCh);
    for (int ch = 0; ch < numCh; ++ch)
        inPtrs[(size_t) ch] = src.getReadPointer (ch);

    // Offline: study + process in one shot, marking `final=true` to flush.
    stretcher.study   (inPtrs.data(), (size_t) numIn, true);
    stretcher.process (inPtrs.data(), (size_t) numIn, true);

    const int dstCap = dst.getNumSamples();
    int outPos = 0;
    std::vector<float*> outPtrs ((size_t) numCh);
    while (outPos < dstCap)
    {
        const int avail = stretcher.available();
        if (avail <= 0) break;
        const int toRead = juce::jmin (avail, dstCap - outPos);
        for (int ch = 0; ch < numCh; ++ch)
            outPtrs[(size_t) ch] = dst.getWritePointer (ch) + outPos;

        const size_t got = stretcher.retrieve (outPtrs.data(), (size_t) toRead);
        if (got == 0) break;          // safety against infinite loop
        outPos += (int) got;
    }
    return outPos > 0;
   #else
    // Default build — passthrough copy. Callers should inspect hasBackend()
    // and fall back to AudioClip.playbackRate (coupled pitch+time) when
    // TimeStretchWrapper reports no backend.
    juce::ignoreUnused (sampleRate, timeRatio, pitchScale);
    const int n = juce::jmin (numIn, dst.getNumSamples());
    for (int ch = 0; ch < numCh; ++ch)
        dst.copyFrom (ch, 0, src, ch, 0, n);
    return false;
   #endif
}

bool TimeStretchWrapper::hasBackend() const noexcept
{
   #if MIDIGPTDAW_WITH_RUBBERBAND
    return true;
   #else
    return false;
   #endif
}

const char* TimeStretchWrapper::backendName() const noexcept
{
   #if MIDIGPTDAW_WITH_RUBBERBAND
    return "rubberband v4 (R3/Finer)";
   #else
    return "(none — passthrough)";
   #endif
}

} // namespace midigpt_daw
