#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"

//==============================================================================
// TransportBar - Top transport control bar (36px height)
//==============================================================================
class TransportBar : public juce::Component,
                     public juce::Timer
{
public:
    TransportBar();
    ~TransportBar() override = default;

    void paint (juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    // ── State getters ───────────────────────────────────────────────────────
    double getBpm() const;
    bool   isPlaying() const;
    bool   isRecording() const;
    bool   isLoopEnabled() const;
    bool   isMetronomeEnabled() const;
    int    getSnapDivision() const;
    int    getKeyIndex() const;
    int    getScaleIndex() const;

    // ── State setters ───────────────────────────────────────────────────────
    void setBpm (double bpm);
    void setBPM (double bpm);
    void setPlaying (bool playing);
    void setRecording (bool recording);
    void setPosition (int bar, int beat, int tick);
    void setTimeDisplay (double seconds);
    void setPositionInfo (double beats, double seconds);
    void setCpuUsage (float percent);

    // ── Callbacks ───────────────────────────────────────────────────────────
    std::function<void (double)>   onBpmChanged;
    std::function<void (double)>&  onBPMChanged = onBpmChanged;  // alias
    std::function<void()>          onPlay;
    std::function<void()>          onStop;
    std::function<void()>          onRecord;
    std::function<void (bool)>     onLoopToggled;
    std::function<void (bool)>     onMetronomeToggled;
    std::function<void (int)>      onSnapChanged;
    std::function<void (int, int)> onKeyScaleChanged;

private:
    // ── Transport buttons ───────────────────────────────────────────────────
    juce::TextButton playButton   { "Play" };
    juce::TextButton stopButton   { "Stop" };
    juce::TextButton recordButton { "Rec" };

    // ── BPM ─────────────────────────────────────────────────────────────────
    juce::Slider bpmSlider;
    juce::Label  bpmLabel;

    // ── Position / Time ─────────────────────────────────────────────────────
    juce::Label positionLabel;
    juce::Label timeLabel;

    // ── Key / Scale ─────────────────────────────────────────────────────────
    juce::ComboBox keySelector;
    juce::ComboBox scaleSelector;

    // ── Snap ────────────────────────────────────────────────────────────────
    juce::ComboBox snapSelector;

    // ── Toggles ─────────────────────────────────────────────────────────────
    juce::TextButton loopButton      { "Loop" };
    juce::TextButton metronomeButton { "Metro" };

    // ── CPU meter ───────────────────────────────────────────────────────────
    float cpuUsage = 0.0f;
    juce::Label cpuLabel;

    // ── State ───────────────────────────────────────────────────────────────
    bool playing   = false;
    bool recording = false;

    void setupBpmSlider();
    void setupSelectors();
    void setupButtons();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TransportBar)
};
