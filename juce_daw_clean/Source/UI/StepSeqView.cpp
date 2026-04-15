#include "StepSeqView.h"

StepSeqView::StepSeqView()
{
    rebuild();
}

void StepSeqView::rebuild()
{
    grid.assign(numRows, std::vector<bool>(numSteps, false));

    if (currentClip == nullptr) return;

    const double stepBeats = currentClip->lengthBeats > 0.0
        ? currentClip->lengthBeats / numSteps
        : 0.25; // default 16th notes if clip length unset

    auto& seq = currentClip->sequence;
    for (int i = 0; i < seq.getNumEvents(); ++i)
    {
        auto& m = seq.getEventPointer(i)->message;
        if (! m.isNoteOn()) continue;
        int row = m.getNoteNumber() - baseNote;
        if (row < 0 || row >= numRows) continue;
        int step = (int)std::round(m.getTimeStamp() / stepBeats);
        if (step < 0 || step >= numSteps) continue;
        grid[row][step] = true;
    }
}

void StepSeqView::cellRect(int row, int step, juce::Rectangle<int>& out) const
{
    const int cellW = juce::jmax(8, getWidth() / numSteps);
    const int cellH = juce::jmax(8, getHeight() / numRows);
    out = juce::Rectangle<int>(step * cellW, row * cellH, cellW - 1, cellH - 1);
}

void StepSeqView::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF101010));

    juce::Rectangle<int> r;
    for (int row = 0; row < numRows; ++row)
    {
        for (int step = 0; step < numSteps; ++step)
        {
            cellRect(row, step, r);
            const bool isBeatStart = (step % 4 == 0);

            if (grid[row][step])
                g.setColour(juce::Colour(0xFF4CAF50));
            else
                g.setColour(isBeatStart ? juce::Colour(0xFF2A2A2A)
                                        : juce::Colour(0xFF1A1A1A));
            g.fillRect(r);
        }
    }

    // Row labels (note names)
    g.setColour(juce::Colour(0xFF707070));
    g.setFont(10.0f);
    for (int row = 0; row < numRows; ++row)
    {
        cellRect(row, 0, r);
        auto name = juce::MidiMessage::getMidiNoteName(baseNote + row, true, true, 4);
        g.drawText(name, 2, r.getY(), 26, r.getHeight(),
                   juce::Justification::centredLeft);
    }
}

void StepSeqView::mouseDown(const juce::MouseEvent& e)
{
    if (isRecording && isRecording()) return; // Z1
    if (currentClip == nullptr) return;

    const int cellW = juce::jmax(8, getWidth() / numSteps);
    const int cellH = juce::jmax(8, getHeight() / numRows);
    const int step = e.x / cellW;
    const int row  = e.y / cellH;

    if (step < 0 || step >= numSteps) return;
    if (row < 0  || row >= numRows)   return;

    grid[row][step] = ! grid[row][step];
    writeBack();
    repaint();
    if (onChanged) onChanged();
}

void StepSeqView::writeBack()
{
    if (currentClip == nullptr) return;

    const double stepBeats = currentClip->lengthBeats > 0.0
        ? currentClip->lengthBeats / numSteps
        : 0.25;

    auto& seq = currentClip->sequence;
    seq.clear();

    for (int row = 0; row < numRows; ++row)
    {
        const int pitch = baseNote + row;
        for (int step = 0; step < numSteps; ++step)
        {
            if (! grid[row][step]) continue;
            const double startBeat = step * stepBeats;
            auto on  = juce::MidiMessage::noteOn(1, pitch, (juce::uint8)defaultVelocity);
            auto off = juce::MidiMessage::noteOff(1, pitch);
            on.setTimeStamp(startBeat);
            off.setTimeStamp(startBeat + stepBeats * 0.9); // gate ~90%
            seq.addEvent(on);
            seq.addEvent(off);
        }
    }
    seq.updateMatchedPairs();
}
