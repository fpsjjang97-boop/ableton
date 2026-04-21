/*
 * MidiGPT DAW — ScoreView.cpp
 */

#include "ScoreView.h"
#include "LookAndFeel.h"

ScoreView::ScoreView()
{
    setOpaque (true);
    startTimerHz (30);  // playhead follow
}

void ScoreView::timerCallback() { repaint(); }

void ScoreView::resized()
{
    // Vertically centre the grand staff with a 4-spacing gap between clefs.
    const int h = getHeight();
    const int totalStaffH = staffLineSpacing * 4 * 2 + staffLineSpacing * 4;
    int top = juce::jmax (headerH + 10, (h - totalStaffH) / 2);
    trebleTopY = top;
    trebleBotY = top + staffLineSpacing * 4;
    bassTopY   = trebleBotY + staffLineSpacing * 4;
    bassBotY   = bassTopY + staffLineSpacing * 4;
}

void ScoreView::paint (juce::Graphics& g)
{
    g.fillAll (juce::Colour (MetallicLookAndFeel::bgPanel));
    drawStaff (g);
    drawNotes (g);
    drawPlayhead (g);

    if (isRecording && isRecording())
    {
        g.setColour (juce::Colour (0x30FF0000));
        g.fillRect (0, 0, getWidth(), getHeight());
        g.setColour (juce::Colour (0xFFFF4444));
        g.setFont (14.0f);
        g.drawText ("REC — score read-only",
                    getLocalBounds().reduced (12),
                    juce::Justification::topRight);
    }

    // No-clip hint so the panel isn't blank on fresh projects.
    if (currentClip == nullptr)
    {
        g.setColour (juce::Colour (MetallicLookAndFeel::textSecondary));
        g.setFont (juce::Font (13.0f, juce::Font::italic));
        g.drawText ("Select a MIDI clip in the Arrangement to see it here",
                    getLocalBounds(),
                    juce::Justification::centred);
    }
}

void ScoreView::drawStaff (juce::Graphics& g)
{
    g.setColour (juce::Colour (MetallicLookAndFeel::textSecondary));
    const float x0 = (float) clefColumnWidth;
    const float x1 = (float) getWidth() - 8.0f;

    auto staffLines = [&] (int topY)
    {
        for (int i = 0; i < 5; ++i)
            g.drawHorizontalLine (topY + i * staffLineSpacing, x0, x1);
    };
    staffLines (trebleTopY);
    staffLines (bassTopY);

    // Vertical spine connecting both clefs — distinguishes "grand staff".
    g.drawLine (x0, (float) trebleTopY, x0, (float) bassBotY, 1.0f);

    // Text clef markers in the left column (no glyph font for a 𝄞/𝄢 SVG —
    // MVP uses readable letters).
    g.setColour (juce::Colour (MetallicLookAndFeel::textPrimary));
    g.setFont (juce::Font (14.0f, juce::Font::bold));
    g.drawText ("G", 8, trebleTopY - 4, clefColumnWidth - 16,
                staffLineSpacing * 4 + 8, juce::Justification::centred);
    g.drawText ("F", 8, bassTopY - 4, clefColumnWidth - 16,
                staffLineSpacing * 4 + 8, juce::Justification::centred);

    // Header band.
    g.setColour (juce::Colour (MetallicLookAndFeel::bgHeader));
    g.fillRect (0, 0, getWidth(), headerH);
    g.setColour (juce::Colour (MetallicLookAndFeel::textSecondary));
    g.setFont (11.0f);
    g.drawText (currentClip ? juce::String ("Score — ") + (currentClip->name.isNotEmpty()
                                                            ? currentClip->name
                                                            : juce::String ("(unnamed)"))
                             : juce::String ("Score"),
                8, 2, getWidth() - 16, headerH - 4,
                juce::Justification::centredLeft);
}

void ScoreView::drawNotes (juce::Graphics& g)
{
    if (currentClip == nullptr) return;
    auto& seq = currentClip->sequence;

    // Barlines at every bar (consults project time signature).
    const double beatsPerBar = beatsPerBarProvider
                                   ? (double) juce::jmax (1, beatsPerBarProvider())
                                   : 4.0;
    {
        g.setColour (juce::Colour (MetallicLookAndFeel::textDim).withAlpha (0.5f));
        const double firstBeat = juce::jmax (0.0, (double)(scrollX / beatWidth));
        const double lastBeat  = firstBeat + (double)(getWidth() - clefColumnWidth) / beatWidth;
        for (double b = std::ceil (firstBeat / beatsPerBar) * beatsPerBar;
             b <= lastBeat; b += beatsPerBar)
        {
            const float bx = beatToX (b);
            if (bx < clefColumnWidth || bx > getWidth()) continue;
            g.drawLine (bx, (float) trebleTopY, bx, (float) bassBotY, 0.8f);
        }
    }

    const float headW = (float) staffLineSpacing * 1.1f;
    const float headH = (float) staffLineSpacing * 0.9f;

    for (int i = 0; i < seq.getNumEvents(); ++i)
    {
        auto* evt = seq.getEventPointer (i);
        if (! evt->message.isNoteOn()) continue;

        const int    pitch     = evt->message.getNoteNumber();
        const double startBeat = evt->message.getTimeStamp();
        const double endBeat   = evt->noteOffObject
                                     ? evt->noteOffObject->message.getTimeStamp()
                                     : startBeat + 0.25;
        const double durBeats  = juce::jmax (0.0625, endBeat - startBeat);

        const float x = beatToX (startBeat);
        if (x + headW < clefColumnWidth || x > getWidth()) continue;

        const int y = pitchToStaffY (pitch);

        // Notehead: filled for quarter and shorter, open for half/whole.
        auto [label, buckets] = quantiseDuration (durBeats);
        const juce::String labelS (label);
        const bool openHead = (labelS == "1" || labelS == "1/2");

        g.setColour (juce::Colour (MetallicLookAndFeel::accentLight));
        if (openHead)
        {
            g.drawEllipse (x - headW * 0.5f, (float) y - headH * 0.5f,
                           headW, headH, 1.4f);
        }
        else
        {
            g.fillEllipse (x - headW * 0.5f, (float) y - headH * 0.5f,
                           headW, headH);
        }

        // Whole notes have no stem; everything else does.
        if (labelS != "1")
        {
            const bool stemUp = pitch < 71;
            const float stemX = stemUp ? (x + headW * 0.45f) : (x - headW * 0.45f);
            const float stemY0 = (float) y;
            const float stemY1 = stemY0 + (stemUp ? -staffLineSpacing * 3.5f
                                                   :  staffLineSpacing * 3.5f);
            g.setColour (juce::Colour (MetallicLookAndFeel::textPrimary));
            g.drawLine (stemX, stemY0, stemX, stemY1, 1.2f);

            // Flag: one stroke for 8th, two for 16th. Drawn as short slants.
            if (labelS == "1/8" || labelS == "1/16")
            {
                g.drawLine (stemX, stemY1,
                            stemX + (stemUp ? 5.0f : -5.0f),
                            stemY1 + (stemUp ? 4.0f : -4.0f), 1.2f);
                if (labelS == "1/16")
                {
                    const float y2 = stemY1 + (stemUp ? 4.0f : -4.0f);
                    g.drawLine (stemX, y2,
                                stemX + (stemUp ? 5.0f : -5.0f),
                                y2 + (stemUp ? 4.0f : -4.0f), 1.2f);
                }
            }
        }

        // Sharp glyph (simple '#') for black keys. Key-signature handling
        // is out of scope for MVP.
        if (juce::MidiMessage::isMidiNoteBlack (pitch))
        {
            g.setFont (juce::Font ((float) staffLineSpacing, juce::Font::bold));
            g.drawText ("#", (int) (x - headW * 1.3f), y - staffLineSpacing,
                        (int) headW, staffLineSpacing * 2,
                        juce::Justification::centredRight);
        }

        // Tie across bar boundary — if the note spans a barline, draw a
        // curved arc from the notehead to the barline so readers see it
        // as "held" rather than as a duplicate note. Full tie-splitting
        // (actually drawing two noteheads joined by a slur) is larger
        // scope; this arc is the visual hint MVP.
        const double nextBar = std::ceil (startBeat / beatsPerBar + 1e-9) * beatsPerBar;
        if (endBeat > nextBar + 0.05)
        {
            const float x2 = beatToX (nextBar);
            if (x2 > clefColumnWidth && x2 < getWidth())
            {
                juce::Path arc;
                const float arcY = (float) y + headH * 0.55f;
                arc.startNewSubPath (x + headW * 0.4f, arcY);
                arc.quadraticTo ((x + x2) * 0.5f, arcY + 5.0f,
                                 x2 - 2.0f, arcY);
                g.setColour (juce::Colour (MetallicLookAndFeel::accent));
                g.strokePath (arc, juce::PathStrokeType (1.2f));
            }
        }
    }
}

void ScoreView::drawPlayhead (juce::Graphics& g)
{
    if (playheadBeat < 0.0) return;
    const float x = beatToX (playheadBeat);
    if (x < clefColumnWidth || x > getWidth()) return;
    g.setColour (juce::Colour (MetallicLookAndFeel::accent).withAlpha (0.8f));
    g.drawVerticalLine ((int) x, (float) headerH, (float) getHeight());
}

void ScoreView::mouseWheelMove (const juce::MouseEvent&,
                                 const juce::MouseWheelDetails& w)
{
    scrollX = juce::jmax (0.0f, scrollX - w.deltaY * 80.0f);
    repaint();
}

int ScoreView::pitchToStaffY (int midiPitch) const
{
    // Diatonic step from middle C (60). Each "step" in C-major is a
    // half-line on the staff (1/2 staffLineSpacing). C major diatonic:
    //   C D E F G A B → 0 2 4 5 7 9 11 semitones → 7 diatonic steps.
    // We treat sharp/flat as occupying the same position as the natural
    // of the same letter (key-signature handling TODO).
    static const int semitoneToStep[12] = {
        0, 0, 1, 1, 2, 3, 3, 4, 4, 5, 5, 6
    };
    const int octavesFromMC = (midiPitch / 12) - 5;      // C5 = octave 0
    const int stepInOct     = semitoneToStep[midiPitch % 12];
    const int diatonicSteps = octavesFromMC * 7 + stepInOct;

    // Middle C (MIDI 60) sits one ledger line below treble staff (just
    // below line 5 = trebleBotY + 1 spacing).
    const int middleCY = trebleBotY + staffLineSpacing;

    // Higher pitches → higher on screen (smaller Y). Each diatonic step
    // = half the line spacing.
    return middleCY - (int) ((float) diatonicSteps * staffLineSpacing * 0.5f);
}

std::pair<const char*, double> ScoreView::quantiseDuration (double beats)
{
    if (beats >= 3.0) return {"1",    4.0};
    if (beats >= 1.5) return {"1/2",  2.0};
    if (beats >= 0.75) return {"1/4", 1.0};
    if (beats >= 0.375) return {"1/8", 0.5};
    return {"1/16", 0.25};
}
