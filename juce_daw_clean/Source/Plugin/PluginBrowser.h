/*
 * MidiGPT DAW — PluginBrowser
 *
 * Modal dialog for scanning VST3 directories and picking a plugin from the
 * KnownPluginList. Returns the chosen PluginDescription via callback.
 *
 * Minimal viable UI: scan-path text field + Scan button + plugin list +
 * OK/Cancel. KnownPluginListComponent could replace the list; we use a
 * simple ListBox to avoid drag/drop categorisation complexity in this
 * sprint.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "PluginHost.h"
#include <functional>

class PluginBrowser : public juce::Component,
                      public juce::ListBoxModel
{
public:
    using SelectCallback = std::function<void(const juce::PluginDescription&)>;

    PluginBrowser(PluginHost& host, SelectCallback onSelect);

    void resized() override;

    /** Convenience modal launcher — owns its DialogWindow. */
    static void launchModal(PluginHost& host, SelectCallback onSelect);

    // ListBoxModel
    int getNumRows() override;
    void paintListBoxItem(int row, juce::Graphics& g,
                          int width, int height, bool selected) override;
    void listBoxItemDoubleClicked(int row, const juce::MouseEvent&) override;

private:
    PluginHost& pluginHost;
    SelectCallback selectCallback;

    juce::TextEditor       pathField;
    juce::TextButton       scanButton    { "Scan" };
    juce::TextButton       defaultsBtn   { "Defaults" };
    juce::TextButton       okButton      { "Use" };
    juce::TextButton       cancelButton  { "Cancel" };
    juce::ListBox          pluginList;
    juce::Label            statusLabel;

    void doScan();
    void useSelected();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PluginBrowser)
};
