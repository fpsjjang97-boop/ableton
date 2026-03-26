#include "MixerPanel.h"

//==============================================================================
// ChannelStrip
//==============================================================================
ChannelStrip::ChannelStrip (int index, const juce::String& name, juce::Colour colour, bool isMaster)
    : trackIndex (index), masterStrip (isMaster), trackName (name), trackColour (colour)
{
    // Name label
    nameLabel.setText (name, juce::dontSendNotification);
    nameLabel.setFont (juce::Font (10.0f, isMaster ? juce::Font::bold : juce::Font::plain));
    nameLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textPrimary);
    nameLabel.setJustificationType (juce::Justification::centred);
    nameLabel.setEditable (false, !isMaster, false);
    addAndMakeVisible (nameLabel);

    // Volume fader
    volumeFader.setSliderStyle (juce::Slider::LinearVertical);
    volumeFader.setRange (-60.0, 6.0, 0.1);
    volumeFader.setValue (0.0);
    volumeFader.setSkewFactorFromMidPoint (-12.0);
    volumeFader.setTextBoxStyle (juce::Slider::NoTextBox, false, 0, 0);
    volumeFader.onValueChange = [this]()
    {
        dbLabel.setText (juce::String (volumeFader.getValue(), 1) + " dB", juce::dontSendNotification);
        if (onVolumeChanged)
            onVolumeChanged (trackIndex, (float) volumeFader.getValue());
    };
    addAndMakeVisible (volumeFader);

    // Pan knob
    panKnob.setSliderStyle (juce::Slider::Rotary);
    panKnob.setRange (-1.0, 1.0, 0.01);
    panKnob.setValue (0.0);
    panKnob.setTextBoxStyle (juce::Slider::NoTextBox, false, 0, 0);
    panKnob.setRotaryParameters (juce::MathConstants<float>::pi * 1.25f,
                                  juce::MathConstants<float>::pi * 2.75f, true);
    panKnob.onValueChange = [this]()
    {
        if (onPanChanged)
            onPanChanged (trackIndex, (float) panKnob.getValue());
    };
    addAndMakeVisible (panKnob);

    // Mute / Solo
    muteButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    muteButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFFF5722));
    muteButton.setClickingTogglesState (true);
    muteButton.onClick = [this]()
    {
        if (onMuteChanged) onMuteChanged (trackIndex, muteButton.getToggleState());
    };
    addAndMakeVisible (muteButton);

    soloButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    soloButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFFFC107));
    soloButton.setClickingTogglesState (true);
    soloButton.onClick = [this]()
    {
        if (onSoloChanged) onSoloChanged (trackIndex, soloButton.getToggleState());
    };
    addAndMakeVisible (soloButton);

    if (isMaster)
    {
        muteButton.setVisible (false);
        soloButton.setVisible (false);
    }

    // dB label
    dbLabel.setText ("0.0 dB", juce::dontSendNotification);
    dbLabel.setFont (juce::Font (9.0f));
    dbLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textDim);
    dbLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (dbLabel);

    startTimerHz (30);
}

ChannelStrip::~ChannelStrip()
{
    stopTimer();
}

void ChannelStrip::paint (juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();

    // Background
    g.setColour (masterStrip ? MetallicLookAndFeel::bgHeader : MetallicLookAndFeel::bgPanel);
    g.fillRect (bounds);

    // Colour strip at top
    g.setColour (trackColour);
    g.fillRect (bounds.removeFromTop (3.0f));

    // VU meters
    auto faderBounds = volumeFader.getBounds();
    int meterX = faderBounds.getRight() + 4;
    int meterW = 5;
    int meterH = faderBounds.getHeight();
    int meterY = faderBounds.getY();

    auto leftMeter = juce::Rectangle<int> (meterX, meterY, meterW, meterH);
    auto rightMeter = juce::Rectangle<int> (meterX + meterW + 2, meterY, meterW, meterH);

    drawMeter (g, leftMeter, meterL, peakL);
    drawMeter (g, rightMeter, meterR, peakR);

    // Border
    g.setColour (MetallicLookAndFeel::border);
    g.drawRect (getLocalBounds(), 1);
}

void ChannelStrip::drawMeter (juce::Graphics& g, juce::Rectangle<int> area, float level, float peak)
{
    g.setColour (MetallicLookAndFeel::bgDark);
    g.fillRect (area);

    float fillH = (float) area.getHeight() * level;
    auto fillArea = area.toFloat().withTop ((float) area.getBottom() - fillH);

    // Gradient: green -> yellow -> red
    if (level > 0.0f)
    {
        if (level > 0.9f)
            g.setColour (MetallicLookAndFeel::meterRed);
        else if (level > 0.7f)
            g.setColour (MetallicLookAndFeel::meterYellow);
        else
            g.setColour (MetallicLookAndFeel::meterGreen);

        g.fillRect (fillArea);
    }

    // Peak indicator
    if (peak > 0.01f)
    {
        float peakY = (float) area.getBottom() - (float) area.getHeight() * peak;
        g.setColour (peak > 0.95f ? MetallicLookAndFeel::meterRed : MetallicLookAndFeel::accentLight);
        g.drawHorizontalLine ((int) peakY, (float) area.getX(), (float) area.getRight());
    }
}

void ChannelStrip::resized()
{
    auto area = getLocalBounds().reduced (4);
    area.removeFromTop (5); // colour strip space

    nameLabel.setBounds (area.removeFromTop (18));

    panKnob.setBounds (area.removeFromTop (36).reduced (6, 2));

    auto buttonRow = area.removeFromTop (20);
    if (! masterStrip)
    {
        muteButton.setBounds (buttonRow.removeFromLeft (buttonRow.getWidth() / 2).reduced (1));
        soloButton.setBounds (buttonRow.reduced (1));
    }

    dbLabel.setBounds (area.removeFromBottom (14));

    // Fader gets remaining space, leave room for meters on right
    auto faderArea = area.reduced (2);
    int meterSpace = 18;
    volumeFader.setBounds (faderArea.withTrimmedRight (meterSpace));
}

void ChannelStrip::timerCallback()
{
    // Smooth meter decay
    meterL *= 0.92f;
    meterR *= 0.92f;
    peakL  *= 0.997f;
    peakR  *= 0.997f;
    repaint();
}

void ChannelStrip::setTrackName (const juce::String& name)
{
    trackName = name;
    nameLabel.setText (name, juce::dontSendNotification);
}

void ChannelStrip::setTrackColour (juce::Colour c)
{
    trackColour = c;
    repaint();
}

void ChannelStrip::setLevel (float left, float right)
{
    meterL = juce::jmax (meterL, juce::jlimit (0.0f, 1.0f, left));
    meterR = juce::jmax (meterR, juce::jlimit (0.0f, 1.0f, right));
    peakL  = juce::jmax (peakL, meterL);
    peakR  = juce::jmax (peakR, meterR);
}

//==============================================================================
// MixerPanel
//==============================================================================
MixerPanel::MixerPanel()
{
    viewport.setViewedComponent (&container, false);
    viewport.setScrollBarsShown (false, true);
    addAndMakeVisible (viewport);

    // Master strip
    masterStrip = std::make_unique<ChannelStrip> (-1, "Master", MetallicLookAndFeel::accent, true);
    addAndMakeVisible (masterStrip.get());

    // Default channels
    addChannel ("Track 1", juce::Colour (0xFF5E81AC));
    addChannel ("Track 2", juce::Colour (0xFFA3BE8C));
    addChannel ("Track 3", juce::Colour (0xFFBF616A));
    addChannel ("Track 4", juce::Colour (0xFFD08770));
}

void MixerPanel::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgDarkest);
}

void MixerPanel::resized()
{
    auto area = getLocalBounds();

    masterStrip->setBounds (area.removeFromRight (masterWidth));
    viewport.setBounds (area);

    rebuildLayout();
}

void MixerPanel::addChannel (const juce::String& name, juce::Colour colour)
{
    int idx = channels.size();
    auto* strip = channels.add (new ChannelStrip (idx, name, colour));
    strip->onVolumeChanged = [this] (int i, float v) { if (onVolumeChanged) onVolumeChanged (i, v); };
    strip->onPanChanged    = [this] (int i, float v) { if (onPanChanged) onPanChanged (i, v); };
    strip->onMuteChanged   = [this] (int i, bool m)  { if (onMuteChanged) onMuteChanged (i, m); };
    strip->onSoloChanged   = [this] (int i, bool s)  { if (onSoloChanged) onSoloChanged (i, s); };
    container.addAndMakeVisible (strip);
    rebuildLayout();
}

void MixerPanel::removeChannel (int index)
{
    if (index >= 0 && index < channels.size())
    {
        channels.remove (index);
        rebuildLayout();
    }
}

void MixerPanel::clearChannels()
{
    channels.clear();
    container.removeAllChildren();
    rebuildLayout();
}

void MixerPanel::setChannelLevel (int index, float left, float right)
{
    if (index >= 0 && index < channels.size())
        channels[index]->setLevel (left, right);
    else if (index == -1 && masterStrip)
        masterStrip->setLevel (left, right);
}

void MixerPanel::rebuildLayout()
{
    int totalW = channels.size() * stripWidth;
    container.setBounds (0, 0, totalW, viewport.getHeight());

    for (int i = 0; i < channels.size(); ++i)
        channels[i]->setBounds (i * stripWidth, 0, stripWidth, viewport.getHeight());
}
