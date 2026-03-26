#include "PianoRoll.h"

//==============================================================================
PianoRoll::PianoRoll()
{
    setWantsKeyboardFocus (true);
    addKeyListener (this);
    startTimerHz (30);

    // Default scroll to middle C area
    scrollY = (float) (totalNotes - 72) * noteHeight;
}

PianoRoll::~PianoRoll()
{
    removeKeyListener (this);
    stopTimer();
}

//==============================================================================
// Coordinate conversions
//==============================================================================
float PianoRoll::beatToX (double beat) const
{
    return pianoKeyWidth + (float) beat * beatWidth - scrollX;
}

double PianoRoll::xToBeat (float x) const
{
    return ((double) x - pianoKeyWidth + scrollX) / (double) beatWidth;
}

int PianoRoll::noteToY (int noteNumber) const
{
    return headerH + (totalNotes - 1 - noteNumber) * noteHeight - (int) scrollY;
}

int PianoRoll::yToNote (int y) const
{
    return totalNotes - 1 - (int) ((float) (y - headerH) + scrollY) / noteHeight;
}

double PianoRoll::snapBeat (double beat) const
{
    if (snapBeats <= 0.0) return beat;
    return std::round (beat / snapBeats) * snapBeats;
}

bool PianoRoll::isBlackKey (int noteNumber)
{
    int n = noteNumber % 12;
    return n == 1 || n == 3 || n == 6 || n == 8 || n == 10;
}

juce::String PianoRoll::noteName (int noteNumber)
{
    static const char* names[] = { "C", "C#", "D", "D#", "E", "F",
                                    "F#", "G", "G#", "A", "A#", "B" };
    int octave = (noteNumber / 12) - 2;
    return juce::String (names[noteNumber % 12]) + juce::String (octave);
}

//==============================================================================
// Hit testing
//==============================================================================
bool PianoRoll::isInPianoArea (juce::Point<int> pos) const
{
    return pos.x < pianoKeyWidth && pos.y >= headerH && pos.y < getHeight() - velocityBarH;
}

bool PianoRoll::isInGridArea (juce::Point<int> pos) const
{
    return pos.x >= pianoKeyWidth && pos.y >= headerH && pos.y < getHeight() - velocityBarH;
}

bool PianoRoll::isInVelocityArea (juce::Point<int> pos) const
{
    return pos.y >= getHeight() - velocityBarH;
}

int PianoRoll::hitTestNote (juce::Point<int> pos) const
{
    for (int i = notes.size() - 1; i >= 0; --i)
    {
        auto& n = notes.getReference (i);
        float nx = beatToX (n.startBeat);
        float nw = (float) n.duration * beatWidth;
        int   ny = noteToY (n.noteNumber);

        if (pos.x >= (int) nx && pos.x <= (int) (nx + nw) &&
            pos.y >= ny && pos.y < ny + noteHeight)
        {
            return i;
        }
    }
    return -1;
}

bool PianoRoll::isOnNoteRightEdge (juce::Point<int> pos, int noteIndex) const
{
    if (noteIndex < 0 || noteIndex >= notes.size()) return false;
    auto& n = notes.getReference (noteIndex);
    float rightEdge = beatToX (n.startBeat + n.duration);
    return std::abs (pos.x - (int) rightEdge) <= 4;
}

//==============================================================================
// Drawing
//==============================================================================
void PianoRoll::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgDarkest);

    auto bounds = getLocalBounds();
    auto headerArea   = bounds.removeFromTop (headerH);
    auto velocityArea = bounds.removeFromBottom (velocityBarH);
    auto pianoArea    = bounds.removeFromLeft (pianoKeyWidth);
    auto gridArea     = bounds;

    drawHeader (g, headerArea);
    drawGrid (g, gridArea);
    drawNotes (g, gridArea);
    drawPlayhead (g, gridArea);
    drawRubberBand (g);
    drawPianoKeys (g, pianoArea);
    drawVelocityBar (g, velocityArea);
}

void PianoRoll::drawHeader (juce::Graphics& g, juce::Rectangle<int> area)
{
    g.setColour (MetallicLookAndFeel::bgHeader);
    g.fillRect (area);

    g.setColour (MetallicLookAndFeel::border);
    g.drawHorizontalLine (area.getBottom() - 1, 0.0f, (float) getWidth());

    // Bar numbers
    g.setFont (juce::Font (10.0f));
    double beatsPerBar = (double) timeSigNum;
    int totalBeats = totalBars * timeSigNum;

    for (int bar = 0; bar <= totalBars; ++bar)
    {
        float x = beatToX (bar * beatsPerBar);
        if (x >= pianoKeyWidth && x < (float) getWidth())
        {
            g.setColour (MetallicLookAndFeel::textDim);
            g.drawText (juce::String (bar + 1), (int) x + 2, area.getY(),
                        40, area.getHeight(), juce::Justification::centredLeft, false);
        }
    }
}

void PianoRoll::drawPianoKeys (juce::Graphics& g, juce::Rectangle<int> area)
{
    g.setColour (MetallicLookAndFeel::bgDark);
    g.fillRect (area);

    g.setFont (juce::Font (9.0f));

    for (int note = 0; note < totalNotes; ++note)
    {
        int y = noteToY (note);
        if (y + noteHeight < area.getY() || y > area.getBottom())
            continue;

        bool black = isBlackKey (note);

        auto keyRect = juce::Rectangle<int> (area.getX(), y, area.getWidth(), noteHeight);

        if (black)
        {
            g.setColour (juce::Colour (0xFF1A1A1A));
            g.fillRect (keyRect);
        }
        else
        {
            g.setColour (juce::Colour (0xFF2C2C2C));
            g.fillRect (keyRect);
        }

        // Key border
        g.setColour (MetallicLookAndFeel::border.withAlpha (0.5f));
        g.drawHorizontalLine (y + noteHeight - 1, (float) area.getX(), (float) area.getRight());

        // Note name on C notes
        if (note % 12 == 0)
        {
            g.setColour (MetallicLookAndFeel::textSecondary);
            g.drawText (noteName (note), keyRect.reduced (2, 0),
                        juce::Justification::centredRight, false);
        }
    }

    // Right border
    g.setColour (MetallicLookAndFeel::border);
    g.drawVerticalLine (area.getRight() - 1, (float) area.getY(), (float) area.getBottom());
}

void PianoRoll::drawGrid (juce::Graphics& g, juce::Rectangle<int> area)
{
    g.saveState();
    g.reduceClipRegion (area);

    double beatsPerBar = (double) timeSigNum;
    int totalBeats = totalBars * timeSigNum;

    // Draw note row backgrounds (alternating for black keys)
    for (int note = 0; note < totalNotes; ++note)
    {
        int y = noteToY (note);
        if (y + noteHeight < area.getY() || y > area.getBottom())
            continue;

        if (isBlackKey (note))
        {
            g.setColour (juce::Colour (0xFF141414));
            g.fillRect (area.getX(), y, area.getWidth(), noteHeight);
        }

        // Octave line
        if (note % 12 == 0)
        {
            g.setColour (MetallicLookAndFeel::border);
            g.drawHorizontalLine (y + noteHeight - 1, (float) area.getX(), (float) area.getRight());
        }
    }

    // Beat grid lines
    for (int beat = 0; beat <= totalBeats; ++beat)
    {
        float x = beatToX ((double) beat);
        if (x < (float) area.getX() || x > (float) area.getRight())
            continue;

        bool isBar = (beat % timeSigNum == 0);
        g.setColour (isBar ? MetallicLookAndFeel::gridBar : MetallicLookAndFeel::border.withAlpha (0.4f));
        g.drawVerticalLine ((int) x, (float) area.getY(), (float) area.getBottom());
    }

    // Sub-beat grid (if zoomed in enough)
    if (beatWidth >= 30.0f)
    {
        g.setColour (MetallicLookAndFeel::border.withAlpha (0.15f));
        double subDiv = snapBeats > 0.0 ? snapBeats : 0.25;
        for (double b = 0.0; b <= (double) totalBeats; b += subDiv)
        {
            float x = beatToX (b);
            if (x >= (float) area.getX() && x <= (float) area.getRight())
                g.drawVerticalLine ((int) x, (float) area.getY(), (float) area.getBottom());
        }
    }

    g.restoreState();
}

void PianoRoll::drawNotes (juce::Graphics& g, juce::Rectangle<int> area)
{
    g.saveState();
    g.reduceClipRegion (area);

    for (int i = 0; i < notes.size(); ++i)
    {
        auto& n = notes.getReference (i);
        float nx = beatToX (n.startBeat);
        float nw = (float) n.duration * beatWidth;
        int   ny = noteToY (n.noteNumber);

        if (nx + nw < (float) area.getX() || nx > (float) area.getRight())
            continue;
        if (ny + noteHeight < area.getY() || ny > area.getBottom())
            continue;

        auto noteRect = juce::Rectangle<float> (nx, (float) ny, nw, (float) noteHeight - 1.0f);

        // Note body - velocity-based brightness
        float velBright = (float) n.velocity / 127.0f;
        auto noteCol = n.selected
            ? MetallicLookAndFeel::clipSelected
            : MetallicLookAndFeel::clipColour.interpolatedWith (MetallicLookAndFeel::accentLight, velBright * 0.3f);

        g.setColour (noteCol);
        g.fillRoundedRectangle (noteRect, 2.0f);

        // Metallic top highlight
        g.setColour (juce::Colours::white.withAlpha (0.08f));
        g.fillRoundedRectangle (noteRect.withHeight (noteRect.getHeight() * 0.4f), 2.0f);

        // Border
        g.setColour (n.selected ? MetallicLookAndFeel::accentLight : noteCol.darker (0.3f));
        g.drawRoundedRectangle (noteRect, 2.0f, n.selected ? 1.5f : 0.8f);

        // Velocity bar inside note (thin line at bottom)
        auto velBarRect = noteRect.withTop (noteRect.getBottom() - 2.0f);
        velBarRect = velBarRect.withWidth (velBarRect.getWidth() * velBright);
        g.setColour (MetallicLookAndFeel::accentLight.withAlpha (0.3f));
        g.fillRect (velBarRect);

        // Resize handle on right edge
        if (n.selected && nw > 10.0f)
        {
            g.setColour (MetallicLookAndFeel::accentLight.withAlpha (0.4f));
            g.fillRect (noteRect.getRight() - 3.0f, noteRect.getY() + 2.0f,
                        2.0f, noteRect.getHeight() - 4.0f);
        }
    }

    g.restoreState();
}

void PianoRoll::drawPlayhead (juce::Graphics& g, juce::Rectangle<int> area)
{
    float x = beatToX (playheadBeat);
    if (x >= (float) area.getX() && x <= (float) area.getRight())
    {
        g.setColour (juce::Colour (0xDDFFFFFF));
        g.drawVerticalLine ((int) x, (float) area.getY(), (float) area.getBottom());

        // Triangle at top
        juce::Path tri;
        tri.addTriangle (x - 4.0f, (float) area.getY(),
                         x + 4.0f, (float) area.getY(),
                         x,        (float) area.getY() + 6.0f);
        g.fillPath (tri);
    }
}

void PianoRoll::drawRubberBand (juce::Graphics& g)
{
    if (dragMode == DragMode::SelectRubberBand)
    {
        auto rect = juce::Rectangle<int> (rubberBandStart, rubberBandEnd);
        g.setColour (MetallicLookAndFeel::accent.withAlpha (0.15f));
        g.fillRect (rect);
        g.setColour (MetallicLookAndFeel::accent.withAlpha (0.5f));
        g.drawRect (rect, 1);
    }
}

void PianoRoll::drawVelocityBar (juce::Graphics& g, juce::Rectangle<int> area)
{
    g.setColour (MetallicLookAndFeel::bgDark);
    g.fillRect (area);

    g.setColour (MetallicLookAndFeel::border);
    g.drawHorizontalLine (area.getY(), 0.0f, (float) getWidth());

    // Label
    g.setColour (MetallicLookAndFeel::textDim);
    g.setFont (juce::Font (9.0f));
    g.drawText ("Vel", area.removeFromLeft (pianoKeyWidth).reduced (2),
                juce::Justification::centredRight, false);

    // Draw velocity bars for each note
    for (int i = 0; i < notes.size(); ++i)
    {
        auto& n = notes.getReference (i);
        float nx = beatToX (n.startBeat);
        float nw = juce::jmax (3.0f, (float) n.duration * beatWidth);

        if (nx + nw < (float) area.getX() || nx > (float) area.getRight())
            continue;

        float velH = ((float) n.velocity / 127.0f) * (float) (area.getHeight() - 4);
        auto barRect = juce::Rectangle<float> (nx, (float) area.getBottom() - velH - 2.0f,
                                                juce::jmin (nw - 1.0f, 8.0f), velH);

        auto velCol = n.selected ? MetallicLookAndFeel::clipSelected
                     : MetallicLookAndFeel::velocityLow.interpolatedWith (
                           MetallicLookAndFeel::velocityHigh, (float) n.velocity / 127.0f);
        g.setColour (velCol);
        g.fillRect (barRect);
    }
}

//==============================================================================
// Mouse interaction
//==============================================================================
void PianoRoll::mouseDown (const juce::MouseEvent& e)
{
    auto pos = e.getPosition();

    // Piano key area - preview note
    if (isInPianoArea (pos))
    {
        int note = yToNote (pos.y);
        if (note >= 0 && note < 128 && onNotePreview)
            onNotePreview (note, 100);
        return;
    }

    // Velocity area
    if (isInVelocityArea (pos))
    {
        dragMode = DragMode::VelocityEdit;
        // Find nearest note and adjust velocity
        int bestIdx = -1;
        float bestDist = 999999.0f;
        for (int i = 0; i < notes.size(); ++i)
        {
            float nx = beatToX (notes[i].startBeat);
            float dist = std::abs (nx - (float) pos.x);
            if (dist < bestDist && dist < 20.0f)
            {
                bestDist = dist;
                bestIdx = i;
            }
        }
        if (bestIdx >= 0)
        {
            int velArea = getHeight() - velocityBarH;
            float velFrac = 1.0f - (float) (pos.y - velArea) / (float) velocityBarH;
            notes.getReference (bestIdx).velocity = juce::jlimit (1, 127, (int) (velFrac * 127.0f));
            if (onNotesChanged) onNotesChanged();
            repaint();
        }
        return;
    }

    // Grid area
    if (! isInGridArea (pos))
        return;

    // Right-click: delete note
    if (e.mods.isRightButtonDown())
    {
        int idx = hitTestNote (pos);
        if (idx >= 0)
        {
            removeNote (idx);
            if (onNotesChanged) onNotesChanged();
        }
        return;
    }

    int hitIdx = hitTestNote (pos);

    if (currentTool == Tool::Draw)
    {
        if (hitIdx >= 0)
        {
            // Click on existing note - select/move/resize
            if (! e.mods.isShiftDown())
                deselectAll();

            notes.getReference (hitIdx).selected = true;

            if (isOnNoteRightEdge (pos, hitIdx))
            {
                dragMode = DragMode::ResizeNote;
                dragNoteIndex = hitIdx;
                dragStartBeat = notes[hitIdx].duration;
            }
            else
            {
                dragMode = DragMode::MoveNote;
                dragNoteIndex = hitIdx;
                dragOffsetBeat = xToBeat ((float) pos.x) - notes[hitIdx].startBeat;
                dragOffsetNote = yToNote (pos.y) - notes[hitIdx].noteNumber;
            }
        }
        else
        {
            // Click on empty space - create new note
            double beat = snapBeat (xToBeat ((float) pos.x));
            int note = yToNote (pos.y);

            if (note >= 0 && note < 128 && beat >= 0.0)
            {
                pendingNote.noteNumber = note;
                pendingNote.startBeat  = beat;
                pendingNote.duration   = snapBeats > 0.0 ? snapBeats : 0.25;
                pendingNote.velocity   = 100;
                pendingNote.selected   = true;

                deselectAll();
                dragMode = DragMode::DrawNote;

                if (onNotePreview)
                    onNotePreview (note, 100);
            }
        }
    }
    else if (currentTool == Tool::Select)
    {
        if (hitIdx >= 0)
        {
            if (! e.mods.isShiftDown() && ! notes[hitIdx].selected)
                deselectAll();

            notes.getReference (hitIdx).selected = true;

            if (isOnNoteRightEdge (pos, hitIdx))
            {
                dragMode = DragMode::ResizeNote;
                dragNoteIndex = hitIdx;
                dragStartBeat = notes[hitIdx].duration;
            }
            else
            {
                dragMode = DragMode::MoveNote;
                dragNoteIndex = hitIdx;
                dragOffsetBeat = xToBeat ((float) pos.x) - notes[hitIdx].startBeat;
                dragOffsetNote = yToNote (pos.y) - notes[hitIdx].noteNumber;
            }
        }
        else
        {
            if (! e.mods.isShiftDown())
                deselectAll();

            dragMode = DragMode::SelectRubberBand;
            rubberBandStart = pos;
            rubberBandEnd   = pos;
        }
    }
    else if (currentTool == Tool::Erase)
    {
        if (hitIdx >= 0)
        {
            removeNote (hitIdx);
            if (onNotesChanged) onNotesChanged();
        }
    }

    repaint();
}

void PianoRoll::mouseDrag (const juce::MouseEvent& e)
{
    auto pos = e.getPosition();

    switch (dragMode)
    {
        case DragMode::DrawNote:
        {
            double endBeat = snapBeat (xToBeat ((float) pos.x));
            pendingNote.duration = juce::jmax (snapBeats > 0.0 ? snapBeats : 0.25,
                                               endBeat - pendingNote.startBeat);
            repaint();
            break;
        }
        case DragMode::MoveNote:
        {
            if (dragNoteIndex < 0 || dragNoteIndex >= notes.size())
                break;

            double newBeat = snapBeat (xToBeat ((float) pos.x) - dragOffsetBeat);
            int newNote = yToNote (pos.y) - dragOffsetNote;
            newBeat = juce::jmax (0.0, newBeat);
            newNote = juce::jlimit (0, 127, newNote);

            double beatDelta = newBeat - notes[dragNoteIndex].startBeat;
            int noteDelta = newNote - notes[dragNoteIndex].noteNumber;

            // Move all selected notes
            for (auto& n : notes)
            {
                if (n.selected)
                {
                    n.startBeat = juce::jmax (0.0, n.startBeat + beatDelta);
                    n.noteNumber = juce::jlimit (0, 127, n.noteNumber + noteDelta);
                }
            }
            repaint();
            break;
        }
        case DragMode::ResizeNote:
        {
            if (dragNoteIndex < 0 || dragNoteIndex >= notes.size())
                break;

            double endBeat = snapBeat (xToBeat ((float) pos.x));
            double minDur = snapBeats > 0.0 ? snapBeats : 0.125;
            auto& n = notes.getReference (dragNoteIndex);
            n.duration = juce::jmax (minDur, endBeat - n.startBeat);
            repaint();
            break;
        }
        case DragMode::SelectRubberBand:
        {
            rubberBandEnd = pos;

            // Select notes within rubber band
            auto selRect = juce::Rectangle<int> (rubberBandStart, rubberBandEnd);
            for (auto& n : notes)
            {
                float nx = beatToX (n.startBeat);
                float nw = (float) n.duration * beatWidth;
                int ny = noteToY (n.noteNumber);
                auto noteRect = juce::Rectangle<float> (nx, (float) ny, nw, (float) noteHeight);
                n.selected = selRect.toFloat().intersects (noteRect);
            }
            repaint();
            break;
        }
        case DragMode::VelocityEdit:
        {
            int velAreaTop = getHeight() - velocityBarH;
            float velFrac = 1.0f - (float) (pos.y - velAreaTop) / (float) velocityBarH;
            int vel = juce::jlimit (1, 127, (int) (velFrac * 127.0f));
            for (auto& n : notes)
            {
                if (n.selected)
                    n.velocity = vel;
            }
            repaint();
            break;
        }
        default:
            break;
    }
}

void PianoRoll::mouseUp (const juce::MouseEvent&)
{
    if (dragMode == DragMode::DrawNote)
    {
        addNote (pendingNote);
        if (onNotesChanged) onNotesChanged();
    }

    if (dragMode == DragMode::MoveNote || dragMode == DragMode::ResizeNote)
    {
        if (onNotesChanged) onNotesChanged();
    }

    dragMode = DragMode::None;
    dragNoteIndex = -1;
    repaint();
}

void PianoRoll::mouseDoubleClick (const juce::MouseEvent& e)
{
    if (isInGridArea (e.getPosition()))
    {
        int idx = hitTestNote (e.getPosition());
        if (idx >= 0)
        {
            removeNote (idx);
            if (onNotesChanged) onNotesChanged();
            repaint();
        }
    }
}

void PianoRoll::mouseWheelMove (const juce::MouseEvent& e, const juce::MouseWheelDetails& w)
{
    if (e.mods.isCtrlDown())
    {
        // Zoom horizontal
        zoomHorizontal (w.deltaY > 0 ? 1.15f : 0.87f);
    }
    else if (e.mods.isShiftDown())
    {
        // Scroll horizontal
        scrollX -= w.deltaY * 100.0f;
        scrollX = juce::jmax (0.0f, scrollX);
    }
    else
    {
        // Scroll vertical
        scrollY -= w.deltaY * 60.0f;
        scrollY = juce::jmax (0.0f, juce::jmin (scrollY,
                    (float) (totalNotes * noteHeight - (getHeight() - headerH - velocityBarH))));
    }
    repaint();
}

//==============================================================================
// Keyboard
//==============================================================================
bool PianoRoll::keyPressed (const juce::KeyPress& key, juce::Component*)
{
    if (key == juce::KeyPress::deleteKey || key == juce::KeyPress::backspaceKey)
    {
        deleteSelected();
        return true;
    }
    if (key == juce::KeyPress::upKey)
    {
        transposeSelected (key.getModifiers().isShiftDown() ? 12 : 1);
        return true;
    }
    if (key == juce::KeyPress::downKey)
    {
        transposeSelected (key.getModifiers().isShiftDown() ? -12 : -1);
        return true;
    }
    if (key.getModifiers().isCommandDown() && key.getKeyCode() == 'C')
    {
        copySelected();
        return true;
    }
    if (key.getModifiers().isCommandDown() && key.getKeyCode() == 'V')
    {
        paste();
        return true;
    }
    if (key.getModifiers().isCommandDown() && key.getKeyCode() == 'A')
    {
        selectAll();
        return true;
    }
    if (key.getKeyCode() == 'D' || key.getKeyCode() == 'd')
    {
        setTool (Tool::Draw);
        return true;
    }
    if (key.getKeyCode() == 'S' || key.getKeyCode() == 's')
    {
        setTool (Tool::Select);
        return true;
    }
    if (key.getKeyCode() == 'E' || key.getKeyCode() == 'e')
    {
        setTool (Tool::Erase);
        return true;
    }
    return false;
}

//==============================================================================
// Note management
//==============================================================================
void PianoRoll::setNotes (const juce::Array<NoteEvent>& newNotes)
{
    notes = newNotes;
    repaint();
}

juce::Array<NoteEvent>& PianoRoll::getNotes()             { return notes; }
const juce::Array<NoteEvent>& PianoRoll::getNotes() const { return notes; }

void PianoRoll::addNote (const NoteEvent& note)
{
    notes.add (note);
    repaint();
}

void PianoRoll::removeNote (int index)
{
    if (index >= 0 && index < notes.size())
    {
        notes.remove (index);
        repaint();
    }
}

void PianoRoll::clearNotes()
{
    notes.clear();
    repaint();
}

void PianoRoll::selectAll()
{
    for (auto& n : notes)
        n.selected = true;
    repaint();
}

void PianoRoll::deselectAll()
{
    for (auto& n : notes)
        n.selected = false;
    repaint();
}

void PianoRoll::deleteSelected()
{
    for (int i = notes.size() - 1; i >= 0; --i)
    {
        if (notes[i].selected)
            notes.remove (i);
    }
    if (onNotesChanged) onNotesChanged();
    repaint();
}

void PianoRoll::transposeSelected (int semitones)
{
    for (auto& n : notes)
    {
        if (n.selected)
            n.noteNumber = juce::jlimit (0, 127, n.noteNumber + semitones);
    }
    if (onNotesChanged) onNotesChanged();
    repaint();
}

void PianoRoll::copySelected()
{
    clipboard.clear();
    for (auto& n : notes)
    {
        if (n.selected)
            clipboard.add (n);
    }
}

void PianoRoll::paste()
{
    if (clipboard.isEmpty()) return;

    deselectAll();

    // Find earliest beat in clipboard
    double minBeat = std::numeric_limits<double>::max();
    for (auto& n : clipboard)
        minBeat = juce::jmin (minBeat, n.startBeat);

    // Paste at playhead
    double offset = playheadBeat - minBeat;

    for (auto n : clipboard)
    {
        n.startBeat += offset;
        n.selected = true;
        notes.add (n);
    }

    if (onNotesChanged) onNotesChanged();
    repaint();
}

//==============================================================================
// View parameters
//==============================================================================
void PianoRoll::setPlayheadPosition (double beatPosition)
{
    playheadBeat = beatPosition;
    repaint();
}

void PianoRoll::setGridSnap (double beatsPerSnap)
{
    snapBeats = beatsPerSnap;
    repaint();
}

void PianoRoll::setTotalBars (int bars)
{
    totalBars = juce::jmax (1, bars);
    repaint();
}

void PianoRoll::setTimeSignature (int numerator, int denominator)
{
    timeSigNum = numerator;
    timeSigDen = denominator;
    repaint();
}

void PianoRoll::zoomHorizontal (float factor)
{
    beatWidth = juce::jlimit (minBeatW, maxBeatW, beatWidth * factor);
    repaint();
}

void PianoRoll::zoomVertical (float factor)
{
    noteHeight = juce::jlimit (minNoteH, maxNoteH, (int) ((float) noteHeight * factor));
    repaint();
}

void PianoRoll::scrollToNote (int noteNumber)
{
    int targetY = (totalNotes - 1 - noteNumber) * noteHeight;
    int viewH = getHeight() - headerH - velocityBarH;
    scrollY = (float) juce::jmax (0, targetY - viewH / 2);
    repaint();
}

//==============================================================================
void PianoRoll::resized()
{
    repaint();
}

void PianoRoll::timerCallback()
{
    // In a real app, update playhead position from the audio engine
}
