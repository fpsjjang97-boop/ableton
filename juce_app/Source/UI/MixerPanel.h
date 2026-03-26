#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"

//==============================================================================
// ChannelStrip - Full mixer channel strip
//==============================================================================
class ChannelStrip : public juce::Component,
                     public juce::Timer
{
public:
    ChannelStrip (int index, const juce::String& name, juce::Colour colour, bool isMaster = false);
    ~ChannelStrip() override;

    void paint (juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    void setTrackName (const juce::String& name);
    void setTrackColour (juce::Colour c);
    void setLevel (float left, float right);
    float getVolume() const { return (float) volumeFader.getValue(); }
    float getPan() const    { return (float) panKnob.getValue(); }

    std::function<void (int, float)> onVolumeChanged;
    std::function<void (int, float)> onPanChanged;
    std::function<void (int, bool)>  onMuteChanged;
    std::function<void (int, bool)>  onSoloChanged;

private:
    int trackIndex;
    bool masterStrip;
    juce::String trackName;
    juce::Colour trackColour;

    juce::Label      nameLabel;
    juce::Slider     volumeFader;
    juce::Slider     panKnob;
    juce::TextButton muteButton { "M" };
    juce::TextButton soloButton { "S" };
    juce::Label      dbLabel;

    float meterL = 0.0f, meterR = 0.0f;
    float peakL  = 0.0f, peakR  = 0.0f;

    void drawMeter (juce::Graphics& g, juce::Rectangle<int> area, float level, float peak);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ChannelStrip)
};

//==============================================================================
// MixerPanel - Full mixer view with channel strips
//==============================================================================
class MixerPanel : public juce::Component
{
public:
    MixerPanel();
    ~MixerPanel() override = default;

    void paint (juce::Graphics& g) override;
    void resized() override;

    void addChannel (const juce::String& name, juce::Colour colour);
    void removeChannel (int index);
    void clearChannels();
    void setChannelLevel (int index, float left, float right);
    int  getNumChannels() const { return channels.size(); }

    std::function<void (int, float)> onVolumeChanged;
    std::function<void (int, float)> onPanChanged;
    std::function<void (int, bool)>  onMuteChanged;
    std::function<void (int, bool)>  onSoloChanged;

private:
    juce::OwnedArray<ChannelStrip> channels;
    std::unique_ptr<ChannelStrip>  masterStrip;
    juce::Viewport viewport;
    juce::Component container;

    static constexpr int stripWidth  = 80;
    static constexpr int masterWidth = 100;

    void rebuildLayout();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MixerPanel)
};
