/*
 * MidiGPT DAW — PluginEditorWindow (U6)
 *
 * Owns an AudioProcessorEditor (the plugin's native GUI) inside a
 * DocumentWindow. Created on demand by MainWindow / mixer strip click.
 * Destroying the window calls releaseResources-style cleanup only for
 * the editor, not the instance itself — the instance lives in
 * TrackPluginChain.
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_basics/juce_gui_basics.h>

class PluginEditorWindow : public juce::DocumentWindow
{
public:
    PluginEditorWindow(juce::AudioPluginInstance& instance,
                       const juce::String& titleName);
    ~PluginEditorWindow() override;

    void closeButtonPressed() override;

    /** Launch (non-modal). Returned pointer is self-owned; call
     *  ``setVisible(false)`` or ``closeButtonPressed`` to dismiss. */
    static PluginEditorWindow* launch(juce::AudioPluginInstance& instance,
                                       const juce::String& title);

    int ownerTrackId { -1 };   // V5 — for manager lookup
    int ownerSlotIdx { -1 };

private:
    std::unique_ptr<juce::AudioProcessorEditor> editor;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginEditorWindow)
};


/** V5 — Tracks open plugin-editor windows so they can be closed when the
 *  owning track or slot is removed. Singleton pattern for simplicity. */
class PluginEditorManager
{
public:
    static PluginEditorManager& instance();

    PluginEditorWindow* openFor(int trackId, int slotIdx,
                                juce::AudioPluginInstance& inst,
                                const juce::String& title);

    void closeAllForTrack(int trackId);
    void closeAll();

private:
    PluginEditorManager() = default;
    std::vector<juce::Component::SafePointer<PluginEditorWindow>> windows;
};
