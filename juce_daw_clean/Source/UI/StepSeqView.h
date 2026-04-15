/*
 * MidiGPT DAW — StepSeqView
 *
 * 16-step / 32-step sequencer grid editing a single MidiClip. Each row =
 * one MIDI note (default 8 rows starting from C2). Click cell to toggle
 * note on/off at that step.
 *
 * Use case: drum patterns + arpeggios. For melodic editing use PianoRoll.
 *
 * Sprint scope: minimal viable — fixed 16 steps, fixed 8 rows, single
 * velocity. Step count selector + per-step velocity arrives in Sprint 4.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/TrackModel.h"
#include <functional>

class StepSeqView : public juce::Component
{
public:
    StepSeqView();

    void setClip(MidiClip* clip)         { currentClip = clip; rebuild(); repaint(); }
    void setRecordingPredicate(std::function<bool()> p) { isRecording = std::move(p); }
    void setStepCount(int n)             { numSteps = juce::jlimit(8, 64, n); rebuild(); repaint(); }
    void setBaseNote(int midi)           { baseNote = juce::jlimit(0, 120, midi); rebuild(); repaint(); }

    void paint(juce::Graphics& g) override;
    void mouseDown(const juce::MouseEvent& e) override;
    void resized() override {}

    std::function<void()> onChanged;

private:
    MidiClip* currentClip { nullptr };
    int numSteps { 16 };
    int numRows  { 8 };
    int baseNote { 36 };           // C2 — kick drum on GM map
    int defaultVelocity { 100 };
    std::function<bool()> isRecording;

    // Internal grid mirror — kept in sync with currentClip->sequence on rebuild
    std::vector<std::vector<bool>> grid; // [row][step]

    void rebuild();
    void writeBack();   // Push grid back to currentClip->sequence
    void cellRect(int row, int step, juce::Rectangle<int>& out) const;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(StepSeqView)
};
