/*
 * MidiGPT DAW — AutomationEditor (S5)
 *
 * Modal-style component for editing one AutomationLane. Click adds a point;
 * right-click on a point deletes it; drag moves a point. Lane is bound to
 * a Track + paramId ("volume" / "pan").
 *
 * Sprint scope: minimum viable single-lane editor. Inline arrangement-view
 * lanes (MultiLane stack) is a Sprint 3 enhancement.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/TrackModel.h"
#include "AutomationLane.h"
#include <functional>

class AutomationEditor : public juce::Component
{
public:
    AutomationEditor(Track& track, const juce::String& paramId,
                     double maxBeats);

    void paint(juce::Graphics& g) override;
    void mouseDown(const juce::MouseEvent& e) override;
    void mouseDrag(const juce::MouseEvent& e) override;
    void mouseUp(const juce::MouseEvent& e) override;

    static void launchModal(Track& track, const juce::String& paramId,
                            double maxBeats);

    std::function<void()> onChanged;

private:
    Track& trackRef;
    juce::String paramId;
    double maxBeats { 16.0 };
    int draggingIdx { -1 };

    AutomationLane& getOrCreateLane();
    float beatToX(double beat) const { return (float)(beat / maxBeats * getWidth()); }
    double xToBeat(float x)    const { return (double)x / getWidth() * maxBeats; }
    float valueToY(float v)    const { return getHeight() * (1.0f - v); }
    float yToValue(float y)    const
    {
        return juce::jlimit(0.0f, 1.0f, 1.0f - y / (float)getHeight());
    }

    int findPointAt(float x, float y, AutomationLane& lane, int hitPx = 8) const;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AutomationEditor)
};
