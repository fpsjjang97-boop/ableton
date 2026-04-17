/*
 * MidiGPT VST3 Plugin — PluginEditor.cpp
 *
 * Plugin UI: style / temperature / variations + generate button, plus
 * server-health and captured-MIDI feedback (Sprint 32 WW5).
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include "PluginEditor.h"

MidiGPTEditor::MidiGPTEditor (MidiGPTProcessor& p)
    : AudioProcessorEditor (&p),
      processorRef (p)
{
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

    // --- Style selector ------------------------------------------------------
    styleBox.addItemList (juce::StringArray { "base", "jazz", "citypop", "metal", "classical" }, 1);
    addAndMakeVisible (styleBox);
    addAndMakeVisible (styleLabel);
    styleLabel.attachToComponent (&styleBox, true);
    styleAttachment = std::make_unique<ComboAttachment> (
        processorRef.parameters, "style", styleBox);

    // --- Generate button -----------------------------------------------------
    generateButton.setColour (juce::TextButton::buttonColourId, juce::Colour (0xFF4A90D9));
    generateButton.onClick = [this]
    {
        processorRef.requestVariation();
    };
    addAndMakeVisible (generateButton);

    // --- Clear captured-input button -----------------------------------------
    clearButton.onClick = [this]
    {
        processorRef.clearCapturedInput();
    };
    addAndMakeVisible (clearButton);

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
    processorRef.setStatusCallback (
        [this] (MidiGPTProcessor::GenerationStatus st, juce::String msg)
        {
            handleStatus (st, std::move (msg));
        });

    // Poll server health once a second so the user sees red/green without
    // having to click a "Connect" button. checkHealth uses a short timeout
    // to avoid stalling the UI thread.
    startTimerHz (1);

    setSize (480, 340);
}

MidiGPTEditor::~MidiGPTEditor()
{
    // Detach the status callback so the processor doesn't invoke a
    // dead editor if the host tears us down while a request is in flight.
    processorRef.setStatusCallback (nullptr);
}

void MidiGPTEditor::paint (juce::Graphics& g)
{
    g.fillAll (getLookAndFeel().findColour (juce::ResizableWindow::backgroundColourId));

    g.setColour (juce::Colours::white);
    g.setFont (20.0f);
    g.drawFittedText ("MidiGPT", 0, 10, getWidth(), 30, juce::Justification::centred, 1);

    g.setFont (12.0f);
    g.setColour (juce::Colours::grey);
    g.drawFittedText ("LLM-driven MIDI variation", 0, 38, getWidth(), 20,
                      juce::Justification::centred, 1);
}

void MidiGPTEditor::resized()
{
    const int margin = 20;
    const int labelW = 100;
    const int controlH = 24;
    int y = 70;

    temperatureSlider.setBounds (margin + labelW, y, getWidth() - margin * 2 - labelW, controlH);
    y += controlH + 12;

    numVariationsSlider.setBounds (margin + labelW, y, getWidth() - margin * 2 - labelW, controlH);
    y += controlH + 12;

    styleBox.setBounds (margin + labelW, y, getWidth() - margin * 2 - labelW, controlH);
    y += controlH + 24;

    // Two buttons side-by-side: Generate (primary), Clear (secondary)
    const int buttonGap = 8;
    const int buttonW = (getWidth() - margin * 2 - buttonGap) * 2 / 3;
    generateButton.setBounds (margin, y, buttonW, 40);
    clearButton.setBounds (margin + buttonW + buttonGap, y,
                           getWidth() - margin * 2 - buttonW - buttonGap, 40);
    y += 40 + 12;

    statusLabel.setBounds (margin, y, getWidth() - margin * 2, 24);
    y += 28;

    // Bottom row: server status (left) + captured count (right)
    const int bottomW = (getWidth() - margin * 2) / 2;
    serverStatusLabel.setBounds (margin, y, bottomW, 20);
    capturedCountLabel.setBounds (margin + bottomW, y, bottomW, 20);
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
        generateButton.setEnabled (ok);
    }

    // Update captured-note count (cheap atomic read).
    capturedCountLabel.setText (
        juce::String ("Captured: ") + juce::String (processorRef.getCapturedNoteCount()),
        juce::dontSendNotification);
}

void MidiGPTEditor::handleStatus (MidiGPTProcessor::GenerationStatus st, juce::String msg)
{
    statusLabel.setText (msg, juce::dontSendNotification);
    switch (st)
    {
        case MidiGPTProcessor::GenerationStatus::Idle:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::grey);
            break;
        case MidiGPTProcessor::GenerationStatus::NoInputCaptured:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::orange);
            break;
        case MidiGPTProcessor::GenerationStatus::InFlight:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::yellow);
            break;
        case MidiGPTProcessor::GenerationStatus::Ready:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::limegreen);
            break;
        case MidiGPTProcessor::GenerationStatus::Error:
            statusLabel.setColour (juce::Label::textColourId, juce::Colours::red);
            break;
    }
}
