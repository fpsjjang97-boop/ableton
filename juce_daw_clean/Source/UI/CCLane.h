/*
 * MidiGPT DAW — CCLane
 *
 * Standalone CC editor sharing time scale with PianoRoll. Edits a single
 * MIDI controller (default CC 1 = Modulation) on the bound MidiClip.
 *
 * Click = add point at mouse position (snapped). Drag = scrub line.
 * Right-click on point = delete. Wheel = zoom (matches PianoRoll).
 *
 * Sprint scope: minimal viable editor for one CC at a time. CC selector
 * combo + multi-lane stack arrives in Sprint 4.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/TrackModel.h"
#include <functional>

class CCLane : public juce::Component
{
public:
    CCLane();

    void setClip(MidiClip* clip)         { currentClip = clip; repaint(); }
    void setRecordingPredicate(std::function<bool()> p) { isRecording = std::move(p); }
    void setController(int ccNumber)      { ccNum = juce::jlimit(0, 127, ccNumber); repaint(); }
    void setBeatWidth(float bw)           { beatWidth = bw; repaint(); }
    void setScrollX(float sx)             { scrollX = sx; repaint(); }
    void setSnapBeats(double s)           { if (s > 0.0) snapBeats = s; }

    void paint(juce::Graphics& g) override;
    void mouseDown(const juce::MouseEvent& e) override;
    void mouseDrag(const juce::MouseEvent& e) override;

    std::function<void()> onChanged;

private:
    MidiClip* currentClip { nullptr };
    int       ccNum       { 1 };
    float     beatWidth   { 40.0f };
    float     scrollX     { 0.0f };
    double    snapBeats   { 0.25 };
    std::function<bool()> isRecording;

    float beatToX(double beat) const { return (float)(beat * beatWidth - scrollX); }
    double xToBeat(float x)    const { return (x + scrollX) / beatWidth; }
    int yToValue(float y)      const
    {
        return juce::jlimit(0, 127,
                            127 - (int)((y / (float)getHeight()) * 127.0f));
    }
    float valueToY(int v)      const
    {
        return (float)(getHeight() * (1.0f - (float)v / 127.0f));
    }

    void addOrUpdatePoint(double beat, int value);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(CCLane)
};
