/*
 * MidiGPT DAW — EditCommands (V1)
 *
 * Minimum viable undo/redo. Covers 4 operations that users repeat most and
 * where accidental loss is most painful:
 *   - AddNoteCmd    (PianoRoll draw)
 *   - DeleteNotesCmd (PianoRoll Delete key)
 *   - AddClipCmd     (ArrangementView double-click)
 *   - DeleteTrackCmd (track context menu)
 *
 * Sprint scope: these 4 only. Automation edits, CC edits, step seq edits,
 * plugin add/remove are NOT undoable in this sprint. Incremental coverage
 * is Sprint 6+.
 *
 * UndoableAction convention: perform() applies the change and returns true;
 * undo() reverses it and returns true. Both must leave the model valid.
 */

#pragma once

#include <juce_data_structures/juce_data_structures.h>
#include "../Core/TrackModel.h"
#include "../Core/AudioEngine.h"

class AddNoteCmd : public juce::UndoableAction
{
public:
    AddNoteCmd(MidiClip* clip, int pitch, int velocity,
               double startBeat, double durationBeats, int channel = 1);

    bool perform() override;
    bool undo() override;

private:
    MidiClip* clip;
    int pitch, velocity, channel;
    double startBeat, durationBeats;
};

class DeleteNotesCmd : public juce::UndoableAction
{
public:
    struct NoteSnap { int pitch; int vel; int ch; double start; double dur; };
    DeleteNotesCmd(MidiClip* clip, std::vector<NoteSnap> snaps);

    bool perform() override;
    bool undo() override;

private:
    MidiClip* clip;
    std::vector<NoteSnap> snaps;
};

class AddClipCmd : public juce::UndoableAction
{
public:
    AddClipCmd(Track* track, double startBeat, double lengthBeats);
    bool perform() override;
    bool undo() override;
private:
    Track* track;
    double startBeat, lengthBeats;
};

class DeleteTrackCmd : public juce::UndoableAction
{
public:
    DeleteTrackCmd(TrackModel& model, int trackId);
    bool perform() override;
    bool undo() override;
private:
    TrackModel& model;
    int trackId;
    Track snapshot;     // full copy for restore
    bool hadSnapshot { false };
};

/** Z2 — Change velocities on a set of notes. Matched by (pitch, startBeat)
 *  pairs since notes are stored as MidiMessageSequence events without
 *  stable ids. Caller supplies before/after velocity per note. */
class ChangeVelocityCmd : public juce::UndoableAction
{
public:
    struct VelChange { int pitch; double start; int beforeVel; int afterVel; int ch { 1 }; };
    ChangeVelocityCmd(MidiClip* clip, std::vector<VelChange> changes);
    bool perform() override;
    bool undo() override;
private:
    MidiClip* clip;
    std::vector<VelChange> changes;
    void apply(bool toAfter);
};

/** Y2 — Move or resize one or more notes. Caller captures the "before"
 *  state (pitch, start, dur) and the "after" state at mouseUp. perform()
 *  applies the after-state; undo() restores the before-state. Matching is
 *  by (beforePitch, beforeStart) since note-ons don't have stable ids. */
class MoveNotesCmd : public juce::UndoableAction
{
public:
    struct Change
    {
        int    beforePitch, afterPitch;
        double beforeStart, afterStart;
        double beforeDur,   afterDur;
        int    channel { 1 };
        int    velocity { 100 };
    };

    MoveNotesCmd(MidiClip* clip, std::vector<Change> changes);
    bool perform() override;
    bool undo() override;

private:
    MidiClip* clip;
    std::vector<Change> changes;

    void applyState(bool toAfter);
};
