#include <JuceHeader.h>
#include <iostream>
#include <cmath>

class TestTone : public juce::AudioSource
{
public:
    void prepareToPlay(int, double sr) override { sampleRate = sr; }
    void releaseResources() override {}
    void getNextAudioBlock(const juce::AudioSourceChannelInfo& buf) override
    {
        for (int i = 0; i < buf.numSamples; ++i)
        {
            float sample = 0.3f * (float)std::sin(phase * 2.0 * 3.14159265);
            phase += 440.0 / sampleRate;
            if (phase >= 1.0) phase -= 1.0;
            for (int ch = 0; ch < buf.buffer->getNumChannels(); ++ch)
                buf.buffer->setSample(ch, buf.startSample + i, sample);
        }
    }
    double sampleRate = 44100.0, phase = 0.0;
};

class App : public juce::JUCEApplication
{
public:
    const juce::String getApplicationName() override { return "AudioTest"; }
    const juce::String getApplicationVersion() override { return "1.0"; }
    void initialise(const juce::String&) override
    {
        std::cout << "Initializing audio..." << std::endl;
        auto result = dm.initialiseWithDefaultDevices(0, 2);
        if (result.isNotEmpty())
            std::cout << "Audio init: " << result.toStdString() << std::endl;

        auto* device = dm.getCurrentAudioDevice();
        if (device)
        {
            std::cout << "Device: " << device->getName().toStdString() << std::endl;
            std::cout << "Sample rate: " << device->getCurrentSampleRate() << std::endl;
            std::cout << "Buffer size: " << device->getCurrentBufferSizeSamples() << std::endl;
        }
        else
        {
            std::cout << "NO AUDIO DEVICE!" << std::endl;
        }

        player.setSource(&tone);
        dm.addAudioCallback(&player);
        std::cout << "Playing 440Hz tone for 3 seconds..." << std::endl;

        juce::Timer::callAfterDelay(3000, [this]() { quit(); });
    }
    void shutdown() override
    {
        dm.removeAudioCallback(&player);
        player.setSource(nullptr);
        std::cout << "Done." << std::endl;
    }

    juce::AudioDeviceManager dm;
    juce::AudioSourcePlayer player;
    TestTone tone;
};

START_JUCE_APPLICATION(App)
