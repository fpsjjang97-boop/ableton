/*
 * MidiGPT DAW — PluginHost implementation (Sprint 1 skeleton)
 */

#include "PluginHost.h"

PluginHost::PluginHost()
{
    // addDefaultFormats picks up VST3 because CMakeLists sets
    // JUCE_PLUGINHOST_VST3=1. AU is macOS-only (auto-disabled on Windows).
    formatManager.addDefaultFormats();
}

PluginHost::~PluginHost() = default;

int PluginHost::scanForPlugins(const juce::FileSearchPath& paths)
{
    const int initialCount = knownPlugins.getNumTypes();

    for (auto* format : formatManager.getFormats())
    {
        if (format == nullptr) continue;

        // PluginDirectoryScanner: recursive scan, one plugin per call to
        // scanNextFile until exhausted. Fourth arg (recursive) = true.
        juce::PluginDirectoryScanner scanner(
            knownPlugins,
            *format,
            paths,
            /*recursive*/ true,
            /*deadMansPedalFile*/ juce::File());

        juce::String pluginBeingScanned;
        while (scanner.scanNextFile(/*dontRescanIfAlreadyInList*/ true,
                                     pluginBeingScanned))
        {
            // Loop until scanner reports done. JUCE handles per-plugin
            // crash isolation through the dead-mans-pedal file mechanism;
            // we pass an empty File which disables that, but VST3 plugins
            // that throw during scan will simply not be added to the list.
        }
    }

    return knownPlugins.getNumTypes() - initialCount;
}

std::unique_ptr<juce::AudioPluginInstance> PluginHost::instantiate(
    const juce::PluginDescription& desc,
    double sampleRate,
    int blockSize,
    juce::String& errorOut)
{
    errorOut.clear();

    auto instance = formatManager.createPluginInstance(desc, sampleRate,
                                                       blockSize, errorOut);
    if (instance == nullptr)
    {
        if (errorOut.isEmpty())
            errorOut = "Plugin failed to load (unknown reason): "
                     + desc.createIdentifierString();
        return nullptr;
    }

    if (errorOut.isNotEmpty())
    {
        // Some formats populate errorOut even on success warnings. Treat
        // a non-null instance with a warning string as success.
        DBG("PluginHost: load warning for "
            << desc.createIdentifierString() << ": " << errorOut);
        errorOut.clear();
    }

    instance->prepareToPlay(sampleRate, blockSize);
    return instance;
}

std::unique_ptr<juce::PluginDescription>
PluginHost::findByIdentifier(const juce::String& identifierString) const
{
    for (auto& desc : knownPlugins.getTypes())
    {
        if (desc.createIdentifierString() == identifierString)
            return std::make_unique<juce::PluginDescription>(desc);
    }
    return nullptr;
}

juce::FileSearchPath PluginHost::getDefaultVst3SearchPaths()
{
    juce::FileSearchPath paths;

   #if JUCE_WINDOWS
    auto programFiles = juce::File::getSpecialLocation(
        juce::File::globalApplicationsDirectory);
    paths.add(programFiles.getChildFile("Common Files\\VST3"));

    auto userVst3 = juce::File::getSpecialLocation(
        juce::File::userApplicationDataDirectory)
            .getChildFile("VST3");
    if (userVst3.isDirectory()) paths.add(userVst3);
   #elif JUCE_MAC
    paths.add(juce::File("/Library/Audio/Plug-Ins/VST3"));
    paths.add(juce::File::getSpecialLocation(juce::File::userHomeDirectory)
                  .getChildFile("Library/Audio/Plug-Ins/VST3"));
   #elif JUCE_LINUX
    paths.add(juce::File("/usr/lib/vst3"));
    paths.add(juce::File("/usr/local/lib/vst3"));
    paths.add(juce::File::getSpecialLocation(juce::File::userHomeDirectory)
                  .getChildFile(".vst3"));
   #endif

    return paths;
}
