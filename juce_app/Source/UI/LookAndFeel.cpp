#include "LookAndFeel.h"

//==============================================================================
// Colour constants
//==============================================================================
const juce::Colour MetallicLookAndFeel::bgDarkest     { 0xFF0E0E0E };
const juce::Colour MetallicLookAndFeel::bgDark        { 0xFF161616 };
const juce::Colour MetallicLookAndFeel::bgMid         { 0xFF1E1E1E };
const juce::Colour MetallicLookAndFeel::bgPanel       { 0xFF1A1A1A };
const juce::Colour MetallicLookAndFeel::bgHeader      { 0xFF1C1C1C };
const juce::Colour MetallicLookAndFeel::bgSelected    { 0xFF3A3A3A };
const juce::Colour MetallicLookAndFeel::bgHover       { 0xFF2A2A2A };
const juce::Colour MetallicLookAndFeel::accent        { 0xFFC0C0C0 };
const juce::Colour MetallicLookAndFeel::accentLight   { 0xFFE0E0E0 };
const juce::Colour MetallicLookAndFeel::textPrimary   { 0xFFE8E8E8 };
const juce::Colour MetallicLookAndFeel::textSecondary { 0xFF909090 };
const juce::Colour MetallicLookAndFeel::textDim       { 0xFF505050 };
const juce::Colour MetallicLookAndFeel::border        { 0xFF2A2A2A };
const juce::Colour MetallicLookAndFeel::gridBar       { 0xFF333333 };
const juce::Colour MetallicLookAndFeel::velocityHigh  { 0xFFAAAAAA };
const juce::Colour MetallicLookAndFeel::velocityLow   { 0xFF555555 };
const juce::Colour MetallicLookAndFeel::meterGreen    { 0xFF4CAF50 };
const juce::Colour MetallicLookAndFeel::meterYellow   { 0xFFFFC107 };
const juce::Colour MetallicLookAndFeel::meterRed      { 0xFFF44336 };
const juce::Colour MetallicLookAndFeel::clipColour    { 0xFF5E81AC };
const juce::Colour MetallicLookAndFeel::clipSelected  { 0xFF88C0D0 };

//==============================================================================
MetallicLookAndFeel::MetallicLookAndFeel()
{
    // ── Default colour scheme ───────────────────────────────────────────────
    setColour (juce::ResizableWindow::backgroundColourId, bgDarkest);

    // TextButton
    setColour (juce::TextButton::buttonColourId,   bgMid);
    setColour (juce::TextButton::buttonOnColourId,  bgSelected);
    setColour (juce::TextButton::textColourOffId,   textPrimary);
    setColour (juce::TextButton::textColourOnId,    accentLight);

    // ComboBox
    setColour (juce::ComboBox::backgroundColourId,    bgMid);
    setColour (juce::ComboBox::textColourId,          textPrimary);
    setColour (juce::ComboBox::outlineColourId,       border);
    setColour (juce::ComboBox::arrowColourId,         textSecondary);

    // Slider
    setColour (juce::Slider::backgroundColourId,          bgDark);
    setColour (juce::Slider::trackColourId,               accent);
    setColour (juce::Slider::thumbColourId,               accentLight);
    setColour (juce::Slider::rotarySliderFillColourId,    accent);
    setColour (juce::Slider::rotarySliderOutlineColourId, bgDark);
    setColour (juce::Slider::textBoxTextColourId,         textPrimary);
    setColour (juce::Slider::textBoxBackgroundColourId,   bgDark);
    setColour (juce::Slider::textBoxOutlineColourId,      border);

    // Label
    setColour (juce::Label::textColourId,           textPrimary);
    setColour (juce::Label::backgroundColourId,     juce::Colour (0x00000000));
    setColour (juce::Label::outlineColourId,        juce::Colour (0x00000000));

    // ScrollBar
    setColour (juce::ScrollBar::thumbColourId,      bgSelected);
    setColour (juce::ScrollBar::trackColourId,      bgDark);

    // TextEditor
    setColour (juce::TextEditor::backgroundColourId,   bgDark);
    setColour (juce::TextEditor::textColourId,         textPrimary);
    setColour (juce::TextEditor::outlineColourId,      border);
    setColour (juce::TextEditor::focusedOutlineColourId, accent);
    setColour (juce::TextEditor::highlightColourId,    bgSelected);

    // ListBox
    setColour (juce::ListBox::backgroundColourId,      bgPanel);
    setColour (juce::ListBox::textColourId,            textPrimary);
    setColour (juce::ListBox::outlineColourId,         border);

    // TreeView
    setColour (juce::TreeView::backgroundColourId,     bgPanel);
    setColour (juce::TreeView::linesColourId,          border);

    // PopupMenu
    setColour (juce::PopupMenu::backgroundColourId,            bgMid);
    setColour (juce::PopupMenu::textColourId,                  textPrimary);
    setColour (juce::PopupMenu::highlightedBackgroundColourId, bgSelected);
    setColour (juce::PopupMenu::highlightedTextColourId,       accentLight);

    // TabbedComponent
    setColour (juce::TabbedButtonBar::tabOutlineColourId,      border);
    setColour (juce::TabbedButtonBar::tabTextColourId,         textSecondary);
    setColour (juce::TabbedButtonBar::frontTextColourId,       textPrimary);

    // Tooltip
    setColour (juce::TooltipWindow::backgroundColourId,  bgMid);
    setColour (juce::TooltipWindow::textColourId,        textPrimary);
    setColour (juce::TooltipWindow::outlineColourId,     border);

    // AlertWindow
    setColour (juce::AlertWindow::backgroundColourId,    bgPanel);
    setColour (juce::AlertWindow::textColourId,          textPrimary);
    setColour (juce::AlertWindow::outlineColourId,       border);
}

//==============================================================================
// Button
//==============================================================================
void MetallicLookAndFeel::drawButtonBackground (juce::Graphics& g,
                                                 juce::Button& button,
                                                 const juce::Colour& backgroundColour,
                                                 bool shouldDrawButtonAsHighlighted,
                                                 bool shouldDrawButtonAsDown)
{
    auto bounds = button.getLocalBounds().toFloat().reduced (0.5f);
    auto cornerSize = 3.0f;

    auto baseColour = backgroundColour;
    if (shouldDrawButtonAsDown)
        baseColour = baseColour.brighter (0.1f);
    else if (shouldDrawButtonAsHighlighted)
        baseColour = baseColour.brighter (0.05f);

    g.setColour (baseColour);
    g.fillRoundedRectangle (bounds, cornerSize);

    // Subtle top highlight for metallic look
    g.setColour (juce::Colours::white.withAlpha (0.03f));
    g.fillRoundedRectangle (bounds.removeFromTop (bounds.getHeight() * 0.5f), cornerSize);

    // Border
    g.setColour (border);
    g.drawRoundedRectangle (button.getLocalBounds().toFloat().reduced (0.5f), cornerSize, 1.0f);
}

juce::Font MetallicLookAndFeel::getTextButtonFont (juce::TextButton&, int buttonHeight)
{
    return juce::Font (juce::jmin (12.0f, (float) buttonHeight * 0.7f));
}

//==============================================================================
// ComboBox
//==============================================================================
void MetallicLookAndFeel::drawComboBox (juce::Graphics& g,
                                         int width, int height,
                                         bool isButtonDown,
                                         int /*buttonX*/, int /*buttonY*/,
                                         int /*buttonW*/, int /*buttonH*/,
                                         juce::ComboBox& box)
{
    auto bounds = juce::Rectangle<int> (0, 0, width, height).toFloat().reduced (0.5f);
    auto cornerSize = 3.0f;

    g.setColour (box.findColour (juce::ComboBox::backgroundColourId));
    g.fillRoundedRectangle (bounds, cornerSize);

    g.setColour (border);
    g.drawRoundedRectangle (bounds, cornerSize, 1.0f);

    // Arrow
    auto arrowZone = juce::Rectangle<int> (width - 20, 0, 16, height).toFloat();
    juce::Path arrow;
    arrow.addTriangle (arrowZone.getCentreX() - 4.0f, arrowZone.getCentreY() - 2.0f,
                       arrowZone.getCentreX() + 4.0f, arrowZone.getCentreY() - 2.0f,
                       arrowZone.getCentreX(),         arrowZone.getCentreY() + 3.0f);
    g.setColour (isButtonDown ? accentLight : textSecondary);
    g.fillPath (arrow);
}

//==============================================================================
// Popup menu
//==============================================================================
void MetallicLookAndFeel::drawPopupMenuBackground (juce::Graphics& g, int width, int height)
{
    g.fillAll (bgMid);
    g.setColour (border);
    g.drawRect (0, 0, width, height, 1);
}

void MetallicLookAndFeel::drawPopupMenuItem (juce::Graphics& g,
                                              const juce::Rectangle<int>& area,
                                              bool isSeparator, bool isActive,
                                              bool isHighlighted, bool isTicked,
                                              bool hasSubMenu,
                                              const juce::String& text,
                                              const juce::String& shortcutKeyText,
                                              const juce::Drawable* icon,
                                              const juce::Colour* textColour)
{
    if (isSeparator)
    {
        auto r = area.reduced (4, 0);
        r.removeFromTop (juce::roundToInt ((float) r.getHeight() * 0.5f - 0.5f));
        g.setColour (border);
        g.fillRect (r.removeFromTop (1));
        return;
    }

    auto r = area.reduced (1);

    if (isHighlighted && isActive)
    {
        g.setColour (bgSelected);
        g.fillRect (r);
    }

    auto col = isActive ? (isHighlighted ? accentLight : textPrimary) : textDim;
    if (textColour != nullptr)
        col = *textColour;

    auto maxFontHeight = (float) r.getHeight() / 1.3f;
    auto font = juce::Font (juce::jmin (maxFontHeight, 14.0f));
    g.setFont (font);

    auto textArea = r.reduced (8, 0);

    if (isTicked)
    {
        g.setColour (accent);
        auto tickArea = textArea.removeFromLeft (18).toFloat();
        juce::Path tick;
        tick.addEllipse (tickArea.reduced (4.0f));
        g.fillPath (tick);
    }

    g.setColour (col);
    g.drawFittedText (text, textArea, juce::Justification::centredLeft, 1);

    if (shortcutKeyText.isNotEmpty())
    {
        g.setColour (textDim);
        g.drawFittedText (shortcutKeyText, textArea, juce::Justification::centredRight, 1);
    }
}

//==============================================================================
// Linear Slider
//==============================================================================
void MetallicLookAndFeel::drawLinearSlider (juce::Graphics& g,
                                             int x, int y, int width, int height,
                                             float sliderPos, float /*minSliderPos*/,
                                             float /*maxSliderPos*/,
                                             juce::Slider::SliderStyle style,
                                             juce::Slider& slider)
{
    bool isVertical = (style == juce::Slider::LinearVertical ||
                       style == juce::Slider::LinearBarVertical);

    auto trackWidth = isVertical ? 4.0f : 4.0f;

    if (isVertical)
    {
        auto trackX = (float) x + (float) width * 0.5f - trackWidth * 0.5f;
        // Background track
        g.setColour (bgDark);
        g.fillRoundedRectangle (trackX, (float) y, trackWidth, (float) height, 2.0f);

        // Filled portion
        g.setColour (accent);
        auto fillHeight = (float) (y + height) - sliderPos;
        g.fillRoundedRectangle (trackX, sliderPos, trackWidth, fillHeight, 2.0f);

        // Thumb
        auto thumbY = sliderPos;
        auto thumbW = 14.0f;
        auto thumbH = 6.0f;
        auto thumbX = (float) x + (float) width * 0.5f - thumbW * 0.5f;
        g.setColour (accentLight);
        g.fillRoundedRectangle (thumbX, thumbY - thumbH * 0.5f, thumbW, thumbH, 2.0f);
        // Metallic highlight on thumb
        g.setColour (juce::Colours::white.withAlpha (0.15f));
        g.fillRoundedRectangle (thumbX, thumbY - thumbH * 0.5f, thumbW, thumbH * 0.5f, 2.0f);
    }
    else
    {
        auto trackY = (float) y + (float) height * 0.5f - trackWidth * 0.5f;
        // Background track
        g.setColour (bgDark);
        g.fillRoundedRectangle ((float) x, trackY, (float) width, trackWidth, 2.0f);

        // Filled portion
        g.setColour (accent);
        g.fillRoundedRectangle ((float) x, trackY, sliderPos - (float) x, trackWidth, 2.0f);

        // Thumb
        auto thumbX = sliderPos;
        auto thumbW = 6.0f;
        auto thumbH = 14.0f;
        auto thumbY2 = (float) y + (float) height * 0.5f - thumbH * 0.5f;
        g.setColour (accentLight);
        g.fillRoundedRectangle (thumbX - thumbW * 0.5f, thumbY2, thumbW, thumbH, 2.0f);
    }
}

//==============================================================================
// Rotary Slider
//==============================================================================
void MetallicLookAndFeel::drawRotarySlider (juce::Graphics& g,
                                             int x, int y, int width, int height,
                                             float sliderPosProportional,
                                             float rotaryStartAngle,
                                             float rotaryEndAngle,
                                             juce::Slider& /*slider*/)
{
    auto radius  = (float) juce::jmin (width, height) * 0.5f - 4.0f;
    auto centreX = (float) x + (float) width  * 0.5f;
    auto centreY = (float) y + (float) height * 0.5f;
    auto angle   = rotaryStartAngle + sliderPosProportional * (rotaryEndAngle - rotaryStartAngle);

    // Background circle
    g.setColour (bgDark);
    g.fillEllipse (centreX - radius, centreY - radius, radius * 2.0f, radius * 2.0f);

    // Arc track
    juce::Path arcBg;
    arcBg.addCentredArc (centreX, centreY, radius - 2.0f, radius - 2.0f,
                          0.0f, rotaryStartAngle, rotaryEndAngle, true);
    g.setColour (bgSelected);
    g.strokePath (arcBg, juce::PathStrokeType (3.0f));

    // Arc fill
    juce::Path arcFill;
    arcFill.addCentredArc (centreX, centreY, radius - 2.0f, radius - 2.0f,
                            0.0f, rotaryStartAngle, angle, true);
    g.setColour (accent);
    g.strokePath (arcFill, juce::PathStrokeType (3.0f));

    // Pointer line
    juce::Path pointer;
    auto pointerLength = radius * 0.6f;
    auto pointerThickness = 2.0f;
    pointer.addRectangle (-pointerThickness * 0.5f, -radius + 4.0f,
                           pointerThickness, pointerLength);
    pointer.applyTransform (juce::AffineTransform::rotation (angle)
                                .translated (centreX, centreY));
    g.setColour (accentLight);
    g.fillPath (pointer);

    // Centre dot
    auto dotRadius = 3.0f;
    g.setColour (accent);
    g.fillEllipse (centreX - dotRadius, centreY - dotRadius, dotRadius * 2.0f, dotRadius * 2.0f);
}

//==============================================================================
// Scrollbar
//==============================================================================
void MetallicLookAndFeel::drawScrollbar (juce::Graphics& g,
                                          juce::ScrollBar& /*scrollbar*/,
                                          int x, int y, int width, int height,
                                          bool isScrollbarVertical,
                                          int thumbStartPosition, int thumbSize,
                                          bool isMouseOver, bool isMouseDown)
{
    g.setColour (bgDark);
    g.fillRect (x, y, width, height);

    auto thumbColour = isMouseDown ? accent : (isMouseOver ? bgSelected.brighter (0.1f) : bgSelected);
    g.setColour (thumbColour);

    if (isScrollbarVertical)
        g.fillRoundedRectangle ((float) x + 1.0f, (float) thumbStartPosition,
                                (float) width - 2.0f, (float) thumbSize, 3.0f);
    else
        g.fillRoundedRectangle ((float) thumbStartPosition, (float) y + 1.0f,
                                (float) thumbSize, (float) height - 2.0f, 3.0f);
}

//==============================================================================
// Tab Button
//==============================================================================
void MetallicLookAndFeel::drawTabButton (juce::TabBarButton& button,
                                          juce::Graphics& g,
                                          bool isMouseOver,
                                          bool isMouseDown)
{
    auto area = button.getActiveArea();
    bool isFront = button.isFrontTab();

    g.setColour (isFront ? bgPanel : bgDark);
    g.fillRect (area);

    if (isFront)
    {
        g.setColour (accent);
        g.fillRect (area.removeFromBottom (2));
    }
    else if (isMouseOver)
    {
        g.setColour (bgHover);
        g.fillRect (area);
    }

    g.setColour (border);
    g.drawRect (button.getActiveArea(), 1);

    g.setColour (isFront ? textPrimary : textSecondary);
    g.setFont (juce::Font (12.0f));
    g.drawFittedText (button.getButtonText(), button.getActiveArea(),
                      juce::Justification::centred, 1);
}

int MetallicLookAndFeel::getTabButtonBestWidth (juce::TabBarButton& button, int /*tabDepth*/)
{
    auto textWidth = juce::Font (12.0f).getStringWidth (button.getButtonText());
    return juce::jmax (80, textWidth + 24);
}

//==============================================================================
// TreeView
//==============================================================================
void MetallicLookAndFeel::drawTreeviewPlusMinusBox (juce::Graphics& g,
                                                     const juce::Rectangle<float>& area,
                                                     juce::Colour /*backgroundColour*/,
                                                     bool isOpen, bool isMouseOver)
{
    auto boxSize = juce::jmin (area.getWidth(), area.getHeight()) * 0.7f;
    auto x = area.getCentreX() - boxSize * 0.5f;
    auto y = area.getCentreY() - boxSize * 0.5f;

    g.setColour (isMouseOver ? accent : textSecondary);
    g.drawRect (x, y, boxSize, boxSize, 1.0f);

    auto lineThickness = 1.5f;
    auto cx = area.getCentreX();
    auto cy = area.getCentreY();

    // Horizontal line
    g.fillRect (cx - boxSize * 0.3f, cy - lineThickness * 0.5f,
                boxSize * 0.6f, lineThickness);

    if (! isOpen)
    {
        // Vertical line
        g.fillRect (cx - lineThickness * 0.5f, cy - boxSize * 0.3f,
                    lineThickness, boxSize * 0.6f);
    }
}

//==============================================================================
// Label
//==============================================================================
void MetallicLookAndFeel::drawLabel (juce::Graphics& g, juce::Label& label)
{
    g.fillAll (label.findColour (juce::Label::backgroundColourId));

    if (! label.isBeingEdited())
    {
        auto textArea = getLabelBorderSize (label).subtractedFrom (label.getLocalBounds());
        g.setColour (label.findColour (juce::Label::textColourId));
        g.setFont (getLabelFont (label));
        g.drawFittedText (label.getText(), textArea, label.getJustificationType(),
                          juce::jmax (1, (int) ((float) textArea.getHeight() / label.getFont().getHeight())),
                          label.getMinimumHorizontalScale());
    }
}

//==============================================================================
// Toggle Button
//==============================================================================
void MetallicLookAndFeel::drawToggleButton (juce::Graphics& g,
                                             juce::ToggleButton& button,
                                             bool shouldDrawButtonAsHighlighted,
                                             bool shouldDrawButtonAsDown)
{
    auto bounds = button.getLocalBounds().toFloat().reduced (2.0f);
    bool isOn = button.getToggleState();

    auto bg = isOn ? bgSelected : bgMid;
    if (shouldDrawButtonAsDown)
        bg = bg.brighter (0.1f);
    else if (shouldDrawButtonAsHighlighted)
        bg = bg.brighter (0.05f);

    g.setColour (bg);
    g.fillRoundedRectangle (bounds, 3.0f);
    g.setColour (border);
    g.drawRoundedRectangle (bounds, 3.0f, 1.0f);

    g.setColour (isOn ? accentLight : textSecondary);
    g.setFont (juce::Font (12.0f));
    g.drawFittedText (button.getButtonText(), button.getLocalBounds(),
                      juce::Justification::centred, 1);
}

//==============================================================================
// Menu Bar
//==============================================================================
void MetallicLookAndFeel::drawMenuBarBackground (juce::Graphics& g,
                                                   int width, int height,
                                                   bool /*isMouseOverBar*/,
                                                   juce::MenuBarComponent& /*menuBar*/)
{
    g.fillAll (bgHeader);
    g.setColour (border);
    g.drawHorizontalLine (height - 1, 0.0f, (float) width);
}

void MetallicLookAndFeel::drawMenuBarItem (juce::Graphics& g,
                                            int width, int height,
                                            int /*itemIndex*/,
                                            const juce::String& itemText,
                                            bool isMouseOverItem,
                                            bool isMenuOpen,
                                            bool /*isMouseOverBar*/,
                                            juce::MenuBarComponent& /*menuBar*/)
{
    if (isMouseOverItem || isMenuOpen)
    {
        g.setColour (bgSelected);
        g.fillRect (0, 0, width, height);
    }

    g.setColour (isMouseOverItem ? accentLight : textPrimary);
    g.setFont (juce::Font (13.0f));
    g.drawFittedText (itemText, 0, 0, width, height, juce::Justification::centred, 1);
}

//==============================================================================
// Tooltip
//==============================================================================
void MetallicLookAndFeel::drawTooltip (juce::Graphics& g,
                                        const juce::String& text,
                                        int width, int height)
{
    g.fillAll (bgMid);
    g.setColour (border);
    g.drawRect (0, 0, width, height, 1);
    g.setColour (textPrimary);
    g.setFont (juce::Font (12.0f));
    g.drawFittedText (text, 4, 2, width - 8, height - 4, juce::Justification::centredLeft, 3);
}

//==============================================================================
// Group Component
//==============================================================================
void MetallicLookAndFeel::drawGroupComponentOutline (juce::Graphics& g,
                                                      int w, int h,
                                                      const juce::String& text,
                                                      const juce::Justification& position,
                                                      juce::GroupComponent& /*group*/)
{
    auto textH = 15.0f;
    auto indent = 3.0f;
    auto textEdge = 6.0f;

    auto font = juce::Font (textH);
    auto textW = text.isEmpty() ? 0.0f : font.getStringWidthFloat (text) + textEdge * 2.0f;

    auto x = indent;
    auto y = textH * 0.5f;
    auto rw = juce::jmax (0.0f, (float) w - indent * 2.0f);
    auto rh = juce::jmax (0.0f, (float) h - y - indent);

    g.setColour (border);
    g.drawRoundedRectangle (x, y, rw, rh, 4.0f, 1.0f);

    if (text.isNotEmpty())
    {
        auto textX = textEdge + x;
        g.setColour (bgPanel);
        g.fillRect (textX - 2.0f, 0.0f, textW + 4.0f, textH);
        g.setColour (textPrimary);
        g.setFont (font);
        g.drawText (text, (int) textX, 0, (int) textW, (int) textH,
                    position, true);
    }
}
