/*
 * MidiGPT VST3 Plugin — PluginProcessor
 *
 * Clean room JUCE AudioProcessor implementation for the MidiGPT LLM.
 * This is a MIDI Effect plugin: MIDI in → MidiGPT LLM → MIDI out.
 *
 * References (public sources only):
 *   - JUCE AudioProcessor API docs: https://docs.juce.com/master/classAudioProcessor.html
 *   - JUCE AudioPluginHost example: https://github.com/juce-framework/JUCE/tree/master/extras/AudioPluginHost
 *   - VST3 SDK public docs: https://steinbergmedia.github.io/vst3_dev_portal/
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

class MidiGPTProcessor : public juce::AudioProcessor
{
public:
    MidiGPTProcessor();
    ~MidiGPTProcessor() override = default;

    // -------------------------------------------------------------------------
    // AudioProcessor lifecycle
    // -------------------------------------------------------------------------
    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    bool isBusesLayoutSupported (const BusesLayout& layouts) const override;

    // -------------------------------------------------------------------------
    // Plugin info
    // -------------------------------------------------------------------------
    const juce::String getName() const override { return "MidiGPT"; }
    bool acceptsMidi() const override  { return true; }
    bool producesMidi() const override { return true; }
    bool isMidiEffect() const override { return true; }
    double getTailLengthSeconds() const override { return 0.0; }

    // -------------------------------------------------------------------------
    // Program / preset handling (VST3 requires at least 1 program)
    // -------------------------------------------------------------------------
    int getNumPrograms() override        { return 1; }
    int getCurrentProgram() override     { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}

    // -------------------------------------------------------------------------
    // State save / restore (host saves these into the project file)
    // -------------------------------------------------------------------------
    void getStateInformation (juce::MemoryBlock& destData) override;
    void setStateInformation (const void* data, int sizeInBytes) override;

    // -------------------------------------------------------------------------
    // Editor
    // -------------------------------------------------------------------------
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    // -------------------------------------------------------------------------
    // MidiGPT-specific API (called from editor)
    // -------------------------------------------------------------------------
    /** Kick off a variation generation request.
     *  Currently a stub; will be wired to the Python HTTP inference server. */
    void requestVariation();

    /** Returns the last generated MIDI sequence (populated by inference).
     *  Empty until the first successful generation. */
    const juce::MidiMessageSequence& getLastGenerated() const { return lastGenerated; }

    // Public parameter tree (exposed to host automation)
    juce::AudioProcessorValueTreeState parameters;

private:
    // Internal MIDI buffer for captured input (used as inference prompt)
    juce::MidiMessageSequence capturedInput;
    juce::MidiMessageSequence lastGenerated;

    static juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MidiGPTProcessor)
};
