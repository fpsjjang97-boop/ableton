/*
 * MidiGPT VST3 Plugin — PerformanceHUD
 *
 * Sprint 36 AAA4. Debug overlay showing real-time metrics:
 *   - Last generation latency (ms)
 *   - Server RTT (ms, from health ping)
 *   - Captured notes / second (running EMA)
 *   - Scheduled output queue depth
 *
 * Hidden by default; toggle via Ctrl+Shift+D (wired in PluginEditor).
 * Rendering is dirt cheap (one std::ostringstream, drawText) — the purpose
 * is sanity checking, not precision profiling.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

class PerformanceHUD : public juce::Component
{
public:
    PerformanceHUD()
    {
        setInterceptsMouseClicks (false, false);
    }

    void setGenerationLatencyMs (double ms)   { lastGenMs = ms;   repaint(); }
    void setServerRttMs (double ms)           { lastRttMs = ms;   repaint(); }
    void setCapturedCount (int count)
    {
        // EMA-ish running rate: assume repaints happen ~1Hz (they do, via
        // PluginEditor's timer). Delta since last call ≈ notes / sec.
        const int delta = juce::jmax (0, count - lastCaptured);
        lastCaptured = count;
        emaNotesPerSec = 0.7 * emaNotesPerSec + 0.3 * delta;
        repaint();
    }
    void setQueueDepth (int depth)            { queueDepth = depth; repaint(); }

    void paint (juce::Graphics& g) override
    {
        const auto bounds = getLocalBounds().toFloat();
        g.setColour (juce::Colours::black.withAlpha (0.55f));
        g.fillRoundedRectangle (bounds, 4.0f);

        g.setColour (juce::Colours::lightgreen);
        g.setFont (juce::Font (juce::Font::getDefaultMonospacedFontName(), 11.0f, 0));

        auto line = [&] (int y, const juce::String& s)
        {
            g.drawText (s, 8, y, getWidth() - 16, 14, juce::Justification::centredLeft);
        };
        line (2,  "gen:  " + (lastGenMs >= 0 ? juce::String (lastGenMs, 0) + " ms" : juce::String ("-")));
        line (18, "rtt:  " + (lastRttMs >= 0 ? juce::String (lastRttMs, 0) + " ms" : juce::String ("-")));
        line (34, "n/s:  " + juce::String (emaNotesPerSec, 1));
        line (50, "q:    " + juce::String (queueDepth));
    }

private:
    double lastGenMs     { -1.0 };
    double lastRttMs     { -1.0 };
    int    lastCaptured  { 0 };
    double emaNotesPerSec { 0.0 };
    int    queueDepth    { 0 };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (PerformanceHUD)
};
