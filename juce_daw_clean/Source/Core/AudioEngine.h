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

class AudioEngine : public juce::AudioIODeviceCallback
{
public:
    AudioEngine();
    ~AudioEngine() override;

    void initialise();
    void shutdown();

    juce::AudioDeviceManager& getDeviceManager() { return deviceManager; }
    MidiEngine& getMidiEngine()                   { return midiEngine; }
    TrackModel& getTrackModel()                   { return trackModel; }
    SynthEngine& getSynthEngine()                 { return synthEngine; }

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

    // VU levels (for mixer display)
    float getVuLeft() const  { return vuLeft; }
    float getVuRight() const { return vuRight; }

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
    SynthEngine synthEngine;

    double currentSampleRate { 44100.0 };
    float masterVolume { 1.0f };
    bool metronomeOn { false };

    float vuLeft { 0.0f };
    float vuRight { 0.0f };

    // Metronome state
    double lastMetronomeBeat { -1.0 };
    int metronomeClickSample { 0 };
    bool metronomeIsDownbeat { false };

    // Test beep on play start
    int testBeepSamples { 0 };
    static constexpr int testBeepLength = 22050; // 0.5s at 44100

    void generateMetronomeClick(float* left, float* right, int numSamples);
};
