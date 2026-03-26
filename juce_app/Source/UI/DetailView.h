#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"
#include "PianoRoll.h"

//==============================================================================
// AIControlPanel - AI generation / variation controls
//==============================================================================
class AIControlPanel : public juce::Component
{
public:
    AIControlPanel();
    ~AIControlPanel() override = default;

    void paint (juce::Graphics& g) override;
    void resized() override;

    // ── Callbacks ───────────────────────────────────────────────────────────
    std::function<void (const juce::String& prompt, int bars, float temperature)> onGenerate;
    std::function<void (const juce::String& type, float amount)>                  onVariation;
    std::function<void()>                                                          onAnalyze;

    // ── Analysis text ──────────────────────────────────────────────────────
    void setAnalysisText (const juce::String& text);

private:
    // Generate tab
    juce::TextEditor promptEditor;
    juce::Slider     barsSlider;
    juce::Slider     temperatureSlider;
    juce::ComboBox   modelSelector;
    juce::TextButton generateButton { "Generate" };
    juce::Label      barsLabel;
    juce::Label      tempLabel;
    juce::Label      modelLabel;

    // Variation tab
    juce::ComboBox   variationTypeSelector;
    juce::Slider     variationAmountSlider;
    juce::TextButton applyVariationButton { "Apply" };
    juce::Label      varTypeLabel;
    juce::Label      varAmountLabel;

    // Analysis tab
    juce::TextButton analyzeButton { "Analyze" };
    juce::TextEditor analysisOutput;

    // Internal tab state
    int currentSubTab = 0;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AIControlPanel)
};

//==============================================================================
// DetailView - Bottom detail panel with tabs
//==============================================================================
class DetailView : public juce::Component
{
public:
    DetailView();
    ~DetailView() override = default;

    void paint (juce::Graphics& g) override;
    void resized() override;

    // ── Access sub-components ───────────────────────────────────────────────
    PianoRoll&      getPianoRoll()       { return pianoRoll; }
    AIControlPanel& getAIPanel()         { return aiPanel; }

    // ── Analysis text ──────────────────────────────────────────────────────
    void setAnalysisText (const juce::String& text);

    // ── Collapse / Expand ───────────────────────────────────────────────────
    bool isCollapsed() const { return collapsed; }
    void setCollapsed (bool shouldCollapse);
    int  getPreferredHeight() const { return collapsed ? collapseBarH : expandedHeight; }

    std::function<void (bool)> onCollapseChanged;

    // ── Tab selection ───────────────────────────────────────────────────────
    enum Tab { ClipNotes, AIGenerate, AIVariation, Analysis };
    void setActiveTab (Tab tab);
    Tab  getActiveTab() const { return activeTab; }

private:
    static constexpr int collapseBarH  = 24;
    static constexpr int tabBarH       = 28;
    int expandedHeight = 300;

    bool collapsed = false;
    Tab  activeTab = ClipNotes;

    // Tab buttons
    juce::TextButton tabClipNotes   { "Clip/Notes" };
    juce::TextButton tabAIGenerate  { "AI Generate" };
    juce::TextButton tabAIVariation { "AI Variation" };
    juce::TextButton tabAnalysis    { "Analysis" };
    juce::TextButton collapseButton { "v" };

    // Content
    PianoRoll      pianoRoll;
    AIControlPanel aiPanel;

    void updateTabStates();
    void showActiveContent();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (DetailView)
};
