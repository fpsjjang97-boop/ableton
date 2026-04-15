/*
 * MidiGPT DAW - TransportBar.cpp
 */

#include "TransportBar.h"

TransportBar::TransportBar(AudioEngine& engine)
    : audioEngine(engine)
{
    rewindButton.onClick  = [this] { audioEngine.rewind(); };
    addAndMakeVisible(rewindButton);

    playButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xFF2E7D32));
    playButton.onClick = [this] {
        if (!audioEngine.isPlaying())
        {
            audioEngine.rewind();  // Always start from beginning
            audioEngine.play();
        }
    };
    addAndMakeVisible(playButton);

    stopButton.onClick = [this] { audioEngine.stop(); };
    addAndMakeVisible(stopButton);

    recordButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xFFC62828));
    recordButton.setClickingTogglesState(true);
    recordButton.onClick = [this] {
        auto& tracks = audioEngine.getTrackModel().getTracks();
        if (tracks.empty()) return;
        auto& t = tracks.front();
        t.armed = recordButton.getToggleState();
        audioEngine.setRecordingTargetTrack(recordButton.getToggleState() ? t.id : -1);
        // Y5 — arm record implies 1-bar count-in by default
        audioEngine.setCountInBars(recordButton.getToggleState() ? 1 : 0);
        if (recordButton.getToggleState() && ! audioEngine.isPlaying())
            audioEngine.play();
    };
    addAndMakeVisible(recordButton);

    loopButton.setClickingTogglesState(true);
    loopButton.onClick = [this] {
        audioEngine.getMidiEngine().setLooping(loopButton.getToggleState());
    };
    addAndMakeVisible(loopButton);

    // Z3 — count-in selector
    countInSelector.addItem("No count-in",  1);
    countInSelector.addItem("1 bar pre",    2);
    countInSelector.addItem("2 bars pre",   3);
    countInSelector.addItem("4 bars pre",   5);
    countInSelector.setSelectedId(2, juce::dontSendNotification);
    countInSelector.onChange = [this] {
        const int id = countInSelector.getSelectedId();
        const int bars = (id == 1 ? 0 : id == 2 ? 1 : id == 3 ? 2 : 4);
        audioEngine.setCountInBars(bars);
    };
    addAndMakeVisible(countInSelector);

    metroButton.setClickingTogglesState(true);
    metroButton.onClick = [this] {
        audioEngine.setMetronome(metroButton.getToggleState());
    };
    addAndMakeVisible(metroButton);

    // BPM
    tempoSlider.setSliderStyle(juce::Slider::IncDecButtons);
    tempoSlider.setRange(20, 300, 0.1);
    tempoSlider.setValue(120.0);
    tempoSlider.setTextBoxStyle(juce::Slider::TextBoxLeft, false, 48, 20);
    tempoSlider.onValueChange = [this] { audioEngine.setTempo(tempoSlider.getValue()); };
    addAndMakeVisible(tempoSlider);

    // Position
    positionLabel.setFont(juce::Font(juce::Font::getDefaultMonospacedFontName(), 14.0f, juce::Font::bold));
    positionLabel.setColour(juce::Label::textColourId, juce::Colour(0xFFE0E0E0));
    positionLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(positionLabel);

    timeLabel.setFont(juce::Font(juce::Font::getDefaultMonospacedFontName(), 12.0f, 0));
    timeLabel.setColour(juce::Label::textColourId, juce::Colour(0xFF909090));
    timeLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(timeLabel);

    // Key selector
    keySelector.addItemList({"C","C#","D","D#","E","F","F#","G","G#","A","A#","B"}, 1);
    keySelector.setSelectedId(1);
    addAndMakeVisible(keySelector);

    // Scale selector
    scaleSelector.addItemList({"Major","Minor","Dorian","Mixolydian","Pentatonic",
                               "Blues","Harmonic Min","Chromatic"}, 1);
    scaleSelector.setSelectedId(1);
    addAndMakeVisible(scaleSelector);

    // Snap selector
    snapSelector.addItemList({"Off","1/1","1/2","1/4","1/8","1/16","1/32"}, 1);
    snapSelector.setSelectedId(6); // 1/16 default
    addAndMakeVisible(snapSelector);

    startTimerHz(30);
}

void TransportBar::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF1C1C1C));

    // Top metallic sheen
    g.setGradientFill(juce::ColourGradient(
        juce::Colours::white.withAlpha(0.02f), 0, 0,
        juce::Colours::transparentWhite, 0, (float)getHeight(), false));
    g.fillRect(getLocalBounds());

    // Bottom border
    g.setColour(juce::Colour(0xFF2A2A2A));
    g.drawHorizontalLine(getHeight() - 1, 0.0f, (float)getWidth());
}

void TransportBar::resized()
{
    auto area = getLocalBounds().reduced(4, 2);

    tempoSlider.setBounds(area.removeFromLeft(100));
    area.removeFromLeft(6);

    rewindButton.setBounds(area.removeFromLeft(36));
    area.removeFromLeft(2);
    playButton.setBounds(area.removeFromLeft(44));
    area.removeFromLeft(2);
    stopButton.setBounds(area.removeFromLeft(40));
    area.removeFromLeft(2);
    recordButton.setBounds(area.removeFromLeft(36));

    area.removeFromLeft(12);

    positionLabel.setBounds(area.removeFromLeft(80));
    timeLabel.setBounds(area.removeFromLeft(70));

    area.removeFromLeft(12);

    keySelector.setBounds(area.removeFromLeft(52));
    area.removeFromLeft(2);
    scaleSelector.setBounds(area.removeFromLeft(100));

    area.removeFromLeft(8);

    snapSelector.setBounds(area.removeFromLeft(60));

    area.removeFromLeft(8);

    loopButton.setBounds(area.removeFromLeft(44));
    area.removeFromLeft(2);
    metroButton.setBounds(area.removeFromLeft(48));
    area.removeFromLeft(6);
    countInSelector.setBounds(area.removeFromLeft(80));   // Z3
}

void TransportBar::timerCallback()
{
    double beats = audioEngine.getPositionBeats();
    int bar  = static_cast<int>(beats / 4.0) + 1;
    int beat = static_cast<int>(std::fmod(beats, 4.0)) + 1;
    int tick = static_cast<int>(std::fmod(beats * 480.0, 480.0));
    positionLabel.setText(juce::String::formatted("%d.%d.%03d", bar, beat, tick),
                          juce::dontSendNotification);

    double seconds = beats * 60.0 / audioEngine.getTempo();
    int mins = static_cast<int>(seconds) / 60;
    int secs = static_cast<int>(seconds) % 60;
    int ms   = static_cast<int>(std::fmod(seconds, 1.0) * 1000.0);
    timeLabel.setText(juce::String::formatted("%d:%02d.%03d", mins, secs, ms),
                      juce::dontSendNotification);

    // Update play button colour
    playButton.setColour(juce::TextButton::buttonColourId,
                         audioEngine.isPlaying() ? juce::Colour(0xFF4CAF50)
                                                 : juce::Colour(0xFF2E7D32));
}
