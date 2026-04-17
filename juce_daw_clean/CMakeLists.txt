# MidiGPT DAW — Standalone JUCE Application
#
# Self-contained DAW with built-in MidiGPT LLM integration.
# NOT a plugin — this IS the host. Can load external VST3/CLAP plugins.
#
# References:
#   https://github.com/juce-framework/JUCE/blob/master/examples/CMake/GuiApp/CMakeLists.txt
#   https://docs.juce.com/master/tutorial_create_projucer_basic_plugin.html
#
# NO references to Cubase binaries or Ghidra output.

cmake_minimum_required(VERSION 3.22)

project(MidiGPTDAW VERSION 0.1.0)

# -----------------------------------------------------------------------------
# JUCE dependency
# -----------------------------------------------------------------------------
add_subdirectory(external/JUCE EXCLUDE_FROM_ALL)

# -----------------------------------------------------------------------------
# Application target
# -----------------------------------------------------------------------------
juce_add_gui_app(MidiGPTDAW
    PRODUCT_NAME            "MidiGPT"
    COMPANY_NAME            "MidiGPT"
    BUNDLE_ID               "com.midigpt.daw"
    ICON_BIG                ""
    ICON_SMALL              ""
    NEEDS_CURL              FALSE
    NEEDS_WEB_BROWSER       FALSE
)

# -----------------------------------------------------------------------------
# Sources
# -----------------------------------------------------------------------------
target_sources(MidiGPTDAW PRIVATE
    # Entry point
    Source/Main.cpp
    Source/MainWindow.h
    Source/MainWindow.cpp

    # Core engine
    Source/Core/AudioEngine.h
    Source/Core/AudioEngine.cpp
    Source/Core/MidiEngine.h
    Source/Core/MidiEngine.cpp
    Source/Core/SynthEngine.h
    Source/Core/SynthEngine.cpp
    Source/Core/TrackModel.h
    Source/Core/TrackModel.cpp

    # UI components
    Source/UI/LookAndFeel.h
    Source/UI/LookAndFeel.cpp
    Source/UI/TransportBar.h
    Source/UI/TransportBar.cpp
    Source/UI/ArrangementView.h
    Source/UI/ArrangementView.cpp
    Source/UI/PianoRoll.h
    Source/UI/PianoRoll.cpp
    Source/UI/MixerPanel.h
    Source/UI/MixerPanel.cpp

    # AI integration
    Source/AI/AIBridge.h
    Source/AI/AIBridge.cpp
    Source/AI/AIPanel.h
    Source/AI/AIPanel.cpp

    # Plugin hosting (F2/F3)
    Source/Plugin/PluginHost.h
    Source/Plugin/PluginHost.cpp
    Source/Plugin/PluginBrowser.h
    Source/Plugin/PluginBrowser.cpp
    Source/Plugin/PluginEditorWindow.h
    Source/Plugin/PluginEditorWindow.cpp
    Source/Plugin/TrackPluginChain.h

    # Audio (F5/F6)
    Source/Audio/AudioClip.h
    Source/Audio/OfflineRenderer.h
    Source/Audio/OfflineRenderer.cpp

    # Routing (F7)
    Source/Core/Bus.h

    # Automation (F4 + S5)
    Source/Automation/AutomationLane.h
    Source/Automation/AutomationEditor.h
    Source/Automation/AutomationEditor.cpp

    # Commands / Undo (V1)
    Source/Command/EditCommands.h
    Source/Command/EditCommands.cpp

    # New editors (F8/F9)
    Source/UI/CCLane.h
    Source/UI/CCLane.cpp
    Source/UI/StepSeqView.h
    Source/UI/StepSeqView.cpp
)

# -----------------------------------------------------------------------------
# Compile definitions
# -----------------------------------------------------------------------------
target_compile_definitions(MidiGPTDAW PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_APPLICATION_NAME_STRING="$<TARGET_PROPERTY:MidiGPTDAW,JUCE_PRODUCT_NAME>"
    JUCE_APPLICATION_VERSION_STRING="$<TARGET_PROPERTY:MidiGPTDAW,JUCE_VERSION>"
    JUCE_PLUGINHOST_VST3=1
    JUCE_PLUGINHOST_LV2=0
)

# -----------------------------------------------------------------------------
# JUCE modules
# -----------------------------------------------------------------------------
target_link_libraries(MidiGPTDAW PRIVATE
    juce::juce_audio_utils
    juce::juce_audio_processors
    juce::juce_audio_formats
    juce::juce_audio_devices
    juce::juce_gui_extra
    juce::juce_dsp
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)

# -----------------------------------------------------------------------------
# C++ standard
# -----------------------------------------------------------------------------
target_compile_features(MidiGPTDAW PRIVATE cxx_std_17)

# =============================================================================
# VST3 Plugin target — MidiGPTPlugin
# -----------------------------------------------------------------------------
# Host-agnostic VST3 + Standalone plugin that runs INSIDE a DAW (Cubase,
# Ableton Live, Reaper, etc.). Shares Source/AI/AIBridge.* with the
# standalone app — both talk to the same inference_server.py over HTTP.
#
# Sprint 32 WW1 (2026-04-17): target activated. Before this the plugin
# source files existed but were orphaned — not compiled by any target.
# =============================================================================
juce_add_plugin(MidiGPTPlugin
    PRODUCT_NAME            "MidiGPT"
    COMPANY_NAME            "MidiGPT"
    BUNDLE_ID               "com.midigpt.plugin"
    PLUGIN_MANUFACTURER_CODE Mgpt
    PLUGIN_CODE             MGpt
    FORMATS                 VST3 Standalone
    IS_MIDI_EFFECT          TRUE
    IS_SYNTH                FALSE
    NEEDS_MIDI_INPUT        TRUE
    NEEDS_MIDI_OUTPUT       TRUE
    EDITOR_WANTS_KEYBOARD_FOCUS TRUE
    COPY_PLUGIN_AFTER_BUILD FALSE
    VST3_CATEGORIES         "Fx" "Tools"
)

target_sources(MidiGPTPlugin PRIVATE
    Source/PluginProcessor.h
    Source/PluginProcessor.cpp
    Source/PluginEditor.h
    Source/PluginEditor.cpp

    # Plugin-local UI components (Sprint 33 XX1~XX6, Sprint 34 YY3, Sprint 35 ZZ3~ZZ5)
    Source/PluginUI/MiniPianoRoll.h
    Source/PluginUI/MiniPianoRoll.cpp
    Source/PluginUI/PresetManager.h
    Source/PluginUI/I18n.h
    Source/PluginUI/PluginLogger.h
    Source/PluginUI/TutorialOverlay.h

    # Shared with standalone — HTTP client to inference_server.py
    Source/AI/AIBridge.h
    Source/AI/AIBridge.cpp
)

target_compile_definitions(MidiGPTPlugin PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
)

target_link_libraries(MidiGPTPlugin PRIVATE
    juce::juce_audio_basics
    juce::juce_audio_processors
    juce::juce_audio_formats
    juce::juce_core
    juce::juce_events
    juce::juce_gui_extra
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)

target_compile_features(MidiGPTPlugin PRIVATE cxx_std_17)
