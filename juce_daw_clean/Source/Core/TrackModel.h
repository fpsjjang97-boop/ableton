/*
 * MidiGPT DAW - TrackModel
 *
 * Data model for DAW tracks. Each track owns a MIDI sequence,
 * volume/pan/mute/solo state, and an optional plugin chain slot.
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_data_structures/juce_data_structures.h>
#include <juce_graphics/juce_graphics.h>
#include <vector>
#include <memory>

#include "../Audio/AudioClip.h"
#include "../Automation/AutomationLane.h"

struct MidiClip
{
    double startBeat { 0.0 };
    double lengthBeats { 4.0 };
    juce::MidiMessageSequence sequence;
};

/** PluginSlot — *metadata only*. The actual AudioPluginInstance lives in
 *  a separate container owned by AudioEngine (Sprint 2) so that Track
 *  remains copy/move-trivial and TrackModel's std::vector<Track> resize
 *  semantics do not break.
 *
 *  pluginUid is PluginDescription::createIdentifierString() — the single
 *  source of truth for plugin identity (rules/05 패턴 H).
 *
 *  state is the binary state blob from AudioPluginInstance::getStateInformation,
 *  serialised in the project file. Empty on a freshly added plugin.
 */
struct PluginSlot
{
    juce::String displayName;       // human-readable, e.g. "TAL-Reverb-4"
    juce::String pluginUid;          // PluginDescription identifier
    bool         bypass { false };
    juce::MemoryBlock state;          // saved plugin state (binary)
};

struct Track
{
    int id { 0 };
    juce::String name { "Track 1" };
    juce::Colour colour { juce::Colours::dodgerblue };

    float volume { 1.0f };     // 0..1
    float pan    { 0.0f };     // -1..1
    bool  mute   { false };
    bool  solo   { false };
    bool  armed  { false };

    int midiChannel { 1 };     // 1-16

    // AA6 — folder track hierarchy. parentTrackId == -1 means top-level.
    // A track with any child is a "folder track" (by convention);
    // rendering indents its children in the arrangement view.
    int  parentTrackId { -1 };
    bool isFolder      { false };
    bool collapsed     { false }; // BB1 — hide children in arrangement when true

    std::vector<MidiClip> clips;

    /** Audio clips (F5). Empty for MIDI-only tracks. */
    std::vector<AudioClip> audioClips;

    /** Routing target. 0 = master bus (default). User buses ≥ 1 (see Bus.h). */
    int outputBusId { 0 };

    /** U3 — Sends (post-fader). level 0..1, busId is send destination. */
    struct Send { int busId { 0 }; float level { 0.0f }; };
    std::vector<Send> sends;

    /** FX chain *metadata*. Actual AudioPluginInstance objects live in
     *  AudioEngine's TrackPluginChain keyed by Track::id. */
    std::vector<PluginSlot> plugins;

    /** Automation envelopes targeting this track's parameters or its
     *  plugin parameters. See AutomationLane::paramId convention. */
    std::vector<AutomationLane> automation;

    /** Flatten all clips into a single sequence for playback. */
    juce::MidiMessageSequence flattenForPlayback() const
    {
        juce::MidiMessageSequence result;
        for (auto& clip : clips)
        {
            for (int i = 0; i < clip.sequence.getNumEvents(); ++i)
            {
                auto msg = clip.sequence.getEventPointer(i)->message;
                msg.setTimeStamp(msg.getTimeStamp() + clip.startBeat);
                result.addEvent(msg);
            }
        }
        result.sort();
        result.updateMatchedPairs();
        return result;
    }
};

class TrackModel
{
public:
    TrackModel() = default;

    Track& addTrack(const juce::String& name = "")
    {
        Track t;
        t.id = nextId++;
        t.name = name.isEmpty() ? ("Track " + juce::String(t.id + 1)) : name;

        static const juce::Colour palette[] = {
            juce::Colours::dodgerblue, juce::Colours::coral,
            juce::Colours::mediumseagreen, juce::Colours::mediumpurple,
            juce::Colours::goldenrod, juce::Colours::hotpink
        };
        t.colour = palette[t.id % 6];

        tracks.push_back(t);
        return tracks.back();
    }

    void removeTrack(int id)
    {
        tracks.erase(std::remove_if(tracks.begin(), tracks.end(),
            [id](const Track& t) { return t.id == id; }), tracks.end());
    }

    Track* getTrack(int id)
    {
        for (auto& t : tracks)
            if (t.id == id) return &t;
        return nullptr;
    }

    std::vector<Track>& getTracks() { return tracks; }
    const std::vector<Track>& getTracks() const { return tracks; }
    int getNumTracks() const { return static_cast<int>(tracks.size()); }

private:
    std::vector<Track> tracks;
    int nextId { 0 };
};
