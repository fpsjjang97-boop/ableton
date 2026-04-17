/*
 * MidiGPT VST3 Plugin — PluginEditor
 *
 * Clean room JUCE AudioProcessorEditor (plugin window UI).
 *
 * Sprint 32 WW5 (2026-04-17): connected to PluginProcessor status callback
 * for error / progress feedback + periodic server health polling.
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
#include "AI/AIBridge.h"

class MidiGPTEditor : public juce::AudioProcessorEditor,
                       private juce::Timer
{
public:
    explicit MidiGPTEditor (MidiGPTProcessor&);
    ~MidiGPTEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    // juce::Timer — server health polling
    void timerCallback() override;

    void handleStatus (MidiGPTProcessor::GenerationStatus st, juce::String msg);

    MidiGPTProcessor& processorRef;

    // Local AIBridge instance used ONLY for health polling (not generation).
    // The processor owns its own bridge for the data path — we could share it,
    // but keeping them separate avoids locking the generation pipeline just
    // to run /health every second.
    AIBridge healthBridge;
    bool     serverConnected { false };

    // --- Controls -----------------------------------------------------------
    juce::TextButton generateButton { "Generate Variation" };
    juce::TextButton clearButton    { "Clear Input" };
    juce::Slider     temperatureSlider;
    juce::Label      temperatureLabel { {}, "Temperature" };
    juce::ComboBox   styleBox;
    juce::Label      styleLabel { {}, "Style" };
    juce::Slider     numVariationsSlider;
    juce::Label      numVariationsLabel { {}, "Variations" };

    juce::Label      statusLabel { {}, "Ready" };
    juce::Label      serverStatusLabel { {}, "Server: ?" };
    juce::Label      capturedCountLabel { {}, "Captured: 0" };

    // --- Parameter attachments (host automation binding) -------------------
    using SliderAttachment = juce::AudioProcessorValueTreeState::SliderAttachment;
    using ComboAttachment  = juce::AudioProcessorValueTreeState::ComboBoxAttachment;

    std::unique_ptr<SliderAttachment> temperatureAttachment;
    std::unique_ptr<SliderAttachment> numVariationsAttachment;
    std::unique_ptr<ComboAttachment>  styleAttachment;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MidiGPTEditor)
};
