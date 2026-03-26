#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"
#include "TransportBar.h"
#include "SessionView.h"
#include "PianoRoll.h"
#include "MixerPanel.h"
#include "FileBrowser.h"
#include "DetailView.h"
#include "../Core/AudioEngine.h"
#include "../Core/MidiEngine.h"
#include "../Core/ProjectState.h"
#include "../Core/SynthEngine.h"
#include "../AI/AIEngine.h"

//==============================================================================
// StatusBar - Bottom status bar
//==============================================================================
class StatusBar : public juce::Component
{
public:
    StatusBar();

    void paint (juce::Graphics& g) override;
    void resized() override;

    void setMessage (const juce::String& msg);
    void setMidiActivity (bool active);

private:
    juce::Label messageLabel;
    juce::Label midiIndicator;
    juce::Label versionLabel;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (StatusBar)
};

//==============================================================================
// MainContentComponent - Assembles all panels
//==============================================================================
class MainContentComponent : public juce::Component,
                             public juce::MenuBarModel,
                             public juce::ApplicationCommandTarget
{
public:
    MainContentComponent();
    ~MainContentComponent() override;

    void paint (juce::Graphics& g) override;
    void resized() override;

    // ── MenuBarModel ────────────────────────────────────────────────────────
    juce::StringArray getMenuBarNames() override;
    juce::PopupMenu getMenuForIndex (int topLevelMenuIndex, const juce::String& menuName) override;
    void menuItemSelected (int menuItemID, int topLevelMenuIndex) override;

    // ── ApplicationCommandTarget ────────────────────────────────────────────
    juce::ApplicationCommandTarget* getNextCommandTarget() override { return nullptr; }
    void getAllCommands (juce::Array<juce::CommandID>& commands) override;
    void getCommandInfo (juce::CommandID commandID, juce::ApplicationCommandInfo& result) override;
    bool perform (const InvocationInfo& info) override;

    // ── Access sub-components ───────────────────────────────────────────────
    TransportBar& getTransportBar()    { return transportBar; }
    SessionView&  getSessionView()     { return sessionView; }
    DetailView&   getDetailView()      { return detailView; }
    MixerPanel&   getMixerPanel()      { return mixerPanel; }
    FileBrowser&  getFileBrowser()     { return fileBrowser; }

    // ── View mode ───────────────────────────────────────────────────────────
    enum class ViewMode { Session, Arrange, Mixer };
    void setViewMode (ViewMode mode);

    // ── Command IDs ─────────────────────────────────────────────────────────
    enum CommandIDs
    {
        cmdNewProject       = 0x1001,
        cmdOpenProject      = 0x1002,
        cmdSaveProject      = 0x1003,
        cmdSaveProjectAs    = 0x1004,
        cmdExportMidi       = 0x1005,
        cmdExportAudio      = 0x1006,
        cmdUndo             = 0x1010,
        cmdRedo             = 0x1011,
        cmdCut              = 0x1012,
        cmdCopy             = 0x1013,
        cmdPaste            = 0x1014,
        cmdDelete           = 0x1015,
        cmdSelectAll        = 0x1016,
        cmdAddTrack         = 0x1020,
        cmdAddScene         = 0x1021,
        cmdDuplicateClip    = 0x1022,
        cmdToggleSession    = 0x1030,
        cmdToggleMixer      = 0x1031,
        cmdToggleFileBrowser= 0x1032,
        cmdToggleDetail     = 0x1033,
        cmdAIGenerate       = 0x1040,
        cmdAIVariation      = 0x1041,
        cmdAIAnalyze        = 0x1042,
        cmdAbout            = 0x1050,
        cmdPreferences      = 0x1051
    };

private:
    MetallicLookAndFeel metallicLookAndFeel;

    // ── Menu bar ────────────────────────────────────────────────────────────
    std::unique_ptr<juce::MenuBarComponent> menuBar;
    juce::ApplicationCommandManager commandManager;

    // ── UI Components ───────────────────────────────────────────────────────
    TransportBar transportBar;
    FileBrowser  fileBrowser;
    SessionView  sessionView;
    DetailView   detailView;
    MixerPanel   mixerPanel;
    StatusBar    statusBar;

    // ── Layout ──────────────────────────────────────────────────────────────
    juce::StretchableLayoutManager verticalLayout;   // top-level vertical
    juce::StretchableLayoutManager horizontalLayout;  // file browser | main content
    juce::StretchableLayoutManager contentLayout;     // session | detail

    std::unique_ptr<juce::StretchableLayoutResizerBar> hSplitter;
    std::unique_ptr<juce::StretchableLayoutResizerBar> vSplitter;

    ViewMode currentViewMode = ViewMode::Session;
    bool fileBrowserVisible  = true;
    bool detailVisible       = true;
    bool mixerVisible        = false;

    static constexpr int transportH    = 36;
    static constexpr int menuBarH      = 24;
    static constexpr int statusBarH    = 22;
    static constexpr int splitterSize  = 4;

    // ── Core Engines ──────────────────────────────────────────────────────
    AudioEngine audioEngine;
    MidiEngine midiEngine;
    ProjectState projectState;
    AIEngine aiEngine;
    juce::AudioDeviceManager deviceManager;
    juce::AudioSourcePlayer audioSourcePlayer;
    juce::Timer* positionTimer = nullptr;

    void setupLayout();
    void connectCallbacks();
    void updateLayout();
    void loadProjectIntoUI();
    void generateAITrack(const juce::String& type);
    void importMidiFile(const juce::File& file);
    void exportMidiFile(const juce::File& file);
    void renderAndPlay();

    // Timer for playhead updates
    class PositionTimer : public juce::Timer
    {
    public:
        PositionTimer(MainContentComponent& o) : owner(o) {}
        void timerCallback() override;
    private:
        MainContentComponent& owner;
    };
    std::unique_ptr<PositionTimer> playbackTimer;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainContentComponent)
};

//==============================================================================
// MainWindow - Top-level window
//==============================================================================
class MainWindow : public juce::DocumentWindow
{
public:
    MainWindow (const juce::String& name);
    ~MainWindow() override = default;

    void closeButtonPressed() override;

    MainContentComponent& getContent() { return *contentComponent; }

private:
    std::unique_ptr<MainContentComponent> contentComponent;
    MetallicLookAndFeel metallicLnF;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainWindow)
};
