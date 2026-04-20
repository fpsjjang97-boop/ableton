/*
 * MidiGPT DAW - MixerPanel.cpp
 */

#include "MixerPanel.h"
#include "LookAndFeel.h"   // palette tokens (review fix)

MixerPanel::MixerPanel(AudioEngine& engine)
    : audioEngine(engine)
{
    addBusButton.onClick = [this] {
        audioEngine.getBusModel().addBus("Bus " +
            juce::String((int)audioEngine.getBusModel().getBuses().size()));
        rebuildStrips();
    };
    addAndMakeVisible(addBusButton);
    startTimerHz(30);
}

void MixerPanel::buildBusStrip(ChannelStrip& cs, int busId)
{
    auto* bus = audioEngine.getBusModel().getBus(busId);
    if (bus == nullptr) return;

    cs.trackId      = busId;
    cs.isMaster     = false;
    cs.trackColour  = bus->colour;

    cs.nameLabel = std::make_unique<juce::Label>("", "BUS:" + bus->name);
    cs.nameLabel->setFont(juce::Font(10.0f, juce::Font::bold));
    cs.nameLabel->setJustificationType(juce::Justification::centred);
    cs.nameLabel->setColour(juce::Label::textColourId, juce::Colour(0xFFB0B0B0));
    addAndMakeVisible(*cs.nameLabel);

    cs.panKnob = std::make_unique<juce::Slider>(juce::Slider::RotaryHorizontalVerticalDrag,
                                                 juce::Slider::NoTextBox);
    cs.panKnob->setRange(-1.0, 1.0, 0.01);
    cs.panKnob->setValue(bus->pan);
    cs.panKnob->setTooltip("버스 패닝 (-1=좌, 0=중앙, 1=우). 더블클릭 = 0");  // KKK3
    cs.panKnob->onValueChange = [this, busId, &p = *cs.panKnob] {
        if (auto* b = audioEngine.getBusModel().getBus(busId))
            b->pan = (float)p.getValue();
    };
    addAndMakeVisible(*cs.panKnob);

    cs.muteBtn = std::make_unique<juce::TextButton>("M");
    cs.muteBtn->setClickingTogglesState(true);
    cs.muteBtn->setToggleState(bus->mute, juce::dontSendNotification);
    cs.muteBtn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(MetallicLookAndFeel::warning));
    cs.muteBtn->setTooltip("버스 음소거");  // KKK3
    cs.muteBtn->onClick = [this, busId, &m = *cs.muteBtn] {
        if (auto* b = audioEngine.getBusModel().getBus(busId))
            b->mute = m.getToggleState();
    };
    addAndMakeVisible(*cs.muteBtn);

    cs.fader = std::make_unique<juce::Slider>(juce::Slider::LinearVertical,
                                               juce::Slider::NoTextBox);
    cs.fader->setRange(-60.0, 6.0, 0.1);
    cs.fader->setSkewFactorFromMidPoint(-12.0);
    cs.fader->setValue(juce::Decibels::gainToDecibels(bus->volume, -60.0f));
    cs.fader->setTooltip("버스 페이더 (-60 dB ~ +6 dB). -12 dB 중간점");  // KKK3
    cs.fader->onValueChange = [this, busId, &f = *cs.fader] {
        if (auto* b = audioEngine.getBusModel().getBus(busId))
            b->volume = juce::Decibels::decibelsToGain((float)f.getValue(), -60.0f);
    };
    addAndMakeVisible(*cs.fader);

    cs.dbLabel = std::make_unique<juce::Label>("", "0.0");
    cs.dbLabel->setFont(juce::Font(9.0f));
    cs.dbLabel->setJustificationType(juce::Justification::centred);
    addAndMakeVisible(*cs.dbLabel);
}

void MixerPanel::rebuildStrips()
{
    strips.clear();
    busStrips.clear();
    for (auto* child : getChildren())
        child->setVisible(false);

    // Remove all children
    removeAllChildren();
    addAndMakeVisible(addBusButton); // re-attach

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
        cs.panKnob->setTooltip("트랙 패닝 (-1=좌, 0=중앙, 1=우)");  // Sprint 47 KKK3
        cs.panKnob->onValueChange = [this, id = track.id, &p = *cs.panKnob] {
            if (auto* t = audioEngine.getTrackModel().getTrack(id))
                t->pan = static_cast<float>(p.getValue());
        };
        addAndMakeVisible(*cs.panKnob);

        // Mute
        cs.muteBtn = std::make_unique<juce::TextButton>("M");
        cs.muteBtn->setClickingTogglesState(true);
        cs.muteBtn->setToggleState(track.mute, juce::dontSendNotification);
        cs.muteBtn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(MetallicLookAndFeel::warning));
        cs.muteBtn->setTooltip("트랙 음소거");  // Sprint 47 KKK3
        cs.muteBtn->onClick = [this, id = track.id, &m = *cs.muteBtn] {
            if (auto* t = audioEngine.getTrackModel().getTrack(id))
                t->mute = m.getToggleState();
        };
        addAndMakeVisible(*cs.muteBtn);

        // Solo
        cs.soloBtn = std::make_unique<juce::TextButton>("S");
        cs.soloBtn->setClickingTogglesState(true);
        cs.soloBtn->setToggleState(track.solo, juce::dontSendNotification);
        cs.soloBtn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(MetallicLookAndFeel::meterYellow));
        cs.soloBtn->setTooltip("트랙 솔로 — 다른 트랙 자동 음소거");  // Sprint 47 KKK3
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
        cs.fader->setTooltip("트랙 볼륨 (-60 dB ~ +6 dB). 더블클릭 = 0 dB");  // Sprint 47 KKK3
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

        // HH4 — FX bypass button (toggles bypass on first plugin slot)
        if (! track.plugins.empty())
        {
            cs.fxBypassBtn = std::make_unique<juce::TextButton>("FX");
            cs.fxBypassBtn->setClickingTogglesState(true);
            cs.fxBypassBtn->setToggleState(! track.plugins[0].bypass, juce::dontSendNotification);
            cs.fxBypassBtn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(MetallicLookAndFeel::accent));
            cs.fxBypassBtn->setColour(juce::TextButton::buttonColourId, juce::Colour(0xFF333333));
            cs.fxBypassBtn->setTooltip("FX 체인 활성/바이패스 (첫 슬롯)");  // Sprint 47 KKK3
            cs.fxBypassBtn->onClick = [this, id = track.id, &btn = *cs.fxBypassBtn] {
                auto* t = audioEngine.getTrackModel().getTrack(id);
                if (t != nullptr && ! t->plugins.empty())
                    t->plugins[0].bypass = ! btn.getToggleState();
            };
            addAndMakeVisible(*cs.fxBypassBtn);
        }

        // V2/W2 — build up to 2 send slots
        for (int slot = 0; slot < 2; ++slot)
        {
            auto& ss = cs.sends[slot];
            ss.busCombo = std::make_unique<juce::ComboBox>();
            ss.busCombo->addItem("-- send --", 1);
            int comboId = 2;
            for (auto& b : audioEngine.getBusModel().getBuses())
            {
                if (b.id == 0) continue;
                ss.busCombo->addItem(b.name, comboId++);
            }

            int selected = 1;
            float level = 0.0f;
            if (slot < (int)track.sends.size())
            {
                int id = 2;
                for (auto& b : audioEngine.getBusModel().getBuses())
                {
                    if (b.id == 0) continue;
                    if (b.id == track.sends[slot].busId) { selected = id; break; }
                    ++id;
                }
                level = track.sends[slot].level;
            }
            ss.busCombo->setSelectedId(selected, juce::dontSendNotification);
            ss.busCombo->onChange = [this, id = track.id, slot,
                                      combo = ss.busCombo.get()] {
                auto* t = audioEngine.getTrackModel().getTrack(id);
                if (t == nullptr) return;
                while ((int)t->sends.size() <= slot)
                    t->sends.push_back({ 0, 0.0f });
                const int sel = combo->getSelectedId();
                if (sel <= 1) { t->sends[slot].busId = 0; t->sends[slot].level = 0.0f; return; }
                int walk = 2;
                for (auto& bb : audioEngine.getBusModel().getBuses())
                {
                    if (bb.id == 0) continue;
                    if (walk == sel)
                    { t->sends[slot].busId = bb.id; if (t->sends[slot].level <= 0.0f) t->sends[slot].level = 0.5f; return; }
                    ++walk;
                }
            };
            addAndMakeVisible(*ss.busCombo);

            ss.level = std::make_unique<juce::Slider>(juce::Slider::RotaryHorizontalVerticalDrag,
                                                       juce::Slider::NoTextBox);
            ss.level->setRange(0.0, 1.0, 0.01);
            ss.level->setValue(level);
            ss.level->onValueChange = [this, id = track.id, slot,
                                        knob = ss.level.get()] {
                auto* t = audioEngine.getTrackModel().getTrack(id);
                if (t == nullptr) return;
                while ((int)t->sends.size() <= slot) t->sends.push_back({ 0, 0.0f });
                t->sends[slot].level = (float)knob->getValue();
            };
            addAndMakeVisible(*ss.level);
        }

        strips.push_back(std::move(cs));
    }

    // T4 — User bus strips (between tracks and master)
    for (auto& bus : audioEngine.getBusModel().getBuses())
    {
        if (bus.id == 0) continue; // master handled separately
        ChannelStrip cs;
        buildBusStrip(cs, bus.id);
        busStrips.push_back(std::move(cs));
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
    repaint();         // review fix — without this, strips paint only on hover
}

void MixerPanel::refresh()
{
    rebuildStrips();
    repaint();
}

void MixerPanel::drawVuMeter(juce::Graphics& g, int x, int y, int w, int h,
                              float level, float peak)
{
    // Background
    g.setColour(juce::Colour(MetallicLookAndFeel::bgDarkest));
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
        g.setColour(juce::Colour(MetallicLookAndFeel::meterYellow));
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

// MM6 — scroll so a given track's strip is visible
void MixerPanel::scrollToTrack(int trackId)
{
    for (size_t i = 0; i < strips.size(); ++i)
    {
        if (strips[i].trackId == trackId)
        {
            int targetX = (int)i * stripWidth;
            if (targetX < scrollX || targetX + stripWidth > scrollX + getWidth())
            {
                scrollX = juce::jmax(0, targetX - getWidth() / 4);
                resized();
                repaint();
            }
            return;
        }
    }
}

// CC4 — total width of all strips combined
int MixerPanel::totalContentWidth() const
{
    return (int)strips.size() * stripWidth
         + (int)busStrips.size() * busWidth
         + 70 + masterWidth + 20;
}

void MixerPanel::mouseWheelMove(const juce::MouseEvent&,
                                 const juce::MouseWheelDetails& w)
{
    int maxScroll = juce::jmax(0, totalContentWidth() - getWidth());
    scrollX = juce::jlimit(0, maxScroll,
        scrollX - (int)(w.deltaY * 80));
    resized();
    repaint();
}

void MixerPanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(MetallicLookAndFeel::bgDarkest));

    // CC4 — apply scroll offset
    const int sx = -scrollX;

    // Strip dividers
    for (size_t i = 0; i <= strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth + sx;
        g.setColour(juce::Colour(0xFF2A2A2A));
        g.drawVerticalLine(x, 0.0f, (float)getHeight());
    }

    // Track colour bars (3px at top)
    for (size_t i = 0; i < strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth + sx;
        g.setColour(strips[i].trackColour);
        g.fillRect(x, 0, stripWidth, 3);
    }

    // T4 — bus area divider + colour bars
    int busBaseX = (int)strips.size() * stripWidth + sx;
    g.setColour(juce::Colour(0xFF333333));
    g.drawVerticalLine(busBaseX, 0.0f, (float)getHeight());
    for (size_t i = 0; i < busStrips.size(); ++i)
    {
        int x = busBaseX + (int)i * busWidth;
        g.setColour(busStrips[i].trackColour);
        g.fillRect(x, 0, busWidth, 3);
    }

    // Master divider
    int masterX = busBaseX + (int)busStrips.size() * busWidth + 66;
    g.setColour(juce::Colour(0xFF444444));
    g.drawVerticalLine(masterX, 0.0f, (float)getHeight());

    // Master colour bar
    g.setColour(juce::Colour(0xFFE0E0E0));
    g.fillRect(masterX, 0, masterWidth, 3);

    // VU meters for each strip
    for (size_t i = 0; i < strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth + sx;
        int faderRight = x + stripWidth - 4;
        int meterY = 80;
        int meterH = getHeight() - meterY - 20;

        drawVuMeter(g, faderRight - 12, meterY, 5, meterH, strips[i].vuL, strips[i].peakL);
        drawVuMeter(g, faderRight - 5, meterY, 5, meterH, strips[i].vuR, strips[i].peakR);
    }

    // TT1 — output bus label per strip
    g.setFont(7.0f);
    for (size_t i = 0; i < strips.size(); ++i)
    {
        auto* t = audioEngine.getTrackModel().getTrack(strips[i].trackId);
        if (t == nullptr) continue;
        int x = (int)i * stripWidth + sx;
        juce::String busName = "Master";
        if (t->outputBusId != 0)
            if (auto* b = audioEngine.getBusModel().getBus(t->outputBusId))
                busName = b->name;
        g.setColour(juce::Colour(0xFF606060));
        g.drawText(busName, x + 2, getHeight() - 28, stripWidth - 4, 10,
                   juce::Justification::centred);
    }

    // Master VU (uses recomputed masterX from above)
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
    const int sx = -scrollX; // CC4

    for (size_t i = 0; i < strips.size(); ++i)
    {
        int x = static_cast<int>(i) * stripWidth + 4 + sx;
        int w = stripWidth - 8;

        strips[i].nameLabel->setBounds(x, 5, w, 16);
        strips[i].panKnob->setBounds(x + w / 4, 24, w / 2, 36);

        int btnY = 62;
        int halfW = (w - 4) / 2;
        strips[i].muteBtn->setBounds(x, btnY, halfW, 20);
        strips[i].soloBtn->setBounds(x + halfW + 4, btnY, halfW, 20);

        // HH4 — FX bypass button
        if (strips[i].fxBypassBtn)
            strips[i].fxBypassBtn->setBounds(x + w - 24, btnY, 24, 20);

        // V2/W2 — 2 send slots above the fader
        const int sendY = 86;
        const int slotH = 32;
        for (int slot = 0; slot < 2; ++slot)
        {
            auto& ss = strips[i].sends[slot];
            const int yOff = sendY + slot * slotH;
            if (ss.busCombo) ss.busCombo->setBounds(x, yOff, w, 14);
            if (ss.level)    ss.level->setBounds(x + w / 4, yOff + 15, w / 2, 14);
        }
        int faderY = sendY + 2 * slotH + 4;
        int faderH = getHeight() - faderY - 18;
        strips[i].fader->setBounds(x + 4, faderY, w - 22, faderH);

        strips[i].dbLabel->setBounds(x, getHeight() - 16, w, 14);

        // TT1 — draw output bus name below fader (in paint, not here)
    }

    // T4 — bus strips (between track strips and master)
    int busBaseX = static_cast<int>(strips.size()) * stripWidth + sx;
    for (size_t i = 0; i < busStrips.size(); ++i)
    {
        int x = busBaseX + (int)i * busWidth + 4;
        int w = busWidth - 8;

        if (busStrips[i].nameLabel) busStrips[i].nameLabel->setBounds(x, 5, w, 16);
        if (busStrips[i].panKnob)   busStrips[i].panKnob->setBounds(x + w / 4, 24, w / 2, 36);
        if (busStrips[i].muteBtn)   busStrips[i].muteBtn->setBounds(x, 62, w, 20);
        int faderY = 86;
        int faderH = getHeight() - faderY - 18;
        if (busStrips[i].fader)     busStrips[i].fader->setBounds(x + 4, faderY, w - 22, faderH);
        if (busStrips[i].dbLabel)   busStrips[i].dbLabel->setBounds(x, getHeight() - 16, w, 14);
    }

    addBusButton.setBounds(busBaseX + (int)busStrips.size() * busWidth + 4, 5, 60, 20);

    // Master
    int mx = busBaseX + (int)busStrips.size() * busWidth + 70;
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

void MixerPanel::mouseDown(const juce::MouseEvent& e)
{
    // MM5 — left-click on VU meter area → reset peak hold
    if (! e.mods.isRightButtonDown())
    {
        // Check if click is in master VU area
        const int busBaseX = (int)strips.size() * stripWidth - scrollX;
        const int masterX = busBaseX + (int)busStrips.size() * busWidth + 66;
        if (e.x >= masterX)
        {
            masterStrip.peakL = 0.0f;
            masterStrip.peakR = 0.0f;
            return;
        }
        // Check track strip VU area
        for (size_t i = 0; i < strips.size(); ++i)
        {
            int sx = (int)i * stripWidth - scrollX;
            if (e.x >= sx && e.x < sx + stripWidth && e.y > 80)
            {
                strips[i].peakL = 0.0f;
                strips[i].peakR = 0.0f;
                return;
            }
        }
        return;
    }

    // X5 — right-click on a bus strip opens context menu
    if (! e.mods.isRightButtonDown()) return;

    const int busBaseX = (int)strips.size() * stripWidth - scrollX; // CC4
    if (e.x < busBaseX) return;

    const int idx = (e.x - busBaseX) / busWidth;
    if (idx < 0 || idx >= (int)busStrips.size()) return;
    showBusContextMenu(busStrips[(size_t)idx].trackId);
}

void MixerPanel::showBusContextMenu(int busId)
{
    auto* bus = audioEngine.getBusModel().getBus(busId);
    if (bus == nullptr) return;

    juce::PopupMenu menu;
    menu.addItem(1, "Rename...");
    menu.addItem(2, "Delete");
    menu.addSeparator();

    juce::PopupMenu outMenu;
    outMenu.addItem(100, "Master", true, bus->outputBusId == 0);
    for (auto& b : audioEngine.getBusModel().getBuses())
    {
        if (b.id == 0 || b.id == busId) continue;
        outMenu.addItem(100 + b.id, b.name, true, bus->outputBusId == b.id);
    }
    menu.addSubMenu("Output Bus", outMenu);

    menu.showMenuAsync(juce::PopupMenu::Options(),
        [this, busId](int result)
        {
            auto* b = audioEngine.getBusModel().getBus(busId);
            if (b == nullptr) return;
            if (result == 1)
            {
                auto* aw = new juce::AlertWindow("Rename Bus", "New name:",
                                                  juce::MessageBoxIconType::NoIcon);
                aw->addTextEditor("n", b->name);
                aw->addButton("OK", 1);
                aw->addButton("Cancel", 0);
                aw->enterModalState(true, juce::ModalCallbackFunction::create(
                    [this, aw, busId](int r) {
                        if (r == 1)
                            if (auto* bb = audioEngine.getBusModel().getBus(busId))
                                bb->name = aw->getTextEditorContents("n");
                        delete aw;
                        rebuildStrips();
                    }), false);
            }
            else if (result == 2)
            {
                audioEngine.getBusModel().removeBus(busId);
                rebuildStrips();
            }
            else if (result >= 100 && result < 200)
            {
                b->outputBusId = result - 100;
            }
        });
}

void MixerPanel::timerCallback()
{
    // Update master VU from engine
    masterStrip.vuL = masterStrip.vuL * 0.92f + audioEngine.getVuLeft() * 0.08f;
    masterStrip.vuR = masterStrip.vuR * 0.92f + audioEngine.getVuRight() * 0.08f;
    masterStrip.peakL = juce::jmax(masterStrip.peakL * 0.997f, audioEngine.getVuLeft());
    masterStrip.peakR = juce::jmax(masterStrip.peakR * 0.997f, audioEngine.getVuRight());

    // LL3 + NN4 — sync M/S + fader from track model
    for (auto& strip : strips)
    {
        auto* t = audioEngine.getTrackModel().getTrack(strip.trackId);
        if (t != nullptr)
        {
            if (strip.muteBtn) strip.muteBtn->setToggleState(t->mute, juce::dontSendNotification);
            if (strip.soloBtn) strip.soloBtn->setToggleState(t->solo, juce::dontSendNotification);
            // OO4 — per-track VU
            strip.vuL = strip.vuL * 0.9f + audioEngine.getTrackVuL(strip.trackId) * 0.1f;
            strip.vuR = strip.vuR * 0.9f + audioEngine.getTrackVuR(strip.trackId) * 0.1f;
            strip.peakL = juce::jmax(strip.peakL * 0.997f, audioEngine.getTrackVuL(strip.trackId));
            strip.peakR = juce::jmax(strip.peakR * 0.997f, audioEngine.getTrackVuR(strip.trackId));
            // NN4 — sync fader if not being dragged
            if (strip.fader && ! strip.fader->isMouseButtonDown())
            {
                double db = juce::Decibels::gainToDecibels(t->volume, -60.0f);
                if (std::abs(strip.fader->getValue() - db) > 0.2)
                    strip.fader->setValue(db, juce::dontSendNotification);
            }
        }
    }

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
