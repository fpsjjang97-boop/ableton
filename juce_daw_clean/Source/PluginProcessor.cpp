/*
 * MidiGPT VST3 Plugin — PluginProcessor.cpp
 *
 * Implementation of the MIDI Effect plugin.
 *
 * References (public sources only):
 *   - JUCE Tutorial: MIDI and the JUCE MIDI API
 *     https://juce.com/learn/tutorials/juce-tutorial-handling-midi-events/
 *   - JUCE AudioProcessorValueTreeState docs:
 *     https://docs.juce.com/master/classAudioProcessorValueTreeState.html
 *   - JUCE AudioPluginHost example code
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include "PluginProcessor.h"
#include "PluginEditor.h"

// -----------------------------------------------------------------------------
// Construction
// -----------------------------------------------------------------------------
MidiGPTProcessor::MidiGPTProcessor()
    : AudioProcessor (BusesProperties()),            // no audio buses (MIDI effect)
      parameters (*this, nullptr, "MidiGPT", createParameterLayout())
{
}

juce::AudioProcessorValueTreeState::ParameterLayout
MidiGPTProcessor::createParameterLayout()
{
    using juce::AudioParameterFloat;
    using juce::AudioParameterChoice;
    using juce::AudioParameterInt;
    using juce::NormalisableRange;

    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    // Temperature (creativity)
    params.push_back (std::make_unique<AudioParameterFloat> (
        juce::ParameterID { "temperature", 1 }, "Temperature",
        NormalisableRange<float> (0.5f, 1.5f, 0.01f), 0.9f));

    // Number of candidate variations
    params.push_back (std::make_unique<AudioParameterInt> (
        juce::ParameterID { "numVariations", 1 }, "Variations",
        1, 5, 3));

    // Style (LoRA adapter selection)
    params.push_back (std::make_unique<AudioParameterChoice> (
        juce::ParameterID { "style", 1 }, "Style",
        juce::StringArray { "base", "jazz", "citypop", "metal", "classical" }, 0));

    return { params.begin(), params.end() };
}

// -----------------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------------
void MidiGPTProcessor::prepareToPlay (double /*sampleRate*/, int /*samplesPerBlock*/)
{
    // Nothing to prepare for a pure MIDI effect.
    capturedInput.clear();
}

void MidiGPTProcessor::releaseResources()
{
    // Nothing to release.
}

bool MidiGPTProcessor::isBusesLayoutSupported (const BusesLayout& /*layouts*/) const
{
    // MIDI effect: accept any bus layout (host will route MIDI separately)
    return true;
}

// -----------------------------------------------------------------------------
// Process block — pass-through by default, capture for inference prompt
// -----------------------------------------------------------------------------
void MidiGPTProcessor::processBlock (juce::AudioBuffer<float>& buffer,
                                     juce::MidiBuffer& midiMessages)
{
    // Clear audio (MIDI effect produces no audio)
    buffer.clear();

    // Capture incoming MIDI into our input sequence for future inference.
    for (const auto metadata : midiMessages)
    {
        const auto msg = metadata.getMessage();
        if (msg.isNoteOnOrOff() || msg.isController() || msg.isPitchWheel())
        {
            capturedInput.addEvent (msg);
        }
    }

    // For now, pass through MIDI unchanged. Future: replace with generated MIDI
    // when the user triggers a variation request.
}

// -----------------------------------------------------------------------------
// State save / restore — AudioProcessorValueTreeState handles serialisation
// -----------------------------------------------------------------------------
void MidiGPTProcessor::getStateInformation (juce::MemoryBlock& destData)
{
    auto state = parameters.copyState();
    std::unique_ptr<juce::XmlElement> xml (state.createXml());
    copyXmlToBinary (*xml, destData);
}

void MidiGPTProcessor::setStateInformation (const void* data, int sizeInBytes)
{
    std::unique_ptr<juce::XmlElement> xmlState (getXmlFromBinary (data, sizeInBytes));
    if (xmlState != nullptr && xmlState->hasTagName (parameters.state.getType()))
    {
        parameters.replaceState (juce::ValueTree::fromXml (*xmlState));
    }
}

// -----------------------------------------------------------------------------
// Editor
// -----------------------------------------------------------------------------
juce::AudioProcessorEditor* MidiGPTProcessor::createEditor()
{
    return new MidiGPTEditor (*this);
}

// -----------------------------------------------------------------------------
// Variation generation — currently a stub
// -----------------------------------------------------------------------------
void MidiGPTProcessor::requestVariation()
{
    // TODO (Week 3-4 of sprint): wire to Python HTTP inference server.
    //   1. Serialise capturedInput to MIDI bytes
    //   2. POST to http://127.0.0.1:8765/generate
    //   3. Parse MIDI response into lastGenerated
    //   4. Notify editor to redraw
    //
    // For now this is a no-op so the skeleton builds and loads.
}

// -----------------------------------------------------------------------------
// VST3 / AU factory entry point — JUCE generates the binding
// -----------------------------------------------------------------------------
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new MidiGPTProcessor();
}
