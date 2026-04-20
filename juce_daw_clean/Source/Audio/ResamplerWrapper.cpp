/*
 * MidiGPT DAW — ResamplerWrapper implementation (Sprint 49 NNN1)
 *
 * See ResamplerWrapper.h for the backend-selection rationale.
 */

#include "ResamplerWrapper.h"

#if MIDIGPTDAW_WITH_R8BRAIN
 #include "CDSPResampler.h"   // r8brain-free-src public header
#endif

#include <cmath>

namespace midigpt_daw
{

#if MIDIGPTDAW_WITH_R8BRAIN
struct ResamplerWrapper::R8Impl
{
    // One resampler per channel. r8brain is double-precision internally,
    // so we keep scratch buffers for float <-> double conversion.
    std::vector<std::unique_ptr<r8b::CDSPResampler24>> resamplers;
    std::vector<std::vector<double>> scratchIn;
    std::vector<std::vector<double>> scratchOut;
};
#endif

ResamplerWrapper::ResamplerWrapper()  = default;
ResamplerWrapper::~ResamplerWrapper() = default;

void ResamplerWrapper::prepare (double sourceSr,
                                double destSr,
                                int    numChannels,
                                int    maxBlockSamples)
{
    jassert (sourceSr > 0.0 && destSr > 0.0);
    jassert (numChannels > 0);
    jassert (maxBlockSamples > 0);

    sourceOverDest = sourceSr / destSr;
    channels       = numChannels;
    bypass         = std::abs (sourceSr - destSr) < 1.0e-6;
    prepared       = true;

    // Fallback backend: fresh Lagrange state per channel.
    lagrange.assign ((size_t) numChannels, juce::LagrangeInterpolator{});

   #if MIDIGPTDAW_WITH_R8BRAIN
    r8 = std::make_unique<R8Impl>();
    r8->resamplers.clear();
    r8->scratchIn .assign ((size_t) numChannels, std::vector<double> ((size_t) maxBlockSamples));
    const int maxOut = (int) std::ceil ((double) maxBlockSamples / sourceOverDest) + 8;
    r8->scratchOut.assign ((size_t) numChannels, std::vector<double> ((size_t) maxOut));

    for (int ch = 0; ch < numChannels; ++ch)
    {
        r8->resamplers.emplace_back (
            std::make_unique<r8b::CDSPResampler24> (sourceSr, destSr, maxBlockSamples));
    }
   #else
    juce::ignoreUnused (maxBlockSamples);
   #endif
}

int ResamplerWrapper::process (const juce::AudioBuffer<float>& src,
                                juce::AudioBuffer<float>&       dst)
{
    jassert (prepared);

    // NB: the 3-arg juce::jmin overload is variadic in modern JUCE, but
    // nesting the 2-arg form keeps this compiling against older pins.
    const int numCh = juce::jmin (src.getNumChannels(),
                                  juce::jmin (dst.getNumChannels(), channels));
    if (numCh == 0) return 0;

    const int numIn  = src.getNumSamples();
    const int numOut = dst.getNumSamples();
    if (numIn == 0 || numOut == 0) return 0;

    if (bypass)
    {
        const int n = juce::jmin (numIn, numOut);
        for (int ch = 0; ch < numCh; ++ch)
            dst.copyFrom (ch, 0, src, ch, 0, n);
        return n;
    }

   #if MIDIGPTDAW_WITH_R8BRAIN
    if (r8 != nullptr && ! r8->resamplers.empty())
    {
        int produced = 0;
        for (int ch = 0; ch < numCh; ++ch)
        {
            auto& inDouble  = r8->scratchIn [(size_t) ch];
            if ((int) inDouble.size() < numIn) inDouble.resize ((size_t) numIn);

            const float* srcPtr = src.getReadPointer (ch);
            for (int i = 0; i < numIn; ++i) inDouble[(size_t) i] = (double) srcPtr[i];

            double* outPtr = nullptr;
            const int outN = r8->resamplers[(size_t) ch]->process (
                inDouble.data(), numIn, outPtr);

            const int writeN = juce::jmin (outN, numOut);
            float* dstPtr = dst.getWritePointer (ch);
            for (int i = 0; i < writeN; ++i) dstPtr[i] = (float) outPtr[i];

            if (ch == 0) produced = writeN;
        }
        return produced;
    }
   #endif

    // JUCE Lagrange fallback.
    for (int ch = 0; ch < numCh; ++ch)
    {
        lagrange[(size_t) ch].process (sourceOverDest,
                                       src.getReadPointer (ch),
                                       dst.getWritePointer (ch),
                                       numOut);
    }
    return numOut;
}

const char* ResamplerWrapper::backendName() const noexcept
{
   #if MIDIGPTDAW_WITH_R8BRAIN
    return "r8brain-free-src";
   #else
    return "JUCE-Lagrange";
   #endif
}

} // namespace midigpt_daw
