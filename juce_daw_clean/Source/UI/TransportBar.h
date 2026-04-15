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

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TransportBar)
};
