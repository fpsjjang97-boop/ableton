/*
  ==============================================================================

    PluginHost.cpp
    MIDI AI Workstation - VST3/CLAP Plugin Host Module

  ==============================================================================
*/

#include "PluginHost.h"

//==============================================================================
PluginHost::PluginHost()
{
    // Register built-in plugin formats (VST3, AU on mac, etc.)
    formatManager.addDefaultFormats();
}

PluginHost::~PluginHost() = default;

//==============================================================================
// Scanning
//==============================================================================

juce::StringArray PluginHost::getDefaultScanPaths()
{
    juce::StringArray paths;

#if JUCE_WINDOWS
    // Standard VST3 paths on Windows
    paths.add ("C:\\Program Files\\Common Files\\VST3");
    paths.add ("C:\\Program Files (x86)\\Common Files\\VST3");

    // User-specific VST3 path
    auto userHome = juce::File::getSpecialLocation (juce::File::userHomeDirectory);
    paths.add (userHome.getChildFile (".vst3").getFullPathName());
#elif JUCE_MAC
    paths.add ("/Library/Audio/Plug-Ins/VST3");
    paths.add ("~/Library/Audio/Plug-Ins/VST3");
#elif JUCE_LINUX
    paths.add ("/usr/lib/vst3");
    paths.add ("/usr/local/lib/vst3");
    auto userHome = juce::File::getSpecialLocation (juce::File::userHomeDirectory);
    paths.add (userHome.getChildFile (".vst3").getFullPathName());
#endif

    return paths;
}

void PluginHost::addScanPath (const juce::File& path)
{
    if (path.isDirectory())
        customScanPaths.addIfNotAlreadyThere (path.getFullPathName());
}

void PluginHost::scanForPlugins()
{
    // Collect all scan paths
    auto paths = getDefaultScanPaths();
    paths.addArray (customScanPaths);

    // Scan each format
    for (auto* format : formatManager.getFormats())
    {
        // VST3 format uses file-based scanning
        auto searchPaths = format->getDefaultLocationsToSearch();

        // Add our custom paths to the search
        for (auto& p : paths)
        {
            juce::File dir (p);
            if (dir.isDirectory())
                searchPaths.addIfNotAlreadyThere (dir);
        }

        // Scan — this can take a while for large plugin collections
        juce::PluginDirectoryScanner scanner (
            knownPlugins,
            *format,
            searchPaths,
            true,   // recursive
            juce::File()  // no dead-mans file (could add for crash recovery)
        );

        juce::String pluginName;
        while (scanner.scanNextFile (true, pluginName))
        {
            // Progress callback could go here
            DBG ("Found plugin: " + pluginName);
        }
    }

    DBG ("Plugin scan complete. Found " + juce::String (knownPlugins.getNumTypes()) + " plugins.");
}

juce::Array<juce::PluginDescription> PluginHost::findPlugins (const juce::String& nameFilter) const
{
    juce::Array<juce::PluginDescription> results;

    for (auto& desc : knownPlugins.getTypes())
    {
        if (nameFilter.isEmpty() || desc.name.containsIgnoreCase (nameFilter))
            results.add (desc);
    }

    return results;
}

//==============================================================================
// Plugin lifecycle
//==============================================================================

std::unique_ptr<PluginSlot> PluginHost::loadPlugin (
    const juce::PluginDescription& desc,
    double sampleRate,
    int blockSize,
    juce::String& errorMessage)
{
    auto instance = formatManager.createPluginInstance (
        desc, sampleRate, blockSize, errorMessage);

    if (instance == nullptr)
        return nullptr;

    auto slot = std::make_unique<PluginSlot>();
    slot->pluginName   = desc.name;
    slot->pluginFormat = desc.pluginFormatName;
    slot->instance     = std::move (instance);

    // Prepare for playback
    slot->instance->prepareToPlay (sampleRate, blockSize);
    slot->instance->setNonRealtime (false);

    DBG ("Loaded plugin: " + slot->pluginName + " (" + slot->pluginFormat + ")");
    return slot;
}

//==============================================================================
// Audio processing
//==============================================================================

void PluginHost::preparePlugin (PluginSlot& slot, double sampleRate, int blockSize)
{
    if (slot.instance != nullptr)
    {
        slot.instance->setRateAndBufferSizeDetails (sampleRate, blockSize);
        slot.instance->prepareToPlay (sampleRate, blockSize);
    }
}

void PluginHost::processPlugin (PluginSlot& slot,
                                juce::AudioBuffer<float>& buffer,
                                juce::MidiBuffer& midiMessages)
{
    if (slot.instance == nullptr || slot.isBypassed)
        return;

    slot.instance->processBlock (buffer, midiMessages);
}

void PluginHost::releasePlugin (PluginSlot& slot)
{
    if (slot.instance != nullptr)
        slot.instance->releaseResources();
}
