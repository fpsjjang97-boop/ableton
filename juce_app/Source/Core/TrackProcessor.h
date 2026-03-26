/*
  ==============================================================================

    TrackProcessor.h
    MIDI AI Workstation - Track Processor

    Represents a single MIDI track containing notes, channel assignment,
    mixer controls, and the logic to extract MIDI events for a given
    beat range during playback.

  ==============================================================================
*/

#pragma once
#include <JuceHeader.h>

//==============================================================================
/**
    Represents one MIDI track with its note data and mixer settings.

    Each track stores a collection of MIDI notes with beat-based timing,
    and can produce a juce::MidiBuffer of events for any requested beat range.
    This is the fundamental data unit that the AudioEngine iterates over
    during playback.
*/
class TrackProcessor
{
public:
    //==========================================================================
    /** A single MIDI note event with beat-based timing. */
    struct Note
    {
        int    pitch       = 60;   // MIDI note number 0-127
        int    velocity    = 100;  // MIDI velocity 0-127
        double startBeat   = 0.0;  // Position in beats from start of project
        double duration    = 1.0;  // Length in beats
        int    channel     = 0;    // MIDI channel 0-15

        /** Returns the end position in beats. */
        double getEndBeat() const { return startBeat + duration; }

        /** Comparison for sorting by start time. */
        bool operator< (const Note& other) const { return startBeat < other.startBeat; }
    };

    //==========================================================================
    TrackProcessor (const juce::String& name, int channel = 0);

    //==========================================================================
    // Note management

    /** Add a note to this track. Thread-safe. */
    void addNote (const Note& note);

    /** Remove a note by index. Thread-safe. */
    void removeNote (int index);

    /** Remove all notes matching the given predicate. Thread-safe. */
    template <typename Predicate>
    void removeNotesIf (Predicate pred)
    {
        const juce::ScopedLock sl (noteLock);
        notes.erase (std::remove_if (notes.begin(), notes.end(), pred), notes.end());
    }

    /** Remove all notes. Thread-safe. */
    void clearNotes();

    /** Get a read-only reference to the note list. Not thread-safe without external locking. */
    const std::vector<Note>& getNotes() const;

    /** Get the number of notes. */
    int getNumNotes() const;

    /** Sort notes by start beat. Call after batch modifications. */
    void sortNotes();

    //==========================================================================
    /**
        Extract MIDI events (note-on and note-off) that fall within the given
        beat range. Sample positions in the returned MidiBuffer are relative
        to the start of the range (sample 0 = startBeat).

        @param startBeat  Start of the range in beats (inclusive)
        @param endBeat    End of the range in beats (exclusive)
        @param sampleRate Current sample rate in Hz
        @param bpm        Current tempo in beats per minute
        @return           MidiBuffer with note-on/off events, sample-positioned
    */
    juce::MidiBuffer getMidiEventsInRange (double startBeat, double endBeat,
                                           double sampleRate, double bpm) const;

    //==========================================================================
    // Properties (public for simple binding; use setters for thread-safe mutation)

    juce::String name;
    int          channel    = 0;      // MIDI channel 0-15
    float        volume     = 1.0f;   // 0.0 to 1.0
    float        pan        = 0.0f;   // -1.0 (left) to 1.0 (right)
    bool         muted      = false;
    bool         solo       = false;
    bool         armed      = false;  // Record-armed
    int          instrument = 0;      // GM program number
    juce::Colour colour;

    /** Get the total length of this track (end of last note). */
    double getTotalLengthInBeats() const;

    /** Acquire the note lock for external batch operations. */
    juce::CriticalSection& getNoteLock() { return noteLock; }

private:
    std::vector<Note>      notes;
    juce::CriticalSection  noteLock;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TrackProcessor)
};
