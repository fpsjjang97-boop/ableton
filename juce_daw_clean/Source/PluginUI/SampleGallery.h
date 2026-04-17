/*
 * MidiGPT VST3 Plugin — SampleGallery
 *
 * Sprint 36 AAA3. A tiny manifest-driven "sample library" for first-run
 * users and demo moments: canned MIDI files bundled with the plugin that
 * can be loaded as the current prompt in one click.
 *
 * We deliberately do NOT embed MIDI as juce::BinaryData (C++-compiled
 * blobs make iteration slow and bloat the plugin binary). Instead, on
 * first use we copy sample files from a known repo location into the
 * user's application data dir, and list those from then on.
 *
 * Fallback: if nothing is available (new user, no repo checkout), the
 * gallery list is empty and the UI hides the menu entry.
 */

#pragma once

#include <juce_core/juce_core.h>

class SampleGallery
{
public:
    struct Sample
    {
        juce::String name;          // display label
        juce::File   file;          // .mid on disk
        juce::String description;   // 1-line hint shown in menu
    };

    /** List all samples available to this user. Empty if no bundled or
        user-copied samples exist. */
    static juce::Array<Sample> listSamples()
    {
        juce::Array<Sample> result;
        auto userDir = samplesDir();
        if (! userDir.isDirectory()) return result;

        juce::Array<juce::File> files;
        userDir.findChildFiles (files, juce::File::findFiles, false, "*.mid");
        for (auto& f : files)
        {
            Sample s;
            s.name = f.getFileNameWithoutExtension();
            s.file = f;
            // Sidecar description: "mysample.mid" + "mysample.txt".
            auto txt = f.withFileExtension (".txt");
            s.description = txt.existsAsFile() ? txt.loadFileAsString().trim()
                                               : juce::String();
            result.add (s);
        }
        return result;
    }

    /** Copy any bundled sample files from the repo's docs/samples/ into the
        user data dir, if they aren't already there. No-op if no repo
        samples found (end-user install without source). */
    static void installIfMissing()
    {
        auto target = samplesDir();
        if (target.isDirectory() && target.getNumberOfChildFiles (juce::File::findFiles) > 0)
            return;   // already populated

        target.createDirectory();

        // Try a handful of likely repo-relative locations. If none match, we
        // just leave the dir empty — the UI will hide the menu.
        auto cwd = juce::File::getCurrentWorkingDirectory();
        juce::Array<juce::File> candidates {
            cwd.getChildFile ("docs/samples"),
            cwd.getChildFile ("../docs/samples"),
            cwd.getChildFile ("../../docs/samples"),
            juce::File::getSpecialLocation (juce::File::currentApplicationFile)
                .getParentDirectory().getChildFile ("samples"),
        };
        for (auto& src : candidates)
        {
            if (! src.isDirectory()) continue;
            juce::Array<juce::File> files;
            src.findChildFiles (files, juce::File::findFiles, false, "*.mid");
            for (auto& f : files)
                f.copyFileTo (target.getChildFile (f.getFileName()));

            // Optional description text files
            src.findChildFiles (files, juce::File::findFiles, false, "*.txt");
            for (auto& f : files)
                f.copyFileTo (target.getChildFile (f.getFileName()));
            if (target.getNumberOfChildFiles (juce::File::findFiles) > 0) return;
        }
    }

private:
    static juce::File samplesDir()
    {
        return juce::File::getSpecialLocation (juce::File::userApplicationDataDirectory)
                   .getChildFile ("MidiGPT").getChildFile ("samples");
    }

    SampleGallery() = delete;
};
