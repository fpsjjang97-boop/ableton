/*
 * MidiGPT DAW - ArrangementView.cpp
 */

#include "ArrangementView.h"
#include "../Automation/AutomationEditor.h"
#include "../Plugin/PluginEditorWindow.h"
#include "../Command/EditCommands.h"
#include "../Audio/ClipStretchUtil.h"  // OOO4 — offline stretch helper
#include "LookAndFeel.h"          // palette tokens (review fix — unify hex → token)

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
        rebuildVisibleTracks();
        repaint();
    };
    addAndMakeVisible(addTrackButton);
    startTimerHz(30);
}

// CC1 — build list of track indices that are not hidden by collapsed parents
void ArrangementView::rebuildVisibleTracks()
{
    visibleTrackIndices.clear();
    auto& tracks = audioEngine.getTrackModel().getTracks();

    for (int i = 0; i < (int)tracks.size(); ++i)
    {
        // Walk parent chain — if any ancestor is collapsed, hide this track
        bool hidden = false;
        int pid = tracks[(size_t)i].parentTrackId;
        int safety = 0;
        while (pid >= 0 && safety++ < 8)
        {
            bool found = false;
            for (auto& t2 : tracks)
            {
                if (t2.id == pid)
                {
                    if (t2.collapsed) { hidden = true; break; }
                    pid = t2.parentTrackId;
                    found = true;
                    break;
                }
            }
            if (!found || hidden) break;
        }
        if (!hidden)
            visibleTrackIndices.push_back(i);
    }
}

// HH3 — Y position helpers using per-track displayHeight
int ArrangementView::yForVisibleRow(int vi) const
{
    auto& tracks = audioEngine.getTrackModel().getTracks();
    int y = 0;
    for (int i = 0; i < vi && i < (int)visibleTrackIndices.size(); ++i)
        y += tracks[(size_t)visibleTrackIndices[(size_t)i]].displayHeight;
    return y - scrollYPixels;
}

int ArrangementView::heightForVisibleRow(int vi) const
{
    auto& tracks = audioEngine.getTrackModel().getTracks();
    if (vi < 0 || vi >= (int)visibleTrackIndices.size()) return trackHeight;
    return tracks[(size_t)visibleTrackIndices[(size_t)vi]].displayHeight;
}

int ArrangementView::totalVisibleHeight() const
{
    auto& tracks = audioEngine.getTrackModel().getTracks();
    int h = 0;
    for (auto idx : visibleTrackIndices)
        h += tracks[(size_t)idx].displayHeight;
    return h;
}

int ArrangementView::visibleTrackAtY(int y) const
{
    auto& tracks = audioEngine.getTrackModel().getTracks();
    int cumY = -scrollYPixels;
    for (int vi = 0; vi < (int)visibleTrackIndices.size(); ++vi)
    {
        int th = tracks[(size_t)visibleTrackIndices[(size_t)vi]].displayHeight;
        if (y >= cumY && y < cumY + th)
            return visibleTrackIndices[(size_t)vi];
        cumY += th;
    }
    return -1;
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
    g.fillAll(juce::Colour(MetallicLookAndFeel::bgDarkest));

    auto& tracks = audioEngine.getTrackModel().getTracks();
    // CC1 — use visible tracks for rendering
    if (visibleTrackIndices.empty() && !tracks.empty())
        const_cast<ArrangementView*>(this)->rebuildVisibleTracks();
    int numVisible = (int)visibleTrackIndices.size();
    float timelineW = (float)(getWidth() - headerWidth);

    // Draw timeline content first, then headers on top
    g.saveState();

    for (int vi = 0; vi < numVisible; ++vi)
    {
        auto& track = tracks[(size_t)visibleTrackIndices[(size_t)vi]];
        int y = yForVisibleRow(vi);
        int th = track.displayHeight;
        if (y + th < 0 || y > getHeight()) continue;

        // Header bg
        g.setColour(juce::Colour(MetallicLookAndFeel::bgHeader));
        g.fillRect(0, y, headerWidth, th);

        // Colour bar
        g.setColour(track.colour);
        g.fillRect(0, y, 4, th);

        // Track name — width derived from header button layout (review fix).
        g.setColour(track.mute ? juce::Colours::grey : juce::Colours::white);
        g.setFont(13.0f);
        g.drawText(track.name, headerNameLeft, y, headerNameWidth(), th,
                   juce::Justification::centredLeft);

        // R/M/S indicators. All three share the headerBtnLeft/right helpers
        // so paint rects match the mouseDown hit rects automatically.
        g.setFont(10.0f);
        {
            const bool armed = (audioEngine.getAudioRecordingTrack() == track.id);
            g.setColour(armed ? juce::Colour(MetallicLookAndFeel::danger)
                              : juce::Colour(MetallicLookAndFeel::textDim));
            g.drawText("R", headerBtnLeft(0), y, headerBtnW, th, juce::Justification::centred);
        }
        if (track.mute)
        {
            g.setColour(juce::Colour(MetallicLookAndFeel::warning));
            g.drawText("M", headerBtnLeft(1), y, headerBtnW, th, juce::Justification::centred);
        }
        if (track.solo)
        {
            g.setColour(juce::Colour(MetallicLookAndFeel::meterYellow));
            g.drawText("S", headerBtnLeft(2), y, headerBtnW, th, juce::Justification::centred);
        }

        // Timeline row bg — alternate row shading uses palette tokens.
        g.setColour(vi % 2 == 0 ? juce::Colour(MetallicLookAndFeel::bgPanel)
                                : juce::Colour(MetallicLookAndFeel::bgDark));
        g.fillRect(headerWidth, y, (int)timelineW, th);

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

            // KK2 + RR1 — per-clip colour, dimmed if muted
            auto clipCol = clip.hasCustomColour() ? clip.colour : track.colour;
            float clipAlpha = track.mute ? 0.2f : 0.6f;
            g.setColour(clipCol.withAlpha(clipAlpha));
            g.fillRoundedRectangle(drawX, (float)(y + 2), drawW,
                                   (float)(th - 4), 3.0f);

            // Mini note preview (clipped) — RR1: dim if muted
            g.setColour(juce::Colours::white.withAlpha(track.mute ? 0.15f : 0.5f));
            for (int ei = 0; ei < clip.sequence.getNumEvents(); ++ei)
            {
                auto* evt = clip.sequence.getEventPointer(ei);
                if (!evt->message.isNoteOn()) continue;
                int note = evt->message.getNoteNumber();
                double t = evt->message.getTimeStamp();
                float nx = cx + (float)(t / clip.lengthBeats * cw);
                if (nx < headerWidth) continue;
                float ny = (float)(y + 2 + (127 - note) * (th - 4) / 128.0f);
                g.fillRect(nx, ny, juce::jmax(1.0f, cw * 0.02f), 1.0f);
            }

            // Clip border (clipped)
            g.setColour(clipCol);
            g.drawRoundedRectangle(drawX, (float)(y + 2), drawW,
                                   (float)(th - 4), 3.0f, 1.0f);

            // TT2 — loop indicator: dashed vertical lines at loop boundaries
            if (clip.loopEnabled && clip.loopLengthBeats > 0.0)
            {
                g.setColour(juce::Colours::white.withAlpha(0.25f));
                for (double lb = clip.loopLengthBeats; lb < clip.lengthBeats; lb += clip.loopLengthBeats)
                {
                    float lx = beatToX(clip.startBeat + lb);
                    if (lx > drawX && lx < drawX + drawW)
                    {
                        for (int dy = y + 4; dy < y + th - 4; dy += 4)
                            g.drawVerticalLine((int)lx, (float)dy, (float)(dy + 2));
                    }
                }
            }

            // NN3 — selection highlight
            for (auto* sc : selectedClips)
            {
                if (sc == &clip)
                {
                    g.setColour(juce::Colours::white.withAlpha(0.15f));
                    g.fillRoundedRectangle(drawX, (float)(y + 2), drawW, (float)(th - 4), 3.0f);
                    g.setColour(juce::Colours::white.withAlpha(0.6f));
                    g.drawRoundedRectangle(drawX, (float)(y + 2), drawW, (float)(th - 4), 3.0f, 1.5f);
                    break;
                }
            }

            // MM4 — clip name (or note count if no name)
            if (drawW > 40)
            {
                g.setColour(juce::Colours::white.withAlpha(0.7f));
                g.setFont(9.0f);
                juce::String label;
                if (clip.name.isNotEmpty())
                    label = clip.name;
                else
                {
                    int noteCount = 0;
                    for (int ei = 0; ei < clip.sequence.getNumEvents(); ++ei)
                        if (clip.sequence.getEventPointer(ei)->message.isNoteOn()) noteCount++;
                    label = juce::String(noteCount) + " notes";
                }
                // VV4 — append bar count
                int bars = juce::jmax(1, (int)std::round(clip.lengthBeats / 4.0));
                label += " | " + juce::String(bars) + "bar";
                g.drawText(label, (int)(drawX + 4), y + 2, (int)(drawW - 8), 12,
                           juce::Justification::topLeft);

                // Take-count badge so users can spot clips with stashed
                // takes from the arrangement (match the PianoRoll badge
                // styling — amber pill, compact).
                if (! clip.takes.empty() && drawW > 60)
                {
                    const int badgeW = 26;
                    const int badgeH = 12;
                    const int bx = (int) (drawX + drawW) - badgeW - 2;
                    const int by = y + 2;
                    g.setColour (juce::Colour (MetallicLookAndFeel::accent).withAlpha (0.9f));
                    g.fillRoundedRectangle ((float) bx, (float) by,
                                             (float) badgeW, (float) badgeH, 2.5f);
                    g.setColour (juce::Colour (MetallicLookAndFeel::bgDarkest));
                    g.setFont (9.0f);
                    g.drawText ("T:" + juce::String ((int) clip.takes.size()),
                                bx, by, badgeW, badgeH,
                                juce::Justification::centred);
                }
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
                                   (float)(th - 16), 3.0f);

            // V6 — stereo waveform: L in top half, R in bottom half (if present)
            const int nCh    = aclip.buffer.getNumChannels();
            const int nSamp  = aclip.buffer.getNumSamples();
            const int clipTop = y + 2;
            const int clipBot = y + th - 16;
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

            // LL6 — audio clip source name
            if (aclip.sourceName.isNotEmpty() && drawW > 30)
            {
                g.setColour(juce::Colours::white.withAlpha(0.7f));
                g.setFont(9.0f);
                g.drawText(aclip.sourceName, (int)(drawX + 4), y + 2, (int)(drawW - 8), 12,
                           juce::Justification::topLeft);
            }

            // PPP1 — fade region overlays + drag handles. The fade triangle
            // is drawn in clip-local coords (not clipped by drawX) so the
            // ramp geometry stays correct even when the clip extends past
            // the viewport. Draw order: dim fill → bright edge line → handle.
            {
                const float clipTopF = (float) clipTop;
                const float clipBotF = (float) clipBot;
                const float clipLeftX  = beatToX (aclip.startBeat);
                const float clipRightX = beatToX (aclip.startBeat + aclip.lengthBeats);

                auto drawHandle = [&] (float hx)
                {
                    const float s = 6.0f;
                    const float hy = clipTopF;
                    g.setColour (juce::Colours::yellow.withAlpha (0.9f));
                    g.fillRect (hx - s * 0.5f, hy, s, s);
                    g.setColour (juce::Colours::black.withAlpha (0.7f));
                    g.drawRect (hx - s * 0.5f, hy, s, s, 1.0f);
                };

                if (aclip.fadeInBeats > 0.0)
                {
                    const float fadeEndX = beatToX (aclip.startBeat + aclip.fadeInBeats);
                    juce::Path p;
                    p.startNewSubPath (clipLeftX, clipBotF);
                    p.lineTo          (fadeEndX, clipTopF);
                    p.lineTo          (clipLeftX, clipTopF);
                    p.closeSubPath();
                    g.setColour (juce::Colours::black.withAlpha (0.45f));
                    g.fillPath (p);
                    g.setColour (juce::Colours::white.withAlpha (0.75f));
                    g.drawLine (clipLeftX, clipBotF, fadeEndX, clipTopF, 1.2f);
                }
                if (aclip.fadeOutBeats > 0.0)
                {
                    const float fadeStartX = beatToX (aclip.startBeat + aclip.lengthBeats - aclip.fadeOutBeats);
                    juce::Path p;
                    p.startNewSubPath (clipRightX, clipBotF);
                    p.lineTo          (fadeStartX, clipTopF);
                    p.lineTo          (clipRightX, clipTopF);
                    p.closeSubPath();
                    g.setColour (juce::Colours::black.withAlpha (0.45f));
                    g.fillPath (p);
                    g.setColour (juce::Colours::white.withAlpha (0.75f));
                    g.drawLine (fadeStartX, clipTopF, clipRightX, clipBotF, 1.2f);
                }

                // Always show handles at the current fade boundary so the
                // user can grab them even when fadeInBeats == 0 (handle sits
                // flush against the clip edge). Skip when the handle would
                // fall outside the viewport.
                const float hIn  = beatToX (aclip.startBeat + aclip.fadeInBeats);
                const float hOut = beatToX (aclip.startBeat + aclip.lengthBeats - aclip.fadeOutBeats);
                if (hIn  >= drawX - 4 && hIn  <= drawX + drawW + 4) drawHandle (hIn);
                if (hOut >= drawX - 4 && hOut <= drawX + drawW + 4) drawHandle (hOut);
            }
        }

        // T5 + CC6 — Inline automation lane (volume) overlay at row bottom (12px)
        for (auto& lane : track.automation)
        {
            if (lane.paramId != "volume" || lane.points.empty()) continue;
            const int laneTop = y + th - 14;
            const int laneH   = 12;

            g.setColour(juce::Colour(0x40000000));
            g.fillRect(headerWidth, laneTop, getWidth() - headerWidth, laneH);

            // CC6 — render curves by sampling valueAt() between points
            juce::Path path;
            bool started = false;
            const float startBeatF = (float)juce::jmax(0.0, (double)scrollXBeats);
            const float endBeatF   = scrollXBeats + beatsVisible;

            // Draw the curve by sampling at pixel resolution
            for (int px = headerWidth; px < getWidth(); ++px)
            {
                double beat = xToBeat((float)px);
                float val = lane.valueAt(beat, 0.5f);
                float py = laneTop + laneH * (1.0f - juce::jlimit(0.0f, 1.0f, val));
                if (!started) { path.startNewSubPath((float)px, py); started = true; }
                else path.lineTo((float)px, py);
            }
            g.setColour(juce::Colour(0xFF4CAF50));
            g.strokePath(path, juce::PathStrokeType(1.0f));

            // Draw control points. Points with a non-zero outgoing curve
            // are drawn in amber + 1 px larger so the user can see which
            // segments are bent (and which are linear).
            for (auto& pt : lane.points)
            {
                float px = beatToX(pt.beat);
                if (px < headerWidth || px > getWidth()) continue;
                float py = laneTop + laneH * (1.0f - juce::jlimit(0.0f, 1.0f, pt.value));
                const bool curved = std::abs(pt.curve) > 0.001f;
                g.setColour(curved ? juce::Colour(MetallicLookAndFeel::accent)
                                   : juce::Colour(0xFF4CAF50));
                const float r = curved ? 3.0f : 2.0f;
                g.fillEllipse(px - r, py - r, r * 2.0f, r * 2.0f);
            }
        }

        // Row divider
        g.setColour(juce::Colour(0xFF333333));
        g.drawHorizontalLine(y + th - 1, 0.0f, (float)getWidth());
    }

    // NN5 — alternating bar background for readability
    {
        double fb = scrollXBeats;
        double lb = scrollXBeats + beatsVisible;
        int tvh = totalVisibleHeight() - scrollYPixels;
        for (double b = std::floor(fb / 8.0) * 8.0; b <= lb; b += 8.0)
        {
            float bx = beatToX(b);
            float bw = beatToX(b + 4.0) - bx;
            if (bx + bw > headerWidth)
            {
                g.setColour(juce::Colour(0x08FFFFFF));
                g.fillRect(juce::jmax((float)headerWidth, bx), 0.0f, bw, (float)tvh);
            }
        }
    }

    // LL2 — Snap-aware beat grid lines
    {
        double firstBeat = scrollXBeats;
        double lastBeat = scrollXBeats + beatsVisible;
        double gridStep = snapBeats > 0.0 ? snapBeats : 1.0;
        // Don't draw too many lines — clamp to minimum pixel spacing
        float minPx = 4.0f;
        while (gridStep * (float)(getWidth() - headerWidth) / beatsVisible < minPx && gridStep < 4.0)
            gridStep *= 2.0;

        for (double beat = std::floor(firstBeat / gridStep) * gridStep; beat <= lastBeat; beat += gridStep)
        {
            float x = beatToX(beat);
            if (x < headerWidth) continue;

            if (std::fmod(beat, 4.0) < 0.001)
                g.setColour(juce::Colour(0xFF3A3A3A));
            else if (std::fmod(beat, 1.0) < 0.001)
                g.setColour(juce::Colour(0xFF2A2A2A));
            else
                g.setColour(juce::Colour(0xFF222222)); // sub-beat lines
            g.drawVerticalLine((int)x, 0.0f, (float)(totalVisibleHeight() - scrollYPixels));
        }
    }

    // Playhead
    if (audioEngine.isPlaying() || audioEngine.getPositionBeats() > 0.001)
    {
        float px = beatToX(audioEngine.getPositionBeats());
        if (px >= headerWidth && px < getWidth())
        {
            g.setColour(juce::Colours::white);
            g.drawVerticalLine((int)px, 0.0f, (float)(totalVisibleHeight() - scrollYPixels));
        }
    }

    // VV6 — stop position marker (dim grey line)
    if (lastStopBeat >= 0.0 && ! audioEngine.isPlaying())
    {
        float spx = beatToX(lastStopBeat);
        if (spx >= headerWidth && spx < getWidth())
        {
            g.setColour(juce::Colour(0x60FF8800));
            g.drawVerticalLine((int)spx, 0.0f, (float)(totalVisibleHeight() - scrollYPixels));
        }
    }

    // Re-draw header backgrounds on top to cover any overflow
    for (int vi = 0; vi < numVisible; ++vi)
    {
        auto& track = tracks[(size_t)visibleTrackIndices[(size_t)vi]];
        int y = yForVisibleRow(vi);
        int th = track.displayHeight;
        if (y + th < 0 || y > getHeight()) continue;

        // V4 — selected track header accent
        const bool isSelected = (track.id == selectedTrackId);
        // PP2 + UU5 — solo=gold, selected=blue, recording=red flash
        juce::Colour headerBg = juce::Colour(0xFF252525);
        if (track.solo)    headerBg = juce::Colour(0xFF3A3520);
        if (isSelected)    headerBg = juce::Colour(0xFF2F3E5A);
        if (track.armed && audioEngine.isPlaying())
        {
            bool flash = ((int)(juce::Time::getMillisecondCounter() / 500) % 2) == 0;
            headerBg = flash ? juce::Colour(0xFF3A1515) : juce::Colour(0xFF2A1010);
        }
        g.setColour(headerBg);
        g.fillRect(0, y, headerWidth, th);

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
        g.fillRect(xOffset, y, isSelected ? 6 : 4, th);
        if (track.isFolder)
        {
            g.setColour(juce::Colour(0xFF666666));
            g.fillRect(xOffset + 6, y + 4, 2, th - 8);
        }

        g.setColour(track.mute ? juce::Colours::grey : juce::Colours::white);
        g.setFont(12.0f);
        g.drawText(track.name, 10 + xOffset, y, headerWidth - 70 - xOffset, th / 2,
                   juce::Justification::bottomLeft);
        // TT3 — track number + UU2 frozen indicator
        g.setColour(juce::Colour(0xFF505050));
        g.setFont(8.0f);
        juce::String numLabel = juce::String(visibleTrackIndices[(size_t)vi] + 1);
        if (track.frozen) numLabel += "F";
        g.drawText(numLabel, xOffset + 1, y + 2, 18, 10, juce::Justification::centredLeft);

        // VV3 — MIDI channel number
        g.setColour(juce::Colour(0xFF606060));
        g.setFont(8.0f);
        g.drawText("ch" + juce::String(track.midiChannel),
                   headerWidth - 70, y + 2, 24, 10, juce::Justification::centredRight);

        // QQ1 — instrument name
        if (track.userProgram >= 0)
        {
            g.setColour(juce::Colour(0xFF808080));
            g.setFont(9.0f);
            g.drawText(juce::MidiMessage::getGMInstrumentName(track.userProgram),
                       10 + xOffset, y + th / 2, headerWidth - 70 - xOffset, th / 2 - 4,
                       juce::Justification::topLeft);
        }

        g.setFont(10.0f);
        if (track.mute)
        {
            g.setColour(juce::Colour(0xFFFF5722));
            g.drawText("M", headerWidth - 56, y, 16, th, juce::Justification::centred);
        }
        if (track.solo)
        {
            g.setColour(juce::Colour(0xFFFFC107));
            g.drawText("S", headerWidth - 38, y, 16, th, juce::Justification::centred);
        }
        // II5 — arm indicator
        g.setColour(track.armed ? juce::Colour(0xFFFF1744) : juce::Colour(0xFF555555));
        g.drawText("R", headerWidth - 18, y, 16, th, juce::Justification::centred);

        // UU1 — output bus label (bottom-left)
        {
            juce::String busLabel = ">Master";
            if (track.outputBusId != 0)
                if (auto* b = audioEngine.getBusModel().getBus(track.outputBusId))
                    busLabel = ">" + b->name;
            g.setColour(juce::Colour(0xFF505050));
            g.setFont(7.0f);
            g.drawText(busLabel, 4 + xOffset, y + th - 12, 60, 10,
                       juce::Justification::centredLeft);
        }

        // RR2 — volume dB display (bottom-right of header)
        {
            float db = juce::Decibels::gainToDecibels(track.volume, -60.0f);
            g.setColour(juce::Colour(0xFF606060));
            g.setFont(8.0f);
            g.drawText(juce::String(db, 1) + "dB",
                       headerWidth - 58, y + th - 12, 40, 10,
                       juce::Justification::centredRight);
        }

        // PP6 — mini VU bar at header bottom
        {
            float vuL = audioEngine.getTrackVuL(track.id);
            float vuR = audioEngine.getTrackVuR(track.id);
            float vu = juce::jmax(vuL, vuR);
            int barW = (int)(vu * (headerWidth - 8));
            if (barW > 0)
            {
                g.setColour(vu > 0.9f ? juce::Colour(0xFFF44336)
                          : vu > 0.6f ? juce::Colour(0xFFFFC107)
                                      : juce::Colour(0xFF4CAF50));
                g.fillRect(4, y + th - 3, juce::jmin(barW, headerWidth - 8), 2);
            }
        }
    }

    // GG4 — Loop region highlight
    if (audioEngine.getMidiEngine().isLooping())
    {
        double ls = audioEngine.getMidiEngine().getLoopStart();
        double le = audioEngine.getMidiEngine().getLoopEnd();
        float lx1 = beatToX(ls);
        float lx2 = beatToX(le);
        if (lx2 > headerWidth && lx1 < getWidth())
        {
            float drawL = juce::jmax((float)headerWidth, lx1);
            float drawR = juce::jmin((float)getWidth(), lx2);

            // Tinted overlay
            g.setColour(juce::Colour(0x155E81AC));
            g.fillRect(drawL, 0.0f, drawR - drawL, (float)(totalVisibleHeight() - scrollYPixels));

            // Loop bar at top
            g.setColour(juce::Colour(0xFF5E81AC));
            g.fillRect(drawL, 0.0f, drawR - drawL, 4.0f);

            // Brackets
            g.drawVerticalLine((int)drawL, 0.0f, (float)(totalVisibleHeight() - scrollYPixels));
            g.drawVerticalLine((int)drawR, 0.0f, (float)(totalVisibleHeight() - scrollYPixels));
        }
    }

    // EE6 — Markers at top of timeline
    for (auto& mk : audioEngine.getMidiEngine().getMarkers())
    {
        float mx = beatToX(mk.beat);
        if (mx < headerWidth || mx > getWidth()) continue;
        g.setColour(mk.colour.withAlpha(0.7f));
        g.drawVerticalLine((int)mx, 0.0f, (float)(totalVisibleHeight() - scrollYPixels));

        // Marker flag
        g.setColour(mk.colour);
        g.fillRect((int)mx, 0, 2, 14);
        juce::Path tri;
        tri.addTriangle((float)mx, 0.0f, (float)mx + 8.0f, 0.0f, (float)mx, 8.0f);
        g.fillPath(tri);

        g.setColour(juce::Colours::black);
        g.setFont(8.0f);
        g.drawText(mk.name, (int)mx + 3, 1, 60, 10, juce::Justification::centredLeft);
    }

    // NN3 — selection rectangle rubber band
    if (selectionDrag)
    {
        int sx1 = juce::jmin(selDragStart.x, getMouseXYRelative().x);
        int sy1 = juce::jmin(selDragStart.y, getMouseXYRelative().y);
        int sw = std::abs(getMouseXYRelative().x - selDragStart.x);
        int sh = std::abs(getMouseXYRelative().y - selDragStart.y);
        g.setColour(juce::Colour(0x305E81AC));
        g.fillRect(sx1, sy1, sw, sh);
        g.setColour(juce::Colour(0x805E81AC));
        g.drawRect(sx1, sy1, sw, sh, 1);
    }

    // Header/timeline divider
    g.setColour(juce::Colour(0xFF444444));
    g.drawVerticalLine(headerWidth, 0.0f, (float)getHeight());

    // DD5 — Time-sig aware bar numbers at top
    // Walk beat positions using the time-signature map to compute correct bar boundaries
    {
        g.setFont(9.0f);
        auto& me = audioEngine.getMidiEngine();
        double beat = 0.0;
        int barNum = 1;

        // Advance to first visible bar
        while (beat + 32.0 < (double)scrollXBeats)
        {
            auto ts = me.timeSigAt(beat);
            double barLen = (ts.den > 0) ? (double)ts.num * (4.0 / (double)ts.den) : 4.0; // D2
            beat += barLen;
            ++barNum;
        }

        while (beat <= scrollXBeats + beatsVisible + 16.0)
        {
            auto ts = me.timeSigAt(beat);
            double barLen = (ts.den > 0) ? (double)ts.num * (4.0 / (double)ts.den) : 4.0; // D2

            float x = beatToX(beat);
            if (x >= headerWidth && x < getWidth())
            {
                g.setColour(juce::Colour(0xFF909090));
                g.drawText(juce::String(barNum), (int)x + 2, 0, 40, 14,
                           juce::Justification::centredLeft);

                // Show time sig if it changes at this bar
                auto prevTs = me.timeSigAt(juce::jmax(0.0, beat - 0.01));
                if (beat < 0.01 || prevTs.num != ts.num || prevTs.den != ts.den)
                {
                    g.setColour(juce::Colour(0xFFFFCC00));
                    g.setFont(8.0f);
                    g.drawText(juce::String(ts.num) + "/" + juce::String(ts.den),
                               (int)x + 2, 12, 30, 10, juce::Justification::centredLeft);
                    g.setFont(9.0f);
                }
            }

            beat += barLen;
            ++barNum;
        }
    }

    // PP5 — secondary time markers (seconds) below bar numbers
    {
        double bps = audioEngine.getTempo() / 60.0;
        if (bps > 0.0)
        {
            g.setColour(juce::Colour(0xFF606060));
            g.setFont(7.0f);
            // Show every 5 seconds
            double startSec = scrollXBeats / bps;
            double endSec = (scrollXBeats + beatsVisible) / bps;
            for (double sec = std::floor(startSec / 5.0) * 5.0; sec <= endSec; sec += 5.0)
            {
                float px = beatToX(sec * bps);
                if (px >= headerWidth && px < getWidth())
                {
                    int m = (int)sec / 60;
                    int s = (int)sec % 60;
                    g.drawText(juce::String::formatted("%d:%02d", m, s),
                               (int)px + 2, 22, 30, 8, juce::Justification::centredLeft);
                }
            }
        }
    }
}

void ArrangementView::resized()
{
    int btnY = totalVisibleHeight() - scrollYPixels + 8; // HH3
    addTrackButton.setBounds(10, juce::jmax(8, btnY), headerWidth - 20, 28);
}

void ArrangementView::timerCallback()
{
    if (audioEngine.isPlaying())
    {
        // EE5 — auto-scroll only when follow mode is on
        if (followPlayhead)
        {
            double pos = audioEngine.getPositionBeats();
            if (pos > scrollXBeats + beatsVisible * 0.8)
                scrollXBeats = (float)(pos - beatsVisible * 0.2);
        }
        repaint();
    }
}

void ArrangementView::mouseDown(const juce::MouseEvent& e)
{
    // Z1 — allow right-click (context menu) but block content edits while recording
    if (isRecording && isRecording() && ! e.mods.isRightButtonDown()) return;

    // JJ1 + LL4 — ruler area (top 16px)
    if (e.y < 16 && e.x >= headerWidth)
    {
        if (e.mods.isShiftDown()) // LL4 — shift+click = start loop drag
        {
            loopDragging = true;
            loopDragStartBeat = juce::jmax(0.0, xToBeat((float)e.x));
            return;
        }
        // JJ1 + NN1 — click = set playhead + start scrub
        double beat = juce::jmax(0.0, xToBeat((float)e.x));
        audioEngine.getMidiEngine().setPositionBeats(beat);
        rulerScrubbing = true;
        repaint();
        return;
    }

    auto& tracks = audioEngine.getTrackModel().getTracks();
    // CC1 — map visible row → actual track index
    int trackIdx = visibleTrackAtY(e.y);
    if (trackIdx < 0) return;

    // Right-click = context menu
    if (e.mods.isRightButtonDown())
    {
        // GG2 + SS3 — check if right-clicking on a MIDI clip or audio clip
        if (e.x >= headerWidth)
        {
            auto& trk = tracks[(size_t)trackIdx];
            double clickBt = xToBeat((float)e.x);

            // MIDI clips
            for (int ci = 0; ci < (int)trk.clips.size(); ++ci)
            {
                auto& c = trk.clips[(size_t)ci];
                if (clickBt >= c.startBeat && clickBt < c.startBeat + c.lengthBeats)
                {
                    showClipContextMenu(trk, ci);
                    return;
                }
            }

            // SS3 — audio clips
            for (int ai = 0; ai < (int)trk.audioClips.size(); ++ai)
            {
                auto& ac = trk.audioClips[(size_t)ai];
                if (clickBt >= ac.startBeat && clickBt < ac.startBeat + ac.lengthBeats)
                {
                    juce::PopupMenu acMenu;
                    acMenu.addItem(1, "Pitch Shift...");
                    acMenu.addItem(2, "Playback Rate...");
                    acMenu.addItem(3, "Fade In/Out...");
                    acMenu.addSeparator();
                    // OOO4 — offline pitch/time stretch (ClipStretchUtil).
                    // Bakes the ratio+pitch into the clip buffer itself so
                    // playback doesn't pay the coupled-rate compromise.
                    acMenu.addItem(5, "Apply Stretch...");
                    acMenu.addSeparator();
                    acMenu.addItem(4, "Delete Audio Clip");
                    acMenu.showMenuAsync(juce::PopupMenu::Options(),
                        [this, tid = trk.id, ai](int r) {
                            auto* tp = audioEngine.getTrackModel().getTrack(tid);
                            if (tp == nullptr || ai >= (int)tp->audioClips.size()) return;
                            auto& clip = tp->audioClips[(size_t)ai];
                            if (r == 1) // Pitch
                            {
                                auto* aw = new juce::AlertWindow("Pitch Shift", "Semitones (-24 to +24):",
                                    juce::MessageBoxIconType::NoIcon);
                                aw->addTextEditor("val", juce::String(clip.pitchSemitones, 1));
                                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                                    [this, tid, ai, aw](int rr) {
                                        auto* tp3 = audioEngine.getTrackModel().getTrack(tid);
                                        if (rr == 1 && tp3 != nullptr && ai < (int)tp3->audioClips.size())
                                            tp3->audioClips[(size_t)ai].pitchSemitones = (float)juce::jlimit(-24.0, 24.0,
                                            aw->getTextEditorContents("val").getDoubleValue());
                                        delete aw; repaint();
                                    }), false);
                            }
                            else if (r == 2) // Rate
                            {
                                auto* aw = new juce::AlertWindow("Playback Rate", "Rate (0.25 to 4.0):",
                                    juce::MessageBoxIconType::NoIcon);
                                aw->addTextEditor("val", juce::String(clip.playbackRate, 2));
                                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                                    [this, tid, ai, aw](int rr) {
                                        auto* tp3 = audioEngine.getTrackModel().getTrack(tid);
                                        if (rr == 1 && tp3 != nullptr && ai < (int)tp3->audioClips.size())
                                            tp3->audioClips[(size_t)ai].playbackRate = juce::jlimit(0.25, 4.0,
                                            aw->getTextEditorContents("val").getDoubleValue());
                                        delete aw; repaint();
                                    }), false);
                            }
                            else if (r == 3) // Fade
                            {
                                auto* aw = new juce::AlertWindow("Fade In/Out", "Beats (e.g. 0.5):",
                                    juce::MessageBoxIconType::NoIcon);
                                aw->addTextEditor("in", juce::String(clip.fadeInBeats, 2));
                                aw->addTextEditor("out", juce::String(clip.fadeOutBeats, 2));
                                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                                    [this, tid, ai, aw](int rr) {
                                        auto* tp3 = audioEngine.getTrackModel().getTrack(tid);
                                        if (rr == 1 && tp3 != nullptr && ai < (int)tp3->audioClips.size()) {
                                            tp3->audioClips[(size_t)ai].fadeInBeats = juce::jmax(0.0, aw->getTextEditorContents("in").getDoubleValue());
                                            tp3->audioClips[(size_t)ai].fadeOutBeats = juce::jmax(0.0, aw->getTextEditorContents("out").getDoubleValue());
                                        }
                                        delete aw; repaint();
                                    }), false);
                            }
                            else if (r == 5) // OOO4 — Apply Stretch
                            {
                                auto* aw = new juce::AlertWindow("Apply Stretch",
                                    "Time ratio (>1 longer, <1 shorter) + Pitch scale (>1 up, <1 down).\n"
                                    "RubberBand backend required — if not built with MIDIGPTDAW_WITH_RUBBERBAND,\n"
                                    "the clip is left unchanged (fallback to coupled playback rate).",
                                    juce::MessageBoxIconType::NoIcon);
                                aw->addTextEditor("time",  "1.0");
                                aw->addTextEditor("pitch", "1.0");
                                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                                    [this, tid, ai, aw](int rr) {
                                        auto* tp3 = audioEngine.getTrackModel().getTrack(tid);
                                        if (rr == 1 && tp3 != nullptr
                                            && ai < (int)tp3->audioClips.size())
                                        {
                                            const double tr = juce::jlimit(0.25, 4.0,
                                                aw->getTextEditorContents("time").getDoubleValue());
                                            const double ps = juce::jlimit(0.5, 2.0,
                                                aw->getTextEditorContents("pitch").getDoubleValue());
                                            auto r = midigpt_daw::stretchAudioClip(
                                                tp3->audioClips[(size_t)ai], tr, ps);
                                            if (! r.success)
                                                juce::AlertWindow::showMessageBoxAsync(
                                                    juce::MessageBoxIconType::InfoIcon,
                                                    "Stretch not applied",
                                                    juce::String("Backend: ") + r.backend
                                                        + "\nReason: " + r.reason
                                                        + "\n\nClip unchanged; playback will use the "
                                                          "coupled playbackRate / pitchSemitones fields.");
                                        }
                                        delete aw; repaint();
                                    }), false);
                            }
                            else if (r == 4) // Delete
                            {
                                tp->audioClips.erase(tp->audioClips.begin() + ai);
                                repaint();
                            }
                        });
                    return;
                }
            }
        }
        showTrackContextMenu(trackIdx);
        return;
    }

    if (e.x < headerWidth)
    {
        // V4 + SS1 — clicking header selects track; Shift = select all clips in track
        selectedTrackId = tracks[(size_t)trackIdx].id;
        if (e.mods.isShiftDown())
        {
            for (auto& clip : tracks[(size_t)trackIdx].clips)
                selectedClips.push_back(&clip);
            repaint();
        }

        // Click on M/S area
        int localX = e.x;
        // NN2 — check if click is near bottom edge of track for height drag
        {
            int rowY = 0;
            for (int vi2 = 0; vi2 < (int)visibleTrackIndices.size(); ++vi2)
            {
                if (visibleTrackIndices[(size_t)vi2] == trackIdx)
                {
                    rowY = yForVisibleRow(vi2);
                    break;
                }
            }
            auto& trks = audioEngine.getTrackModel().getTracks();
            int bottomEdge = rowY + trks[(size_t)trackIdx].displayHeight;
            if (std::abs(e.y - bottomEdge) <= 4)
            {
                heightDragVi = trackIdx;
                heightDragStartY = e.y;
                heightDragOrigH = trks[(size_t)trackIdx].displayHeight;
                return;
            }
        }

        // II5 — R (arm) button area
        if (localX >= headerWidth - 20)
        {
            tracks[(size_t)trackIdx].armed = !tracks[(size_t)trackIdx].armed;
            int tid = tracks[(size_t)trackIdx].armed ? tracks[(size_t)trackIdx].id : -1;
            audioEngine.setRecordingTargetTrack(tid);
            repaint();
            return;
        }
        if (localX >= headerBtnLeft(0) && localX < headerBtnRight(0))
        {
            // PPP3 — audio record arm toggle. Clicking R sets this track as
            // the audio recording target; clicking R on the already-armed
            // track disarms. Transport state is left alone — user still
            // needs to press Play (or the Space bar) to start capture, and
            // DD1's callback only writes when midiEngine.isPlaying(). Hint
            // the user via the status bar so the two-step sequence is
            // discoverable without a tutorial overlay.
            const int curArmed = audioEngine.getAudioRecordingTrack();
            const int newId    = tracks[(size_t)trackIdx].id;
            const bool armNow  = (curArmed != newId);
            audioEngine.setAudioRecordingTrack(armNow ? newId : -1);
            if (onStatusMessage)
            {
                onStatusMessage (armNow
                    ? juce::String("Armed '") + tracks[(size_t)trackIdx].name
                      + "' — press Space to record audio"
                    : juce::String("Disarmed audio recording"));
            }
        }
        else if (localX >= headerBtnLeft(1) && localX < headerBtnRight(1))
        {
            tracks[(size_t)trackIdx].mute = !tracks[(size_t)trackIdx].mute;
        }
        else if (localX >= headerBtnLeft(2) && localX < headerBtnRight(2))
        {
            // II3 — exclusive solo: plain click unsolos others, Ctrl = additive
            bool newSolo = !tracks[(size_t)trackIdx].solo;
            if (newSolo && !e.mods.isCtrlDown())
            {
                for (auto& t2 : tracks)
                    t2.solo = false;
            }
            tracks[(size_t)trackIdx].solo = newSolo;
        }
        else
        {
            // GG3 — start track reorder drag from header area
            trackDragFrom = trackIdx;
        }
        repaint();
        return;
    }

    // Click on timeline - find clip
    auto& track = tracks[(size_t)trackIdx];
    selectedTrackId = track.id;                   // U7
    double clickBeat = xToBeat((float)e.x);

    // U1 — check if click falls in the automation lane strip at row bottom
    // CC1 — find visible row for this track index
    int visRow = 0;
    for (int vi = 0; vi < (int)visibleTrackIndices.size(); ++vi)
        if (visibleTrackIndices[(size_t)vi] == trackIdx) { visRow = vi; break; }
    const int visRowH = heightForVisibleRow(visRow);
    const int rowTop = yForVisibleRow(visRow);
    const int laneTop = rowTop + visRowH - 14;
    const int laneBot = rowTop + visRowH - 2;
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

        // Alt+drag on an existing point bends the segment that leaves it
        // (writes to points[hitIdx].curve; valueAt already applies a
        // power curve when |curve| > 0.001).
        if (e.mods.isAltDown() && hitIdx >= 0 && hitIdx < (int)lane->points.size())
        {
            autoDragMode       = AutoDragMode::Curve;
            autoDragStartY     = e.y;
            autoDragStartCurve = lane->points[(size_t)hitIdx].curve;
        }
        else
        {
            autoDragMode = AutoDragMode::Value;
        }
        repaint();
        return;
    }

    // PPP2 — shared helper: snapshot the drag-target clip's state so
    // mouseUp can build an AudioClipEditCmd covering fade and trim drags
    // through a single undo command.
    auto snapForUndo = [&] (AudioClip& ac)
    {
        audioDragClip                      = &ac;
        audioDragBeforeStartBeat           = ac.startBeat;
        audioDragBeforeLengthBeats         = ac.lengthBeats;
        audioDragBeforeSourceOffsetSamples = ac.sourceOffsetSamples;
        audioDragBeforeFadeInBeats         = ac.fadeInBeats;
        audioDragBeforeFadeOutBeats        = ac.fadeOutBeats;
    };

    // PPP1 — audio clip fade handle hit test. Top fadeHandleHeight px of
    // the clip row; ±5 px X tolerance. Must run BEFORE the trim hit test
    // because a fresh fade handle at fadeInBeats==0 sits on the clip edge,
    // and we want drags in the top strip to adjust fade, not trim.
    {
        const int clipTopY = rowTop + 2;                          // matches paint()
        if (e.y >= clipTopY && e.y <= clipTopY + fadeHandleHeight)
        {
            for (int ci = 0; ci < (int)track.audioClips.size(); ++ci)
            {
                auto& ac = track.audioClips[(size_t)ci];
                const float hIn  = beatToX(ac.startBeat + ac.fadeInBeats);
                const float hOut = beatToX(ac.startBeat + ac.lengthBeats - ac.fadeOutBeats);
                if (std::abs((float)e.x - hIn) <= 5.0f)
                {
                    fadeMode     = FadeMode::In;
                    fadeTrackIdx = trackIdx;
                    fadeClipIdx  = ci;
                    snapForUndo(ac);
                    return;
                }
                if (std::abs((float)e.x - hOut) <= 5.0f)
                {
                    fadeMode     = FadeMode::Out;
                    fadeTrackIdx = trackIdx;
                    fadeClipIdx  = ci;
                    snapForUndo(ac);
                    return;
                }
            }
        }
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
            snapForUndo(ac);
            return;
        }
        if (std::abs((float)e.x - rightX) <= 6.0f)
        {
            trimMode = TrimMode::Right;
            trimTrackIdx = trackIdx;
            trimClipIdx  = ci;
            snapForUndo(ac);
            return;
        }
    }

    for (auto& clip : track.clips)
    {
        if (clickBeat >= clip.startBeat && clickBeat < clip.startBeat + clip.lengthBeats)
        {
            // HH2 — check right edge for resize handle (±6px)
            float rightEdgeX = beatToX(clip.startBeat + clip.lengthBeats);
            if (std::abs((float)e.x - rightEdgeX) <= 6.0f)
            {
                resizeClip = &clip;
                resizeClipOrigLen = clip.lengthBeats;
                return;
            }

            if (onClipSelected) onClipSelected(&clip);
            // FF3 — start clip drag
            dragClip = &clip;
            dragClipOrigStart = clip.startBeat;
            dragClipOrigLen   = clip.lengthBeats;
            dragOffsetBeats   = clickBeat - clip.startBeat;
            return;
        }
    }

    // JJ4 — no clip hit → start selection rectangle
    if (e.x >= headerWidth)
    {
        selectionDrag = true;
        selDragStart = e.getPosition();
        selectedClips.clear();
    }
}

void ArrangementView::mouseDrag(const juce::MouseEvent& e)
{
    // NN2 — track height drag
    if (heightDragVi >= 0)
    {
        auto& trks = audioEngine.getTrackModel().getTracks();
        if (heightDragVi < (int)trks.size())
        {
            int delta = e.y - heightDragStartY;
            trks[(size_t)heightDragVi].displayHeight = juce::jmax(24, heightDragOrigH + delta);
            resized();
            repaint();
        }
        return;
    }

    // NN1 — ruler scrub
    if (rulerScrubbing)
    {
        double beat = juce::jmax(0.0, xToBeat((float)e.x));
        audioEngine.getMidiEngine().setPositionBeats(beat);
        repaint();
        return;
    }

    // LL4 — loop drag
    if (loopDragging)
    {
        double endBeat = juce::jmax(0.0, xToBeat((float)e.x));
        double lo = juce::jmin(loopDragStartBeat, endBeat);
        double hi = juce::jmax(loopDragStartBeat, endBeat);
        audioEngine.getMidiEngine().setLoopRegion(lo, hi);
        audioEngine.getMidiEngine().setLooping(true);
        repaint();
        return;
    }

    // JJ4 — selection rectangle drag
    if (selectionDrag)
    {
        // Find clips within the rectangle
        selectedClips.clear();
        int x1 = juce::jmin(selDragStart.x, e.x);
        int x2 = juce::jmax(selDragStart.x, e.x);
        double b1 = xToBeat((float)x1);
        double b2 = xToBeat((float)x2);
        int y1 = juce::jmin(selDragStart.y, e.y);
        int y2 = juce::jmax(selDragStart.y, e.y);

        auto& tracks = audioEngine.getTrackModel().getTracks();
        for (int vi = 0; vi < (int)visibleTrackIndices.size(); ++vi)
        {
            int vy = yForVisibleRow(vi);
            int vh = heightForVisibleRow(vi);
            if (vy + vh < y1 || vy > y2) continue;
            auto& trk = tracks[(size_t)visibleTrackIndices[(size_t)vi]];
            for (auto& clip : trk.clips)
            {
                if (clip.startBeat + clip.lengthBeats > b1 && clip.startBeat < b2)
                    selectedClips.push_back(&clip);
            }
        }
        repaint();
        return;
    }

    // HH2 — clip resize drag
    if (resizeClip != nullptr)
    {
        double newEnd = juce::jmax(resizeClip->startBeat + 0.25,
                                   xToBeat((float)e.x));
        newEnd = snapBeat(newEnd); // II2
        resizeClip->lengthBeats = newEnd - resizeClip->startBeat;
        repaint();
        return;
    }

    // GG3 — track reorder drag
    if (trackDragFrom >= 0 && e.x < headerWidth)
    {
        int targetRow = visibleTrackAtY(e.y);
        if (targetRow >= 0) trackDragTo = targetRow;
        repaint();
        return;
    }

    // FF3 — clip drag move
    if (dragClip != nullptr && e.x >= headerWidth)
    {
        double newBeat = juce::jmax(0.0, xToBeat((float)e.x) - dragOffsetBeats);
        newBeat = snapBeat(newBeat); // II2
        dragClip->startBeat = newBeat;
        repaint();
        return;
    }

    // PPP1 — audio clip fade drag. Updates fadeInBeats / fadeOutBeats
    // based on the mouse beat; clamped against the opposing fade and a
    // minimum sliver (1/16 beat) to avoid zero-length gaps between fades.
    if (fadeMode != FadeMode::None && fadeTrackIdx >= 0 && fadeClipIdx >= 0)
    {
        auto& tracks = audioEngine.getTrackModel().getTracks();
        if (fadeTrackIdx >= (int)tracks.size()) { fadeMode = FadeMode::None; return; }
        auto& track = tracks[(size_t)fadeTrackIdx];
        if (fadeClipIdx >= (int)track.audioClips.size()) { fadeMode = FadeMode::None; return; }
        auto& ac = track.audioClips[(size_t)fadeClipIdx];

        const double mouseBeat   = xToBeat((float)e.x);
        const double minSliver   = 0.0625;   // 1/16 beat minimum between fades
        const double maxAllowed  = juce::jmax(0.0, ac.lengthBeats - minSliver);

        if (fadeMode == FadeMode::In)
        {
            const double raw = snapBeat(mouseBeat - ac.startBeat);
            ac.fadeInBeats = juce::jlimit(0.0,
                                           juce::jmax(0.0, maxAllowed - ac.fadeOutBeats),
                                           raw);
        }
        else // FadeMode::Out
        {
            const double clipEnd = ac.startBeat + ac.lengthBeats;
            const double raw     = snapBeat(clipEnd - mouseBeat);
            ac.fadeOutBeats = juce::jlimit(0.0,
                                            juce::jmax(0.0, maxAllowed - ac.fadeInBeats),
                                            raw);
        }
        repaint();
        return;
    }

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

    // Find visible row for autoDragTrackIdx
    int adVi = 0;
    for (int v = 0; v < (int)visibleTrackIndices.size(); ++v)
        if (visibleTrackIndices[(size_t)v] == autoDragTrackIdx) { adVi = v; break; }
    const int rowTop = yForVisibleRow(adVi);
    const int adH = heightForVisibleRow(adVi);
    const int laneTop = rowTop + adH - 14;
    const int laneH   = 12;

    auto& pt = lane->points[(size_t)autoDragPointIdx];

    if (autoDragMode == AutoDragMode::Curve)
    {
        // ~50 px vertical drag = full ±1 curve. Dragging up makes the
        // segment bulge up (convex, positive curve); down = concave.
        const float dy = (float)(e.y - autoDragStartY);
        pt.curve = juce::jlimit(-1.0f, 1.0f,
            autoDragStartCurve - dy * 0.02f);
        repaint();
        return;
    }

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
    // NN2 — end track height drag
    heightDragVi = -1;

    // NN1 — end ruler scrub
    rulerScrubbing = false;

    // LL4 — end loop drag
    loopDragging = false;

    // JJ4 — end selection drag
    selectionDrag = false;

    // HH2 — finalize clip resize with undo
    if (resizeClip != nullptr && resizeClip->lengthBeats != resizeClipOrigLen)
    {
        if (undoManager != nullptr)
        {
            undoManager->beginNewTransaction("Resize clip");
            undoManager->perform(new MoveClipCmd(resizeClip,
                resizeClip->startBeat, resizeClipOrigLen,
                resizeClip->startBeat, resizeClip->lengthBeats));
        }
    }
    resizeClip = nullptr;

    // GG3 — finalize track reorder
    if (trackDragFrom >= 0 && trackDragTo >= 0 && trackDragFrom != trackDragTo)
    {
        audioEngine.getTrackModel().moveTrack(trackDragFrom, trackDragTo);
        rebuildVisibleTracks();
        if (onTrackListChanged) onTrackListChanged();
    }
    trackDragFrom = -1;
    trackDragTo   = -1;

    // FF3 — finalize clip drag with undo
    if (dragClip != nullptr)
    {
        if (undoManager != nullptr
            && (dragClip->startBeat != dragClipOrigStart
                || dragClip->lengthBeats != dragClipOrigLen))
        {
            undoManager->beginNewTransaction("Move clip");
            undoManager->perform(new MoveClipCmd(dragClip,
                dragClipOrigStart, dragClipOrigLen,
                dragClip->startBeat, dragClip->lengthBeats));
        }
        dragClip = nullptr;
    }

    autoDragTrackIdx = -1;
    autoDragPointIdx = -1;
    // PPP2 — finalize fade/trim drag as a single AudioClipEditCmd on
    // the undo stack. Unified command covers the four fields the user
    // can touch during a drag (start/length/sourceOffset/fade in/out).
    if (audioDragClip != nullptr && undoManager != nullptr)
    {
        AudioClipEditCmd::Snap before;
        before.startBeat           = audioDragBeforeStartBeat;
        before.lengthBeats         = audioDragBeforeLengthBeats;
        before.sourceOffsetSamples = audioDragBeforeSourceOffsetSamples;
        before.fadeInBeats         = audioDragBeforeFadeInBeats;
        before.fadeOutBeats        = audioDragBeforeFadeOutBeats;
        auto after = AudioClipEditCmd::snapshot(*audioDragClip);

        const bool changed =
               before.startBeat           != after.startBeat
            || before.lengthBeats         != after.lengthBeats
            || before.sourceOffsetSamples != after.sourceOffsetSamples
            || before.fadeInBeats         != after.fadeInBeats
            || before.fadeOutBeats        != after.fadeOutBeats;

        if (changed)
        {
            undoManager->beginNewTransaction("Edit audio clip");
            undoManager->perform(new AudioClipEditCmd(audioDragClip, before, after));
        }
    }
    audioDragClip = nullptr;

    trimMode = TrimMode::None;     // X3
    trimTrackIdx = -1;
    trimClipIdx = -1;

    fadeMode     = FadeMode::None;  // PPP1
    fadeTrackIdx = -1;
    fadeClipIdx  = -1;
}

void ArrangementView::mouseDoubleClick(const juce::MouseEvent& e)
{
    // LL5 + MM2 — double-click header: name area = rename, bottom edge = reset height
    if (e.x < headerWidth)
    {
        int trackIdx = visibleTrackAtY(e.y);
        if (trackIdx >= 0)
        {
            auto& tracks = audioEngine.getTrackModel().getTracks();
            auto& track = tracks[(size_t)trackIdx];

            // MM2 — double-click on name area → inline rename
            if (e.x < headerWidth - 60)
            {
                auto* aw = new juce::AlertWindow("Rename Track", "",
                                                  juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("name", track.name);
                aw->addButton("OK", 1);
                aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, tid = track.id, aw](int r) {
                        auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                        if (r == 1 && tp2 != nullptr)
                            tp2->name = aw->getTextEditorContents("name");
                        delete aw;
                        if (onTrackListChanged) onTrackListChanged();
                        repaint();
                    }), false);
            }
            else // LL5 — reset height
            {
                track.displayHeight = 48;
                resized();
                repaint();
            }
        }
        return;
    }

    auto& tracks = audioEngine.getTrackModel().getTracks();
    // CC1 — map visible row
    int trackIdx = visibleTrackAtY(e.y);
    if (trackIdx < 0) return;

    auto& track = tracks[(size_t)trackIdx];
    double clickBeat = xToBeat((float)e.x);

    // Check if double-clicking on existing clip
    for (auto& clip : track.clips)
        if (clickBeat >= clip.startBeat && clickBeat < clip.startBeat + clip.lengthBeats)
            return; // already exists

    // Create new empty clip at snapped position
    const double snapped = snapBeat(clickBeat); // II2

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
        int maxScroll = juce::jmax(0, totalVisibleHeight() - getHeight()); // HH3
        scrollYPixels = juce::jlimit(0, maxScroll, scrollYPixels - (int)(w.deltaY * 60));
    }
    resized();
    repaint();
}

// GG2 — clip context menu: duplicate, split, delete
void ArrangementView::showClipContextMenu(Track& track, int clipIdx)
{
    juce::PopupMenu menu;
    menu.addItem(1, "Duplicate Clip");
    menu.addItem(2, "Split at Playhead");
    menu.addItem(3, "Delete Clip");
    menu.addItem(4, "Rename Clip..."); // MM4
    menu.addSeparator();
    // KK2 — clip colour
    juce::PopupMenu clipColMenu;
    clipColMenu.addItem(10, "Blue");
    clipColMenu.addItem(11, "Green");
    clipColMenu.addItem(12, "Red");
    clipColMenu.addItem(13, "Orange");
    clipColMenu.addItem(14, "Purple");
    clipColMenu.addItem(15, "Reset to Track");
    menu.addSubMenu("Clip Colour", clipColMenu);
    // SS4 — clip loop
    menu.addItem(20, track.clips[(size_t)clipIdx].loopEnabled ? "Loop: OFF" : "Loop: ON");
    if (track.clips[(size_t)clipIdx].loopEnabled)
        menu.addItem(21, "Set Loop Length...");
    menu.addItem(22, "Set Swing..."); // UU3
    menu.addItem(23, "Set Clip Gain..."); // SSS

    menu.showMenuAsync(juce::PopupMenu::Options(),
        [this, tid = track.id, clipIdx](int result)
        {
            auto* tp = audioEngine.getTrackModel().getTrack(tid);
            if (tp == nullptr) return;
            auto& track = *tp;
            if (clipIdx < 0 || clipIdx >= (int)track.clips.size()) return;

            if (result == 1) // Duplicate
            {
                auto copy = track.clips[(size_t)clipIdx];
                copy.startBeat = copy.startBeat + copy.lengthBeats;
                track.clips.push_back(std::move(copy));
                repaint();
            }
            else if (result == 2) // Split at playhead
            {
                double playBeat = audioEngine.getPositionBeats();
                auto& clip = track.clips[(size_t)clipIdx];
                double relBeat = playBeat - clip.startBeat;
                if (relBeat <= 0.0 || relBeat >= clip.lengthBeats) return;

                // Create second half
                MidiClip second;
                second.startBeat = playBeat;
                second.lengthBeats = clip.lengthBeats - relBeat;

                // Move notes to appropriate clip
                for (int i = clip.sequence.getNumEvents() - 1; i >= 0; --i)
                {
                    auto msg = clip.sequence.getEventPointer(i)->message;
                    if (msg.getTimeStamp() >= relBeat)
                    {
                        auto moved = msg;
                        moved.setTimeStamp(msg.getTimeStamp() - relBeat);
                        second.sequence.addEvent(moved);
                        clip.sequence.deleteEvent(i, false);
                    }
                }
                second.sequence.updateMatchedPairs();

                clip.lengthBeats = relBeat;
                clip.sequence.updateMatchedPairs();

                track.clips.push_back(std::move(second));
                repaint();
            }
            else if (result == 3) // Delete
            {
                track.clips.erase(track.clips.begin() + clipIdx);
                repaint();
            }
            else if (result == 4) // MM4 — Rename clip
            {
                auto* aw = new juce::AlertWindow("Rename Clip", "",
                                                  juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("name", track.clips[(size_t)clipIdx].name);
                aw->addButton("OK", 1);
                aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, tid, clipIdx, aw](int r) {
                        auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                        if (r == 1 && tp2 != nullptr && clipIdx < (int)tp2->clips.size())
                            tp2->clips[(size_t)clipIdx].name = aw->getTextEditorContents("name");
                        delete aw;
                        repaint();
                    }), false);
            }
            else if (result == 20) // SS4 — toggle clip loop
            {
                auto& c = track.clips[(size_t)clipIdx];
                c.loopEnabled = ! c.loopEnabled;
                repaint();
            }
            else if (result == 21) // SS4 — set loop length
            {
                auto* aw = new juce::AlertWindow("Loop Length", "Beats:",
                    juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("len", juce::String(track.clips[(size_t)clipIdx].loopLengthBeats, 2));
                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, tid, clipIdx, aw](int r) {
                        auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                        if (r == 1 && tp2 != nullptr && clipIdx < (int)tp2->clips.size())
                            tp2->clips[(size_t)clipIdx].loopLengthBeats = juce::jmax(0.25,
                                aw->getTextEditorContents("len").getDoubleValue());
                        delete aw; repaint();
                    }), false);
            }
            else if (result == 22) // UU3 — set swing
            {
                auto* aw = new juce::AlertWindow("Set Swing", "Swing amount (0.0=straight, 0.5=full triplet):",
                    juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("val", juce::String(track.clips[(size_t)clipIdx].swing, 2));
                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, tid, clipIdx, aw](int r) {
                        auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                        if (r == 1 && tp2 != nullptr && clipIdx < (int)tp2->clips.size())
                            tp2->clips[(size_t)clipIdx].swing = (float)juce::jlimit(0.0, 0.5,
                                aw->getTextEditorContents("val").getDoubleValue());
                        delete aw; repaint();
                    }), false);
            }
            else if (result == 23) // SSS — set clip gain
            {
                auto* aw = new juce::AlertWindow("Clip Gain",
                    "Velocity multiplier (0.0=mute, 1.0=unity, 2.0=max):",
                    juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("val", juce::String(track.clips[(size_t)clipIdx].gain, 2));
                aw->addButton("OK", 1); aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, tid, clipIdx, aw](int r) {
                        auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                        if (r == 1 && tp2 != nullptr && clipIdx < (int)tp2->clips.size())
                            tp2->clips[(size_t)clipIdx].gain = (float) juce::jlimit(0.0, 2.0,
                                aw->getTextEditorContents("val").getDoubleValue());
                        delete aw; repaint();
                    }), false);
            }
            else if (result >= 10 && result <= 15) // KK2 — clip colour
            {
                auto& c = track.clips[(size_t)clipIdx];
                static const juce::Colour cpal[] = {
                    juce::Colour(0xFF5E81AC), juce::Colour(0xFFA3BE8C),
                    juce::Colour(0xFFBF616A), juce::Colour(0xFFD08770),
                    juce::Colour(0xFFB48EAD)
                };
                if (result == 15)
                    c.colour = juce::Colour(0x00000000); // reset
                else
                    c.colour = cpal[result - 10];
                repaint();
            }
        });
}

void ArrangementView::showTrackContextMenu(int trackIdx)
{
    auto& tracks = audioEngine.getTrackModel().getTracks();
    if (trackIdx < 0 || trackIdx >= (int)tracks.size()) return;

    auto& track = tracks[(size_t)trackIdx];

    juce::PopupMenu menu;
    menu.addItem(1, "Rename Track...");
    menu.addItem(2, "Delete Track");
    menu.addItem(6, "Duplicate Track"); // II1
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
    colMenu.addSeparator();
    colMenu.addItem(208, "Custom..."); // JJ3
    menu.addSubMenu("Colour", colMenu);

    // OO2 — MIDI channel selector
    {
        juce::PopupMenu chMenu;
        for (int ch = 1; ch <= 16; ++ch)
            chMenu.addItem(800 + ch, "Ch " + juce::String(ch), true, track.midiChannel == ch);
        menu.addSubMenu("MIDI Channel", chMenu);
    }

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

    // EE2 — Freeze/Unfreeze
    menu.addItem(510, track.frozen ? "Unfreeze" : "Freeze Track");
    menu.addItem(511, "Bounce in Place"); // JJ2
    menu.addSeparator();

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
        [this, trackIdx, tid = track.id](int result)
        {
            auto* tp = audioEngine.getTrackModel().getTrack(tid);
            if (tp == nullptr) return;
            auto& track = *tp;
            if (result == 1)
            {
                auto* aw = new juce::AlertWindow("Rename Track", "Enter new name:",
                                                  juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("name", track.name);
                aw->addButton("OK", 1);
                aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, tid, aw](int r)
                    {
                        auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                        if (r == 1 && tp2 != nullptr)
                            tp2->name = aw->getTextEditorContents("name");
                        delete aw;
                        if (onTrackListChanged) onTrackListChanged();
                        repaint();
                    }), false);
            }
            else if (result == 2) // KK5 — confirm before delete
            {
                juce::AlertWindow::showAsync(
                    juce::MessageBoxOptions()
                        .withIconType(juce::MessageBoxIconType::QuestionIcon)
                        .withTitle("Delete Track")
                        .withMessage("Delete \"" + track.name + "\" and all its clips?")
                        .withButton("Delete")
                        .withButton("Cancel"),
                    [this, tid = track.id](int r) {
                        if (r != 1) return;
                        PluginEditorManager::instance().closeAllForTrack(tid);
                        audioEngine.getPluginChains().clearTrack(tid);
                        audioEngine.getTrackModel().removeTrack(tid);
                        if (onTrackListChanged) onTrackListChanged();
                        rebuildVisibleTracks();
                        resized();
                        repaint();
                    });
            }
            else if (result == 6) // II1 — duplicate track
            {
                auto& dup = audioEngine.getTrackModel().addTrack(track.name + " (copy)");
                audioEngine.prebuildTrackSynth(dup.id);
                dup.colour      = track.colour;
                dup.volume      = track.volume;
                dup.pan         = track.pan;
                dup.mute        = track.mute;
                dup.midiChannel = track.midiChannel;
                dup.outputBusId = track.outputBusId;
                dup.sends       = track.sends;
                dup.clips       = track.clips;
                dup.audioClips  = track.audioClips;
                dup.automation  = track.automation;
                dup.plugins     = track.plugins;
                dup.displayHeight = track.displayHeight;
                rebuildVisibleTracks();
                if (onTrackListChanged) onTrackListChanged();
                repaint();
            }
            else if (result == 3) { track.mute = !track.mute; repaint(); }
            else if (result == 4) { track.solo = !track.solo; repaint(); }
            else if (result >= 100 && result < 200)
            {
                // Store in data model — AudioEngine applies on each block
                track.userProgram = result - 100;
                repaint();
            }
            else if (result >= 200 && result < 300)
            {
                if (result == 208) // JJ3 — custom hex color
                {
                    auto* aw = new juce::AlertWindow("Custom Colour",
                        "Enter hex colour (e.g. FF5E81AC):",
                        juce::MessageBoxIconType::NoIcon);
                    aw->addTextEditor("hex", track.colour.toDisplayString(true));
                    aw->addButton("OK", 1);
                    aw->addButton("Cancel", 0);
                    aw->enterModalState(true, juce::ModalCallbackFunction::create(
                        [this, tid, aw](int r) {
                            auto* tp2 = audioEngine.getTrackModel().getTrack(tid);
                            if (r == 1 && tp2 != nullptr)
                            {
                                auto hex = aw->getTextEditorContents("hex").trim();
                                if (! hex.startsWith("0x") && ! hex.startsWith("0X"))
                                    hex = "0x" + hex;
                                tp2->colour = juce::Colour((juce::uint32)hex.getHexValue64());
                                if (onTrackListChanged) onTrackListChanged();
                                repaint();
                            }
                            delete aw;
                        }), false);
                }
                else
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
            else if (result == 510) // EE2 — freeze/unfreeze
            {
                if (track.frozen)
                {
                    // Unfreeze: remove the frozen AudioClip, restore MIDI
                    if (! track.audioClips.empty())
                        track.audioClips.pop_back();
                    track.frozen = false;
                }
                else
                {
                    // Freeze: render track to AudioClip. Enhancements
                    // 2026-04-21: apply the per-track plugin chain so the
                    // frozen audio includes FX (prior version rendered
                    // only bare synth output), and prepare the plugins at
                    // the same sample rate used for the offline render.
                    double maxBeat = 16.0;
                    for (auto& c : track.clips)
                        maxBeat = juce::jmax(maxBeat, c.startBeat + c.lengthBeats);

                    const double sr = 44100.0;
                    const int totalSamples = (int)(maxBeat / (audioEngine.getTempo() / 60.0) * sr);
                    if (totalSamples > 0)
                    {
                        AudioClip frozen;
                        frozen.startBeat = 0.0;
                        frozen.lengthBeats = maxBeat;
                        frozen.sourceSampleRate = sr;
                        frozen.buffer.setSize(2, totalSamples);
                        frozen.buffer.clear();
                        frozen.sourceName = track.name + " (frozen)";

                        auto& syn = audioEngine.getOrCreateTrackSynth(track.id);
                        auto seq = track.flattenForPlayback();
                        const double bps = audioEngine.getTempo() / 60.0;
                        const int blockSize = 512;
                        const bool hasFx = ! track.plugins.empty();

                        // Re-prepare synth + plugin chain at the offline SR
                        // so plugin state is coherent with the render. After
                        // freeze finishes they'll be re-prepared again by
                        // audioDeviceAboutToStart during normal playback.
                        syn.prepare(sr, blockSize);
                        if (hasFx)
                            audioEngine.getPluginChains().prepareAll(sr, blockSize);

                        for (int pos = 0; pos < totalSamples; pos += blockSize)
                        {
                            const int thisBlock = juce::jmin(blockSize, totalSamples - pos);
                            const double blockBeat = (double)pos / sr * bps;
                            const double endBeat = (double)(pos + thisBlock) / sr * bps;

                            juce::MidiBuffer mb;
                            for (int i = 0; i < seq.getNumEvents(); ++i)
                            {
                                auto* evt = seq.getEventPointer(i);
                                double eb = evt->message.getTimeStamp();
                                if (eb >= blockBeat && eb < endBeat)
                                {
                                    int off = (int)((eb - blockBeat) / bps * sr);
                                    mb.addEvent(evt->message, juce::jlimit(0, thisBlock - 1, off));
                                }
                            }

                            juce::AudioBuffer<float> buf(2, thisBlock);
                            buf.clear();
                            syn.renderBlock(buf, mb);

                            // Run the track's plugin chain on the synth
                            // output so the frozen audio matches what the
                            // user hears live. Uses a scratch MidiBuffer
                            // per call to avoid sharing state.
                            if (hasFx)
                            {
                                juce::MidiBuffer fxMidi;
                                audioEngine.getPluginChains().processTrack(
                                    track.id, track, buf, fxMidi);
                            }

                            for (int ch = 0; ch < 2; ++ch)
                                frozen.buffer.copyFrom(ch, pos, buf, ch, 0, thisBlock);
                        }

                        track.audioClips.push_back(std::move(frozen));
                        track.frozen = true;
                    }
                }
                repaint();
            }
            else if (result == 511) // JJ2 — Bounce in Place
            {
                double maxBeat = 16.0;
                for (auto& c : track.clips)
                    maxBeat = juce::jmax(maxBeat, c.startBeat + c.lengthBeats);

                const double sr = 44100.0;
                const int totalSamples = (int)(maxBeat / (audioEngine.getTempo() / 60.0) * sr);
                if (totalSamples > 0)
                {
                    AudioClip bounced;
                    bounced.startBeat = 0.0;
                    bounced.lengthBeats = maxBeat;
                    bounced.sourceSampleRate = sr;
                    bounced.buffer.setSize(2, totalSamples);
                    bounced.buffer.clear();

                    auto& syn = audioEngine.getOrCreateTrackSynth(track.id);
                    auto seq = track.flattenForPlayback();
                    const double bps = audioEngine.getTempo() / 60.0;
                    const int blk = 512;
                    for (int pos = 0; pos < totalSamples; pos += blk)
                    {
                        const int nb = juce::jmin(blk, totalSamples - pos);
                        const double bb = (double)pos / sr * bps;
                        const double eb = (double)(pos + nb) / sr * bps;
                        juce::MidiBuffer mb;
                        for (int i = 0; i < seq.getNumEvents(); ++i)
                        {
                            auto* evt = seq.getEventPointer(i);
                            double bt = evt->message.getTimeStamp();
                            if (bt >= bb && bt < eb)
                                mb.addEvent(evt->message, juce::jlimit(0, nb-1, (int)((bt-bb)/bps*sr)));
                        }
                        juce::AudioBuffer<float> buf(2, nb);
                        buf.clear();
                        syn.renderBlock(buf, mb);
                        for (int ch = 0; ch < 2; ++ch)
                            bounced.buffer.copyFrom(ch, pos, buf, ch, 0, nb);
                    }
                    // Replace: clear MIDI clips, add audio clip
                    track.clips.clear();
                    track.audioClips.push_back(std::move(bounced));
                    repaint();
                }
            }
            else if (result == 500) // AA6 — folder toggle
            {
                track.isFolder = ! track.isFolder;
                repaint();
            }
            else if (result == 501) // BB1 + CC1 — collapse toggle with visual update
            {
                track.collapsed = ! track.collapsed;
                rebuildVisibleTracks();
                resized();
                repaint();
            }
            else if (result == 600) // top-level
            {
                track.parentTrackId = -1;
                repaint();
            }
            else if (result > 800 && result <= 816) // OO2 — MIDI channel
            {
                track.midiChannel = result - 800;
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
