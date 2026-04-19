/*
 * MidiGPT DAW - MetallicLookAndFeel.cpp
 */

#include "LookAndFeel.h"

MetallicLookAndFeel::MetallicLookAndFeel()
{
    // Window
    setColour(juce::ResizableWindow::backgroundColourId, juce::Colour(bgDarkest));

    // Buttons
    setColour(juce::TextButton::buttonColourId, juce::Colour(bgMid));
    setColour(juce::TextButton::buttonOnColourId, juce::Colour(bgSelected));
    setColour(juce::TextButton::textColourOffId, juce::Colour(textPrimary));
    setColour(juce::TextButton::textColourOnId, juce::Colour(accentLight));

    // ComboBox
    setColour(juce::ComboBox::backgroundColourId, juce::Colour(bgMid));
    setColour(juce::ComboBox::outlineColourId, juce::Colour(border));
    setColour(juce::ComboBox::textColourId, juce::Colour(textPrimary));
    setColour(juce::ComboBox::arrowColourId, juce::Colour(textSecondary));

    // Slider
    setColour(juce::Slider::backgroundColourId, juce::Colour(bgDark));
    setColour(juce::Slider::trackColourId, juce::Colour(accent));
    setColour(juce::Slider::thumbColourId, juce::Colour(accentLight));
    setColour(juce::Slider::textBoxTextColourId, juce::Colour(textPrimary));
    setColour(juce::Slider::textBoxBackgroundColourId, juce::Colour(bgDark));
    setColour(juce::Slider::textBoxOutlineColourId, juce::Colour(border));

    // Label
    setColour(juce::Label::textColourId, juce::Colour(textPrimary));

    // ScrollBar
    setColour(juce::ScrollBar::thumbColourId, juce::Colour(bgSelected));
    setColour(juce::ScrollBar::trackColourId, juce::Colour(bgDark));

    // TextEditor
    setColour(juce::TextEditor::backgroundColourId, juce::Colour(bgDark));
    setColour(juce::TextEditor::textColourId, juce::Colour(textPrimary));
    setColour(juce::TextEditor::outlineColourId, juce::Colour(border));
    setColour(juce::TextEditor::focusedOutlineColourId, juce::Colour(accent));

    // ListBox
    setColour(juce::ListBox::backgroundColourId, juce::Colour(bgPanel));
    setColour(juce::ListBox::textColourId, juce::Colour(textPrimary));

    // PopupMenu
    setColour(juce::PopupMenu::backgroundColourId, juce::Colour(bgMid));
    setColour(juce::PopupMenu::textColourId, juce::Colour(textPrimary));
    setColour(juce::PopupMenu::highlightedBackgroundColourId, juce::Colour(bgSelected));
    setColour(juce::PopupMenu::highlightedTextColourId, juce::Colour(accentLight));

    // TabbedButtonBar
    setColour(juce::TabbedButtonBar::tabOutlineColourId, juce::Colour(border));
    setColour(juce::TabbedButtonBar::tabTextColourId, juce::Colour(textSecondary));

    // Tooltip
    setColour(juce::TooltipWindow::backgroundColourId, juce::Colour(bgMid));
    setColour(juce::TooltipWindow::textColourId, juce::Colour(textPrimary));
    setColour(juce::TooltipWindow::outlineColourId, juce::Colour(border));
}

// ---------------------------------------------------------------------------
void MetallicLookAndFeel::drawButtonBackground(juce::Graphics& g, juce::Button& btn,
                                                const juce::Colour& bg,
                                                bool hover, bool down)
{
    auto bounds = btn.getLocalBounds().toFloat().reduced(0.5f);
    auto baseColour = down ? bg.brighter(0.1f)
                     : hover ? bg.brighter(0.05f) : bg;

    g.setColour(baseColour);
    g.fillRoundedRectangle(bounds, 3.0f);

    // Metallic highlight on top half
    g.setColour(juce::Colours::white.withAlpha(down ? 0.02f : 0.03f));
    g.fillRoundedRectangle(bounds.removeFromTop(bounds.getHeight() * 0.5f), 3.0f);

    g.setColour(juce::Colour(border));
    g.drawRoundedRectangle(btn.getLocalBounds().toFloat().reduced(0.5f), 3.0f, 0.5f);
}

void MetallicLookAndFeel::drawButtonText(juce::Graphics& g, juce::TextButton& btn,
                                          bool /*hover*/, bool /*down*/)
{
    auto font = getTextButtonFont(btn, btn.getHeight());
    g.setFont(font);
    g.setColour(btn.findColour(btn.getToggleState() ? juce::TextButton::textColourOnId
                                                     : juce::TextButton::textColourOffId));
    g.drawFittedText(btn.getButtonText(), btn.getLocalBounds().reduced(2),
                     juce::Justification::centred, 1);
}

juce::Font MetallicLookAndFeel::getTextButtonFont(juce::TextButton&, int buttonHeight)
{
    return juce::Font(juce::jmin(12.0f, buttonHeight * 0.7f));
}

// ---------------------------------------------------------------------------
void MetallicLookAndFeel::drawComboBox(juce::Graphics& g, int w, int h, bool /*down*/,
                                        int, int, int, int, juce::ComboBox& box)
{
    auto bounds = juce::Rectangle<float>(0, 0, (float)w, (float)h);

    g.setColour(box.findColour(juce::ComboBox::backgroundColourId));
    g.fillRoundedRectangle(bounds, 3.0f);

    g.setColour(box.findColour(juce::ComboBox::outlineColourId));
    g.drawRoundedRectangle(bounds.reduced(0.5f), 3.0f, 0.5f);

    // Arrow
    auto arrowZone = bounds.removeFromRight(20.0f).reduced(6.0f);
    juce::Path arrow;
    arrow.addTriangle(arrowZone.getX(), arrowZone.getY(),
                      arrowZone.getRight(), arrowZone.getY(),
                      arrowZone.getCentreX(), arrowZone.getBottom());
    g.setColour(box.findColour(juce::ComboBox::arrowColourId));
    g.fillPath(arrow);
}

// ---------------------------------------------------------------------------
void MetallicLookAndFeel::drawLinearSlider(juce::Graphics& g, int x, int y, int w, int h,
                                            float sliderPos, float /*minPos*/, float /*maxPos*/,
                                            juce::Slider::SliderStyle style, juce::Slider& slider)
{
    bool isVertical = (style == juce::Slider::LinearVertical);

    if (isVertical)
    {
        float trackW = 4.0f;
        float cx = x + w * 0.5f;
        float trackX = cx - trackW * 0.5f;

        g.setColour(slider.findColour(juce::Slider::backgroundColourId));
        g.fillRoundedRectangle(trackX, (float)y, trackW, (float)h, 2.0f);

        g.setColour(slider.findColour(juce::Slider::trackColourId));
        g.fillRoundedRectangle(trackX, sliderPos, trackW, (float)(y + h) - sliderPos, 2.0f);

        // Thumb
        float thumbW = 14.0f, thumbH = 6.0f;
        auto thumbRect = juce::Rectangle<float>(cx - thumbW * 0.5f, sliderPos - thumbH * 0.5f,
                                                 thumbW, thumbH);
        g.setColour(slider.findColour(juce::Slider::thumbColourId));
        g.fillRoundedRectangle(thumbRect, 2.0f);

        g.setColour(juce::Colours::white.withAlpha(0.15f));
        g.fillRoundedRectangle(thumbRect.removeFromTop(thumbH * 0.5f), 2.0f);
    }
    else
    {
        float trackH = 4.0f;
        float cy = y + h * 0.5f;
        float trackY = cy - trackH * 0.5f;

        g.setColour(slider.findColour(juce::Slider::backgroundColourId));
        g.fillRoundedRectangle((float)x, trackY, (float)w, trackH, 2.0f);

        g.setColour(slider.findColour(juce::Slider::trackColourId));
        g.fillRoundedRectangle((float)x, trackY, sliderPos - (float)x, trackH, 2.0f);

        // Thumb
        float thumbW = 6.0f, thumbH = 14.0f;
        auto thumbRect = juce::Rectangle<float>(sliderPos - thumbW * 0.5f, cy - thumbH * 0.5f,
                                                 thumbW, thumbH);
        g.setColour(slider.findColour(juce::Slider::thumbColourId));
        g.fillRoundedRectangle(thumbRect, 2.0f);

        g.setColour(juce::Colours::white.withAlpha(0.15f));
        g.fillRoundedRectangle(thumbRect.removeFromTop(thumbH * 0.5f), 2.0f);
    }
}

// ---------------------------------------------------------------------------
void MetallicLookAndFeel::drawRotarySlider(juce::Graphics& g, int x, int y, int w, int h,
                                            float sliderPos, float startAngle, float endAngle,
                                            juce::Slider&)
{
    float radius = juce::jmin((float)w, (float)h) * 0.5f - 4.0f;
    float cx = x + w * 0.5f;
    float cy = y + h * 0.5f;
    float angle = startAngle + sliderPos * (endAngle - startAngle);

    // Track arc
    juce::Path bgArc;
    bgArc.addCentredArc(cx, cy, radius, radius, 0.0f, startAngle, endAngle, true);
    g.setColour(juce::Colour(bgDark));
    g.strokePath(bgArc, juce::PathStrokeType(3.0f));

    // Filled arc
    juce::Path filledArc;
    filledArc.addCentredArc(cx, cy, radius, radius, 0.0f, startAngle, angle, true);
    g.setColour(juce::Colour(accent));
    g.strokePath(filledArc, juce::PathStrokeType(3.0f));

    // Pointer line
    float lineLen = radius - 4.0f;
    juce::Path pointer;
    pointer.addLineSegment(juce::Line<float>(0.0f, -lineLen, 0.0f, -radius + 1.0f), 2.0f);
    g.setColour(juce::Colour(accentLight));
    g.fillPath(pointer, juce::AffineTransform::rotation(angle).translated(cx, cy));

    // Center dot
    g.setColour(juce::Colour(accentLight));
    g.fillEllipse(cx - 3.0f, cy - 3.0f, 6.0f, 6.0f);
}

// ---------------------------------------------------------------------------
void MetallicLookAndFeel::drawScrollbar(juce::Graphics& g, juce::ScrollBar&,
                                         int x, int y, int w, int h,
                                         bool vertical, int thumbStart, int thumbSize,
                                         bool over, bool dragging)
{
    g.setColour(juce::Colour(bgDark));
    g.fillRect(x, y, w, h);

    auto thumbColour = juce::Colour(bgSelected);
    if (dragging) thumbColour = thumbColour.brighter(0.15f);
    else if (over) thumbColour = thumbColour.brighter(0.08f);

    g.setColour(thumbColour);
    if (vertical)
        g.fillRoundedRectangle((float)x + 1, (float)thumbStart, (float)w - 2, (float)thumbSize, 3.0f);
    else
        g.fillRoundedRectangle((float)thumbStart, (float)y + 1, (float)thumbSize, (float)h - 2, 3.0f);
}

// ---------------------------------------------------------------------------
// Sprint 47 KKK4 — static paint helpers (기존 UI 변경 없이 추가만)
void MetallicLookAndFeel::drawPanelBackground(juce::Graphics& g,
                                               juce::Rectangle<float> bounds,
                                               float cornerRadius)
{
    g.setColour(juce::Colour(bgPanel));
    g.fillRoundedRectangle(bounds, cornerRadius);

    g.setColour(juce::Colour(border));
    g.drawRoundedRectangle(bounds.reduced(0.5f), cornerRadius, 0.5f);
}

void MetallicLookAndFeel::drawSectionHeader(juce::Graphics& g,
                                             juce::Rectangle<int> bounds,
                                             const juce::String& text,
                                             float fontSize)
{
    g.setColour(juce::Colour(bgHeader));
    g.fillRect(bounds);

    // Bottom divider — accent 로 섹션 경계 강조
    g.setColour(juce::Colour(border));
    g.drawLine(static_cast<float>(bounds.getX()),
               static_cast<float>(bounds.getBottom() - 1),
               static_cast<float>(bounds.getRight()),
               static_cast<float>(bounds.getBottom() - 1),
               1.0f);

    g.setFont(juce::Font(fontSize, juce::Font::bold));
    g.setColour(juce::Colour(textPrimary));
    g.drawFittedText(text, bounds.reduced(spacingM, 0),
                     juce::Justification::centredLeft, 1);
}

void MetallicLookAndFeel::drawDivider(juce::Graphics& g,
                                       juce::Rectangle<int> bounds,
                                       bool vertical)
{
    g.setColour(juce::Colour(border));
    if (vertical)
    {
        int x = bounds.getCentreX();
        g.drawLine(static_cast<float>(x),
                   static_cast<float>(bounds.getY()),
                   static_cast<float>(x),
                   static_cast<float>(bounds.getBottom()),
                   1.0f);
    }
    else
    {
        int y = bounds.getCentreY();
        g.drawLine(static_cast<float>(bounds.getX()),
                   static_cast<float>(y),
                   static_cast<float>(bounds.getRight()),
                   static_cast<float>(y),
                   1.0f);
    }
}

// ---------------------------------------------------------------------------
void MetallicLookAndFeel::drawTabButton(juce::TabBarButton& btn, juce::Graphics& g,
                                         bool over, bool /*down*/)
{
    auto area = btn.getLocalBounds();
    bool isActive = btn.isFrontTab();

    g.setColour(isActive ? juce::Colour(bgMid) : juce::Colour(bgDarkest));
    g.fillRect(area);

    if (over && !isActive)
    {
        g.setColour(juce::Colour(bgHover));
        g.fillRect(area);
    }

    if (isActive)
    {
        g.setColour(juce::Colour(accent));
        g.fillRect(area.removeFromBottom(2));
    }

    g.setColour(isActive ? juce::Colour(textPrimary) : juce::Colour(textSecondary));
    g.setFont(12.0f);
    g.drawFittedText(btn.getButtonText(), btn.getLocalBounds(), juce::Justification::centred, 1);
}
