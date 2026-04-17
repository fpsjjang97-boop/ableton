/*
 * MidiGPT VST3 Plugin — MiniPianoRoll.cpp
 *
 * See header for design notes.
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include "MiniPianoRoll.h"

MiniPianoRoll::MiniPianoRoll()
{
    setOpaque (true);
    setInterceptsMouseClicks (false, false);
}

void MiniPianoRoll::setSequence (const juce::MidiMessageSequence& newSequence)
{
    sequence = newSequence;
    sequence.updateMatchedPairs();
    rebuildNoteCache();
    repaint();
}

void MiniPianoRoll::setTitle (const juce::String& t)
{
    title = t;
    repaint();
}

void MiniPianoRoll::setEmptyPlaceholder (const juce::String& text)
{
    emptyPlaceholder = text;
    repaint();
}

void MiniPianoRoll::rebuildNoteCache()
{
    notes.clear();
    lowestPitch  = 127;
    highestPitch = 0;
    totalBeats   = 4.0;

    for (int i = 0; i < sequence.getNumEvents(); ++i)
    {
        auto* evt = sequence.getEventPointer (i);
        const auto& msg = evt->message;
        if (! msg.isNoteOn()) continue;

        const double startBeat = msg.getTimeStamp();
        double lengthBeat = 0.5;    // default if no matching off
        if (evt->noteOffObject != nullptr)
        {
            lengthBeat = evt->noteOffObject->message.getTimeStamp() - startBeat;
            if (lengthBeat <= 0.0) lengthBeat = 0.25;
        }

        const int pitch = msg.getNoteNumber();
        const int vel   = msg.getVelocity();

        notes.push_back ({ startBeat, lengthBeat, pitch, vel });
        lowestPitch  = juce::jmin (lowestPitch, pitch);
        highestPitch = juce::jmax (highestPitch, pitch);
        totalBeats   = juce::jmax (totalBeats, startBeat + lengthBeat);
    }

    // Keep at least a 12-semitone window so a single-note sequence
    // doesn't render as a full-height block.
    if (lowestPitch > highestPitch)
    {
        lowestPitch  = 60;
        highestPitch = 72;
    }
    else if (highestPitch - lowestPitch < 11)
    {
        const int centre = (lowestPitch + highestPitch) / 2;
        lowestPitch  = juce::jmax (0,   centre - 6);
        highestPitch = juce::jmin (127, centre + 6);
    }
}

void MiniPianoRoll::paint (juce::Graphics& g)
{
    const auto bounds = getLocalBounds().toFloat();

    // Background
    g.fillAll (juce::Colour (0xFF1B1D26));

    // Title bar
    const int titleH = 18;
    g.setColour (juce::Colour (0xFF2A2D3A));
    g.fillRect (bounds.withHeight ((float) titleH));
    g.setColour (juce::Colours::white.withAlpha (0.9f));
    g.setFont (11.0f);
    g.drawText (title, 6, 0, getWidth() - 12, titleH, juce::Justification::centredLeft);

    const auto noteArea = bounds.withTrimmedTop ((float) titleH).reduced (1.0f);

    if (notes.empty())
    {
        g.setColour (juce::Colours::grey);
        g.setFont (12.0f);
        g.drawText (emptyPlaceholder, noteArea.toNearestInt(), juce::Justification::centred);
        return;
    }

    // Horizontal grid lines every 4 semitones — subtle.
    const int pitchRange = juce::jmax (1, highestPitch - lowestPitch);
    const float rowH = noteArea.getHeight() / (float) pitchRange;

    g.setColour (juce::Colours::white.withAlpha (0.05f));
    for (int p = lowestPitch; p <= highestPitch; p += 4)
    {
        const float y = noteArea.getBottom() - (p - lowestPitch) * rowH;
        g.drawHorizontalLine ((int) y, noteArea.getX(), noteArea.getRight());
    }

    // Vertical beat markers (integer beats).
    g.setColour (juce::Colours::white.withAlpha (0.07f));
    const float beatW = noteArea.getWidth() / (float) juce::jmax (1.0, totalBeats);
    for (int b = 1; b < (int) totalBeats; ++b)
    {
        const float x = noteArea.getX() + b * beatW;
        g.drawVerticalLine ((int) x, noteArea.getY(), noteArea.getBottom());
    }

    // Notes
    for (const auto& n : notes)
    {
        const float x  = noteArea.getX() + (float) (n.startBeat * beatW);
        const float w  = juce::jmax (1.5f, (float) (n.lengthBeat * beatW));
        const float y  = noteArea.getBottom() - (n.pitch - lowestPitch + 1) * rowH;
        const float h  = juce::jmax (1.5f, rowH - 1.0f);

        // Colour: hue by pitch class, brightness by velocity.
        const float hue = (n.pitch % 12) / 12.0f;
        const float bright = 0.5f + (n.velocity / 127.0f) * 0.5f;
        g.setColour (juce::Colour::fromHSV (hue, 0.7f, bright, 0.9f));
        g.fillRect (x, y, w, h);
    }
}
