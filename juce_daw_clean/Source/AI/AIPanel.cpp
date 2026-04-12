/*
 * MidiGPT DAW - AIPanel.cpp
 */

#include "AIPanel.h"

AIPanel::AIPanel(AudioEngine& engine)
    : audioEngine(engine)
{
    generateButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xFF4A90D9));
    generateButton.onClick = [this] { onGenerate(); };
    addAndMakeVisible(generateButton);

    connectButton.onClick = [this] { onCheckServer(); };
    addAndMakeVisible(connectButton);

    temperatureSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    temperatureSlider.setRange(0.5, 1.5, 0.01);
    temperatureSlider.setValue(0.9);
    temperatureSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 45, 20);
    addAndMakeVisible(temperatureSlider);
    temperatureLabel.attachToComponent(&temperatureSlider, true);
    addAndMakeVisible(temperatureLabel);

    styleBox.addItemList({"base", "jazz", "citypop", "metal", "classical"}, 1);
    styleBox.setSelectedId(1);
    addAndMakeVisible(styleBox);
    styleLabel.attachToComponent(&styleBox, true);
    addAndMakeVisible(styleLabel);

    variationsSlider.setSliderStyle(juce::Slider::IncDecButtons);
    variationsSlider.setRange(1, 5, 1);
    variationsSlider.setValue(1);
    variationsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 40, 20);
    addAndMakeVisible(variationsSlider);
    variationsLabel.attachToComponent(&variationsSlider, true);
    addAndMakeVisible(variationsLabel);

    statusLabel.setJustificationType(juce::Justification::centred);
    statusLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible(statusLabel);

    startTimerHz(1);
}

void AIPanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF1E1E2E));

    g.setColour(juce::Colours::white);
    g.setFont(14.0f);
    g.drawText("MidiGPT AI", 8, 4, getWidth(), 20, juce::Justification::centredLeft);

    g.setColour(juce::Colour(0xFF333355));
    g.drawHorizontalLine(26, 0.0f, (float)getWidth());
}

void AIPanel::resized()
{
    int y = 32;
    int labelW = 85;
    int ctrlW = getWidth() - labelW - 16;

    temperatureSlider.setBounds(labelW + 8, y, ctrlW, 22);
    y += 28;
    styleBox.setBounds(labelW + 8, y, ctrlW, 22);
    y += 28;
    variationsSlider.setBounds(labelW + 8, y, ctrlW, 22);
    y += 34;

    generateButton.setBounds(8, y, getWidth() - 16, 32);
    y += 38;
    connectButton.setBounds(8, y, getWidth() - 16, 24);
    y += 30;
    statusLabel.setBounds(8, y, getWidth() - 16, 20);
}

void AIPanel::timerCallback()
{
    // Periodic server health check
    bool ok = aiBridge.checkHealth(500);
    if (ok != serverConnected)
    {
        serverConnected = ok;
        statusLabel.setText(ok ? "Server Connected" : "Disconnected",
                            juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId,
                              ok ? juce::Colours::limegreen : juce::Colours::grey);
        generateButton.setEnabled(ok);
    }
}

void AIPanel::onCheckServer()
{
    bool ok = aiBridge.checkHealth(2000);
    serverConnected = ok;
    statusLabel.setText(ok ? "Server Connected" : "Server not reachable",
                        juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId,
                          ok ? juce::Colours::limegreen : juce::Colours::red);
}

void AIPanel::onGenerate()
{
    if (!serverConnected) return;

    auto* track = (targetTrackId >= 0)
        ? audioEngine.getTrackModel().getTrack(targetTrackId)
        : (!audioEngine.getTrackModel().getTracks().empty()
            ? &audioEngine.getTrackModel().getTracks().front()
            : nullptr);

    if (track == nullptr || track->clips.empty())
    {
        statusLabel.setText("No MIDI clip to use as input", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, juce::Colours::orange);
        return;
    }

    auto inputSeq = track->flattenForPlayback();

    AIBridge::GenerateParams params;
    params.style = styleBox.getText();
    params.temperature = static_cast<float>(temperatureSlider.getValue());
    params.numVariations = static_cast<int>(variationsSlider.getValue());
    params.tempo = audioEngine.getTempo();

    statusLabel.setText("Generating...", juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, juce::Colours::yellow);

    aiBridge.requestVariationAsync(inputSeq, params,
        [this, trackPtr = track](AIBridge::Result result)
        {
            if (result.success)
            {
                // Add generated MIDI as a new clip on the same track
                MidiClip newClip;
                newClip.startBeat = trackPtr->clips.back().startBeat
                                  + trackPtr->clips.back().lengthBeats;
                newClip.sequence = std::move(result.generatedSequence);

                // Calculate clip length from sequence
                double maxBeat = 0;
                for (int i = 0; i < newClip.sequence.getNumEvents(); ++i)
                    maxBeat = juce::jmax(maxBeat,
                        newClip.sequence.getEventPointer(i)->message.getTimeStamp());
                newClip.lengthBeats = juce::jmax(4.0, std::ceil(maxBeat / 4.0) * 4.0);

                trackPtr->clips.push_back(std::move(newClip));

                statusLabel.setText("Generated!", juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::limegreen);
            }
            else
            {
                statusLabel.setText(result.errorMessage, juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::red);
            }
        });
}
