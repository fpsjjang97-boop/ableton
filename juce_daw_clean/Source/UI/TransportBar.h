/*
 * MidiGPT DAW - TransportBar
 *
 * Full transport with BPM, key/scale selection, snap, loop, metronome.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Core/AudioEngine.h"

class TransportBar : public juce::Component,
                     public juce::Timer
{
public:
    explicit TransportBar(AudioEngine& engine);

    void paint(juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;
    void mouseDown(const juce::MouseEvent& e) override; // OO5
    void mouseDoubleClick(const juce::MouseEvent& e) override; // SS2

private:
    AudioEngine& audioEngine;

    juce::TextButton rewindButton  { "<<" };
    juce::TextButton playButton    { "Play" };
    juce::TextButton stopButton    { "Stop" };
    juce::TextButton recordButton  { "Rec" };
    juce::TextButton loopButton    { "Loop" };
    juce::TextButton metroButton   { "Metro" };

    juce::Slider  tempoSlider;
    juce::Label   positionLabel { {}, "1.1.000" };
    juce::Label   timeLabel     { {}, "0:00.000" };

    juce::ComboBox keySelector;
    juce::ComboBox scaleSelector;
    juce::ComboBox snapSelector;
    juce::ComboBox countInSelector;  // Z3 — 0..4 bars

    bool showTimeFormat { false }; // OO5 — false=bar:beat, true=min:sec

public:
    // FF6 — tempo tap (public for keyboard shortcut access)
    void handleTap();
private:
    juce::TextButton tapButton { "Tap" };
    std::vector<double> tapTimes;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TransportBar)
};
