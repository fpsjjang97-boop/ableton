/*
 * MidiGPT DAW - MainWindow
 *
 * Main application window with menu bar, transport, arrangement,
 * piano roll, mixer, AI panel, and status bar.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "Core/AudioEngine.h"
#include "UI/LookAndFeel.h"
#include "UI/TransportBar.h"
#include "UI/ArrangementView.h"
#include "UI/PianoRoll.h"
#include "UI/MixerPanel.h"
#include "AI/AIPanel.h"

class MainWindow : public juce::DocumentWindow
{
public:
    MainWindow(const juce::String& name);
    ~MainWindow() override;
    void closeButtonPressed() override;

private:
    MetallicLookAndFeel metalLookAndFeel;

    class StatusBar : public juce::Component
    {
    public:
        StatusBar();
        void paint(juce::Graphics& g) override;
        void resized() override;
        void setMessage(const juce::String& msg);
    private:
        juce::Label messageLabel { {}, "Ready" };
        juce::Label versionLabel { {}, "MidiGPT DAW v0.1.0" };
    };

    class MainContent : public juce::Component,
                        public juce::MenuBarModel,
                        public juce::FileDragAndDropTarget,
                        public juce::KeyListener,
                        public juce::Timer
    {
    public:
        MainContent();
        ~MainContent() override;

        void paint(juce::Graphics& g) override;
        void resized() override;

        // MenuBarModel
        juce::StringArray getMenuBarNames() override;
        juce::PopupMenu getMenuForIndex(int idx, const juce::String&) override;
        void menuItemSelected(int menuItemID, int idx) override;

        // FileDragAndDropTarget
        bool isInterestedInFileDrag(const juce::StringArray& files) override;
        void filesDropped(const juce::StringArray& files, int x, int y) override;

        // KeyListener
        bool keyPressed(const juce::KeyPress& key, juce::Component*) override;

        // Timer (playhead sync)
        void timerCallback() override;

        // Project I/O
        void saveProject();
        void saveProjectAs();
        void loadProject();
        void exportMidi();
        void newProject();

    private:
        AudioEngine audioEngine;

        juce::MenuBarComponent menuBar;
        TransportBar      transportBar;
        ArrangementView   arrangementView;
        PianoRoll         pianoRoll;
        MixerPanel        mixerPanel;
        AIPanel           aiPanel;
        StatusBar         statusBar;

        juce::TabbedComponent bottomTabs { juce::TabbedButtonBar::TabsAtTop };

        juce::File currentProjectFile;

        void loadMidiFile(const juce::File& file);
    };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MainWindow)
};
