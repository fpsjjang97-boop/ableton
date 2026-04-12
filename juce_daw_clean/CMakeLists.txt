# MidiGPT VST3 Plugin — Clean Room
#
# Based on JUCE official CMake template for audio plugins.
# References:
#   https://github.com/juce-framework/JUCE/blob/master/examples/CMake/AudioPlugin/CMakeLists.txt
#   https://juce.com/learn/tutorials/juce-cmake-repository-usage
#
# NO references to Cubase, Steinberg proprietary code, or Ghidra output.

cmake_minimum_required(VERSION 3.22)

project(MidiGPTPlugin VERSION 0.1.0)

# -----------------------------------------------------------------------------
# JUCE dependency
# -----------------------------------------------------------------------------
# Option A (recommended): add JUCE as a git submodule at external/JUCE
#   git submodule add https://github.com/juce-framework/JUCE external/JUCE
# Option B: use find_package(JUCE) if JUCE is installed system-wide
add_subdirectory(external/JUCE EXCLUDE_FROM_ALL)

# -----------------------------------------------------------------------------
# Plugin target
# -----------------------------------------------------------------------------
juce_add_plugin(MidiGPTPlugin
    COMPANY_NAME                "MidiGPT"
    IS_SYNTH                    FALSE
    NEEDS_MIDI_INPUT            TRUE
    NEEDS_MIDI_OUTPUT           TRUE
    IS_MIDI_EFFECT              TRUE        # MIDI-in, MIDI-out plugin (no audio processing)
    EDITOR_WANTS_KEYBOARD_FOCUS TRUE
    COPY_PLUGIN_AFTER_BUILD     TRUE        # auto-copy to user plugin folder
    PLUGIN_MANUFACTURER_CODE    MGpt        # 4-char code (unique)
    PLUGIN_CODE                 MgPl        # 4-char code (unique)
    FORMATS                     VST3 Standalone
    PRODUCT_NAME                "MidiGPT"
)

# -----------------------------------------------------------------------------
# Sources
# -----------------------------------------------------------------------------
target_sources(MidiGPTPlugin PRIVATE
    Source/PluginProcessor.h
    Source/PluginProcessor.cpp
    Source/PluginEditor.h
    Source/PluginEditor.cpp
    Source/AIBridge.h
    Source/AIBridge.cpp
)

# -----------------------------------------------------------------------------
# Compile definitions — JUCE standard flags
# -----------------------------------------------------------------------------
target_compile_definitions(MidiGPTPlugin PUBLIC
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_VST3_CAN_REPLACE_VST2=0
)

# -----------------------------------------------------------------------------
# JUCE modules
# -----------------------------------------------------------------------------
target_link_libraries(MidiGPTPlugin PRIVATE
    juce::juce_audio_utils
    juce::juce_audio_processors
    juce::juce_gui_extra
    juce::juce_dsp
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)

# -----------------------------------------------------------------------------
# C++ standard
# -----------------------------------------------------------------------------
target_compile_features(MidiGPTPlugin PRIVATE cxx_std_17)
