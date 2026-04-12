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

struct MidiClip
{
    double startBeat { 0.0 };
    double lengthBeats { 4.0 };
    juce::MidiMessageSequence sequence;
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

    std::vector<MidiClip> clips;

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
