/*
 * MidiGPT DAW - MetallicLookAndFeel
 *
 * Dark metallic theme. All colours and custom draw routines
 * written from scratch based on standard JUCE LookAndFeel_V4 API.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

class MetallicLookAndFeel : public juce::LookAndFeel_V4
{
public:
    // Colour palette
    static constexpr juce::uint32 bgDarkest   = 0xFF0E0E0E;
    static constexpr juce::uint32 bgDark      = 0xFF161616;
    static constexpr juce::uint32 bgMid       = 0xFF1E1E1E;
    static constexpr juce::uint32 bgPanel     = 0xFF1A1A1A;
    static constexpr juce::uint32 bgHeader    = 0xFF1C1C1C;
    static constexpr juce::uint32 bgSelected  = 0xFF3A3A3A;
    static constexpr juce::uint32 bgHover     = 0xFF2A2A2A;
    static constexpr juce::uint32 accent      = 0xFFC0C0C0;
    static constexpr juce::uint32 accentLight = 0xFFE0E0E0;
    static constexpr juce::uint32 textPrimary = 0xFFE8E8E8;
    static constexpr juce::uint32 textSecondary = 0xFF909090;
    static constexpr juce::uint32 textDim     = 0xFF505050;
    static constexpr juce::uint32 border      = 0xFF2A2A2A;
    static constexpr juce::uint32 gridBar     = 0xFF333333;
    static constexpr juce::uint32 clipColour  = 0xFF5E81AC;
    static constexpr juce::uint32 clipSelected = 0xFF88C0D0;
    static constexpr juce::uint32 meterGreen  = 0xFF4CAF50;
    static constexpr juce::uint32 meterYellow = 0xFFFFC107;
    static constexpr juce::uint32 meterRed    = 0xFFF44336;
    static constexpr juce::uint32 velocityHigh = 0xFFAAAAAA;
    static constexpr juce::uint32 velocityLow  = 0xFF555555;

    MetallicLookAndFeel();

    void drawButtonBackground(juce::Graphics&, juce::Button&,
                              const juce::Colour& bg, bool hover, bool down) override;
    void drawButtonText(juce::Graphics&, juce::TextButton&,
                        bool hover, bool down) override;

    void drawComboBox(juce::Graphics&, int w, int h, bool down,
                      int bx, int by, int bw, int bh, juce::ComboBox&) override;

    void drawLinearSlider(juce::Graphics&, int x, int y, int w, int h,
                          float pos, float minPos, float maxPos,
                          juce::Slider::SliderStyle, juce::Slider&) override;

    void drawRotarySlider(juce::Graphics&, int x, int y, int w, int h,
                          float pos, float startAngle, float endAngle,
                          juce::Slider&) override;

    void drawScrollbar(juce::Graphics&, juce::ScrollBar&, int x, int y, int w, int h,
                       bool vertical, int thumbStart, int thumbSize,
                       bool over, bool dragging) override;

    void drawTabButton(juce::TabBarButton&, juce::Graphics&,
                       bool over, bool down) override;

    juce::Font getTextButtonFont(juce::TextButton&, int buttonHeight) override;
};
