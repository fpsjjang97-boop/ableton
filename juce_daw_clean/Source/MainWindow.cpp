/*
 * MidiGPT DAW - MainWindow.cpp
 */

#include "MainWindow.h"

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
    // Menu bar
    menuBar.setModel(this);
    addAndMakeVisible(menuBar);

    addAndMakeVisible(transportBar);
    addAndMakeVisible(arrangementView);
    addAndMakeVisible(aiPanel);
    addAndMakeVisible(statusBar);

    // Bottom tabs
    bottomTabs.addTab("Piano Roll", juce::Colour(0xFF1A1A2E), &pianoRoll, false);
    bottomTabs.addTab("Mixer",      juce::Colour(0xFF1A1A1A), &mixerPanel, false);
    addAndMakeVisible(bottomTabs);

    // Wire clip selection
    arrangementView.onClipSelected = [this](MidiClip* clip)
    {
        pianoRoll.setClip(clip);
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
    return { "File", "Edit", "Create", "View", "AI", "Help" };
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
            menu.addItem(106, "Export MIDI...",     true, false);
            menu.addSeparator();
            menu.addItem(199, "Quit",               true, false);
            break;

        case 1: // Edit
            menu.addItem(201, "Undo",              true, false);
            menu.addItem(202, "Redo",              true, false);
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

        case 4: // AI
            menu.addItem(501, "Generate Variation", true, false);
            menu.addItem(502, "Analyze Clip",       true, false);
            break;

        case 5: // Help
            menu.addItem(601, "About MidiGPT DAW", true, false);
            menu.addItem(602, "Audio Settings...",  true, false);
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
        case 199: // Quit
            juce::JUCEApplication::getInstance()->systemRequestedQuit();
            break;
        case 301: // Add Track
            audioEngine.getTrackModel().addTrack();
            mixerPanel.refresh();
            arrangementView.repaint();
            break;
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
        default:
            break;
    }
}

// =============================================================================
// MIDI file drag & drop
// =============================================================================
bool MainWindow::MainContent::isInterestedInFileDrag(const juce::StringArray& files)
{
    for (auto& f : files)
        if (f.endsWithIgnoreCase(".mid") || f.endsWithIgnoreCase(".midi"))
            return true;
    return false;
}

void MainWindow::MainContent::filesDropped(const juce::StringArray& files, int, int)
{
    for (auto& f : files)
    {
        if (f.endsWithIgnoreCase(".mid") || f.endsWithIgnoreCase(".midi"))
        {
            loadMidiFile(juce::File(f));
            break;
        }
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
void MainWindow::MainContent::saveProject()
{
    if (currentProjectFile == juce::File())
    { saveProjectAs(); return; }

    juce::DynamicObject::Ptr root = new juce::DynamicObject();
    root->setProperty("version", 1);
    root->setProperty("projectName", "MidiGPT Project");
    root->setProperty("bpm", audioEngine.getTempo());

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

        juce::Array<juce::var> clipArr;
        for (auto& clip : track.clips)
        {
            juce::DynamicObject::Ptr cObj = new juce::DynamicObject();
            cObj->setProperty("startBeat", clip.startBeat);
            cObj->setProperty("lengthBeats", clip.lengthBeats);

            juce::Array<juce::var> noteArr;
            for (int i = 0; i < clip.sequence.getNumEvents(); ++i)
            {
                auto* evt = clip.sequence.getEventPointer(i);
                if (!evt->message.isNoteOn()) continue;

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
            cObj->setProperty("notes", noteArr);
            clipArr.add(juce::var(cObj.get()));
        }
        tObj->setProperty("clips", clipArr);
        trackArr.add(juce::var(tObj.get()));
    }
    root->setProperty("tracks", trackArr);

    auto json = juce::JSON::toString(juce::var(root.get()));
    currentProjectFile.replaceWithText(json);
    statusBar.setMessage("Saved: " + currentProjectFile.getFileName());
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
            if (!file.existsAsFile()) return;

            auto parsed = juce::JSON::parse(file.loadFileAsString());
            if (!parsed.isObject()) return;

            audioEngine.stop();
            audioEngine.rewind();

            // Clear existing tracks
            auto& tm = audioEngine.getTrackModel();
            while (tm.getNumTracks() > 0)
                tm.removeTrack(tm.getTracks().front().id);

            audioEngine.setTempo(parsed.getProperty("bpm", 120.0));

            auto* tracksArr = parsed.getProperty("tracks", juce::var()).getArray();
            if (!tracksArr) return;

            for (auto& tVar : *tracksArr)
            {
                auto& track = tm.addTrack(tVar.getProperty("name", "Track").toString());
                track.midiChannel = tVar.getProperty("channel", 1);
                track.volume = (float)(double)tVar.getProperty("volume", 1.0);
                track.pan = (float)(double)tVar.getProperty("pan", 0.0);
                track.mute = tVar.getProperty("mute", false);
                track.solo = tVar.getProperty("solo", false);
                track.colour = juce::Colour((juce::uint32)(int)tVar.getProperty("colour", (int)0xFF5E81AC));

                auto* clipsArr = tVar.getProperty("clips", juce::var()).getArray();
                if (!clipsArr) continue;
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
                        clip.sequence.updateMatchedPairs();
                    }
                    track.clips.push_back(std::move(clip));
                }
            }

            currentProjectFile = file;
            mixerPanel.refresh();
            arrangementView.repaint();

            auto& tracks = tm.getTracks();
            if (!tracks.empty() && !tracks.front().clips.empty())
                pianoRoll.setClip(&tracks.front().clips.front());

            statusBar.setMessage("Opened: " + file.getFileName());
        });
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
