#include "StepSeqView.h"

StepSeqView::StepSeqView()
{
    // DD4 — step count selector
    for (int n : { 8, 16, 24, 32, 48, 64 })
        stepCountPicker.addItem(juce::String(n) + " steps", n);
    stepCountPicker.setSelectedId(numSteps, juce::dontSendNotification);
    stepCountPicker.onChange = [this] {
        setStepCount(stepCountPicker.getSelectedId());
    };
    addAndMakeVisible(stepCountPicker);

    rebuild();
}

void StepSeqView::resized()
{
    stepCountPicker.setBounds(getWidth() - 110, 4, 100, 22);
}

void StepSeqView::rebuild()
{
    grid.assign(numRows, std::vector<bool>(numSteps, false));
    velocities.assign(numRows, std::vector<int>(numSteps, defaultVelocity)); // DD4

    if (currentClip == nullptr) return;

    const double stepBeats = currentClip->lengthBeats > 0.0
        ? currentClip->lengthBeats / numSteps
        : 0.25;

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
        velocities[row][step] = m.getVelocity(); // DD4
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
            {
                // DD4 — velocity maps to brightness (0.3..1.0)
                float bright = 0.3f + 0.7f * (float)velocities[row][step] / 127.0f;
                g.setColour(juce::Colour(0xFF4CAF50).withMultipliedBrightness(bright));
            }
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

    // DD4 — right-click + drag on active cell = velocity edit
    if (e.mods.isRightButtonDown() && grid[row][step])
    {
        velocityDrag = true;
        return;
    }

    grid[row][step] = ! grid[row][step];
    if (grid[row][step])
        velocities[row][step] = defaultVelocity; // DD4
    writeBack();
    repaint();
    if (onChanged) onChanged();
}

// DD4 — vertical drag adjusts velocity of the clicked cell
void StepSeqView::mouseDrag(const juce::MouseEvent& e)
{
    if (!velocityDrag || currentClip == nullptr) return;

    const int cellW = juce::jmax(8, getWidth() / numSteps);
    const int cellH = juce::jmax(8, getHeight() / numRows);
    const int step = e.getMouseDownX() / cellW;
    const int row  = e.getMouseDownY() / cellH;

    if (step < 0 || step >= numSteps || row < 0 || row >= numRows) return;
    if (!grid[row][step]) return;

    // Map vertical drag distance to velocity change
    int vel = juce::jlimit(1, 127,
        velocities[row][step] - e.getDistanceFromDragStartY());
    velocities[row][step] = vel;

    writeBack();
    repaint();
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
            auto on  = juce::MidiMessage::noteOn(1, pitch, (juce::uint8)velocities[row][step]); // DD4
            auto off = juce::MidiMessage::noteOff(1, pitch);
            on.setTimeStamp(startBeat);
            off.setTimeStamp(startBeat + stepBeats * 0.9); // gate ~90%
            seq.addEvent(on);
            seq.addEvent(off);
        }
    }
    seq.updateMatchedPairs();
}
