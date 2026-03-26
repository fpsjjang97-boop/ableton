#include "DetailView.h"

//==============================================================================
// AIControlPanel
//==============================================================================
AIControlPanel::AIControlPanel()
{
    // ── Prompt ──────────────────────────────────────────────────────────────
    promptEditor.setMultiLine (false);
    promptEditor.setTextToShowWhenEmpty ("Describe the MIDI you want to generate...",
                                         MetallicLookAndFeel::textDim);
    promptEditor.setFont (juce::Font (12.0f));
    addAndMakeVisible (promptEditor);

    // ── Bars slider ─────────────────────────────────────────────────────────
    barsSlider.setSliderStyle (juce::Slider::LinearHorizontal);
    barsSlider.setRange (1.0, 32.0, 1.0);
    barsSlider.setValue (4.0);
    barsSlider.setTextBoxStyle (juce::Slider::TextBoxRight, false, 30, 20);
    addAndMakeVisible (barsSlider);

    barsLabel.setText ("Bars:", juce::dontSendNotification);
    barsLabel.setFont (juce::Font (11.0f));
    barsLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    addAndMakeVisible (barsLabel);

    // ── Temperature slider ──────────────────────────────────────────────────
    temperatureSlider.setSliderStyle (juce::Slider::LinearHorizontal);
    temperatureSlider.setRange (0.1, 2.0, 0.05);
    temperatureSlider.setValue (0.8);
    temperatureSlider.setTextBoxStyle (juce::Slider::TextBoxRight, false, 40, 20);
    addAndMakeVisible (temperatureSlider);

    tempLabel.setText ("Temperature:", juce::dontSendNotification);
    tempLabel.setFont (juce::Font (11.0f));
    tempLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    addAndMakeVisible (tempLabel);

    // ── Model selector ──────────────────────────────────────────────────────
    modelSelector.addItem ("GPT-4", 1);
    modelSelector.addItem ("Claude", 2);
    modelSelector.addItem ("Local Model", 3);
    modelSelector.setSelectedId (1, juce::dontSendNotification);
    addAndMakeVisible (modelSelector);

    modelLabel.setText ("Model:", juce::dontSendNotification);
    modelLabel.setFont (juce::Font (11.0f));
    modelLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    addAndMakeVisible (modelLabel);

    // ── Generate button ─────────────────────────────────────────────────────
    generateButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgSelected);
    generateButton.setColour (juce::TextButton::textColourOffId, MetallicLookAndFeel::accentLight);
    generateButton.onClick = [this]()
    {
        if (onGenerate)
            onGenerate (promptEditor.getText(),
                        (int) barsSlider.getValue(),
                        (float) temperatureSlider.getValue());
    };
    addAndMakeVisible (generateButton);

    // ── Variation controls ──────────────────────────────────────────────────
    variationTypeSelector.addItem ("Humanize", 1);
    variationTypeSelector.addItem ("Rhythmic Shift", 2);
    variationTypeSelector.addItem ("Melodic Shift", 3);
    variationTypeSelector.addItem ("Harmonize", 4);
    variationTypeSelector.addItem ("Simplify", 5);
    variationTypeSelector.addItem ("Complexify", 6);
    variationTypeSelector.addItem ("Style Transfer", 7);
    variationTypeSelector.setSelectedId (1, juce::dontSendNotification);
    addAndMakeVisible (variationTypeSelector);

    varTypeLabel.setText ("Type:", juce::dontSendNotification);
    varTypeLabel.setFont (juce::Font (11.0f));
    varTypeLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    addAndMakeVisible (varTypeLabel);

    variationAmountSlider.setSliderStyle (juce::Slider::LinearHorizontal);
    variationAmountSlider.setRange (0.0, 1.0, 0.01);
    variationAmountSlider.setValue (0.5);
    variationAmountSlider.setTextBoxStyle (juce::Slider::TextBoxRight, false, 40, 20);
    addAndMakeVisible (variationAmountSlider);

    varAmountLabel.setText ("Amount:", juce::dontSendNotification);
    varAmountLabel.setFont (juce::Font (11.0f));
    varAmountLabel.setColour (juce::Label::textColourId, MetallicLookAndFeel::textSecondary);
    addAndMakeVisible (varAmountLabel);

    applyVariationButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgSelected);
    applyVariationButton.setColour (juce::TextButton::textColourOffId, MetallicLookAndFeel::accentLight);
    applyVariationButton.onClick = [this]()
    {
        if (onVariation)
            onVariation (variationTypeSelector.getText(),
                         (float) variationAmountSlider.getValue());
    };
    addAndMakeVisible (applyVariationButton);

    // ── Analysis ────────────────────────────────────────────────────────────
    analysisOutput.setMultiLine (true);
    analysisOutput.setReadOnly (true);
    analysisOutput.setFont (juce::Font (juce::Font::getDefaultMonospacedFontName(), 11.0f, juce::Font::plain));
    analysisOutput.setText ("Click 'Analyze' to inspect the current clip.\n\n"
                            "Analysis will show:\n"
                            "  - Key / Scale detection\n"
                            "  - Note density & range\n"
                            "  - Rhythmic patterns\n"
                            "  - Chord progression\n");
    addAndMakeVisible (analysisOutput);

    analyzeButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgSelected);
    analyzeButton.setColour (juce::TextButton::textColourOffId, MetallicLookAndFeel::accentLight);
    analyzeButton.onClick = [this]()
    {
        if (onAnalyze) onAnalyze();
    };
    addAndMakeVisible (analyzeButton);
}

void AIControlPanel::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgPanel);
}

void AIControlPanel::resized()
{
    auto area = getLocalBounds().reduced (8, 4);

    // Sub-tab area: show all controls, user can scroll or we stack them
    // For now, display generate controls at top, variation in middle, analysis at bottom

    // Generate section
    auto genSection = area.removeFromTop (area.getHeight() / 3);
    {
        auto row = genSection.removeFromTop (24);
        promptEditor.setBounds (row);
        genSection.removeFromTop (4);

        auto row2 = genSection.removeFromTop (22);
        barsLabel.setBounds (row2.removeFromLeft (40));
        barsSlider.setBounds (row2.removeFromLeft (140));
        row2.removeFromLeft (10);
        tempLabel.setBounds (row2.removeFromLeft (80));
        temperatureSlider.setBounds (row2.removeFromLeft (140));

        genSection.removeFromTop (4);
        auto row3 = genSection.removeFromTop (24);
        modelLabel.setBounds (row3.removeFromLeft (45));
        modelSelector.setBounds (row3.removeFromLeft (120));
        row3.removeFromLeft (10);
        generateButton.setBounds (row3.removeFromLeft (100));
    }

    area.removeFromTop (6);

    // Variation section
    auto varSection = area.removeFromTop (area.getHeight() / 2);
    {
        auto row = varSection.removeFromTop (22);
        varTypeLabel.setBounds (row.removeFromLeft (40));
        variationTypeSelector.setBounds (row.removeFromLeft (140));
        row.removeFromLeft (10);
        varAmountLabel.setBounds (row.removeFromLeft (55));
        variationAmountSlider.setBounds (row.removeFromLeft (140));

        varSection.removeFromTop (4);
        auto row2 = varSection.removeFromTop (24);
        applyVariationButton.setBounds (row2.removeFromLeft (100));
    }

    area.removeFromTop (6);

    // Analysis section
    {
        auto row = area.removeFromTop (24);
        analyzeButton.setBounds (row.removeFromLeft (80));
        area.removeFromTop (4);
        analysisOutput.setBounds (area);
    }
}

//==============================================================================
// DetailView
//==============================================================================
DetailView::DetailView()
{
    // Tab buttons
    auto setupTab = [this] (juce::TextButton& btn, Tab tab)
    {
        btn.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgDark);
        btn.setColour (juce::TextButton::buttonOnColourId, MetallicLookAndFeel::bgPanel);
        btn.setColour (juce::TextButton::textColourOffId, MetallicLookAndFeel::textSecondary);
        btn.setColour (juce::TextButton::textColourOnId, MetallicLookAndFeel::textPrimary);
        btn.setClickingTogglesState (true);
        btn.setRadioGroupId (2001);
        btn.onClick = [this, tab]() { setActiveTab (tab); };
        addAndMakeVisible (btn);
    };

    setupTab (tabClipNotes,   ClipNotes);
    setupTab (tabAIGenerate,  AIGenerate);
    setupTab (tabAIVariation, AIVariation);
    setupTab (tabAnalysis,    Analysis);

    tabClipNotes.setToggleState (true, juce::dontSendNotification);

    // Collapse button
    collapseButton.setColour (juce::TextButton::buttonColourId, MetallicLookAndFeel::bgDark);
    collapseButton.setColour (juce::TextButton::textColourOffId, MetallicLookAndFeel::textSecondary);
    collapseButton.onClick = [this]()
    {
        setCollapsed (! collapsed);
    };
    addAndMakeVisible (collapseButton);

    // Content
    addAndMakeVisible (pianoRoll);
    addChildComponent (aiPanel); // hidden by default

    showActiveContent();
}

void DetailView::paint (juce::Graphics& g)
{
    g.fillAll (MetallicLookAndFeel::bgDarkest);

    // Top bar
    g.setColour (MetallicLookAndFeel::bgHeader);
    g.fillRect (0, 0, getWidth(), collapseBarH);

    g.setColour (MetallicLookAndFeel::border);
    g.drawHorizontalLine (0, 0.0f, (float) getWidth());
    g.drawHorizontalLine (collapseBarH - 1, 0.0f, (float) getWidth());

    if (! collapsed)
    {
        g.drawHorizontalLine (collapseBarH + tabBarH - 1, 0.0f, (float) getWidth());
    }
}

void DetailView::resized()
{
    auto area = getLocalBounds();

    // Collapse bar
    auto barArea = area.removeFromTop (collapseBarH);
    collapseButton.setBounds (barArea.removeFromRight (30).reduced (2));

    if (collapsed)
        return;

    // Tab bar
    auto tabArea = area.removeFromTop (tabBarH);
    int tabW = juce::jmin (120, tabArea.getWidth() / 4);
    tabClipNotes.setBounds (tabArea.removeFromLeft (tabW).reduced (1, 2));
    tabAIGenerate.setBounds (tabArea.removeFromLeft (tabW).reduced (1, 2));
    tabAIVariation.setBounds (tabArea.removeFromLeft (tabW).reduced (1, 2));
    tabAnalysis.setBounds (tabArea.removeFromLeft (tabW).reduced (1, 2));

    // Content area
    pianoRoll.setBounds (area);
    aiPanel.setBounds (area);
}

void DetailView::setCollapsed (bool shouldCollapse)
{
    collapsed = shouldCollapse;
    collapseButton.setButtonText (collapsed ? "^" : "v");

    pianoRoll.setVisible (! collapsed && activeTab == ClipNotes);
    aiPanel.setVisible (! collapsed && activeTab != ClipNotes);

    if (onCollapseChanged)
        onCollapseChanged (collapsed);

    resized();
    repaint();
}

void DetailView::setActiveTab (Tab tab)
{
    activeTab = tab;
    updateTabStates();
    showActiveContent();
    resized();
}

void DetailView::updateTabStates()
{
    tabClipNotes.setToggleState   (activeTab == ClipNotes,   juce::dontSendNotification);
    tabAIGenerate.setToggleState  (activeTab == AIGenerate,  juce::dontSendNotification);
    tabAIVariation.setToggleState (activeTab == AIVariation, juce::dontSendNotification);
    tabAnalysis.setToggleState    (activeTab == Analysis,    juce::dontSendNotification);
}

void DetailView::showActiveContent()
{
    pianoRoll.setVisible (activeTab == ClipNotes && ! collapsed);
    aiPanel.setVisible (activeTab != ClipNotes && ! collapsed);
}

void DetailView::setAnalysisText (const juce::String& text)
{
    aiPanel.setAnalysisText (text);
}

void AIControlPanel::setAnalysisText (const juce::String& text)
{
    analysisOutput.setText (text);
}
