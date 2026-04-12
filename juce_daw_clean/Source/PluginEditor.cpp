/*
 * MidiGPT VST3 Plugin — PluginEditor.cpp
 *
 * Minimal plugin UI: style selector, temperature, variations, generate button.
 * Based on JUCE standard tutorial patterns.
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
    generateButton.onClick = [this]
    {
        statusLabel.setText ("Generating...", juce::dontSendNotification);
        processorRef.requestVariation();
        statusLabel.setText ("Ready", juce::dontSendNotification);
    };
    addAndMakeVisible (generateButton);

    // --- Status label --------------------------------------------------------
    statusLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (statusLabel);

    setSize (480, 320);
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

    generateButton.setBounds (margin, y, getWidth() - margin * 2, 40);
    y += 40 + 12;

    statusLabel.setBounds (margin, y, getWidth() - margin * 2, 24);
}
