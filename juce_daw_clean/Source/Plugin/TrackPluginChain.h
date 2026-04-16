/*
 * MidiGPT DAW — TrackPluginChain
 *
 * Owns AudioPluginInstance objects for one track (and for the master bus).
 * Track data model (TrackModel.h) holds *metadata* (PluginSlot) only;
 * actual processing instances live here so Track stays copy-friendly.
 *
 * Lookup keyed by trackId (int). Master bus uses key = -1.
 *
 * Audio thread API: process(buffer, sampleRate, blockSize)
 *   Iterates instances in slot order, processes in place. bypass flag in
 *   PluginSlot is honoured by skipping that slot.
 *
 * Lifecycle:
 *   - Add: addPlugin(trackId, slotIndex, std::move(instance))
 *   - Remove: removePlugin(trackId, slotIndex)
 *   - Rebuild on prepareToPlay(sr, blockSize) when device changes
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include "../Core/TrackModel.h"
#include <map>
#include <vector>
#include <memory>

class TrackPluginChain
{
public:
    TrackPluginChain() = default;

    /** Add a prepared plugin instance to a track at slot index. */
    void addPlugin(int trackId, int slotIndex,
                   std::unique_ptr<juce::AudioPluginInstance> inst)
    {
        if (inst == nullptr) return;
        auto& chain = chains[trackId];
        if (slotIndex < 0 || slotIndex > (int)chain.size())
            slotIndex = (int)chain.size();
        chain.insert(chain.begin() + slotIndex, std::move(inst));
    }

    void removePlugin(int trackId, int slotIndex)
    {
        auto it = chains.find(trackId);
        if (it == chains.end()) return;
        auto& chain = it->second;
        if (slotIndex < 0 || slotIndex >= (int)chain.size()) return;
        chain.erase(chain.begin() + slotIndex);
    }

    void clearTrack(int trackId) { chains.erase(trackId); }
    void clearAll()              { chains.clear(); }

    int getNumPlugins(int trackId) const
    {
        auto it = chains.find(trackId);
        return it == chains.end() ? 0 : (int)it->second.size();
    }

    juce::AudioPluginInstance* getPlugin(int trackId, int slotIndex)
    {
        auto it = chains.find(trackId);
        if (it == chains.end()) return nullptr;
        if (slotIndex < 0 || slotIndex >= (int)it->second.size()) return nullptr;
        return it->second[slotIndex].get();
    }

    /** Re-prepare every instance for a new sample rate / block size.
     *  Called from AudioEngine::audioDeviceAboutToStart. */
    void prepareAll(double sampleRate, int blockSize)
    {
        for (auto& [id, chain] : chains)
            for (auto& inst : chain)
                if (inst != nullptr)
                    inst->prepareToPlay(sampleRate, blockSize);
    }

    /** FF2 — total latency in samples for a given track's plugin chain. */
    int getTotalLatency(int trackId) const
    {
        auto it = chains.find(trackId);
        if (it == chains.end()) return 0;
        int total = 0;
        for (auto& inst : it->second)
            if (inst != nullptr)
                total += inst->getLatencySamples();
        return total;
    }

    /** Process a single track's audio buffer through its plugin chain,
     *  honouring per-slot bypass from the Track's PluginSlot vector.
     *  midiBuf may be empty for pure FX. */
    void processTrack(int trackId, const Track& trackMeta,
                      juce::AudioBuffer<float>& buffer,
                      juce::MidiBuffer& midiBuf)
    {
        auto it = chains.find(trackId);
        if (it == chains.end()) return;
        auto& chain = it->second;

        const int numSlots = juce::jmin((int)chain.size(),
                                        (int)trackMeta.plugins.size());
        for (int s = 0; s < numSlots; ++s)
        {
            if (trackMeta.plugins[s].bypass) continue;
            if (chain[s] == nullptr) continue;
            chain[s]->processBlock(buffer, midiBuf);
        }
    }

private:
    // trackId (int, -1 for master) → ordered plugin instances
    std::map<int, std::vector<std::unique_ptr<juce::AudioPluginInstance>>> chains;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackPluginChain)
};
