cmake_minimum_required(VERSION 3.22)
project(MidiAIWorkstation VERSION 1.0.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# JUCE path
set(JUCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../JUCE")
add_subdirectory(${JUCE_DIR} ${CMAKE_CURRENT_BINARY_DIR}/JUCE)

juce_add_gui_app(MidiAIWorkstation
    PRODUCT_NAME "MIDI AI Workstation"
    COMPANY_NAME "MidiAI"
    BUNDLE_ID "com.midiai.workstation"
    VERSION "1.0.0"
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT TRUE
)

target_sources(MidiAIWorkstation PRIVATE
    # Core
    Source/Core/AudioEngine.cpp
    Source/Core/AudioEngine.h
    Source/Core/MidiEngine.cpp
    Source/Core/MidiEngine.h
    Source/Core/ProjectState.cpp
    Source/Core/ProjectState.h
    Source/Core/TrackProcessor.cpp
    Source/Core/TrackProcessor.h
    Source/Core/SynthEngine.cpp
    Source/Core/SynthEngine.h

    # UI
    Source/UI/MainWindow.cpp
    Source/UI/MainWindow.h
    Source/UI/TransportBar.cpp
    Source/UI/TransportBar.h
    Source/UI/SessionView.cpp
    Source/UI/SessionView.h
    Source/UI/PianoRoll.cpp
    Source/UI/PianoRoll.h
    Source/UI/MixerPanel.cpp
    Source/UI/MixerPanel.h
    Source/UI/FileBrowser.cpp
    Source/UI/FileBrowser.h
    Source/UI/DetailView.cpp
    Source/UI/DetailView.h
    Source/UI/LookAndFeel.cpp
    Source/UI/LookAndFeel.h

    # AI
    Source/AI/AIEngine.cpp
    Source/AI/AIEngine.h

    # Main
    Source/Main.cpp
)

target_compile_definitions(MidiAIWorkstation PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_DISPLAY_SPLASH_SCREEN=0
    JUCE_REPORT_APP_USAGE=0
    JUCE_MODAL_LOOPS_PERMITTED=1
    JUCE_VST3_CAN_REPLACE_VST2=0
    DONT_SET_USING_JUCE_NAMESPACE=0
)

target_link_libraries(MidiAIWorkstation PRIVATE
    juce::juce_audio_basics
    juce::juce_audio_devices
    juce::juce_audio_formats
    juce::juce_audio_processors
    juce::juce_audio_utils
    juce::juce_core
    juce::juce_data_structures
    juce::juce_events
    juce::juce_graphics
    juce::juce_gui_basics
    juce::juce_gui_extra
)

juce_generate_juce_header(MidiAIWorkstation)

# === Audio Beep Test ===
juce_add_console_app(BeepTest
    PRODUCT_NAME "BeepTest"
    NEEDS_MIDI_OUTPUT TRUE
)
target_sources(BeepTest PRIVATE Source/auto_test.cpp)
target_compile_definitions(BeepTest PRIVATE
    JUCE_WEB_BROWSER=0
    JUCE_USE_CURL=0
    JUCE_DISPLAY_SPLASH_SCREEN=0
    DONT_SET_USING_JUCE_NAMESPACE=0
)
target_link_libraries(BeepTest PRIVATE
    juce::juce_audio_basics
    juce::juce_audio_devices
    juce::juce_audio_formats
    juce::juce_audio_utils
    juce::juce_core
    juce::juce_events
)
juce_generate_juce_header(BeepTest)
