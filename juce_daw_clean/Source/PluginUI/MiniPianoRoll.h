/*
 * MidiGPT VST3 Plugin — MiniPianoRoll
 *
 * Compact read-only piano-roll component for rendering a
 * ``juce::MidiMessageSequence`` in the plugin editor. Used in the
 * Sprint 33 Dual Pane to show captured-input vs. last-generated side
 * by side.
 *
 * NOT a full editor — no interaction, no scrolling, no CC lanes.
 * Optimised for the "I want to see what came out" glanceable use case.
 *
 * References (public sources only):
 *   - JUCE Component class: https://docs.juce.com/master/classComponent.html
 *   - JUCE MidiMessageSequence: https://docs.juce.com/master/classMidiMessageSequence.html
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_basics/juce_audio_basics.h>

class MiniPianoRoll : public juce::Component
{
public:
    MiniPianoRoll();
    ~MiniPianoRoll() override = default;

    /** Replace the displayed sequence. Triggers repaint. Timestamps are
        assumed to be in beats (ppq). Safe to call from the message thread. */
    void setSequence (const juce::MidiMessageSequence& newSequence);

    /** Title rendered in the top-left corner (e.g. "Input", "Output"). */
    void setTitle (const juce::String& title);

    /** Empty-state placeholder text (rendered centre when no notes). */
    void setEmptyPlaceholder (const juce::String& text);

    void paint (juce::Graphics& g) override;

private:
    juce::MidiMessageSequence sequence;
    juce::String title;
    juce::String emptyPlaceholder { "— empty —" };

    // Cached note metadata (start beat / length / pitch / velocity) so we
    // don't re-walk the sequence on every paint.
    struct NoteBox
    {
        double startBeat;
        double lengthBeat;
        int    pitch;
        int    velocity;
    };
    std::vector<NoteBox> notes;
    int  lowestPitch { 60 };
    int  highestPitch { 72 };
    double totalBeats { 4.0 };

    void rebuildNoteCache();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MiniPianoRoll)
};
