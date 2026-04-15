#include "AutomationEditor.h"

AutomationEditor::AutomationEditor(Track& t, const juce::String& pid, double mb)
    : trackRef(t), paramId(pid), maxBeats(juce::jmax(1.0, mb))
{
    setSize(640, 240);
    getOrCreateLane(); // ensure lane exists for editing
}

AutomationLane& AutomationEditor::getOrCreateLane()
{
    for (auto& l : trackRef.automation)
        if (l.paramId == paramId) return l;
    AutomationLane l;
    l.paramId = paramId;
    trackRef.automation.push_back(std::move(l));
    return trackRef.automation.back();
}

int AutomationEditor::findPointAt(float x, float y, AutomationLane& lane, int hitPx) const
{
    int best = -1;
    float bestDist = 1e9f;
    for (int i = 0; i < (int)lane.points.size(); ++i)
    {
        const float px = beatToX(lane.points[i].beat);
        const float py = valueToY(lane.points[i].value);
        const float dx = px - x;
        const float dy = py - y;
        const float d = std::sqrt(dx*dx + dy*dy);
        if (d < bestDist) { bestDist = d; best = i; }
    }
    return (bestDist <= hitPx) ? best : -1;
}

void AutomationEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF101010));

    // Beat grid
    g.setColour(juce::Colour(0xFF252525));
    for (double b = 0; b <= maxBeats; b += 1.0)
    {
        float x = beatToX(b);
        g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
    }

    // Center / range labels
    g.setColour(juce::Colour(0xFF333333));
    g.drawHorizontalLine(getHeight() / 2, 0.0f, (float)getWidth());

    g.setColour(juce::Colour(0xFF707070));
    g.setFont(11.0f);
    g.drawText(paramId, 6, 4, 200, 16, juce::Justification::centredLeft);

    auto& lane = getOrCreateLane();
    if (lane.points.empty())
    {
        g.setColour(juce::Colour(0xFF505050));
        g.drawText("Click to add automation points", getLocalBounds(),
                   juce::Justification::centred);
        return;
    }

    // Polyline + filled area
    juce::Path filled;
    filled.startNewSubPath(beatToX(lane.points.front().beat), (float)getHeight());
    for (auto& p : lane.points)
        filled.lineTo(beatToX(p.beat), valueToY(p.value));
    filled.lineTo(beatToX(lane.points.back().beat), (float)getHeight());
    filled.closeSubPath();
    g.setColour(juce::Colour(0x404CAF50));
    g.fillPath(filled);

    g.setColour(juce::Colour(0xFF4CAF50));
    juce::Path line;
    line.startNewSubPath(beatToX(lane.points.front().beat),
                         valueToY(lane.points.front().value));
    for (auto& p : lane.points)
    {
        const float x = beatToX(p.beat);
        const float y = valueToY(p.value);
        line.lineTo(x, y);
        g.fillEllipse(x - 4.0f, y - 4.0f, 8.0f, 8.0f);
    }
    g.strokePath(line, juce::PathStrokeType(1.5f));
}

void AutomationEditor::mouseDown(const juce::MouseEvent& e)
{
    auto& lane = getOrCreateLane();

    if (e.mods.isRightButtonDown())
    {
        int idx = findPointAt((float)e.x, (float)e.y, lane);
        if (idx >= 0)
        {
            lane.points.erase(lane.points.begin() + idx);
            repaint();
            if (onChanged) onChanged();
        }
        return;
    }

    int idx = findPointAt((float)e.x, (float)e.y, lane);
    if (idx >= 0)
    {
        draggingIdx = idx;
        return;
    }

    // Add point
    const double beat = juce::jlimit(0.0, maxBeats, xToBeat((float)e.x));
    const float value = yToValue((float)e.y);
    lane.addPoint(beat, value);

    // After insertion the new point's index needs to be located again
    for (int i = 0; i < (int)lane.points.size(); ++i)
        if (std::abs(lane.points[i].beat - beat) < 1e-6 && lane.points[i].value == juce::jlimit(0.0f, 1.0f, value))
            { draggingIdx = i; break; }

    repaint();
    if (onChanged) onChanged();
}

void AutomationEditor::mouseDrag(const juce::MouseEvent& e)
{
    if (draggingIdx < 0) return;
    auto& lane = getOrCreateLane();
    if (draggingIdx >= (int)lane.points.size()) { draggingIdx = -1; return; }

    auto& p = lane.points[draggingIdx];
    p.beat  = juce::jlimit(0.0, maxBeats, xToBeat((float)e.x));
    p.value = yToValue((float)e.y);

    // Re-sort if order changed
    std::sort(lane.points.begin(), lane.points.end(),
              [](const AutomationPoint& a, const AutomationPoint& b)
              { return a.beat < b.beat; });

    // Rediscover index after sort
    draggingIdx = -1;
    for (int i = 0; i < (int)lane.points.size(); ++i)
        if (std::abs(lane.points[i].beat - p.beat) < 1e-6) { draggingIdx = i; break; }

    repaint();
    if (onChanged) onChanged();
}

void AutomationEditor::mouseUp(const juce::MouseEvent&)
{
    draggingIdx = -1;
}

void AutomationEditor::launchModal(Track& track, const juce::String& pid, double maxBeats)
{
    auto* editor = new AutomationEditor(track, pid, maxBeats);

    juce::DialogWindow::LaunchOptions opts;
    opts.dialogTitle = "Automation — " + track.name + " / " + pid;
    opts.content.setOwned(editor);
    opts.dialogBackgroundColour = juce::Colour(0xFF101010);
    opts.escapeKeyTriggersCloseButton = true;
    opts.useNativeTitleBar = true;
    opts.resizable = true;
    opts.launchAsync();
}
