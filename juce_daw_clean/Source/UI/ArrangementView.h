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

    // U7 — selected track tracking (PluginBrowser / future)
    int getSelectedTrackId() const { return selectedTrackId; }

    // W1 — UndoManager injection
    void setUndoManager(juce::UndoManager* um) { undoManager = um; }
    // Z1 — recording predicate (blocks mouseDown edits while true)
    void setRecordingPredicate(std::function<bool()> p) { isRecording = std::move(p); }

    void mouseDrag(const juce::MouseEvent& e) override;
    void mouseUp(const juce::MouseEvent& e) override;

private:
    AudioEngine& audioEngine;

    static constexpr int trackHeight = 48;
    static constexpr int headerWidth = 160;

    float beatsVisible { 64.0f };
    float scrollXBeats { 0.0f };
    int scrollYPixels { 0 };

    int selectedTrackId { -1 };                   // U7
    juce::UndoManager* undoManager { nullptr };    // W1
    std::function<bool()> isRecording;              // Z1

    // U1 — inline automation lane editing state
    int   autoDragTrackIdx { -1 };
    int   autoDragPointIdx { -1 };
    float autoLaneHPx { 12.0f };

    // X3 — audio clip trim drag state
    enum class TrimMode { None, Left, Right };
    TrimMode trimMode { TrimMode::None };
    int      trimTrackIdx { -1 };
    int      trimClipIdx  { -1 };

    float beatToX(double beat) const;
    double xToBeat(float x) const;

    void showTrackContextMenu(int trackIdx);

    juce::TextButton addTrackButton { "+ Track" };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ArrangementView)
};
