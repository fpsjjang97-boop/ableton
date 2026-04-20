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
#include "../Audio/ResamplerWrapper.h"
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

    // DD1 — audio input recording
    void setAudioRecordingTrack(int trackId) { audioRecTrackId = trackId; }
    int  getAudioRecordingTrack() const      { return audioRecTrackId; }
    bool isAudioRecording() const            { return audioRecTrackId >= 0 && midiEngine.isPlaying(); }
    void finalizeAudioRecording();  // call after stop to create AudioClip

    // PPP4 — input monitoring. When true, the armed track's audio input is
    // mixed into that track's buffer so it flows through the track's
    // plugins, fader and sends and becomes audible at the master.
    //
    // **Default OFF** — speaker+mic setups (laptop, studio monitors without
    // headphones) create a feedback loop the first time the user arms a
    // track. Users who want monitoring flip it on explicitly via
    // setInputMonitoring() or a future UI toggle.
    void setInputMonitoring(bool on) { inputMonitoringOn = on; }
    bool isInputMonitoring() const   { return inputMonitoringOn; }

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

    // OO4 — per-track VU levels
    float getTrackVuL(int trackId) const { auto it = trackVuL.find(trackId); return it != trackVuL.end() ? it->second : 0.0f; }
    float getTrackVuR(int trackId) const { auto it = trackVuR.find(trackId); return it != trackVuR.end() ? it->second : 0.0f; }

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

public:
    SynthEngine& getOrCreateTrackSynth(int trackId); // EE2 needs public access

    /** T1 — GUI-thread alloc of a track's SynthEngine. Call right after
     *  TrackModel::addTrack() so the audio thread never has to allocate. */
    void prebuildTrackSynth(int trackId);

private:

    // Reusable buffers for per-track + per-bus processing (allocated in
    // audioDeviceAboutToStart, cleared every block to avoid alloc on RT thread)
    juce::AudioBuffer<float> trackBuf;
    juce::AudioBuffer<float> busAccum;
    std::map<int, juce::AudioBuffer<float>> busBuffers; // S4 — per-bus accumulators

    // NNN6 — shared AudioClip resampler + scratch. Sized in
    // audioDeviceAboutToStart so the audio thread never allocates. Each
    // clip prepare()s with its own effective source SR per block; the
    // underlying Lagrange state is reset per prepare() so clips don't
    // cross-contaminate.
    midigpt_daw::ResamplerWrapper clipResampler;
    juce::AudioBuffer<float>      clipScratch;

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

    // OO4 — per-track VU state
    std::map<int, float> trackVuL, trackVuR;

    // W6/X1 — MIDI input recording. Device-thread callback pushes into a
    // MidiMessageCollector; audio thread drains on each block and writes to
    // the current clip. This removes the device-thread race on
    // MidiMessageSequence.
    int recordingTrackId { -1 };
    juce::MidiMessageCollector midiInputCollector;
    double midiInputLatencyMs { 0.0 }; // AA4

    // DD1 — audio recording state
    int audioRecTrackId { -1 };
    juce::AudioBuffer<float> audioRecBuffer;  // accumulates input samples
    int audioRecWritePos { 0 };
    double audioRecStartBeat { 0.0 };

    // PPP4 — live input monitoring flag (see setInputMonitoring). Default
    // off to avoid feedback loops on integrated speaker/mic hardware; UI
    // caller opts in.
    bool inputMonitoringOn { false };

    // Test beep on play start
    int testBeepSamples { 0 };
    static constexpr int testBeepLength = 22050; // 0.5s at 44100

    void generateMetronomeClick(float* left, float* right, int numSamples);

    // FF2 — PDC: per-track delay compensation buffers
    std::map<int, juce::AudioBuffer<float>> pdcDelayBuffers;
    std::map<int, int> pdcDelaySamples;
    int maxPluginLatency { 0 };
    void updatePDC();
};
