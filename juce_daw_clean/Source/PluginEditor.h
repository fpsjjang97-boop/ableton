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
#include "PluginUI/PresetManager.h"
#include "PluginUI/I18n.h"
#include "PluginUI/PluginLogger.h"
#include "PluginUI/TutorialOverlay.h"
#include "PluginUI/SampleGallery.h"
#include "PluginUI/PerformanceHUD.h"

class MidiGPTEditor : public juce::AudioProcessorEditor,
                       public juce::FileDragAndDropTarget,  // YY5 drag-and-drop
                       private juce::Timer,
                       private juce::KeyListener             // YY2 shortcuts
{
public:
    explicit MidiGPTEditor (MidiGPTProcessor&);
    ~MidiGPTEditor() override;

    void paint (juce::Graphics&) override;
    void resized() override;

    // YY5 — FileDragAndDropTarget
    bool isInterestedInFileDrag (const juce::StringArray& files) override;
    void filesDropped (const juce::StringArray& files, int x, int y) override;
    void fileDragEnter (const juce::StringArray&, int, int) override { dragHover = true;  repaint(); }
    void fileDragExit  (const juce::StringArray&)                    override { dragHover = false; repaint(); }

private:
    // juce::Timer — server health polling + piano roll refresh
    void timerCallback() override;

    // juce::KeyListener — YY2 shortcuts
    bool keyPressed (const juce::KeyPress& key, juce::Component* origin) override;

    void handleStatus (MidiGPTProcessor::GenerationStatus st, juce::String msg);
    void refreshPianoRolls();       // repaint input/output panes from current state
    void applyUndoRedoEnable();     // enable/disable undo/redo buttons from history depth

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

    // --- YY3 Preset manager UI -------------------------------------------
    void onSavePreset();
    void onLoadPresetSelected();
    void onDeletePreset();
    void refreshPresetCombo();
    std::unique_ptr<PresetManager> presetManager;

    // --- YY5 drag-and-drop visual feedback -------------------------------
    bool dragHover { false };

    // --- YY6 Theme toggle ------------------------------------------------
    void applyTheme (bool dark);
    bool darkTheme { true };
    std::unique_ptr<juce::LookAndFeel_V4> customLookAndFeel;

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

    // YY4 Undo/Redo buttons
    juce::TextButton undoButton     { "Undo" };
    juce::TextButton redoButton     { "Redo" };

    // YY3 Preset combo + save/delete
    juce::ComboBox   presetBox;
    juce::TextButton savePresetButton   { "Save Preset" };
    juce::TextButton deletePresetButton { "Delete" };

    // YY6 Theme toggle (text reflects CURRENT theme; click cycles)
    juce::TextButton themeButton    { "Dark" };

    // ZZ3 Language toggle (KO ↔ EN)
    juce::TextButton langButton     { "EN" };

    // ZZ5 First-run tutorial overlay + ZZ6 tooltip window
    TutorialOverlay tutorial;
    juce::TooltipWindow tooltipWindow { this, 600 /*ms delay*/ };

    // ZZ5 persistent "tutorial seen" flag via PropertiesFile
    std::unique_ptr<juce::PropertiesFile> settings;
    void applyLanguage();        // re-label all localised controls
    void maybeStartTutorial();   // first-run only

    // AAA2 Report Issue / AAA3 sample gallery / AAA4 performance HUD
    juce::TextButton reportButton   { "Report" };
    juce::TextButton sampleButton   { "Sample" };
    PerformanceHUD   perfHud;
    bool             hudVisible { false };

    void onReportIssue();
    void onLoadSampleMenu();
    void toggleHud();
    void maybeOfferCrashRecovery();    // AAA1 — called during construction

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
