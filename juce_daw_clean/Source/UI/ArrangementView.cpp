/*
 * MidiGPT DAW - ArrangementView.cpp
 */

#include "ArrangementView.h"

ArrangementView::ArrangementView(AudioEngine& engine)
    : audioEngine(engine)
{
    addTrackButton.onClick = [this] {
        auto& t = audioEngine.getTrackModel().addTrack();
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

        g.setColour(juce::Colour(0xFF252525));
        g.fillRect(0, y, headerWidth, trackHeight);

        g.setColour(track.colour);
        g.fillRect(0, y, 4, trackHeight);

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
        // Click on M/S area
        int localX = e.x;
        if (localX >= headerWidth - 42 && localX < headerWidth - 26)
        {
            tracks[(size_t)trackIdx].mute = !tracks[(size_t)trackIdx].mute;
            repaint();
        }
        else if (localX >= headerWidth - 22)
        {
            tracks[(size_t)trackIdx].solo = !tracks[(size_t)trackIdx].solo;
            repaint();
        }
        return;
    }

    // Click on timeline - find clip
    auto& track = tracks[(size_t)trackIdx];
    double clickBeat = xToBeat((float)e.x);

    for (auto& clip : track.clips)
    {
        if (clickBeat >= clip.startBeat && clickBeat < clip.startBeat + clip.lengthBeats)
        {
            if (onClipSelected) onClipSelected(&clip);
            return;
        }
    }
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
    double snapped = std::floor(clickBeat / 4.0) * 4.0;
    MidiClip newClip;
    newClip.startBeat = snapped;
    newClip.lengthBeats = 4.0;
    track.clips.push_back(newClip);

    if (onClipSelected) onClipSelected(&track.clips.back());
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
        });
}
