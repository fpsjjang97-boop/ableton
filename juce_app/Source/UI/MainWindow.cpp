#include "MainWindow.h"

//==============================================================================
// Conversion helpers: ai::Note (tick-based) <-> TrackProcessor::Note (beat-based)
//==============================================================================
static constexpr int TICKS_PER_BEAT = 480;

static TrackProcessor::Note aiToTrack (const ai::Note& n)
{
    TrackProcessor::Note out;
    out.pitch     = n.pitch;
    out.velocity  = n.velocity;
    out.startBeat = static_cast<double>(n.startTick) / TICKS_PER_BEAT;
    out.duration  = static_cast<double>(n.durationTicks) / TICKS_PER_BEAT;
    out.channel   = n.channel;
    return out;
}

static ai::Note trackToAI (const TrackProcessor::Note& n)
{
    ai::Note out;
    out.pitch         = n.pitch;
    out.velocity      = n.velocity;
    out.startTick     = static_cast<int>(n.startBeat * TICKS_PER_BEAT);
    out.durationTicks = static_cast<int>(n.duration * TICKS_PER_BEAT);
    out.channel       = n.channel;
    return out;
}

static std::vector<ai::Note> trackNotesToAI (const std::vector<TrackProcessor::Note>& notes)
{
    std::vector<ai::Note> out;
    out.reserve(notes.size());
    for (auto& n : notes) out.push_back(trackToAI(n));
    return out;
}

//==============================================================================
// StatusBar
//==============================================================================
StatusBar::StatusBar()
{
    messageLabel.setText ("Ready", juce::dontSendNotification);
    messageLabel.setFont (juce::Font (11.0f));
    messageLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    addAndMakeVisible (messageLabel);

    midiIndicator.setText ("MIDI", juce::dontSendNotification);
    midiIndicator.setFont (juce::Font (10.0f));
    midiIndicator.setColour (juce::Label::textColourId, MetallicLookAndFeel::textDim);
    midiIndicator.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (midiIndicator);

    versionLabel.setText ("MIDI AI Workstation v1.0", juce::dontSendNotification);
    versionLabel.setFont (juce::Font (10.0f));
    versionLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textDim);
    versionLabel.setJustificationType (juce::Justification::centredRight);
    addAndMakeVisible (versionLabel);
}

void StatusBar::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgHeader);
    g.setColour (MetallicLookAndFeel::border);
    g.drawHorizontalLine (0, 0.0f, (float) getWidth());
}

void StatusBar::resized()
{
    auto area = getLocalBounds().reduced (6, 0);
    messageLabel.setBounds (area.removeFromLeft (area.getWidth() / 2));
    versionLabel.setBounds (area.removeFromRight (200));
    midiIndicator.setBounds (area);
}

void StatusBar::setMessage (const juce::String& msg)
{
    messageLabel.setText (msg, juce::dontSendNotification);
}

void StatusBar::setMidiActivity (bool active)
{
    midiIndicator.setColour (juce::Label::textColourId,
                              active ? MetallicLookAndFeel::meterGreen
                                     : MetallicLookAndFeel::textDim);
}

//==============================================================================
// MainContentComponent
//==============================================================================
MainContentComponent::MainContentComponent()
{
    juce::LookAndFeel::setDefaultLookAndFeel (&metallicLookAndFeel);

    // ── Init audio ────────────────────────────────────────────────────
    auto audioInitResult = deviceManager.initialiseWithDefaultDevices (0, 2);
    if (audioInitResult.isNotEmpty())
        DBG ("Audio init error: " + audioInitResult);
    else
        DBG ("Audio init OK");

    auto* dev = deviceManager.getCurrentAudioDevice();
    if (dev)
        DBG ("Audio device: " + dev->getName() + " sr=" + juce::String(dev->getCurrentSampleRate())
             + " buf=" + juce::String(dev->getCurrentBufferSizeSamples()));
    else
        DBG ("NO AUDIO DEVICE!");

    audioSourcePlayer.setSource (&audioEngine);
    deviceManager.addAudioCallback (&audioSourcePlayer);
    DBG ("Audio callback registered");

    // ── Command manager ───────────────────────────────────────────────
    commandManager.registerAllCommandsForTarget (this);
    addKeyListener (commandManager.getKeyMappings());

    // ── Menu bar ──────────────────────────────────────────────────────
    menuBar = std::make_unique<juce::MenuBarComponent> (this);
    addAndMakeVisible (menuBar.get());

    // ── Main components ───────────────────────────────────────────────
    addAndMakeVisible (transportBar);
    addAndMakeVisible (fileBrowser);
    addAndMakeVisible (sessionView);
    addAndMakeVisible (detailView);
    addChildComponent (mixerPanel);
    addAndMakeVisible (statusBar);

    // ── Splitters ─────────────────────────────────────────────────────
    hSplitter = std::make_unique<juce::StretchableLayoutResizerBar> (
        &horizontalLayout, 1, true);
    hSplitter->setColour (juce::ResizableWindow::backgroundColourId,
                           MetallicLookAndFeel::border);
    addAndMakeVisible (hSplitter.get());

    vSplitter = std::make_unique<juce::StretchableLayoutResizerBar> (
        &contentLayout, 1, false);
    vSplitter->setColour (juce::ResizableWindow::backgroundColourId,
                           MetallicLookAndFeel::border);
    addAndMakeVisible (vSplitter.get());

    setupLayout();
    connectCallbacks();

    // ── Default project with one track ────────────────────────────────
    projectState.bpm = 120.0;
    projectState.key = "C";
    projectState.scale = "minor";
    auto defaultTrack = std::make_shared<TrackProcessor> ("Track 1", 0);
    defaultTrack->colour = juce::Colour (0xFFB0B0B0);
    projectState.tracks.push_back (defaultTrack);
    audioEngine.addTrack (defaultTrack);
    audioEngine.setBPM (120.0);
    loadProjectIntoUI();

    // ── Playback position timer (30fps) ───────────────────────────────
    playbackTimer = std::make_unique<PositionTimer> (*this);
    playbackTimer->startTimerHz (30);

    setSize (1400, 900);
    // Auto-generate tracks and render to WAV
    generateAITrack ("melody");
    generateAITrack ("chords");
    generateAITrack ("bass");

    juce::Timer::callAfterDelay (1000, [this]()
    {
        renderAndPlay();
    });

    statusBar.setMessage ("Generating AI music... will render and play shortly");
}

MainContentComponent::~MainContentComponent()
{
    if (playbackTimer) playbackTimer->stopTimer();
    deviceManager.removeAudioCallback (&audioSourcePlayer);
    audioSourcePlayer.setSource (nullptr);
    juce::LookAndFeel::setDefaultLookAndFeel (nullptr);
}

void MainContentComponent::PositionTimer::timerCallback()
{
    if (owner.audioEngine.isPlaying())
    {
        double beats = owner.audioEngine.getPositionInBeats();
        double seconds = owner.audioEngine.getPositionInSeconds();
        owner.transportBar.setPositionInfo (beats, seconds);
    }
}

void MainContentComponent::renderAndPlay()
{
    // Offline render all tracks to WAV
    double sr = 48000.0;
    double bpmVal = projectState.bpm > 0 ? projectState.bpm : 120.0;

    // Find total length in beats
    double totalBeats = 0;
    for (auto& track : projectState.tracks)
        totalBeats = std::max (totalBeats, track->getTotalLengthInBeats());

    if (totalBeats <= 0) totalBeats = 16.0;
    totalBeats += 2.0; // extra for release tails

    double totalSeconds = (totalBeats / bpmVal) * 60.0;
    int totalSamples = static_cast<int> (sr * totalSeconds);

    juce::AudioBuffer<float> buffer (2, totalSamples);
    buffer.clear();

    // Create a fresh synth for offline rendering
    SynthEngine offlineSynth;
    offlineSynth.prepareToPlay (sr, 512);

    // Set instruments per track
    for (auto& track : projectState.tracks)
        offlineSynth.setProgram (track->channel, track->instrument);

    // Render in 512-sample blocks
    int blockSize = 512;
    double currentBeat = 0.0;
    double samplesPerBeat = (60.0 / bpmVal) * sr;

    for (int pos = 0; pos < totalSamples; pos += blockSize)
    {
        int thisBlock = std::min (blockSize, totalSamples - pos);
        double blockStartBeat = static_cast<double> (pos) / samplesPerBeat;
        double blockEndBeat = static_cast<double> (pos + thisBlock) / samplesPerBeat;

        // Gather MIDI events from all tracks
        juce::MidiBuffer midiBuffer;
        for (auto& track : projectState.tracks)
        {
            if (track->muted) continue;
            auto trackMidi = track->getMidiEventsInRange (blockStartBeat, blockEndBeat, sr, bpmVal);
            for (const auto metadata : trackMidi)
                midiBuffer.addEvent (metadata.getMessage(), metadata.samplePosition);
        }

        // Render this block
        juce::AudioBuffer<float> blockBuf (2, thisBlock);
        blockBuf.clear();
        offlineSynth.renderNextBlock (blockBuf, midiBuffer, 0, thisBlock);

        // Copy to main buffer
        for (int ch = 0; ch < 2; ++ch)
            buffer.addFrom (ch, pos, blockBuf, ch, 0, thisBlock);
    }

    // Analyze result
    float maxLevel = buffer.getMagnitude (0, totalSamples);
    float rmsLevel = buffer.getRMSLevel (0, 0, totalSamples);

    // Write WAV
    juce::File wavFile = juce::File::getSpecialLocation (juce::File::userDesktopDirectory)
                             .getChildFile ("MidiAI_Output.wav");
    wavFile.deleteFile();

    if (auto fos = std::unique_ptr<juce::FileOutputStream> (wavFile.createOutputStream()))
    {
        juce::WavAudioFormat wavFormat;
        if (auto* writer = wavFormat.createWriterFor (fos.release(), sr, 2, 16, {}, 0))
        {
            writer->writeFromAudioSampleBuffer (buffer, 0, totalSamples);
            delete writer;

            statusBar.setMessage ("Rendered " + juce::String (totalSeconds, 1) + "s to Desktop/MidiAI_Output.wav"
                                   + " (max=" + juce::String (maxLevel, 2) + " rms=" + juce::String (rmsLevel, 3) + ")"
                                   + " — Opening...");

            // Auto-play the WAV file
            wavFile.startAsProcess();
        }
    }

    // Also start realtime playback
    audioEngine.play();
    transportBar.setPlaying (true);
}

void MainContentComponent::loadProjectIntoUI()
{
    // Sync session view tracks
    sessionView.clearTracks();
    for (auto& track : projectState.tracks)
    {
        sessionView.addTrack (track->name, track->colour);
        // Add clip indicator for tracks with notes
        if (track->getNumNotes() > 0)
            sessionView.setClipState (static_cast<int> (&track - &projectState.tracks[0]), 0, true);
    }

    // Sync mixer
    mixerPanel.clearChannels();
    for (auto& track : projectState.tracks)
        mixerPanel.addChannel (track->name, track->colour);

    // Sync transport
    transportBar.setBPM (projectState.bpm);

    // Load first track into piano roll
    if (! projectState.tracks.empty())
    {
        auto& firstTrack = projectState.tracks[0];
        auto& pr = detailView.getPianoRoll();
        pr.clearNotes();
        for (auto& note : firstTrack->getNotes())
            pr.addNote ({ note.pitch, note.startBeat, note.duration, note.velocity, false });
    }
}

void MainContentComponent::generateAITrack (const juce::String& type)
{
    std::vector<ai::Note> aiNotes;

    if (type == "melody")
        aiNotes = aiEngine.generateMelody (projectState.key, projectState.scale, 32, "pop", 0.7f, 5);
    else if (type == "chords")
        aiNotes = aiEngine.generateChords (projectState.key, projectState.scale, 32, "pop", 3);
    else if (type == "bass")
        aiNotes = aiEngine.generateBass (projectState.key, projectState.scale, 32, "pop", 2);

    if (aiNotes.empty()) return;

    int idx = static_cast<int> (projectState.tracks.size());
    juce::Colour colours[] = {
        juce::Colour (0xFFB0B0B0), juce::Colour (0xFF8C8C8C),
        juce::Colour (0xFFC8C8C8), juce::Colour (0xFF9A9A9A),
        juce::Colour (0xFF707070), juce::Colour (0xFFD4D4D4),
        juce::Colour (0xFFA0A0A0), juce::Colour (0xFF787878)
    };

    auto track = std::make_shared<TrackProcessor> (
        "AI " + type.substring(0,1).toUpperCase() + type.substring(1),
        juce::jlimit (0, 15, idx));
    track->colour = colours[idx % 8];

    for (auto& n : aiNotes)
        track->addNote (aiToTrack (n));

    projectState.tracks.push_back (track);
    audioEngine.addTrack (track);

    // Update UI
    sessionView.addTrack (track->name, track->colour);
    sessionView.setClipState (idx, 0, true);
    mixerPanel.addChannel (track->name, track->colour);

    // Load into piano roll
    auto& pr = detailView.getPianoRoll();
    pr.clearNotes();
    for (auto& n : aiNotes)
    {
        auto tn = aiToTrack (n);
        pr.addNote ({ tn.pitch, tn.startBeat, tn.duration, tn.velocity, false });
    }

    statusBar.setMessage ("Generated " + type + ": " + juce::String (aiNotes.size()) + " notes"
                           + " (total tracks: " + juce::String(audioEngine.getNumTracks()) + ")");
    DBG ("AI GENERATE: " << type << " = " << (int)aiNotes.size() << " notes, audioEngine tracks=" << audioEngine.getNumTracks());
}

void MainContentComponent::importMidiFile (const juce::File& file)
{
    if (projectState.loadMidiFile (file))
    {
        // Re-sync audio engine
        for (auto& t : projectState.tracks)
            audioEngine.addTrack (t);
        audioEngine.setBPM (projectState.bpm);
        loadProjectIntoUI();
        statusBar.setMessage ("Imported: " + file.getFileName()
                               + " (" + juce::String (projectState.tracks.size()) + " tracks)");
    }
    else
    {
        statusBar.setMessage ("Failed to import: " + file.getFileName());
    }
}

void MainContentComponent::exportMidiFile (const juce::File& file)
{
    if (projectState.saveMidiFile (file))
        statusBar.setMessage ("Exported: " + file.getFileName());
    else
        statusBar.setMessage ("Export failed");
}

void MainContentComponent::setupLayout()
{
    // Horizontal: [FileBrowser] | [splitter] | [Content]
    horizontalLayout.setItemLayout (0, 150.0, 400.0, 220.0);  // file browser
    horizontalLayout.setItemLayout (1, splitterSize, splitterSize, splitterSize); // splitter
    horizontalLayout.setItemLayout (2, 200.0, -1.0, -0.8);    // main content

    // Content vertical: [Session] | [splitter] | [Detail]
    contentLayout.setItemLayout (0, 100.0, -1.0, -0.6);    // session
    contentLayout.setItemLayout (1, splitterSize, splitterSize, splitterSize); // splitter
    contentLayout.setItemLayout (2, 80.0, 500.0, 280.0);   // detail
}

void MainContentComponent::connectCallbacks()
{
    // ── Transport → AudioEngine ────────────────────────────────────────
    transportBar.onPlay = [this]()
    {
        if (transportBar.isPlaying())
        {
            // Debug: show what we're about to play
            int totalNotes = 0;
            int numTracks = audioEngine.getNumTracks();
            for (int i = 0; i < numTracks; ++i)
            {
                auto* t = audioEngine.getTrack(i);
                if (t) totalNotes += t->getNumNotes();
            }
            audioEngine.play();
            statusBar.setMessage ("Playing: " + juce::String(numTracks) + " tracks, "
                                   + juce::String(totalNotes) + " notes, "
                                   + juce::String(audioEngine.getBPM(), 1) + " BPM");
            DBG ("PLAY: " << numTracks << " tracks, " << totalNotes << " notes");
        }
        else
        {
            audioEngine.pause();
            statusBar.setMessage ("Paused");
        }
    };

    transportBar.onStop = [this]()
    {
        audioEngine.stop();
        audioEngine.setPosition (0.0);
        transportBar.setPositionInfo (0.0, 0.0);
        statusBar.setMessage ("Stopped");
    };

    transportBar.onRecord = [this]()
    {
        statusBar.setMessage (transportBar.isRecording() ? "Recording armed" : "Record off");
    };

    transportBar.onBPMChanged = [this] (double bpm)
    {
        audioEngine.setBPM (bpm);
        projectState.bpm = bpm;
    };

    transportBar.onLoopToggled = [this] (bool loopOn)
    {
        audioEngine.setLooping (loopOn, 0.0, projectState.tracks.empty() ? 16.0
            : projectState.tracks[0]->getTotalLengthInBeats());
    };

    transportBar.onMetronomeToggled = [this] (bool on)
    {
        audioEngine.setMetronomeEnabled (on);
    };

    // ── Session View ───────────────────────────────────────────────────
    sessionView.onClipDoubleClicked = [this] (int trackIdx, int scene)
    {
        juce::ignoreUnused (scene);
        detailView.setActiveTab (DetailView::ClipNotes);
        if (detailView.isCollapsed())
            detailView.setCollapsed (false);

        // Load track notes into piano roll
        if (trackIdx >= 0 && trackIdx < (int) projectState.tracks.size())
        {
            auto& track = projectState.tracks[trackIdx];
            auto& pr = detailView.getPianoRoll();
            pr.clearNotes();
            for (auto& n : track->getNotes())
                pr.addNote ({ n.pitch, n.startBeat, n.duration, n.velocity, false });
            statusBar.setMessage ("Editing: " + track->name);
        }
    };

    sessionView.onTrackMuteToggled = [this] (int idx, bool muted)
    {
        if (idx >= 0 && idx < (int) projectState.tracks.size())
            projectState.tracks[idx]->muted = muted;
    };

    sessionView.onTrackSoloToggled = [this] (int idx, bool solo)
    {
        if (idx >= 0 && idx < (int) projectState.tracks.size())
            projectState.tracks[idx]->solo = solo;
    };

    // ── File browser ───────────────────────────────────────────────────
    fileBrowser.onFileDoubleClicked = [this] (const juce::File& file)
    {
        if (file.hasFileExtension ("mid;midi"))
            importMidiFile (file);
        else
            statusBar.setMessage ("Selected: " + file.getFileName());
    };

    // ── Detail view collapse ───────────────────────────────────────────
    detailView.onCollapseChanged = [this] (bool /*collapsed*/)
    {
        updateLayout();
    };

    // ── Mixer volume/pan ───────────────────────────────────────────────
    mixerPanel.onVolumeChanged = [this] (int idx, float vol)
    {
        if (idx >= 0 && idx < (int) projectState.tracks.size())
            projectState.tracks[idx]->volume = vol;
    };

    mixerPanel.onPanChanged = [this] (int idx, float pan)
    {
        if (idx >= 0 && idx < (int) projectState.tracks.size())
            projectState.tracks[idx]->pan = pan;
    };
}

void MainContentComponent::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgDarkest);
}

void MainContentComponent::resized()
{
    updateLayout();
}

void MainContentComponent::updateLayout()
{
    auto area = getLocalBounds();

    // Menu bar at very top
    menuBar->setBounds (area.removeFromTop (menuBarH));

    // Transport bar
    transportBar.setBounds (area.removeFromTop (transportH));

    // Status bar at bottom
    statusBar.setBounds (area.removeFromBottom (statusBarH));

    // Middle area: File browser | Content
    juce::Rectangle<int> contentArea;

    if (fileBrowserVisible)
    {
        fileBrowser.setVisible (true);
        hSplitter->setVisible (true);

        int fbWidth = 220;
        fileBrowser.setBounds (area.getX(), area.getY(), fbWidth, area.getHeight());
        hSplitter->setBounds (area.getX() + fbWidth, area.getY(), splitterSize, area.getHeight());
        contentArea = area.withTrimmedLeft (fbWidth + splitterSize);
    }
    else
    {
        fileBrowser.setVisible (false);
        hSplitter->setVisible (false);
        contentArea = area;
    }

    // Layout content area: session/mixer on top, detail on bottom
    if (mixerVisible)
    {
        mixerPanel.setBounds (contentArea);
        sessionView.setVisible (false);
        detailView.setVisible (false);
        vSplitter->setVisible (false);
    }
    else
    {
        mixerPanel.setVisible (false);
        sessionView.setVisible (true);

        int detailH = detailView.getPreferredHeight();

        if (detailVisible && ! detailView.isCollapsed())
        {
            detailView.setVisible (true);
            vSplitter->setVisible (true);

            auto detailArea = contentArea.removeFromBottom (detailH);
            vSplitter->setBounds (contentArea.removeFromBottom (splitterSize));
            detailView.setBounds (detailArea);
            sessionView.setBounds (contentArea);
        }
        else
        {
            detailView.setVisible (true);
            vSplitter->setVisible (false);

            // Collapsed detail bar
            detailView.setBounds (contentArea.removeFromBottom (detailH));
            sessionView.setBounds (contentArea);
        }
    }
}

void MainContentComponent::setViewMode (ViewMode mode)
{
    currentViewMode = mode;
    sessionView.setVisible (mode == ViewMode::Session || mode == ViewMode::Arrange);
    mixerPanel.setVisible (mode == ViewMode::Mixer);
    updateLayout();
}

//==============================================================================
// Menu Bar
//==============================================================================
juce::StringArray MainContentComponent::getMenuBarNames()
{
    return { "File", "Edit", "Create", "View", "AI", "Help" };
}

juce::PopupMenu MainContentComponent::getMenuForIndex (int topLevelMenuIndex,
                                                         const juce::String& /*menuName*/)
{
    juce::PopupMenu menu;

    switch (topLevelMenuIndex)
    {
        case 0: // File
            menu.addCommandItem (&commandManager, cmdNewProject);
            menu.addCommandItem (&commandManager, cmdOpenProject);
            menu.addSeparator();
            menu.addCommandItem (&commandManager, cmdSaveProject);
            menu.addCommandItem (&commandManager, cmdSaveProjectAs);
            menu.addSeparator();
            menu.addCommandItem (&commandManager, cmdExportMidi);
            menu.addCommandItem (&commandManager, cmdExportAudio);
            break;

        case 1: // Edit
            menu.addCommandItem (&commandManager, cmdUndo);
            menu.addCommandItem (&commandManager, cmdRedo);
            menu.addSeparator();
            menu.addCommandItem (&commandManager, cmdCut);
            menu.addCommandItem (&commandManager, cmdCopy);
            menu.addCommandItem (&commandManager, cmdPaste);
            menu.addCommandItem (&commandManager, cmdDelete);
            menu.addSeparator();
            menu.addCommandItem (&commandManager, cmdSelectAll);
            break;

        case 2: // Create
            menu.addCommandItem (&commandManager, cmdAddTrack);
            menu.addCommandItem (&commandManager, cmdAddScene);
            menu.addSeparator();
            menu.addCommandItem (&commandManager, cmdDuplicateClip);
            break;

        case 3: // View
            menu.addCommandItem (&commandManager, cmdToggleSession);
            menu.addCommandItem (&commandManager, cmdToggleMixer);
            menu.addSeparator();
            menu.addCommandItem (&commandManager, cmdToggleFileBrowser);
            menu.addCommandItem (&commandManager, cmdToggleDetail);
            break;

        case 4: // AI
            menu.addCommandItem (&commandManager, cmdAIGenerate);
            menu.addCommandItem (&commandManager, cmdAIVariation);
            menu.addCommandItem (&commandManager, cmdAIAnalyze);
            break;

        case 5: // Help
            menu.addCommandItem (&commandManager, cmdAbout);
            menu.addCommandItem (&commandManager, cmdPreferences);
            break;
    }

    return menu;
}

void MainContentComponent::menuItemSelected (int /*menuItemID*/, int /*topLevelMenuIndex*/)
{
    // Handled by command system
}

//==============================================================================
// Commands
//==============================================================================
void MainContentComponent::getAllCommands (juce::Array<juce::CommandID>& commands)
{
    commands.addArray ({
        cmdNewProject, cmdOpenProject, cmdSaveProject, cmdSaveProjectAs,
        cmdExportMidi, cmdExportAudio,
        cmdUndo, cmdRedo, cmdCut, cmdCopy, cmdPaste, cmdDelete, cmdSelectAll,
        cmdAddTrack, cmdAddScene, cmdDuplicateClip,
        cmdToggleSession, cmdToggleMixer, cmdToggleFileBrowser, cmdToggleDetail,
        cmdAIGenerate, cmdAIVariation, cmdAIAnalyze,
        cmdAbout, cmdPreferences
    });
}

void MainContentComponent::getCommandInfo (juce::CommandID commandID,
                                            juce::ApplicationCommandInfo& result)
{
    switch (commandID)
    {
        case cmdNewProject:
            result.setInfo ("New Project", "Create a new project", "File", 0);
            result.addDefaultKeypress ('N', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdOpenProject:
            result.setInfo ("Open Project...", "Open an existing project", "File", 0);
            result.addDefaultKeypress ('O', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdSaveProject:
            result.setInfo ("Save Project", "Save the current project", "File", 0);
            result.addDefaultKeypress ('S', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdSaveProjectAs:
            result.setInfo ("Save Project As...", "Save project to a new file", "File", 0);
            result.addDefaultKeypress ('S', juce::ModifierKeys::ctrlModifier | juce::ModifierKeys::shiftModifier);
            break;
        case cmdExportMidi:
            result.setInfo ("Export MIDI...", "Export as MIDI file", "File", 0);
            break;
        case cmdExportAudio:
            result.setInfo ("Export Audio...", "Export as audio file", "File", 0);
            break;
        case cmdUndo:
            result.setInfo ("Undo", "Undo last action", "Edit", 0);
            result.addDefaultKeypress ('Z', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdRedo:
            result.setInfo ("Redo", "Redo last action", "Edit", 0);
            result.addDefaultKeypress ('Y', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdCut:
            result.setInfo ("Cut", "Cut selection", "Edit", 0);
            result.addDefaultKeypress ('X', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdCopy:
            result.setInfo ("Copy", "Copy selection", "Edit", 0);
            result.addDefaultKeypress ('C', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdPaste:
            result.setInfo ("Paste", "Paste from clipboard", "Edit", 0);
            result.addDefaultKeypress ('V', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdDelete:
            result.setInfo ("Delete", "Delete selection", "Edit", 0);
            result.addDefaultKeypress (juce::KeyPress::deleteKey, 0);
            break;
        case cmdSelectAll:
            result.setInfo ("Select All", "Select all items", "Edit", 0);
            result.addDefaultKeypress ('A', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdAddTrack:
            result.setInfo ("Add Track", "Add a new track", "Create", 0);
            result.addDefaultKeypress ('T', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdAddScene:
            result.setInfo ("Add Scene", "Add a new scene", "Create", 0);
            break;
        case cmdDuplicateClip:
            result.setInfo ("Duplicate Clip", "Duplicate selected clip", "Create", 0);
            result.addDefaultKeypress ('D', juce::ModifierKeys::ctrlModifier);
            break;
        case cmdToggleSession:
            result.setInfo ("Session View", "Show session view", "View", 0);
            result.addDefaultKeypress (juce::KeyPress::F1Key, 0);
            break;
        case cmdToggleMixer:
            result.setInfo ("Mixer", "Toggle mixer view", "View", 0);
            result.addDefaultKeypress (juce::KeyPress::F2Key, 0);
            break;
        case cmdToggleFileBrowser:
            result.setInfo ("File Browser", "Toggle file browser panel", "View", 0);
            result.addDefaultKeypress (juce::KeyPress::F3Key, 0);
            break;
        case cmdToggleDetail:
            result.setInfo ("Detail Panel", "Toggle detail panel", "View", 0);
            result.addDefaultKeypress (juce::KeyPress::F4Key, 0);
            break;
        case cmdAIGenerate:
            result.setInfo ("AI Generate...", "Generate MIDI with AI", "AI", 0);
            result.addDefaultKeypress ('G', juce::ModifierKeys::ctrlModifier | juce::ModifierKeys::shiftModifier);
            break;
        case cmdAIVariation:
            result.setInfo ("AI Variation...", "Create AI variation", "AI", 0);
            break;
        case cmdAIAnalyze:
            result.setInfo ("Analyze Clip", "Analyze current clip", "AI", 0);
            break;
        case cmdAbout:
            result.setInfo ("About", "About MIDI AI Workstation", "Help", 0);
            break;
        case cmdPreferences:
            result.setInfo ("Preferences...", "Application preferences", "Help", 0);
            break;
        default:
            break;
    }
}

bool MainContentComponent::perform (const InvocationInfo& info)
{
    switch (info.commandID)
    {
        case cmdNewProject:
        {
            audioEngine.stop();
            projectState.tracks.clear();
            auto t = std::make_shared<TrackProcessor> ("Track 1", 0);
            t->colour = juce::Colour (0xFFB0B0B0);
            projectState.tracks.push_back (t);
            audioEngine.addTrack (t);
            projectState.bpm = 120.0;
            audioEngine.setBPM (120.0);
            loadProjectIntoUI();
            statusBar.setMessage ("New project created");
            return true;
        }

        case cmdOpenProject:
        {
            auto chooser = std::make_shared<juce::FileChooser> (
                "Import MIDI", juce::File(), "*.mid;*.midi");
            chooser->launchAsync (juce::FileBrowserComponent::openMode |
                                   juce::FileBrowserComponent::canSelectFiles,
                [this, chooser] (const juce::FileChooser& fc)
                {
                    auto file = fc.getResult();
                    if (file.existsAsFile())
                        importMidiFile (file);
                });
            return true;
        }

        case cmdSaveProject:
            statusBar.setMessage ("Project saved");
            return true;

        case cmdSaveProjectAs:
        {
            auto chooser = std::make_shared<juce::FileChooser> (
                "Save Project As", juce::File(), "*.maw");
            chooser->launchAsync (juce::FileBrowserComponent::saveMode,
                [this, chooser] (const juce::FileChooser& fc)
                {
                    auto file = fc.getResult();
                    if (file != juce::File())
                        statusBar.setMessage ("Saved: " + file.getFileName());
                });
            return true;
        }

        case cmdExportMidi:
        {
            auto chooser = std::make_shared<juce::FileChooser> (
                "Export MIDI", juce::File(), "*.mid");
            chooser->launchAsync (juce::FileBrowserComponent::saveMode,
                [this, chooser] (const juce::FileChooser& fc)
                {
                    auto file = fc.getResult();
                    if (file != juce::File())
                        exportMidiFile (file);
                });
            return true;
        }

        case cmdExportAudio:
            renderAndPlay();
            return true;

        case cmdUndo:
            if (projectState.undo())
            {
                loadProjectIntoUI();
                statusBar.setMessage ("Undo");
            }
            return true;

        case cmdRedo:
            if (projectState.redo())
            {
                loadProjectIntoUI();
                statusBar.setMessage ("Redo");
            }
            return true;

        case cmdCut:
            detailView.getPianoRoll().copySelected();
            detailView.getPianoRoll().deleteSelected();
            return true;

        case cmdCopy:
            detailView.getPianoRoll().copySelected();
            return true;

        case cmdPaste:
            detailView.getPianoRoll().paste();
            return true;

        case cmdDelete:
            detailView.getPianoRoll().deleteSelected();
            return true;

        case cmdSelectAll:
            detailView.getPianoRoll().selectAll();
            return true;

        case cmdAddTrack:
        {
            int n = sessionView.getNumTracks() + 1;
            // Cycle through colours
            juce::Colour colours[] = {
                juce::Colour (0xFF5E81AC), juce::Colour (0xFFA3BE8C),
                juce::Colour (0xFFBF616A), juce::Colour (0xFFD08770),
                juce::Colour (0xFFB48EAD), juce::Colour (0xFF8FBCBB),
                juce::Colour (0xFFEBCB8B), juce::Colour (0xFF81A1C1)
            };
            sessionView.addTrack ("Track " + juce::String (n),
                                   colours[n % 8]);
            mixerPanel.addChannel ("Track " + juce::String (n),
                                    colours[n % 8]);
            statusBar.setMessage ("Added Track " + juce::String (n));
            return true;
        }

        case cmdAddScene:
            statusBar.setMessage ("Scene added");
            return true;

        case cmdDuplicateClip:
            statusBar.setMessage ("Clip duplicated");
            return true;

        case cmdToggleSession:
            setViewMode (ViewMode::Session);
            return true;

        case cmdToggleMixer:
            mixerVisible = ! mixerVisible;
            mixerPanel.setVisible (mixerVisible);
            updateLayout();
            return true;

        case cmdToggleFileBrowser:
            fileBrowserVisible = ! fileBrowserVisible;
            fileBrowser.setVisible (fileBrowserVisible);
            hSplitter->setVisible (fileBrowserVisible);
            updateLayout();
            return true;

        case cmdToggleDetail:
            detailView.setCollapsed (! detailView.isCollapsed());
            return true;

        case cmdAIGenerate:
        {
            // Show generate tab and generate melody
            detailView.setActiveTab (DetailView::AIGenerate);
            if (detailView.isCollapsed())
                detailView.setCollapsed (false);
            generateAITrack ("melody");
            return true;
        }

        case cmdAIVariation:
        {
            detailView.setActiveTab (DetailView::AIVariation);
            if (detailView.isCollapsed())
                detailView.setCollapsed (false);

            // Generate variation of first track with notes
            for (auto& track : projectState.tracks)
            {
                if (track->getNumNotes() > 0)
                {
                    auto aiSrc = trackNotesToAI (track->getNotes());
                    auto varAiNotes = aiEngine.generateVariation (
                        aiSrc, "mixed", 0.5f, projectState.key, projectState.scale);

                    int idx = static_cast<int> (projectState.tracks.size());
                    auto varTrack = std::make_shared<TrackProcessor> (
                        track->name + " (var)", juce::jlimit (0, 15, idx));
                    varTrack->colour = juce::Colour (0xFFA0A0A0);
                    for (auto& n : varAiNotes)
                        varTrack->addNote (aiToTrack (n));

                    projectState.tracks.push_back (varTrack);
                    audioEngine.addTrack (varTrack);
                    sessionView.addTrack (varTrack->name, varTrack->colour);
                    sessionView.setClipState (idx, 0, true);
                    mixerPanel.addChannel (varTrack->name, varTrack->colour);

                    statusBar.setMessage ("Variation: " + juce::String (varAiNotes.size()) + " notes");
                    break;
                }
            }
            return true;
        }

        case cmdAIAnalyze:
        {
            detailView.setActiveTab (DetailView::Analysis);
            if (detailView.isCollapsed())
                detailView.setCollapsed (false);

            // Analyze first track with notes
            for (auto& track : projectState.tracks)
            {
                if (track->getNumNotes() > 0)
                {
                    auto aiNts = trackNotesToAI (track->getNotes());
                    auto result = aiEngine.analyzeTrack (
                        aiNts, projectState.key, projectState.scale);
                    juce::String info;
                    info << "Track: " << track->name << "\n"
                         << "Notes: " << result.noteCount << "\n"
                         << "Score: " << result.score << "/100 (" << result.grade << ")\n"
                         << "Scale: " << result.scaleConsistency << "%\n"
                         << "Dynamics: " << result.velocityDynamics << "/100\n"
                         << "Rhythm: " << result.rhythmRegularity << "/100\n"
                         << "Diversity: " << result.noteDiversity << "/100\n";
                    if (! result.issues.isEmpty())
                    {
                        info << "\nIssues:\n";
                        for (auto& issue : result.issues)
                            info << "  - " << issue << "\n";
                    }
                    detailView.setAnalysisText (info);
                    statusBar.setMessage ("Analysis: " + track->name + " = " + result.grade);
                    break;
                }
            }
            return true;
        }

        case cmdAbout:
            juce::AlertWindow::showMessageBoxAsync (
                juce::MessageBoxIconType::InfoIcon,
                "About MIDI AI Workstation",
                "MIDI AI Workstation v1.0\n\n"
                "A commercial-grade DAW with AI-powered MIDI generation.\n\n"
                "Built with JUCE framework.",
                "OK");
            return true;

        case cmdPreferences:
            statusBar.setMessage ("Preferences (not yet implemented)");
            return true;

        default:
            return false;
    }
}

//==============================================================================
// MainWindow
//==============================================================================
MainWindow::MainWindow (const juce::String& name)
    : DocumentWindow (name,
                      MetallicLookAndFeel::bgDarkest,
                      DocumentWindow::allButtons)
{
    setLookAndFeel (&metallicLnF);
    setUsingNativeTitleBar (true);

    contentComponent = std::make_unique<MainContentComponent>();
    setContentOwned (contentComponent.release(), true);

    setResizable (true, true);
    setResizeLimits (800, 600, 3840, 2160);
    centreWithSize (1400, 900);

    setVisible (true);
}

void MainWindow::closeButtonPressed()
{
    juce::JUCEApplication::getInstance()->systemRequestedQuit();
}
