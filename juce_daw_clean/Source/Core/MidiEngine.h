/*
 * MidiGPT DAW - MidiEngine
 *
 * MIDI sequencer: reads TrackModel, outputs MIDI messages in sync
 * with the audio callback timeline. Handles transport position,
 * tempo, time signature, and loop regions.
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include "TrackModel.h"

class MidiEngine
{
public:
    MidiEngine() = default;

    void setTrackModel(TrackModel* model) { trackModel = model; }

    // Transport
    void setTempo(double bpm)          { tempo = bpm; }
    double getTempo() const            { return tempo; }
    void setTimeSignature(int num, int den) { tsNum = num; tsDen = den; }

    void setPlaying(bool shouldPlay)   { playing = shouldPlay; }
    bool isPlaying() const             { return playing; }

    void setPositionBeats(double beats) { positionBeats = beats; }
    double getPositionBeats() const    { return positionBeats; }

    void setLoopRegion(double startBeat, double endBeat)
    {
        loopStart = startBeat;
        loopEnd = endBeat;
        looping = (endBeat > startBeat);
    }
    void setLooping(bool on) { looping = on; }
    bool isLooping() const   { return looping; }

    /** Call from the audio callback. Fills midiBuffer with events
        for the current block. Advances the playhead. */
    void processBlock(int numSamples, double sampleRate,
                      juce::MidiBuffer& midiBuffer)
    {
        midiBuffer.clear();
        if (!playing || trackModel == nullptr || sampleRate <= 0.0)
            return;

        double beatsPerSample = tempo / (60.0 * sampleRate);
        double blockStartBeat = positionBeats;
        double blockEndBeat = positionBeats + numSamples * beatsPerSample;

        // Solo logic: if any track is soloed, mute all non-soloed tracks
    bool anySolo = false;
    for (auto& t : trackModel->getTracks())
        if (t.solo) { anySolo = true; break; }

    for (auto& track : trackModel->getTracks())
        {
            if (track.mute) continue;
            if (anySolo && !track.solo) continue;

            auto seq = track.flattenForPlayback();
            for (int i = 0; i < seq.getNumEvents(); ++i)
            {
                auto* evt = seq.getEventPointer(i);
                double eventBeat = evt->message.getTimeStamp();

                if (eventBeat >= blockStartBeat && eventBeat < blockEndBeat)
                {
                    int sampleOffset = static_cast<int>(
                        (eventBeat - blockStartBeat) / beatsPerSample);
                    sampleOffset = juce::jmax(0, juce::jmin(sampleOffset, numSamples - 1));

                    auto msg = evt->message;
                    msg.setChannel(track.midiChannel);
                    midiBuffer.addEvent(msg, sampleOffset);
                }
            }
        }

        // Advance playhead
        positionBeats = blockEndBeat;

        if (looping && positionBeats >= loopEnd)
            positionBeats = loopStart;
    }

private:
    TrackModel* trackModel { nullptr };
    double tempo { 120.0 };
    int tsNum { 4 }, tsDen { 4 };

    bool playing { false };
    double positionBeats { 0.0 };

    bool looping { false };
    double loopStart { 0.0 };
    double loopEnd { 0.0 };
};
