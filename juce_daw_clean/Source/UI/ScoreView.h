/*
 * MidiGPT DAW — ScoreView
 *
 * Minimal staff-notation view of the currently-selected MIDI clip.
 * Renders a grand staff (treble + bass clefs) and draws each note as a
 * notehead + stem at the nearest standard duration. Not a music-
 * engraving engine — this is a "piano roll, but on staff paper" so
 * users who read notation can sight-check generated content without
 * leaving the DAW.
 *
 * Scope (2026-04-21 MVP):
 *   - 5-line treble/bass grand staff, splitting at middle C.
 *   - Filled oval noteheads at quantised pitches.
 *   - Stems up / down depending on register (above/below B4).
 *   - Duration quantised to whole / half / quarter / 8th / 16th.
 *   - Horizontal scroll (mouse wheel).
 *   - Playhead indicator.
 * Not included: key-signature accidentals, beaming, ties, rests,
 *   multiple voices. Planned follow-up.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/TrackModel.h"

class ScoreView : public juce::Component,
                  public juce::Timer
{
public:
    ScoreView();

    void paint (juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    void setClip (MidiClip* clip)           { currentClip = clip; repaint(); }
    void setPlayheadBeat (double b)          { playheadBeat = b; }
    void setRecordingPredicate (std::function<bool()> p) { isRecording = std::move(p); }

    // Scroll / zoom
    void mouseWheelMove (const juce::MouseEvent&, const juce::MouseWheelDetails&) override;

private:
    MidiClip* currentClip { nullptr };
    double   playheadBeat { -1.0 };
    std::function<bool()> isRecording;

    // Layout constants — tweaking is cheap because layout is all-code.
    static constexpr int    clefColumnWidth = 48;
    static constexpr int    staffLineSpacing = 10;       // px between staff lines
    static constexpr int    headerH          = 20;
    float                    beatWidth       { 60.0f };
    float                    scrollX         { 0.0f };

    // Derived layout — computed in resized().
    int trebleTopY  { 0 };   // top line of treble staff
    int trebleBotY  { 0 };
    int bassTopY    { 0 };
    int bassBotY    { 0 };

    void drawStaff        (juce::Graphics& g);
    void drawNotes        (juce::Graphics& g);
    void drawPlayhead     (juce::Graphics& g);

    // Pitch → staff Y. Uses diatonic C-major steps; accidentals drawn as
    // "sharp" symbol next to notehead without changing Y.
    int pitchToStaffY (int midiPitch) const;

    // Beat → X on screen given scroll.
    float beatToX (double beat) const
    {
        return (float) clefColumnWidth + (float) beat * beatWidth - scrollX;
    }

    // Nearest standard duration bucket from beats. Returns (label, beats)
    // where label ∈ { "1", "1/2", "1/4", "1/8", "1/16" }.
    static std::pair<const char*, double> quantiseDuration (double beats);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ScoreView)
};
