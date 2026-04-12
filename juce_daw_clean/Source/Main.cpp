/*
 * MidiGPT DAW - Main.cpp
 *
 * Application entry point. Creates the main window.
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include <juce_gui_basics/juce_gui_basics.h>
#include "MainWindow.h"

class MidiGPTApplication : public juce::JUCEApplication
{
public:
    const juce::String getApplicationName() override    { return "MidiGPT"; }
    const juce::String getApplicationVersion() override { return "0.1.0"; }
    bool moreThanOneInstanceAllowed() override           { return false; }

    void initialise(const juce::String& /*commandLine*/) override
    {
        mainWindow = std::make_unique<MainWindow>("MidiGPT DAW");
    }

    void shutdown() override
    {
        mainWindow.reset();
    }

    void systemRequestedQuit() override
    {
        quit();
    }

private:
    std::unique_ptr<MainWindow> mainWindow;
};

START_JUCE_APPLICATION(MidiGPTApplication)
