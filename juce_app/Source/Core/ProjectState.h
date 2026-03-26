/*
  ==============================================================================

    ProjectState.h
    MIDI AI Workstation - Project State Management

    Handles project persistence (save/load in JSON format), MIDI file
    import/export, track management, and undo/redo history.

  ==============================================================================
*/

#pragma once
#include <JuceHeader.h>
#include "TrackProcessor.h"

//==============================================================================
/**
    Manages the complete project state: track data, tempo, metadata, and
    provides file I/O for both native JSON projects and standard MIDI files.
    Includes a linear undo/redo system for non-destructive editing.
*/
class ProjectState
{
public:
    ProjectState();

    //==========================================================================
    // Project properties
    juce::String projectName      = "Untitled";
    juce::File   projectFile;
    double       bpm              = 120.0;
    int          timeSignatureNum = 4;
    int          timeSignatureDen = 4;
    juce::String key              = "C";
    juce::String scale            = "minor";
    bool         modified         = false;

    //==========================================================================
    // Track management
    std::vector<std::shared_ptr<TrackProcessor>> tracks;

    void addTrack (std::shared_ptr<TrackProcessor> track);
    void removeTrack (int index);
    int  getNumTracks() const;
    TrackProcessor* getTrack (int index) const;

    //==========================================================================
    // MIDI file I/O

    /** Export the project as a Standard MIDI File (Type 1). */
    bool saveMidiFile (const juce::File& file) const;

    /** Load a Standard MIDI File, replacing current project content. */
    bool loadMidiFile (const juce::File& file);

    //==========================================================================
    // Native project I/O (JSON format)

    /** Save the project to a JSON file. */
    bool saveProject (const juce::File& file) const;

    /** Load a project from a JSON file. */
    bool loadProject (const juce::File& file);

    //==========================================================================
    // Static factory

    /** Import a MIDI file and return a new ProjectState. */
    static std::shared_ptr<ProjectState> importMidi (const juce::File& midiFile);

    //==========================================================================
    // Undo / Redo

    /** Capture a snapshot of the current state for undo. */
    void pushUndo (const juce::String& description);

    /** Revert to the previous state. Returns true if successful. */
    bool undo();

    /** Re-apply a previously undone state. Returns true if successful. */
    bool redo();

    bool canUndo() const;
    bool canRedo() const;

    /** Get a human-readable description of the next undo action. */
    juce::String getUndoDescription() const;

    /** Get a human-readable description of the next redo action. */
    juce::String getRedoDescription() const;

private:
    //==========================================================================
    struct UndoState
    {
        juce::String description;
        juce::var    state;
    };

    std::vector<UndoState> undoHistory;
    int undoPosition = -1;

    static constexpr int maxUndoLevels = 100;

    //==========================================================================
    // Serialization helpers

    /** Serialize the entire project state to a juce::var (JSON-compatible). */
    juce::var toVar() const;

    /** Deserialize project state from a juce::var. */
    void fromVar (const juce::var& v);

    /** Convert a single Note to a juce::var. */
    static juce::var noteToVar (const TrackProcessor::Note& note);

    /** Convert a juce::var back to a Note. */
    static TrackProcessor::Note varToNote (const juce::var& v);

    /** Convert a single TrackProcessor to a juce::var. */
    static juce::var trackToVar (const TrackProcessor& track);

    /** Create a TrackProcessor from a juce::var. */
    static std::shared_ptr<TrackProcessor> varToTrack (const juce::var& v);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ProjectState)
};
