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
      processorRef (p)
{
    // --- Piano roll panes ---------------------------------------------------
    inputRoll.setTitle ("Input (Captured)");
    inputRoll.setEmptyPlaceholder ("MIDI 를 재생/입력하면 여기에 표시됩니다");
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

    // Taller window for the dual piano-roll pane (+160px vs Sprint 32).
    setSize (720, 500);
}

MidiGPTEditor::~MidiGPTEditor()
{
    // Detach the status callback so the processor doesn't invoke a dead
    // editor if the host tears us down while a request is in flight.
    processorRef.setStatusCallback (nullptr);
}

void MidiGPTEditor::paint (juce::Graphics& g)
{
    g.fillAll (getLookAndFeel().findColour (juce::ResizableWindow::backgroundColourId));

    g.setColour (juce::Colours::white);
    g.setFont (20.0f);
    g.drawFittedText ("MidiGPT", 0, 10, getWidth(), 28, juce::Justification::centred, 1);

    g.setFont (12.0f);
    g.setColour (juce::Colours::grey);
    g.drawFittedText ("LLM-driven MIDI variation", 0, 38, getWidth(), 16,
                      juce::Justification::centred, 1);

    // --- XX5 Progress overlay -----------------------------------------------
    if (generationInFlight)
    {
        const auto bounds = getLocalBounds().toFloat();
        g.setColour (juce::Colours::black.withAlpha (0.4f));
        g.fillRect (bounds);

        g.setColour (juce::Colours::white);
        g.setFont (14.0f);
        g.drawFittedText ("Generating...  (Cancel 버튼으로 중단)",
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

    // Piano roll dual pane (top area)
    const int rollAreaH = 150;
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
    y += controlH + 14;

    // Action buttons: Generate (primary) + Cancel (overlay-only) + Clear + Export + Info
    const int buttonGap = 6;
    const int totalW = getWidth() - margin * 2;
    const int primaryW = totalW * 2 / 5;
    const int secondaryW = (totalW - primaryW - buttonGap * 3) / 3;

    generateButton.setBounds (margin, y, primaryW, 36);
    cancelButton.setBounds   (margin, y, primaryW, 36);        // same spot; visibility toggles
    int x = margin + primaryW + buttonGap;
    clearButton.setBounds  (x, y, secondaryW, 36); x += secondaryW + buttonGap;
    exportButton.setBounds (x, y, secondaryW, 36); x += secondaryW + buttonGap;
    infoButton.setBounds   (x, y, secondaryW, 36);
    y += 36 + 8;

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
