/*
 * MidiGPT DAW — OfflineRenderer
 *
 * Renders the project to a WAV file by running MidiEngine + SynthEngine in
 * non-realtime, repeatedly calling processBlock and writing to disk.
 *
 * Plugin chains (TrackPluginChain) are NOT applied here in this sprint —
 * offline reproduction of plugin chains requires per-track audio routing
 * which is added in F3 audio path. For now the renderer reproduces the
 * "MIDI through SynthEngine" path only. Sprint 2 wires it to the full
 * audio graph.
 */

#pragma once

#include <juce_audio_formats/juce_audio_formats.h>
#include <juce_audio_devices/juce_audio_devices.h>
#include "../Core/MidiEngine.h"
#include "../Core/SynthEngine.h"
#include "../Core/TrackModel.h"
#include "../Plugin/TrackPluginChain.h"
#include "../Core/Bus.h"

class OfflineRenderer
{
public:
    /** Render lengthBeats worth of audio at sampleRate to wavFile.
     *  T3/V3 — full live-path parity when both pluginChains and busModel
     *  are supplied (bus routing + post-fader sends). pluginChains'
     *  instances should already be prepared at sampleRate/blockSize. */
    static bool renderToWav(TrackModel& tracks,
                            double tempoBpm,
                            double lengthBeats,
                            double sampleRate,
                            const juce::File& wavFile,
                            juce::String& errorOut,
                            int blockSize = 512,
                            TrackPluginChain* pluginChains = nullptr,
                            BusModel* busModel = nullptr);
};
