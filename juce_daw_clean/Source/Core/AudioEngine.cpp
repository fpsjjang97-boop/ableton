/*
 * MidiGPT DAW - AudioEngine.cpp
 */

#include "AudioEngine.h"

AudioEngine::AudioEngine()
{
    midiEngine.setTrackModel(&trackModel);
}

AudioEngine::~AudioEngine()
{
    shutdown();
}

void AudioEngine::initialise()
{
    // Try default devices first
    auto result = deviceManager.initialiseWithDefaultDevices(0, 2);

    if (result.isNotEmpty())
    {
        DBG("AudioEngine: default init failed: " + result);

        // Fallback: try with explicit setup
        juce::AudioDeviceManager::AudioDeviceSetup setup;
        setup.outputChannels.setRange(0, 2, true);
        setup.inputChannels.clear();
        setup.sampleRate = 44100.0;
        setup.bufferSize = 512;
        result = deviceManager.initialise(0, 2, nullptr, true, {}, &setup);

        if (result.isNotEmpty())
            DBG("AudioEngine: fallback init also failed: " + result);
    }

    deviceManager.addAudioCallback(this);

    // Log which device we're using
    if (auto* device = deviceManager.getCurrentAudioDevice())
        DBG("AudioEngine: using " + device->getName() + " @ "
            + juce::String(device->getCurrentSampleRate()) + " Hz");
    else
        DBG("AudioEngine: WARNING - no audio device!");
}

void AudioEngine::shutdown()
{
    deviceManager.removeAudioCallback(this);
    deviceManager.closeAudioDevice();
}

void AudioEngine::play()
{
    // Auto-rewind if at the end or past all content
    if (midiEngine.getPositionBeats() > 64.0)
        midiEngine.setPositionBeats(0.0);

    midiEngine.setPlaying(true);
    lastMetronomeBeat = -1.0;
    testBeepSamples = testBeepLength; // no beep (set to 0 to debug audio)
}

void AudioEngine::stop()
{
    midiEngine.setPlaying(false);
    synthEngine.allNotesOff();
}

void AudioEngine::togglePlayStop()
{
    if (midiEngine.isPlaying()) stop(); else play();
}

void AudioEngine::rewind()
{
    midiEngine.setPositionBeats(0.0);
    synthEngine.allNotesOff();
    lastMetronomeBeat = -1.0;
}

// ---------------------------------------------------------------------------
void AudioEngine::audioDeviceIOCallbackWithContext(
    const float* const*, int,
    float* const* outputChannelData, int numOutputChannels,
    int numSamples, const juce::AudioIODeviceCallbackContext&)
{
    // Clear
    for (int ch = 0; ch < numOutputChannels; ++ch)
        if (outputChannelData[ch])
            juce::FloatVectorOperations::clear(outputChannelData[ch], numSamples);

    // MIDI sequencer
    juce::MidiBuffer midiBuf;
    double beatsBefore = midiEngine.getPositionBeats();
    midiEngine.processBlock(numSamples, currentSampleRate, midiBuf);

    // Apply per-track volume by scaling MIDI velocity
    juce::MidiBuffer volumeAdjustedMidi;
    auto& tracks = trackModel.getTracks();

    for (const auto meta : midiBuf)
    {
        auto msg = meta.getMessage();
        if (msg.isNoteOn())
        {
            // Find track by channel, scale velocity by track volume
            for (auto& track : tracks)
            {
                if (track.midiChannel == msg.getChannel())
                {
                    int scaledVel = juce::jlimit(1, 127,
                        (int)(msg.getVelocity() * track.volume));
                    msg = juce::MidiMessage::noteOn(msg.getChannel(),
                        msg.getNoteNumber(), (juce::uint8)scaledVel);
                    msg.setTimeStamp(meta.getMessage().getTimeStamp());
                    break;
                }
            }
        }
        volumeAdjustedMidi.addEvent(msg, meta.samplePosition);
    }

    // Render all MIDI through single synth instance
    juce::AudioBuffer<float> tempBuf(numOutputChannels, numSamples);
    tempBuf.clear();
    synthEngine.renderBlock(tempBuf, volumeAdjustedMidi);

    // Copy to output with master volume
    for (int ch = 0; ch < juce::jmin(numOutputChannels, tempBuf.getNumChannels()); ++ch)
    {
        auto* dest = outputChannelData[ch];
        auto* src = tempBuf.getReadPointer(ch);
        for (int s = 0; s < numSamples; ++s)
            dest[s] += src[s] * masterVolume;
    }

    // Metronome
    if (metronomeOn && midiEngine.isPlaying())
    {
        double beatsAfter = midiEngine.getPositionBeats();
        double beatFloorBefore = std::floor(beatsBefore);
        double beatFloorAfter = std::floor(beatsAfter);

        if (beatFloorAfter > beatFloorBefore || beatsBefore < 0.001)
        {
            metronomeClickSample = 0;
            metronomeIsDownbeat = (std::fmod(beatsAfter, 4.0) < 1.0);
        }

        if (numOutputChannels >= 2)
            generateMetronomeClick(outputChannelData[0], outputChannelData[1], numSamples);
        else if (numOutputChannels >= 1)
            generateMetronomeClick(outputChannelData[0], outputChannelData[0], numSamples);
    }

    // Send MIDI to external output
    if (!midiBuf.isEmpty())
    {
        auto* midiOut = deviceManager.getDefaultMidiOutput();
        if (midiOut) midiOut->sendBlockOfMessagesNow(midiBuf);
    }

    // Test beep (A440, 0.5s) - verifies audio output works
    if (testBeepSamples < testBeepLength)
    {
        for (int s = 0; s < numSamples && testBeepSamples < testBeepLength; ++s, ++testBeepSamples)
        {
            float t = (float)testBeepSamples / (float)testBeepLength;
            float env = (1.0f - t) * 0.4f; // fade out
            float sample = std::sin(2.0f * juce::MathConstants<float>::pi * 440.0f
                                    * testBeepSamples / (float)currentSampleRate) * env;
            for (int ch = 0; ch < numOutputChannels; ++ch)
                outputChannelData[ch][s] += sample;
        }
    }

    // VU meters
    if (numOutputChannels >= 1)
    {
        float peakL = 0.0f;
        for (int s = 0; s < numSamples; ++s)
            peakL = juce::jmax(peakL, std::abs(outputChannelData[0][s]));
        vuLeft = vuLeft * 0.92f + peakL * 0.08f;
    }
    if (numOutputChannels >= 2)
    {
        float peakR = 0.0f;
        for (int s = 0; s < numSamples; ++s)
            peakR = juce::jmax(peakR, std::abs(outputChannelData[1][s]));
        vuRight = vuRight * 0.92f + peakR * 0.08f;
    }
}

void AudioEngine::generateMetronomeClick(float* left, float* right, int numSamples)
{
    const int clickDuration = static_cast<int>(currentSampleRate * 0.03); // 30ms
    const float freq = metronomeIsDownbeat ? 1500.0f : 1000.0f;
    const float vol = metronomeIsDownbeat ? 0.5f : 0.35f;

    for (int s = 0; s < numSamples; ++s)
    {
        if (metronomeClickSample < clickDuration)
        {
            float t = static_cast<float>(metronomeClickSample) / static_cast<float>(clickDuration);
            float env = std::exp(-t * 8.0f);
            float sample = std::sin(2.0f * juce::MathConstants<float>::pi * freq
                                    * metronomeClickSample / (float)currentSampleRate)
                           * env * vol;
            left[s] += sample;
            right[s] += sample;
        }
        metronomeClickSample++;
    }
}

void AudioEngine::audioDeviceAboutToStart(juce::AudioIODevice* device)
{
    currentSampleRate = device->getCurrentSampleRate();
    synthEngine.prepare(currentSampleRate, device->getCurrentBufferSizeSamples());
}

void AudioEngine::audioDeviceStopped()
{
    currentSampleRate = 44100.0;
}
