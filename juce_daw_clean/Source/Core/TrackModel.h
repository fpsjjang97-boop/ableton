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
    juce::String name; // MM4 — clip name for display
    juce::MidiMessageSequence sequence;

    /** FF5 — swing amount: 0.0 = straight, 0.5 = full triplet swing. */
    float swing { 0.0f };

    /** KK2 — per-clip colour override. Default (0) = use track colour. */
    juce::Colour colour { 0x00000000 };
    bool hasCustomColour() const { return colour.getAlpha() > 0; }

    /** KK6 — per-clip MIDI channel override. 0 = use track channel. */
    int channel { 0 };

    /** PP4 — clip internal loop. When enabled, the clip content repeats
     *  every loopLengthBeats within the clip's lengthBeats. */
    bool loopEnabled { false };
    double loopLengthBeats { 4.0 };
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
    int userProgram { -1 };    // -1 = use MIDI file programs, 0-127 = override

    // AA6 — folder track hierarchy. parentTrackId == -1 means top-level.
    // A track with any child is a "folder track" (by convention);
    // rendering indents its children in the arrangement view.
    int  parentTrackId { -1 };
    bool isFolder      { false };
    bool collapsed     { false }; // BB1 — hide children in arrangement when true
    bool frozen        { false }; // EE2 — frozen tracks play only their frozenClip

    // FF1 — automation recording mode
    enum class AutoMode { Read, Write, Latch };
    AutoMode autoMode { AutoMode::Read };
    bool inputMonitor { false }; // FF4 — pass audio input to output
    bool overdub      { true };  // HH1 — true=layer on top, false=replace region
    int  displayHeight { 48 };   // HH3 — per-track pixel height in arrangement

    std::vector<MidiClip> clips;

    /** Audio clips (F5). Empty for MIDI-only tracks. */
    std::vector<AudioClip> audioClips;

    /** Routing target. 0 = master bus (default). User buses ≥ 1 (see Bus.h). */
    int outputBusId { 0 };

    /** U3 — Sends (post-fader). level 0..1, busId is send destination. */
    struct Send {
        int busId { 0 }; float level { 0.0f };
        bool preFader { false };  // EE3
        bool sidechain { false }; // KK3 — route to plugin sidechain input
    };
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
            // PP4 — determine how many loop iterations to emit
            int loops = 1;
            if (clip.loopEnabled && clip.loopLengthBeats > 0.0)
                loops = juce::jmax(1, (int)std::ceil(clip.lengthBeats / clip.loopLengthBeats));

            for (int loop = 0; loop < loops; ++loop)
            {
            const double loopOffset = loop * clip.loopLengthBeats;

            for (int i = 0; i < clip.sequence.getNumEvents(); ++i)
            {
                auto msg = clip.sequence.getEventPointer(i)->message;
                double t = msg.getTimeStamp() + loopOffset;
                // PP4 — clip events that exceed lengthBeats
                if (t >= clip.lengthBeats) continue;

                // FF5 — apply swing: shift even-numbered 8th notes
                if (clip.swing > 0.001f)
                {
                    const double eighthNote = 0.5;
                    const int eighthIdx = (int)(t / eighthNote + 0.001);
                    if (eighthIdx % 2 == 1) // odd 8th = "and" beat
                        t += clip.swing * eighthNote;
                }

                msg.setTimeStamp(t + clip.startBeat);
                // KK6 — per-clip channel override
                if (clip.channel > 0 && clip.channel <= 16)
                    msg.setChannel(clip.channel);
                result.addEvent(msg);
            }
            } // PP4 loop iteration
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

    // GG3 — move track from one index to another
    void moveTrack(int fromIdx, int toIdx)
    {
        if (fromIdx < 0 || fromIdx >= (int)tracks.size()) return;
        if (toIdx < 0 || toIdx >= (int)tracks.size()) return;
        if (fromIdx == toIdx) return;
        auto t = std::move(tracks[(size_t)fromIdx]);
        tracks.erase(tracks.begin() + fromIdx);
        // BC1 — adjust toIdx after erase: if from < to, target shifted left by 1
        if (fromIdx < toIdx) --toIdx;
        toIdx = juce::jlimit(0, (int)tracks.size(), toIdx);
        tracks.insert(tracks.begin() + toIdx, std::move(t));
    }

private:
    std::vector<Track> tracks;
    int nextId { 0 };
};
