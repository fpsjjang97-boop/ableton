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
    // Colour palette — Cakewalk × Ableton Live 11 hybrid (Sprint 51 UI pass).
    // Base stack borrows Live 11's very-dark neutral charcoal with crisp
    // flat separation between panels; accent + selection borrow Cakewalk's
    // signature warm amber gold so interactive elements feel "warm" rather
    // than the icy blue of the prior Unity pass. Meter/status colours kept
    // accessible (standard green/yellow/red). Tweak constexpr here to
    // propagate project-wide.
    static constexpr juce::uint32 bgDarkest   = 0xFF1B1B1B;   // app frame / root (Live 11 black)
    static constexpr juce::uint32 bgDark      = 0xFF242424;   // track rows, slider track
    static constexpr juce::uint32 bgMid       = 0xFF333333;   // buttons, combo, text editor
    static constexpr juce::uint32 bgPanel     = 0xFF2A2A2A;   // arrangement row shade, panels
    static constexpr juce::uint32 bgHeader    = 0xFF383838;   // track header, top bars
    static constexpr juce::uint32 bgSelected  = 0xFFE9A41F;   // Cakewalk amber selection
    static constexpr juce::uint32 bgHover     = 0xFF404040;
    static constexpr juce::uint32 accent      = 0xFFE9A41F;   // Cakewalk amber — primary accent
    static constexpr juce::uint32 accentLight = 0xFFFFC04D;   // hover/active (softer amber)
    static constexpr juce::uint32 textPrimary = 0xFFE8E8E8;
    static constexpr juce::uint32 textSecondary = 0xFFA8A8A8;
    static constexpr juce::uint32 textDim     = 0xFF5E5E5E;
    static constexpr juce::uint32 border      = 0xFF181818;   // Live 11-style hard border
    static constexpr juce::uint32 gridBar     = 0xFF3A3A3A;
    static constexpr juce::uint32 clipColour  = 0xFF6A9BD8;   // calm blue — Live 11 default clip
    static constexpr juce::uint32 clipSelected = 0xFFFFC04D;  // amber on selection
    static constexpr juce::uint32 meterGreen  = 0xFF4CAF50;
    static constexpr juce::uint32 meterYellow = 0xFFFFC107;
    static constexpr juce::uint32 meterRed    = 0xFFF44336;
    static constexpr juce::uint32 velocityHigh = 0xFFD0D0D0;
    static constexpr juce::uint32 velocityLow  = 0xFF606060;

    // Sprint 47 KKK1 — semantic color tokens (기존 grayscale 에 상태색 추가)
    // 사용 원칙: warning/danger 는 파괴적 동작 직전, success 는 완료 확인,
    //            infoBlue 는 비임계 정보(노트 카운트, BPM 등).
    static constexpr juce::uint32 warning     = 0xFFFFB300;   // 밝은 주황
    static constexpr juce::uint32 danger      = 0xFFE53935;   // 선명한 빨강
    static constexpr juce::uint32 success     = 0xFF66BB6A;   // 뚜렷한 초록 (meterGreen 보다 대비)
    static constexpr juce::uint32 infoBlue    = 0xFF5E81AC;   // clipColour 와 동일 — 정보 버튼 공용
    static constexpr juce::uint32 infoLight   = 0xFF88C0D0;   // 하이라이트 blue

    // Sprint 47 KKK1 — spacing/padding scale (설계서: docs/ui_style_guide.md)
    // 모든 컴포넌트는 이 상수를 써서 여백 일관성을 유지. 직접 리터럴 금지.
    static constexpr int spacingXS = 2;    // inline 소 간격
    static constexpr int spacingS  = 4;    // 아이콘 text 간 간격
    static constexpr int spacingM  = 8;    // 섹션 내 위젯 간격
    static constexpr int spacingL  = 16;   // 섹션간 간격
    static constexpr int spacingXL = 24;   // 큰 블록간 간격

    // Sprint 47 KKK1 — font size scale
    static constexpr float fontXS = 9.0f;   // status text, captions
    static constexpr float fontS  = 11.0f;  // labels
    static constexpr float fontM  = 13.0f;  // body
    static constexpr float fontL  = 16.0f;  // section headers
    static constexpr float fontXL = 20.0f;  // app title

    // Sprint 47 KKK1 — corner radius scale
    static constexpr float radiusS = 2.0f;
    static constexpr float radiusM = 3.0f;
    static constexpr float radiusL = 6.0f;

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

    // Sprint 47 KKK4 — paint helper (static, 기존 오버라이드와 독립).
    // 호출 안 해도 기존 UI 동작은 불변. 신규/리팩터링 컴포넌트가 공유 paint.
    static void drawPanelBackground(juce::Graphics& g,
                                    juce::Rectangle<float> bounds,
                                    float cornerRadius = radiusM);
    static void drawSectionHeader(juce::Graphics& g,
                                  juce::Rectangle<int> bounds,
                                  const juce::String& text,
                                  float fontSize = fontL);
    static void drawDivider(juce::Graphics& g,
                            juce::Rectangle<int> bounds,
                            bool vertical = false);
};
