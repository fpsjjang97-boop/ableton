/*
 * MidiGPT DAW - PianoRoll.cpp
 * Full MIDI editor with draw/select/erase, drag move/resize,
 * velocity editing, zoom, scroll, clipboard, undo-ready.
 */

#include "PianoRoll.h"
#include "../Command/EditCommands.h"
#include "../Core/Groove.h"
#include "LookAndFeel.h"   // palette tokens (review fix)

PianoRoll::PianoRoll()
{
    setOpaque(true);
    setWantsKeyboardFocus(true);
    addKeyListener(this);
    scrollY = (127 - 72) * noteHeight - 100;
    startTimerHz(30);
}

// ---------------------------------------------------------------------------
// Coordinates
// ---------------------------------------------------------------------------
float PianoRoll::noteToY(int note) const { return headerH + (127 - note) * noteHeight - scrollY; }
int   PianoRoll::yToNote(float y) const  { return 127 - static_cast<int>((y - headerH + scrollY) / noteHeight); }
float PianoRoll::beatToX(double beat) const { return pianoKeyWidth + static_cast<float>(beat * beatWidth) - scrollX; }
double PianoRoll::xToBeat(float x) const   { return (x - pianoKeyWidth + scrollX) / beatWidth; }

double PianoRoll::snapBeat(double beat) const
{
    if (snapBeats <= 0.0) return beat;
    return std::round(beat / snapBeats) * snapBeats;
}

// ---------------------------------------------------------------------------
// Paint
// ---------------------------------------------------------------------------
void PianoRoll::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(MetallicLookAndFeel::bgDarkest));
    drawGrid(g);
    drawNotes(g);
    drawPlayhead(g);
    drawPianoKeys(g);
    drawHeader(g);
    drawVelocityBar(g);

    // Y1 — recording overlay
    if (isRecording && isRecording())
    {
        g.setColour(juce::Colour(0x30FF0000));
        g.fillRect(0, 0, getWidth(), getHeight());
        g.setColour(juce::Colour(0xFFFF4444));
        g.setFont(14.0f);
        g.drawText("REC — editing locked", getLocalBounds().reduced(12),
                   juce::Justification::topRight);
    }
}

void PianoRoll::drawHeader(juce::Graphics& g)
{
    g.setColour(juce::Colour(MetallicLookAndFeel::bgDark));
    g.fillRect(0, 0, getWidth(), headerH);

    g.setColour(juce::Colour(0xFF909090));
    g.setFont(9.0f);

    double firstBeat = scrollX / beatWidth;
    double lastBeat = firstBeat + (getWidth() - pianoKeyWidth) / beatWidth;

    for (double beat = std::floor(firstBeat / 4.0) * 4.0; beat <= lastBeat; beat += 4.0)
    {
        float x = beatToX(beat);
        if (x >= pianoKeyWidth)
            g.drawText(juce::String(static_cast<int>(beat / 4.0) + 1),
                       (int)x + 2, 0, 30, headerH, juce::Justification::centredLeft);
    }

    // Take-lane indicator: top-right badge showing "T: N" so the user
    // can see stashed takes exist on this clip. Discoverability hook for
    // the 'T' keyboard shortcut which opens the take picker.
    if (currentClip != nullptr && ! currentClip->takes.empty())
    {
        const int badgeW = 48;
        const int badgeX = getWidth() - badgeW - 4;
        g.setColour (juce::Colour (MetallicLookAndFeel::accent).withAlpha (0.9f));
        g.fillRoundedRectangle ((float) badgeX, 2.0f,
                                 (float) badgeW, (float) headerH - 4.0f, 3.0f);
        g.setColour (juce::Colour (MetallicLookAndFeel::bgDarkest));
        g.setFont (10.0f);
        g.drawText ("T: " + juce::String ((int) currentClip->takes.size()),
                    badgeX, 0, badgeW, headerH,
                    juce::Justification::centred);
    }
}

void PianoRoll::drawPianoKeys(juce::Graphics& g)
{
    // High-contrast keys so the piano column is actually visible against
    // the dark background — mimics Ableton Live / Cakewalk where white
    // keys are near-white and black keys are near-black.
    int bottom = gridAreaBottom();
    for (int note = 0; note < 128; ++note)
    {
        float y = noteToY(note);
        if (y + noteHeight < headerH || y > bottom) continue;

        bool isBlack = juce::MidiMessage::isMidiNoteBlack(note);
        g.setColour(isBlack ? juce::Colour(0xFF1A1A1A) : juce::Colour(0xFFCCCCCC));
        g.fillRect(0.0f, y, (float)pianoKeyWidth, noteHeight);

        // Key separator — dark line between white keys, lighter on black.
        g.setColour(isBlack ? juce::Colour(0xFF000000) : juce::Colour(0xFF808080));
        g.drawHorizontalLine(static_cast<int>(y + noteHeight), 0.0f, (float)pianoKeyWidth);

        if (note % 12 == 0)
        {
            // C note labels are dark text on white keys for readability.
            g.setColour(juce::Colour(0xFF1A1A1A));
            g.setFont(juce::Font(9.0f, juce::Font::bold));
            g.drawText("C" + juce::String(note / 12 - 1), 2, (int)y, pianoKeyWidth - 4,
                       (int)noteHeight, juce::Justification::centredLeft);
        }
    }
    // Divider between key column and grid.
    g.setColour(juce::Colour(MetallicLookAndFeel::border));
    g.drawVerticalLine(pianoKeyWidth, (float)headerH, (float)bottom);
}

void PianoRoll::drawGrid(juce::Graphics& g)
{
    // Grid rows: alternate shading between black-note and white-note rows
    // so the pitch axis is visually scannable even on an empty clip.
    int bottom = gridAreaBottom(), right = gridAreaRight();

    for (int note = 0; note < 128; ++note)
    {
        float y = noteToY(note);
        if (y + noteHeight < headerH || y > bottom) continue;

        bool isBlack = juce::MidiMessage::isMidiNoteBlack(note);
        g.setColour(isBlack ? juce::Colour(MetallicLookAndFeel::bgDark)
                            : juce::Colour(MetallicLookAndFeel::bgPanel));
        g.fillRect((float)pianoKeyWidth, y, (float)(right - pianoKeyWidth), noteHeight);

        if (note % 12 == 0)
        {
            // C-row accent line — Cakewalk-style amber tint for octave marker.
            g.setColour(juce::Colour(MetallicLookAndFeel::accent).withAlpha(0.25f));
            g.drawHorizontalLine((int)y, (float)pianoKeyWidth, (float)right);
        }
    }

    double firstBeat = scrollX / beatWidth;
    double lastBeat = firstBeat + (right - pianoKeyWidth) / beatWidth;

    for (double beat = std::floor(firstBeat); beat <= lastBeat; beat += snapBeats)
    {
        float x = beatToX(beat);
        if (x < pianoKeyWidth) continue;

        if (std::fmod(beat, 4.0) < 0.001)
            g.setColour(juce::Colour(0xFF333333));
        else if (std::fmod(beat, 1.0) < 0.001)
            g.setColour(juce::Colour(0xFF2A2A2A).withAlpha(0.4f));
        else if (beatWidth >= 30.0f)
            g.setColour(juce::Colour(0xFF2A2A2A).withAlpha(0.15f));
        else continue;

        g.drawVerticalLine((int)x, (float)headerH, (float)bottom);
    }
}

void PianoRoll::drawNotes(juce::Graphics& g)
{
    if (!currentClip) return;
    auto& seq = currentClip->sequence;
    int bottom = gridAreaBottom();

    for (int i = 0; i < seq.getNumEvents(); ++i)
    {
        auto* evt = seq.getEventPointer(i);
        if (!evt->message.isNoteOn()) continue;

        int note = evt->message.getNoteNumber();
        double startBeat = evt->message.getTimeStamp();
        double endBeat = startBeat + 0.25;
        if (evt->noteOffObject) endBeat = evt->noteOffObject->message.getTimeStamp();

        float x = beatToX(startBeat);
        float w = beatToX(endBeat) - x;
        float y = noteToY(note);

        if (y + noteHeight < headerH || y > bottom || x + w < pianoKeyWidth) continue;

        int vel = evt->message.getVelocity();
        bool sel = isSelected(i);

        auto baseColour = sel ? juce::Colour(0xFF88C0D0) : juce::Colour(0xFF5E81AC);
        auto noteColour = baseColour.interpolatedWith(juce::Colour(0xFFE0E0E0), vel / 127.0f * 0.3f);

        g.setColour(noteColour);
        g.fillRoundedRectangle(x + 1, y + 1, juce::jmax(2.0f, w - 1), noteHeight - 2, 2.0f);

        g.setColour(juce::Colours::white.withAlpha(0.08f));
        g.fillRoundedRectangle(x + 1, y + 1, juce::jmax(2.0f, w - 1), (noteHeight - 2) * 0.4f, 2.0f);

        g.setColour(noteColour.darker(0.3f));
        g.fillRect(x + 2, y + noteHeight - 3, juce::jmax(1.0f, (w - 3) * vel / 127.0f), 2.0f);

        g.setColour(sel ? juce::Colours::white.withAlpha(0.4f) : juce::Colours::white.withAlpha(0.15f));
        g.drawRoundedRectangle(x + 1, y + 1, juce::jmax(2.0f, w - 1), noteHeight - 2, 2.0f, 0.5f);

        if (sel && w > 8)
        {
            g.setColour(juce::Colours::white.withAlpha(0.3f));
            g.fillRect(x + w - 4, y + 2, 2.0f, noteHeight - 4);
        }
    }

    if (dragMode == RubberBand)
    {
        g.setColour(juce::Colour(0xFFC0C0C0).withAlpha(0.15f));
        g.fillRect(rubberBandRect);
        g.setColour(juce::Colour(0xFFC0C0C0).withAlpha(0.5f));
        g.drawRect(rubberBandRect, 1.0f);
    }
}

void PianoRoll::drawPlayhead(juce::Graphics& g)
{
    if (playheadBeat < 0.0) return;
    float px = beatToX(playheadBeat);
    if (px >= pianoKeyWidth && px < getWidth())
    {
        g.setColour(juce::Colours::white.withAlpha(0.85f));
        g.drawVerticalLine((int)px, (float)headerH, (float)gridAreaBottom());

        // Triangle at top
        juce::Path tri;
        tri.addTriangle(px - 4, (float)headerH, px + 4, (float)headerH, px, (float)headerH + 6);
        g.fillPath(tri);
    }
}

void PianoRoll::drawVelocityBar(juce::Graphics& g)
{
    int top = gridAreaBottom();
    g.setColour(juce::Colour(0xFF111122));
    g.fillRect(0, top, getWidth(), velocityBarH);
    g.setColour(juce::Colour(0xFF333355));
    g.drawHorizontalLine(top, 0.0f, (float)getWidth());

    if (!currentClip) return;
    auto& seq = currentClip->sequence;
    for (int i = 0; i < seq.getNumEvents(); ++i)
    {
        auto* evt = seq.getEventPointer(i);
        if (!evt->message.isNoteOn()) continue;

        float x = beatToX(evt->message.getTimeStamp());
        if (x < pianoKeyWidth) continue;

        int vel = evt->message.getVelocity();
        float velNorm = vel / 127.0f;
        float barH = velNorm * (velocityBarH - 4);

        auto colour = juce::Colour(0xFF555555).interpolatedWith(juce::Colour(0xFFAAAAAA), velNorm);
        if (isSelected(i)) colour = juce::Colour(0xFF88C0D0);

        g.setColour(colour);
        g.fillRect(x, (float)(top + velocityBarH - 2 - barH), 3.0f, barH);
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
int PianoRoll::findNoteAt(double beat, int noteNum)
{
    if (!currentClip) return -1;
    auto& seq = currentClip->sequence;
    for (int i = 0; i < seq.getNumEvents(); ++i)
    {
        auto* evt = seq.getEventPointer(i);
        if (!evt->message.isNoteOn() || evt->message.getNoteNumber() != noteNum) continue;
        double start = evt->message.getTimeStamp();
        double end = start + 0.25;
        if (evt->noteOffObject) end = evt->noteOffObject->message.getTimeStamp();
        if (beat >= start && beat < end) return i;
    }
    return -1;
}

bool PianoRoll::isNearNoteEnd(int idx, float mx) const
{
    if (!currentClip || idx < 0) return false;
    auto* evt = currentClip->sequence.getEventPointer(idx);
    if (!evt || !evt->noteOffObject) return false;
    float endX = beatToX(evt->noteOffObject->message.getTimeStamp());
    return std::abs(mx - endX) < 6.0f;
}

bool PianoRoll::isSelected(int idx) const
{
    for (auto s : selectedIndices) if (s == idx) return true;
    return false;
}

void PianoRoll::deleteSelected()
{
    if (!currentClip) return;
    auto& seq = currentClip->sequence;

    // W1 — snapshot selected notes for undo, then perform via UndoManager
    if (undoManager != nullptr && ! selectedIndices.empty())
    {
        std::vector<DeleteNotesCmd::NoteSnap> snaps;
        for (int idx : selectedIndices)
        {
            if (idx < 0 || idx >= seq.getNumEvents()) continue;
            auto* evt = seq.getEventPointer(idx);
            if (! evt->message.isNoteOn()) continue;
            DeleteNotesCmd::NoteSnap s;
            s.pitch = evt->message.getNoteNumber();
            s.vel   = evt->message.getVelocity();
            s.ch    = evt->message.getChannel();
            s.start = evt->message.getTimeStamp();
            s.dur   = evt->noteOffObject
                       ? evt->noteOffObject->message.getTimeStamp() - s.start
                       : 0.25;
            snaps.push_back(s);
        }
        undoManager->beginNewTransaction("Delete notes");
        undoManager->perform(new DeleteNotesCmd(currentClip, std::move(snaps)));
        selectedIndices.clear();
        repaint();
        if (onNotesChanged) onNotesChanged();
        return;
    }

    std::sort(selectedIndices.begin(), selectedIndices.end(), std::greater<int>());
    for (int idx : selectedIndices)
    {
        if (idx < seq.getNumEvents())
        {
            auto* evt = seq.getEventPointer(idx);
            if (evt->noteOffObject)
                seq.deleteEvent(seq.getIndexOf(evt->noteOffObject), false);
            seq.deleteEvent(idx, false);
        }
    }
    selectedIndices.clear();
    repaint();
    if (onNotesChanged) onNotesChanged();
}

// ---------------------------------------------------------------------------
// Mouse
// ---------------------------------------------------------------------------
void PianoRoll::mouseDown(const juce::MouseEvent& e)
{
    // Y1 — block edits while recording (read-only preview). Velocity bar,
    // note draw/select/erase all disabled. Playhead continues to update.
    if (isRecording && isRecording()) return;

    float mx = (float)e.x, my = (float)e.y;

    // Velocity bar
    if (my >= gridAreaBottom())
    {
        if (!currentClip) return;
        auto& seq = currentClip->sequence;
        int closest = -1; float closestDist = 999.0f;
        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            auto* evt = seq.getEventPointer(i);
            if (!evt->message.isNoteOn()) continue;
            float dist = std::abs(beatToX(evt->message.getTimeStamp()) - mx);
            if (dist < closestDist) { closestDist = dist; closest = i; }
        }
        if (closest >= 0 && closestDist < 10.0f)
        {
            dragMode = VelocityEdit;
            dragNoteIdx = closest;
            selectedIndices = { closest };

            // Z2 — snapshot for undo
            velBefore.clear();
            auto* e0 = seq.getEventPointer(closest);
            if (e0 != nullptr && e0->message.isNoteOn())
            {
                NoteBefore nb;
                nb.pitch = e0->message.getNoteNumber();
                nb.ch    = e0->message.getChannel();
                nb.vel   = e0->message.getVelocity();
                nb.start = e0->message.getTimeStamp();
                nb.dur   = e0->noteOffObject
                    ? e0->noteOffObject->message.getTimeStamp() - nb.start
                    : 0.25;
                velBefore.push_back(nb);
            }

            float velNorm = juce::jlimit(0.0f, 1.0f,
                1.0f - (my - gridAreaBottom()) / (float)velocityBarH);
            int vel = juce::jlimit(1, 127, (int)(velNorm * 127));

            // Rebuild noteOn with new velocity
            auto& msg = seq.getEventPointer(closest)->message;
            auto newMsg = juce::MidiMessage::noteOn(msg.getChannel(), msg.getNoteNumber(), (juce::uint8)vel);
            newMsg.setTimeStamp(msg.getTimeStamp());
            msg = newMsg;
            repaint();
        }
        return;
    }

    if (mx < pianoKeyWidth) return;

    double beat = xToBeat(mx);
    int note = yToNote(my);
    if (note < 0 || note > 127) return;

    int foundIdx = findNoteAt(beat, note);

    // Erase tool or right-click
    if (currentTool == EraseTool || e.mods.isRightButtonDown())
    {
        if (foundIdx >= 0)
        {
            selectedIndices = { foundIdx };
            deleteSelected();
        }
        return;
    }

    // Draw tool
    if (currentTool == DrawTool)
    {
        if (foundIdx >= 0)
        {
            if (isNearNoteEnd(foundIdx, mx))
            {
                selectedIndices = { foundIdx };
                dragMode = ResizeNote;
                dragNoteIdx = foundIdx;

                // Y2 — snapshot for undo
                moveBefore.clear();
                auto* e2 = currentClip->sequence.getEventPointer(foundIdx);
                if (e2 != nullptr && e2->message.isNoteOn())
                {
                    NoteBefore nb;
                    nb.pitch = e2->message.getNoteNumber();
                    nb.ch    = e2->message.getChannel();
                    nb.vel   = e2->message.getVelocity();
                    nb.start = e2->message.getTimeStamp();
                    nb.dur   = e2->noteOffObject
                        ? e2->noteOffObject->message.getTimeStamp() - nb.start
                        : 0.25;
                    moveBefore.push_back(nb);
                }
            }
            else
            {
                selectedIndices = { foundIdx };
                dragMode = MoveNote;
                dragNoteIdx = foundIdx;
                dragStartBeat = beat;
                dragStartNote = note;
                // Store original positions for all selected
                origPositions.clear();
                auto* evt = currentClip->sequence.getEventPointer(foundIdx);
                origPositions.push_back({ evt->message.getTimeStamp(), evt->message.getNoteNumber() });

                // Y2 — full snapshot for undo
                moveBefore.clear();
                for (int idx : selectedIndices)
                {
                    auto* e2 = currentClip->sequence.getEventPointer(idx);
                    if (e2 == nullptr || ! e2->message.isNoteOn()) continue;
                    NoteBefore nb;
                    nb.pitch = e2->message.getNoteNumber();
                    nb.ch    = e2->message.getChannel();
                    nb.vel   = e2->message.getVelocity();
                    nb.start = e2->message.getTimeStamp();
                    nb.dur   = e2->noteOffObject
                        ? e2->noteOffObject->message.getTimeStamp() - nb.start
                        : 0.25;
                    moveBefore.push_back(nb);
                }
            }
        }
        else if (currentClip)
        {
            double snapped = snapBeat(beat);
            auto noteOn = juce::MidiMessage::noteOn(1, note, (juce::uint8)100);
            noteOn.setTimeStamp(snapped);
            auto noteOff = juce::MidiMessage::noteOff(1, note);
            noteOff.setTimeStamp(snapped + snapBeats);
            currentClip->sequence.addEvent(noteOn);
            currentClip->sequence.addEvent(noteOff);
            currentClip->sequence.updateMatchedPairs();
            dragMode = DrawNote;
            dragStartBeat = snapped;
            dragStartNote = note;
            repaint();
            if (onNotesChanged) onNotesChanged();
        }
        return;
    }

    // Select tool
    if (currentTool == SelectTool)
    {
        if (foundIdx >= 0)
        {
            if (isNearNoteEnd(foundIdx, mx))
            {
                if (!isSelected(foundIdx)) selectedIndices = { foundIdx };
                dragMode = ResizeNote;
                dragNoteIdx = foundIdx;
            }
            else
            {
                if (e.mods.isShiftDown())
                {
                    auto it = std::find(selectedIndices.begin(), selectedIndices.end(), foundIdx);
                    if (it != selectedIndices.end()) selectedIndices.erase(it);
                    else selectedIndices.push_back(foundIdx);
                }
                else
                {
                    if (!isSelected(foundIdx)) selectedIndices = { foundIdx };
                    dragMode = MoveNote;
                    dragNoteIdx = foundIdx;
                    dragStartBeat = beat;
                    dragStartNote = note;
                    origPositions.clear();
                    for (int si : selectedIndices)
                    {
                        auto* evt = currentClip->sequence.getEventPointer(si);
                        if (evt && evt->message.isNoteOn())
                            origPositions.push_back({ evt->message.getTimeStamp(), evt->message.getNoteNumber() });
                    }
                }
            }
        }
        else
        {
            selectedIndices.clear();
            dragMode = RubberBand;
            dragStartX = mx;
            dragStartY = my;
            rubberBandRect = {};
        }
        repaint();
    }
}

void PianoRoll::mouseDrag(const juce::MouseEvent& e)
{
    if (!currentClip) return;
    float mx = (float)e.x, my = (float)e.y;

    if (dragMode == DrawNote)
    {
        double currentBeat = snapBeat(xToBeat(mx));
        double duration = juce::jmax(snapBeats, currentBeat - dragStartBeat);
        auto& seq = currentClip->sequence;
        for (int i = seq.getNumEvents() - 1; i >= 0; --i)
        {
            auto* evt = seq.getEventPointer(i);
            if (evt->message.isNoteOn() && evt->message.getNoteNumber() == dragStartNote
                && std::abs(evt->message.getTimeStamp() - dragStartBeat) < 0.001)
            {
                if (evt->noteOffObject)
                    evt->noteOffObject->message.setTimeStamp(dragStartBeat + duration);
                break;
            }
        }
        repaint();
    }
    else if (dragMode == MoveNote)
    {
        double currentBeat = xToBeat(mx);
        int currentNote = yToNote(my);
        double deltaBeat = snapBeat(currentBeat - dragStartBeat);
        int deltaNoteNum = currentNote - dragStartNote;

        auto& seq = currentClip->sequence;
        for (size_t si = 0; si < selectedIndices.size() && si < origPositions.size(); ++si)
        {
            int idx = selectedIndices[si];
            if (idx >= seq.getNumEvents()) continue;
            auto* evt = seq.getEventPointer(idx);
            if (!evt->message.isNoteOn()) continue;

            double newBeat = juce::jmax(0.0, origPositions[si].beat + deltaBeat);
            int newNote = juce::jlimit(0, 127, origPositions[si].noteNum + deltaNoteNum);

            double dur = 0.25;
            if (evt->noteOffObject)
                dur = evt->noteOffObject->message.getTimeStamp() - evt->message.getTimeStamp();

            auto on = juce::MidiMessage::noteOn(evt->message.getChannel(), newNote, evt->message.getVelocity());
            on.setTimeStamp(newBeat);
            evt->message = on;

            if (evt->noteOffObject)
            {
                auto off = juce::MidiMessage::noteOff(evt->message.getChannel(), newNote);
                off.setTimeStamp(newBeat + dur);
                evt->noteOffObject->message = off;
            }
        }
        repaint();
    }
    else if (dragMode == ResizeNote)
    {
        double currentBeat = snapBeat(xToBeat(mx));
        auto& seq = currentClip->sequence;
        for (int idx : selectedIndices)
        {
            if (idx >= seq.getNumEvents()) continue;
            auto* evt = seq.getEventPointer(idx);
            if (!evt->message.isNoteOn() || !evt->noteOffObject) continue;
            double newEnd = juce::jmax(evt->message.getTimeStamp() + snapBeats, currentBeat);
            evt->noteOffObject->message.setTimeStamp(newEnd);
        }
        repaint();
    }
    else if (dragMode == RubberBand)
    {
        float x1 = juce::jmin(dragStartX, mx), y1 = juce::jmin(dragStartY, my);
        float x2 = juce::jmax(dragStartX, mx), y2 = juce::jmax(dragStartY, my);
        rubberBandRect = { x1, y1, x2 - x1, y2 - y1 };

        selectedIndices.clear();
        auto& seq = currentClip->sequence;
        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            auto* evt = seq.getEventPointer(i);
            if (!evt->message.isNoteOn()) continue;
            float nx = beatToX(evt->message.getTimeStamp());
            float ny = noteToY(evt->message.getNoteNumber());
            if (nx >= x1 && nx <= x2 && ny >= y1 && ny + noteHeight <= y2 + noteHeight)
                selectedIndices.push_back(i);
        }
        repaint();
    }
    else if (dragMode == VelocityEdit)
    {
        float velNorm = juce::jlimit(0.0f, 1.0f,
            1.0f - (my - gridAreaBottom()) / (float)velocityBarH);
        int vel = juce::jlimit(1, 127, (int)(velNorm * 127));

        auto& seq = currentClip->sequence;
        for (int idx : selectedIndices)
        {
            if (idx >= seq.getNumEvents()) continue;
            auto& msg = seq.getEventPointer(idx)->message;
            if (!msg.isNoteOn()) continue;
            auto newMsg = juce::MidiMessage::noteOn(msg.getChannel(), msg.getNoteNumber(), (juce::uint8)vel);
            newMsg.setTimeStamp(msg.getTimeStamp());
            msg = newMsg;
        }
        repaint();
    }
}

void PianoRoll::mouseUp(const juce::MouseEvent&)
{
    // X2 — wrap DrawNote completion in an undoable action.
    // Strategy: remove the preview note that was placed during mouseDown/drag
    // and re-insert it via AddNoteCmd so undo/redo works symmetrically.
    if (dragMode == DrawNote && undoManager != nullptr && currentClip != nullptr
        && dragNoteIdx >= 0 && dragNoteIdx < currentClip->sequence.getNumEvents())
    {
        auto& seq = currentClip->sequence;
        auto* evt = seq.getEventPointer(dragNoteIdx);
        if (evt != nullptr && evt->message.isNoteOn())
        {
            const int pitch  = evt->message.getNoteNumber();
            const int vel    = evt->message.getVelocity();
            const int ch     = evt->message.getChannel();
            const double start = evt->message.getTimeStamp();
            const double dur   = evt->noteOffObject
                ? evt->noteOffObject->message.getTimeStamp() - start
                : snapBeats;

            // Remove preview (both on and off)
            if (evt->noteOffObject)
            {
                int offIdx = seq.getIndexOf(evt->noteOffObject);
                if (offIdx >= 0) seq.deleteEvent(offIdx, false);
            }
            seq.deleteEvent(seq.getIndexOf(evt), false);
            seq.updateMatchedPairs();

            undoManager->beginNewTransaction("Draw note");
            undoManager->perform(new AddNoteCmd(currentClip, pitch, vel, start, dur, ch));
        }
    }

    // Y2 — Move/Resize undo: pair before-state with after-state and record
    if ((dragMode == MoveNote || dragMode == ResizeNote)
        && undoManager != nullptr && currentClip != nullptr
        && ! moveBefore.empty())
    {
        auto& seq = currentClip->sequence;
        std::vector<MoveNotesCmd::Change> changes;
        changes.reserve(moveBefore.size());

        // AA1 — consumed set to prevent a single after-note being matched
        // to multiple before-notes when velocity/channel collide.
        std::vector<bool> consumed(seq.getNumEvents(), false);

        for (auto& nb : moveBefore)
        {
            int bestIdx = -1;
            double bestDelta = 1e9;
            for (int i = 0; i < seq.getNumEvents(); ++i)
            {
                if (consumed[i]) continue;
                auto* e2 = seq.getEventPointer(i);
                if (! e2->message.isNoteOn()) continue;
                if (e2->message.getVelocity() != nb.vel) continue;
                if (e2->message.getChannel()  != nb.ch)  continue;
                const int    afterPitch = e2->message.getNoteNumber();
                const double afterStart = e2->message.getTimeStamp();
                if (std::abs(afterPitch - nb.pitch) > 24) continue;
                if (std::abs(afterStart - nb.start) > 32.0) continue;
                const double d = std::abs(afterStart - nb.start)
                               + std::abs((double)(afterPitch - nb.pitch));
                if (d < bestDelta) { bestDelta = d; bestIdx = i; }
            }
            if (bestIdx < 0) continue;
            consumed[bestIdx] = true;

            auto* e2 = seq.getEventPointer(bestIdx);
            MoveNotesCmd::Change ch;
            ch.beforePitch = nb.pitch;
            ch.beforeStart = nb.start;
            ch.beforeDur   = nb.dur;
            ch.afterPitch  = e2->message.getNoteNumber();
            ch.afterStart  = e2->message.getTimeStamp();
            ch.afterDur    = e2->noteOffObject
                ? e2->noteOffObject->message.getTimeStamp() - ch.afterStart
                : nb.dur;
            ch.channel  = nb.ch;
            ch.velocity = nb.vel;
            changes.push_back(ch);
        }

        // Skip recording if nothing actually changed (pure click)
        bool anyChange = false;
        for (auto& c : changes)
            if (c.beforePitch != c.afterPitch
             || std::abs(c.beforeStart - c.afterStart) > 1e-6
             || std::abs(c.beforeDur   - c.afterDur)   > 1e-6)
            { anyChange = true; break; }

        if (anyChange)
        {
            undoManager->beginNewTransaction(dragMode == MoveNote ? "Move notes" : "Resize note");
            // Revert to before-state, then perform forward; ensures perform/undo symmetry.
            // (Apply reverse of changes now so perform() brings us back to after-state.)
            for (auto& c : changes)
            {
                // Revert afterState to beforeState in-place so perform() re-applies
                auto tmpPitch = c.afterPitch;
                auto tmpStart = c.afterStart;
                auto tmpDur   = c.afterDur;
                for (int i = 0; i < seq.getNumEvents(); ++i)
                {
                    auto* e2 = seq.getEventPointer(i);
                    if (! e2->message.isNoteOn()) continue;
                    if (e2->message.getNoteNumber() != tmpPitch) continue;
                    if (std::abs(e2->message.getTimeStamp() - tmpStart) > 1e-6) continue;

                    auto newOn = juce::MidiMessage::noteOn(c.channel, c.beforePitch, (juce::uint8)c.velocity);
                    newOn.setTimeStamp(c.beforeStart);
                    e2->message = newOn;
                    if (e2->noteOffObject)
                    {
                        auto newOff = juce::MidiMessage::noteOff(c.channel, c.beforePitch);
                        newOff.setTimeStamp(c.beforeStart + c.beforeDur);
                        e2->noteOffObject->message = newOff;
                    }
                    break;
                }
            }
            seq.updateMatchedPairs();
            undoManager->perform(new MoveNotesCmd(currentClip, std::move(changes)));
        }

        moveBefore.clear();
    }

    // Z2 — velocity drag undo
    if (dragMode == VelocityEdit && undoManager != nullptr && currentClip != nullptr
        && ! velBefore.empty())
    {
        auto& seq = currentClip->sequence;
        std::vector<ChangeVelocityCmd::VelChange> vchanges;
        for (auto& nb : velBefore)
        {
            for (int i = 0; i < seq.getNumEvents(); ++i)
            {
                auto* e2 = seq.getEventPointer(i);
                if (! e2->message.isNoteOn()) continue;
                if (e2->message.getNoteNumber() != nb.pitch) continue;
                if (std::abs(e2->message.getTimeStamp() - nb.start) > 1e-6) continue;
                const int afterVel = e2->message.getVelocity();
                if (afterVel != nb.vel)
                    vchanges.push_back({ nb.pitch, nb.start, nb.vel, afterVel, nb.ch });
                break;
            }
        }
        if (! vchanges.empty())
        {
            // Revert to before, then perform to re-apply after.
            for (auto& v : vchanges)
                for (int i = 0; i < seq.getNumEvents(); ++i)
                {
                    auto* e2 = seq.getEventPointer(i);
                    if (! e2->message.isNoteOn()) continue;
                    if (e2->message.getNoteNumber() != v.pitch) continue;
                    if (std::abs(e2->message.getTimeStamp() - v.start) > 1e-6) continue;
                    auto m = juce::MidiMessage::noteOn(v.ch, v.pitch, (juce::uint8)v.beforeVel);
                    m.setTimeStamp(v.start);
                    e2->message = m;
                    break;
                }
            undoManager->beginNewTransaction("Velocity");
            undoManager->perform(new ChangeVelocityCmd(currentClip, std::move(vchanges)));
        }
        velBefore.clear();
    }

    if (dragMode == MoveNote || dragMode == ResizeNote || dragMode == DrawNote
        || dragMode == VelocityEdit)
        if (onNotesChanged) onNotesChanged();
    dragMode = None;
    dragNoteIdx = -1;
    dragNoteIdx = -1;
    origPositions.clear();
    repaint();
}

void PianoRoll::mouseDoubleClick(const juce::MouseEvent& e)
{
    if (!currentClip || e.x < pianoKeyWidth) return;
    int idx = findNoteAt(xToBeat((float)e.x), yToNote((float)e.y));
    if (idx >= 0) { selectedIndices = { idx }; deleteSelected(); }
}

void PianoRoll::mouseWheelMove(const juce::MouseEvent& e, const juce::MouseWheelDetails& w)
{
    if (e.mods.isCtrlDown())
        beatWidth = juce::jlimit(8.0f, 200.0f, beatWidth * (w.deltaY > 0 ? 1.15f : 0.87f));
    else if (e.mods.isShiftDown())
        scrollX = juce::jmax(0.0f, scrollX - w.deltaY * 100.0f);
    else
        scrollY = juce::jmax(0.0f, scrollY - w.deltaY * 60.0f);
    repaint();
}

// ---------------------------------------------------------------------------
// Keyboard
// ---------------------------------------------------------------------------
bool PianoRoll::keyPressed(const juce::KeyPress& key, juce::Component*)
{
    if (!currentClip) return false;

    if (key == juce::KeyPress::deleteKey || key == juce::KeyPress::backspaceKey)
    { deleteSelected(); return true; }

    if (key == juce::KeyPress('d')) { setTool(DrawTool); return true; }
    if (key == juce::KeyPress('s')) { setTool(SelectTool); return true; }
    if (key == juce::KeyPress('e')) { setTool(EraseTool); return true; }

    // Transpose
    if (key == juce::KeyPress::upKey || key == juce::KeyPress::downKey)
    {
        int delta = (key == juce::KeyPress::upKey) ? 1 : -1;
        if (key.getModifiers().isShiftDown()) delta *= 12;
        auto& seq = currentClip->sequence;
        for (int idx : selectedIndices)
        {
            if (idx >= seq.getNumEvents()) continue;
            auto* evt = seq.getEventPointer(idx);
            if (!evt->message.isNoteOn()) continue;
            int nn = juce::jlimit(0, 127, evt->message.getNoteNumber() + delta);
            evt->message = juce::MidiMessage::noteOn(evt->message.getChannel(), nn, evt->message.getVelocity());
            evt->message.setTimeStamp(seq.getEventPointer(idx)->message.getTimeStamp());
            if (evt->noteOffObject)
            {
                auto off = juce::MidiMessage::noteOff(evt->message.getChannel(), nn);
                off.setTimeStamp(evt->noteOffObject->message.getTimeStamp());
                evt->noteOffObject->message = off;
            }
        }
        repaint();
        if (onNotesChanged) onNotesChanged();
        return true;
    }

    // Select All
    if (key == juce::KeyPress('a', juce::ModifierKeys::ctrlModifier, 0))
    {
        selectedIndices.clear();
        auto& seq = currentClip->sequence;
        for (int i = 0; i < seq.getNumEvents(); ++i)
            if (seq.getEventPointer(i)->message.isNoteOn())
                selectedIndices.push_back(i);
        repaint();
        return true;
    }

    // Copy
    if (key == juce::KeyPress('c', juce::ModifierKeys::ctrlModifier, 0))
    {
        clipboard.clear();
        auto& seq = currentClip->sequence;
        double minBeat = 1e9;
        for (int idx : selectedIndices)
        {
            auto* evt = seq.getEventPointer(idx);
            if (evt && evt->message.isNoteOn())
                minBeat = juce::jmin(minBeat, evt->message.getTimeStamp());
        }
        for (int idx : selectedIndices)
        {
            auto* evt = seq.getEventPointer(idx);
            if (!evt || !evt->message.isNoteOn()) continue;
            ClipboardNote cn;
            cn.beat = evt->message.getTimeStamp() - minBeat;
            cn.noteNum = evt->message.getNoteNumber();
            cn.velocity = evt->message.getVelocity();
            cn.duration = 0.25;
            if (evt->noteOffObject)
                cn.duration = evt->noteOffObject->message.getTimeStamp() - evt->message.getTimeStamp();
            clipboard.push_back(cn);
        }
        return true;
    }

    // Paste
    if (key == juce::KeyPress('v', juce::ModifierKeys::ctrlModifier, 0))
    {
        if (clipboard.empty() || !currentClip) return true;
        double pasteBeat = playheadBeat >= 0 ? playheadBeat : 0.0;
        auto& seq = currentClip->sequence;
        selectedIndices.clear();
        for (auto& cn : clipboard)
        {
            auto on = juce::MidiMessage::noteOn(1, cn.noteNum, (juce::uint8)cn.velocity);
            on.setTimeStamp(pasteBeat + cn.beat);
            auto off = juce::MidiMessage::noteOff(1, cn.noteNum);
            off.setTimeStamp(pasteBeat + cn.beat + cn.duration);
            seq.addEvent(on);
            seq.addEvent(off);
        }
        seq.updateMatchedPairs();
        repaint();
        if (onNotesChanged) onNotesChanged();
        return true;
    }

    // Cut = Copy + Delete
    if (key == juce::KeyPress('x', juce::ModifierKeys::ctrlModifier, 0))
    {
        keyPressed(juce::KeyPress('c', juce::ModifierKeys::ctrlModifier, 0), this);
        deleteSelected();
        return true;
    }

    // Quantize: Q = full strength, Shift+Q = soft (50%)
    if (key == juce::KeyPress('q'))
    {
        const double strength = key.getModifiers().isShiftDown() ? 0.5 : 1.0;
        quantizeNotes(strength);
        return true;
    }

    // Take lanes: T = popup to swap/stash takes on the current clip.
    // First entry is "Stash current as Take N"; following entries
    // promote a stashed take into the active sequence.
    if (key == juce::KeyPress('t') && currentClip != nullptr)
    {
        juce::PopupMenu menu;
        const int numTakes = (int) currentClip->takes.size();
        menu.addItem (1, "Stash current as Take " + juce::String (numTakes + 1));
        if (numTakes > 0)
        {
            menu.addSeparator();
            for (int i = 0; i < numTakes; ++i)
            {
                const auto& lab = currentClip->takes[(size_t) i].name;
                menu.addItem (100 + i, "Swap to: "
                    + (lab.isNotEmpty() ? lab : ("Take " + juce::String (i + 1))));
            }
        }
        menu.showMenuAsync (juce::PopupMenu::Options{},
            [this] (int choice)
            {
                if (choice <= 0 || currentClip == nullptr) return;
                if (choice == 1)
                {
                    currentClip->stashCurrentAsTake (
                        "Take " + juce::String ((int) currentClip->takes.size() + 1));
                }
                else if (choice >= 100)
                {
                    currentClip->swapTake (choice - 100);
                }
                selectedIndices.clear();
                repaint();
                if (onNotesChanged) onNotesChanged();
            });
        return true;
    }

    // Groove: G = open picker (popup with built-in templates).
    if (key == juce::KeyPress('g'))
    {
        juce::PopupMenu menu;
        int id = 1;
        for (auto& g : GrooveTemplate::registry())
            menu.addItem (id++, g.name);
        menu.addSeparator();
        menu.addItem (100, "Strength: 100%");
        menu.addItem (75,  "Strength: 75%");
        menu.addItem (50,  "Strength: 50%");

        menu.showMenuAsync (juce::PopupMenu::Options{},
            [this] (int choice)
            {
                if (choice <= 0) return;
                if (choice >= 1 && choice <= (int) GrooveTemplate::registry().size())
                {
                    const auto& name = GrooveTemplate::registry()[(size_t)(choice - 1)].name;
                    applyGroove (name, 1.0);
                }
            });
        return true;
    }

    return false;
}

void PianoRoll::applyGroove (const juce::String& templateName, double strength)
{
    if (currentClip == nullptr) return;
    const auto* tmpl = GrooveTemplate::findByName (templateName);
    if (tmpl == nullptr) return;

    // Groove applies across the full clip length. Selection-scoped
    // variant honors the selectedIndices vector.
    std::vector<int> sel;
    if (! selectedIndices.empty())
        sel.assign (selectedIndices.begin(), selectedIndices.end());

    const double beatsPerBar = beatsPerBarProvider
                                   ? (double) juce::jmax (1, beatsPerBarProvider())
                                   : 4.0;
    tmpl->apply (currentClip->sequence,
                 0.0,
                 juce::jmax (beatsPerBar, currentClip->lengthBeats),
                 strength,
                 sel,
                 beatsPerBar);

    repaint();
    if (onNotesChanged) onNotesChanged();
}

void PianoRoll::quantizeNotes(double strength)
{
    if (currentClip == nullptr)         return;
    if (snapBeats <= 0.0)               return;
    strength = juce::jlimit(0.0, 1.0, strength);
    if (strength <= 0.0)                return;

    auto& seq = currentClip->sequence;

    // Determine target indices: selected if any, otherwise all note-on events.
    std::vector<int> targets;
    if (!selectedIndices.empty())
    {
        targets.reserve(selectedIndices.size());
        for (int idx : selectedIndices)
            if (idx >= 0 && idx < seq.getNumEvents())
                targets.push_back(idx);
    }
    else
    {
        for (int i = 0; i < seq.getNumEvents(); ++i)
            if (seq.getEventPointer(i)->message.isNoteOn())
                targets.push_back(i);
    }

    if (targets.empty()) return;

    int moved = 0;
    for (int idx : targets)
    {
        auto* evt = seq.getEventPointer(idx);
        if (evt == nullptr || ! evt->message.isNoteOn()) continue;

        const double original = evt->message.getTimeStamp();
        const double snapped  = snapBeat(original);
        const double newStart = original + (snapped - original) * strength;
        const double delta    = newStart - original;
        if (std::abs(delta) < 1.0e-9) continue;

        evt->message.setTimeStamp(newStart);
        if (evt->noteOffObject != nullptr)
        {
            const double offTime = evt->noteOffObject->message.getTimeStamp();
            evt->noteOffObject->message.setTimeStamp(offTime + delta);
        }
        ++moved;
    }

    if (moved == 0) return;

    seq.updateMatchedPairs();
    repaint();
    if (onNotesChanged) onNotesChanged();
}

void PianoRoll::timerCallback()
{
    // Playhead position will be set externally
}

void PianoRoll::resized() {}
