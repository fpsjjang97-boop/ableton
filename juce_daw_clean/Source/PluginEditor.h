/*
 * MidiGPT VST3 Plugin — PluginEditor
 *
 * Clean room JUCE AudioProcessorEditor (plugin window UI).
 *
 * Sprint 32 WW5 (2026-04-17): connected to PluginProcessor status callback
 * for error / progress feedback + periodic server health polling.
 * Sprint 33 XX2-XX6 (2026-04-17):
 *   XX2 MiniPianoRoll dual pane (input vs last generated)
 *   XX3 Export MIDI button (FileChooser → lastGenerated.mid)
 *   XX4 Style change → async LoRA hot-swap
 *   XX5 Progress overlay + Cancel button during generation
 *   XX6 Server Info dialog (/status endpoint dump)
 *
 * References (public sources only):
 *   - JUCE Tutorial: Build a plug-in editor
 *     https://juce.com/learn/tutorials/juce-tutorial-plugin-editor/
 *   - JUCE FileChooser (async): https://docs.juce.com/master/classFileChooser.html
 *   - JUCE Component class: https://docs.juce.com/master/classComponent.html
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>
#include "PluginProcessor.h"
#include "AI/AIBridge.h"
#include "PluginUI/MiniPianoRoll.h"

class MidiGPTEditor : public juce::AudioProcessorEditor,
                       private juce::Timer
{
public:
    explicit MidiGPTEditor (MidiGPTProcessor&);
    ~MidiGPTEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;

private:
    // juce::Timer — server health polling + piano roll refresh
    void timerCallback() override;

    void handleStatus (MidiGPTProcessor::GenerationStatus st, juce::String msg);
    void refreshPianoRolls();       // repaint input/output panes from current state

    // --- XX3 Export MIDI --------------------------------------------------
    void onExportMidi();
    std::unique_ptr<juce::FileChooser> activeChooser;

    // --- XX4 Style change → LoRA hot-swap ---------------------------------
    void onStyleChanged();
    juce::String currentLoraName { "base" };
    bool         loraLoadInFlight { false };

    // --- XX5 Progress overlay ---------------------------------------------
    void setGenerationInFlight (bool inFlight);
    bool generationInFlight { false };

    // --- XX6 Server Info --------------------------------------------------
    void onServerInfo();

    MidiGPTProcessor& processorRef;

    // Local AIBridge instance used ONLY for health polling / server info /
    // LoRA hot-swap (not generation itself — the processor owns that
    // bridge). Keeping them separate means a long LoRA swap doesn't queue
    // behind a pending generation on the same worker thread.
    AIBridge healthBridge;
    bool     serverConnected { false };

    // --- Piano roll panes (XX1 + XX2) -----------------------------------
    MiniPianoRoll inputRoll;
    MiniPianoRoll outputRoll;

    // --- Controls -----------------------------------------------------------
    juce::TextButton generateButton { "Generate Variation" };
    juce::TextButton cancelButton   { "Cancel" };
    juce::TextButton clearButton    { "Clear Input" };
    juce::TextButton exportButton   { "Export MIDI" };
    juce::TextButton infoButton     { "Server Info" };

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
