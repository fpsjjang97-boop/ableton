/*
 * MidiGPT DAW - MixerPanel
 *
 * Channel strip mixer with VU meters, dB faders, pan knobs.
 * Strip width 80px, master 100px.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
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

        juce::Colour trackColour;

        // VU meter state
        float vuL { 0.0f }, vuR { 0.0f };
        float peakL { 0.0f }, peakR { 0.0f };
    };

    std::vector<ChannelStrip> strips;
    ChannelStrip masterStrip;

    void rebuildStrips();
    void drawVuMeter(juce::Graphics& g, int x, int y, int w, int h, float level, float peak);

    static constexpr int stripWidth  = 80;
    static constexpr int masterWidth = 100;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MixerPanel)
};
