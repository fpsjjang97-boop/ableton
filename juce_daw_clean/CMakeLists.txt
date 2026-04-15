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
