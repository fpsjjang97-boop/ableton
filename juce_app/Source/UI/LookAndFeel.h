#pragma once
#include <JuceHeader.h>

//==============================================================================
// MetallicLookAndFeel - Dark metallic theme for the DAW
//==============================================================================
class MetallicLookAndFeel : public juce::LookAndFeel_V4
{
public:
    MetallicLookAndFeel();
    ~MetallicLookAndFeel() override = default;

    // ── Colour constants (metallic dark theme) ──────────────────────────────
    static const juce::Colour bgDarkest;      // #0E0E0E
    static const juce::Colour bgDark;         // #161616
    static const juce::Colour bgMid;          // #1E1E1E
    static const juce::Colour bgPanel;        // #1A1A1A
    static const juce::Colour bgHeader;       // #1C1C1C
    static const juce::Colour bgSelected;     // #3A3A3A
    static const juce::Colour bgHover;        // #2A2A2A
    static const juce::Colour accent;         // #C0C0C0
    static const juce::Colour accentLight;    // #E0E0E0
    static const juce::Colour textPrimary;    // #E8E8E8
    static const juce::Colour textSecondary;  // #909090
    static const juce::Colour textDim;        // #505050
    static const juce::Colour border;         // #2A2A2A
    static const juce::Colour gridBar;        // #333333
    static const juce::Colour velocityHigh;   // #AAAAAA
    static const juce::Colour velocityLow;    // #555555
    static const juce::Colour meterGreen;     // #4CAF50
    static const juce::Colour meterYellow;    // #FFC107
    static const juce::Colour meterRed;       // #F44336
    static const juce::Colour clipColour;     // #5E81AC
    static const juce::Colour clipSelected;   // #88C0D0

    // ── Button ──────────────────────────────────────────────────────────────
    void drawButtonBackground (juce::Graphics& g,
                               juce::Button& button,
                               const juce::Colour& backgroundColour,
                               bool shouldDrawButtonAsHighlighted,
                               bool shouldDrawButtonAsDown) override;

    juce::Font getTextButtonFont (juce::TextButton&, int buttonHeight) override;

    // ── ComboBox ────────────────────────────────────────────────────────────
    void drawComboBox (juce::Graphics& g,
                       int width, int height,
                       bool isButtonDown,
                       int buttonX, int buttonY, int buttonW, int buttonH,
                       juce::ComboBox& box) override;

    void drawPopupMenuBackground (juce::Graphics& g, int width, int height) override;

    void drawPopupMenuItem (juce::Graphics& g,
                            const juce::Rectangle<int>& area,
                            bool isSeparator, bool isActive, bool isHighlighted,
                            bool isTicked, bool hasSubMenu,
                            const juce::String& text,
                            const juce::String& shortcutKeyText,
                            const juce::Drawable* icon,
                            const juce::Colour* textColour) override;

    // ── Linear Slider ───────────────────────────────────────────────────────
    void drawLinearSlider (juce::Graphics& g,
                           int x, int y, int width, int height,
                           float sliderPos, float minSliderPos, float maxSliderPos,
                           juce::Slider::SliderStyle style,
                           juce::Slider& slider) override;

    // ── Rotary Slider ───────────────────────────────────────────────────────
    void drawRotarySlider (juce::Graphics& g,
                           int x, int y, int width, int height,
                           float sliderPosProportional,
                           float rotaryStartAngle,
                           float rotaryEndAngle,
                           juce::Slider& slider) override;

    // ── Scrollbar ───────────────────────────────────────────────────────────
    void drawScrollbar (juce::Graphics& g,
                        juce::ScrollBar& scrollbar,
                        int x, int y, int width, int height,
                        bool isScrollbarVertical,
                        int thumbStartPosition, int thumbSize,
                        bool isMouseOver, bool isMouseDown) override;

    // ── Tab Button ──────────────────────────────────────────────────────────
    void drawTabButton (juce::TabBarButton& button,
                        juce::Graphics& g,
                        bool isMouseOver,
                        bool isMouseDown) override;

    int getTabButtonBestWidth (juce::TabBarButton& button, int tabDepth) override;

    // ── TreeView ────────────────────────────────────────────────────────────
    void drawTreeviewPlusMinusBox (juce::Graphics& g,
                                   const juce::Rectangle<float>& area,
                                   juce::Colour backgroundColour,
                                   bool isOpen, bool isMouseOver) override;

    // ── Label ───────────────────────────────────────────────────────────────
    void drawLabel (juce::Graphics& g, juce::Label& label) override;

    // ── Toggle Button ───────────────────────────────────────────────────────
    void drawToggleButton (juce::Graphics& g,
                           juce::ToggleButton& button,
                           bool shouldDrawButtonAsHighlighted,
                           bool shouldDrawButtonAsDown) override;

    // ── Menu Bar ────────────────────────────────────────────────────────────
    void drawMenuBarBackground (juce::Graphics& g, int width, int height,
                                bool isMouseOverBar, juce::MenuBarComponent& menuBar) override;

    void drawMenuBarItem (juce::Graphics& g, int width, int height,
                          int itemIndex, const juce::String& itemText,
                          bool isMouseOverItem, bool isMenuOpen, bool isMouseOverBar,
                          juce::MenuBarComponent& menuBar) override;

    // ── Tooltip ─────────────────────────────────────────────────────────────
    void drawTooltip (juce::Graphics& g, const juce::String& text,
                      int width, int height) override;

    // ── Group component ─────────────────────────────────────────────────────
    void drawGroupComponentOutline (juce::Graphics& g, int w, int h,
                                    const juce::String& text,
                                    const juce::Justification& position,
                                    juce::GroupComponent& group) override;

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MetallicLookAndFeel)
};
