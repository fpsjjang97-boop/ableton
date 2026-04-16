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

    // EE5 — zoom presets and follow-playhead toggle
    void setZoomBeats(float beats) { beatsVisible = juce::jlimit(4.0f, 256.0f, beats); resized(); repaint(); }
    void setFollowPlayhead(bool f) { followPlayhead = f; }
    float getBeatsVisible() const { return beatsVisible; } // QQ3
    void setLastStopBeat(double b) { lastStopBeat = b; } // VV6
    void setScrollX(float sx) { scrollXBeats = sx; repaint(); } // QQ3

    // II2 — snap grid
    void setSnapBeats(double s) { snapBeats = s; }
    double snapBeat(double b) const { return snapBeats > 0.0 ? std::round(b / snapBeats) * snapBeats : b; }
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
    double snapBeats { 0.25 }; // II2 — snap grid (0 = off)

    int selectedTrackId { -1 };                   // U7
    juce::UndoManager* undoManager { nullptr };    // W1
    std::function<bool()> isRecording;              // Z1
    bool followPlayhead { true };                    // EE5
    double lastStopBeat { -1.0 };                    // VV6

    // NN1 — ruler scrub (drag in ruler area = scrub playhead)
    bool rulerScrubbing { false };

    // LL4 — loop drag state
    bool loopDragging { false };
    double loopDragStartBeat { 0.0 };

    // U1 — inline automation lane editing state
    int   autoDragTrackIdx { -1 };
    int   autoDragPointIdx { -1 };
    float autoLaneHPx { 12.0f };

    // GG3 — track reorder drag state
    int trackDragFrom { -1 };
    int trackDragTo   { -1 };

public:
    // JJ4 — selection rectangle (public for clipboard access from MainWindow)
    std::vector<MidiClip*> selectedClips;

    // LL1 — clipboard
    std::vector<MidiClip> clipboardClips;

private:
    bool selectionDrag { false };
    juce::Point<int> selDragStart;

    // HH2 — clip resize state
    MidiClip* resizeClip { nullptr };
    double    resizeClipOrigLen { 0.0 };

    // FF3 — clip drag move state
    MidiClip* dragClip { nullptr };
    double    dragClipOrigStart { 0.0 };
    double    dragClipOrigLen   { 0.0 };
    double    dragOffsetBeats   { 0.0 };

    // X3 — audio clip trim drag state
    enum class TrimMode { None, Left, Right };
    TrimMode trimMode { TrimMode::None };
    int      trimTrackIdx { -1 };
    int      trimClipIdx  { -1 };

    float beatToX(double beat) const;
    double xToBeat(float x) const;

    void showTrackContextMenu(int trackIdx);
    void showClipContextMenu(Track& track, int clipIdx); // GG2

    // CC1 — visible track list (excludes children of collapsed folders)
    std::vector<int> visibleTrackIndices;
    void rebuildVisibleTracks();
    int  visibleTrackAtY(int y) const;  // returns index into tracks[], or -1

    // HH3 — Y offset for visible row (accounts for per-track displayHeight)
    int  yForVisibleRow(int vi) const;
    int  heightForVisibleRow(int vi) const;
    int  totalVisibleHeight() const;

    // HH3 — track height resize drag
    int heightDragVi { -1 };
    int heightDragStartY { 0 };
    int heightDragOrigH  { 48 };

    juce::TextButton addTrackButton { "+ Track" };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ArrangementView)
};
