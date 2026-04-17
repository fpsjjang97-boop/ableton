/*
 * MidiGPT VST3 Plugin — PresetManager
 *
 * Global (cross-project) parameter-preset persistence for the plugin.
 *
 * Why a separate subsystem? VST3's ``getStateInformation`` already persists
 * parameters PER PROJECT, but most users want to save a "my jazz sound"
 * preset and recall it from any project they open next. This class owns the
 * user-application-data folder side of that.
 *
 * Storage:
 *   <user app data>/MidiGPT/presets/<name>.xml
 * File format: AudioProcessorValueTreeState XML state. Reusing the VTS schema
 * means load is a direct replaceState() and we get free backwards-compat
 * across parameter additions.
 *
 * References (public sources only):
 *   - JUCE File::getSpecialLocation: https://docs.juce.com/master/classFile.html
 *   - JUCE AudioProcessorValueTreeState: https://docs.juce.com/master/classAudioProcessorValueTreeState.html
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_core/juce_core.h>
#include <juce_audio_processors/juce_audio_processors.h>

class PresetManager
{
public:
    explicit PresetManager (juce::AudioProcessorValueTreeState& vtsRef)
        : vts (vtsRef),
          presetsDir (juce::File::getSpecialLocation (juce::File::userApplicationDataDirectory)
                          .getChildFile ("MidiGPT")
                          .getChildFile ("presets"))
    {
        // Create on first use — no-op if already exists.
        presetsDir.createDirectory();
    }

    /** List preset names (filename without .xml), sorted alphabetically. */
    juce::StringArray listPresets() const
    {
        juce::StringArray names;
        if (! presetsDir.isDirectory()) return names;
        juce::Array<juce::File> files;
        presetsDir.findChildFiles (files, juce::File::findFiles, false, "*.xml");
        for (auto& f : files)
            names.add (f.getFileNameWithoutExtension());
        names.sort (/* ignoreCase */ true);
        return names;
    }

    /** Save current parameter state under ``name`` (sanitised).
        Returns true on successful write. */
    bool save (const juce::String& rawName)
    {
        const auto name = sanitise (rawName);
        if (name.isEmpty()) return false;

        auto state = vts.copyState();
        auto xml = std::unique_ptr<juce::XmlElement> (state.createXml());
        if (xml == nullptr) return false;

        auto file = presetsDir.getChildFile (name + ".xml");
        return xml->writeTo (file, {});
    }

    /** Restore parameters from preset ``name``. Returns true if the file
        existed and parsed. Parameters not present in the XML keep current
        values (replaceState semantics). */
    bool load (const juce::String& name)
    {
        auto file = presetsDir.getChildFile (name + ".xml");
        if (! file.existsAsFile()) return false;
        auto xml = juce::parseXML (file);
        if (xml == nullptr) return false;
        if (! xml->hasTagName (vts.state.getType())) return false;

        vts.replaceState (juce::ValueTree::fromXml (*xml));
        return true;
    }

    /** Delete preset file. Returns true if the file existed and was removed. */
    bool remove (const juce::String& name)
    {
        auto file = presetsDir.getChildFile (name + ".xml");
        if (! file.existsAsFile()) return false;
        return file.deleteFile();
    }

    juce::File getPresetsDir() const { return presetsDir; }

private:
    juce::AudioProcessorValueTreeState& vts;
    juce::File presetsDir;

    /** Keep preset names filesystem-safe: strip path separators + control chars.
        Returns an empty string if nothing usable remains. */
    static juce::String sanitise (juce::String s)
    {
        s = s.trim();
        s = s.removeCharacters ("\\/:*?\"<>|\r\n\t");
        if (s.length() > 64) s = s.substring (0, 64);
        return s;
    }

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (PresetManager)
};
