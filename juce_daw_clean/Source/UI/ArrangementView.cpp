/*
 * MidiGPT DAW - ArrangementView.cpp
 */

#include "ArrangementView.h"
#include "../Automation/AutomationEditor.h"
#include "../Plugin/PluginEditorWindow.h"
#include "../Command/EditCommands.h"

ArrangementView::ArrangementView(AudioEngine& engine)
    : audioEngine(engine)
{
    addTrackButton.onClick = [this] {
        auto& t = audioEngine.getTrackModel().addTrack();
        audioEngine.prebuildTrackSynth(t.id); // T1
        MidiClip clip;
        clip.startBeat = 0;
        clip.lengthBeats = 16.0;
        t.clips.push_back(clip);
        if (onTrackListChanged) onTrackListChanged();
        repaint();
    };
    addAndMakeVisible(addTrackButton);
    startTimerHz(30);
}

float ArrangementView::beatToX(double beat) const
{
    float timelineW = (float)(getWidth() - headerWidth);
    return headerWidth + (float)((beat - scrollXBeats) / beatsVisible * timelineW);
}

double ArrangementView::xToBeat(float x) const
{
    float timelineW = (float)(getWidth() - headerWidth);
    return (double)(x - headerWidth) / timelineW * beatsVisible + scrollXBeats;
}

void ArrangementView::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF181818));

    auto& tracks = audioEngine.getTrackModel().getTracks();
    int numTracks = (int)tracks.size();
    float timelineW = (float)(getWidth() - headerWidth);

    // Draw timeline content first, then headers on top
    g.saveState();

    for (int i = 0; i < numTracks; ++i)
    {
        auto& track = tracks[(size_t)i];
        int y = i * trackHeight - scrollYPixels;
        if (y + trackHeight < 0 || y > getHeight()) continue;

        // Header bg
        g.setColour(juce::Colour(0xFF252525));
        g.fillRect(0, y, headerWidth, trackHeight);

        // Colour bar
        g.setColour(track.colour);
        g.fillRect(0, y, 4, trackHeight);

        // Track name
        g.setColour(track.mute ? juce::Colours::grey : juce::Colours::white);
        g.setFont(13.0f);
        g.drawText(track.name, 10, y, headerWidth - 50, trackHeight,
                   juce::Justification::centredLeft);

        // M/S indicators
        g.setFont(10.0f);
        if (track.mute)
        {
            g.setColour(juce::Colour(0xFFFF5722));
            g.drawText("M", headerWidth - 40, y, 16, trackHeight, juce::Justification::centred);
        }
        if (track.solo)
        {
            g.setColour(juce::Colour(0xFFFFC107));
            g.drawText("S", headerWidth - 20, y, 16, trackHeight, juce::Justification::centred);
        }

        // Timeline row bg
        g.setColour(i % 2 == 0 ? juce::Colour(0xFF1C1C1C) : juce::Colour(0xFF202020));
        g.fillRect(headerWidth, y, (int)timelineW, trackHeight);

        // Clips
        for (size_t ci = 0; ci < track.clips.size(); ++ci)
        {
            auto& clip = track.clips[ci];
            float cx = beatToX(clip.startBeat);
            float cw = (float)(clip.lengthBeats / beatsVisible * timelineW);

            if (cx + cw < headerWidth || cx > getWidth()) continue;

            // Clamp clip to not draw over header
            float drawX = juce::jmax((float)headerWidth + 1, cx + 1);
            float drawW = juce::jmax(2.0f, (cx + cw - 1) - drawX);
            if (drawW <= 0) continue;

            g.setColour(track.colour.withAlpha(0.6f));
            g.fillRoundedRectangle(drawX, (float)(y + 2), drawW,
                                   (float)(trackHeight - 4), 3.0f);

            // Mini note preview (clipped)
            g.setColour(juce::Colours::white.withAlpha(0.5f));
            for (int ei = 0; ei < clip.sequence.getNumEvents(); ++ei)
            {
                auto* evt = clip.sequence.getEventPointer(ei);
                if (!evt->message.isNoteOn()) continue;
                int note = evt->message.getNoteNumber();
                double t = evt->message.getTimeStamp();
                float nx = cx + (float)(t / clip.lengthBeats * cw);
                if (nx < headerWidth) continue;
                float ny = (float)(y + 2 + (127 - note) * (trackHeight - 4) / 128.0f);
                g.fillRect(nx, ny, juce::jmax(1.0f, cw * 0.02f), 1.0f);
            }

            // Clip border (clipped)
            g.setColour(track.colour);
            g.drawRoundedRectangle(drawX, (float)(y + 2), drawW,
                                   (float)(trackHeight - 4), 3.0f, 1.0f);

            // Clip name (if wide enough)
            if (drawW > 40)
            {
                g.setColour(juce::Colours::white.withAlpha(0.7f));
                g.setFont(9.0f);
                int noteCount = 0;
                for (int ei = 0; ei < clip.sequence.getNumEvents(); ++ei)
                    if (clip.sequence.getEventPointer(ei)->message.isNoteOn()) noteCount++;
                g.drawText(juce::String(noteCount) + " notes",
                           (int)(drawX + 4), y + 2, (int)(drawW - 8), 12,
                           juce::Justification::topLeft);
            }
        }

        // U4 — audio clip waveform thumbnails
        for (auto& aclip : track.audioClips)
        {
            float cx = beatToX(aclip.startBeat);
            float cw = beatToX(aclip.startBeat + aclip.lengthBeats) - cx;
            if (cx + cw < headerWidth || cx > getWidth()) continue;
            float drawX = juce::jmax(cx, (float)headerWidth);
            float drawW = juce::jmin(cx + cw, (float)getWidth()) - drawX;
            if (drawW <= 1.0f) continue;

            g.setColour(track.colour.withAlpha(0.35f));
            g.fillRoundedRectangle(drawX, (float)(y + 2), drawW,
                                   (float)(trackHeight - 16), 3.0f);

            // V6 — stereo waveform: L in top half, R in bottom half (if present)
            const int nCh    = aclip.buffer.getNumChannels();
            const int nSamp  = aclip.buffer.getNumSamples();
            const int clipTop = y + 2;
            const int clipBot = y + trackHeight - 16;
            const int clipH   = clipBot - clipTop;
            const bool stereo = (nCh >= 2) && clipH >= 12;
            if (nSamp > 0 && drawW > 1.0f)
            {
                const float srcStart = (float)((drawX - cx) / cw * nSamp);
                const float srcEnd   = (float)((drawX + drawW - cx) / cw * nSamp);
                const int px = (int)drawW;

                auto drawChannel = [&](int ch, int topY, int botY)
                {
                    const int midY  = (topY + botY) / 2;
                    const int halfH = (botY - topY) / 2 - 1;
                    if (halfH <= 0) return;
                    auto* rp = aclip.buffer.getReadPointer(ch);
                    for (int i = 0; i < px; ++i)
                    {
                        int a = (int)(srcStart + (srcEnd - srcStart) * i / (float)px);
                        int b = (int)(srcStart + (srcEnd - srcStart) * (i + 1) / (float)px);
                        a = juce::jlimit(0, nSamp - 1, a);
                        b = juce::jlimit(a + 1, nSamp, b);
                        float lo = 0.0f, hi = 0.0f;
                        for (int k = a; k < b; ++k)
                        { lo = juce::jmin(lo, rp[k]); hi = juce::jmax(hi, rp[k]); }
                        int y0 = midY - (int)(hi * halfH);
                        int y1 = midY - (int)(lo * halfH);
                        g.drawVerticalLine((int)drawX + i, (float)y0, (float)y1);
                    }
                };

                g.setColour(juce::Colours::white.withAlpha(0.65f));
                if (stereo)
                {
                    const int midLine = clipTop + clipH / 2;
                    drawChannel(0, clipTop, midLine);
                    drawChannel(1, midLine, clipBot);
                    g.setColour(juce::Colour(0xFF303030));
                    g.drawHorizontalLine(midLine, (float)drawX, (float)(drawX + drawW));
                }
                else
                {
                    drawChannel(0, clipTop, clipBot);
                }
            }
        }

        // T5 — Inline automation lane (volume) overlay at row bottom (12px)
        for (auto& lane : track.automation)
        {
            if (lane.paramId != "volume" || lane.points.empty()) continue;
            const int laneTop = y + trackHeight - 14;
            const int laneH   = 12;

            g.setColour(juce::Colour(0x40000000));
            g.fillRect(headerWidth, laneTop, getWidth() - headerWidth, laneH);

            juce::Path path;
            bool started = false;
            for (auto& pt : lane.points)
            {
                float px = beatToX(pt.beat);
                if (px < headerWidth) continue;
                float py = laneTop + laneH * (1.0f - juce::jlimit(0.0f, 1.0f, pt.value));
                if (! started) { path.startNewSubPath(px, py); started = true; }
                else            path.lineTo(px, py);
                g.setColour(juce::Colour(0xFF4CAF50));
                g.fillEllipse(px - 2.0f, py - 2.0f, 4.0f, 4.0f);
            }
            g.setColour(juce::Colour(0xFF4CAF50));
            g.strokePath(path, juce::PathStrokeType(1.0f));
        }

        // Row divider
        g.setColour(juce::Colour(0xFF333333));
        g.drawHorizontalLine(y + trackHeight - 1, 0.0f, (float)getWidth());
    }

    // Beat grid lines
    g.setColour(juce::Colour(0xFF2A2A2A));
    double firstBeat = scrollXBeats;
    double lastBeat = scrollXBeats + beatsVisible;

    for (double beat = std::floor(firstBeat); beat <= lastBeat; beat += 1.0)
    {
        float x = beatToX(beat);
        if (x < headerWidth) continue;

        if (std::fmod(beat, 4.0) < 0.001)
            g.setColour(juce::Colour(0xFF3A3A3A));
        else
            g.setColour(juce::Colour(0xFF2A2A2A));
        g.drawVerticalLine((int)x, 0.0f, (float)(numTracks * trackHeight - scrollYPixels));
    }

    // Playhead
    if (audioEngine.isPlaying() || audioEngine.getPositionBeats() > 0.001)
    {
        float px = beatToX(audioEngine.getPositionBeats());
        if (px >= headerWidth && px < getWidth())
        {
            g.setColour(juce::Colours::white);
            g.drawVerticalLine((int)px, 0.0f, (float)(numTracks * trackHeight - scrollYPixels));
        }
    }

    // Re-draw header backgrounds on top to cover any overflow
    for (int i = 0; i < numTracks; ++i)
    {
        auto& track = tracks[(size_t)i];
        int y = i * trackHeight - scrollYPixels;
        if (y + trackHeight < 0 || y > getHeight()) continue;

        // V4 — selected track header accent
        const bool isSelected = (track.id == selectedTrackId);
        g.setColour(isSelected ? juce::Colour(0xFF2F3E5A) : juce::Colour(0xFF252525));
        g.fillRect(0, y, headerWidth, trackHeight);

        // AA6 — folder indent: walk parent chain to compute depth
        int indent = 0;
        int pid = track.parentTrackId;
        int safety = 0;
        while (pid >= 0 && safety++ < 8)
        {
            bool found = false;
            for (auto& t2 : tracks)
                if (t2.id == pid) { pid = t2.parentTrackId; found = true; break; }
            if (! found) break;
            ++indent;
        }
        const int xOffset = indent * 12;

        g.setColour(track.colour);
        g.fillRect(xOffset, y, isSelected ? 6 : 4, trackHeight);
        if (track.isFolder)
        {
            g.setColour(juce::Colour(0xFF666666));
            g.fillRect(xOffset + 6, y + 4, 2, trackHeight - 8);
        }

        g.setColour(track.mute ? juce::Colours::grey : juce::Colours::white);
        g.setFont(13.0f);
        g.drawText(track.name, 10, y, headerWidth - 50, trackHeight,
                   juce::Justification::centredLeft);

        g.setFont(10.0f);
        if (track.mute)
        {
            g.setColour(juce::Colour(0xFFFF5722));
            g.drawText("M", headerWidth - 40, y, 16, trackHeight, juce::Justification::centred);
        }
        if (track.solo)
        {
            g.setColour(juce::Colour(0xFFFFC107));
            g.drawText("S", headerWidth - 20, y, 16, trackHeight, juce::Justification::centred);
        }
    }

    // Header/timeline divider
    g.setColour(juce::Colour(0xFF444444));
    g.drawVerticalLine(headerWidth, 0.0f, (float)getHeight());

    // Bar numbers at top
    g.setColour(juce::Colour(0xFF909090));
    g.setFont(9.0f);
    for (double beat = std::floor(firstBeat / 4.0) * 4.0; beat <= lastBeat; beat += 4.0)
    {
        float x = beatToX(beat);
        if (x >= headerWidth)
            g.drawText(juce::String((int)(beat / 4.0) + 1), (int)x + 2, 0, 30, 14,
                       juce::Justification::centredLeft);
    }
}

void ArrangementView::resized()
{
    int numTracks = audioEngine.getTrackModel().getNumTracks();
    int btnY = numTracks * trackHeight - scrollYPixels + 8;
    addTrackButton.setBounds(10, juce::jmax(8, btnY), headerWidth - 20, 28);
}

void ArrangementView::timerCallback()
{
    if (audioEngine.isPlaying())
    {
        // Auto-scroll to follow playhead
        double pos = audioEngine.getPositionBeats();
        if (pos > scrollXBeats + beatsVisible * 0.8)
            scrollXBeats = (float)(pos - beatsVisible * 0.2);
        repaint();
    }
}

void ArrangementView::mouseDown(const juce::MouseEvent& e)
{
    // Z1 — allow right-click (context menu) but block content edits while recording
    if (isRecording && isRecording() && ! e.mods.isRightButtonDown()) return;

    auto& tracks = audioEngine.getTrackModel().getTracks();
    int trackIdx = (e.y + scrollYPixels) / trackHeight;

    if (trackIdx < 0 || trackIdx >= (int)tracks.size()) return;

    // Right-click = context menu
    if (e.mods.isRightButtonDown())
    {
        showTrackContextMenu(trackIdx);
        return;
    }

    if (e.x < headerWidth)
    {
        // V4 — clicking header selects the track
        selectedTrackId = tracks[(size_t)trackIdx].id;

        // Click on M/S area
        int localX = e.x;
        if (localX >= headerWidth - 42 && localX < headerWidth - 26)
        {
            tracks[(size_t)trackIdx].mute = !tracks[(size_t)trackIdx].mute;
        }
        else if (localX >= headerWidth - 22)
        {
            tracks[(size_t)trackIdx].solo = !tracks[(size_t)trackIdx].solo;
        }
        repaint();
        return;
    }

    // Click on timeline - find clip
    auto& track = tracks[(size_t)trackIdx];
    selectedTrackId = track.id;                   // U7
    double clickBeat = xToBeat((float)e.x);

    // U1 — check if click falls in the automation lane strip at row bottom
    const int rowTop = trackIdx * trackHeight - scrollYPixels;
    const int laneTop = rowTop + trackHeight - 14;
    const int laneBot = rowTop + trackHeight - 2;
    if (e.y >= laneTop && e.y <= laneBot)
    {
        // Find or create "volume" lane
        AutomationLane* lane = nullptr;
        for (auto& l : track.automation)
            if (l.paramId == "volume") { lane = &l; break; }
        if (lane == nullptr)
        {
            AutomationLane nl; nl.paramId = "volume";
            track.automation.push_back(std::move(nl));
            lane = &track.automation.back();
        }

        const float laneH = (float)(laneBot - laneTop);
        const float value = juce::jlimit(0.0f, 1.0f,
            1.0f - (float)(e.y - laneTop) / laneH);

        // Shift+click or mods.isCommandDown → delete nearest point
        if (e.mods.isShiftDown() || e.mods.isCommandDown())
        {
            int best = -1;
            float bestDx = 1e9f;
            for (int i = 0; i < (int)lane->points.size(); ++i)
            {
                float px = beatToX(lane->points[i].beat);
                if (std::abs(px - e.x) < bestDx) { bestDx = std::abs(px - e.x); best = i; }
            }
            if (best >= 0 && bestDx <= 8.0f)
            {
                lane->points.erase(lane->points.begin() + best);
                repaint();
            }
            return;
        }

        // Grab existing point (within 8px) or add new one
        int hitIdx = -1;
        for (int i = 0; i < (int)lane->points.size(); ++i)
        {
            float px = beatToX(lane->points[i].beat);
            if (std::abs(px - e.x) <= 8.0f) { hitIdx = i; break; }
        }
        if (hitIdx < 0)
        {
            lane->addPoint(juce::jmax(0.0, clickBeat), value);
            for (int i = 0; i < (int)lane->points.size(); ++i)
                if (std::abs(lane->points[i].beat - clickBeat) < 1e-6) { hitIdx = i; break; }
        }
        autoDragTrackIdx = trackIdx;
        autoDragPointIdx = hitIdx;
        repaint();
        return;
    }

    // X3 — audio clip trim handle hit test (±6px from either edge)
    for (int ci = 0; ci < (int)track.audioClips.size(); ++ci)
    {
        auto& ac = track.audioClips[(size_t)ci];
        const float leftX  = beatToX(ac.startBeat);
        const float rightX = beatToX(ac.startBeat + ac.lengthBeats);
        if (std::abs((float)e.x - leftX) <= 6.0f)
        {
            trimMode = TrimMode::Left;
            trimTrackIdx = trackIdx;
            trimClipIdx  = ci;
            return;
        }
        if (std::abs((float)e.x - rightX) <= 6.0f)
        {
            trimMode = TrimMode::Right;
            trimTrackIdx = trackIdx;
            trimClipIdx  = ci;
            return;
        }
    }

    for (auto& clip : track.clips)
    {
        if (clickBeat >= clip.startBeat && clickBeat < clip.startBeat + clip.lengthBeats)
        {
            if (onClipSelected) onClipSelected(&clip);
            return;
        }
    }
}

void ArrangementView::mouseDrag(const juce::MouseEvent& e)
{
    // X3 — audio clip trim drag
    if (trimMode != TrimMode::None && trimTrackIdx >= 0 && trimClipIdx >= 0)
    {
        auto& tracks = audioEngine.getTrackModel().getTracks();
        if (trimTrackIdx >= (int)tracks.size()) { trimMode = TrimMode::None; return; }
        auto& track = tracks[(size_t)trimTrackIdx];
        if (trimClipIdx >= (int)track.audioClips.size()) { trimMode = TrimMode::None; return; }
        auto& ac = track.audioClips[(size_t)trimClipIdx];

        const double newBeat = juce::jmax(0.0, xToBeat((float)e.x));
        const double bps = audioEngine.getTempo() / 60.0;

        if (trimMode == TrimMode::Left)
        {
            const double deltaBeats = newBeat - ac.startBeat;
            const juce::int64 deltaSamples = (juce::int64)(deltaBeats / bps * ac.sourceSampleRate);
            const juce::int64 newOffset = ac.sourceOffsetSamples + deltaSamples;
            if (newOffset >= 0 && newOffset < ac.buffer.getNumSamples())
            {
                ac.sourceOffsetSamples = newOffset;
                ac.startBeat = newBeat;
                ac.lengthBeats = juce::jmax(0.1, ac.lengthBeats - deltaBeats);
            }
        }
        else // Right
        {
            ac.lengthBeats = juce::jmax(0.1, newBeat - ac.startBeat);
        }
        repaint();
        return;
    }

    if (autoDragTrackIdx < 0 || autoDragPointIdx < 0) return;
    auto& tracks = audioEngine.getTrackModel().getTracks();
    if (autoDragTrackIdx >= (int)tracks.size()) { autoDragPointIdx = -1; return; }
    auto& track = tracks[(size_t)autoDragTrackIdx];

    AutomationLane* lane = nullptr;
    for (auto& l : track.automation)
        if (l.paramId == "volume") { lane = &l; break; }
    if (lane == nullptr || autoDragPointIdx >= (int)lane->points.size())
    { autoDragPointIdx = -1; return; }

    const int rowTop = autoDragTrackIdx * trackHeight - scrollYPixels;
    const int laneTop = rowTop + trackHeight - 14;
    const int laneH   = 12;

    auto& pt = lane->points[(size_t)autoDragPointIdx];
    pt.beat  = juce::jmax(0.0, xToBeat((float)e.x));
    pt.value = juce::jlimit(0.0f, 1.0f,
        1.0f - (float)(e.y - laneTop) / (float)laneH);

    // Resort + rediscover index
    double savedBeat = pt.beat;
    std::sort(lane->points.begin(), lane->points.end(),
              [](const AutomationPoint& a, const AutomationPoint& b)
              { return a.beat < b.beat; });
    for (int i = 0; i < (int)lane->points.size(); ++i)
        if (std::abs(lane->points[i].beat - savedBeat) < 1e-9)
        { autoDragPointIdx = i; break; }

    repaint();
}

void ArrangementView::mouseUp(const juce::MouseEvent&)
{
    autoDragTrackIdx = -1;
    autoDragPointIdx = -1;
    trimMode = TrimMode::None;     // X3
    trimTrackIdx = -1;
    trimClipIdx = -1;
}

void ArrangementView::mouseDoubleClick(const juce::MouseEvent& e)
{
    if (e.x < headerWidth) return;

    auto& tracks = audioEngine.getTrackModel().getTracks();
    int trackIdx = (e.y + scrollYPixels) / trackHeight;
    if (trackIdx < 0 || trackIdx >= (int)tracks.size()) return;

    auto& track = tracks[(size_t)trackIdx];
    double clickBeat = xToBeat((float)e.x);

    // Check if double-clicking on existing clip
    for (auto& clip : track.clips)
        if (clickBeat >= clip.startBeat && clickBeat < clip.startBeat + clip.lengthBeats)
            return; // already exists

    // Create new empty clip at snapped position (4-beat grid)
    const double snapped = std::floor(clickBeat / 4.0) * 4.0;

    // W1 — undoable path when UndoManager is available
    if (undoManager != nullptr)
    {
        undoManager->beginNewTransaction("Add clip");
        undoManager->perform(new AddClipCmd(&track, snapped, 4.0));
    }
    else
    {
        MidiClip newClip;
        newClip.startBeat = snapped;
        newClip.lengthBeats = 4.0;
        track.clips.push_back(newClip);
    }

    if (! track.clips.empty() && onClipSelected)
        onClipSelected(&track.clips.back());
    repaint();
}

void ArrangementView::mouseWheelMove(const juce::MouseEvent& e, const juce::MouseWheelDetails& w)
{
    if (e.mods.isCtrlDown())
    {
        // Zoom horizontal
        float factor = w.deltaY > 0 ? 0.85f : 1.18f;
        beatsVisible = juce::jlimit(4.0f, 256.0f, beatsVisible * factor);
    }
    else if (e.mods.isShiftDown() || e.x > headerWidth)
    {
        // Horizontal scroll
        scrollXBeats = juce::jmax(0.0f, scrollXBeats - w.deltaY * beatsVisible * 0.1f);
    }
    else
    {
        // Vertical scroll
        int maxScroll = juce::jmax(0, audioEngine.getTrackModel().getNumTracks() * trackHeight - getHeight());
        scrollYPixels = juce::jlimit(0, maxScroll, scrollYPixels - (int)(w.deltaY * 60));
    }
    resized();
    repaint();
}

void ArrangementView::showTrackContextMenu(int trackIdx)
{
    auto& tracks = audioEngine.getTrackModel().getTracks();
    if (trackIdx < 0 || trackIdx >= (int)tracks.size()) return;

    auto& track = tracks[(size_t)trackIdx];

    juce::PopupMenu menu;
    menu.addItem(1, "Rename Track...");
    menu.addItem(2, "Delete Track");
    menu.addSeparator();
    menu.addItem(3, "Mute", true, track.mute);
    menu.addItem(4, "Solo", true, track.solo);
    menu.addSeparator();

    // Instrument submenu
    juce::PopupMenu instMenu;
    instMenu.addItem(100, "Grand Piano");
    instMenu.addItem(104, "Electric Piano");
    instMenu.addItem(116, "Organ");
    instMenu.addItem(124, "Nylon Guitar");
    instMenu.addItem(125, "Steel Guitar");
    instMenu.addItem(132, "Acoustic Bass");
    instMenu.addItem(138, "Synth Bass");
    instMenu.addItem(140, "Violin");
    instMenu.addItem(148, "String Ensemble");
    instMenu.addItem(156, "Trumpet");
    instMenu.addItem(173, "Flute");
    instMenu.addItem(180, "Square Lead");
    instMenu.addItem(188, "Pad (New Age)");
    menu.addSubMenu("Instrument", instMenu);

    // Colour submenu
    juce::PopupMenu colMenu;
    colMenu.addItem(200, "Blue");
    colMenu.addItem(201, "Green");
    colMenu.addItem(202, "Red");
    colMenu.addItem(203, "Orange");
    colMenu.addItem(204, "Purple");
    colMenu.addItem(205, "Teal");
    colMenu.addItem(206, "Gold");
    colMenu.addItem(207, "Pink");
    menu.addSubMenu("Colour", colMenu);

    // Automation submenu (S5)
    juce::PopupMenu autoMenu;
    autoMenu.addItem(300, "Edit Volume...");
    autoMenu.addItem(301, "Edit Pan...");
    menu.addSubMenu("Automation", autoMenu);

    // U2 — Output Bus submenu
    juce::PopupMenu busMenu;
    busMenu.addItem(400, "Master", true, track.outputBusId == 0);
    for (auto& bus : audioEngine.getBusModel().getBuses())
    {
        if (bus.id == 0) continue;
        const int menuId = 400 + bus.id;
        busMenu.addItem(menuId, bus.name, true, track.outputBusId == bus.id);
    }
    menu.addSubMenu("Output Bus", busMenu);

    // AA6 / BB1 — Folder / Parent submenu
    menu.addItem(500, track.isFolder ? "Unmark as Folder" : "Mark as Folder");
    if (track.isFolder)
        menu.addItem(501, track.collapsed ? "Expand children" : "Collapse children");
    juce::PopupMenu parentMenu;
    parentMenu.addItem(600, "(top-level)", true, track.parentTrackId < 0);
    for (auto& other : tracks)
    {
        if (other.id == track.id) continue;
        parentMenu.addItem(600 + other.id, other.name, true, track.parentTrackId == other.id);
    }
    menu.addSubMenu("Parent Folder", parentMenu);

    menu.showMenuAsync(juce::PopupMenu::Options(),
        [this, trackIdx, &track](int result)
        {
            if (result == 1)
            {
                auto* aw = new juce::AlertWindow("Rename Track", "Enter new name:",
                                                  juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("name", track.name);
                aw->addButton("OK", 1);
                aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, &track, aw](int r)
                    {
                        if (r == 1)
                            track.name = aw->getTextEditorContents("name");
                        delete aw;
                        if (onTrackListChanged) onTrackListChanged();
                        repaint();
                    }), false);
            }
            else if (result == 2)
            {
                PluginEditorManager::instance().closeAllForTrack(track.id); // V5
                audioEngine.getPluginChains().clearTrack(track.id);
                audioEngine.getTrackModel().removeTrack(track.id);
                if (onTrackListChanged) onTrackListChanged();
                resized();
                repaint();
            }
            else if (result == 3) { track.mute = !track.mute; repaint(); }
            else if (result == 4) { track.solo = !track.solo; repaint(); }
            else if (result >= 100 && result < 200)
            {
                int program = result - 100;
                audioEngine.getSynthEngine().setProgramForChannel(track.midiChannel - 1, program);
                repaint();
            }
            else if (result >= 200 && result < 300)
            {
                static const juce::Colour palette[] = {
                    juce::Colour(0xFF5E81AC), juce::Colour(0xFFA3BE8C),
                    juce::Colour(0xFFBF616A), juce::Colour(0xFFD08770),
                    juce::Colour(0xFFB48EAD), juce::Colour(0xFF8FBCBB),
                    juce::Colour(0xFFEBCB8B), juce::Colour(0xFFE0789E)
                };
                track.colour = palette[result - 200];
                if (onTrackListChanged) onTrackListChanged();
                repaint();
            }
            else if (result == 300 || result == 301)
            {
                const juce::String pid = (result == 300) ? "volume" : "pan";
                double maxBeats = 16.0;
                for (auto& c : track.clips)
                    maxBeats = juce::jmax(maxBeats, c.startBeat + c.lengthBeats);
                AutomationEditor::launchModal(track, pid, maxBeats);
            }
            else if (result >= 400 && result < 500)
            {
                track.outputBusId = result - 400; // 0=master, else busId
                repaint();
            }
            else if (result == 500) // AA6 — folder toggle
            {
                track.isFolder = ! track.isFolder;
                repaint();
            }
            else if (result == 501) // BB1 — collapse toggle (render impact: Sprint 12)
            {
                track.collapsed = ! track.collapsed;
                repaint();
            }
            else if (result == 600) // top-level
            {
                track.parentTrackId = -1;
                repaint();
            }
            else if (result > 600 && result < 700) // parent assignment
            {
                const int parentId = result - 600;
                if (parentId != track.id) track.parentTrackId = parentId;
                repaint();
            }
        });
}
