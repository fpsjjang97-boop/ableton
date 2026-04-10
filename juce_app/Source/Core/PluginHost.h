/*
  ==============================================================================

    PluginHost.h
    MIDI AI Workstation - VST3/CLAP Plugin Host Module

    Loads, manages, and renders VST3/CLAP audio plugins.
    Each track can have an instrument plugin + insert effect chain.

    Phase 1 scope:
      - Scan VST3 paths for available plugins
      - Load/unload plugin instances
      - Route MIDI to instrument plugins
      - Render audio from plugins into the track mix bus
      - Basic preset management (save/load plugin state)

  ==============================================================================
*/

#pragma once
#include <JuceHeader.h>

//==============================================================================
/**
    Represents a single loaded plugin instance with its editor and state.
*/
struct PluginSlot
{
    std::unique_ptr<juce::AudioPluginInstance> instance;
    juce::String pluginName;
    juce::String pluginFormat;   // "VST3", "CLAP", etc.
    bool         isBypassed = false;

    /** Save current plugin state to memory block. */
    juce::MemoryBlock getState() const
    {
        juce::MemoryBlock state;
        if (instance != nullptr)
            instance->getStateInformation (state);
        return state;
    }

    /** Restore plugin state from memory block. */
    void setState (const juce::MemoryBlock& state)
    {
        if (instance != nullptr)
            instance->setStateInformation (state.getData(), (int) state.getSize());
    }
};

//==============================================================================
/**
    Manages VST3/CLAP plugin scanning, loading, and audio rendering.

    Typical usage per track:
      1. loadInstrument(trackIndex, pluginDescription)  — synth/sampler
      2. addInsert(trackIndex, pluginDescription)        — effect chain
      3. processBlock() called from AudioEngine          — renders audio
*/
class PluginHost
{
public:
    PluginHost();
    ~PluginHost();

    //==========================================================================
    // Scanning
    //==========================================================================

    /** Scan default VST3 directories and return list of found plugins. */
    void scanForPlugins();

    /** Get the list of available plugins found by the last scan. */
    const juce::KnownPluginList& getKnownPlugins() const  { return knownPlugins; }

    /** Get plugin descriptions matching a name substring (case-insensitive). */
    juce::Array<juce::PluginDescription> findPlugins (const juce::String& nameFilter) const;

    /** Add custom scan path. */
    void addScanPath (const juce::File& path);

    /** Get default VST3 scan paths for this platform. */
    static juce::StringArray getDefaultScanPaths();

    //==========================================================================
    // Plugin lifecycle
    //==========================================================================

    /** Load a plugin from description. Returns nullptr on failure.
        errorMessage is filled on failure. */
    std::unique_ptr<PluginSlot> loadPlugin (
        const juce::PluginDescription& desc,
        double sampleRate,
        int blockSize,
        juce::String& errorMessage);

    //==========================================================================
    // Audio processing
    //==========================================================================

    /** Prepare a plugin slot for playback. */
    static void preparePlugin (PluginSlot& slot, double sampleRate, int blockSize);

    /** Process a block of audio through a plugin.
        For instruments: midiMessages should contain the MIDI to render.
        For effects: buffer already contains audio to process. */
    static void processPlugin (PluginSlot& slot,
                               juce::AudioBuffer<float>& buffer,
                               juce::MidiBuffer& midiMessages);

    /** Release plugin resources. */
    static void releasePlugin (PluginSlot& slot);

    //==========================================================================
    // Format manager access
    //==========================================================================
    juce::AudioPluginFormatManager& getFormatManager()  { return formatManager; }

private:
    juce::AudioPluginFormatManager formatManager;
    juce::KnownPluginList          knownPlugins;
    juce::StringArray              customScanPaths;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (PluginHost)
};
