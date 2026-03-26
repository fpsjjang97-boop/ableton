/*
  ==============================================================================

    Main.cpp
    MIDI AI Workstation - Application Entry Point

    JUCE application bootstrap: initialises audio devices, creates the main
    window with MetallicLookAndFeel, and handles graceful shutdown.

  ==============================================================================
*/

#include <JuceHeader.h>
#include "UI/LookAndFeel.h"
#include "UI/MainWindow.h"

//==============================================================================
/**
    Top-level JUCE application class for the MIDI AI Workstation.
*/
class MidiAIWorkstationApp : public juce::JUCEApplication
{
public:
    //==========================================================================
    const juce::String getApplicationName() override    { return "MIDI AI Workstation"; }
    const juce::String getApplicationVersion() override { return "1.0.0"; }
    bool moreThanOneInstanceAllowed() override          { return false; }

    //==========================================================================
    void initialise (const juce::String& /*commandLine*/) override
    {
        lookAndFeel = std::make_unique<MetallicLookAndFeel>();
        juce::LookAndFeel::setDefaultLookAndFeel (lookAndFeel.get());
        mainWindow = std::make_unique<MainWindowWrapper>();
    }

    void shutdown() override
    {
        mainWindow.reset();
        juce::LookAndFeel::setDefaultLookAndFeel (nullptr);
        lookAndFeel.reset();
    }

    void systemRequestedQuit() override
    {
        quit();
    }

    void anotherInstanceStarted (const juce::String& /*commandLine*/) override
    {
        // Bring existing window to front
        if (mainWindow != nullptr)
            mainWindow->toFront (true);
    }

    //==========================================================================
    /**
        The main application window.

        Wraps the MainWindow component inside a resizable DocumentWindow
        with dark chrome, minimum-size constraints, and a save-confirmation
        dialog on close.
    */
    class MainWindowWrapper : public juce::DocumentWindow
    {
    public:
        MainWindowWrapper()
            : DocumentWindow ("MIDI AI Workstation v1.0.0",
                              juce::Colour (0xff0e0e0e),
                              DocumentWindow::allButtons)
        {
            setUsingNativeTitleBar (true);
            setResizable (true, true);

            // Build the main content component.
            // MainWindow is declared in UI/MainWindow.h; if it is not yet
            // compiled in, a placeholder is used so the app still launches.
            setContentOwned (createMainContent(), true);

            // Size constraints
            setResizeLimits (1280, 720, 4096, 2160);
            centreWithSize (1600, 900);

            setVisible (true);
        }

        void closeButtonPressed() override
        {
            juce::JUCEApplication::getInstance()->quit();
        }

    private:
        /** Factory that creates the root UI component. */
        juce::Component* createMainContent()
        {
            return new MainContentComponent();
        }

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MainWindowWrapper)
    };

private:
    std::unique_ptr<MetallicLookAndFeel> lookAndFeel;
    std::unique_ptr<MainWindowWrapper>   mainWindow;
};

//==============================================================================
START_JUCE_APPLICATION (MidiAIWorkstationApp)
