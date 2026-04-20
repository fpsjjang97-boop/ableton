#include "EditCommands.h"
#include "../Audio/AudioClip.h"
#include <cmath>

// ---------------------------------------------------------------------------
// AddNoteCmd
// ---------------------------------------------------------------------------
AddNoteCmd::AddNoteCmd(MidiClip* c, int p, int v, double sb, double db, int ch)
    : clip(c), pitch(p), velocity(v), channel(ch),
      startBeat(sb), durationBeats(db) {}

bool AddNoteCmd::perform()
{
    if (clip == nullptr) return false;
    auto on  = juce::MidiMessage::noteOn(channel, pitch, (juce::uint8)velocity);
    auto off = juce::MidiMessage::noteOff(channel, pitch);
    on.setTimeStamp(startBeat);
    off.setTimeStamp(startBeat + durationBeats);
    clip->sequence.addEvent(on);
    clip->sequence.addEvent(off);
    clip->sequence.updateMatchedPairs();
    return true;
}

bool AddNoteCmd::undo()
{
    if (clip == nullptr) return false;
    for (int i = clip->sequence.getNumEvents() - 1; i >= 0; --i)
    {
        auto& m = clip->sequence.getEventPointer(i)->message;
        if (m.isNoteOn()
            && m.getNoteNumber() == pitch
            && std::abs(m.getTimeStamp() - startBeat) < 1e-6)
        {
            // Find matching off and remove both
            if (auto* off = clip->sequence.getEventPointer(i)->noteOffObject)
            {
                for (int j = 0; j < clip->sequence.getNumEvents(); ++j)
                    if (clip->sequence.getEventPointer(j) == off)
                    {
                        clip->sequence.deleteEvent(j, false);
                        break;
                    }
            }
            clip->sequence.deleteEvent(i, false);
            clip->sequence.updateMatchedPairs();
            return true;
        }
    }
    return false;
}

// ---------------------------------------------------------------------------
// DeleteNotesCmd
// ---------------------------------------------------------------------------
DeleteNotesCmd::DeleteNotesCmd(MidiClip* c, std::vector<NoteSnap> s)
    : clip(c), snaps(std::move(s)) {}

bool DeleteNotesCmd::perform()
{
    if (clip == nullptr) return false;
    // Match by (pitch, start) and remove on+off pair
    for (auto& s : snaps)
    {
        for (int i = clip->sequence.getNumEvents() - 1; i >= 0; --i)
        {
            auto& m = clip->sequence.getEventPointer(i)->message;
            if (m.isNoteOn()
                && m.getNoteNumber() == s.pitch
                && std::abs(m.getTimeStamp() - s.start) < 1e-6)
            {
                if (auto* off = clip->sequence.getEventPointer(i)->noteOffObject)
                    for (int j = 0; j < clip->sequence.getNumEvents(); ++j)
                        if (clip->sequence.getEventPointer(j) == off)
                        { clip->sequence.deleteEvent(j, false); break; }
                clip->sequence.deleteEvent(i, false);
                break;
            }
        }
    }
    clip->sequence.updateMatchedPairs();
    return true;
}

bool DeleteNotesCmd::undo()
{
    if (clip == nullptr) return false;
    for (auto& s : snaps)
    {
        auto on  = juce::MidiMessage::noteOn(s.ch, s.pitch, (juce::uint8)s.vel);
        auto off = juce::MidiMessage::noteOff(s.ch, s.pitch);
        on.setTimeStamp(s.start);
        off.setTimeStamp(s.start + s.dur);
        clip->sequence.addEvent(on);
        clip->sequence.addEvent(off);
    }
    clip->sequence.updateMatchedPairs();
    return true;
}

// ---------------------------------------------------------------------------
// AddClipCmd
// ---------------------------------------------------------------------------
AddClipCmd::AddClipCmd(Track* t, double sb, double lb)
    : track(t), startBeat(sb), lengthBeats(lb) {}

bool AddClipCmd::perform()
{
    if (track == nullptr) return false;
    MidiClip c;
    c.startBeat = startBeat;
    c.lengthBeats = lengthBeats;
    track->clips.push_back(std::move(c));
    return true;
}

bool AddClipCmd::undo()
{
    if (track == nullptr) return false;
    for (auto it = track->clips.begin(); it != track->clips.end(); ++it)
        if (std::abs(it->startBeat - startBeat) < 1e-6
            && std::abs(it->lengthBeats - lengthBeats) < 1e-6
            && it->sequence.getNumEvents() == 0)
        {
            track->clips.erase(it);
            return true;
        }
    return false;
}

// ---------------------------------------------------------------------------
// ChangeVelocityCmd (Z2)
// ---------------------------------------------------------------------------
ChangeVelocityCmd::ChangeVelocityCmd(MidiClip* c, std::vector<VelChange> v)
    : clip(c), changes(std::move(v)) {}

void ChangeVelocityCmd::apply(bool toAfter)
{
    if (clip == nullptr) return;
    auto& seq = clip->sequence;
    for (auto& v : changes)
    {
        const int newVel = toAfter ? v.afterVel : v.beforeVel;
        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            auto* e = seq.getEventPointer(i);
            if (! e->message.isNoteOn()) continue;
            if (e->message.getNoteNumber() != v.pitch) continue;
            if (std::abs(e->message.getTimeStamp() - v.start) > 1e-6) continue;
            auto m = juce::MidiMessage::noteOn(v.ch, v.pitch, (juce::uint8)newVel);
            m.setTimeStamp(v.start);
            e->message = m;
            break;
        }
    }
}

bool ChangeVelocityCmd::perform() { apply(true);  return true; }
bool ChangeVelocityCmd::undo()    { apply(false); return true; }

// ---------------------------------------------------------------------------
// MoveNotesCmd (Y2)
// ---------------------------------------------------------------------------
MoveNotesCmd::MoveNotesCmd(MidiClip* c, std::vector<Change> ch)
    : clip(c), changes(std::move(ch)) {}

void MoveNotesCmd::applyState(bool toAfter)
{
    if (clip == nullptr) return;
    auto& seq = clip->sequence;

    // BB2 — per-Cmd consumed set so the same seq event is never rewritten
    // twice (guards against velocity/channel collision on overlapping notes).
    std::vector<bool> consumed(seq.getNumEvents(), false);
    int applied = 0, missed = 0;

    for (auto& c : changes)
    {
        const int   fromPitch = toAfter ? c.beforePitch : c.afterPitch;
        const double fromStart = toAfter ? c.beforeStart : c.afterStart;
        const int   toPitch   = toAfter ? c.afterPitch  : c.beforePitch;
        const double toStart   = toAfter ? c.afterStart  : c.beforeStart;
        const double toDur     = toAfter ? c.afterDur    : c.beforeDur;

        bool found = false;
        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            if (consumed[i]) continue;
            auto* evt = seq.getEventPointer(i);
            if (! evt->message.isNoteOn()) continue;
            if (evt->message.getNoteNumber() != fromPitch) continue;
            if (std::abs(evt->message.getTimeStamp() - fromStart) > 1e-6) continue;

            auto newOn = juce::MidiMessage::noteOn(c.channel, toPitch, (juce::uint8)c.velocity);
            newOn.setTimeStamp(toStart);
            evt->message = newOn;

            if (evt->noteOffObject != nullptr)
            {
                auto newOff = juce::MidiMessage::noteOff(c.channel, toPitch);
                newOff.setTimeStamp(toStart + toDur);
                evt->noteOffObject->message = newOff;
            }
            consumed[i] = true;
            found = true;
            ++applied;
            break;
        }
        if (! found) ++missed;
    }
    seq.updateMatchedPairs();

    if (missed > 0)
        DBG("MoveNotesCmd: " << missed << "/" << (applied + missed)
            << " notes not matched during apply");
}

bool MoveNotesCmd::perform() { applyState(true);  return true; }
bool MoveNotesCmd::undo()    { applyState(false); return true; }

// ---------------------------------------------------------------------------
// DeleteTrackCmd
// ---------------------------------------------------------------------------
DeleteTrackCmd::DeleteTrackCmd(TrackModel& m, int id)
    : model(m), trackId(id) {}

bool DeleteTrackCmd::perform()
{
    auto* t = model.getTrack(trackId);
    if (t == nullptr) return false;
    // NOTE: plugin AudioPluginInstance objects are NOT snapshotted here —
    // undoing a track deletion will restore the metadata (PluginSlot) but
    // not the live plugin state. Caller must re-instantiate if needed.
    // Scope kept minimal for Sprint 5.
    snapshot.id          = t->id;
    snapshot.name        = t->name;
    snapshot.colour      = t->colour;
    snapshot.volume      = t->volume;
    snapshot.pan         = t->pan;
    snapshot.mute        = t->mute;
    snapshot.solo        = t->solo;
    snapshot.armed       = t->armed;
    snapshot.midiChannel = t->midiChannel;
    snapshot.outputBusId = t->outputBusId;
    snapshot.clips       = t->clips;
    snapshot.audioClips  = t->audioClips;
    snapshot.plugins     = t->plugins;
    snapshot.sends       = t->sends;
    snapshot.automation  = t->automation;
    hadSnapshot = true;

    model.removeTrack(trackId);
    return true;
}

bool DeleteTrackCmd::undo()
{
    if (! hadSnapshot) return false;
    auto& t = model.addTrack(snapshot.name);
    t.colour      = snapshot.colour;
    t.volume      = snapshot.volume;
    t.pan         = snapshot.pan;
    t.mute        = snapshot.mute;
    t.solo        = snapshot.solo;
    t.armed       = snapshot.armed;
    t.midiChannel = snapshot.midiChannel;
    t.outputBusId = snapshot.outputBusId;
    t.clips       = snapshot.clips;
    t.audioClips  = snapshot.audioClips;
    t.plugins     = snapshot.plugins;
    t.sends       = snapshot.sends;
    t.automation  = snapshot.automation;
    return true;
}

// DD6 — TrackPropertyCmd
TrackPropertyCmd::TrackPropertyCmd(TrackModel& m, int tid, Prop p,
                                   float bf, float af, bool bb, bool ab)
    : model(m), trackId(tid), prop(p), beforeF(bf), afterF(af), beforeB(bb), afterB(ab)
{}

void TrackPropertyCmd::apply(float fval, bool bval)
{
    auto* t = model.getTrack(trackId);
    if (t == nullptr) return;
    switch (prop)
    {
        case Volume: t->volume = fval; break;
        case Pan:    t->pan    = fval; break;
        case Mute:   t->mute   = bval; break;
        case Solo:   t->solo   = bval; break;
    }
}

bool TrackPropertyCmd::perform()
{
    apply(afterF, afterB);
    return true;
}

bool TrackPropertyCmd::undo()
{
    apply(beforeF, beforeB);
    return true;
}

// EE4 — MoveClipCmd
MoveClipCmd::MoveClipCmd(MidiClip* c, double bs, double bl, double as, double al)
    : clip(c), beforeStart(bs), beforeLen(bl), afterStart(as), afterLen(al) {}

bool MoveClipCmd::perform()
{
    if (clip == nullptr) return false;
    clip->startBeat = afterStart;
    clip->lengthBeats = afterLen;
    return true;
}

bool MoveClipCmd::undo()
{
    if (clip == nullptr) return false;
    clip->startBeat = beforeStart;
    clip->lengthBeats = beforeLen;
    return true;
}

// ---------------------------------------------------------------------------
// PPP2 — AudioClipEditCmd
// ---------------------------------------------------------------------------
AudioClipEditCmd::AudioClipEditCmd(AudioClip* c, Snap b, Snap a)
    : clip(c), before(b), after(a) {}

AudioClipEditCmd::Snap AudioClipEditCmd::snapshot(const AudioClip& c)
{
    Snap s;
    s.startBeat           = c.startBeat;
    s.lengthBeats         = c.lengthBeats;
    s.sourceOffsetSamples = c.sourceOffsetSamples;
    s.fadeInBeats         = c.fadeInBeats;
    s.fadeOutBeats        = c.fadeOutBeats;
    return s;
}

void AudioClipEditCmd::apply(const Snap& s)
{
    if (clip == nullptr) return;
    clip->startBeat           = s.startBeat;
    clip->lengthBeats         = s.lengthBeats;
    clip->sourceOffsetSamples = s.sourceOffsetSamples;
    clip->fadeInBeats         = s.fadeInBeats;
    clip->fadeOutBeats        = s.fadeOutBeats;
}

bool AudioClipEditCmd::perform() { if (!clip) return false; apply(after);  return true; }
bool AudioClipEditCmd::undo()    { if (!clip) return false; apply(before); return true; }
