#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"

//==============================================================================
// NoteEvent - A MIDI note in the piano roll
//==============================================================================
struct NoteEvent
{
    int    noteNumber  = 60;    // 0-127
    double startBeat   = 0.0;  // in beats
    double duration    = 1.0;  // in beats
    int    velocity    = 100;   // 0-127
    bool   selected    = false;
    int    channel     = 0;
};

//==============================================================================
// PianoRoll - Full piano roll MIDI editor
//==============================================================================
class PianoRoll : public juce::Component,
                  public juce::KeyListener,
                  public juce::Timer
{
public:
    PianoRoll();
    ~PianoRoll() override;

    void paint (juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    // Mouse interaction
    void mouseDown (const juce::MouseEvent& e) override;
    void mouseDrag (const juce::MouseEvent& e) override;
    void mouseUp (const juce::MouseEvent& e) override;
    void mouseDoubleClick (const juce::MouseEvent& e) override;
    void mouseWheelMove (const juce::MouseEvent& e, const juce::MouseWheelDetails& w) override;

    // Keyboard
    bool keyPressed (const juce::KeyPress& key, juce::Component* originatingComponent) override;

    // ── Note data ───────────────────────────────────────────────────────────
    void setNotes (const juce::Array<NoteEvent>& notes);
    juce::Array<NoteEvent>& getNotes();
    const juce::Array<NoteEvent>& getNotes() const;

    void addNote (const NoteEvent& note);
    void removeNote (int index);
    void clearNotes();
    void selectAll();
    void deselectAll();
    void deleteSelected();
    void transposeSelected (int semitones);
    void copySelected();
    void paste();

    // ── Playhead ────────────────────────────────────────────────────────────
    void setPlayheadPosition (double beatPosition);
    double getPlayheadPosition() const { return playheadBeat; }

    // ── View parameters ─────────────────────────────────────────────────────
    void setGridSnap (double beatsPerSnap);
    void setTotalBars (int bars);
    void setTimeSignature (int numerator, int denominator);
    void zoomHorizontal (float factor);
    void zoomVertical (float factor);
    void scrollToNote (int noteNumber);

    // ── Tool mode ───────────────────────────────────────────────────────────
    enum class Tool { Draw, Select, Erase };
    void setTool (Tool t) { currentTool = t; }
    Tool getTool() const { return currentTool; }

    // ── Callbacks ───────────────────────────────────────────────────────────
    std::function<void()>               onNotesChanged;
    std::function<void (int)>           onNoteSelected;
    std::function<void (int, int)>      onNotePreview;  // noteNumber, velocity

private:
    // ── Constants ───────────────────────────────────────────────────────────
    static constexpr int totalNotes     = 128;
    static constexpr int pianoKeyWidth  = 48;
    static constexpr int velocityBarH   = 60;
    static constexpr int headerH        = 20;
    static constexpr int minNoteH       = 6;
    static constexpr int maxNoteH       = 24;
    static constexpr float minBeatW     = 8.0f;
    static constexpr float maxBeatW     = 200.0f;

    // ── Notes ───────────────────────────────────────────────────────────────
    juce::Array<NoteEvent> notes;
    juce::Array<NoteEvent> clipboard;

    // ── View state ──────────────────────────────────────────────────────────
    float beatWidth      = 40.0f;   // pixels per beat
    int   noteHeight     = 12;      // pixels per note row
    float scrollX        = 0.0f;    // horizontal scroll in pixels
    float scrollY        = 0.0f;    // vertical scroll in pixels
    double snapBeats     = 0.25;    // snap grid (1/16)
    int   totalBars      = 16;
    int   timeSigNum     = 4;
    int   timeSigDen     = 4;
    double playheadBeat  = 0.0;
    Tool  currentTool    = Tool::Draw;

    // ── Interaction state ───────────────────────────────────────────────────
    enum class DragMode { None, DrawNote, MoveNote, ResizeNote, SelectRubberBand, VelocityEdit };
    DragMode dragMode    = DragMode::None;

    int   dragNoteIndex  = -1;
    double dragStartBeat = 0.0;
    int   dragStartNote  = 0;
    double dragOffsetBeat = 0.0;
    int   dragOffsetNote = 0;
    juce::Point<int> rubberBandStart;
    juce::Point<int> rubberBandEnd;
    NoteEvent pendingNote;

    // ── Coordinate conversion ───────────────────────────────────────────────
    float beatToX (double beat) const;
    double xToBeat (float x) const;
    int noteToY (int noteNumber) const;
    int yToNote (int y) const;
    double snapBeat (double beat) const;

    // ── Drawing helpers ─────────────────────────────────────────────────────
    void drawPianoKeys (juce::Graphics& g, juce::Rectangle<int> area);
    void drawGrid (juce::Graphics& g, juce::Rectangle<int> area);
    void drawNotes (juce::Graphics& g, juce::Rectangle<int> area);
    void drawPlayhead (juce::Graphics& g, juce::Rectangle<int> area);
    void drawRubberBand (juce::Graphics& g);
    void drawVelocityBar (juce::Graphics& g, juce::Rectangle<int> area);
    void drawHeader (juce::Graphics& g, juce::Rectangle<int> area);

    // ── Hit testing ─────────────────────────────────────────────────────────
    int  hitTestNote (juce::Point<int> pos) const;
    bool isOnNoteRightEdge (juce::Point<int> pos, int noteIndex) const;
    bool isInPianoArea (juce::Point<int> pos) const;
    bool isInGridArea (juce::Point<int> pos) const;
    bool isInVelocityArea (juce::Point<int> pos) const;

    // ── Utilities ───────────────────────────────────────────────────────────
    static bool isBlackKey (int noteNumber);
    static juce::String noteName (int noteNumber);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (PianoRoll)
};
