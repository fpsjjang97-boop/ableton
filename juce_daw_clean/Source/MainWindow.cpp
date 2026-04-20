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
    // Clean exit deletes the crash-recovery file so the next launch does
    // not show the "Restore?" popup. panicSave() writes this file every
    // 2 minutes regardless of crash state; keeping it around after a
    // normal close was confusing (the popup appeared every session).
    auto cleanupRecovery = []()
    {
        auto rec = juce::File::getSpecialLocation(juce::File::tempDirectory)
                       .getChildFile("MidiGPTDAW_recovery.mgp");
        if (rec.existsAsFile()) rec.deleteFile();
    };

    // VV2 — confirm quit if dirty
    auto* content = dynamic_cast<MainContent*>(getContentComponent());
    if (content != nullptr && content->isDirty())
    {
        juce::AlertWindow::showAsync(
            juce::MessageBoxOptions()
                .withIconType(juce::MessageBoxIconType::QuestionIcon)
                .withTitle("Quit")
                .withMessage("Save changes before quitting?")
                .withButton("Save").withButton("Quit").withButton("Cancel"),
            [content, cleanupRecovery](int r) {
                if (r == 1) { content->saveProject(); cleanupRecovery(); juce::JUCEApplication::getInstance()->systemRequestedQuit(); }
                else if (r == 2) { cleanupRecovery(); juce::JUCEApplication::getInstance()->systemRequestedQuit(); }
            });
        return;
    }
    cleanupRecovery();
    juce::JUCEApplication::getInstance()->systemRequestedQuit();
}

// Forward declaration — defined below near Project Save/Load section
static juce::PropertiesFile& getAppProps();

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

    // Bottom tabs — use palette tokens so background follows LookAndFeel
    // instead of baked-in hex. Piano Roll (index 0) is selected explicitly
    // after mount so the component actually paints on first frame; prior
    // to this, the tab row was visible but no content showed until the
    // user clicked a tab.
    bottomTabs.addTab("Piano Roll", juce::Colour(MetallicLookAndFeel::bgPanel),    &pianoRoll,    false);
    bottomTabs.addTab("CC Lane",    juce::Colour(MetallicLookAndFeel::bgPanel),    &ccLane,       false);
    bottomTabs.addTab("Step Seq",   juce::Colour(MetallicLookAndFeel::bgPanel),    &stepSeqView,  false);
    bottomTabs.addTab("Mixer",      juce::Colour(MetallicLookAndFeel::bgPanel),    &mixerPanel,   false);
    addAndMakeVisible(bottomTabs);
    bottomTabs.setCurrentTabIndex(0);     // initial activation (review fix)

    // Wire clip selection + MM6 auto-scroll mixer
    arrangementView.onClipSelected = [this](MidiClip* clip)
    {
        pianoRoll.setClip(clip);
        ccLane.setClip(clip);
        stepSeqView.setClip(clip);
        bottomTabs.setCurrentTabIndex(0);
        mixerPanel.scrollToTrack(arrangementView.getSelectedTrackId());
    };

    // Wire track list changes + NN6 dirty flag
    arrangementView.onTrackListChanged = [this]()
    {
        mixerPanel.refresh();
        arrangementView.repaint();
        markDirty();
    };

    // PPP3 review — surface arrangement-view hints (R arm toggle, etc.)
    // through the window's status bar.
    arrangementView.onStatusMessage = [this](juce::String msg)
    {
        statusBar.setMessage(msg);
    };

    // Default track with a short demo clip so pressing Play on a fresh
    // project immediately produces audible synth output. Previously the
    // clip was empty (silence), which read as "DAW broken" to new users.
    auto& track = audioEngine.getTrackModel().addTrack("MidiGPT Track 1");
    audioEngine.prebuildTrackSynth(track.id); // T1 — GUI-thread alloc
    MidiClip demoClip;
    demoClip.startBeat = 0;
    demoClip.lengthBeats = 16.0;
    {
        // 4-note C major arpeggio over the first beat (C4 E4 G4 C5, 1/4
        // notes). Users can immediately verify audio output and overwrite
        // the notes from the Piano Roll.
        auto addNote = [&](int pitch, double startBeat, double durBeats)
        {
            auto on  = juce::MidiMessage::noteOn (1, pitch, (juce::uint8) 100);
            auto off = juce::MidiMessage::noteOff(1, pitch);
            on .setTimeStamp(startBeat);
            off.setTimeStamp(startBeat + durBeats);
            demoClip.sequence.addEvent(on);
            demoClip.sequence.addEvent(off);
        };
        addNote(60, 0.00, 0.5);   // C4
        addNote(64, 0.50, 0.5);   // E4
        addNote(67, 1.00, 0.5);   // G4
        addNote(72, 1.50, 0.5);   // C5
        demoClip.sequence.updateMatchedPairs();
    }
    track.clips.push_back(demoClip);

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

    // Force a full layout.
    resized();

    // Aggressive first-paint kick. Symptom: individual panels stay invisible
    // until the mouse hovers over them (classic JUCE cold-start: dirty
    // flags set in ctor get cleared by the first OS paint that only redraws
    // the root). Schedule a RECURSIVE repaint on the next message-loop
    // turn so the OS paint event that follows cover every descendant,
    // and repeat once more after 100ms in case some panels were still
    // initializing on the first pass.
    auto kickRepaint = [self = juce::Component::SafePointer<MainContent>(this)]()
    {
        auto* c = self.getComponent();
        if (c == nullptr) return;
        std::function<void(juce::Component*)> walk = [&](juce::Component* n)
        {
            if (n == nullptr) return;
            n->repaint();
            for (int i = 0; i < n->getNumChildComponents(); ++i)
                walk (n->getChildComponent(i));
        };
        walk (c);
        writeDiagLine ("paint-kick cascade fired, children="
                      + juce::String (c->getNumChildComponents()));
    };

    // Window nudge — force the OS compositor to invalidate the full frame.
    // Known JUCE Windows cold-start issue: the first OS paint only covers
    // the root, leaving descendant components unpainted until mouseMove
    // retriggers. Growing and shrinking the top-level window by 1 px causes
    // WM_SIZE → full WM_PAINT on every child. User symptom: "마우스가
    // 지나가거나 클릭해야 보임" — this fires a synthetic "mouse" by
    // resizing immediately.
    auto nudgeWindow = [self = juce::Component::SafePointer<MainContent>(this)]()
    {
        auto* c = self.getComponent();
        if (c == nullptr) return;
        auto* top = c->getTopLevelComponent();
        if (top == nullptr) return;
        const auto b = top->getBounds();
        top->setBounds (b.withWidth (b.getWidth() + 1));
        top->setBounds (b);
        writeDiagLine ("window nudge fired (size="
                      + juce::String (b.getWidth()) + "x"
                      + juce::String (b.getHeight()) + ")");
    };

    juce::MessageManager::callAsync (kickRepaint);
    juce::Timer::callAfterDelay (80,  nudgeWindow);
    juce::Timer::callAfterDelay (160, kickRepaint);
    juce::Timer::callAfterDelay (500, [this]() { runSelfCheck(); });

    // HH5 — check for crash recovery on startup
    checkCrashRecovery();
}

// ---------------------------------------------------------------------------
// Runtime self-check — walks the component tree and logs state to
// daw_debug.log so remote users can share findings without a debugger.
// ---------------------------------------------------------------------------
void MainWindow::MainContent::runSelfCheck()
{
    writeDiagLine ("== self-check ==");
    writeDiagLine ("window size = " + juce::String (getWidth())
                  + " x " + juce::String (getHeight()));

    std::function<void(juce::Component*, int)> walk = [&](juce::Component* n, int depth)
    {
        if (n == nullptr) return;
        juce::String indent;
        for (int i = 0; i < depth; ++i) indent += "  ";
        const auto b = n->getBounds();
        writeDiagLine (indent + "[" + juce::String (depth) + "] '"
            + n->getName() + "' "
            + (n->isVisible() ? "V" : "-")
            + (n->isOpaque() ? "O" : "-")
            + " bounds=" + b.toString()
            + " type=" + juce::String (typeid(*n).name()));
        for (int i = 0; i < n->getNumChildComponents(); ++i)
            walk (n->getChildComponent(i), depth + 1);
    };
    walk (this, 0);
    writeDiagLine ("== /self-check ==");
}

bool MainWindow::MainContent::keyPressed(const juce::KeyPress& key, juce::Component*)
{
    // Space = toggle play/stop
    if (key == juce::KeyPress::spaceKey)
    {
        if (audioEngine.isPlaying())
        {
            arrangementView.setLastStopBeat(audioEngine.getPositionBeats()); // VV6
            audioEngine.stop();
            // DD1 — finalize audio recording on stop
            if (audioEngine.getAudioRecordingTrack() >= 0)
            {
                audioEngine.finalizeAudioRecording();
                arrangementView.repaint();
                statusBar.setMessage("Audio recording saved");
            }
        }
        else if (audioEngine.getPositionBeats() > 0.001)
        {
            // QQ2 — second stop: return to start
            audioEngine.rewind();
            arrangementView.repaint();
        }
        else
        {
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

    // MM1 — Delete key removes selected clips from JJ4 selection
    if (key == juce::KeyPress::deleteKey || key == juce::KeyPress::backspaceKey)
    {
        if (! arrangementView.selectedClips.empty())
        {
            auto& tracks = audioEngine.getTrackModel().getTracks();
            for (auto* selClip : arrangementView.selectedClips)
            {
                for (auto& trk : tracks)
                {
                    trk.clips.erase(
                        std::remove_if(trk.clips.begin(), trk.clips.end(),
                            [selClip](const MidiClip& c) { return &c == selClip; }),
                        trk.clips.end());
                }
            }
            arrangementView.selectedClips.clear();
            arrangementView.repaint();
            statusBar.setMessage("Deleted selected clips");
            return true;
        }
    }
    // TT6 — Escape deselect all
    if (key == juce::KeyPress::escapeKey)
    {
        arrangementView.selectedClips.clear();
        arrangementView.repaint();
        return true;
    }
    // RR3 — Ctrl+A select all clips
    if (key == juce::KeyPress('a', juce::ModifierKeys::ctrlModifier, 0))
    {
        arrangementView.selectedClips.clear();
        for (auto& trk : audioEngine.getTrackModel().getTracks())
            for (auto& clip : trk.clips)
                arrangementView.selectedClips.push_back(&clip);
        arrangementView.repaint();
        statusBar.setMessage("Selected " + juce::String((int)arrangementView.selectedClips.size()) + " clips");
        return true;
    }
    // OO6 — Home/End navigation
    if (key == juce::KeyPress::homeKey)
    {
        audioEngine.rewind();
        arrangementView.repaint();
        return true;
    }
    if (key == juce::KeyPress::endKey)
    {
        double maxBeat = 0.0;
        for (auto& trk : audioEngine.getTrackModel().getTracks())
            for (auto& c : trk.clips)
                maxBeat = juce::jmax(maxBeat, c.startBeat + c.lengthBeats);
        audioEngine.getMidiEngine().setPositionBeats(maxBeat);
        arrangementView.repaint();
        return true;
    }
    // OO1 — Ctrl+D duplicate selected clips in place
    if (key == juce::KeyPress('d', juce::ModifierKeys::ctrlModifier, 0))
    {
        auto& tracks = audioEngine.getTrackModel().getTracks();
        int duped = 0;
        for (auto* sel : arrangementView.selectedClips)
        {
            if (sel == nullptr) continue;
            for (auto& trk : tracks)
            {
                for (size_t ci = 0; ci < trk.clips.size(); ++ci)
                {
                    if (&trk.clips[ci] == sel)
                    {
                        auto copy = trk.clips[ci];
                        copy.startBeat += copy.lengthBeats;
                        trk.clips.push_back(std::move(copy));
                        ++duped;
                        break;
                    }
                }
            }
        }
        if (duped > 0)
        {
            arrangementView.repaint();
            markDirty();
            statusBar.setMessage("Duplicated " + juce::String(duped) + " clip(s)");
        }
        return true;
    }
    // LL1 — Ctrl+C/V clip clipboard
    if (key == juce::KeyPress('c', juce::ModifierKeys::ctrlModifier, 0))
    {
        auto& sel = arrangementView.selectedClips;
        arrangementView.clipboardClips.clear();
        for (auto* clip : sel)
            if (clip != nullptr)
                arrangementView.clipboardClips.push_back(*clip);
        if (! arrangementView.clipboardClips.empty())
            statusBar.setMessage("Copied " + juce::String((int)arrangementView.clipboardClips.size()) + " clip(s)");
        return true;
    }
    if (key == juce::KeyPress('v', juce::ModifierKeys::ctrlModifier, 0))
    {
        if (arrangementView.clipboardClips.empty()) return true;
        int selId = arrangementView.getSelectedTrackId();
        auto* t = audioEngine.getTrackModel().getTrack(selId);
        if (t == nullptr)
        {
            auto& tracks = audioEngine.getTrackModel().getTracks();
            if (! tracks.empty()) t = &tracks.front();
        }
        if (t != nullptr)
        {
            double pos = audioEngine.getPositionBeats();
            double firstStart = arrangementView.clipboardClips.front().startBeat; // B1
            for (auto clip : arrangementView.clipboardClips)
            {
                clip.startBeat = pos + (clip.startBeat - firstStart);
                t->clips.push_back(std::move(clip));
            }
            arrangementView.repaint();
            statusBar.setMessage("Pasted " + juce::String((int)arrangementView.clipboardClips.size()) + " clip(s)");
        }
        return true;
    }
    // EE5 — Zoom presets: Ctrl+1 = 16 beats, Ctrl+2 = 64, Ctrl+3 = 128
    if (key == juce::KeyPress('1', juce::ModifierKeys::ctrlModifier, 0))
    { arrangementView.setZoomBeats(16.0f); return true; }
    if (key == juce::KeyPress('2', juce::ModifierKeys::ctrlModifier, 0))
    { arrangementView.setZoomBeats(64.0f); return true; }
    if (key == juce::KeyPress('3', juce::ModifierKeys::ctrlModifier, 0))
    { arrangementView.setZoomBeats(128.0f); return true; }
    // GG5 — ? key = shortcut overlay
    if (key == juce::KeyPress('/', juce::ModifierKeys::shiftModifier, '?')
        || key == juce::KeyPress(juce::KeyPress::F1Key))
    {
        juce::String help;
        help << "=== Keyboard Shortcuts ===\n\n"
             << "Space         Play / Stop / Rewind\n"
             << "Ctrl+S        Save project\n"
             << "Ctrl+O        Open project\n"
             << "Ctrl+N        New project\n"
             << "Ctrl+T        Add track\n"
             << "Ctrl+Z        Undo\n"
             << "Ctrl+Y        Redo\n"
             << "Ctrl+C/V      Copy / Paste clips\n"
             << "Ctrl+D        Duplicate selected clips\n"
             << "Ctrl+A        Select all clips\n"
             << "Ctrl+0        Zoom to fit\n"
             << "Ctrl+1/2/3    Zoom 16/64/128 beats\n"
             << "Ctrl+L        Scroll to playhead\n"
             << "Delete        Delete selected clips\n"
             << "Home / End    Go to start / end\n"
             << "F             Follow playhead toggle\n"
             << "L             Loop toggle\n"
             << "Shift+Ruler   Set loop region\n"
             << "T             Tempo tap\n"
             << "Q / Shift+Q   Quantize / Humanize\n"
             << "Up/Down       Transpose (Shift=octave)\n"
             << "F1 / ?        This help\n";

        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::InfoIcon,
            "Keyboard Shortcuts", help);
        return true;
    }
    // GG4 — L key = toggle loop
    if (key == juce::KeyPress('l') && ! key.getModifiers().isCtrlDown())
    {
        auto& me = audioEngine.getMidiEngine();
        if (me.isLooping())
        {
            me.setLooping(false);
            statusBar.setMessage("Loop OFF");
        }
        else
        {
            if (me.getLoopEnd() <= me.getLoopStart())
                me.setLoopRegion(0.0, 16.0);
            me.setLooping(true);
            statusBar.setMessage("Loop ON (" +
                juce::String(me.getLoopStart(), 1) + " - " +
                juce::String(me.getLoopEnd(), 1) + " beats)");
        }
        arrangementView.repaint();
        return true;
    }
    // QQ3 — Ctrl+L = scroll to playhead
    if (key == juce::KeyPress('l', juce::ModifierKeys::ctrlModifier, 0))
    {
        double pos = audioEngine.getPositionBeats();
        arrangementView.setZoomBeats(arrangementView.getBeatsVisible()); // keep zoom
        // Center playhead in view
        float newScroll = (float)(pos - arrangementView.getBeatsVisible() * 0.5);
        arrangementView.setScrollX(juce::jmax(0.0f, newScroll));
        return true;
    }
    // OO3 — Ctrl+0 = zoom to fit all content
    if (key == juce::KeyPress('0', juce::ModifierKeys::ctrlModifier, 0))
    {
        double maxBeat = 16.0;
        for (auto& trk : audioEngine.getTrackModel().getTracks())
        {
            for (auto& c : trk.clips)
                maxBeat = juce::jmax(maxBeat, c.startBeat + c.lengthBeats);
            for (auto& a : trk.audioClips)
                maxBeat = juce::jmax(maxBeat, a.startBeat + a.lengthBeats);
        }
        arrangementView.setZoomBeats((float)(maxBeat + 4.0));
        return true;
    }
    // FF6 — T key = tempo tap
    if (key == juce::KeyPress('t') && ! key.getModifiers().isCtrlDown())
    {
        transportBar.handleTap();
        return true;
    }
    // F key = toggle follow playhead
    if (key == juce::KeyPress('f'))
    {
        static bool follow = true;
        follow = !follow;
        arrangementView.setFollowPlayhead(follow);
        statusBar.setMessage(follow ? "Follow playhead ON" : "Follow playhead OFF");
        return true;
    }

    return false;
}

// NN6 — mark project as dirty (unsaved changes)
void MainWindow::MainContent::markDirty()
{
    if (! projectDirty)
    {
        projectDirty = true;
        // UU6 — filename + dirty indicator
        juce::String title = "MidiGPT";
        if (currentProjectFile != juce::File())
            title += " - " + currentProjectFile.getFileNameWithoutExtension();
        title += " *";
        if (auto* w = findParentComponentOfClass<MainWindow>())
            w->setName(title);
    }
}

// GG6 — begin undo group: if same name and < 500ms since last, reuse transaction
void MainWindow::MainContent::beginUndoGroup(const juce::String& name)
{
    auto now = juce::Time::getMillisecondCounter();
    if (name == lastUndoGroupName && (now - lastUndoGroupTime) < 500)
        return; // reuse current transaction
    undoManager.beginNewTransaction(name);
    lastUndoGroupName = name;
    lastUndoGroupTime = now;
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

    // HH5 — panic save every ~2 min (independent of auto-save)
    static int panicTicks = 0;
    if (++panicTicks >= 30 * 120) // 2 min at 30fps
    {
        panicTicks = 0;
        panicSave();
    }
}

void MainWindow::MainContent::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(MetallicLookAndFeel::bgDarkest));
}

void MainWindow::MainContent::resized()
{
    auto area = getLocalBounds();

    menuBar.setBounds(area.removeFromTop(24));
    transportBar.setBounds(area.removeFromTop(36));
    statusBar.setBounds(area.removeFromBottom(22));

    // AI panel — reverted to RIGHT side; the Sprint 51 left-move caused a
    // ghost double-render we could not isolate. Restore original layout
    // and pursue the Live 11 Browser sidebar via a dedicated redesign later.
    aiPanel.setBounds(area.removeFromRight(250));

    // Bottom multidock tabs.
    bottomTabs.setBounds(area.removeFromBottom(300));

    // Arrangement fills the rest.
    arrangementView.setBounds(area);

    // File-based diagnostic log so we can reason about runtime state
    // without a debugger. Every resized() call appends bounds of the
    // key children. Users can share this file to confirm which build
    // is actually running and what the live layout looks like.
    writeDiagLine ("resized w=" + juce::String (getWidth())
                  + " h=" + juce::String (getHeight())
                  + " ai="  + aiPanel.getBounds().toString()
                  + " tabs=" + bottomTabs.getBounds().toString()
                  + " arr="  + arrangementView.getBounds().toString());

    // Force the active tab's content to lay out + paint immediately. JUCE
    // TabbedComponent caches bounds from the first setCurrentTabIndex,
    // which fires in our ctor before setSize expanded the window; the
    // content stays at 0×0 until the user toggles tabs.
    if (auto* cur = bottomTabs.getCurrentContentComponent())
    {
        const int tabBarH = bottomTabs.getTabBarDepth();
        auto inner = bottomTabs.getLocalBounds().withTrimmedTop(tabBarH);
        cur->setBounds(inner);
        cur->setVisible(true);
        cur->repaint();
        writeDiagLine ("tab content bounds=" + cur->getBounds().toString()
                      + " name='" + juce::String(cur->getName()) + "'");
    }
    else
    {
        writeDiagLine ("tab content NULL — bottomTabs has no current content");
    }
}

juce::File MainWindow::MainContent::getDiagLogFile()
{
    // %APPDATA%\MidiGPT\daw_debug.log — stable path the user can open with
    // Notepad and paste into a bug report.
    auto dir = juce::File::getSpecialLocation (juce::File::userApplicationDataDirectory)
                   .getChildFile ("MidiGPT");
    dir.createDirectory();
    return dir.getChildFile ("daw_debug.log");
}

void MainWindow::MainContent::writeDiagLine (const juce::String& line)
{
    static std::once_flag header;
    auto f = getDiagLogFile();
    std::call_once (header, [&] {
        // Truncate on each run so the file only contains the latest session.
        f.replaceWithText ("[MidiGPT DAW diag log — session started]\n", false, false, "\n");
    });
    f.appendText (juce::Time::getCurrentTime().toISO8601 (true)
                  + "  " + line + "\n", false, false, "\n");
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
            menu.addItem(110, "Export Audio Stems...", true, false); // II6
            menu.addSeparator();
            // Audio→MIDI: surface the existing tools/audio_to_midi pipeline
            // so users can discover it from the standalone app. Item ID 112
            // opens a dialog pointing at scripts/e2e_pipeline.py.
            menu.addItem(112, "Audio → MIDI (external)...", true, false);
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
            menu.addItem(201, "Undo" + juce::String(undoManager.canUndo() ? ": " + undoManager.getUndoDescription() : ""),
                          undoManager.canUndo(), false);
            menu.addItem(202, "Redo" + juce::String(undoManager.canRedo() ? ": " + undoManager.getRedoDescription() : ""),
                          undoManager.canRedo(), false);
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
            menu.addSeparator();
            menu.addItem(303, audioEngine.isAudioRecording()
                ? "Stop Audio Recording" : "Record Audio (selected track)",
                true, audioEngine.isAudioRecording()); // DD1
            menu.addSeparator();
            menu.addItem(304, "Add Marker at Playhead...", true, false); // EE6
            menu.addItem(305, "Clear All Markers",         true, false); // EE6
            break;

        case 3: // View
            menu.addItem(401, "Arrangement",       true, false);
            menu.addItem(402, "Mixer",             true, false);
            menu.addItem(403, "Piano Roll",        true, false);
            menu.addSeparator();
            { // QQ6 — snap selector
                juce::PopupMenu snapMenu;
                snapMenu.addItem(410, "Off",    true, false);
                snapMenu.addItem(411, "1 Bar",  true, false);
                snapMenu.addItem(412, "1 Beat", true, false);
                snapMenu.addItem(413, "1/8",    true, false);
                snapMenu.addItem(414, "1/16",   true, false);
                menu.addSubMenu("Snap to Grid", snapMenu);
            }
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
            menu.addSeparator();
            menu.addItem(605, "Tempo Map Editor...",      true, false); // CC2
            menu.addItem(606, "Time Signature Editor...", true, false); // CC3
            break;
    }
    return menu;
}

void MainWindow::MainContent::menuItemSelected(int menuItemID, int)
{
    switch (menuItemID)
    {
        case 101: // VV1 — confirm if dirty
            if (projectDirty)
            {
                juce::AlertWindow::showAsync(
                    juce::MessageBoxOptions()
                        .withIconType(juce::MessageBoxIconType::QuestionIcon)
                        .withTitle("New Project")
                        .withMessage("Save changes before creating a new project?")
                        .withButton("Save").withButton("Don't Save").withButton("Cancel"),
                    [this](int r) {
                        if (r == 1) { saveProject(); newProject(); }
                        else if (r == 2) newProject();
                    });
            }
            else newProject();
            break;
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
        case 112: // Audio→MIDI pipeline — info dialog (external script)
        {
            juce::AlertWindow::showMessageBoxAsync(
                juce::MessageBoxIconType::InfoIcon,
                "Audio → MIDI",
                "Audio-to-MIDI conversion runs via the Python pipeline:\n\n"
                "    python scripts/e2e_pipeline.py --audio <input.wav> "
                "--output <output.mid>\n\n"
                "The pipeline uses basic_pitch + source-filter refine and "
                "writes a .mid file you can drag into the Arrangement or\n"
                "load with File → Import MIDI.\n\n"
                "A direct in-DAW action is planned for a future sprint.");
            break;
        }
        case 110: // II6 — export audio stems
        {
            auto chooser = std::make_shared<juce::FileChooser>(
                "Export Audio Stems — choose folder", juce::File(), "*");
            chooser->launchAsync(juce::FileBrowserComponent::openMode
                                 | juce::FileBrowserComponent::canSelectDirectories,
                [this, chooser](const juce::FileChooser& fc) {
                    auto dir = fc.getResult();
                    if (! dir.isDirectory()) dir = dir.getParentDirectory();
                    if (! dir.isDirectory()) return;

                    const double sr = 44100.0;
                    double maxBeats = 16.0;
                    for (auto& tr : audioEngine.getTrackModel().getTracks())
                        for (auto& c : tr.clips)
                            maxBeats = juce::jmax(maxBeats, c.startBeat + c.lengthBeats);

                    int exported = 0;
                    for (auto& track : audioEngine.getTrackModel().getTracks())
                    {
                        const int totalSamples = (int)(maxBeats / (audioEngine.getTempo() / 60.0) * sr);
                        if (totalSamples <= 0) continue;

                        juce::AudioBuffer<float> buf(2, totalSamples);
                        buf.clear();

                        auto& syn = audioEngine.getOrCreateTrackSynth(track.id);
                        auto seq = track.flattenForPlayback();
                        const double bps = audioEngine.getTempo() / 60.0;
                        const int blk = 512;
                        for (int pos = 0; pos < totalSamples; pos += blk)
                        {
                            const int nb = juce::jmin(blk, totalSamples - pos);
                            const double bb = (double)pos / sr * bps;
                            const double eb = (double)(pos + nb) / sr * bps;
                            juce::MidiBuffer mb;
                            for (int i = 0; i < seq.getNumEvents(); ++i)
                            {
                                auto* ev = seq.getEventPointer(i);
                                double bt = ev->message.getTimeStamp();
                                if (bt >= bb && bt < eb)
                                    mb.addEvent(ev->message, juce::jlimit(0, nb-1, (int)((bt-bb)/bps*sr)));
                            }
                            juce::AudioBuffer<float> tmp(2, nb);
                            tmp.clear();
                            syn.renderBlock(tmp, mb);
                            for (int ch = 0; ch < 2; ++ch)
                                buf.copyFrom(ch, pos, tmp, ch, 0, nb);
                        }

                        auto safeName = track.name;
                        for (auto& ch : "<>:\"/\\|?*") safeName = safeName.replaceCharacter(ch, '_');
                        auto wavFile = dir.getChildFile(safeName + ".wav");

                        juce::WavAudioFormat wav;
                        auto fos = std::make_unique<juce::FileOutputStream>(wavFile);
                        if (fos->openedOk())
                        {
                            std::unique_ptr<juce::AudioFormatWriter> w(
                                wav.createWriterFor(fos.get(), sr, 2, 16, {}, 0));
                            if (w != nullptr)
                            {
                                fos.release();
                                w->writeFromAudioSampleBuffer(buf, 0, totalSamples);
                                ++exported;
                            }
                        }
                    }
                    statusBar.setMessage("Exported " + juce::String(exported) + " audio stems");
                });
            break;
        }
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
        case 702: openPluginBrowser(); break; // same dialog
        case 705: // BB4 + CC5 — save plugin preset (slot picker if multiple)
        {
            const int selId = arrangementView.getSelectedTrackId();
            auto* t = audioEngine.getTrackModel().getTrack(selId);
            if (t == nullptr || t->plugins.empty())
            { statusBar.setMessage("No plugin on selected track"); break; }

            // CC5 — pick slot if multiple
            int slotToUse = 0;
            if (t->plugins.size() > 1)
            {
                juce::PopupMenu pm;
                for (int s = 0; s < (int)t->plugins.size(); ++s)
                    pm.addItem(s + 1, "[" + juce::String(s + 1) + "] " + t->plugins[(size_t)s].displayName);
                pm.showMenuAsync(juce::PopupMenu::Options(),
                    [this, t](int chosen) {
                        if (chosen <= 0) return;
                        int s = chosen - 1;
                        auto* inst2 = audioEngine.getPluginChains().getPlugin(t->id, s);
                        if (inst2 == nullptr) { statusBar.setMessage("Plugin not loaded"); return; }
                        auto chooser2 = std::make_shared<juce::FileChooser>(
                            "Save Preset", juce::File(), "*.vstpreset;*.bin");
                        chooser2->launchAsync(juce::FileBrowserComponent::saveMode,
                            [this, chooser2, inst2](const juce::FileChooser& fc) {
                                auto f = fc.getResult();
                                if (f == juce::File()) return;
                                juce::MemoryBlock mb;
                                inst2->getStateInformation(mb);
                                if (f.replaceWithData(mb.getData(), mb.getSize()))
                                    statusBar.setMessage("Saved preset: " + f.getFileName());
                            });
                    });
                break;
            }
            auto* inst = audioEngine.getPluginChains().getPlugin(t->id, slotToUse);
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
        case 703: // U6 + CC5 — open editor for chosen plugin slot on selected track
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

            // CC5 — if only 1 slot, open directly; otherwise show picker
            if (t->plugins.size() == 1)
            {
                if (auto* inst = audioEngine.getPluginChains().getPlugin(t->id, 0))
                    PluginEditorManager::instance().openFor(t->id, 0, *inst, t->plugins[0].displayName);
                else
                    statusBar.setMessage("Plugin instance not loaded");
            }
            else
            {
                juce::PopupMenu slotMenu;
                for (int s = 0; s < (int)t->plugins.size(); ++s)
                {
                    auto& slot = t->plugins[(size_t)s];
                    slotMenu.addItem(s + 1,
                        "[" + juce::String(s + 1) + "] " + slot.displayName,
                        audioEngine.getPluginChains().getPlugin(t->id, s) != nullptr);
                }
                slotMenu.showMenuAsync(juce::PopupMenu::Options(),
                    [this, t](int chosen) {
                        if (chosen <= 0) return;
                        int s = chosen - 1;
                        if (auto* inst = audioEngine.getPluginChains().getPlugin(t->id, s))
                            PluginEditorManager::instance().openFor(
                                t->id, s, *inst, t->plugins[(size_t)s].displayName);
                    });
            }
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
        case 303: // DD1 — toggle audio recording on selected track
        {
            if (audioEngine.isAudioRecording())
            {
                audioEngine.stop();
                audioEngine.finalizeAudioRecording();
                arrangementView.repaint();
                statusBar.setMessage("Audio recording saved");
            }
            else
            {
                const int selId = arrangementView.getSelectedTrackId();
                if (selId < 0)
                { statusBar.setMessage("Select a track first"); break; }
                audioEngine.setAudioRecordingTrack(selId);
                if (! audioEngine.isPlaying()) audioEngine.play();
                statusBar.setMessage("Recording audio on track...");
            }
            break;
        }
        case 304: // EE6 — Add marker at playhead
        {
            auto* aw = new juce::AlertWindow("Add Marker", "Marker name:",
                                              juce::MessageBoxIconType::NoIcon);
            aw->addTextEditor("name", "Marker");
            aw->addButton("OK", 1);
            aw->addButton("Cancel", 0);
            aw->enterModalState(true, juce::ModalCallbackFunction::create(
                [this, aw](int r) {
                    if (r == 1)
                    {
                        auto name = aw->getTextEditorContents("name");
                        audioEngine.getMidiEngine().addMarker(
                            audioEngine.getPositionBeats(), name);
                        arrangementView.repaint();
                        statusBar.setMessage("Marker added: " + name);
                    }
                    delete aw;
                }), false);
            break;
        }
        case 305: // EE6 — Clear all markers
            audioEngine.getMidiEngine().clearMarkers();
            arrangementView.repaint();
            statusBar.setMessage("All markers cleared");
            break;
        // QQ6 — snap grid selection
        case 410: arrangementView.setSnapBeats(0.0); statusBar.setMessage("Snap: Off"); break;
        case 411: arrangementView.setSnapBeats(4.0); statusBar.setMessage("Snap: 1 Bar"); break;
        case 412: arrangementView.setSnapBeats(1.0); statusBar.setMessage("Snap: 1 Beat"); break;
        case 413: arrangementView.setSnapBeats(0.5); statusBar.setMessage("Snap: 1/8"); break;
        case 414: arrangementView.setSnapBeats(0.25); statusBar.setMessage("Snap: 1/16"); break;
        case 402: // Mixer (tab index 3 — Piano=0, CC=1, StepSeq=2, Mixer=3)
            bottomTabs.setCurrentTabIndex(3);
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
        case 605: // CC2 — Tempo Map Editor
        {
            auto* aw = new juce::AlertWindow(
                "Tempo Map Editor",
                "Enter tempo changes (one per line):\n"
                "Format: beat bpm  (e.g. \"0 120\" means BPM 120 at beat 0)\n\n"
                "Current map:",
                juce::MessageBoxIconType::NoIcon);

            // Populate with current data
            juce::String current;
            auto& tmap = audioEngine.getMidiEngine().getTempoMap();
            if (tmap.empty())
                current = "0 " + juce::String(audioEngine.getTempo(), 1);
            else
                for (auto& [b, bpm] : tmap)
                    current += juce::String(b, 2) + " " + juce::String(bpm, 1) + "\n";

            aw->addTextEditor("data", current.trim(), "", true);
            aw->getTextEditor("data")->setMultiLine(true, false);
            aw->getTextEditor("data")->setReturnKeyStartsNewLine(true);
            aw->getTextEditor("data")->setSize(300, 120);
            aw->addButton("Apply", 1);
            aw->addButton("Clear All", 2);
            aw->addButton("Cancel", 0);
            aw->enterModalState(true, juce::ModalCallbackFunction::create(
                [this, aw](int r) {
                    if (r == 2) // Clear
                    {
                        audioEngine.getMidiEngine().clearTempoMap();
                        statusBar.setMessage("Tempo map cleared (constant " +
                            juce::String(audioEngine.getTempo(), 1) + " BPM)");
                    }
                    else if (r == 1) // Apply
                    {
                        audioEngine.getMidiEngine().clearTempoMap();
                        auto text = aw->getTextEditorContents("data");
                        juce::StringArray lines;
                        lines.addLines(text);
                        int count = 0;
                        for (auto& line : lines)
                        {
                            auto parts = juce::StringArray::fromTokens(line.trim(), " \t", "");
                            if (parts.size() >= 2)
                            {
                                double beat = parts[0].getDoubleValue();
                                double bpm  = juce::jlimit(20.0, 300.0, parts[1].getDoubleValue());
                                audioEngine.getMidiEngine().addTempoChange(beat, bpm);
                                if (count == 0) audioEngine.setTempo(bpm);
                                ++count;
                            }
                        }
                        statusBar.setMessage("Tempo map: " + juce::String(count) + " change(s)");
                    }
                    delete aw;
                }), false);
            break;
        }
        case 606: // CC3 — Time Signature Editor
        {
            auto* aw = new juce::AlertWindow(
                "Time Signature Editor",
                "Enter time signature changes (one per line):\n"
                "Format: beat num den  (e.g. \"0 4 4\" means 4/4 at beat 0)\n\n"
                "Current map:",
                juce::MessageBoxIconType::NoIcon);

            juce::String current;
            auto& tsmap = audioEngine.getMidiEngine().getTimeSignatureMap();
            if (tsmap.empty())
                current = "0 4 4";
            else
                for (auto& [b, sig] : tsmap)
                    current += juce::String(b, 2) + " " + juce::String(sig.num)
                               + " " + juce::String(sig.den) + "\n";

            aw->addTextEditor("data", current.trim(), "", true);
            aw->getTextEditor("data")->setMultiLine(true, false);
            aw->getTextEditor("data")->setReturnKeyStartsNewLine(true);
            aw->getTextEditor("data")->setSize(300, 120);
            aw->addButton("Apply", 1);
            aw->addButton("Clear All", 2);
            aw->addButton("Cancel", 0);
            aw->enterModalState(true, juce::ModalCallbackFunction::create(
                [this, aw](int r) {
                    if (r == 2)
                    {
                        audioEngine.getMidiEngine().clearTimeSignatureMap();
                        statusBar.setMessage("Time signature map cleared (constant 4/4)");
                    }
                    else if (r == 1)
                    {
                        audioEngine.getMidiEngine().clearTimeSignatureMap();
                        auto text = aw->getTextEditorContents("data");
                        juce::StringArray lines;
                        lines.addLines(text);
                        int count = 0;
                        for (auto& line : lines)
                        {
                            auto parts = juce::StringArray::fromTokens(line.trim(), " \t", "");
                            if (parts.size() >= 3)
                            {
                                double beat = parts[0].getDoubleValue();
                                int num = juce::jlimit(1, 32, parts[1].getIntValue());
                                int den = juce::jlimit(1, 32, parts[2].getIntValue());
                                audioEngine.getMidiEngine().addTimeSignatureChange(beat, num, den);
                                if (count == 0) audioEngine.getMidiEngine().setTimeSignature(num, den);
                                ++count;
                            }
                        }
                        statusBar.setMessage("Time sig map: " + juce::String(count) + " change(s)");
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
            // Z5 — recent file items (170..179)
            if (menuItemID >= 170 && menuItemID < 180)
            {
                int idx = menuItemID - 170;
                if (idx < recentFiles.size() && recentFiles[idx].existsAsFile())
                    loadProjectFromFile(recentFiles[idx]);
            }
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
    int nextChannel = 1; // TT4 — auto-assign channels (skip 10=drums)
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

        // VV5 — extract track name from MIDI meta event
        for (int mi = 0; mi < srcTrack->getNumEvents(); ++mi)
        {
            auto& mm = srcTrack->getEventPointer(mi)->message;
            if (mm.isTextMetaEvent() && mm.getMetaEventType() == 3) // Track Name
            {
                auto tname = mm.getTextFromTextMetaEvent();
                if (tname.isNotEmpty())
                { newTrack.name = tname; break; }
            }
        }

        // TT4 — auto-assign MIDI channel
        newTrack.midiChannel = nextChannel;
        ++nextChannel;
        if (nextChannel == 10) ++nextChannel; // skip drums
        if (nextChannel > 16) nextChannel = 1;

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

        // QQ5 — extract first program change from MIDI track → userProgram
        for (int i = 0; i < srcTrack->getNumEvents(); ++i)
        {
            auto& pm = srcTrack->getEventPointer(i)->message;
            if (pm.isProgramChange())
            {
                newTrack.userProgram = pm.getProgramChangeNumber();
                break;
            }
        }

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
    root->setProperty("version", 4);              // RR6 — adds userProgram, clipName, markers, etc.
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

        // EE6 — markers
        juce::Array<juce::var> mkArr;
        for (auto& mk : audioEngine.getMidiEngine().getMarkers())
        {
            juce::DynamicObject::Ptr o = new juce::DynamicObject();
            o->setProperty("beat", mk.beat);
            o->setProperty("name", mk.name);
            o->setProperty("colour", (int)mk.colour.getARGB());
            mkArr.add(juce::var(o.get()));
        }
        root->setProperty("markers", mkArr);
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
        if (track.userProgram >= 0) tObj->setProperty("userProgram", track.userProgram);
        tObj->setProperty("parentTrackId", track.parentTrackId); // AA6
        tObj->setProperty("isFolder",      track.isFolder);
        tObj->setProperty("collapsed",     track.collapsed);      // BB1
        // RR6 — v4 fields
        if (track.displayHeight != 48) tObj->setProperty("displayHeight", track.displayHeight);
        if (track.frozen) tObj->setProperty("frozen", true);
        if (track.overdub != true) tObj->setProperty("overdub", track.overdub);
        if (track.inputMonitor) tObj->setProperty("inputMonitor", true);

        // U3 — sends
        juce::Array<juce::var> sendsArr;
        for (auto& s : track.sends)
        {
            juce::DynamicObject::Ptr so = new juce::DynamicObject();
            so->setProperty("busId", s.busId);
            so->setProperty("level", (double)s.level);
            so->setProperty("preFader", s.preFader); // EE3
            if (s.sidechain) so->setProperty("sidechain", true); // KK3
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
            if (clip.name.isNotEmpty()) cObj->setProperty("name", clip.name); // MM4
            if (clip.hasCustomColour()) // KK2
                cObj->setProperty("colour", (int)clip.colour.getARGB());
            if (clip.swing > 0.001f) // FF5
                cObj->setProperty("swing", (double)clip.swing);

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
            if (a.fadeInBeats > 0.0)  aObj->setProperty("fadeInBeats", a.fadeInBeats);   // DD2
            if (a.fadeOutBeats > 0.0) aObj->setProperty("fadeOutBeats", a.fadeOutBeats); // DD2
            if (std::abs(a.pitchSemitones) > 0.01f) aObj->setProperty("pitchSemitones", (double)a.pitchSemitones); // PP1
            if (std::abs(a.playbackRate - 1.0) > 0.001) aObj->setProperty("playbackRate", a.playbackRate); // PP1

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
                if (std::abs(pt.curve) > 0.001f) // CC6 — only save non-zero
                    p->setProperty("curve", (double)pt.curve);
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
    projectDirty = false; // NN6
    // UU6 — show filename in title bar
    if (auto* w = findParentComponentOfClass<MainWindow>())
        w->setName("MidiGPT - " + currentProjectFile.getFileNameWithoutExtension());
    // SS5 — show project stats on save
    int totalClips = 0, totalAudio = 0;
    for (auto& t : audioEngine.getTrackModel().getTracks())
    { totalClips += (int)t.clips.size(); totalAudio += (int)t.audioClips.size(); }
    statusBar.setMessage("Saved v4: " + currentProjectFile.getFileName()
        + " (" + juce::String(audioEngine.getTrackModel().getNumTracks()) + " tracks, "
        + juce::String(totalClips) + " clips, "
        + juce::String(totalAudio) + " audio)");
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
            audioEngine.getMidiEngine().clearMarkers(); // EE6
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

            // EE6 — restore markers
            if (auto* mkArr = parsed.getProperty("markers", juce::var()).getArray())
                for (auto& v : *mkArr)
                    audioEngine.getMidiEngine().addMarker(
                        v.getProperty("beat", 0.0),
                        v.getProperty("name", "Marker").toString());

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
                track.userProgram = tVar.getProperty("userProgram", -1);
                track.parentTrackId = tVar.getProperty("parentTrackId", -1); // AA6
                track.isFolder      = tVar.getProperty("isFolder", false);
                track.collapsed     = tVar.getProperty("collapsed", false);  // BB1
                // RR6 — v4 fields
                track.displayHeight  = tVar.getProperty("displayHeight", 48);
                track.frozen         = tVar.getProperty("frozen", false);
                track.overdub        = tVar.getProperty("overdub", true);
                track.inputMonitor   = tVar.getProperty("inputMonitor", false);

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
                            s.preFader = sv.getProperty("preFader", false); // EE3
                            s.sidechain = sv.getProperty("sidechain", false); // KK3
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
                        clip.name = cVar.getProperty("name", "").toString(); // MM4
                        // KK2 + FF5
                        if (cVar.hasProperty("colour"))
                            clip.colour = juce::Colour((juce::uint32)(int)cVar.getProperty("colour", 0));
                        clip.swing = (float)(double)cVar.getProperty("swing", 0.0);

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
                            ac.fadeInBeats  = aVar.getProperty("fadeInBeats", 0.0);  // DD2
                            ac.fadeOutBeats = aVar.getProperty("fadeOutBeats", 0.0); // DD2
                            ac.pitchSemitones = (float)(double)aVar.getProperty("pitchSemitones", 0.0); // PP1
                            ac.playbackRate = aVar.getProperty("playbackRate", 1.0); // PP1
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
                                    pt.curve = (float)(double)pVar.getProperty("curve", 0.0); // CC6
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
            // UU6 — title bar
            if (auto* w = findParentComponentOfClass<MainWindow>())
                w->setName("MidiGPT - " + file.getFileNameWithoutExtension());
            projectDirty = false;
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

                // RR5 — insert program change if user has set an instrument
                if (track.userProgram >= 0)
                {
                    auto pc = juce::MidiMessage::programChange(track.midiChannel, track.userProgram);
                    pc.setTimeStamp(0.0);
                    midiTrack.addEvent(pc);
                }

                auto seq = track.flattenForPlayback();
                for (int i = 0; i < seq.getNumEvents(); ++i)
                {
                    auto msg = seq.getEventPointer(i)->message;
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

                // RR5 — program change for stems
                if (track.userProgram >= 0)
                {
                    auto pc = juce::MidiMessage::programChange(track.midiChannel, track.userProgram);
                    pc.setTimeStamp(0.0);
                    midiTrack.addEvent(pc);
                }

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

    clip.sourceName = file.getFileNameWithoutExtension(); // LL6
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

// HH5 — crash recovery
juce::File MainWindow::MainContent::getCrashRecoveryFile() const
{
    return juce::File::getSpecialLocation(juce::File::tempDirectory)
        .getChildFile("MidiGPTDAW_recovery.mgp");
}

void MainWindow::MainContent::panicSave()
{
    auto recFile = getCrashRecoveryFile();
    auto saved = currentProjectFile;
    currentProjectFile = recFile;
    saveProject();
    currentProjectFile = saved;
}

void MainWindow::MainContent::checkCrashRecovery()
{
    auto recFile = getCrashRecoveryFile();
    if (! recFile.existsAsFile()) return;

    // HH5 — use async message box for crash recovery
    juce::AlertWindow::showAsync(
        juce::MessageBoxOptions()
            .withIconType(juce::MessageBoxIconType::WarningIcon)
            .withTitle("Crash Recovery")
            .withMessage("A recovery file was found. Restore it?")
            .withButton("Restore")
            .withButton("Discard"),
        [this, recFile](int result) {
            if (result == 1) // Restore
            {
                loadProjectFromFile(recFile);
                recFile.deleteFile();
                statusBar.setMessage("Recovered from crash save");
            }
            else // Discard
            {
                recFile.deleteFile();
            }
        });
}
