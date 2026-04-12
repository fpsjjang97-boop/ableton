/*
 * MidiGPT DAW - MixerPanel.cpp
 */

#include "MixerPanel.h"

MixerPanel::MixerPanel(AudioEngine& engine)
    : audioEngine(engine)
{
    startTimerHz(30);
}

void MixerPanel::rebuildStrips()
{
    strips.clear();
    for (auto* child : getChildren())
        child->setVisible(false);

    // Remove all children
    removeAllChildren();

    auto& tracks = audioEngine.getTrackModel().getTracks();

    for (auto& track : tracks)
    {
        ChannelStrip cs;
        cs.trackId = track.id;
        cs.trackColour = track.colour;

        // Name
        cs.nameLabel = std::make_unique<juce::Label>("", track.name);
        cs.nameLabel->setFont(juce::Font(10.0f, juce::Font::bold));
        cs.nameLabel->setJustificationType(juce::Justification::centred);
        cs.nameLabel->setColour(juce::Label::textColourId, track.colour);
        addAndMakeVisible(*cs.nameLabel);

        // Pan
        cs.panKnob = std::make_unique<juce::Slider>(juce::Slider::RotaryHorizontalVerticalDrag,
                                                     juce::Slider::NoTextBox);
        cs.panKnob->setRange(-1.0, 1.0, 0.01);
        cs.panKnob->setValue(track.pan);
        cs.panKnob->onValueChange = [this, id = track.id, &p = *cs.panKnob] {
            if (auto* t = audioEngine.getTrackModel().getTrack(id))
                t->pan = static_cast<float>(p.getValue());
        };
        addAndMakeVisible(*cs.panKnob);

        // Mute
        cs.muteBtn = std::make_unique<juce::TextButton>("M");
        cs.muteBtn->setClickingTogglesState(true);
        cs.muteBtn->setToggleState(track.mute, juce::dontSendNotification);
        cs.muteBtn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(0xFFFF5722));
        cs.muteBtn->onClick = [this, id = track.id, &m = *cs.muteBtn] {
            if (auto* t = audioEngine.getTrackModel().getTrack(id))
                t->mute = m.getToggleState();
        };
        addAndMakeVisible(*cs.muteBtn);

        // Solo
        cs.soloBtn = std::make_unique<juce::TextButton>("S");
        cs.soloBtn->setClickingTogglesState(true);
        cs.soloBtn->setToggleState(track.solo, juce::dontSendNotification);
        cs.soloBtn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(0xFFFFC107));
        cs.soloBtn->onClick = [this, id = track.id, &s = *cs.soloBtn] {
            if (auto* t = audioEngine.getTrackModel().getTrack(id))
                t->solo = s.getToggleState();
        };
        addAndMakeVisible(*cs.soloBtn);

        // Volume fader (-60 to +6 dB, skew at -12)
        cs.fader = std::make_unique<juce::Slider>(juce::Slider::LinearVertical,
                                                   juce::Slider::NoTextBox);
        cs.fader->setRange(-60.0, 6.0, 0.1);
        cs.fader->setSkewFactorFromMidPoint(-12.0);
        cs.fader->setValue(juce::Decibels::gainToDecibels(track.volume, -60.0f));
        cs.fader->onValueChange = [this, id = track.id, &f = *cs.fader] {
            if (auto* t = audioEngine.getTrackModel().getTrack(id))
                t->volume = juce::Decibels::decibelsToGain(static_cast<float>(f.getValue()), -60.0f);
        };
        addAndMakeVisible(*cs.fader);

        // dB label
        cs.dbLabel = std::make_unique<juce::Label>("", "0.0");
        cs.dbLabel->setFont(juce::Font(9.0f));
        cs.dbLabel->setJustificationType(juce::Justification::centred);
        cs.dbLabel->setColour(juce::Label::textColourId, juce::Colour(0xFF909090));
        addAndMakeVisible(*cs.dbLabel);

        strips.push_back(std::move(cs));
    }

    // Master strip
    masterStrip = {};
    masterStrip.isMaster = true;
    masterStrip.trackColour = juce::Colour(0xFFE0E0E0);

    masterStrip.nameLabel = std::make_unique<juce::Label>("", "MASTER");
    masterStrip.nameLabel->setFont(juce::Font(10.0f, juce::Font::bold));
    masterStrip.nameLabel->setJustificationType(juce::Justification::centred);
    masterStrip.nameLabel->setColour(juce::Label::textColourId, juce::Colour(0xFFE0E0E0));
    addAndMakeVisible(*masterStrip.nameLabel);

    masterStrip.fader = std::make_unique<juce::Slider>(juce::Slider::LinearVertical,
                                                        juce::Slider::NoTextBox);
    masterStrip.fader->setRange(-60.0, 6.0, 0.1);
    masterStrip.fader->setSkewFactorFromMidPoint(-12.0);
    masterStrip.fader->setValue(0.0);
    masterStrip.fader->onValueChange = [this] {
        audioEngine.setMasterVolume(
            juce::Decibels::decibelsToGain(static_cast<float>(masterStrip.fader->getValue()), -60.0f));
    };
    addAndMakeVisible(*masterStrip.fader);

    masterStrip.dbLabel = std::make_unique<juce::Label>("", "0.0");
    masterStrip.dbLabel->setFont(juce::Font(9.0f));
    masterStrip.dbLabel->setJustificationType(juce::Justification::centred);
    masterStrip.dbLabel->setColour(juce::Label::textColourId, juce::Colour(0xFF909090));
    addAndMakeVisible(*masterStrip.dbLabel);

    resized();
}

void MixerPanel::refresh()
{
    rebuildStrips();
}

void MixerPanel::drawVuMeter(juce::Graphics& g, int x, int y, int w, int h,
                              float level, float peak)
{
    // Background
    g.setColour(juce::Colour(0xFF0E0E0E));
    g.fillRect(x, y, w, h);

    float barH = level * h;
    float greenH = h * 0.7f;
    float yellowH = h * 0.2f;

    // Green zone
    float drawH = juce::jmin(barH, greenH);
    g.setColour(juce::Colour(0xFF4CAF50));
    g.fillRect((float)x, (float)(y + h) - drawH, (float)w, drawH);

    // Yellow zone
    if (barH > greenH)
    {
        float yH = juce::jmin(barH - greenH, yellowH);
        g.setColour(juce::Colour(0xFFFFC107));
        g.fillRect((float)x, (float)(y + h - greenH) - yH, (float)w, yH);
    }

    // Red zone
    if (barH > greenH + yellowH)
    {
        float rH = barH - greenH - yellowH;
        g.setColour(juce::Colour(0xFFF44336));
        g.fillRect((float)x, (float)(y + h - greenH - yellowH) - rH, (float)w, rH);
    }

    // Peak indicator
    if (peak > 0.01f)
    {
        float peakY = (float)(y + h) - peak * h;
        g.setColour(peak > 0.95f ? juce::Colour(0xFFF44336) : juce::Colour(0xFFE0E0E0));
        g.drawHorizontalLine(static_cast<int>(peakY), (float)x, (float)(x + w));
    }
}

void MixerPanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF0E0E0E));

    // Strip dividers
    for (size_t i = 0; i <= strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth;
        g.setColour(juce::Colour(0xFF2A2A2A));
        g.drawVerticalLine(x, 0.0f, (float)getHeight());
    }

    // Track colour bars (3px at top)
    for (size_t i = 0; i < strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth;
        g.setColour(strips[i].trackColour);
        g.fillRect(x, 0, stripWidth, 3);
    }

    // Master divider
    int masterX = static_cast<int>(strips.size()) * stripWidth;
    g.setColour(juce::Colour(0xFF444444));
    g.drawVerticalLine(masterX, 0.0f, (float)getHeight());

    // Master colour bar
    g.setColour(juce::Colour(0xFFE0E0E0));
    g.fillRect(masterX, 0, masterWidth, 3);

    // VU meters for each strip
    for (size_t i = 0; i < strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth;
        int faderRight = x + stripWidth - 4;
        int meterY = 80;
        int meterH = getHeight() - meterY - 20;

        drawVuMeter(g, faderRight - 12, meterY, 5, meterH, strips[i].vuL, strips[i].peakL);
        drawVuMeter(g, faderRight - 5, meterY, 5, meterH, strips[i].vuR, strips[i].peakR);
    }

    // Master VU
    {
        int meterY = 40;
        int meterH = getHeight() - meterY - 20;
        drawVuMeter(g, masterX + masterWidth - 16, meterY, 5, meterH,
                    masterStrip.vuL, masterStrip.peakL);
        drawVuMeter(g, masterX + masterWidth - 9, meterY, 5, meterH,
                    masterStrip.vuR, masterStrip.peakR);
    }
}

void MixerPanel::resized()
{
    for (size_t i = 0; i < strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth + 4;
        int w = stripWidth - 8;

        strips[i].nameLabel->setBounds(x, 5, w, 16);
        strips[i].panKnob->setBounds(x + w / 4, 24, w / 2, 36);

        int btnY = 62;
        int halfW = (w - 4) / 2;
        strips[i].muteBtn->setBounds(x, btnY, halfW, 20);
        strips[i].soloBtn->setBounds(x + halfW + 4, btnY, halfW, 20);

        int faderY = 86;
        int faderH = getHeight() - faderY - 18;
        strips[i].fader->setBounds(x + 4, faderY, w - 22, faderH);

        strips[i].dbLabel->setBounds(x, getHeight() - 16, w, 14);
    }

    // Master
    int mx = static_cast<int>(strips.size()) * stripWidth + 4;
    int mw = masterWidth - 8;

    if (masterStrip.nameLabel)
        masterStrip.nameLabel->setBounds(mx, 5, mw, 16);
    if (masterStrip.fader)
    {
        int faderY = 40;
        int faderH = getHeight() - faderY - 18;
        masterStrip.fader->setBounds(mx + 4, faderY, mw - 26, faderH);
    }
    if (masterStrip.dbLabel)
        masterStrip.dbLabel->setBounds(mx, getHeight() - 16, mw, 14);
}

void MixerPanel::timerCallback()
{
    // Update master VU from engine
    masterStrip.vuL = masterStrip.vuL * 0.92f + audioEngine.getVuLeft() * 0.08f;
    masterStrip.vuR = masterStrip.vuR * 0.92f + audioEngine.getVuRight() * 0.08f;
    masterStrip.peakL = juce::jmax(masterStrip.peakL * 0.997f, audioEngine.getVuLeft());
    masterStrip.peakR = juce::jmax(masterStrip.peakR * 0.997f, audioEngine.getVuRight());

    // Update dB labels
    for (auto& strip : strips)
    {
        if (strip.fader && strip.dbLabel)
        {
            float db = static_cast<float>(strip.fader->getValue());
            strip.dbLabel->setText(juce::String(db, 1) + " dB", juce::dontSendNotification);
        }
    }
    if (masterStrip.fader && masterStrip.dbLabel)
    {
        float db = static_cast<float>(masterStrip.fader->getValue());
        masterStrip.dbLabel->setText(juce::String(db, 1) + " dB", juce::dontSendNotification);
    }

    repaint();
}
