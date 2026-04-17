/*
 * MidiGPT VST3 Plugin — First-run TutorialOverlay
 *
 * Full-panel semi-transparent overlay that walks the user through the
 * editor the first time they open it. Uses juce::PropertiesFile to store
 * the "tutorial_seen" flag so subsequent sessions skip it.
 *
 * Design: one overlay, N "steps" each highlighting a control. User clicks
 * "Next" to advance, "Skip" to dismiss. No arrows or complicated rigging —
 * just a dim backdrop + a bright rectangle around the current target +
 * a caption card. Simple, robust, localised via I18n.
 *
 * Sprint 35 ZZ5.
 */

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <functional>
#include "I18n.h"

class TutorialOverlay : public juce::Component
{
public:
    struct Step
    {
        juce::Component* target;   // the control being highlighted (may be null = full screen)
        juce::String titleKey;     // I18n key, e.g. "tut.step1.title"
        juce::String bodyKey;
    };

    using DismissCallback = std::function<void()>;

    TutorialOverlay()
    {
        setInterceptsMouseClicks (true, true);

        nextButton.setButtonText ("Next");
        nextButton.onClick = [this] { advance(); };
        addAndMakeVisible (nextButton);

        skipButton.setButtonText ("Skip");
        skipButton.onClick = [this] { dismiss(); };
        addAndMakeVisible (skipButton);
    }

    void setSteps (juce::Array<Step> s) { steps = std::move (s); idx = 0; repaint(); }
    void setOnDismiss (DismissCallback cb) { onDismiss = std::move (cb); }

    void start()
    {
        idx = 0;
        setVisible (true);
        toFront (true);
    }

    void paint (juce::Graphics& g) override
    {
        g.fillAll (juce::Colours::black.withAlpha (0.72f));

        if (idx >= steps.size())
        {
            dismiss();
            return;
        }

        const auto& step = steps.getReference (idx);

        // Highlight ring around the current target (if any).
        if (step.target != nullptr && step.target->isVisible())
        {
            auto tb = step.target->getBoundsInParent();
            // Walk up the tree to map into our local coords.
            auto* p = step.target->getParentComponent();
            while (p != nullptr && p != this)
            {
                tb += p->getBoundsInParent().getTopLeft();
                p = p->getParentComponent();
            }
            auto ring = tb.expanded (6).toFloat();

            // Cut a hole: re-fill the target rect with transparent so the
            // underlying UI shows through. JUCE doesn't give us a clean
            // "punch-out" so we draw a coloured stroke to call attention.
            g.setColour (juce::Colours::white.withAlpha (0.08f));
            g.fillRoundedRectangle (ring, 6.0f);
            g.setColour (juce::Colours::yellow);
            g.drawRoundedRectangle (ring, 6.0f, 3.0f);
        }

        // Caption card (centred).
        auto card = getLocalBounds().withSizeKeepingCentre (juce::jmin (420, getWidth() - 32), 140).toFloat();
        g.setColour (juce::Colour (0xFF2A2D3A));
        g.fillRoundedRectangle (card, 8.0f);
        g.setColour (juce::Colours::white.withAlpha (0.2f));
        g.drawRoundedRectangle (card, 8.0f, 1.5f);

        g.setColour (juce::Colours::white);
        g.setFont (16.0f);
        g.drawFittedText (I18n::t (step.titleKey),
                          card.toNearestInt().reduced (16, 12).withHeight (24),
                          juce::Justification::centredLeft, 1);
        g.setFont (12.0f);
        g.setColour (juce::Colours::lightgrey);
        g.drawFittedText (I18n::t (step.bodyKey),
                          card.toNearestInt().reduced (16, 12).translated (0, 28)
                              .withHeight ((int) card.getHeight() - 56),
                          juce::Justification::topLeft, 4);

        g.setColour (juce::Colours::grey);
        g.setFont (11.0f);
        g.drawFittedText (juce::String (idx + 1) + " / " + juce::String (steps.size()),
                          card.toNearestInt().reduced (16, 10).withY ((int) card.getBottom() - 22),
                          juce::Justification::bottomLeft, 1);
    }

    void resized() override
    {
        // Buttons anchored to the caption card bottom-right.
        auto card = getLocalBounds().withSizeKeepingCentre (juce::jmin (420, getWidth() - 32), 140);
        nextButton.setBounds (card.getRight() - 80, card.getBottom() - 34, 64, 24);
        skipButton.setBounds (card.getRight() - 160, card.getBottom() - 34, 64, 24);
    }

private:
    void advance()
    {
        ++idx;
        if (idx >= steps.size()) dismiss();
        else                     repaint();
    }
    void dismiss()
    {
        setVisible (false);
        if (onDismiss) onDismiss();
    }

    juce::Array<Step> steps;
    int idx { 0 };
    juce::TextButton nextButton, skipButton;
    DismissCallback onDismiss;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TutorialOverlay)
};
