/*
 * MidiGPT DAW — TimeStretchWrapper + ClipStretchUtil test harness
 * Sprint 50 OOO5
 *
 * Mirrors the NNN3 pattern (test_resampler.cpp). Validates the offline
 * pitch/time stretch path with synthetic inputs.
 *
 * Build-mode split:
 *   - Default (no MIDIGPTDAW_WITH_RUBBERBAND): TimeStretchWrapper has no
 *     backend. Tests verify stretch() returns 0 AND stretchAudioClip()
 *     leaves the clip untouched with a descriptive reason.
 *   - With RubberBand: stretch() produces ~timeRatio*inSamples output,
 *     pitch-shifted content, and clip fields update correctly.
 *
 * Exit codes: 0 pass, 1 fail, 2 harness error.
 */

#include "../Source/Audio/AudioClip.h"
#include "../Source/Audio/ClipStretchUtil.h"
#include "../Source/Audio/TimeStretchWrapper.h"

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_core/juce_core.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <vector>

namespace
{

void fillSine (juce::AudioBuffer<float>& buf, double freq, double sr, float amp = 0.5f)
{
    const int numCh = buf.getNumChannels();
    const int n     = buf.getNumSamples();
    for (int ch = 0; ch < numCh; ++ch)
    {
        auto* dst = buf.getWritePointer (ch);
        for (int i = 0; i < n; ++i)
            dst[i] = amp * (float) std::sin (2.0 * juce::MathConstants<double>::pi
                                              * freq * (double) i / sr);
    }
}

// Estimate dominant frequency by counting zero-crossings. Good enough
// for pure-sine validation without an FFT dep.
double zeroCrossingHz (const float* data, int n, double sr)
{
    if (n < 4 || sr <= 0.0) return 0.0;
    int crossings = 0;
    for (int i = 1; i < n; ++i)
    {
        const bool prevPos = data[i - 1] >= 0.0f;
        const bool curPos  = data[i]     >= 0.0f;
        if (prevPos != curPos) ++crossings;
    }
    const double seconds = (double) n / sr;
    // Two zero-crossings per cycle.
    return (double) crossings / (2.0 * seconds);
}

struct Result { juce::String name; bool passed; juce::String detail; };

// -- Default build (no backend) tests --------------------------------------

Result testNoBackendReport()
{
    midigpt_daw::TimeStretchWrapper w;
   #if MIDIGPTDAW_WITH_RUBBERBAND
    if (! w.hasBackend())
        return { "hasBackend-rb", false, "expected true with rubberband build" };
   #else
    if (w.hasBackend())
        return { "hasBackend-nobackend", false, "expected false in default build" };
   #endif
    return { "hasBackend", true, w.backendName() };
}

Result testNoBackendPassthrough()
{
   #if MIDIGPTDAW_WITH_RUBBERBAND
    return { "no-backend-passthrough", true, "skipped (rubberband build)" };
   #else
    midigpt_daw::TimeStretchWrapper w;
    juce::AudioBuffer<float> src (1, 4096), dst (1, 8192);
    fillSine (src, 440.0, 48000.0);
    dst.clear();
    const int n = w.stretch (src, dst, 48000.0, 2.0, 1.0);
    if (n != 0)
        return { "no-backend-return", false, "stretch returned " + juce::String (n) + ", expected 0" };

    // dst should still be zero (we promised not to touch it).
    double maxVal = 0.0;
    for (int i = 0; i < dst.getNumSamples(); ++i)
        maxVal = std::max (maxVal, (double) std::abs (dst.getReadPointer (0)[i]));
    if (maxVal > 1.0e-6)
        return { "no-backend-no-mutate", false,
                 "dst was modified (maxVal=" + juce::String (maxVal) + ")" };
    return { "no-backend-passthrough", true, "" };
   #endif
}

Result testClipUtilNoBackend()
{
   #if MIDIGPTDAW_WITH_RUBBERBAND
    return { "clip-util-no-backend", true, "skipped (rubberband build)" };
   #else
    AudioClip clip;
    clip.sourceSampleRate = 48000.0;
    clip.lengthBeats      = 8.0;
    clip.pitchSemitones   = 0.0f;
    clip.playbackRate     = 1.0;
    clip.buffer.setSize (2, 48000);
    fillSine (clip.buffer, 440.0, 48000.0);

    const int origSamples = clip.buffer.getNumSamples();
    const double origLen  = clip.lengthBeats;

    auto r = midigpt_daw::stretchAudioClip (clip, 2.0, 1.5);

    if (r.success)
        return { "clip-util-no-backend", false, "unexpected success in default build" };

    if (clip.buffer.getNumSamples() != origSamples)
        return { "clip-util-preserve-buffer", false, "buffer size changed on failure" };
    if (std::abs (clip.lengthBeats - origLen) > 1.0e-9)
        return { "clip-util-preserve-length", false, "lengthBeats changed on failure" };

    return { "clip-util-no-backend", true, juce::String (r.reason) };
   #endif
}

// -- RubberBand build tests ------------------------------------------------

Result testStretchTimeRatio()
{
   #if ! MIDIGPTDAW_WITH_RUBBERBAND
    return { "time-ratio", true, "skipped (no backend)" };
   #else
    midigpt_daw::TimeStretchWrapper w;
    const double sr = 48000.0;
    const int numIn = 48000;         // 1 second
    const double timeRatio = 2.0;

    juce::AudioBuffer<float> src (1, numIn);
    fillSine (src, 440.0, sr);
    juce::AudioBuffer<float> dst (1, (int) (numIn * timeRatio) + 4096);
    dst.clear();

    const int produced = w.stretch (src, dst, sr, timeRatio, 1.0);
    if (produced <= 0)
        return { "time-ratio", false, "produced=0" };

    // Expect output length within ±10% of timeRatio * numIn.
    const double expected = (double) numIn * timeRatio;
    const double err = std::abs ((double) produced - expected) / expected;
    if (err > 0.10)
        return { "time-ratio", false,
                 "produced=" + juce::String (produced)
                 + " expected≈" + juce::String (expected)
                 + " err=" + juce::String (err * 100.0, 2) + "%" };

    return { "time-ratio-2x", true,
             "produced=" + juce::String (produced)
             + " (expected≈" + juce::String (expected) + ")" };
   #endif
}

Result testStretchPitchScale()
{
   #if ! MIDIGPTDAW_WITH_RUBBERBAND
    return { "pitch-scale", true, "skipped (no backend)" };
   #else
    midigpt_daw::TimeStretchWrapper w;
    const double sr = 48000.0;
    const int numIn = 48000;
    const double pitchScale = 2.0;   // octave up

    juce::AudioBuffer<float> src (1, numIn);
    fillSine (src, 440.0, sr);
    juce::AudioBuffer<float> dst (1, numIn + 4096);
    dst.clear();

    const int produced = w.stretch (src, dst, sr, 1.0, pitchScale);
    if (produced <= 0)
        return { "pitch-scale", false, "produced=0" };

    // Skip the edges (RubberBand attack/release) and measure zero-crossings.
    const int skip = 2048;
    const int n    = juce::jmax (0, produced - 2 * skip);
    if (n < 1024) return { "pitch-scale", false, "not enough samples to measure" };

    const double estHz = zeroCrossingHz (dst.getReadPointer (0) + skip, n, sr);
    // Expect ≈880Hz; allow ±5%.
    const double expected = 440.0 * pitchScale;
    const double err = std::abs (estHz - expected) / expected;
    if (err > 0.05)
        return { "pitch-scale", false,
                 "measured=" + juce::String (estHz, 1) + "Hz"
                 + " expected≈" + juce::String (expected, 1) + "Hz" };

    return { "pitch-scale-octave", true,
             "measured=" + juce::String (estHz, 1) + "Hz" };
   #endif
}

Result testClipUtilApply()
{
   #if ! MIDIGPTDAW_WITH_RUBBERBAND
    return { "clip-util-apply", true, "skipped (no backend)" };
   #else
    AudioClip clip;
    clip.sourceSampleRate = 48000.0;
    clip.lengthBeats      = 4.0;
    clip.pitchSemitones   = 7.0f;    // should be reset to 0 after apply
    clip.playbackRate     = 1.5;     // should be reset to 1.0
    clip.buffer.setSize (1, 48000);
    fillSine (clip.buffer, 440.0, 48000.0);

    auto r = midigpt_daw::stretchAudioClip (clip, 2.0, 1.0);
    if (! r.success)
        return { "clip-util-apply", false,
                 "expected success, got: " + juce::String (r.reason) };

    // Post-conditions.
    if (std::abs (clip.lengthBeats - 8.0) > 1.0e-9)
        return { "clip-util-apply", false,
                 "lengthBeats=" + juce::String (clip.lengthBeats) + ", expected 8.0" };
    if (std::abs (clip.pitchSemitones) > 1.0e-6f)
        return { "clip-util-apply", false, "pitchSemitones not reset" };
    if (std::abs (clip.playbackRate - 1.0) > 1.0e-9)
        return { "clip-util-apply", false, "playbackRate not reset" };
    if (clip.buffer.getNumSamples() < 48000)       // should be ~96k (2x)
        return { "clip-util-apply", false,
                 "buffer shrunk: " + juce::String (clip.buffer.getNumSamples()) };

    return { "clip-util-apply", true,
             "new buffer=" + juce::String (clip.buffer.getNumSamples()) + " samples" };
   #endif
}

} // namespace

int main (int argc, char** argv)
{
    juce::ignoreUnused (argc, argv);

    std::printf ("MidiGPT TimeStretchWrapper test harness\n");
    {
        midigpt_daw::TimeStretchWrapper probe;
        std::printf ("  backend: %s (hasBackend=%s)\n\n",
                      probe.backendName(),
                      probe.hasBackend() ? "true" : "false");
    }

    std::vector<Result> results;
    results.push_back (testNoBackendReport());
    results.push_back (testNoBackendPassthrough());
    results.push_back (testClipUtilNoBackend());
    results.push_back (testStretchTimeRatio());
    results.push_back (testStretchPitchScale());
    results.push_back (testClipUtilApply());

    int failed = 0;
    for (const auto& r : results)
    {
        std::printf ("  [%s] %-30s  %s\n",
                      r.passed ? "PASS" : "FAIL",
                      r.name.toRawUTF8(),
                      r.detail.toRawUTF8());
        if (! r.passed) ++failed;
    }

    std::printf ("\n%d / %d passed\n",
                  (int) results.size() - failed, (int) results.size());
    return failed == 0 ? 0 : 1;
}
