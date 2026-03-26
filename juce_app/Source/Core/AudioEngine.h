/*
  ==============================================================================

    AudioEngine.h
    MIDI AI Workstation - Core Audio Engine

    Real-time audio engine managing transport, track mixing, synthesis,
    and metronome generation.

  ==============================================================================
*/

#pragma once
#include <JuceHeader.h>

class TrackProcessor;
class SynthEngine;

//==============================================================================
/**
    Main audio engine for the MIDI AI Workstation.

    Manages real-time audio processing, transport control, track mixing,
    and metronome click generation. Implements juce::AudioSource so it can
    be driven by an AudioSourcePlayer connected to the device manager.
*/
class AudioEngine : public juce::AudioSource
{
public:
    AudioEngine();
    ~AudioEngine() override;

    //==========================================================================
    // AudioSource interface
    void prepareToPlay (int samplesPerBlock, double sampleRate) override;
    void releaseResources() override;
    void getNextAudioBlock (const juce::AudioSourceChannelInfo& bufferToFill) override;

    //==========================================================================
    // Transport
    void play();
    void stop();
    void pause();
    void setPosition (double positionInBeats);
    double getPositionInBeats() const;
    double getPositionInSeconds() const;
    bool isPlaying() const;

    //==========================================================================
    // Settings
    void setBPM (double bpm);
    double getBPM() const;
    void setTimeSignature (int numerator, int denominator);
    void setLooping (bool shouldLoop, double loopStartBeat, double loopEndBeat);

    //==========================================================================
    // Track management
    void addTrack (std::shared_ptr<TrackProcessor> track);
    void removeTrack (int index);
    int getNumTracks() const;
    TrackProcessor* getTrack (int index) const;

    //==========================================================================
    // Master
    void setMasterVolume (float volume);
    float getMasterVolume() const;

    //==========================================================================
    // MIDI output
    void setMidiOutput (juce::MidiOutput* output);

    //==========================================================================
    // Metronome
    void setMetronomeEnabled (bool enabled);
    bool isMetronomeEnabled() const;

private:
    double sampleRate      = 44100.0;
    int    samplesPerBlock  = 512;

    std::atomic<double> bpm { 120.0 };
    std::atomic<double> currentPositionInSamples { 0.0 };
    std::atomic<bool>   playing { false };

    std::atomic<bool>   looping { false };
    std::atomic<double> loopStartBeat { 0.0 };
    std::atomic<double> loopEndBeat { 16.0 };

    int timeSignatureNum = 4;
    int timeSignatureDen = 4;

    std::atomic<float> masterVolume { 1.0f };
    std::atomic<bool>  metronomeEnabled { false };

    std::vector<std::shared_ptr<TrackProcessor>> tracks;
    std::unique_ptr<SynthEngine> synthEngine;
    juce::MidiOutput* midiOutput = nullptr;

    juce::CriticalSection lock;

    // Metronome click state
    int metronomeSamplesRemaining = 0;
    float metronomePhase          = 0.0f;
    float metronomeFrequency      = 1000.0f; // Hz for click
    bool  metronomeAccent         = false;

    //==========================================================================
    // Helpers
    double beatsToSamples (double beats) const;
    double samplesToBeats (double samples) const;
    void   generateMetronomeClick (juce::AudioBuffer<float>& buffer,
                                   int startSample, int numSamples,
                                   double blockStartBeat, double blockEndBeat);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AudioEngine)
};
