/*
 * MidiGPT DAW - MainWindow.cpp
 */

#include "MainWindow.h"
#include "Plugin/PluginBrowser.h"
#include "Plugin/PluginEditorWindow.h"
#include "Audio/OfflineRenderer.h"
#include "Automation/AutomationEditor.h"

// =============================================================================
// StatusBar
// =============================================================================
MainWindow::StatusBar::StatusBar()
{
    messageLabel.setFont(juce::Font(11.0f));
    messageLabel.setColour(juce::Label::textColourId, juce::Colour(0xFF909090));
    addAndMakeVisible(messageLabel);

    versionLabel.setFont(juce::Font(10.0f));
    versionLabel.setColour(juce::Label::textColourId, juce::Colour(0xFF505050));
    versionLabel.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(versionLabel);
}

void MainWindow::StatusBar::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF1C1C1C));
    g.setColour(juce::Colour(0xFF2A2A2A));
    g.drawHorizontalLine(0, 0.0f, (float)getWidth());
}

void MainWindow::StatusBar::resized()
{
    auto area = getLocalBounds().reduced(6, 0);
    messageLabel.setBounds(area.removeFromLeft(area.getWidth() / 2));
    versionLabel.setBounds(area);
}

void MainWindow::StatusBar::setMessage(const juce::String& msg)
{
    messageLabel.setText(msg, juce::dontSendNotification);
}

// =============================================================================
// MainWindow
// =============================================================================
MainWindow::MainWindow(const juce::String& name)
    : DocumentWindow(name, juce::Colour(0xFF0E0E0E), DocumentWindow::allButtons)
{
    juce::LookAndFeel::setDefaultLookAndFeel(&metalLookAndFeel);

    setUsingNativeTitleBar(true);
    setContentOwned(new MainContent(), true);
    setResizable(true, true);
    setResizeLimits(1280, 720, 4096, 2160);
    centreWithSize(1600, 900);
    setVisible(true);
}

MainWindow::~MainWindow()
{
    juce::LookAndFeel::setDefaultLookAndFeel(nullptr);
}

void MainWindow::closeButtonPressed()
{
    juce::JUCEApplication::getInstance()->systemRequestedQuit();
}

// =============================================================================
// MainContent
// =============================================================================
MainWindow::MainContent::MainContent()
    : transportBar(audioEngine),
      arrangementView(audioEngine),
      mixerPanel(audioEngine),
      aiPanel(audioEngine)
{
    // AA3 — load persisted recent files
    {
        auto raw = getAppProps().getValue("recentFiles");
        juce::StringArray paths;
        paths.addLines(raw);
        for (auto& p : paths)
            if (p.isNotEmpty()) recentFiles.add(juce::File(p));
    }
    // AA4 — restore MIDI input latency
    audioEngine.setMidiInputLatencyMs(
        getAppProps().getDoubleValue("midiInputLatencyMs", 0.0));

    // Menu bar
    menuBar.setModel(this);
    addAndMakeVisible(menuBar);

    addAndMakeVisible(transportBar);
    addAndMakeVisible(arrangementView);
    addAndMakeVisible(aiPanel);
    addAndMakeVisible(statusBar);

    // W1 — wire undo manager into editors
    pianoRoll.setUndoManager(&undoManager);
    arrangementView.setUndoManager(&undoManager);
    // Y1 + Z1 — recording predicate on every content editor
    auto recPred = [this] { return audioEngine.isRecording(); };
    pianoRoll.setRecordingPredicate(recPred);
    arrangementView.setRecordingPredicate(recPred);
    ccLane.setRecordingPredicate(recPred);
    stepSeqView.setRecordingPredicate(recPred);

    // Bottom tabs
    bottomTabs.addTab("Piano Roll", juce::Colour(0xFF1A1A2E), &pianoRoll, false);
    bottomTabs.addTab("CC Lane",    juce::Colour(0xFF1A1A1A), &ccLane, false);
    bottomTabs.addTab("Step Seq",   juce::Colour(0xFF1A1A1A), &stepSeqView, false);
    bottomTabs.addTab("Mixer",      juce::Colour(0xFF1A1A1A), &mixerPanel, false);
    addAndMakeVisible(bottomTabs);

    // Wire clip selection — feed all editors that show the active clip
    arrangementView.onClipSelected = [this](MidiClip* clip)
    {
        pianoRoll.setClip(clip);
        ccLane.setClip(clip);
        stepSeqView.setClip(clip);
        bottomTabs.setCurrentTabIndex(0);
    };

    // Wire track list changes
    arrangementView.onTrackListChanged = [this]()
    {
        mixerPanel.refresh();
        arrangementView.repaint();
    };

    // Default track with empty clip
    auto& track = audioEngine.getTrackModel().addTrack("MidiGPT Track 1");
    audioEngine.prebuildTrackSynth(track.id); // T1 — GUI-thread alloc
    MidiClip emptyClip;
    emptyClip.startBeat = 0;
    emptyClip.lengthBeats = 16.0;
    track.clips.push_back(emptyClip);

    pianoRoll.setClip(&track.clips.front());
    mixerPanel.refresh();

    audioEngine.initialise();

    // Global keyboard shortcuts
    addKeyListener(this);

    // Playhead sync timer
    startTimerHz(30);

    // Show audio device info
    if (auto* device = audioEngine.getDeviceManager().getCurrentAudioDevice())
        statusBar.setMessage("Audio: " + device->getName()
                             + " @ " + juce::String((int)device->getCurrentSampleRate()) + " Hz");
    else
        statusBar.setMessage("WARNING: No audio device detected! Go to Help > Audio Settings");

    setSize(1600, 900);
}

bool MainWindow::MainContent::keyPressed(const juce::KeyPress& key, juce::Component*)
{
    // Space = toggle play/stop
    if (key == juce::KeyPress::spaceKey)
    {
        if (audioEngine.isPlaying())
            audioEngine.stop();
        else
        {
            audioEngine.rewind();
            audioEngine.play();
        }
        return true;
    }
    // Ctrl+S = save
    if (key == juce::KeyPress('s', juce::ModifierKeys::ctrlModifier, 0))
    { saveProject(); return true; }
    // Ctrl+O = open
    if (key == juce::KeyPress('o', juce::ModifierKeys::ctrlModifier, 0))
    { menuItemSelected(102, 0); return true; }
    // Ctrl+N = new
    if (key == juce::KeyPress('n', juce::ModifierKeys::ctrlModifier, 0))
    { menuItemSelected(101, 0); return true; }
    // Ctrl+T = add track
    if (key == juce::KeyPress('t', juce::ModifierKeys::ctrlModifier, 0))
    { menuItemSelected(301, 0); return true; }
    // V1 — Ctrl+Z = undo, Ctrl+Y / Ctrl+Shift+Z = redo
    if (key == juce::KeyPress('z', juce::ModifierKeys::ctrlModifier, 0))
    {
        if (undoManager.undo())
        {
            mixerPanel.refresh();
            arrangementView.repaint();
            pianoRoll.repaint();
            statusBar.setMessage("Undo");
        }
        return true;
    }
    if (key == juce::KeyPress('y', juce::ModifierKeys::ctrlModifier, 0)
     || key == juce::KeyPress('z', juce::ModifierKeys::ctrlModifier | juce::ModifierKeys::shiftModifier, 0))
    {
        if (undoManager.redo())
        {
            mixerPanel.refresh();
            arrangementView.repaint();
            pianoRoll.repaint();
            statusBar.setMessage("Redo");
        }
        return true;
    }

    return false;
}

MainWindow::MainContent::~MainContent()
{
    stopTimer();
    removeKeyListener(this);
    menuBar.setModel(nullptr);
    audioEngine.shutdown();
}

void MainWindow::MainContent::timerCallback()
{
    pianoRoll.setPlayheadBeat(audioEngine.getPositionBeats());
    if (audioEngine.isPlaying())
        pianoRoll.repaint();

    // X6 + Y4 — Auto-save. Interval user-configurable via Preferences.
    // 0 minutes = disabled. Skipped while playing.
    static int autoSaveTicks = 0;
    ++autoSaveTicks;
    if (autoSaveMinutes > 0)
    {
        const int ticksPerInterval = 30 * 60 * autoSaveMinutes;
        if (autoSaveTicks >= ticksPerInterval)
        {
            autoSaveTicks = 0;
            if (currentProjectFile != juce::File() && ! audioEngine.isPlaying())
            {
                saveProject();
                statusBar.setMessage("Auto-saved " + currentProjectFile.getFileName());
            }
        }
    }
}

void MainWindow::MainContent::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF0E0E0E));
}

void MainWindow::MainContent::resized()
{
    auto area = getLocalBounds();

    menuBar.setBounds(area.removeFromTop(24));
    transportBar.setBounds(area.removeFromTop(36));
    statusBar.setBounds(area.removeFromBottom(22));

    // AI panel on right
    aiPanel.setBounds(area.removeFromRight(250));

    // Bottom tabs
    bottomTabs.setBounds(area.removeFromBottom(300));

    // Arrangement fills the rest
    arrangementView.setBounds(area);
}

// =============================================================================
// Menu
// =============================================================================
juce::StringArray MainWindow::MainContent::getMenuBarNames()
{
    return { "File", "Edit", "Create", "View", "Plugins", "AI", "Help" };
}

juce::PopupMenu MainWindow::MainContent::getMenuForIndex(int idx, const juce::String&)
{
    juce::PopupMenu menu;

    switch (idx)
    {
        case 0: // File
            menu.addItem(101, "New Project",        true, false);
            menu.addItem(102, "Open...",            true, false);
            menu.addSeparator();
            menu.addItem(103, "Save",               true, false);
            menu.addItem(104, "Save As...",         true, false);
            menu.addSeparator();
            menu.addItem(105, "Import MIDI...",     true, false);
            menu.addItem(106, "Export MIDI...",       true, false);
            menu.addItem(109, "Export MIDI Stems...", true, false); // AA5
            menu.addItem(107, "Import Audio...",      true, false);
            menu.addItem(108, "Render to WAV...",     true, false);
            menu.addSeparator();
            {
                // Z5 — recent files submenu (ids 170..179)
                juce::PopupMenu recentMenu;
                for (int i = 0; i < juce::jmin(10, recentFiles.size()); ++i)
                    recentMenu.addItem(170 + i, recentFiles[i].getFileName(),
                                       recentFiles[i].existsAsFile());
                if (recentFiles.isEmpty())
                    recentMenu.addItem(999, "(none)", false);
                menu.addSubMenu("Open Recent", recentMenu);
            }
            menu.addSeparator();
            menu.addItem(199, "Quit",               true, false);
            break;

        case 1: // Edit
            menu.addItem(201, "Undo",  undoManager.canUndo(), false);
            menu.addItem(202, "Redo",  undoManager.canRedo(), false);
            menu.addSeparator();
            menu.addItem(203, "Cut",               true, false);
            menu.addItem(204, "Copy",              true, false);
            menu.addItem(205, "Paste",             true, false);
            menu.addItem(206, "Delete",            true, false);
            menu.addItem(207, "Select All",        true, false);
            break;

        case 2: // Create
            menu.addItem(301, "Add MIDI Track",    true, false);
            menu.addItem(302, "Duplicate Clip",    true, false);
            break;

        case 3: // View
            menu.addItem(401, "Arrangement",       true, false);
            menu.addItem(402, "Mixer",             true, false);
            menu.addItem(403, "Piano Roll",        true, false);
            break;

        case 4: // Plugins (F2 + U6 + BB3)
            menu.addItem(701, "Plugin Browser...",  true, false);
            menu.addItem(702, "Add to Selected Track", true, false);
            menu.addItem(703, "Open Plugin Editor (first slot)", true, false);
            menu.addItem(704, "Automate Plugin Parameter...", true, false);
            menu.addItem(705, "Save Plugin Preset...", true, false); // BB4
            menu.addItem(706, "Load Plugin Preset...", true, false); // BB4
            break;

        case 5: // AI
            menu.addItem(501, "Generate Variation", true, false);
            menu.addItem(502, "Analyze Clip",       true, false);
            break;

        case 6: // Help
            menu.addItem(601, "About MidiGPT DAW", true, false);
            menu.addItem(602, "Audio Settings...",  true, false);
            menu.addItem(603, "Auto-save Interval...", true, false); // Y4
            menu.addItem(604, "MIDI Input Latency...", true, false); // AA4
            break;
    }
    return menu;
}

void MainWindow::MainContent::menuItemSelected(int menuItemID, int)
{
    switch (menuItemID)
    {
        case 101: newProject(); break;
        case 102: loadProject(); break;
        case 103: saveProject(); break;
        case 104: saveProjectAs(); break;
        case 105: // Import MIDI
        {
            auto chooser = std::make_shared<juce::FileChooser>(
                "Import MIDI", juce::File(), "*.mid;*.midi");
            chooser->launchAsync(juce::FileBrowserComponent::openMode
                                 | juce::FileBrowserComponent::canSelectFiles,
                [this, chooser](const juce::FileChooser& fc)
                {
                    auto file = fc.getResult();
                    if (file.existsAsFile())
                        loadMidiFile(file);
                });
            break;
        }
        case 106: exportMidi(); break;
        case 109: exportMidiStems(); break; // AA5
        case 107: importAudioFile(); break;
        case 108: renderToWav(); break;
        case 201: // Undo
            if (undoManager.undo()) { mixerPanel.refresh(); arrangementView.repaint(); pianoRoll.repaint(); }
            break;
        case 202: // Redo
            if (undoManager.redo()) { mixerPanel.refresh(); arrangementView.repaint(); pianoRoll.repaint(); }
            break;
        case 199: // Quit
            juce::JUCEApplication::getInstance()->systemRequestedQuit();
            break;
        case 701: openPluginBrowser(); break;
        default:
            // Z5 — recent file items (170..179)
            if (menuItemID >= 170 && menuItemID < 180)
            {
                int idx = menuItemID - 170;
                if (idx < recentFiles.size() && recentFiles[idx].existsAsFile())
                    loadProjectFromFile(recentFiles[idx]); // AA2
            }
            break;
        case 702: openPluginBrowser(); break; // same dialog
        case 705: // BB4 — save first-slot plugin preset (selected track)
        {
            const int selId = arrangementView.getSelectedTrackId();
            auto* t = audioEngine.getTrackModel().getTrack(selId);
            if (t == nullptr || t->plugins.empty())
            { statusBar.setMessage("No plugin on selected track"); break; }
            auto* inst = audioEngine.getPluginChains().getPlugin(t->id, 0);
            if (inst == nullptr) { statusBar.setMessage("Plugin not loaded"); break; }

            auto chooser = std::make_shared<juce::FileChooser>(
                "Save Preset", juce::File(), "*.vstpreset;*.bin");
            chooser->launchAsync(juce::FileBrowserComponent::saveMode,
                [this, chooser, inst](const juce::FileChooser& fc) {
                    auto f = fc.getResult();
                    if (f == juce::File()) return;
                    juce::MemoryBlock mb;
                    inst->getStateInformation(mb);
                    if (f.replaceWithData(mb.getData(), mb.getSize()))
                        statusBar.setMessage("Saved preset: " + f.getFileName());
                });
            break;
        }
        case 706: // BB4 — load preset
        {
            const int selId = arrangementView.getSelectedTrackId();
            auto* t = audioEngine.getTrackModel().getTrack(selId);
            if (t == nullptr || t->plugins.empty())
            { statusBar.setMessage("No plugin on selected track"); break; }
            auto* inst = audioEngine.getPluginChains().getPlugin(t->id, 0);
            if (inst == nullptr) { statusBar.setMessage("Plugin not loaded"); break; }

            auto chooser = std::make_shared<juce::FileChooser>(
                "Load Preset", juce::File(), "*.vstpreset;*.bin");
            chooser->launchAsync(juce::FileBrowserComponent::openMode
                                 | juce::FileBrowserComponent::canSelectFiles,
                [this, chooser, inst](const juce::FileChooser& fc) {
                    auto f = fc.getResult();
                    if (! f.existsAsFile()) return;
                    juce::MemoryBlock mb;
                    if (f.loadFileAsData(mb) && mb.getSize() > 0)
                    {
                        inst->setStateInformation(mb.getData(), (int)mb.getSize());
                        statusBar.setMessage("Loaded preset: " + f.getFileName());
                    }
                });
            break;
        }
        case 704: // BB3 — pick plugin param → open AutomationEditor
        {
            const int selId = arrangementView.getSelectedTrackId();
            auto* t = audioEngine.getTrackModel().getTrack(selId);
            if (t == nullptr || t->plugins.empty())
            {
                statusBar.setMessage("Select a track with at least one plugin");
                break;
            }
            // Plugin slot picker + param picker — single popup
            juce::PopupMenu pm;
            int id = 1;
            for (int s = 0; s < (int)t->plugins.size(); ++s)
            {
                auto* inst = audioEngine.getPluginChains().getPlugin(t->id, s);
                if (inst == nullptr) continue;
                juce::PopupMenu sub;
                for (auto* p : inst->getParameters())
                {
                    if (p == nullptr) continue;
                    sub.addItem(id, p->getName(64));
                    if (id > 999) break;
                    ++id;
                }
                pm.addSubMenu(t->plugins[s].displayName, sub);
            }
            pm.showMenuAsync(juce::PopupMenu::Options(),
                [this, t](int chosen) {
                    if (chosen <= 0) return;
                    int walk = 1;
                    for (int s = 0; s < (int)t->plugins.size(); ++s)
                    {
                        auto* inst = audioEngine.getPluginChains().getPlugin(t->id, s);
                        if (inst == nullptr) continue;
                        for (auto* p : inst->getParameters())
                        {
                            if (p == nullptr) continue;
                            if (walk == chosen)
                            {
                                const juce::String pid =
                                    t->plugins[s].pluginUid + "/" + p->getName(64);
                                double maxBeats = 16.0;
                                for (auto& c : t->clips)
                                    maxBeats = juce::jmax(maxBeats, c.startBeat + c.lengthBeats);
                                AutomationEditor::launchModal(*t, pid, maxBeats);
                                return;
                            }
                            ++walk;
                        }
                    }
                });
            break;
        }
        case 703: // U6 — open editor for first plugin on selected track
        {
            const int selId = arrangementView.getSelectedTrackId();
            auto* t = audioEngine.getTrackModel().getTrack(selId);
            if (t == nullptr || t->plugins.empty())
            {
                auto& tracks = audioEngine.getTrackModel().getTracks();
                if (tracks.empty() || tracks.front().plugins.empty())
                {
                    statusBar.setMessage("No plugin on selected/first track");
                    break;
                }
                t = &tracks.front();
            }
            if (auto* inst = audioEngine.getPluginChains().getPlugin(t->id, 0))
                PluginEditorManager::instance().openFor(t->id, 0, *inst, t->plugins[0].displayName);
            else
                statusBar.setMessage("Plugin instance not loaded");
            break;
        }
        case 301: // Add Track
        {
            auto& nt = audioEngine.getTrackModel().addTrack();
            audioEngine.prebuildTrackSynth(nt.id); // T1
            mixerPanel.refresh();
            arrangementView.repaint();
            break;
        }
        case 402: // Mixer
            bottomTabs.setCurrentTabIndex(1);
            break;
        case 403: // Piano Roll
            bottomTabs.setCurrentTabIndex(0);
            break;
        case 602: // Audio Settings
        {
            auto* comp = new juce::AudioDeviceSelectorComponent(
                audioEngine.getDeviceManager(), 0, 0, 0, 2, true, true, true, false);
            comp->setSize(500, 400);
            juce::DialogWindow::LaunchOptions opts;
            opts.content.setOwned(comp);
            opts.dialogTitle = "Audio Settings";
            opts.dialogBackgroundColour = juce::Colour(0xFF1E1E1E);
            opts.launchAsync();
            break;
        }
        case 601: // About
        {
            juce::AlertWindow::showMessageBoxAsync(
                juce::MessageBoxIconType::InfoIcon,
                "About MidiGPT DAW",
                "MidiGPT DAW v0.1.0\n\n"
                "AI-powered MIDI workstation with built-in LLM.\n"
                "Clean room JUCE implementation.");
            break;
        }
        case 604: // AA4 — MIDI input latency
        {
            auto* aw = new juce::AlertWindow(
                "MIDI Input Latency",
                "Additional latency in ms (negative = MIDI earlier, positive = later):",
                juce::MessageBoxIconType::NoIcon);
            aw->addTextEditor("ms", juce::String(audioEngine.getMidiInputLatencyMs()));
            aw->addButton("OK", 1);
            aw->addButton("Cancel", 0);
            aw->enterModalState(true, juce::ModalCallbackFunction::create(
                [this, aw](int r) {
                    if (r == 1)
                    {
                        double v = aw->getTextEditorContents("ms").getDoubleValue();
                        audioEngine.setMidiInputLatencyMs(juce::jlimit(-500.0, 500.0, v));
                        getAppProps().setValue("midiInputLatencyMs", audioEngine.getMidiInputLatencyMs());
                        getAppProps().saveIfNeeded();
                        statusBar.setMessage("MIDI input latency: " +
                            juce::String(audioEngine.getMidiInputLatencyMs(), 1) + " ms");
                    }
                    delete aw;
                }), false);
            break;
        }
        case 603: // Y4 — auto-save interval
        {
            auto* aw = new juce::AlertWindow(
                "Auto-save Interval",
                "Minutes between auto-saves (0 = disabled):",
                juce::MessageBoxIconType::NoIcon);
            aw->addTextEditor("m", juce::String(autoSaveMinutes));
            aw->addButton("OK", 1);
            aw->addButton("Cancel", 0);
            aw->enterModalState(true, juce::ModalCallbackFunction::create(
                [this, aw](int r) {
                    if (r == 1)
                    {
                        int v = aw->getTextEditorContents("m").getIntValue();
                        autoSaveMinutes = juce::jlimit(0, 120, v);
                        statusBar.setMessage(autoSaveMinutes == 0
                            ? "Auto-save disabled"
                            : "Auto-save every " + juce::String(autoSaveMinutes) + " min");
                    }
                    delete aw;
                }), false);
            break;
        }
        default:
            break;
    }
}

// =============================================================================
// MIDI file drag & drop
// =============================================================================
bool MainWindow::MainContent::isInterestedInFileDrag(const juce::StringArray& files)
{
    static const juce::StringArray exts {
        ".mid", ".midi",
        ".wav", ".aif", ".aiff", ".flac", ".mp3", ".ogg"
    };
    for (auto& f : files)
        for (auto& ext : exts)
            if (f.endsWithIgnoreCase(ext)) return true;
    return false;
}

void MainWindow::MainContent::filesDropped(const juce::StringArray& files, int, int)
{
    for (auto& f : files)
    {
        if (f.endsWithIgnoreCase(".mid") || f.endsWithIgnoreCase(".midi"))
            loadMidiFile(juce::File(f));
        else if (f.endsWithIgnoreCase(".wav") || f.endsWithIgnoreCase(".aif")
              || f.endsWithIgnoreCase(".aiff") || f.endsWithIgnoreCase(".flac")
              || f.endsWithIgnoreCase(".mp3")  || f.endsWithIgnoreCase(".ogg"))
            loadAudioFile(juce::File(f));
    }
}

void MainWindow::MainContent::loadMidiFile(const juce::File& file)
{
    juce::MidiFile midiFile;
    juce::FileInputStream fis(file);

    if (!fis.openedOk() || !midiFile.readFrom(fis))
    {
        statusBar.setMessage("Failed to load: " + file.getFileName());
        return;
    }

    midiFile.convertTimestampTicksToSeconds();
    double bpm = audioEngine.getTempo();

    int tracksAdded = 0;
    for (int t = 0; t < midiFile.getNumTracks(); ++t)
    {
        auto* srcTrack = midiFile.getTrack(t);
        if (!srcTrack || srcTrack->getNumEvents() == 0) continue;

        bool hasNotes = false;
        for (int i = 0; i < srcTrack->getNumEvents(); ++i)
            if (srcTrack->getEventPointer(i)->message.isNoteOn())
            { hasNotes = true; break; }
        if (!hasNotes) continue;

        auto& newTrack = audioEngine.getTrackModel().addTrack(
            file.getFileNameWithoutExtension() + " [" + juce::String(t) + "]");

        MidiClip clip;
        clip.startBeat = 0.0;

        for (int i = 0; i < srcTrack->getNumEvents(); ++i)
        {
            auto msg = srcTrack->getEventPointer(i)->message;
            msg.setTimeStamp(msg.getTimeStamp() * (bpm / 60.0));
            clip.sequence.addEvent(msg);
        }
        clip.sequence.updateMatchedPairs();

        double maxBeat = 0;
        for (int i = 0; i < clip.sequence.getNumEvents(); ++i)
            maxBeat = juce::jmax(maxBeat, clip.sequence.getEventPointer(i)->message.getTimeStamp());
        clip.lengthBeats = juce::jmax(4.0, std::ceil(maxBeat / 4.0) * 4.0);

        newTrack.clips.push_back(std::move(clip));
        tracksAdded++;
    }

    mixerPanel.refresh();
    arrangementView.repaint();

    auto& tracks = audioEngine.getTrackModel().getTracks();
    if (!tracks.empty() && !tracks.back().clips.empty())
    {
        pianoRoll.setClip(&tracks.back().clips.front());
        bottomTabs.setCurrentTabIndex(0);
    }

    statusBar.setMessage("Loaded " + file.getFileName()
                         + " (" + juce::String(tracksAdded) + " tracks)");
}

// =============================================================================
// Project Save/Load (JSON)
// =============================================================================
// AA3 — single app-level PropertiesFile for recent files & preferences
static juce::PropertiesFile& getAppProps()
{
    static juce::PropertiesFile::Options opts;
    static juce::PropertiesFile props([]{
        opts.applicationName     = "MidiGPTDAW";
        opts.filenameSuffix      = ".settings";
        opts.osxLibrarySubFolder = "Application Support";
        opts.folderName          = "MidiGPTDAW";
        opts.storageFormat       = juce::PropertiesFile::storeAsXML;
        return opts;
    }());
    return props;
}

void MainWindow::MainContent::pushRecent(const juce::File& f)
{
    recentFiles.removeFirstMatchingValue(f);
    recentFiles.insert(0, f);
    while (recentFiles.size() > 10) recentFiles.remove(recentFiles.size() - 1);

    // AA3 — persist
    juce::StringArray paths;
    for (auto& rf : recentFiles) paths.add(rf.getFullPathName());
    getAppProps().setValue("recentFiles", paths.joinIntoString("\n"));
    getAppProps().saveIfNeeded();
}

void MainWindow::MainContent::saveProject()
{
    // .mgp v2 — adds audioClips, plugins, automation, buses, outputBusId.
    // Forward-compat: v1 loaders see "version": 2 and may bail; this is BREAKING.
    if (currentProjectFile == juce::File())
    { saveProjectAs(); return; }

    pushRecent(currentProjectFile); // Z5

    juce::DynamicObject::Ptr root = new juce::DynamicObject();
    root->setProperty("version", 3);              // T6 — adds audioClips wavRef
    root->setProperty("projectName", "MidiGPT Project");
    root->setProperty("bpm", audioEngine.getTempo());
    // BB5/BB6 — tempo/time-sig maps
    {
        juce::Array<juce::var> tmArr;
        for (auto& [b, bpm] : audioEngine.getMidiEngine().getTempoMap())
        {
            juce::DynamicObject::Ptr o = new juce::DynamicObject();
            o->setProperty("beat", b);
            o->setProperty("bpm", bpm);
            tmArr.add(juce::var(o.get()));
        }
        root->setProperty("tempoMap", tmArr);

        juce::Array<juce::var> tsArr;
        for (auto& [b, sig] : audioEngine.getMidiEngine().getTimeSignatureMap())
        {
            juce::DynamicObject::Ptr o = new juce::DynamicObject();
            o->setProperty("beat", b);
            o->setProperty("num", sig.num);
            o->setProperty("den", sig.den);
            tsArr.add(juce::var(o.get()));
        }
        root->setProperty("tsMap", tsArr);
    }

    // T6 — sidecar audio dir for externalised clips (sibling to .mgp file)
    auto audioDir = currentProjectFile.getParentDirectory().getChildFile(
        currentProjectFile.getFileNameWithoutExtension() + "_audio");

    // Buses
    juce::Array<juce::var> busArr;
    for (auto& bus : audioEngine.getBusModel().getBuses())
    {
        if (bus.id == 0) continue; // master implicit
        juce::DynamicObject::Ptr b = new juce::DynamicObject();
        b->setProperty("id", bus.id);
        b->setProperty("name", bus.name);
        b->setProperty("volume", (double)bus.volume);
        b->setProperty("pan", (double)bus.pan);
        b->setProperty("mute", bus.mute);
        b->setProperty("outputBusId", bus.outputBusId);
        busArr.add(juce::var(b.get()));
    }
    root->setProperty("buses", busArr);

    juce::Array<juce::var> trackArr;
    for (auto& track : audioEngine.getTrackModel().getTracks())
    {
        juce::DynamicObject::Ptr tObj = new juce::DynamicObject();
        tObj->setProperty("name", track.name);
        tObj->setProperty("channel", track.midiChannel);
        tObj->setProperty("volume", (double)track.volume);
        tObj->setProperty("pan", (double)track.pan);
        tObj->setProperty("mute", track.mute);
        tObj->setProperty("solo", track.solo);
        tObj->setProperty("colour", (int)track.colour.getARGB());
        tObj->setProperty("outputBusId", track.outputBusId);
        tObj->setProperty("parentTrackId", track.parentTrackId); // AA6
        tObj->setProperty("isFolder",      track.isFolder);
        tObj->setProperty("collapsed",     track.collapsed);      // BB1

        // U3 — sends
        juce::Array<juce::var> sendsArr;
        for (auto& s : track.sends)
        {
            juce::DynamicObject::Ptr so = new juce::DynamicObject();
            so->setProperty("busId", s.busId);
            so->setProperty("level", (double)s.level);
            sendsArr.add(juce::var(so.get()));
        }
        tObj->setProperty("sends", sendsArr);

        // MIDI clips
        juce::Array<juce::var> clipArr;
        for (auto& clip : track.clips)
        {
            juce::DynamicObject::Ptr cObj = new juce::DynamicObject();
            cObj->setProperty("startBeat", clip.startBeat);
            cObj->setProperty("lengthBeats", clip.lengthBeats);

            juce::Array<juce::var> noteArr;
            juce::Array<juce::var> ccArr;
            for (int i = 0; i < clip.sequence.getNumEvents(); ++i)
            {
                auto* evt = clip.sequence.getEventPointer(i);
                if (evt->message.isNoteOn())
                {
                    juce::DynamicObject::Ptr nObj = new juce::DynamicObject();
                    nObj->setProperty("pitch", evt->message.getNoteNumber());
                    nObj->setProperty("velocity", (int)evt->message.getVelocity());
                    nObj->setProperty("start", evt->message.getTimeStamp());
                    double dur = 0.25;
                    if (evt->noteOffObject)
                        dur = evt->noteOffObject->message.getTimeStamp() - evt->message.getTimeStamp();
                    nObj->setProperty("duration", dur);
                    noteArr.add(juce::var(nObj.get()));
                }
                else if (evt->message.isController())
                {
                    juce::DynamicObject::Ptr cc = new juce::DynamicObject();
                    cc->setProperty("cc", evt->message.getControllerNumber());
                    cc->setProperty("value", evt->message.getControllerValue());
                    cc->setProperty("beat", evt->message.getTimeStamp());
                    ccArr.add(juce::var(cc.get()));
                }
            }
            cObj->setProperty("notes", noteArr);
            cObj->setProperty("ccs", ccArr);
            clipArr.add(juce::var(cObj.get()));
        }
        tObj->setProperty("clips", clipArr);

        // T6 — Audio clips: embed if small (<1MB), else externalise as WAV.
        constexpr juce::int64 kInlineMaxBytes = 1 * 1024 * 1024;
        juce::Array<juce::var> audioArr;
        int audioIdx = 0;
        for (auto& a : track.audioClips)
        {
            juce::DynamicObject::Ptr aObj = new juce::DynamicObject();
            aObj->setProperty("startBeat", a.startBeat);
            aObj->setProperty("lengthBeats", a.lengthBeats);
            aObj->setProperty("sourceSampleRate", a.sourceSampleRate);
            aObj->setProperty("channels", a.buffer.getNumChannels());
            aObj->setProperty("samples", a.buffer.getNumSamples());
            aObj->setProperty("sourceOffsetSamples", (double)a.sourceOffsetSamples); // W5

            const juce::int64 byteSize = (juce::int64)sizeof(float)
                * a.buffer.getNumChannels() * a.buffer.getNumSamples();

            if (byteSize > kInlineMaxBytes)
            {
                // Externalise as 16-bit WAV in sidecar dir
                audioDir.createDirectory();
                auto wavName = juce::String(track.id) + "_" + juce::String(audioIdx) + ".wav";
                auto wavFile = audioDir.getChildFile(wavName);
                wavFile.deleteFile();

                auto fos = std::make_unique<juce::FileOutputStream>(wavFile);
                if (fos->openedOk())
                {
                    juce::WavAudioFormat wav;
                    std::unique_ptr<juce::AudioFormatWriter> w(
                        wav.createWriterFor(fos.get(), a.sourceSampleRate,
                                            (unsigned)a.buffer.getNumChannels(),
                                            16, {}, 0));
                    if (w != nullptr)
                    {
                        fos.release();
                        w->writeFromAudioSampleBuffer(a.buffer, 0, a.buffer.getNumSamples());
                        w->flush();
                    }
                }
                aObj->setProperty("wavRef", audioDir.getFileName() + "/" + wavName);
            }
            else
            {
                juce::MemoryBlock mb(byteSize);
                auto* dst = (float*)mb.getData();
                for (int s = 0; s < a.buffer.getNumSamples(); ++s)
                    for (int ch = 0; ch < a.buffer.getNumChannels(); ++ch)
                        *dst++ = a.buffer.getReadPointer(ch)[s];
                aObj->setProperty("pcmBase64", mb.toBase64Encoding());
            }
            audioArr.add(juce::var(aObj.get()));
            ++audioIdx;
        }
        tObj->setProperty("audioClips", audioArr);

        // Plugin slots (state)
        juce::Array<juce::var> pluginArr;
        for (int slotIdx = 0; slotIdx < (int)track.plugins.size(); ++slotIdx)
        {
            auto& slot = track.plugins[slotIdx];
            juce::DynamicObject::Ptr p = new juce::DynamicObject();
            p->setProperty("displayName", slot.displayName);
            p->setProperty("pluginUid", slot.pluginUid);
            p->setProperty("bypass", slot.bypass);

            // Snapshot current instance state at save time
            if (auto* inst = audioEngine.getPluginChains().getPlugin(track.id, slotIdx))
            {
                juce::MemoryBlock state;
                inst->getStateInformation(state);
                p->setProperty("state", state.toBase64Encoding());
            }
            else
            {
                p->setProperty("state", slot.state.toBase64Encoding());
            }
            pluginArr.add(juce::var(p.get()));
        }
        tObj->setProperty("plugins", pluginArr);

        // Automation lanes
        juce::Array<juce::var> autoArr;
        for (auto& lane : track.automation)
        {
            juce::DynamicObject::Ptr la = new juce::DynamicObject();
            la->setProperty("paramId", lane.paramId);
            la->setProperty("enabled", lane.enabled);
            juce::Array<juce::var> pts;
            for (auto& pt : lane.points)
            {
                juce::DynamicObject::Ptr p = new juce::DynamicObject();
                p->setProperty("beat", pt.beat);
                p->setProperty("value", (double)pt.value);
                pts.add(juce::var(p.get()));
            }
            la->setProperty("points", pts);
            autoArr.add(juce::var(la.get()));
        }
        tObj->setProperty("automation", autoArr);

        trackArr.add(juce::var(tObj.get()));
    }
    root->setProperty("tracks", trackArr);

    auto json = juce::JSON::toString(juce::var(root.get()));
    currentProjectFile.replaceWithText(json);
    statusBar.setMessage("Saved (v2): " + currentProjectFile.getFileName());
}

void MainWindow::MainContent::saveProjectAs()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Save Project", juce::File(), "*.mgp");
    chooser->launchAsync(juce::FileBrowserComponent::saveMode,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto file = fc.getResult();
            if (file != juce::File())
            {
                currentProjectFile = file.withFileExtension("mgp");
                saveProject();
            }
        });
}

void MainWindow::MainContent::loadProject()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Open Project", juce::File(), "*.mgp");
    chooser->launchAsync(juce::FileBrowserComponent::openMode
                         | juce::FileBrowserComponent::canSelectFiles,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto file = fc.getResult();
            if (file.existsAsFile()) loadProjectFromFile(file);
        });
}

void MainWindow::MainContent::loadProjectFromFile(const juce::File& file)
{
    // AA2 — direct-path load. Same body as the old dialog callback.
    {
            if (!file.existsAsFile()) return;

            auto parsed = juce::JSON::parse(file.loadFileAsString());
            if (!parsed.isObject()) return;

            audioEngine.stop();
            audioEngine.rewind();

            // Clear existing tracks + plugin instances
            auto& tm = audioEngine.getTrackModel();
            while (tm.getNumTracks() > 0)
                tm.removeTrack(tm.getTracks().front().id);
            audioEngine.getPluginChains().clearAll();

            const int version = (int)parsed.getProperty("version", 1);
            audioEngine.setTempo(parsed.getProperty("bpm", 120.0));

            // BB5/BB6 — restore tempo + time-sig maps
            audioEngine.getMidiEngine().clearTempoMap();
            audioEngine.getMidiEngine().clearTimeSignatureMap();
            if (auto* tmArr = parsed.getProperty("tempoMap", juce::var()).getArray())
                for (auto& v : *tmArr)
                    audioEngine.getMidiEngine().addTempoChange(
                        v.getProperty("beat", 0.0),
                        v.getProperty("bpm", 120.0));
            if (auto* tsArr = parsed.getProperty("tsMap", juce::var()).getArray())
                for (auto& v : *tsArr)
                    audioEngine.getMidiEngine().addTimeSignatureChange(
                        v.getProperty("beat", 0.0),
                        v.getProperty("num", 4),
                        v.getProperty("den", 4));

            // v2 — restore buses
            if (version >= 2)
            {
                auto* busesArr = parsed.getProperty("buses", juce::var()).getArray();
                if (busesArr)
                {
                    for (auto& bVar : *busesArr)
                    {
                        auto& b = audioEngine.getBusModel().addBus(
                            bVar.getProperty("name", "Bus").toString());
                        b.volume = (float)(double)bVar.getProperty("volume", 1.0);
                        b.pan    = (float)(double)bVar.getProperty("pan", 0.0);
                        b.mute   = bVar.getProperty("mute", false);
                        b.outputBusId = bVar.getProperty("outputBusId", 0);
                    }
                }
            }

            auto* tracksArr = parsed.getProperty("tracks", juce::var()).getArray();
            if (!tracksArr) return;

            for (auto& tVar : *tracksArr)
            {
                auto& track = tm.addTrack(tVar.getProperty("name", "Track").toString());
                audioEngine.prebuildTrackSynth(track.id); // T1
                track.midiChannel = tVar.getProperty("channel", 1);
                track.volume = (float)(double)tVar.getProperty("volume", 1.0);
                track.pan = (float)(double)tVar.getProperty("pan", 0.0);
                track.mute = tVar.getProperty("mute", false);
                track.solo = tVar.getProperty("solo", false);
                track.colour = juce::Colour((juce::uint32)(int)tVar.getProperty("colour", (int)0xFF5E81AC));
                track.outputBusId = tVar.getProperty("outputBusId", 0);
                track.parentTrackId = tVar.getProperty("parentTrackId", -1); // AA6
                track.isFolder      = tVar.getProperty("isFolder", false);
                track.collapsed     = tVar.getProperty("collapsed", false);  // BB1

                // U3 — sends
                if (version >= 3)
                {
                    auto* sArr = tVar.getProperty("sends", juce::var()).getArray();
                    if (sArr)
                    {
                        for (auto& sv : *sArr)
                        {
                            Track::Send s;
                            s.busId = sv.getProperty("busId", 0);
                            s.level = (float)(double)sv.getProperty("level", 0.0);
                            track.sends.push_back(s);
                        }
                    }
                }

                auto* clipsArr = tVar.getProperty("clips", juce::var()).getArray();
                if (clipsArr)
                {
                    track.clips.clear();
                    for (auto& cVar : *clipsArr)
                    {
                        MidiClip clip;
                        clip.startBeat = cVar.getProperty("startBeat", 0.0);
                        clip.lengthBeats = cVar.getProperty("lengthBeats", 4.0);

                        auto* notesArr = cVar.getProperty("notes", juce::var()).getArray();
                        if (notesArr)
                        {
                            for (auto& nVar : *notesArr)
                            {
                                int pitch = nVar.getProperty("pitch", 60);
                                int vel = nVar.getProperty("velocity", 100);
                                double start = nVar.getProperty("start", 0.0);
                                double dur = nVar.getProperty("duration", 0.25);
                                auto on = juce::MidiMessage::noteOn(1, pitch, (juce::uint8)vel);
                                on.setTimeStamp(start);
                                auto off = juce::MidiMessage::noteOff(1, pitch);
                                off.setTimeStamp(start + dur);
                                clip.sequence.addEvent(on);
                                clip.sequence.addEvent(off);
                            }
                        }
                        // v2 — CC events
                        if (version >= 2)
                        {
                            auto* ccArr = cVar.getProperty("ccs", juce::var()).getArray();
                            if (ccArr)
                            {
                                for (auto& ccVar : *ccArr)
                                {
                                    int cc  = ccVar.getProperty("cc", 1);
                                    int val = ccVar.getProperty("value", 0);
                                    double beat = ccVar.getProperty("beat", 0.0);
                                    auto m = juce::MidiMessage::controllerEvent(1, cc, val);
                                    m.setTimeStamp(beat);
                                    clip.sequence.addEvent(m);
                                }
                            }
                        }
                        clip.sequence.updateMatchedPairs();
                        track.clips.push_back(std::move(clip));
                    }
                }

                if (version >= 2)
                {
                    // Audio clips
                    auto* aArr = tVar.getProperty("audioClips", juce::var()).getArray();
                    if (aArr)
                    {
                        for (auto& aVar : *aArr)
                        {
                            AudioClip ac;
                            ac.startBeat = aVar.getProperty("startBeat", 0.0);
                            ac.lengthBeats = aVar.getProperty("lengthBeats", 0.0);
                            ac.sourceSampleRate = aVar.getProperty("sourceSampleRate", 44100.0);
                            ac.sourceOffsetSamples = (juce::int64)(double)aVar.getProperty("sourceOffsetSamples", 0.0); // W5
                            const int ch = aVar.getProperty("channels", 1);
                            const int sa = aVar.getProperty("samples", 0);

                            // T6 — prefer wavRef (external) over inline pcmBase64
                            const juce::String wavRef = aVar.getProperty("wavRef", "").toString();
                            bool loaded = false;
                            if (wavRef.isNotEmpty())
                            {
                                auto wavFile = file.getParentDirectory().getChildFile(wavRef);
                                if (wavFile.existsAsFile())
                                {
                                    juce::AudioFormatManager fmt;
                                    fmt.registerBasicFormats();
                                    std::unique_ptr<juce::AudioFormatReader> rd(fmt.createReaderFor(wavFile));
                                    if (rd != nullptr)
                                    {
                                        ac.sourceSampleRate = rd->sampleRate;
                                        ac.buffer.setSize(juce::jmin(2, (int)rd->numChannels),
                                                          (int)rd->lengthInSamples);
                                        rd->read(&ac.buffer, 0, (int)rd->lengthInSamples,
                                                 0, true, ac.buffer.getNumChannels() > 1);
                                        loaded = true;
                                    }
                                }
                                if (! loaded)
                                    DBG("Audio wavRef not found: " << wavRef);
                            }

                            if (! loaded)
                            {
                                juce::MemoryBlock mb;
                                mb.fromBase64Encoding(aVar.getProperty("pcmBase64", "").toString());
                                ac.buffer.setSize(juce::jmax(1, ch), sa);
                                auto* src = (const float*)mb.getData();
                                const int got = (int)(mb.getSize() / sizeof(float));
                                const int per = juce::jmin(sa * juce::jmax(1, ch), got);
                                for (int s = 0; s < sa; ++s)
                                    for (int c = 0; c < ch; ++c)
                                    {
                                        int idx = s * ch + c;
                                        if (idx >= per) break;
                                        ac.buffer.getWritePointer(c)[s] = src[idx];
                                    }
                            }
                            track.audioClips.push_back(std::move(ac));
                        }
                    }

                    // Plugin slots — instantiate via PluginHost using saved uid
                    auto* pArr = tVar.getProperty("plugins", juce::var()).getArray();
                    if (pArr)
                    {
                        auto* device = audioEngine.getDeviceManager().getCurrentAudioDevice();
                        const double sr = device ? device->getCurrentSampleRate() : 44100.0;
                        const int    bs = device ? device->getCurrentBufferSizeSamples() : 512;
                        int slotIdx = 0;
                        for (auto& pVar : *pArr)
                        {
                            PluginSlot slot;
                            slot.displayName = pVar.getProperty("displayName", "").toString();
                            slot.pluginUid   = pVar.getProperty("pluginUid", "").toString();
                            slot.bypass      = pVar.getProperty("bypass", false);
                            slot.state.fromBase64Encoding(pVar.getProperty("state", "").toString());
                            track.plugins.push_back(slot);

                            auto desc = pluginHost.findByIdentifier(slot.pluginUid);
                            if (desc != nullptr)
                            {
                                juce::String err;
                                auto inst = pluginHost.instantiate(*desc, sr, bs, err);
                                if (inst != nullptr)
                                {
                                    if (slot.state.getSize() > 0)
                                        inst->setStateInformation(slot.state.getData(),
                                                                  (int)slot.state.getSize());
                                    audioEngine.getPluginChains().addPlugin(track.id, slotIdx, std::move(inst));
                                }
                                else
                                {
                                    DBG("Plugin reload failed: " << err);
                                }
                            }
                            ++slotIdx;
                        }
                    }

                    // Automation lanes
                    auto* laneArr = tVar.getProperty("automation", juce::var()).getArray();
                    if (laneArr)
                    {
                        for (auto& laVar : *laneArr)
                        {
                            AutomationLane lane;
                            lane.paramId = laVar.getProperty("paramId", "").toString();
                            lane.enabled = laVar.getProperty("enabled", true);
                            auto* ptArr = laVar.getProperty("points", juce::var()).getArray();
                            if (ptArr)
                            {
                                for (auto& pVar : *ptArr)
                                {
                                    AutomationPoint pt;
                                    pt.beat  = pVar.getProperty("beat", 0.0);
                                    pt.value = (float)(double)pVar.getProperty("value", 0.0);
                                    lane.points.push_back(pt);
                                }
                            }
                            track.automation.push_back(std::move(lane));
                        }
                    }
                }
            }

            currentProjectFile = file;
            pushRecent(file); // Z5
            mixerPanel.refresh();
            arrangementView.repaint();

            auto& tracks = tm.getTracks();
            if (!tracks.empty() && !tracks.front().clips.empty())
                pianoRoll.setClip(&tracks.front().clips.front());

            // U5 — report missing wavRef files
            juce::StringArray missing;
            for (auto& t : tracks)
                for (auto& a : t.audioClips)
                    if (a.buffer.getNumSamples() == 0)
                        missing.add(t.name);
            if (! missing.isEmpty())
            {
                juce::AlertWindow::showMessageBoxAsync(
                    juce::MessageBoxIconType::WarningIcon,
                    "Missing audio files",
                    "The following tracks reference audio that could not be found:\n\n"
                    + missing.joinIntoString("\n")
                    + "\n\nUse Import Audio... to relink them.");
            }

            statusBar.setMessage("Opened (v" + juce::String(version) + "): " + file.getFileName());
    }
}

void MainWindow::MainContent::newProject()
{
    audioEngine.stop();
    audioEngine.rewind();

    auto& tm = audioEngine.getTrackModel();
    while (tm.getNumTracks() > 0)
        tm.removeTrack(tm.getTracks().front().id);

    auto& track = tm.addTrack("Track 1");
    MidiClip emptyClip;
    emptyClip.startBeat = 0;
    emptyClip.lengthBeats = 16.0;
    track.clips.push_back(emptyClip);

    pianoRoll.setClip(&track.clips.front());
    mixerPanel.refresh();
    arrangementView.repaint();

    currentProjectFile = {};
    statusBar.setMessage("New project created");
}

void MainWindow::MainContent::exportMidi()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Export MIDI", juce::File(), "*.mid");
    chooser->launchAsync(juce::FileBrowserComponent::saveMode,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto file = fc.getResult();
            if (file == juce::File()) return;

            auto outFile = file.withFileExtension("mid");
            juce::MidiFile midiFile;
            midiFile.setTicksPerQuarterNote(480);

            // Tempo track
            juce::MidiMessageSequence tempoTrack;
            auto tempoMsg = juce::MidiMessage::tempoMetaEvent(
                static_cast<int>(60000000.0 / audioEngine.getTempo()));
            tempoMsg.setTimeStamp(0.0);
            tempoTrack.addEvent(tempoMsg);
            midiFile.addTrack(tempoTrack);

            double bpm = audioEngine.getTempo();

            for (auto& track : audioEngine.getTrackModel().getTracks())
            {
                juce::MidiMessageSequence midiTrack;

                // Track name meta event
                auto nameMsg = juce::MidiMessage::textMetaEvent(3, track.name);
                nameMsg.setTimeStamp(0.0);
                midiTrack.addEvent(nameMsg);

                auto seq = track.flattenForPlayback();
                for (int i = 0; i < seq.getNumEvents(); ++i)
                {
                    auto msg = seq.getEventPointer(i)->message;
                    // Convert beats to ticks (480 TPQ)
                    msg.setTimeStamp(msg.getTimeStamp() * 480.0);
                    msg.setChannel(track.midiChannel);
                    midiTrack.addEvent(msg);
                }

                midiFile.addTrack(midiTrack);
            }

            juce::FileOutputStream fos(outFile);
            if (fos.openedOk())
            {
                midiFile.writeTo(fos);
                statusBar.setMessage("Exported: " + outFile.getFileName());
            }
        });
}

// AA5 — export each track as a separate SMF inside a chosen directory.
void MainWindow::MainContent::exportMidiStems()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Export MIDI Stems — choose destination folder", juce::File(), "*");
    chooser->launchAsync(juce::FileBrowserComponent::openMode
                         | juce::FileBrowserComponent::canSelectDirectories,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto dir = fc.getResult();
            if (! dir.isDirectory())
            {
                dir = dir.getParentDirectory();
                if (! dir.isDirectory()) return;
            }

            const double bpm = audioEngine.getTempo();
            int exported = 0;
            for (auto& track : audioEngine.getTrackModel().getTracks())
            {
                juce::MidiFile midiFile;
                midiFile.setTicksPerQuarterNote(480);

                juce::MidiMessageSequence tempoTrack;
                auto tempoMsg = juce::MidiMessage::tempoMetaEvent(
                    static_cast<int>(60000000.0 / bpm));
                tempoMsg.setTimeStamp(0.0);
                tempoTrack.addEvent(tempoMsg);
                midiFile.addTrack(tempoTrack);

                juce::MidiMessageSequence midiTrack;
                auto nameMsg = juce::MidiMessage::textMetaEvent(3, track.name);
                nameMsg.setTimeStamp(0.0);
                midiTrack.addEvent(nameMsg);

                auto seq = track.flattenForPlayback();
                for (int i = 0; i < seq.getNumEvents(); ++i)
                {
                    auto msg = seq.getEventPointer(i)->message;
                    msg.setTimeStamp(msg.getTimeStamp() * 480.0);
                    msg.setChannel(track.midiChannel);
                    midiTrack.addEvent(msg);
                }
                midiFile.addTrack(midiTrack);

                // Safe filename
                auto safeName = track.name;
                for (auto& ch : "<>:\"/\\|?*") safeName = safeName.replaceCharacter(ch, '_');
                auto outFile = dir.getChildFile(safeName + ".mid");

                juce::FileOutputStream fos(outFile);
                if (fos.openedOk()) { midiFile.writeTo(fos); ++exported; }
            }
            statusBar.setMessage("Exported " + juce::String(exported) + " stems to " + dir.getFileName());
        });
}

// =============================================================================
// F5 — Audio file import (wav/aif/mp3/flac)
// =============================================================================
void MainWindow::MainContent::importAudioFile()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Import Audio", juce::File(), "*.wav;*.aif;*.aiff;*.flac;*.mp3;*.ogg");
    chooser->launchAsync(juce::FileBrowserComponent::openMode
                         | juce::FileBrowserComponent::canSelectFiles,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto file = fc.getResult();
            if (file.existsAsFile()) loadAudioFile(file);
        });
}

void MainWindow::MainContent::loadAudioFile(const juce::File& file)
{
    juce::AudioFormatManager fmt;
    fmt.registerBasicFormats();

    std::unique_ptr<juce::AudioFormatReader> reader(fmt.createReaderFor(file));
    if (reader == nullptr)
    {
        statusBar.setMessage("Unsupported audio: " + file.getFileName());
        return;
    }

    AudioClip clip;
    clip.sourceSampleRate = reader->sampleRate;
    clip.startBeat = 0.0;
    const int numChannels = juce::jmin(2, (int)reader->numChannels);
    clip.buffer.setSize(numChannels, (int)reader->lengthInSamples);
    reader->read(&clip.buffer, 0, (int)reader->lengthInSamples, 0, true, numChannels > 1);

    const double durationSec = (double)reader->lengthInSamples / reader->sampleRate;
    clip.lengthBeats = durationSec * (audioEngine.getTempo() / 60.0);

    auto& newTrack = audioEngine.getTrackModel().addTrack(file.getFileNameWithoutExtension());
    audioEngine.prebuildTrackSynth(newTrack.id); // T1
    newTrack.audioClips.push_back(std::move(clip));

    mixerPanel.refresh();
    arrangementView.repaint();
    statusBar.setMessage("Imported audio: " + file.getFileName()
                         + " (" + juce::String(durationSec, 2) + "s)");
}

// =============================================================================
// F6 — Render to WAV (offline)
// =============================================================================
void MainWindow::MainContent::renderToWav()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Render to WAV", juce::File(), "*.wav");
    chooser->launchAsync(juce::FileBrowserComponent::saveMode,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto file = fc.getResult();
            if (file == juce::File()) return;
            auto wav = file.withFileExtension("wav");

            // Determine length: longest clip end across all tracks.
            double maxBeats = 16.0;
            for (auto& tr : audioEngine.getTrackModel().getTracks())
                for (auto& c : tr.clips)
                    maxBeats = juce::jmax(maxBeats, c.startBeat + c.lengthBeats);

            const double sr = 44100.0;
            juce::String err;
            const bool wasPlaying = audioEngine.isPlaying();
            if (wasPlaying) audioEngine.stop();

            const bool ok = OfflineRenderer::renderToWav(
                audioEngine.getTrackModel(),
                audioEngine.getTempo(),
                maxBeats,
                sr,
                wav,
                err,
                /*blockSize*/ 512,
                &audioEngine.getPluginChains(),
                &audioEngine.getBusModel());      // V3 — bus + sends

            if (ok)
                statusBar.setMessage("Rendered: " + wav.getFileName());
            else
                statusBar.setMessage("Render failed: " + err);
        });
}

// =============================================================================
// F2 — Plugin browser
// =============================================================================
void MainWindow::MainContent::openPluginBrowser()
{
    PluginBrowser::launchModal(pluginHost,
        [this](const juce::PluginDescription& desc)
        {
            auto& tracks = audioEngine.getTrackModel().getTracks();
            if (tracks.empty())
            {
                statusBar.setMessage("No track to add plugin to");
                return;
            }
            // U7 — prefer selected track from ArrangementView
            Track* targetPtr = nullptr;
            const int selId = arrangementView.getSelectedTrackId();
            if (selId >= 0)
                targetPtr = audioEngine.getTrackModel().getTrack(selId);
            if (targetPtr == nullptr) targetPtr = &tracks.front();
            auto& target = *targetPtr;

            juce::String err;
            auto* device = audioEngine.getDeviceManager().getCurrentAudioDevice();
            const double sr = device ? device->getCurrentSampleRate() : 44100.0;
            const int    bs = device ? device->getCurrentBufferSizeSamples() : 512;

            auto inst = pluginHost.instantiate(desc, sr, bs, err);
            if (inst == nullptr)
            {
                statusBar.setMessage("Plugin load failed: " + err);
                return;
            }

            PluginSlot slot;
            slot.displayName = desc.name;
            slot.pluginUid   = desc.createIdentifierString();
            target.plugins.push_back(std::move(slot));

            const int slotIdx = (int)target.plugins.size() - 1;
            audioEngine.getPluginChains().addPlugin(target.id, slotIdx, std::move(inst));

            statusBar.setMessage("Added " + desc.name + " to " + target.name);
        });
}
