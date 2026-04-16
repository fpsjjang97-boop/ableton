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
#include <map>

class MidiEngine
{
public:
    MidiEngine() = default;

    void setTrackModel(TrackModel* model) { trackModel = model; }

    // Transport
    void setTempo(double bpm)          { tempo = bpm; }
    double getTempo() const            { return tempoAt(positionBeats); } // BB5
    void setTimeSignature(int num, int den) { tsNum = num; tsDen = den; }

    // BB5 — tempo map (beat → bpm). Empty map = constant `tempo`.
    void addTempoChange(double atBeat, double bpm) { tempoMap[atBeat] = bpm; }
    void clearTempoMap() { tempoMap.clear(); }
    const std::map<double, double>& getTempoMap() const { return tempoMap; }
    double tempoAt(double beat) const
    {
        if (tempoMap.empty()) return tempo;
        auto it = tempoMap.upper_bound(beat);
        if (it == tempoMap.begin()) return tempo;
        return (--it)->second;
    }

    // BB6 — time-signature map (beat → (num,den)). Empty = tsNum/tsDen fixed.
    struct TimeSig { int num; int den; };
    void addTimeSignatureChange(double atBeat, int num, int den)
    { tsMap[atBeat] = { num, den }; }
    void clearTimeSignatureMap() { tsMap.clear(); }
    const std::map<double, TimeSig>& getTimeSignatureMap() const { return tsMap; }
    TimeSig timeSigAt(double beat) const
    {
        if (tsMap.empty()) return { tsNum, tsDen };
        auto it = tsMap.upper_bound(beat);
        if (it == tsMap.begin()) return { tsNum, tsDen };
        return (--it)->second;
    }

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
    double getLoopStart() const { return loopStart; }
    double getLoopEnd()   const { return loopEnd; }

    // GG1 — punch in/out region
    void setPunchRegion(double inBeat, double outBeat)
    { punchIn = inBeat; punchOut = outBeat; punchEnabled = (outBeat > inBeat); }
    void setPunchEnabled(bool on) { punchEnabled = on; }
    bool isPunchEnabled() const   { return punchEnabled; }
    double getPunchIn()  const    { return punchIn; }
    double getPunchOut() const    { return punchOut; }
    bool isInPunchRegion(double beat) const
    { return !punchEnabled || (beat >= punchIn && beat < punchOut); }

    // EE6 — Markers (named positions)
    struct Marker { double beat; juce::String name; juce::Colour colour { juce::Colours::yellow }; };
    void addMarker(double beat, const juce::String& name)
    { markers.push_back({ beat, name }); std::sort(markers.begin(), markers.end(),
        [](auto& a, auto& b) { return a.beat < b.beat; }); }
    void removeMarker(int idx) { if (idx >= 0 && idx < (int)markers.size()) markers.erase(markers.begin() + idx); }
    void clearMarkers() { markers.clear(); }
    std::vector<Marker>& getMarkers() { return markers; }
    const std::vector<Marker>& getMarkers() const { return markers; }

    /** Call from the audio callback. Fills midiBuffer with events
        for the current block. Advances the playhead. */
    void processBlock(int numSamples, double sampleRate,
                      juce::MidiBuffer& midiBuffer)
    {
        midiBuffer.clear();
        if (!playing || trackModel == nullptr || sampleRate <= 0.0)
            return;

        // BB5 — use tempo at current position (tempo map aware)
        const double effTempo = tempoAt(positionBeats);
        double beatsPerSample = effTempo / (60.0 * sampleRate);
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
    std::map<double, double>   tempoMap;  // BB5
    std::map<double, TimeSig>  tsMap;     // BB6

    bool playing { false };
    double positionBeats { 0.0 };

    bool looping { false };
    double loopStart { 0.0 };
    double loopEnd { 0.0 };

    // GG1
    bool   punchEnabled { false };
    double punchIn  { 0.0 };
    double punchOut { 0.0 };

    std::vector<Marker> markers; // EE6
};
