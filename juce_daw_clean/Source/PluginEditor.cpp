/*
 * MidiGPT VST3 Plugin — PluginEditor.cpp
 *
 * Plugin UI: style / temperature / variations + generate button,
 * server-health and captured-MIDI feedback (Sprint 32 WW5),
 * Input/Output piano-roll dual pane + Export + LoRA hot-swap +
 * Progress overlay + Server Info (Sprint 33 XX2~XX6).
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include "PluginEditor.h"

MidiGPTEditor::MidiGPTEditor (MidiGPTProcessor& p)
    : AudioProcessorEditor (&p),
      processorRef (p),
      presetManager (std::make_unique<PresetManager> (p.parameters))
{
    // --- YY6 Theme: start in dark mode, remember via state ------------------
    customLookAndFeel = std::make_unique<juce::LookAndFeel_V4> (
        juce::LookAndFeel_V4::getDarkColourScheme());
    setLookAndFeel (customLookAndFeel.get());

    // --- Piano roll panes ---------------------------------------------------
    inputRoll.setTitle ("Input (Captured)");
    inputRoll.setEmptyPlaceholder ("MIDI 재생/입력 또는 .mid 파일을 여기로 드롭");
    addAndMakeVisible (inputRoll);

    outputRoll.setTitle ("Output (Generated)");
    outputRoll.setEmptyPlaceholder ("Generate 버튼을 누르면 결과가 표시됩니다");
    addAndMakeVisible (outputRoll);

    // --- Temperature slider --------------------------------------------------
    temperatureSlider.setSliderStyle (juce::Slider::LinearHorizontal);
    temperatureSlider.setTextBoxStyle (juce::Slider::TextBoxRight, false, 60, 20);
    temperatureSlider.setRange (0.5, 1.5, 0.01);
    addAndMakeVisible (temperatureSlider);
    addAndMakeVisible (temperatureLabel);
    temperatureLabel.attachToComponent (&temperatureSlider, true);
    temperatureAttachment = std::make_unique<SliderAttachment> (
        processorRef.parameters, "temperature", temperatureSlider);

    // --- Num variations slider -----------------------------------------------
    numVariationsSlider.setSliderStyle (juce::Slider::IncDecButtons);
    numVariationsSlider.setTextBoxStyle (juce::Slider::TextBoxRight, false, 60, 20);
    numVariationsSlider.setRange (1, 5, 1);
    addAndMakeVisible (numVariationsSlider);
    addAndMakeVisible (numVariationsLabel);
    numVariationsLabel.attachToComponent (&numVariationsSlider, true);
    numVariationsAttachment = std::make_unique<SliderAttachment> (
        processorRef.parameters, "numVariations", numVariationsSlider);

    // --- Style selector (XX4 LoRA hot-swap trigger) --------------------------
    styleBox.addItemList (juce::StringArray { "base", "jazz", "citypop", "metal", "classical" }, 1);
    addAndMakeVisible (styleBox);
    addAndMakeVisible (styleLabel);
    styleLabel.attachToComponent (&styleBox, true);
    styleAttachment = std::make_unique<ComboAttachment> (
        processorRef.parameters, "style", styleBox);
    // onChange fires AFTER the VTS attachment has updated the parameter,
    // so processorRef.parameters reflects the new style when we read it.
    styleBox.onChange = [this] { onStyleChanged(); };

    // --- Generate / Cancel buttons ------------------------------------------
    generateButton.setColour (juce::TextButton::buttonColourId, juce::Colour (0xFF4A90D9));
    generateButton.onClick = [this]
    {
        processorRef.requestVariation();
        setGenerationInFlight (true);
    };
    addAndMakeVisible (generateButton);

    cancelButton.setColour (juce::TextButton::buttonColourId, juce::Colour (0xFF703030));
    cancelButton.onClick = [this]
    {
        // AIBridge::cancelPendingRequests signals the worker to exit after
        // its current read — we can't abort a JUCE blocking HTTP read mid-flight,
        // so this is "no callback will fire" rather than "socket closed now".
        // The UI goes back to idle immediately.
        processorRef.clearCapturedInput();   // also drops prompt; avoids accidental resume
        setGenerationInFlight (false);
        statusLabel.setText ("취소됨", juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::grey);
    };
    cancelButton.setVisible (false);
    addAndMakeVisible (cancelButton);

    // --- Clear captured-input button -----------------------------------------
    clearButton.onClick = [this]
    {
        processorRef.clearCapturedInput();
        inputRoll.setSequence (juce::MidiMessageSequence());
    };
    addAndMakeVisible (clearButton);

    // --- XX3 Export MIDI -----------------------------------------------------
    exportButton.onClick = [this] { onExportMidi(); };
    addAndMakeVisible (exportButton);

    // --- XX6 Server Info -----------------------------------------------------
    infoButton.onClick = [this] { onServerInfo(); };
    addAndMakeVisible (infoButton);

    // --- YY4 Undo / Redo buttons ---------------------------------------------
    undoButton.onClick = [this] { processorRef.undoGeneration(); applyUndoRedoEnable(); };
    redoButton.onClick = [this] { processorRef.redoGeneration(); applyUndoRedoEnable(); };
    addAndMakeVisible (undoButton);
    addAndMakeVisible (redoButton);
    applyUndoRedoEnable();

    // --- YY3 Preset manager UI -----------------------------------------------
    presetBox.setTextWhenNothingSelected ("Load Preset...");
    presetBox.onChange = [this] { onLoadPresetSelected(); };
    addAndMakeVisible (presetBox);
    refreshPresetCombo();

    savePresetButton.onClick = [this] { onSavePreset(); };
    addAndMakeVisible (savePresetButton);

    deletePresetButton.onClick = [this] { onDeletePreset(); };
    addAndMakeVisible (deletePresetButton);

    // --- YY6 Theme toggle ----------------------------------------------------
    themeButton.onClick = [this] { applyTheme (! darkTheme); };
    themeButton.setTooltip ("Toggle dark/light theme");
    addAndMakeVisible (themeButton);

    // --- Status labels -------------------------------------------------------
    statusLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (statusLabel);

    serverStatusLabel.setJustificationType (juce::Justification::centredLeft);
    serverStatusLabel.setColour (juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible (serverStatusLabel);

    capturedCountLabel.setJustificationType (juce::Justification::centredRight);
    capturedCountLabel.setColour (juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible (capturedCountLabel);

    // --- Wire processor callbacks -------------------------------------------
    // SafePointer guard: a status callback may be in the MessageManager queue
    // when the host tears this editor down between request and response
    // (2-20s window). Dispatching the queued lambda on a dead `this` would
    // be UB. SafePointer zeros itself when the component is destroyed, so
    // the lambda short-circuits safely.
    juce::Component::SafePointer<MidiGPTEditor> safeThis (this);
    processorRef.setStatusCallback (
        [safeThis] (MidiGPTProcessor::GenerationStatus st, juce::String msg) mutable
        {
            if (auto* self = safeThis.getComponent())
                self->handleStatus (st, std::move (msg));
        });

    // Populate from any state restored before we attached (host opening a
    // saved project).
    refreshPianoRolls();

    // Poll server health once a second + refresh piano rolls every tick.
    // checkHealth uses a short timeout so the UI thread doesn't stall.
    startTimerHz (1);

    // --- YY1 Resizable window ------------------------------------------------
    // 720×500 is the default; constrainer caps prevent degenerate layouts
    // (piano rolls collapse < ~40px) and over-huge windows that would
    // display awkwardly in plugin host rack panels. resized() already uses
    // proportional widths so scales cleanly between these bounds.
    setResizable (true, true);
    setResizeLimits (580, 420, 1600, 1100);

    // --- YY2 Keyboard shortcuts ----------------------------------------------
    // addKeyListener on this component; also setWantsKeyboardFocus so the
    // host grants focus when we're clicked. CMake already declared
    // EDITOR_WANTS_KEYBOARD_FOCUS TRUE for VST3 hosts that respect it.
    setWantsKeyboardFocus (true);
    addKeyListener (this);

    setSize (720, 520);
}

MidiGPTEditor::~MidiGPTEditor()
{
    // Detach the status callback so the processor doesn't invoke a dead
    // editor if the host tears us down while a request is in flight.
    processorRef.setStatusCallback (nullptr);

    // Must unwire the shared LookAndFeel before our owned customLookAndFeel
    // dtor runs, otherwise child Components retain a stale pointer.
    setLookAndFeel (nullptr);
    removeKeyListener (this);
}

void MidiGPTEditor::paint (juce::Graphics& g)
{
    g.fillAll (getLookAndFeel().findColour (juce::ResizableWindow::backgroundColourId));

    // Title color adapts to theme via LookAndFeel's default text colour.
    g.setColour (getLookAndFeel().findColour (juce::Label::textColourId));
    g.setFont (20.0f);
    g.drawFittedText ("MidiGPT", 0, 10, getWidth(), 28, juce::Justification::centred, 1);

    g.setFont (12.0f);
    g.setColour (getLookAndFeel().findColour (juce::Label::textColourId).withAlpha (0.6f));
    g.drawFittedText ("LLM-driven MIDI variation", 0, 38, getWidth(), 16,
                      juce::Justification::centred, 1);

    // --- YY5 Drag-and-drop hover highlight ----------------------------------
    if (dragHover)
    {
        g.setColour (juce::Colours::limegreen.withAlpha (0.15f));
        g.fillRect (getLocalBounds());
        g.setColour (juce::Colours::limegreen);
        g.drawRect (getLocalBounds().reduced (4), 3);
    }

    // --- XX5 Progress overlay -----------------------------------------------
    if (generationInFlight)
    {
        const auto bounds = getLocalBounds().toFloat();
        g.setColour (juce::Colours::black.withAlpha (0.4f));
        g.fillRect (bounds);

        g.setColour (juce::Colours::white);
        g.setFont (14.0f);
        g.drawFittedText ("Generating...  (Cancel / Esc 로 중단)",
                          bounds.toNearestInt(),
                          juce::Justification::centred, 2);
    }
}

void MidiGPTEditor::resized()
{
    const int margin = 16;
    const int labelW = 100;
    const int controlH = 22;
    int y = 62;

    // YY6 Theme toggle: pinned top-right corner, 24×24
    themeButton.setBounds (getWidth() - margin - 24, 14, 24, 24);

    // Piano roll dual pane (top area) — scales vertically a bit at larger sizes.
    const int rollAreaH = juce::jmax (120, (getHeight() - 280) / 2);
    const int rollGap = 8;
    const int rollW = (getWidth() - margin * 2 - rollGap) / 2;
    inputRoll.setBounds  (margin,                       y, rollW, rollAreaH);
    outputRoll.setBounds (margin + rollW + rollGap,     y, rollW, rollAreaH);
    y += rollAreaH + 14;

    // Parameter controls
    temperatureSlider.setBounds (margin + labelW, y, getWidth() - margin * 2 - labelW, controlH);
    y += controlH + 8;

    numVariationsSlider.setBounds (margin + labelW, y, getWidth() - margin * 2 - labelW, controlH);
    y += controlH + 8;

    styleBox.setBounds (margin + labelW, y, getWidth() - margin * 2 - labelW, controlH);
    y += controlH + 10;

    // --- YY3 Preset row: [combo .................][Save][Delete] ----------
    const int totalW = getWidth() - margin * 2;
    const int buttonGap = 6;
    const int smallBtnW = 72;
    const int presetComboW = totalW - (smallBtnW + buttonGap) * 2;
    presetBox.setBounds        (margin, y, presetComboW, controlH);
    savePresetButton.setBounds (margin + presetComboW + buttonGap,
                                y, smallBtnW, controlH);
    deletePresetButton.setBounds (margin + presetComboW + buttonGap * 2 + smallBtnW,
                                  y, smallBtnW, controlH);
    y += controlH + 14;

    // Action buttons row 1: Generate (primary) + Cancel overlay + Clear + Export + Info
    const int primaryW = totalW * 2 / 5;
    const int secondaryW = (totalW - primaryW - buttonGap * 3) / 3;

    generateButton.setBounds (margin, y, primaryW, 32);
    cancelButton.setBounds   (margin, y, primaryW, 32);        // same spot; visibility toggles
    int x = margin + primaryW + buttonGap;
    clearButton.setBounds  (x, y, secondaryW, 32); x += secondaryW + buttonGap;
    exportButton.setBounds (x, y, secondaryW, 32); x += secondaryW + buttonGap;
    infoButton.setBounds   (x, y, secondaryW, 32);
    y += 32 + 6;

    // Action buttons row 2: Undo / Redo (YY4), filler on right
    const int undoW = 80;
    undoButton.setBounds (margin, y, undoW, 26);
    redoButton.setBounds (margin + undoW + buttonGap, y, undoW, 26);
    y += 26 + 6;

    statusLabel.setBounds (margin, y, totalW, 20);
    y += 22;

    const int bottomW = totalW / 2;
    serverStatusLabel.setBounds (margin, y, bottomW, 18);
    capturedCountLabel.setBounds (margin + bottomW, y, bottomW, 18);
}

void MidiGPTEditor::timerCallback()
{
    const bool ok = healthBridge.checkHealth (500);
    if (ok != serverConnected)
    {
        serverConnected = ok;
        serverStatusLabel.setText (ok ? "Server: connected" : "Server: disconnected",
                                   juce::dontSendNotification);
        serverStatusLabel.setColour (juce::Label::textColourId,
                                     ok ? juce::Colours::limegreen : juce::Colours::red);
        generateButton.setEnabled (ok && ! generationInFlight);
    }

    capturedCountLabel.setText (
        juce::String ("Captured: ") + juce::String (processorRef.getCapturedNoteCount()),
        juce::dontSendNotification);

    refreshPianoRolls();
}

void MidiGPTEditor::refreshPianoRolls()
{
    // These copies are cheap (vector<MidiEventHolder>) for the sizes we deal
    // with in a plugin editor. Called at 1Hz so not hot.
    inputRoll.setSequence  (processorRef.getCapturedInputCopy());
    outputRoll.setSequence (processorRef.getLastGenerated());
}

void MidiGPTEditor::handleStatus (MidiGPTProcessor::GenerationStatus st, juce::String msg)
{
    statusLabel.setText (msg, juce::dontSendNotification);
    switch (st)
    {
        case MidiGPTProcessor::GenerationStatus::Idle:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::grey);
            setGenerationInFlight (false);
            break;
        case MidiGPTProcessor::GenerationStatus::NoInputCaptured:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::orange);
            setGenerationInFlight (false);
            break;
        case MidiGPTProcessor::GenerationStatus::InFlight:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::yellow);
            setGenerationInFlight (true);
            break;
        case MidiGPTProcessor::GenerationStatus::Ready:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
            setGenerationInFlight (false);
            // Refresh output roll immediately so the user sees the result
            // before the next 1Hz tick.
            outputRoll.setSequence (processorRef.getLastGenerated());
            // YY4: history depth may have grown (new generation) or shrunk
            // (undo/redo that fired Ready). Either way refresh buttons.
            applyUndoRedoEnable();
            break;
        case MidiGPTProcessor::GenerationStatus::Error:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
            setGenerationInFlight (false);
            break;
    }
}

void MidiGPTEditor::setGenerationInFlight (bool inFlight)
{
    generationInFlight = inFlight;
    generateButton.setVisible (! inFlight);
    cancelButton.setVisible   (inFlight);
    generateButton.setEnabled (serverConnected && ! inFlight);
    repaint();   // redraw overlay
}

// -----------------------------------------------------------------------------
// XX3 Export MIDI — async FileChooser → write lastGenerated as standard MIDI
// -----------------------------------------------------------------------------
void MidiGPTEditor::onExportMidi()
{
    const auto& seq = processorRef.getLastGenerated();
    if (seq.getNumEvents() == 0)
    {
        statusLabel.setText ("내보낼 생성 결과가 없습니다", juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::orange);
        return;
    }

    // FileChooser must be heap-allocated for async launch (JUCE 6+).
    activeChooser = std::make_unique<juce::FileChooser> (
        "Export MIDI", juce::File(), "*.mid");

    const auto flags = juce::FileBrowserComponent::saveMode
                     | juce::FileBrowserComponent::canSelectFiles
                     | juce::FileBrowserComponent::warnAboutOverwriting;

    juce::Component::SafePointer<MidiGPTEditor> safeThis (this);
    activeChooser->launchAsync (flags,
        [safeThis, seqCopy = seq] (const juce::FileChooser& fc) mutable
        {
            auto file = fc.getResult();
            if (file == juce::File())
                return;   // user cancelled

            if (file.getFileExtension().isEmpty())
                file = file.withFileExtension (".mid");

            juce::MidiFile mf;
            mf.setTicksPerQuarterNote (480);
            mf.addTrack (seqCopy);

            juce::FileOutputStream out (file);
            auto* self = safeThis.getComponent();
            if (! self) return;   // editor destroyed between dialog and callback

            if (! out.openedOk())
            {
                self->statusLabel.setText ("파일 쓰기 실패: " + file.getFullPathName(),
                                           juce::dontSendNotification);
                self->statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
                return;
            }
            if (mf.writeTo (out))
            {
                self->statusLabel.setText ("내보내기 완료: " + file.getFileName(),
                                           juce::dontSendNotification);
                self->statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
            }
            else
            {
                self->statusLabel.setText ("MIDI 직렬화 실패", juce::dontSendNotification);
                self->statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
            }
        });
}

// -----------------------------------------------------------------------------
// XX4 Style change → async LoRA hot-swap
// -----------------------------------------------------------------------------
void MidiGPTEditor::onStyleChanged()
{
    const auto newStyle = styleBox.getText();
    if (newStyle == currentLoraName || loraLoadInFlight || ! serverConnected)
        return;

    loraLoadInFlight = true;
    statusLabel.setText ("LoRA 로드 중: " + newStyle + "...", juce::dontSendNotification);
    statusLabel.setColour (juce::Label::textColourId, juce::Colours::yellow);

    juce::Component::SafePointer<MidiGPTEditor> safeThis (this);
    healthBridge.loadLoraAsync (newStyle,
        [safeThis, newStyle] (bool success, juce::String err) mutable
        {
            auto* self = safeThis.getComponent();
            if (! self) return;   // editor torn down before LoRA response

            self->loraLoadInFlight = false;
            if (success)
            {
                self->currentLoraName = newStyle;
                self->statusLabel.setText ("LoRA 로드 완료: " + newStyle,
                                           juce::dontSendNotification);
                self->statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
            }
            else
            {
                self->statusLabel.setText (err.isNotEmpty() ? err : juce::String ("LoRA 로드 실패"),
                                           juce::dontSendNotification);
                self->statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
            }
        });
}

// -----------------------------------------------------------------------------
// XX6 Server Info dialog
// -----------------------------------------------------------------------------
void MidiGPTEditor::onServerInfo()
{
    auto status = healthBridge.getStatus (2000);
    juce::String body;

    if (! status.isObject())
    {
        body = "서버에 연결할 수 없습니다.\n(http://127.0.0.1:8765)";
    }
    else
    {
        auto format = [] (const juce::String& label, const juce::var& v) -> juce::String
        {
            return label + ": " + (v.toString().isEmpty() ? juce::String ("-") : v.toString()) + "\n";
        };
        body += format ("Model loaded", status.getProperty ("model_loaded", {}));
        body += format ("Model path",   status.getProperty ("model_path",   {}));
        body += format ("Active LoRA",  status.getProperty ("active_lora",  {}));
        body += format ("Device",       status.getProperty ("device",       {}));
        body += format ("Vocab size",   status.getProperty ("vocab_size",   {}));
        body += format ("Block size",   status.getProperty ("block_size",   {}));
        body += format ("Parameters",   status.getProperty ("param_count",  {}));
    }

    juce::AlertWindow::showMessageBoxAsync (
        juce::MessageBoxIconType::InfoIcon,
        "MidiGPT Server Info",
        body);
}

// =============================================================================
// YY2 — Keyboard shortcuts
// =============================================================================
// KeyListener callback. Return true to consume, false to let the component
// chain process it. Plugin hosts vary wildly in what keys they forward to the
// editor; on hosts that swallow keys we at least don't get spurious events.
bool MidiGPTEditor::keyPressed (const juce::KeyPress& key, juce::Component* /*origin*/)
{
    // Space = Generate
    if (key == juce::KeyPress::spaceKey)
    {
        if (generateButton.isEnabled())
            generateButton.triggerClick();
        return true;
    }
    // Esc = Cancel (if in flight)
    if (key == juce::KeyPress::escapeKey)
    {
        if (generationInFlight)
            cancelButton.triggerClick();
        return true;
    }
    // Ctrl/Cmd + E = Export MIDI
    if (key == juce::KeyPress ('e', juce::ModifierKeys::commandModifier, 0))
    {
        onExportMidi();
        return true;
    }
    // Ctrl/Cmd + I = Server Info
    if (key == juce::KeyPress ('i', juce::ModifierKeys::commandModifier, 0))
    {
        onServerInfo();
        return true;
    }
    // Ctrl/Cmd + K = Clear input
    if (key == juce::KeyPress ('k', juce::ModifierKeys::commandModifier, 0))
    {
        clearButton.triggerClick();
        return true;
    }
    // Ctrl/Cmd + Z = Undo, Ctrl/Cmd + Shift + Z = Redo (standard)
    if (key == juce::KeyPress ('z', juce::ModifierKeys::commandModifier, 0))
    {
        undoButton.triggerClick();
        return true;
    }
    if (key == juce::KeyPress ('z', juce::ModifierKeys::commandModifier
                                    | juce::ModifierKeys::shiftModifier, 0))
    {
        redoButton.triggerClick();
        return true;
    }
    return false;
}

// =============================================================================
// YY3 — Preset UI handlers
// =============================================================================
void MidiGPTEditor::refreshPresetCombo()
{
    presetBox.clear (juce::dontSendNotification);
    const auto names = presetManager->listPresets();
    for (int i = 0; i < names.size(); ++i)
        presetBox.addItem (names[i], i + 1);
    presetBox.setSelectedId (0, juce::dontSendNotification);   // "Load Preset..." placeholder
}

void MidiGPTEditor::onLoadPresetSelected()
{
    const auto name = presetBox.getText();
    if (name.isEmpty()) return;
    if (presetManager->load (name))
    {
        statusLabel.setText ("프리셋 로드됨: " + name, juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
    }
    else
    {
        statusLabel.setText ("프리셋 로드 실패: " + name, juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
    }
}

void MidiGPTEditor::onSavePreset()
{
    // AlertWindow name prompt — async to keep VST3 hosts happy.
    auto aw = std::make_shared<juce::AlertWindow> (
        "Save Preset", "프리셋 이름을 입력하세요.",
        juce::MessageBoxIconType::QuestionIcon);
    aw->addTextEditor ("name", "preset1");
    aw->addButton ("Save",   1, juce::KeyPress (juce::KeyPress::returnKey));
    aw->addButton ("Cancel", 0, juce::KeyPress (juce::KeyPress::escapeKey));

    juce::Component::SafePointer<MidiGPTEditor> safeThis (this);
    aw->enterModalState (true,
        juce::ModalCallbackFunction::create (
            [aw, safeThis] (int result) mutable
            {
                auto* self = safeThis.getComponent();
                if (self == nullptr) return;
                if (result == 1)
                {
                    const auto name = aw->getTextEditorContents ("name").trim();
                    if (name.isEmpty()) return;
                    if (self->presetManager->save (name))
                    {
                        self->refreshPresetCombo();
                        self->statusLabel.setText ("프리셋 저장: " + name,
                                                   juce::dontSendNotification);
                        self->statusLabel.setColour (juce::Label::textColourId,
                                                     juce::Colours::limegreen);
                    }
                    else
                    {
                        self->statusLabel.setText ("프리셋 저장 실패",
                                                   juce::dontSendNotification);
                        self->statusLabel.setColour (juce::Label::textColourId,
                                                     juce::Colours::red);
                    }
                }
            }));
}

void MidiGPTEditor::onDeletePreset()
{
    const auto name = presetBox.getText();
    if (name.isEmpty()) return;
    if (presetManager->remove (name))
    {
        refreshPresetCombo();
        statusLabel.setText ("프리셋 삭제: " + name, juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
    }
}

// =============================================================================
// YY4 — undo/redo button enable state
// =============================================================================
void MidiGPTEditor::applyUndoRedoEnable()
{
    undoButton.setEnabled (processorRef.undoDepth() > 0);
    redoButton.setEnabled (processorRef.redoDepth() > 0);
}

// =============================================================================
// YY5 — FileDragAndDropTarget (drag a .mid onto the editor to set as prompt)
// =============================================================================
bool MidiGPTEditor::isInterestedInFileDrag (const juce::StringArray& files)
{
    for (const auto& f : files)
        if (f.endsWithIgnoreCase (".mid") || f.endsWithIgnoreCase (".midi"))
            return true;
    return false;
}

void MidiGPTEditor::filesDropped (const juce::StringArray& files, int /*x*/, int /*y*/)
{
    dragHover = false;
    repaint();

    // Only the first MIDI file is used as the prompt — multi-file drop is an
    // ambiguity we'd rather not guess at (merge? queue?). Caller can drop
    // another file next to replace.
    juce::File midiFile;
    for (const auto& f : files)
    {
        if (f.endsWithIgnoreCase (".mid") || f.endsWithIgnoreCase (".midi"))
        {
            midiFile = juce::File (f);
            break;
        }
    }
    if (midiFile == juce::File() || ! midiFile.existsAsFile())
        return;

    juce::FileInputStream stream (midiFile);
    if (! stream.openedOk())
    {
        statusLabel.setText ("파일 열기 실패: " + midiFile.getFileName(),
                             juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
        return;
    }

    juce::MidiFile mf;
    if (! mf.readFrom (stream))
    {
        statusLabel.setText ("MIDI 파일 파싱 실패",
                             juce::dontSendNotification);
        statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
        return;
    }

    // Convert event timestamps to BEATS using the MIDI header's time format.
    // Positive getTimeFormat() = ticks-per-quarter-note → beats = ticks / ppq.
    // Negative = SMPTE (frame-rate based) — rare in music MIDI files, but
    // handle gracefully by falling back to convertTimestampsToSeconds() and
    // using the first tempo event (or 120 BPM default).
    const int timeFormat = mf.getTimeFormat();
    juce::MidiMessageSequence flat;

    if (timeFormat > 0)
    {
        const double ppq = static_cast<double> (timeFormat);
        for (int t = 0; t < mf.getNumTracks(); ++t)
        {
            if (auto* track = mf.getTrack (t))
            {
                for (int e = 0; e < track->getNumEvents(); ++e)
                {
                    auto* evt = track->getEventPointer (e);
                    auto copyMsg = evt->message;
                    copyMsg.setTimeStamp (evt->message.getTimeStamp() / ppq);
                    flat.addEvent (copyMsg, 0.0);
                }
            }
        }
    }
    else
    {
        // SMPTE fallback: seconds → beats via first tempo event.
        mf.convertTimestampsToSeconds();
        double bpm = 120.0;
        if (auto* track0 = mf.getTrack (0))
        {
            for (int e = 0; e < track0->getNumEvents(); ++e)
            {
                auto& msg = track0->getEventPointer (e)->message;
                if (msg.isTempoMetaEvent())
                {
                    bpm = 60.0 / msg.getTempoSecondsPerQuarterNote();
                    break;
                }
            }
        }
        for (int t = 0; t < mf.getNumTracks(); ++t)
        {
            if (auto* track = mf.getTrack (t))
            {
                for (int e = 0; e < track->getNumEvents(); ++e)
                {
                    auto* evt = track->getEventPointer (e);
                    auto copyMsg = evt->message;
                    copyMsg.setTimeStamp (evt->message.getTimeStamp() * (bpm / 60.0));
                    flat.addEvent (copyMsg, 0.0);
                }
            }
        }
    }
    flat.updateMatchedPairs();

    processorRef.loadAsCapturedInput (flat);
    inputRoll.setSequence (flat);
    statusLabel.setText (
        juce::String ("Loaded: ") + midiFile.getFileName()
            + "  (" + juce::String (processorRef.getCapturedNoteCount()) + " notes)",
        juce::dontSendNotification);
    statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
}

// =============================================================================
// YY6 — Theme toggle (dark/light via LookAndFeel_V4 colour scheme swap)
// =============================================================================
void MidiGPTEditor::applyTheme (bool dark)
{
    darkTheme = dark;
    customLookAndFeel = std::make_unique<juce::LookAndFeel_V4> (
        dark ? juce::LookAndFeel_V4::getDarkColourScheme()
             : juce::LookAndFeel_V4::getLightColourScheme());
    setLookAndFeel (customLookAndFeel.get());
    themeButton.setButtonText (dark ? "Dark" : "Light");
    sendLookAndFeelChange();
    repaint();
}
