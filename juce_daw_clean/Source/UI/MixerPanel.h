/*
 * MidiGPT DAW - MixerPanel
 *
 * Channel strip mixer with VU meters, dB faders, pan knobs.
 * Strip width 80px, master 100px.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <array>
#include "../Core/AudioEngine.h"

class MixerPanel : public juce::Component,
                   public juce::Timer
{
public:
    explicit MixerPanel(AudioEngine& engine);

    void paint(juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;
    void refresh();
    void scrollToTrack(int trackId); // MM6

private:
    AudioEngine& audioEngine;

    struct ChannelStrip
    {
        int trackId { -1 };
        bool isMaster { false };

        std::unique_ptr<juce::Slider>     fader;
        std::unique_ptr<juce::Slider>     panKnob;
        std::unique_ptr<juce::TextButton> muteBtn;
        std::unique_ptr<juce::TextButton> soloBtn;
        std::unique_ptr<juce::Label>      nameLabel;
        std::unique_ptr<juce::Label>      dbLabel;

        // HH4 — FX bypass toggle
        std::unique_ptr<juce::TextButton> fxBypassBtn;

        // V2/W2 — up to 2 send slots per strip
        struct SendSlot
        {
            std::unique_ptr<juce::ComboBox> busCombo;
            std::unique_ptr<juce::Slider>   level;
        };
        std::array<SendSlot, 2> sends;

        juce::Colour trackColour;

        // VU meter state
        float vuL { 0.0f }, vuR { 0.0f };
        float peakL { 0.0f }, peakR { 0.0f };
    };

    std::vector<ChannelStrip> strips;
    std::vector<ChannelStrip> busStrips;   // T4 — mixer strips for user buses
    ChannelStrip masterStrip;

    juce::TextButton addBusButton { "+ Bus" };

    void rebuildStrips();
    void buildBusStrip(ChannelStrip& cs, int busId);
    void drawVuMeter(juce::Graphics& g, int x, int y, int w, int h, float level, float peak);
    void mouseDown(const juce::MouseEvent& e) override;   // X5
    void showBusContextMenu(int busId);                   // X5

    // CC4 — horizontal scroll
    int scrollX { 0 };
    void mouseWheelMove(const juce::MouseEvent& e,
                        const juce::MouseWheelDetails& w) override;
    int  totalContentWidth() const;

    static constexpr int stripWidth  = 80;
    static constexpr int busWidth    = 80;
    static constexpr int masterWidth = 100;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MixerPanel)
};
