#include "MidiEngine.h"

MidiEngine::MidiEngine() {}

MidiEngine::~MidiEngine()
{
    closeOutput();
    closeInput();
}

// ============================================================
// Output
// ============================================================

juce::StringArray MidiEngine::getAvailableOutputs() const
{
    juce::StringArray names;
    for (auto& info : juce::MidiOutput::getAvailableDevices())
        names.add(info.name);
    return names;
}

bool MidiEngine::openOutput(const juce::String& deviceName)
{
    closeOutput();
    for (auto& info : juce::MidiOutput::getAvailableDevices())
    {
        if (info.name == deviceName)
        {
            midiOutput = juce::MidiOutput::openDevice(info.identifier);
            return midiOutput != nullptr;
        }
    }
    return false;
}

void MidiEngine::closeOutput()
{
    if (midiOutput)
    {
        sendAllNotesOff();
        midiOutput.reset();
    }
}

void MidiEngine::sendMessage(const juce::MidiMessage& msg)
{
    if (midiOutput)
        midiOutput->sendMessageNow(msg);
}

void MidiEngine::sendNoteOn(int channel, int note, float velocity)
{
    sendMessage(juce::MidiMessage::noteOn(channel, note, velocity));
}

void MidiEngine::sendNoteOff(int channel, int note)
{
    sendMessage(juce::MidiMessage::noteOff(channel, note));
}

void MidiEngine::sendAllNotesOff()
{
    if (!midiOutput) return;
    for (int ch = 1; ch <= 16; ++ch)
    {
        midiOutput->sendMessageNow(juce::MidiMessage::allNotesOff(ch));
        midiOutput->sendMessageNow(juce::MidiMessage::allSoundOff(ch));
    }
}

void MidiEngine::sendProgramChange(int channel, int program)
{
    sendMessage(juce::MidiMessage::programChange(channel, program));
}

// ============================================================
// Input
// ============================================================

juce::StringArray MidiEngine::getAvailableInputs() const
{
    juce::StringArray names;
    for (auto& info : juce::MidiInput::getAvailableDevices())
        names.add(info.name);
    return names;
}

bool MidiEngine::openInput(const juce::String& deviceName)
{
    closeInput();
    for (auto& info : juce::MidiInput::getAvailableDevices())
    {
        if (info.name == deviceName)
        {
            midiInput = juce::MidiInput::openDevice(info.identifier, this);
            if (midiInput)
            {
                midiInput->start();
                return true;
            }
        }
    }
    return false;
}

void MidiEngine::closeInput()
{
    if (midiInput)
    {
        midiInput->stop();
        midiInput.reset();
    }
}

void MidiEngine::handleIncomingMidiMessage(juce::MidiInput* /*source*/,
                                            const juce::MidiMessage& message)
{
    if (onMidiInput)
        onMidiInput(message);
}
