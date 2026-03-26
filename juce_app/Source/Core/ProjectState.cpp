/*
  ==============================================================================

    ProjectState.cpp
    MIDI AI Workstation - Project State Management

  ==============================================================================
*/

#include "ProjectState.h"

//==============================================================================
ProjectState::ProjectState()
{
    undoHistory.reserve (maxUndoLevels + 1);
}

//==============================================================================
// Track management
//==============================================================================

void ProjectState::addTrack (std::shared_ptr<TrackProcessor> track)
{
    if (track != nullptr)
    {
        tracks.push_back (std::move (track));
        modified = true;
    }
}

void ProjectState::removeTrack (int index)
{
    if (index >= 0 && index < static_cast<int> (tracks.size()))
    {
        tracks.erase (tracks.begin() + index);
        modified = true;
    }
}

int ProjectState::getNumTracks() const
{
    return static_cast<int> (tracks.size());
}

TrackProcessor* ProjectState::getTrack (int index) const
{
    if (index >= 0 && index < static_cast<int> (tracks.size()))
        return tracks[static_cast<size_t> (index)].get();

    return nullptr;
}

//==============================================================================
// MIDI file export (Standard MIDI File Type 1)
//==============================================================================

bool ProjectState::saveMidiFile (const juce::File& file) const
{
    juce::MidiFile midiFile;
    midiFile.setTicksPerQuarterNote (480);

    // Track 0: tempo track (meta events only)
    {
        juce::MidiMessageSequence tempoTrack;

        // Tempo meta event at tick 0
        auto tempoEvent = juce::MidiMessage::tempoMetaEvent (
            static_cast<int> (60000000.0 / bpm)); // microseconds per beat
        tempoEvent.setTimeStamp (0.0);
        tempoTrack.addEvent (tempoEvent);

        // Time signature meta event
        auto timeSigEvent = juce::MidiMessage::timeSignatureMetaEvent (
            timeSignatureNum, timeSignatureDen);
        timeSigEvent.setTimeStamp (0.0);
        tempoTrack.addEvent (timeSigEvent);

        // End of track
        auto endOfTrack = juce::MidiMessage::endOfTrack();
        endOfTrack.setTimeStamp (tempoTrack.getEndTime() + 1.0);
        tempoTrack.addEvent (endOfTrack);

        midiFile.addTrack (tempoTrack);
    }

    // One MIDI track per project track
    for (const auto& track : tracks)
    {
        if (track == nullptr)
            continue;

        juce::MidiMessageSequence seq;
        const int ticksPerBeat = 480;

        // Program change at the start
        if (track->instrument > 0)
        {
            auto pc = juce::MidiMessage::programChange (track->channel + 1, track->instrument);
            pc.setTimeStamp (0.0);
            seq.addEvent (pc);
        }

        // Track name meta event
        if (track->name.isNotEmpty())
        {
            auto nameEvent = juce::MidiMessage::textMetaEvent (3, track->name);
            nameEvent.setTimeStamp (0.0);
            seq.addEvent (nameEvent);
        }

        // Notes
        const auto& notes = track->getNotes();
        for (const auto& note : notes)
        {
            double startTick = note.startBeat * ticksPerBeat;
            double endTick   = note.getEndBeat() * ticksPerBeat;
            int ch = track->channel + 1; // MIDI channels are 1-based

            auto noteOn = juce::MidiMessage::noteOn (ch, note.pitch,
                                                      static_cast<juce::uint8> (note.velocity));
            noteOn.setTimeStamp (startTick);
            seq.addEvent (noteOn);

            auto noteOff = juce::MidiMessage::noteOff (ch, note.pitch);
            noteOff.setTimeStamp (endTick);
            seq.addEvent (noteOff);
        }

        // End of track marker
        auto endOfTrack = juce::MidiMessage::endOfTrack();
        endOfTrack.setTimeStamp (seq.getEndTime() + 1.0);
        seq.addEvent (endOfTrack);

        seq.sort();
        midiFile.addTrack (seq);
    }

    // Write to file
    juce::FileOutputStream outputStream (file);

    if (outputStream.failedToOpen())
        return false;

    outputStream.setPosition (0);
    outputStream.truncate();

    return midiFile.writeTo (outputStream, 1); // Type 1 MIDI
}

//==============================================================================
// MIDI file import
//==============================================================================

bool ProjectState::loadMidiFile (const juce::File& file)
{
    juce::FileInputStream inputStream (file);

    if (inputStream.failedToOpen())
        return false;

    juce::MidiFile midiFile;

    if (! midiFile.readFrom (inputStream))
        return false;

    // Clear existing state
    tracks.clear();
    projectName = file.getFileNameWithoutExtension();

    // Extract tempo from track 0
    const int ticksPerQuarterNote = midiFile.getTimeFormat();

    if (ticksPerQuarterNote <= 0)
        return false; // SMPTE timing not supported

    // Convert MIDI file to time-based format for easier parsing
    midiFile.convertTimestampTicksToSeconds();

    // Scan for tempo events in all tracks
    bpm = 120.0; // default
    for (int t = 0; t < midiFile.getNumTracks(); ++t)
    {
        const auto* sequence = midiFile.getTrack (t);
        if (sequence == nullptr)
            continue;

        for (int i = 0; i < sequence->getNumEvents(); ++i)
        {
            const auto& event = sequence->getEventPointer (i)->message;

            if (event.isTempoMetaEvent())
            {
                double tempo = event.getTempoMetaEventTickLength (ticksPerQuarterNote);
                if (tempo > 0.0)
                    bpm = 60.0 / tempo;
            }

            if (event.isTimeSignatureMetaEvent())
            {
                int num = 4, den = 4;
                event.getTimeSignatureInfo (num, den);
                timeSignatureNum = num;
                timeSignatureDen = den;
            }
        }
    }

    // Import each track
    const juce::Colour trackColours[] = {
        juce::Colours::cornflowerblue,
        juce::Colours::coral,
        juce::Colours::mediumseagreen,
        juce::Colours::mediumpurple,
        juce::Colours::sandybrown,
        juce::Colours::hotpink,
        juce::Colours::cadetblue,
        juce::Colours::darkkhaki
    };
    constexpr int numColours = sizeof (trackColours) / sizeof (trackColours[0]);

    for (int t = 0; t < midiFile.getNumTracks(); ++t)
    {
        const auto* sequence = midiFile.getTrack (t);
        if (sequence == nullptr)
            continue;

        // Extract track name
        juce::String trackName = "Track " + juce::String (t + 1);
        int trackChannel = 0;
        bool hasNotes = false;

        for (int i = 0; i < sequence->getNumEvents(); ++i)
        {
            const auto& msg = sequence->getEventPointer (i)->message;

            if (msg.isTextMetaEvent() && msg.getMetaEventType() == 3)
                trackName = msg.getTextFromTextMetaEvent();

            if (msg.isNoteOn())
            {
                hasNotes = true;
                trackChannel = msg.getChannel() - 1;
            }
        }

        // Skip tracks with no notes (e.g., tempo-only track 0)
        if (! hasNotes)
            continue;

        auto track = std::make_shared<TrackProcessor> (trackName, juce::jlimit (0, 15, trackChannel));
        track->colour = trackColours[static_cast<int> (tracks.size()) % numColours];

        // Pair note-on/note-off events using the matched pairs from JUCE
        const_cast<juce::MidiMessageSequence*>(sequence)->updateMatchedPairs();

        for (int i = 0; i < sequence->getNumEvents(); ++i)
        {
            const auto* eventHolder = sequence->getEventPointer (i);
            const auto& msg = eventHolder->message;

            if (! msg.isNoteOn() || msg.getFloatVelocity() == 0.0f)
                continue;

            double startTimeSeconds = msg.getTimeStamp();
            double endTimeSeconds   = startTimeSeconds;

            // Find the matching note-off
            if (eventHolder->noteOffObject != nullptr)
                endTimeSeconds = eventHolder->noteOffObject->message.getTimeStamp();
            else
                endTimeSeconds = startTimeSeconds + 0.25; // fallback: quarter note

            // Convert seconds to beats: beats = seconds * (bpm / 60)
            double startBeat = startTimeSeconds * (bpm / 60.0);
            double endBeat   = endTimeSeconds * (bpm / 60.0);
            double duration  = endBeat - startBeat;

            if (duration < 0.001)
                duration = 0.25; // minimum duration: 16th note at reasonable tempo

            TrackProcessor::Note note;
            note.pitch     = msg.getNoteNumber();
            note.velocity  = msg.getVelocity();
            note.startBeat = startBeat;
            note.duration  = duration;
            note.channel   = msg.getChannel() - 1;

            track->addNote (note);
        }

        track->sortNotes();
        tracks.push_back (std::move (track));
    }

    modified = false;
    return true;
}

//==============================================================================
// Native project save (JSON)
//==============================================================================

bool ProjectState::saveProject (const juce::File& file) const
{
    auto projectVar = toVar();
    juce::String jsonString = juce::JSON::toString (projectVar, true);

    if (! file.replaceWithText (jsonString))
        return false;

    return true;
}

bool ProjectState::loadProject (const juce::File& file)
{
    juce::String jsonString = file.loadFileAsString();

    if (jsonString.isEmpty())
        return false;

    auto parsed = juce::JSON::parse (jsonString);

    if (! parsed.isObject())
        return false;

    fromVar (parsed);
    projectFile = file;
    modified    = false;
    return true;
}

//==============================================================================
// Static factory
//==============================================================================

std::shared_ptr<ProjectState> ProjectState::importMidi (const juce::File& midiFile)
{
    auto project = std::make_shared<ProjectState>();

    if (project->loadMidiFile (midiFile))
        return project;

    return nullptr;
}

//==============================================================================
// Undo / Redo
//==============================================================================

void ProjectState::pushUndo (const juce::String& description)
{
    // Remove any redo states beyond current position
    if (undoPosition >= 0 && undoPosition < static_cast<int> (undoHistory.size()) - 1)
        undoHistory.erase (undoHistory.begin() + undoPosition + 1, undoHistory.end());

    // Capture current state
    UndoState snapshot;
    snapshot.description = description;
    snapshot.state       = toVar();
    undoHistory.push_back (std::move (snapshot));

    // Enforce maximum undo depth
    if (static_cast<int> (undoHistory.size()) > maxUndoLevels)
        undoHistory.erase (undoHistory.begin());

    undoPosition = static_cast<int> (undoHistory.size()) - 1;
}

bool ProjectState::undo()
{
    if (! canUndo())
        return false;

    // If we are at the latest state and haven't saved current, push it
    if (undoPosition == static_cast<int> (undoHistory.size()) - 1)
    {
        UndoState current;
        current.description = "Current";
        current.state       = toVar();
        undoHistory.push_back (std::move (current));
    }

    undoPosition--;
    fromVar (undoHistory[static_cast<size_t> (undoPosition)].state);
    modified = true;
    return true;
}

bool ProjectState::redo()
{
    if (! canRedo())
        return false;

    undoPosition++;
    fromVar (undoHistory[static_cast<size_t> (undoPosition)].state);
    modified = true;
    return true;
}

bool ProjectState::canUndo() const
{
    return undoPosition > 0;
}

bool ProjectState::canRedo() const
{
    return undoPosition >= 0
           && undoPosition < static_cast<int> (undoHistory.size()) - 1;
}

juce::String ProjectState::getUndoDescription() const
{
    if (canUndo() && undoPosition > 0)
        return undoHistory[static_cast<size_t> (undoPosition)].description;

    return {};
}

juce::String ProjectState::getRedoDescription() const
{
    if (canRedo())
        return undoHistory[static_cast<size_t> (undoPosition + 1)].description;

    return {};
}

//==============================================================================
// Serialization
//==============================================================================

juce::var ProjectState::toVar() const
{
    auto* obj = new juce::DynamicObject();

    obj->setProperty ("projectName",      projectName);
    obj->setProperty ("bpm",              bpm);
    obj->setProperty ("timeSignatureNum", timeSignatureNum);
    obj->setProperty ("timeSignatureDen", timeSignatureDen);
    obj->setProperty ("key",              key);
    obj->setProperty ("scale",            scale);
    obj->setProperty ("version",          1); // Schema version for future compatibility

    juce::Array<juce::var> trackArray;
    for (const auto& track : tracks)
    {
        if (track != nullptr)
            trackArray.add (trackToVar (*track));
    }
    obj->setProperty ("tracks", trackArray);

    return juce::var (obj);
}

void ProjectState::fromVar (const juce::var& v)
{
    if (! v.isObject())
        return;

    projectName      = v.getProperty ("projectName", "Untitled").toString();
    bpm              = static_cast<double> (v.getProperty ("bpm", 120.0));
    timeSignatureNum = static_cast<int> (v.getProperty ("timeSignatureNum", 4));
    timeSignatureDen = static_cast<int> (v.getProperty ("timeSignatureDen", 4));
    key              = v.getProperty ("key", "C").toString();
    scale            = v.getProperty ("scale", "minor").toString();

    tracks.clear();

    auto* trackArray = v.getProperty ("tracks", juce::var()).getArray();
    if (trackArray != nullptr)
    {
        for (const auto& trackVar : *trackArray)
        {
            auto track = varToTrack (trackVar);
            if (track != nullptr)
                tracks.push_back (std::move (track));
        }
    }
}

juce::var ProjectState::noteToVar (const TrackProcessor::Note& note)
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty ("pitch",     note.pitch);
    obj->setProperty ("velocity",  note.velocity);
    obj->setProperty ("startBeat", note.startBeat);
    obj->setProperty ("duration",  note.duration);
    obj->setProperty ("channel",   note.channel);
    return juce::var (obj);
}

TrackProcessor::Note ProjectState::varToNote (const juce::var& v)
{
    TrackProcessor::Note note;

    if (v.isObject())
    {
        note.pitch     = static_cast<int> (v.getProperty ("pitch", 60));
        note.velocity  = static_cast<int> (v.getProperty ("velocity", 100));
        note.startBeat = static_cast<double> (v.getProperty ("startBeat", 0.0));
        note.duration  = static_cast<double> (v.getProperty ("duration", 1.0));
        note.channel   = static_cast<int> (v.getProperty ("channel", 0));
    }

    return note;
}

juce::var ProjectState::trackToVar (const TrackProcessor& track)
{
    auto* obj = new juce::DynamicObject();

    obj->setProperty ("name",       track.name);
    obj->setProperty ("channel",    track.channel);
    obj->setProperty ("volume",     static_cast<double> (track.volume));
    obj->setProperty ("pan",        static_cast<double> (track.pan));
    obj->setProperty ("muted",      track.muted);
    obj->setProperty ("solo",       track.solo);
    obj->setProperty ("armed",      track.armed);
    obj->setProperty ("instrument", track.instrument);
    obj->setProperty ("colour",     track.colour.toString());

    juce::Array<juce::var> noteArray;
    const auto& notes = track.getNotes();
    for (const auto& note : notes)
        noteArray.add (noteToVar (note));

    obj->setProperty ("notes", noteArray);

    return juce::var (obj);
}

std::shared_ptr<TrackProcessor> ProjectState::varToTrack (const juce::var& v)
{
    if (! v.isObject())
        return nullptr;

    juce::String name    = v.getProperty ("name", "Track").toString();
    int          channel = static_cast<int> (v.getProperty ("channel", 0));

    auto track = std::make_shared<TrackProcessor> (name, channel);

    track->volume     = static_cast<float> (static_cast<double> (v.getProperty ("volume", 1.0)));
    track->pan        = static_cast<float> (static_cast<double> (v.getProperty ("pan", 0.0)));
    track->muted      = static_cast<bool> (v.getProperty ("muted", false));
    track->solo       = static_cast<bool> (v.getProperty ("solo", false));
    track->armed      = static_cast<bool> (v.getProperty ("armed", false));
    track->instrument = static_cast<int> (v.getProperty ("instrument", 0));

    juce::String colourStr = v.getProperty ("colour", "").toString();
    if (colourStr.isNotEmpty())
        track->colour = juce::Colour::fromString (colourStr);

    auto* noteArray = v.getProperty ("notes", juce::var()).getArray();
    if (noteArray != nullptr)
    {
        for (const auto& noteVar : *noteArray)
            track->addNote (varToNote (noteVar));

        track->sortNotes();
    }

    return track;
}
