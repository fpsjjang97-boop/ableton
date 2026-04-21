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

# Sprint 47 재빌드 대응 — MSVC 가 소스를 cp949 로 해석해 한글 리터럴에서
# C2001/C1075 발생. 전역 /utf-8 로 source/execution charset 을 UTF-8 로 고정.
if (MSVC)
    add_compile_options(/utf-8)
endif()

# -----------------------------------------------------------------------------
# JUCE dependency
# -----------------------------------------------------------------------------
add_subdirectory(external/JUCE EXCLUDE_FROM_ALL)

# -----------------------------------------------------------------------------
# Sprint 49 NNN1 — r8brain-free-src (high-quality resampler, opt-in)
# -----------------------------------------------------------------------------
# When MIDIGPTDAW_WITH_R8BRAIN=ON is passed at CMake configure time, we
# FetchContent the library (MIT license) and compile it as a static lib.
# Default OFF so existing builds are not forced to reach the internet.
#
# Override the fetch with -DFETCHCONTENT_SOURCE_DIR_R8BRAIN_FREE_SRC=... to
# point at a local clone (air-gapped environments).
option(MIDIGPTDAW_WITH_R8BRAIN
       "Fetch r8brain-free-src and enable it as a ResamplerWrapper backend" OFF)

if(MIDIGPTDAW_WITH_R8BRAIN)
    include(FetchContent)
    FetchContent_Declare(
        r8brain_free_src
        GIT_REPOSITORY https://github.com/avaneev/r8brain-free-src.git
        # Pinned to 7.1 (NNN2). Note: Avaneev changed tag format from
        # "version-X.Y" (6.x) to just "X.Y" (7.x). If bumping, verify the
        # r8b::CDSPResampler24 ctor signature hasn't drifted (NNN1 pimpl
        # relies on it).
        GIT_TAG        7.1
    )
    FetchContent_MakeAvailable(r8brain_free_src)

    add_library(midigpt_r8brain STATIC
        ${r8brain_free_src_SOURCE_DIR}/r8bbase.cpp
        ${r8brain_free_src_SOURCE_DIR}/pffft.cpp
    )
    target_include_directories(midigpt_r8brain PUBLIC ${r8brain_free_src_SOURCE_DIR})
    message(STATUS "MidiGPTDAW: r8brain-free-src enabled at ${r8brain_free_src_SOURCE_DIR}")
endif()

# -----------------------------------------------------------------------------
# Sprint 50 OOO1 — RubberBand v4 (pitch/time stretch, opt-in, GPL!)
# -----------------------------------------------------------------------------
# **Licence warning**: RubberBand is licensed GPL-v2+ OR commercial
# (Breakfast Quay). Enabling this option links the core library into
# MidiGPTDAW and the resulting binary inherits GPL terms for distribution,
# unless a commercial licence is purchased. Default OFF keeps the build
# licence-clean.
#
# Override fetch: -DFETCHCONTENT_SOURCE_DIR_RUBBERBAND_SRC=/path/to/local
option(MIDIGPTDAW_WITH_RUBBERBAND
       "Fetch breakfastquay/rubberband and enable TimeStretchWrapper (GPL!)" OFF)

if(MIDIGPTDAW_WITH_RUBBERBAND)
    # Tamp down rubberband's auxiliary targets before pulling it in.
    set(RUBBERBAND_BUILD_SHARED OFF CACHE BOOL "" FORCE)
    set(RUBBERBAND_BUILD_CLI     OFF CACHE BOOL "" FORCE)
    set(RUBBERBAND_BUILD_VAMP    OFF CACHE BOOL "" FORCE)
    set(RUBBERBAND_BUILD_LADSPA  OFF CACHE BOOL "" FORCE)
    set(RUBBERBAND_BUILD_TESTS   OFF CACHE BOOL "" FORCE)

    include(FetchContent)
    FetchContent_Declare(
        rubberband_src
        GIT_REPOSITORY https://github.com/breakfastquay/rubberband.git
        GIT_TAG        v4.0.0
    )
    FetchContent_MakeAvailable(rubberband_src)
    message(STATUS "MidiGPTDAW: rubberband v4 enabled (expected target: rubberband)")
endif()

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
    Source/Core/Groove.h

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
    # Sprint 49 NNN1 — backend-agnostic resampler wrapper (scaffold only)
    Source/Audio/ResamplerWrapper.h
    Source/Audio/ResamplerWrapper.cpp
    # Sprint 50 OOO1 — pitch/time stretch wrapper (RubberBand opt-in)
    Source/Audio/TimeStretchWrapper.h
    Source/Audio/TimeStretchWrapper.cpp
    # Sprint 50 OOO2 — offline AudioClip stretch helper
    Source/Audio/ClipStretchUtil.h
    Source/Audio/ClipStretchUtil.cpp

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
    Source/UI/ScoreView.h
    Source/UI/ScoreView.cpp
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
    juce::juce_opengl              # Sprint 51 — OpenGL attach bypasses paint cascade bug
    juce::juce_dsp
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)

# NNN1 — opt-in r8brain backend link (default OFF → no-op).
if(MIDIGPTDAW_WITH_R8BRAIN)
    target_compile_definitions(MidiGPTDAW PRIVATE MIDIGPTDAW_WITH_R8BRAIN=1)
    target_link_libraries(MidiGPTDAW PRIVATE midigpt_r8brain)
endif()

# OOO1 — opt-in rubberband backend link (default OFF → no-op).
if(MIDIGPTDAW_WITH_RUBBERBAND)
    target_compile_definitions(MidiGPTDAW PRIVATE MIDIGPTDAW_WITH_RUBBERBAND=1)
    # rubberband's CMake normally exports a target named "rubberband".
    # If a future tag bump changes this (e.g. rubberband::rubberband), fix
    # here — a hard CMake error on unknown target beats silent disabling.
    target_link_libraries(MidiGPTDAW PRIVATE rubberband)
endif()

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

    # Plugin-local UI components (Sprint 33 XX1~XX6, Sprint 34 YY3, Sprint 35 ZZ3~ZZ5,
    # Sprint 36 AAA3/AAA4)
    Source/PluginUI/MiniPianoRoll.h
    Source/PluginUI/MiniPianoRoll.cpp
    Source/PluginUI/PresetManager.h
    Source/PluginUI/I18n.h
    Source/PluginUI/PluginLogger.h
    Source/PluginUI/TutorialOverlay.h
    Source/PluginUI/SampleGallery.h
    Source/PluginUI/PerformanceHUD.h

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

# =============================================================================
# Sprint 49 NNN3 — ResamplerWrapper test harness (opt-in)
# -----------------------------------------------------------------------------
# Console app that validates ResamplerWrapper correctness + THD+N quality.
# Run manually after building to gate future swaps of the resampler backend
# (Lagrange default / r8brain / future WindowedSinc). Opt-in so the main
# DAW/plugin build isn't slowed by this extra target.
# =============================================================================
option(MIDIGPTDAW_BUILD_TESTS "Build ResamplerWrapper + future test targets" OFF)

if(MIDIGPTDAW_BUILD_TESTS)
    juce_add_console_app(MidiGPTResamplerTest
        PRODUCT_NAME "MidiGPTResamplerTest"
    )
    target_sources(MidiGPTResamplerTest PRIVATE
        Source/Audio/ResamplerWrapper.h
        Source/Audio/ResamplerWrapper.cpp
        tests/test_resampler.cpp
    )
    target_link_libraries(MidiGPTResamplerTest PRIVATE
        juce::juce_audio_basics
        juce::juce_audio_formats
        juce::juce_core
        juce::juce_dsp
        juce::juce_recommended_config_flags
        juce::juce_recommended_warning_flags
    )
    target_compile_features(MidiGPTResamplerTest PRIVATE cxx_std_17)

    if(MIDIGPTDAW_WITH_R8BRAIN)
        target_compile_definitions(MidiGPTResamplerTest PRIVATE MIDIGPTDAW_WITH_R8BRAIN=1)
        target_link_libraries(MidiGPTResamplerTest PRIVATE midigpt_r8brain)
    endif()

    # Sprint 50 OOO5 — TimeStretchWrapper test harness
    juce_add_console_app(MidiGPTStretchTest
        PRODUCT_NAME "MidiGPTStretchTest"
    )
    target_sources(MidiGPTStretchTest PRIVATE
        Source/Audio/TimeStretchWrapper.h
        Source/Audio/TimeStretchWrapper.cpp
        Source/Audio/ClipStretchUtil.h
        Source/Audio/ClipStretchUtil.cpp
        tests/test_stretch.cpp
    )
    target_link_libraries(MidiGPTStretchTest PRIVATE
        juce::juce_audio_basics
        juce::juce_core
        juce::juce_recommended_config_flags
        juce::juce_recommended_warning_flags
    )
    target_compile_features(MidiGPTStretchTest PRIVATE cxx_std_17)

    if(MIDIGPTDAW_WITH_RUBBERBAND)
        target_compile_definitions(MidiGPTStretchTest PRIVATE MIDIGPTDAW_WITH_RUBBERBAND=1)
        target_link_libraries(MidiGPTStretchTest PRIVATE rubberband)
    endif()
endif()
