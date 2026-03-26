#include "TransportBar.h"

//==============================================================================
TransportBar::TransportBar()
{
    setupBpmSlider();
    setupSelectors();
    setupButtons();

    // Position / time labels
    positionLabel.setText ("1.1.000", juce::dontSendNotification);
    positionLabel.setFont (juce::Font (juce::Font::getDefaultMonospacedFontName(), 14.0f, juce::Font::bold));
    positionLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::accentLight);
    positionLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (positionLabel);

    timeLabel.setText ("0:00.000", juce::dontSendNotification);
    timeLabel.setFont (juce::Font (juce::Font::getDefaultMonospacedFontName(), 12.0f, juce::Font::plain));
    timeLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    timeLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (timeLabel);

    // CPU label
    cpuLabel.setText ("CPU: 0%", juce::dontSendNotification);
    cpuLabel.setFont (juce::Font (11.0f));
    cpuLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textDim);
    cpuLabel.setJustificationType (juce::Justification::centredRight);
    addAndMakeVisible (cpuLabel);

    startTimerHz (15);
}

//==============================================================================
void TransportBar::setupBpmSlider()
{
    bpmSlider.setSliderStyle (juce::Slider::IncDecButtons);
    bpmSlider.setRange (20.0, 300.0, 0.1);
    bpmSlider.setValue (120.0);
    bpmSlider.setTextBoxStyle (juce::Slider::TextBoxLeft, false, 55, 24);
    bpmSlider.setIncDecButtonsMode (juce::Slider::incDecButtonsDraggable_Vertical);
    bpmSlider.onValueChange = [this]()
    {
        if (onBpmChanged)
            onBpmChanged (bpmSlider.getValue());
    };
    addAndMakeVisible (bpmSlider);

    bpmLabel.setText ("BPM", juce::dontSendNotification);
    bpmLabel.setFont (juce::Font (10.0f));
    bpmLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textDim);
    bpmLabel.setJustificationType (juce::Justification::centredLeft);
    addAndMakeVisible (bpmLabel);
}

void TransportBar::setupSelectors()
{
    // Key selector
    const juce::StringArray keys { "C", "C#", "D", "D#", "E", "F",
                                    "F#", "G", "G#", "A", "A#", "B" };
    for (int i = 0; i < keys.size(); ++i)
        keySelector.addItem (keys[i], i + 1);
    keySelector.setSelectedId (1, juce::dontSendNotification);
    keySelector.onChange = [this]()
    {
        if (onKeyScaleChanged)
            onKeyScaleChanged (keySelector.getSelectedId() - 1, scaleSelector.getSelectedId() - 1);
    };
    addAndMakeVisible (keySelector);

    // Scale selector
    const juce::StringArray scales { "Major", "Minor", "Dorian", "Mixolydian",
                                      "Phrygian", "Lydian", "Pentatonic Maj",
                                      "Pentatonic Min", "Blues", "Harmonic Min",
                                      "Melodic Min", "Chromatic" };
    for (int i = 0; i < scales.size(); ++i)
        scaleSelector.addItem (scales[i], i + 1);
    scaleSelector.setSelectedId (1, juce::dontSendNotification);
    scaleSelector.onChange = [this]()
    {
        if (onKeyScaleChanged)
            onKeyScaleChanged (keySelector.getSelectedId() - 1, scaleSelector.getSelectedId() - 1);
    };
    addAndMakeVisible (scaleSelector);

    // Snap selector
    const juce::StringArray snaps { "Off", "1/1", "1/2", "1/4", "1/8", "1/16", "1/32" };
    for (int i = 0; i < snaps.size(); ++i)
        snapSelector.addItem (snaps[i], i + 1);
    snapSelector.setSelectedId (4, juce::dontSendNotification); // default 1/4
    snapSelector.onChange = [this]()
    {
        if (onSnapChanged)
            onSnapChanged (snapSelector.getSelectedId() - 1);
    };
    addAndMakeVisible (snapSelector);
}

void TransportBar::setupButtons()
{
    playButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    playButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFF2E7D32));
    playButton.setClickingTogglesState (false);
    playButton.onClick = [this]()
    {
        playing = !playing;
        playButton.setToggleState (playing, juce::dontSendNotification);
        if (onPlay) onPlay();
    };
    addAndMakeVisible (playButton);

    stopButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    stopButton.onClick = [this]()
    {
        playing = false;
        recording = false;
        playButton.setToggleState (false, juce::dontSendNotification);
        recordButton.setToggleState (false, juce::dontSendNotification);
        if (onStop) onStop();
    };
    addAndMakeVisible (stopButton);

    recordButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    recordButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFC62828));
    recordButton.setClickingTogglesState (true);
    recordButton.onClick = [this]()
    {
        recording = recordButton.getToggleState();
        if (onRecord) onRecord();
    };
    addAndMakeVisible (recordButton);

    loopButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    loopButton.setColour (juce::TextButton::buttonOnColourId, MetallicLookAndFeel::bgSelected);
    loopButton.setClickingTogglesState (true);
    loopButton.onClick = [this]()
    {
        if (onLoopToggled) onLoopToggled (loopButton.getToggleState());
    };
    addAndMakeVisible (loopButton);

    metronomeButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    metronomeButton.setColour (juce::TextButton::buttonOnColourId, MetallicLookAndFeel::bgSelected);
    metronomeButton.setClickingTogglesState (true);
    metronomeButton.onClick = [this]()
    {
        if (onMetronomeToggled) onMetronomeToggled (metronomeButton.getToggleState());
    };
    addAndMakeVisible (metronomeButton);
}

//==============================================================================
void TransportBar::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgHeader);

    // Bottom border
    g.setColour (MetallicLookAndFeel::border);
    g.drawHorizontalLine (getHeight() - 1, 0.0f, (float) getWidth());

    // Subtle gradient on top for metallic sheen
    g.setGradientFill (juce::ColourGradient (
        juce::Colours::white.withAlpha (0.02f), 0.0f, 0.0f,
        juce::Colours::transparentBlack, 0.0f, (float) getHeight(),
        false));
    g.fillRect (getLocalBounds());

    // CPU meter bar
    auto cpuArea = cpuLabel.getBounds().translated (-50, 0).withWidth (44).reduced (0, 10);
    g.setColour (MetallicLookAndFeel::bgDark);
    g.fillRoundedRectangle (cpuArea.toFloat(), 2.0f);
    auto fillW = cpuArea.getWidth() * cpuUsage / 100.0f;
    auto meterColour = cpuUsage < 60.0f ? MetallicLookAndFeel::meterGreen
                     : cpuUsage < 85.0f ? MetallicLookAndFeel::meterYellow
                     : MetallicLookAndFeel::meterRed;
    g.setColour (meterColour);
    g.fillRoundedRectangle (cpuArea.toFloat().withWidth (fillW), 2.0f);
}

void TransportBar::resized()
{
    auto area = getLocalBounds().reduced (4, 2);
    int h = area.getHeight();
    int spacing = 4;

    // BPM
    bpmSlider.setBounds (area.removeFromLeft (100).reduced (0, 1));
    area.removeFromLeft (spacing);

    // Transport buttons
    playButton.setBounds (area.removeFromLeft (40).reduced (0, 2));
    area.removeFromLeft (2);
    stopButton.setBounds (area.removeFromLeft (40).reduced (0, 2));
    area.removeFromLeft (2);
    recordButton.setBounds (area.removeFromLeft (40).reduced (0, 2));
    area.removeFromLeft (spacing * 2);

    // Position display
    positionLabel.setBounds (area.removeFromLeft (80));
    area.removeFromLeft (spacing);
    timeLabel.setBounds (area.removeFromLeft (70));
    area.removeFromLeft (spacing * 2);

    // Separator
    area.removeFromLeft (spacing);

    // Key/Scale
    keySelector.setBounds (area.removeFromLeft (52).reduced (0, 3));
    area.removeFromLeft (2);
    scaleSelector.setBounds (area.removeFromLeft (100).reduced (0, 3));
    area.removeFromLeft (spacing * 2);

    // Snap
    snapSelector.setBounds (area.removeFromLeft (60).reduced (0, 3));
    area.removeFromLeft (spacing * 2);

    // Loop / Metronome
    loopButton.setBounds (area.removeFromLeft (44).reduced (0, 2));
    area.removeFromLeft (2);
    metronomeButton.setBounds (area.removeFromLeft (48).reduced (0, 2));

    // CPU on right
    cpuLabel.setBounds (area.removeFromRight (70));
}

void TransportBar::timerCallback()
{
    // Update CPU label
    cpuLabel.setText ("CPU: " + juce::String ((int) cpuUsage) + "%", juce::dontSendNotification);
}

//==============================================================================
// Getters
//==============================================================================
double TransportBar::getBpm() const              { return bpmSlider.getValue(); }
bool   TransportBar::isPlaying() const           { return playing; }
bool   TransportBar::isRecording() const         { return recording; }
bool   TransportBar::isLoopEnabled() const       { return loopButton.getToggleState(); }
bool   TransportBar::isMetronomeEnabled() const  { return metronomeButton.getToggleState(); }
int    TransportBar::getSnapDivision() const     { return snapSelector.getSelectedId() - 1; }
int    TransportBar::getKeyIndex() const         { return keySelector.getSelectedId() - 1; }
int    TransportBar::getScaleIndex() const       { return scaleSelector.getSelectedId() - 1; }

//==============================================================================
// Setters
//==============================================================================
void TransportBar::setBpm (double bpm)
{
    bpmSlider.setValue (bpm, juce::dontSendNotification);
}

void TransportBar::setBPM (double bpm)
{
    setBpm (bpm);
}

void TransportBar::setPositionInfo (double beats, double seconds)
{
    int bar  = (int) (beats / 4.0) + 1;
    int beat = ((int) beats % 4) + 1;
    int tick = (int) ((beats - (int) beats) * 1000.0);
    setPosition (bar, beat, tick);
    setTimeDisplay (seconds);
}

void TransportBar::setPlaying (bool p)
{
    playing = p;
    playButton.setToggleState (p, juce::dontSendNotification);
}

void TransportBar::setRecording (bool r)
{
    recording = r;
    recordButton.setToggleState (r, juce::dontSendNotification);
}

void TransportBar::setPosition (int bar, int beat, int tick)
{
    positionLabel.setText (juce::String (bar) + "." + juce::String (beat) + "."
                           + juce::String (tick).paddedLeft ('0', 3),
                           juce::dontSendNotification);
}

void TransportBar::setTimeDisplay (double seconds)
{
    int mins = (int) (seconds / 60.0);
    double secs = seconds - mins * 60.0;
    timeLabel.setText (juce::String (mins) + ":" + juce::String (secs, 3).paddedLeft ('0', 6),
                       juce::dontSendNotification);
}

void TransportBar::setCpuUsage (float percent)
{
    cpuUsage = juce::jlimit (0.0f, 100.0f, percent);
}
