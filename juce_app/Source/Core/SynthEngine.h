/*
  ==============================================================================
    SynthEngine.h
    MIDI AI Workstation - Multi-timbral Synthesizer Engine

    64-voice polyphonic synthesizer with GM-style program selection.
    Each program has unique waveform, harmonics, ADSR, and filter settings
    to provide realistic instrument sounds without external SoundFonts.
  ==============================================================================
*/
#pragma once
#include <JuceHeader.h>

//==============================================================================
/** Instrument preset defining the timbral characteristics of a GM program. */
struct InstrumentPreset
{
    juce::String name;
    // Harmonic amplitudes (up to 16 partials). fundamental = harmonics[0]
    float harmonics[16] = { 1.0f };
    int   numHarmonics  = 1;
    // ADSR
    float attack  = 0.01f;
    float decay   = 0.3f;
    float sustain = 0.6f;
    float release = 0.5f;
    // Filter
    float filterCutoffMultiplier = 4.0f;  // cutoff = fundamental * this
    float filterResonance        = 0.0f;  // 0-1
    // Waveform type for mixing: 0=sine, 1=saw, 2=square, 3=triangle, 4=noise
    int   waveType = 0;
    // Detune second oscillator (cents)
    float detuneCents = 7.0f;
    // Vibrato
    float vibratoRate  = 0.0f;  // Hz
    float vibratoDepth = 0.0f;  // semitones
    // Stereo width
    float stereoWidth = 0.1f;
};

//==============================================================================
class SynthSound : public juce::SynthesiserSound
{
public:
    SynthSound() = default;
    bool appliesToNote (int) override    { return true; }
    bool appliesToChannel (int) override { return true; }
};

//==============================================================================
class SynthVoice : public juce::SynthesiserVoice
{
public:
    SynthVoice();

    bool canPlaySound (juce::SynthesiserSound* sound) override;

    void startNote (int midiNoteNumber, float velocity,
                    juce::SynthesiserSound* sound,
                    int currentPitchWheelPosition) override;
    void stopNote (float velocity, bool allowTailOff) override;
    void pitchWheelMoved (int newValue) override;
    void controllerMoved (int controllerNumber, int newValue) override;
    void renderNextBlock (juce::AudioBuffer<float>& outputBuffer,
                          int startSample, int numSamples) override;

    void setPreset (const InstrumentPreset* preset) { currentPreset = preset; }

private:
    const InstrumentPreset* currentPreset = nullptr;

    // Oscillator phases (up to 16 harmonics)
    double phases[16]    = {};
    double osc2Phases[16] = {};
    double baseFreq      = 440.0;

    // Envelope
    juce::ADSR adsr;

    // Filter (two-pole state variable)
    float filterLow[2]  = {};
    float filterBand[2] = {};

    // State
    float noteVelocity    = 0.0f;
    int   currentNote     = -1;
    float pitchBendFactor = 1.0f;

    // Vibrato LFO
    double vibratoPhase = 0.0;

    // Generate one sample
    float generateSample (double freq, int channel);
    void  updateFilter (float& sample, int channel, float cutoff, float resonance);

    static double noteToFrequency (double n) {
        return 440.0 * std::pow (2.0, (n - 69.0) / 12.0);
    }
};

//==============================================================================
class SynthEngine
{
public:
    SynthEngine();

    void prepareToPlay (double sampleRate, int samplesPerBlock);
    void renderNextBlock (juce::AudioBuffer<float>& buffer,
                          const juce::MidiBuffer& midiMessages,
                          int startSample, int numSamples);

    void noteOn  (int channel, int noteNumber, float velocity);
    void noteOff (int channel, int noteNumber);
    void allNotesOff();
    void setProgram (int channel, int program);
    void setNumVoices (int numVoices);

    /** Get the preset for a GM program number. */
    static const InstrumentPreset& getPreset (int program);

private:
    juce::Synthesiser synth;
    double currentSampleRate = 44100.0;
    int channelPrograms[16] = {};

    static constexpr int defaultNumVoices = 64;
    static void initPresets();
    static std::vector<InstrumentPreset> presets;
    static bool presetsInitialized;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SynthEngine)
};
