/*
  ==============================================================================

    TrackProcessor.cpp
    MIDI AI Workstation - Track Processor

  ==============================================================================
*/

#include "TrackProcessor.h"

//==============================================================================
TrackProcessor::TrackProcessor (const juce::String& trackName, int midiChannel)
    : name (trackName),
      channel (juce::jlimit (0, 15, midiChannel)),
      colour (juce::Colours::cornflowerblue)
{
    notes.reserve (256);
}

//==============================================================================
// Note management
//==============================================================================

void TrackProcessor::addNote (const Note& note)
{
    const juce::ScopedLock sl (noteLock);

    Note sanitised = note;
    sanitised.pitch    = juce::jlimit (0, 127, sanitised.pitch);
    sanitised.velocity = juce::jlimit (1, 127, sanitised.velocity);
    sanitised.duration = juce::jmax (0.001, sanitised.duration);
    sanitised.channel  = juce::jlimit (0, 15, sanitised.channel);

    notes.push_back (sanitised);
}

void TrackProcessor::removeNote (int index)
{
    const juce::ScopedLock sl (noteLock);

    if (index >= 0 && index < static_cast<int> (notes.size()))
        notes.erase (notes.begin() + index);
}

void TrackProcessor::clearNotes()
{
    const juce::ScopedLock sl (noteLock);
    notes.clear();
}

const std::vector<TrackProcessor::Note>& TrackProcessor::getNotes() const
{
    return notes;
}

int TrackProcessor::getNumNotes() const
{
    const juce::ScopedLock sl (noteLock);
    return static_cast<int> (notes.size());
}

void TrackProcessor::sortNotes()
{
    const juce::ScopedLock sl (noteLock);
    std::sort (notes.begin(), notes.end());
}

//==============================================================================
// MIDI event extraction
//==============================================================================

juce::MidiBuffer TrackProcessor::getMidiEventsInRange (double startBeat, double endBeat,
                                                        double sampleRate, double bpm) const
{
    juce::MidiBuffer result;

    if (muted || bpm <= 0.0 || sampleRate <= 0.0 || endBeat <= startBeat)
        return result;

    const juce::ScopedLock sl (noteLock);

    // Conversion factor: samples per beat
    const double samplesPerBeat = (60.0 / bpm) * sampleRate;
    const double rangeStartSample = 0.0; // sample 0 = startBeat

    for (const auto& note : notes)
    {
        const double noteEnd = note.getEndBeat();

        // --- Note-on events ---
        // A note-on falls in this range if the note starts within [startBeat, endBeat)
        if (note.startBeat >= startBeat && note.startBeat < endBeat)
        {
            double offsetBeats  = note.startBeat - startBeat;
            int    sampleOffset = static_cast<int> (offsetBeats * samplesPerBeat + rangeStartSample);

            if (sampleOffset < 0)
                sampleOffset = 0;

            // Use the track's channel if the note's channel matches 0 (default),
            // otherwise respect the note's explicit channel
            int ch = (note.channel == 0) ? channel : note.channel;

            auto noteOn = juce::MidiMessage::noteOn (ch + 1, // MIDI channels are 1-based
                                                     note.pitch,
                                                     static_cast<juce::uint8> (note.velocity));
            result.addEvent (noteOn, sampleOffset);
        }

        // --- Note-off events ---
        // A note-off falls in this range if the note ends within [startBeat, endBeat)
        if (noteEnd >= startBeat && noteEnd < endBeat)
        {
            double offsetBeats  = noteEnd - startBeat;
            int    sampleOffset = static_cast<int> (offsetBeats * samplesPerBeat + rangeStartSample);

            if (sampleOffset < 0)
                sampleOffset = 0;

            int ch = (note.channel == 0) ? channel : note.channel;

            auto noteOff = juce::MidiMessage::noteOff (ch + 1, note.pitch);
            result.addEvent (noteOff, sampleOffset);
        }

        // --- Handle notes that started before this range but are still sounding ---
        // If a note started before startBeat and ends after startBeat, we need
        // a note-on at sample 0 so the synth knows to sound it.
        // (This handles seeking / loop boundaries where notes span the boundary.)
        if (note.startBeat < startBeat && noteEnd > startBeat)
        {
            int ch = (note.channel == 0) ? channel : note.channel;

            auto noteOn = juce::MidiMessage::noteOn (ch + 1,
                                                     note.pitch,
                                                     static_cast<juce::uint8> (note.velocity));
            result.addEvent (noteOn, 0);
        }
    }

    return result;
}

//==============================================================================
// Properties
//==============================================================================

double TrackProcessor::getTotalLengthInBeats() const
{
    const juce::ScopedLock sl (noteLock);

    double maxEnd = 0.0;

    for (const auto& note : notes)
    {
        double end = note.getEndBeat();
        if (end > maxEnd)
            maxEnd = end;
    }

    return maxEnd;
}
