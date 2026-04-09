/*
 * MidiGPT VST3 Plugin — PluginEditor
 *
 * Clean room JUCE AudioProcessorEditor (plugin window UI).
 *
 * References (public sources only):
 *   - JUCE Tutorial: Build a plug-in editor
 *     https://juce.com/learn/tutorials/juce-tutorial-plugin-editor/
 *   - JUCE Component class: https://docs.juce.com/master/classComponent.html
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>
#include "PluginProcessor.h"

class MidiGPTEditor : public juce::AudioProcessorEditor
{
public:
    explicit MidiGPTEditor (MidiGPTProcessor&);
    ~MidiGPTEditor() override = default;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    MidiGPTProcessor& processorRef;

    // --- Controls -----------------------------------------------------------
    juce::TextButton generateButton { "Generate Variation" };
    juce::Slider     temperatureSlider;
    juce::Label      temperatureLabel { {}, "Temperature" };
    juce::ComboBox   styleBox;
    juce::Label      styleLabel { {}, "Style" };
    juce::Slider     numVariationsSlider;
    juce::Label      numVariationsLabel { {}, "Variations" };

    juce::Label      statusLabel { {}, "Ready" };

    // --- Parameter attachments (host automation binding) -------------------
    using SliderAttachment = juce::AudioProcessorValueTreeState::SliderAttachment;
    using ComboAttachment  = juce::AudioProcessorValueTreeState::ComboBoxAttachment;

    std::unique_ptr<SliderAttachment> temperatureAttachment;
    std::unique_ptr<SliderAttachment> numVariationsAttachment;
    std::unique_ptr<ComboAttachment>  styleAttachment;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MidiGPTEditor)
};
