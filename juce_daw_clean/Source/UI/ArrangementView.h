/*
 * MidiGPT DAW - ArrangementView
 *
 * Timeline view: track headers + clip grid + playhead.
 * Supports: zoom/scroll, clip creation (double-click), clip selection,
 * track context menu (rename/delete/instrument/colour).
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/TrackModel.h"
#include "../Core/AudioEngine.h"

class ArrangementView : public juce::Component,
                        public juce::Timer
{
public:
    explicit ArrangementView(AudioEngine& engine);

    void paint(juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    void mouseDown(const juce::MouseEvent& e) override;
    void mouseDoubleClick(const juce::MouseEvent& e) override;
    void mouseWheelMove(const juce::MouseEvent& e, const juce::MouseWheelDetails& w) override;

    std::function<void(MidiClip*)> onClipSelected;
    std::function<void()> onTrackListChanged;

private:
    AudioEngine& audioEngine;

    static constexpr int trackHeight = 48;
    static constexpr int headerWidth = 160;

    float beatsVisible { 64.0f };
    float scrollXBeats { 0.0f };
    int scrollYPixels { 0 };

    float beatToX(double beat) const;
    double xToBeat(float x) const;

    void showTrackContextMenu(int trackIdx);

    juce::TextButton addTrackButton { "+ Track" };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ArrangementView)
};
