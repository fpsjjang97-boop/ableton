#include <JuceHeader.h>
#include <iostream>
#include <cmath>

class BeepSource : public juce::AudioSource {
public:
    void prepareToPlay(int, double sr) override { sampleRate = sr; std::cout << "prepareToPlay sr=" << sr << std::endl; }
    void releaseResources() override {}
    void getNextAudioBlock(const juce::AudioSourceChannelInfo& b) override {
        for (int i = 0; i < b.numSamples; ++i) {
            float s = 0.3f * (float)std::sin(phase * 2.0 * 3.14159265);
            phase += 440.0 / sampleRate;
            if (phase >= 1.0) phase -= 1.0;
            for (int ch = 0; ch < b.buffer->getNumChannels(); ++ch)
                b.buffer->setSample(ch, b.startSample + i, s);
        }
        blockCount++;
        if (blockCount % 100 == 0)
            std::cout << "rendered " << blockCount << " blocks" << std::endl;
    }
    double sampleRate = 44100.0, phase = 0.0;
    int blockCount = 0;
};

class App : public juce::JUCEApplication {
public:
    const juce::String getApplicationName() override { return "BeepTest"; }
    const juce::String getApplicationVersion() override { return "1.0"; }
    void initialise(const juce::String&) override {
        std::cout << "=== Audio Device Test ===" << std::endl;
        
        // List available device types
        auto& types = dm.getAvailableDeviceTypes();
        std::cout << "Device types: " << types.size() << std::endl;
        for (auto* t : types)
            std::cout << "  Type: " << t->getTypeName().toStdString() << std::endl;
        
        // Initialize
        auto err = dm.initialiseWithDefaultDevices(0, 2);
        if (err.isNotEmpty())
            std::cout << "Init error: " << err.toStdString() << std::endl;
        else
            std::cout << "Init OK" << std::endl;
        
        auto* dev = dm.getCurrentAudioDevice();
        if (dev) {
            std::cout << "Device: " << dev->getName().toStdString() << std::endl;
            std::cout << "SampleRate: " << dev->getCurrentSampleRate() << std::endl;
            std::cout << "BufferSize: " << dev->getCurrentBufferSizeSamples() << std::endl;
            std::cout << "OutputChannels: " << dev->getActiveOutputChannels().countNumberOfSetBits() << std::endl;
        } else {
            std::cout << "NO DEVICE FOUND!" << std::endl;
        }
        
        player.setSource(&beep);
        dm.addAudioCallback(&player);
        std::cout << "Audio callback added. Should hear 440Hz beep..." << std::endl;
        std::cout << "Waiting 5 seconds..." << std::endl;
        
        juce::Timer::callAfterDelay(5000, [this]() {
            std::cout << "Blocks rendered: " << beep.blockCount << std::endl;
            if (beep.blockCount == 0)
                std::cout << "*** NO AUDIO BLOCKS RENDERED - AUDIO PIPELINE BROKEN ***" << std::endl;
            else
                std::cout << "Audio pipeline working!" << std::endl;
            quit();
        });
    }
    void shutdown() override {
        dm.removeAudioCallback(&player);
        player.setSource(nullptr);
    }
    juce::AudioDeviceManager dm;
    juce::AudioSourcePlayer player;
    BeepSource beep;
};

START_JUCE_APPLICATION(App)
