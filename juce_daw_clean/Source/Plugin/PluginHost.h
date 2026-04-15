/*
 * MidiGPT DAW — PluginHost (Sprint 1 skeleton)
 *
 * VST3 plugin scanning + instantiation. Owns the JUCE format manager and a
 * KnownPluginList. Returns AudioPluginInstance unique_ptrs to callers; the
 * AudioEngine / Track is responsible for routing audio through them.
 *
 * IMPORTANT (rules/05-bug-history.md):
 *   - Pattern G: every error path returns a non-empty errorOut string AND a
 *     null instance. Caller must check both.
 *   - Pattern A: PluginDescription is keyed by createIdentifierString(); this
 *     is the *only* identity the rest of the app uses to refer to a plugin.
 *
 * STATUS:
 *   Sprint 1 — header + minimal scan/instantiate. UI for plugin browser
 *   (FileSearchPathListComponent + KnownPluginListComponent), per-track FX
 *   chain processBlock integration, and project-level plugin state save/load
 *   are deferred to Sprint 2.
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <memory>

class PluginHost
{
public:
    PluginHost();
    ~PluginHost();

    /** Scan the given directories for VST3 plugins (recursive).
     *  Adds discovered types to knownPlugins. Idempotent — re-scanning the
     *  same path will not duplicate entries (KnownPluginList dedupes).
     *  @returns the number of newly-added plugin types. */
    int scanForPlugins(const juce::FileSearchPath& paths);

    juce::KnownPluginList&       getKnownList()       { return knownPlugins; }
    const juce::KnownPluginList& getKnownList() const { return knownPlugins; }

    /** Instantiate a plugin instance.
     *  @param desc        from KnownPluginList (or createIdentifierString reverse-lookup)
     *  @param sampleRate  current device sample rate
     *  @param blockSize   current device block size
     *  @param errorOut    populated with error message on failure
     *  @returns nullptr on failure; valid instance with prepareToPlay already
     *           called on success. */
    std::unique_ptr<juce::AudioPluginInstance> instantiate(
        const juce::PluginDescription& desc,
        double sampleRate,
        int blockSize,
        juce::String& errorOut);

    /** Reverse-lookup PluginDescription from the identifier string used in
     *  serialised projects. Returns nullopt if not in knownPlugins (project
     *  references a plugin that is no longer installed). */
    std::unique_ptr<juce::PluginDescription> findByIdentifier(const juce::String& identifierString) const;

    /** Default plugin search paths for the host platform.
     *  Windows: %ProgramFiles%\Common Files\VST3 + user-level VST3 folders. */
    static juce::FileSearchPath getDefaultVst3SearchPaths();

private:
    juce::AudioPluginFormatManager formatManager;
    juce::KnownPluginList          knownPlugins;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginHost)
};
