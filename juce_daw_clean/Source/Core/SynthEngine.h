/*
 * MidiGPT DAW - SynthEngine
 *
 * Built-in polyphonic synthesizer with GM-style presets.
 * Provides immediate audible feedback without external plugins.
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <cmath>
#include <array>

class SynthEngine
{
public:
    SynthEngine();

    void prepare(double sampleRate, int blockSize);
    void renderBlock(juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi);
    void allNotesOff();

    void setProgramForChannel(int channel, int program);

private:
    // ----- Voice -----
    struct Voice
    {
        bool active  { false };
        int  note    { 60 };
        int  channel { 0 };
        float velocity { 0.5f };

        double phase1 { 0.0 };
        double phase2 { 0.0 };
        double phaseInc { 0.0 };

        // ADSR state
        enum Stage { Off, Attack, Decay, Sustain, Release };
        Stage envStage { Off };
        float envLevel { 0.0f };

        // Preset params (copied on note-on)
        float attack  { 0.005f };
        float decay   { 0.1f };
        float sustainLvl { 0.7f };
        float release { 0.15f };
        int   waveType { 0 };    // 0=sine 1=saw 2=square 3=triangle
        float detuneCents { 0.0f };
        float filterCutoffMul { 8.0f };
        float filterQ { 0.3f };

        // Filter state
        float filterLp { 0.0f };
        float filterBp { 0.0f };
    };

    // ----- Preset -----
    struct Preset
    {
        int waveType { 0 };
        float attack { 0.005f };
        float decay  { 0.1f };
        float sustain { 0.7f };
        float release { 0.15f };
        float detuneCents { 0.0f };
        float filterCutoff { 8.0f };
        float filterQ { 0.3f };
        std::array<float, 8> harmonics {{ 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f }};
    };

    static constexpr int maxVoices = 64;
    std::array<Voice, maxVoices> voices;
    std::array<int, 16> channelProgram;

    double sampleRate { 44100.0 };
    std::array<Preset, 128> presets;

    void initPresets();
    void noteOn(int channel, int note, float velocity);
    void noteOff(int channel, int note);
    Voice* findFreeVoice();

    float renderVoiceSample(Voice& v);
    void advanceEnvelope(Voice& v);
};
