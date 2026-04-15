/*
 * MidiGPT DAW - AudioEngine
 *
 * Central audio/MIDI engine with built-in synthesizer,
 * metronome, and MIDI device output.
 */

#pragma once

#include <juce_audio_devices/juce_audio_devices.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include "MidiEngine.h"
#include "SynthEngine.h"
#include "TrackModel.h"
#include "Bus.h"
#include "../Plugin/TrackPluginChain.h"
#include <map>
#include <memory>

class AudioEngine : public juce::AudioIODeviceCallback,
                    public juce::MidiInputCallback  // W6
{
public:
    AudioEngine();
    ~AudioEngine() override;

    void initialise();
    void shutdown();

    // W6 — MIDI input → selected+armed track
    void handleIncomingMidiMessage(juce::MidiInput* source,
                                   const juce::MidiMessage& message) override;

    void setRecordingTargetTrack(int trackId) { recordingTrackId = trackId; }
    int  getRecordingTargetTrack() const      { return recordingTrackId; }

    /** Y1 — true when a track is armed for record AND transport is playing. */
    bool isRecording() const { return recordingTrackId >= 0 && midiEngine.isPlaying(); }

    /** AA4 — Additional MIDI input port latency in milliseconds.
     *  Added to device driver latency when timestamping recorded events.
     *  Positive values shift events earlier in the timeline. */
    void setMidiInputLatencyMs(double ms) { midiInputLatencyMs = ms; }
    double getMidiInputLatencyMs() const { return midiInputLatencyMs; }

    juce::AudioDeviceManager& getDeviceManager() { return deviceManager; }
    MidiEngine& getMidiEngine()                   { return midiEngine; }
    TrackModel& getTrackModel()                   { return trackModel; }
    SynthEngine& getSynthEngine()                 { return synthEngine; }
    BusModel& getBusModel()                       { return busModel; }
    TrackPluginChain& getPluginChains()           { return pluginChains; }

    // Transport
    void play();
    void stop();
    void togglePlayStop();
    void rewind();
    bool isPlaying() const { return midiEngine.isPlaying(); }

    double getPositionBeats() const { return midiEngine.getPositionBeats(); }
    double getTempo() const         { return midiEngine.getTempo(); }
    void setTempo(double bpm)       { midiEngine.setTempo(bpm); }

    // Master
    void setMasterVolume(float vol) { masterVolume = vol; }
    float getMasterVolume() const   { return masterVolume; }

    // Metronome
    void setMetronome(bool on) { metronomeOn = on; }
    bool getMetronome() const  { return metronomeOn; }

    // Y5 — count-in (pre-roll) bars before transport starts
    void setCountInBars(int bars) { countInBars = juce::jmax(0, bars); }
    int  getCountInBars() const   { return countInBars; }

    // VU levels (for mixer display). RMS-based (W4).
    float getVuLeft() const  { return vuLeft; }
    float getVuRight() const { return vuRight; }
    float getPeakHoldLeft()  const { return peakHoldL; }
    float getPeakHoldRight() const { return peakHoldR; }

    // AudioIODeviceCallback
    void audioDeviceIOCallbackWithContext(const float* const* inputChannelData,
                                         int numInputChannels,
                                         float* const* outputChannelData,
                                         int numOutputChannels,
                                         int numSamples,
                                         const juce::AudioIODeviceCallbackContext& context) override;
    void audioDeviceAboutToStart(juce::AudioIODevice* device) override;
    void audioDeviceStopped() override;

private:
    juce::AudioDeviceManager deviceManager;
    TrackModel trackModel;
    MidiEngine midiEngine;
    SynthEngine synthEngine;          // legacy preview/AI panel; per-track replicas below
    BusModel    busModel;
    TrackPluginChain pluginChains;

    // S1 — per-track SynthEngine instances (avoid voice cross-talk)
    std::map<int, std::unique_ptr<SynthEngine>> trackSynths;
    SynthEngine& getOrCreateTrackSynth(int trackId);

public:
    /** T1 — GUI-thread alloc of a track's SynthEngine. Call right after
     *  TrackModel::addTrack() so the audio thread never has to allocate. */
    void prebuildTrackSynth(int trackId);

private:

    // Reusable buffers for per-track + per-bus processing (allocated in
    // audioDeviceAboutToStart, cleared every block to avoid alloc on RT thread)
    juce::AudioBuffer<float> trackBuf;
    juce::AudioBuffer<float> busAccum;
    std::map<int, juce::AudioBuffer<float>> busBuffers; // S4 — per-bus accumulators

    double currentSampleRate { 44100.0 };
    float masterVolume { 1.0f };
    bool metronomeOn { false };

    // Y5 — count-in state
    int  countInBars { 0 };
    double countInRemainingBeats { 0.0 };  // > 0 = in count-in phase

    float vuLeft { 0.0f };
    float vuRight { 0.0f };
    // W4 — peak hold (1 sec)
    float peakHoldL { 0.0f };
    float peakHoldR { 0.0f };
    int   peakHoldCountdownL { 0 };
    int   peakHoldCountdownR { 0 };

    // Metronome state
    double lastMetronomeBeat { -1.0 };
    int metronomeClickSample { 0 };
    bool metronomeIsDownbeat { false };

    // W6/X1 — MIDI input recording. Device-thread callback pushes into a
    // MidiMessageCollector; audio thread drains on each block and writes to
    // the current clip. This removes the device-thread race on
    // MidiMessageSequence.
    int recordingTrackId { -1 };
    juce::MidiMessageCollector midiInputCollector;
    double midiInputLatencyMs { 0.0 }; // AA4

    // Test beep on play start
    int testBeepSamples { 0 };
    static constexpr int testBeepLength = 22050; // 0.5s at 44100

    void generateMetronomeClick(float* left, float* right, int numSamples);
};
