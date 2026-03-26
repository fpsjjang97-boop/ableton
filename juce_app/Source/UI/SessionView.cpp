#include "SessionView.h"

//==============================================================================
// ClipSlot
//==============================================================================
ClipSlot::ClipSlot (int trackIndex, int sceneIndex)
    : track (trackIndex), scene (sceneIndex)
{
}

void ClipSlot::paint (juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced (1.0f);

    if (hasClip())
    {
        auto bg = selected ? MetallicLookAndFeel::clipSelected : colour;
        if (isPlaying)
            bg = bg.brighter (0.2f);

        g.setColour (bg);
        g.fillRoundedRectangle (bounds, 2.0f);

        // Clip name
        g.setColour (MetallicLookAndFeel::textPrimary);
        g.setFont (juce::Font (10.0f));
        g.drawFittedText (clipName, getLocalBounds().reduced (4, 2),
                          juce::Justification::centredLeft, 1);

        // Playing indicator
        if (isPlaying)
        {
            g.setColour (MetallicLookAndFeel::meterGreen);
            g.fillEllipse (bounds.getRight() - 8.0f, bounds.getCentreY() - 2.5f, 5.0f, 5.0f);
        }
    }
    else
    {
        // Empty slot
        g.setColour (selected ? MetallicLookAndFeel::bgSelected : MetallicLookAndFeel::bgDark);
        g.fillRoundedRectangle (bounds, 2.0f);
    }

    // Border
    g.setColour (MetallicLookAndFeel::border);
    g.drawRoundedRectangle (bounds, 2.0f, 0.5f);
}

void ClipSlot::mouseDown (const juce::MouseEvent& e)
{
    if (e.mods.isRightButtonDown())
        return;

    if (hasClip() && onClipTriggered)
        onClipTriggered (track, scene);

    if (onClipSelected)
        onClipSelected (track, scene, true);

    selected = true;
    repaint();
}

void ClipSlot::mouseDoubleClick (const juce::MouseEvent&)
{
    if (onClipDoubleClick)
        onClipDoubleClick (track, scene);
}

void ClipSlot::setClipName (const juce::String& name)   { clipName = name; repaint(); }
void ClipSlot::setPlaying (bool p)                       { isPlaying = p; repaint(); }
void ClipSlot::setSelected (bool s)                      { selected = s; repaint(); }
void ClipSlot::setClipColour (juce::Colour c)            { colour = c; repaint(); }

//==============================================================================
// TrackHeader
//==============================================================================
TrackHeader::TrackHeader (int trackIndex, const juce::String& name, juce::Colour colour)
    : trackIdx (trackIndex), trackName (name), trackColour (colour)
{
    nameLabel.setText (name, juce::dontSendNotification);
    nameLabel.setFont (juce::Font (11.0f, juce::Font::bold));
    nameLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textPrimary);
    nameLabel.setJustificationType (juce::Justification::centred);
    nameLabel.setEditable (false, true, false);
    nameLabel.onTextChange = [this]()
    {
        trackName = nameLabel.getText();
        if (onNameChanged)
            onNameChanged (trackIdx, trackName);
    };
    addAndMakeVisible (nameLabel);

    muteButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    muteButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFFF5722));
    muteButton.setClickingTogglesState (true);
    muteButton.onClick = [this]()
    {
        if (onMuteChanged) onMuteChanged (trackIdx, muteButton.getToggleState());
    };
    addAndMakeVisible (muteButton);

    soloButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    soloButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFFFC107));
    soloButton.setClickingTogglesState (true);
    soloButton.onClick = [this]()
    {
        if (onSoloChanged) onSoloChanged (trackIdx, soloButton.getToggleState());
    };
    addAndMakeVisible (soloButton);
}

void TrackHeader::paint (juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    g.setColour (MetallicLookAndFeel::bgHeader);
    g.fillRect (bounds);

    // Colour strip at top
    g.setColour (trackColour);
    g.fillRect (bounds.removeFromTop (3.0f));

    // Border
    g.setColour (MetallicLookAndFeel::border);
    g.drawRect (getLocalBounds(), 1);
}

void TrackHeader::resized()
{
    auto area = getLocalBounds().reduced (2);
    area.removeFromTop (5); // space for colour strip

    auto buttonArea = area.removeFromBottom (18);
    muteButton.setBounds (buttonArea.removeFromLeft (buttonArea.getWidth() / 2).reduced (1));
    soloButton.setBounds (buttonArea.reduced (1));

    nameLabel.setBounds (area);
}

void TrackHeader::mouseDoubleClick (const juce::MouseEvent&)
{
    nameLabel.showEditor();
}

void TrackHeader::setTrackName (const juce::String& name)
{
    trackName = name;
    nameLabel.setText (name, juce::dontSendNotification);
}

void TrackHeader::setTrackColour (juce::Colour c)
{
    trackColour = c;
    repaint();
}

void TrackHeader::setMuted (bool m) { muteButton.setToggleState (m, juce::dontSendNotification); }
void TrackHeader::setSoloed (bool s) { soloButton.setToggleState (s, juce::dontSendNotification); }

//==============================================================================
// MixerStrip
//==============================================================================
MixerStrip::MixerStrip (int trackIndex, const juce::String& name, juce::Colour colour)
    : trackIdx (trackIndex), trackName (name), trackColour (colour)
{
    volumeSlider.setSliderStyle (juce::Slider::LinearVertical);
    volumeSlider.setRange (-60.0, 6.0, 0.1);
    volumeSlider.setValue (0.0);
    volumeSlider.setTextBoxStyle (juce::Slider::NoTextBox, false, 0, 0);
    volumeSlider.setSkewFactorFromMidPoint (-12.0);
    volumeSlider.onValueChange = [this]()
    {
        if (onVolumeChanged)
            onVolumeChanged (trackIdx, (float) volumeSlider.getValue());
    };
    addAndMakeVisible (volumeSlider);

    panKnob.setSliderStyle (juce::Slider::Rotary);
    panKnob.setRange (-1.0, 1.0, 0.01);
    panKnob.setValue (0.0);
    panKnob.setTextBoxStyle (juce::Slider::NoTextBox, false, 0, 0);
    panKnob.onValueChange = [this]()
    {
        if (onPanChanged)
            onPanChanged (trackIdx, (float) panKnob.getValue());
    };
    addAndMakeVisible (panKnob);

    muteButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    muteButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFFF5722));
    muteButton.setClickingTogglesState (true);
    addAndMakeVisible (muteButton);

    soloButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
    soloButton.setColour (juce::TextButton::buttonOnColourId, juce::Colour (0xFFFFC107));
    soloButton.setClickingTogglesState (true);
    addAndMakeVisible (soloButton);

    nameLabel.setText (name, juce::dontSendNotification);
    nameLabel.setFont (juce::Font (10.0f));
    nameLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    nameLabel.setJustificationType (juce::Justification::centred);
    addAndMakeVisible (nameLabel);
}

void MixerStrip::paint (juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    g.setColour (MetallicLookAndFeel::bgPanel);
    g.fillRect (bounds);

    // Colour strip
    g.setColour (trackColour);
    g.fillRect (bounds.removeFromTop (2.0f));

    // VU meters
    auto meterArea = getLocalBounds().reduced (2).removeFromRight (8);
    auto meterH = meterArea.getHeight() - 40;
    meterArea = meterArea.withHeight (meterH).translated (0, 20);

    // Left meter
    auto leftArea = meterArea.removeFromLeft (3).toFloat();
    g.setColour (MetallicLookAndFeel::bgDark);
    g.fillRect (leftArea);
    auto leftFill = leftArea.getHeight() * meterL;
    g.setColour (meterL > 0.9f ? MetallicLookAndFeel::meterRed
                 : meterL > 0.7f ? MetallicLookAndFeel::meterYellow
                 : MetallicLookAndFeel::meterGreen);
    g.fillRect (leftArea.withTop (leftArea.getBottom() - leftFill));

    meterArea.removeFromLeft (2);

    // Right meter
    auto rightArea = meterArea.removeFromLeft (3).toFloat();
    g.setColour (MetallicLookAndFeel::bgDark);
    g.fillRect (rightArea);
    auto rightFill = rightArea.getHeight() * meterR;
    g.setColour (meterR > 0.9f ? MetallicLookAndFeel::meterRed
                 : meterR > 0.7f ? MetallicLookAndFeel::meterYellow
                 : MetallicLookAndFeel::meterGreen);
    g.fillRect (rightArea.withTop (rightArea.getBottom() - rightFill));

    // Border
    g.setColour (MetallicLookAndFeel::border);
    g.drawRect (getLocalBounds(), 1);
}

void MixerStrip::resized()
{
    auto area = getLocalBounds().reduced (2);
    area.removeFromTop (4); // colour strip

    nameLabel.setBounds (area.removeFromBottom (16));

    auto buttonRow = area.removeFromBottom (18);
    muteButton.setBounds (buttonRow.removeFromLeft (buttonRow.getWidth() / 2).reduced (1));
    soloButton.setBounds (buttonRow.reduced (1));

    panKnob.setBounds (area.removeFromTop (30).reduced (4));

    area.removeFromRight (12); // VU meter space
    volumeSlider.setBounds (area.reduced (2));
}

void MixerStrip::setLevel (float levelL, float levelR)
{
    meterL = juce::jlimit (0.0f, 1.0f, levelL);
    meterR = juce::jlimit (0.0f, 1.0f, levelR);
    repaint();
}

//==============================================================================
// SessionView
//==============================================================================
SessionView::SessionView()
{
    addAndMakeVisible (gridViewport);
    gridViewport.setViewedComponent (&gridContainer, false);
    gridViewport.setScrollBarsShown (true, true);

    addAndMakeVisible (headerContainer);
    addAndMakeVisible (mixerContainer);

    // Create scene launch buttons
    for (int s = 0; s < numScenes; ++s)
    {
        auto* btn = sceneLaunchButtons.add (new juce::TextButton (juce::String (s + 1)));
        btn->setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgMid);
        btn->onClick = [this, s]()
        {
            if (onSceneLaunched) onSceneLaunched (s);
        };
        gridContainer.addAndMakeVisible (btn);
    }

    // Add some default tracks
    addTrack ("Track 1", juce::Colour (0xFF5E81AC));
    addTrack ("Track 2", juce::Colour (0xFFA3BE8C));
    addTrack ("Track 3", juce::Colour (0xFFBF616A));
    addTrack ("Track 4", juce::Colour (0xFFD08770));

    startTimerHz (30);
}

SessionView::~SessionView()
{
    stopTimer();
}

void SessionView::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgDarkest);
}

void SessionView::resized()
{
    rebuildLayout();
}

void SessionView::timerCallback()
{
    // Animate meters - in a real app, this would read from the audio engine
}

void SessionView::addTrack (const juce::String& name, juce::Colour colour)
{
    int idx = trackHeaders.size();

    auto* header = trackHeaders.add (new TrackHeader (idx, name, colour));
    header->onMuteChanged = [this] (int track, bool muted)
    {
        if (onTrackMuteToggled) onTrackMuteToggled (track, muted);
    };
    header->onSoloChanged = [this] (int track, bool soloed)
    {
        if (onTrackSoloToggled) onTrackSoloToggled (track, soloed);
    };
    headerContainer.addAndMakeVisible (header);

    auto* mixer = mixerStrips.add (new MixerStrip (idx, name, colour));
    mixer->onVolumeChanged = [this] (int track, float val)
    {
        if (onVolumeChanged) onVolumeChanged (track, val);
    };
    mixer->onPanChanged = [this] (int track, float val)
    {
        if (onPanChanged) onPanChanged (track, val);
    };
    mixerContainer.addAndMakeVisible (mixer);

    // Create clip slots for this track
    for (int s = 0; s < numScenes; ++s)
    {
        auto* slot = clipSlots.add (new ClipSlot (idx, s));
        slot->onClipTriggered = [this] (int t, int sc)
        {
            if (onClipTriggered) onClipTriggered (t, sc);
        };
        slot->onClipDoubleClick = [this] (int t, int sc)
        {
            if (onClipDoubleClicked) onClipDoubleClicked (t, sc);
        };
        gridContainer.addAndMakeVisible (slot);
    }

    rebuildLayout();
}

void SessionView::removeTrack (int index)
{
    if (index < 0 || index >= trackHeaders.size())
        return;

    trackHeaders.remove (index);
    mixerStrips.remove (index);

    // Remove clip slots for this track (in reverse)
    for (int s = numScenes - 1; s >= 0; --s)
    {
        int slotIdx = index * numScenes + s;
        if (slotIdx < clipSlots.size())
            clipSlots.remove (slotIdx);
    }

    rebuildLayout();
}

void SessionView::setClip (int track, int scene, const juce::String& name)
{
    if (auto* slot = getSlot (track, scene))
        slot->setClipName (name);
}

void SessionView::clearClip (int track, int scene)
{
    if (auto* slot = getSlot (track, scene))
        slot->setClipName ({});
}

void SessionView::setClipPlaying (int track, int scene, bool playing)
{
    if (auto* slot = getSlot (track, scene))
        slot->setPlaying (playing);
}

void SessionView::setNumScenes (int /*scenes*/)
{
    // Would need to rebuild grid - omitted for simplicity
    rebuildLayout();
}

void SessionView::clearTracks()
{
    clipSlots.clear();
    trackHeaders.clear();
    mixerStrips.clear();
    headerContainer.removeAllChildren();
    mixerContainer.removeAllChildren();
    gridContainer.removeAllChildren();

    // Re-add scene launch buttons to grid container
    for (auto* btn : sceneLaunchButtons)
        gridContainer.addAndMakeVisible (btn);

    rebuildLayout();
}

void SessionView::setClipState (int trackIdx, int sceneIdx, bool hasClipState)
{
    if (auto* slot = getSlot (trackIdx, sceneIdx))
    {
        if (hasClipState)
        {
            if (! slot->hasClip())
                slot->setClipName ("Clip");
        }
        else
        {
            slot->setClipName ({});
        }
    }
}

ClipSlot* SessionView::getSlot (int track, int scene)
{
    int idx = track * numScenes + scene;
    return (idx >= 0 && idx < clipSlots.size()) ? clipSlots[idx] : nullptr;
}

void SessionView::rebuildLayout()
{
    int nTracks = trackHeaders.size();
    int totalWidth = nTracks * trackWidth + sceneColWidth;

    // Header container
    headerContainer.setBounds (0, 0, getWidth(), headerHeight);
    for (int t = 0; t < nTracks; ++t)
        trackHeaders[t]->setBounds (t * trackWidth, 0, trackWidth, headerHeight);

    // Grid
    int gridY = headerHeight;
    int gridH = getHeight() - headerHeight - mixerHeight;
    gridViewport.setBounds (0, gridY, getWidth(), gridH);

    int contentH = numScenes * slotHeight;
    gridContainer.setBounds (0, 0, totalWidth, contentH);

    for (int t = 0; t < nTracks; ++t)
    {
        for (int s = 0; s < numScenes; ++s)
        {
            if (auto* slot = getSlot (t, s))
                slot->setBounds (t * trackWidth, s * slotHeight, trackWidth, slotHeight);
        }
    }

    // Scene launch buttons
    for (int s = 0; s < numScenes && s < sceneLaunchButtons.size(); ++s)
        sceneLaunchButtons[s]->setBounds (nTracks * trackWidth, s * slotHeight,
                                          sceneColWidth, slotHeight);

    // Mixer at bottom
    int mixerY = getHeight() - mixerHeight;
    mixerContainer.setBounds (0, mixerY, getWidth(), mixerHeight);
    for (int t = 0; t < nTracks; ++t)
        mixerStrips[t]->setBounds (t * trackWidth, 0, trackWidth, mixerHeight);
}
