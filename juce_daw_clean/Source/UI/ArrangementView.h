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
    // PPP3 review — hint channel for status-bar messages triggered by
    // view-local actions (e.g. "Press Space to record" after R arm).
    std::function<void(juce::String)> onStatusMessage;

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

    // PPP3/PPP2 review — track-header button layout, single source of
    // truth for paint and hit-test. Buttons (R, M, S) are right-aligned
    // inside the header row with a fixed 8 px right margin and 2 px gap.
    // Index 0 = R (leftmost), 1 = M, 2 = S (rightmost).
    static constexpr int headerBtnW         = 16;
    static constexpr int headerBtnGap       = 2;
    static constexpr int headerBtnCount     = 3;
    static constexpr int headerBtnRightPad  = 8;
    static constexpr int headerBtnLeft (int idx)
    {
        return headerWidth - headerBtnRightPad - headerBtnW
             - (headerBtnCount - 1 - idx) * (headerBtnGap + headerBtnW);
    }
    static constexpr int headerBtnRight (int idx)
    {
        return headerBtnLeft(idx) + headerBtnW;
    }
    // Track-name field runs from left margin to just before the leftmost
    // button. Subtract 2 px so the name never butts up against the R box.
    static constexpr int headerNameLeft     = 10;
    static constexpr int headerNameWidth() { return headerBtnLeft(0) - headerNameLeft - 2; }

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

    // Bezier curve editing — Alt+drag on a point adjusts its outgoing
    // segment curvature instead of moving the point. Matches Ableton's
    // "grab-midpoint-to-bend" semantic but anchored on the point itself
    // so hit-testing stays simple.
    enum class AutoDragMode { Value, Curve };
    AutoDragMode autoDragMode { AutoDragMode::Value };
    int   autoDragStartY     { 0 };
    float autoDragStartCurve { 0.0f };

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

    // PPP1 — audio clip fade drag state (top-of-clip handles; distinct from
    // edge trim which spans the full clip height). Activated only when the
    // hit falls within the top fadeHandleHeight px of the clip row.
    enum class FadeMode { None, In, Out };
    FadeMode fadeMode     { FadeMode::None };
    int      fadeTrackIdx { -1 };
    int      fadeClipIdx  { -1 };
    static constexpr int fadeHandleHeight = 8;

    // PPP2 — shared "before" snapshot for audio-clip drag undo. Populated at
    // mouseDown for both fade and trim paths; compared against the clip's
    // live state at mouseUp to build an AudioClipEditCmd. Stored as raw
    // pointer because AudioClip is a POD-ish struct — invalid if the user
    // removes the clip mid-drag, but such concurrent edits are UI-gated.
    struct AudioClip* audioDragClip { nullptr };
    double      audioDragBeforeStartBeat           { 0.0 };
    double      audioDragBeforeLengthBeats         { 0.0 };
    juce::int64 audioDragBeforeSourceOffsetSamples { 0 };
    double      audioDragBeforeFadeInBeats         { 0.0 };
    double      audioDragBeforeFadeOutBeats        { 0.0 };

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
