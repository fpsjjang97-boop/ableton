/*
 * MidiGPT DAW — Bus
 *
 * Mixer bus model. Tracks route to a Bus by id; buses sum and route to
 * either the master or another bus (one level of subgrouping for now).
 *
 * Bus 0 is reserved for Master. User-created buses start at id 1.
 *
 * Sprint scope: data model + AudioEngine bus mixer wiring (master + 1 level
 * of subgroups). Send/aux routing and post-fader sends arrive in Sprint 4.
 */

#pragma once

#include <juce_graphics/juce_graphics.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include <vector>
#include <algorithm>
#include <functional>

struct Bus
{
    int          id        { 0 };
    juce::String name      { "Master" };
    juce::Colour colour    { juce::Colours::lightgrey };
    float        volume    { 1.0f };
    float        pan       { 0.0f };
    bool         mute      { false };
    int          outputBusId { 0 }; // 0 = master (the master itself ignores this)

    // FX chain metadata (mirrors PluginSlot from TrackModel.h)
    // Actual instances live in TrackPluginChain keyed by negative ids:
    //   key = -(busId + 100)  to avoid collision with track ids.
    // Empty in Sprint 1 — wiring deferred.
};

class BusModel
{
public:
    BusModel()
    {
        Bus master;
        master.id = 0;
        master.name = "Master";
        master.colour = juce::Colour(0xFFE0E0E0);
        buses.push_back(master);
    }

    Bus& addBus(const juce::String& name)
    {
        Bus b;
        b.id = nextId++;
        b.name = name;
        buses.push_back(b);
        return buses.back();
    }

    void removeBus(int id)
    {
        if (id == 0) return; // protect master
        buses.erase(std::remove_if(buses.begin(), buses.end(),
            [id](const Bus& b) { return b.id == id; }), buses.end());

        // Y3 — clear orphan references in *other* buses (tracks cleaned up
        // externally via onBusRemoved callback since BusModel doesn't own
        // TrackModel).
        for (auto& b : buses)
            if (b.outputBusId == id) b.outputBusId = 0;

        if (onBusRemoved) onBusRemoved(id);
    }

    /** Y3 — fired after a bus is removed. Caller wires this to rewrite
     *  Track::outputBusId / Track::sends referring to the removed id. */
    std::function<void(int removedBusId)> onBusRemoved;

    Bus* getBus(int id)
    {
        for (auto& b : buses) if (b.id == id) return &b;
        return nullptr;
    }

    std::vector<Bus>& getBuses() { return buses; }
    const std::vector<Bus>& getBuses() const { return buses; }

private:
    std::vector<Bus> buses;
    int nextId { 1 };
};
