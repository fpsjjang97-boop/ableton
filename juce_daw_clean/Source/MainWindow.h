/*
 * MidiGPT DAW - MainWindow
 *
 * Main application window with menu bar, transport, arrangement,
 * piano roll, mixer, AI panel, and status bar.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_data_structures/juce_data_structures.h>
#include "Core/AudioEngine.h"
#include "UI/LookAndFeel.h"
#include "UI/TransportBar.h"
#include "UI/ArrangementView.h"
#include "UI/PianoRoll.h"
#include "UI/MixerPanel.h"
#include "UI/CCLane.h"
#include "UI/StepSeqView.h"
#include "AI/AIPanel.h"
#include "Plugin/PluginHost.h"

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

public: // VV2 — needs access from closeButtonPressed
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
        void loadProject();                    // dialog
        void loadProjectFromFile(const juce::File& file); // AA2 — direct
        void exportMidi();
        void exportMidiStems();                 // AA5
        void newProject();

        // Audio I/O (F5/F6)
        void importAudioFile();
        void renderToWav();

        // Plugins (F2)
        void openPluginBrowser();

    public:
        bool isDirty() const { return projectDirty; } // VV2
        juce::UndoManager undoManager; // V1 — accessible to child components
        int autoSaveMinutes { 5 };      // Y4 — 0 = disabled

        // GG6 — undo grouping: coalesce rapid edits into one transaction
        void beginUndoGroup(const juce::String& name);
        juce::int64 lastUndoGroupTime { 0 };
        juce::String lastUndoGroupName;

    private:
        AudioEngine audioEngine;
        PluginHost  pluginHost;

        juce::MenuBarComponent menuBar;
        TransportBar      transportBar;
        ArrangementView   arrangementView;
        PianoRoll         pianoRoll;
        CCLane            ccLane;
        StepSeqView       stepSeqView;
        MixerPanel        mixerPanel;
        AIPanel           aiPanel;
        StatusBar         statusBar;

        juce::TabbedComponent bottomTabs { juce::TabbedButtonBar::TabsAtTop };

        juce::File currentProjectFile;
        bool projectDirty { false }; // NN6
        void markDirty();

        // Z5 — most recent project files (max 10)
        juce::Array<juce::File> recentFiles;
        void pushRecent(const juce::File& f);

        void loadMidiFile(const juce::File& file);
        void loadAudioFile(const juce::File& file);

        // HH5 — crash recovery
        void panicSave();
        void checkCrashRecovery();
        juce::File getCrashRecoveryFile() const;

        // Sprint 51 review — file-based diagnostic log (for remote bug
        // triage without attaching a debugger). Written to
        // %APPDATA%\MidiGPT\daw_debug.log; reset on each launch.
        static juce::File getDiagLogFile();
        static void writeDiagLine (const juce::String& line);

        // Runtime self-check: walks the component tree, logs every direct
        // child of MainContent + bottomTabs with type/name/bounds/visible,
        // and flags suspicious states (0x0 visible components, duplicate
        // names, overlap) to daw_debug.log. Runs once ~500 ms after
        // startup so all first-frame paints have had a chance to fire.
        void runSelfCheck();
    };

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MainWindow)
};
