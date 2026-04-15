#include "CCLane.h"

CCLane::CCLane() = default;

void CCLane::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF181818));

    // Horizontal mid-line
    g.setColour(juce::Colour(0xFF303030));
    g.drawHorizontalLine(getHeight() / 2, 0.0f, (float)getWidth());

    // Beat grid
    if (beatWidth > 8.0f)
    {
        g.setColour(juce::Colour(0xFF252525));
        const double firstBeat = scrollX / beatWidth;
        const double lastBeat  = firstBeat + getWidth() / beatWidth;
        for (double b = std::floor(firstBeat); b <= lastBeat; b += 1.0)
        {
            float x = beatToX(b);
            g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
        }
    }

    if (currentClip == nullptr) return;

    // Collect existing CC events for this controller
    auto& seq = currentClip->sequence;
    std::vector<std::pair<double, int>> ccEvents;
    for (int i = 0; i < seq.getNumEvents(); ++i)
    {
        auto& m = seq.getEventPointer(i)->message;
        if (m.isController() && m.getControllerNumber() == ccNum)
            ccEvents.push_back({ m.getTimeStamp(), m.getControllerValue() });
    }

    if (ccEvents.empty()) return;
    std::sort(ccEvents.begin(), ccEvents.end(),
              [](auto& a, auto& b) { return a.first < b.first; });

    // Draw filled polyline from baseline
    juce::Path filled;
    filled.startNewSubPath(beatToX(ccEvents.front().first), (float)getHeight());
    for (auto& [b, v] : ccEvents)
        filled.lineTo(beatToX(b), valueToY(v));
    filled.lineTo(beatToX(ccEvents.back().first), (float)getHeight());
    filled.closeSubPath();

    g.setColour(juce::Colour(0x40FFC107));
    g.fillPath(filled);

    // Outline + points
    g.setColour(juce::Colour(0xFFFFC107));
    juce::Path line;
    line.startNewSubPath(beatToX(ccEvents.front().first),
                         valueToY(ccEvents.front().second));
    for (auto& [b, v] : ccEvents)
    {
        float x = beatToX(b);
        float y = valueToY(v);
        line.lineTo(x, y);
        g.fillEllipse(x - 3.0f, y - 3.0f, 6.0f, 6.0f);
    }
    g.strokePath(line, juce::PathStrokeType(1.5f));
}

void CCLane::mouseDown(const juce::MouseEvent& e)
{
    if (isRecording && isRecording()) return; // Z1
    if (currentClip == nullptr) return;

    if (e.mods.isRightButtonDown())
    {
        // Delete nearest point within 6px
        double targetBeat = xToBeat(e.x);
        auto& seq = currentClip->sequence;
        int bestIdx = -1;
        double bestDist = 1e9;
        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            auto& m = seq.getEventPointer(i)->message;
            if (! (m.isController() && m.getControllerNumber() == ccNum)) continue;
            double dist = std::abs(m.getTimeStamp() - targetBeat) * beatWidth;
            if (dist < bestDist) { bestDist = dist; bestIdx = i; }
        }
        if (bestIdx >= 0 && bestDist <= 6.0)
        {
            seq.deleteEvent(bestIdx, false);
            seq.updateMatchedPairs();
            repaint();
            if (onChanged) onChanged();
        }
        return;
    }

    double beat = std::round(xToBeat((float)e.x) / snapBeats) * snapBeats;
    int value = yToValue((float)e.y);
    addOrUpdatePoint(beat, value);
}

void CCLane::mouseDrag(const juce::MouseEvent& e)
{
    if (currentClip == nullptr) return;
    if (e.mods.isRightButtonDown()) return;

    double beat = std::round(xToBeat((float)e.x) / snapBeats) * snapBeats;
    int value = yToValue((float)e.y);
    addOrUpdatePoint(beat, value);
}

void CCLane::addOrUpdatePoint(double beat, int value)
{
    if (currentClip == nullptr) return;
    if (beat < 0.0) beat = 0.0;

    auto& seq = currentClip->sequence;

    // Remove any existing point at this exact beat (within 1 tick) to avoid duplicates
    for (int i = seq.getNumEvents() - 1; i >= 0; --i)
    {
        auto& m = seq.getEventPointer(i)->message;
        if (m.isController() && m.getControllerNumber() == ccNum)
            if (std::abs(m.getTimeStamp() - beat) < 1e-6)
                seq.deleteEvent(i, false);
    }

    auto cc = juce::MidiMessage::controllerEvent(1, ccNum, value);
    cc.setTimeStamp(beat);
    seq.addEvent(cc);
    seq.updateMatchedPairs();
    repaint();
    if (onChanged) onChanged();
}
