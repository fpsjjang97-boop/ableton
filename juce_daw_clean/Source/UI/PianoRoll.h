/*
 * MidiGPT DAW - PianoRoll
 * Full MIDI note editor with draw/select/erase tools, drag move/resize,
 * velocity editing, zoom, scroll, clipboard, playhead.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/TrackModel.h"
#include <functional>

class PianoRoll : public juce::Component,
                  public juce::KeyListener,
                  public juce::Timer
{
public:
    PianoRoll();

    void setClip(MidiClip* clip) { currentClip = clip; repaint(); }
    MidiClip* getClip() const    { return currentClip; }

    // W1 — UndoManager injection (non-owning)
    void setUndoManager(juce::UndoManager* um) { undoManager = um; }

    // Y1 — lock edits while recording (predicate injection)
    void setRecordingPredicate(std::function<bool()> pred) { isRecording = std::move(pred); }

    void setPlayheadBeat(double beat) { playheadBeat = beat; }

    void paint(juce::Graphics& g) override;
    void resized() override;

    void mouseDown(const juce::MouseEvent& e) override;
    void mouseDrag(const juce::MouseEvent& e) override;
    void mouseUp(const juce::MouseEvent& e) override;
    void mouseDoubleClick(const juce::MouseEvent& e) override;
    void mouseWheelMove(const juce::MouseEvent& e, const juce::MouseWheelDetails& w) override;
    bool keyPressed(const juce::KeyPress& key, juce::Component*) override;
    void timerCallback() override;

    std::function<void()> onNotesChanged;

    enum Tool { DrawTool, SelectTool, EraseTool };
    void setTool(Tool t) { currentTool = t; repaint(); }
    Tool getTool() const { return currentTool; }

    /** Quantize note start positions to the current snap grid.
     *  strength 1.0 = full snap, 0.5 = halfway, 0.0 = no-op (idempotent).
     *  If selectedIndices is non-empty only those notes are moved; otherwise
     *  every note in the clip. Note durations are preserved (note-off shifts
     *  by the same delta as note-on). Destructive — copy clip externally if
     *  undo is required. */
    void quantizeNotes(double strength = 1.0);

    /** Active snap grid in beats (1.0 = quarter, 0.25 = sixteenth, ...).
     *  Quantize and draw operations both use this value. */
    void setSnapBeats(double s) { if (s > 0.0) { snapBeats = s; repaint(); } }
    double getSnapBeats() const { return snapBeats; }

private:
    MidiClip* currentClip { nullptr };
    Tool currentTool { DrawTool };
    double playheadBeat { -1.0 };

    static constexpr int pianoKeyWidth = 48;
    static constexpr int velocityBarH  = 60;
    static constexpr int headerH       = 20;
    static constexpr int totalNotes    = 128;

    float noteHeight { 12.0f };
    float beatWidth  { 40.0f };
    float scrollX { 0.0f };
    float scrollY { 0.0f };
    double snapBeats { 0.25 };

    juce::UndoManager* undoManager { nullptr }; // W1
    std::function<bool()> isRecording;           // Y1

    enum DragMode { None, DrawNote, MoveNote, ResizeNote, RubberBand, VelocityEdit };
    DragMode dragMode { None };
    int dragNoteIdx { -1 };
    double dragStartBeat { 0.0 };
    int dragStartNote { 0 };
    float dragStartX { 0.0f };
    float dragStartY { 0.0f };
    juce::Rectangle<float> rubberBandRect;

    struct OrigPos { double beat; int noteNum; };
    std::vector<OrigPos> origPositions;

    // Y2 — full snapshot for Move/Resize undo
    struct NoteBefore { int pitch, ch, vel; double start, dur; };
    std::vector<NoteBefore> moveBefore;

    // Z2 — velocity drag snapshot
    std::vector<NoteBefore> velBefore;

    std::vector<int> selectedIndices;

    struct ClipboardNote { double beat; int noteNum; int velocity; double duration; };
    std::vector<ClipboardNote> clipboard;

    float noteToY(int note) const;
    int yToNote(float y) const;
    float beatToX(double beat) const;
    double xToBeat(float x) const;
    int gridAreaRight() const { return getWidth(); }
    int gridAreaBottom() const { return getHeight() - velocityBarH; }

    void drawHeader(juce::Graphics& g);
    void drawPianoKeys(juce::Graphics& g);
    void drawGrid(juce::Graphics& g);
    void drawNotes(juce::Graphics& g);
    void drawPlayhead(juce::Graphics& g);
    void drawVelocityBar(juce::Graphics& g);

    int findNoteAt(double beat, int noteNum);
    bool isNearNoteEnd(int idx, float mx) const;
    bool isSelected(int idx) const;
    double snapBeat(double beat) const;
    void deleteSelected();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PianoRoll)
};
