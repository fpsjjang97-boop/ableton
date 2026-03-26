#pragma once
#include <JuceHeader.h>

/**
 * MidiEngine — handles MIDI device I/O (input/output ports).
 * Routes incoming MIDI to recording tracks, outgoing MIDI to hardware.
 */
class MidiEngine : public juce::MidiInputCallback
{
public:
    MidiEngine();
    ~MidiEngine() override;

    // MIDI Output
    juce::StringArray getAvailableOutputs() const;
    bool openOutput(const juce::String& deviceName);
    void closeOutput();
    juce::MidiOutput* getOutput() const { return midiOutput.get(); }

    void sendMessage(const juce::MidiMessage& msg);
    void sendNoteOn(int channel, int note, float velocity);
    void sendNoteOff(int channel, int note);
    void sendAllNotesOff();
    void sendProgramChange(int channel, int program);

    // MIDI Input
    juce::StringArray getAvailableInputs() const;
    bool openInput(const juce::String& deviceName);
    void closeInput();

    // Callback for incoming MIDI
    std::function<void(const juce::MidiMessage&)> onMidiInput;

    // MidiInputCallback
    void handleIncomingMidiMessage(juce::MidiInput* source,
                                   const juce::MidiMessage& message) override;

private:
    std::unique_ptr<juce::MidiOutput> midiOutput;
    std::unique_ptr<juce::MidiInput> midiInput;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MidiEngine)
};
