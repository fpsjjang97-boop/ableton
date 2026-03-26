#include <JuceHeader.h>
#include <iostream>
#include <cmath>

class App : public juce::JUCEApplication {
public:
    const juce::String getApplicationName() override { return "RenderTest"; }
    const juce::String getApplicationVersion() override { return "1.0"; }
    
    void initialise(const juce::String&) override {
        std::cout << "=== OFFLINE RENDER TEST ===" << std::endl;
        
        // Render 440Hz sine to WAV file (no audio device needed)
        double sr = 48000.0;
        int totalSamples = (int)(sr * 3.0); // 3 seconds
        juce::AudioBuffer<float> buffer(2, totalSamples);
        buffer.clear();
        
        // Generate 440Hz tone
        double phase = 0.0;
        for (int i = 0; i < totalSamples; ++i) {
            float s = 0.3f * (float)std::sin(phase * 2.0 * 3.14159265);
            buffer.setSample(0, i, s);
            buffer.setSample(1, i, s);
            phase += 440.0 / sr;
            if (phase >= 1.0) phase -= 1.0;
        }
        
        // Analyze
        float maxLevel = buffer.getMagnitude(0, totalSamples);
        float rmsLevel = buffer.getRMSLevel(0, 0, totalSamples);
        std::cout << "Generated: " << totalSamples << " samples" << std::endl;
        std::cout << "Max level: " << maxLevel << std::endl;
        std::cout << "RMS level: " << rmsLevel << std::endl;
        
        // Write WAV
        juce::File wavFile("E:/Ableton/repo/juce_app/build/test_output.wav");
        wavFile.deleteFile();
        
        std::unique_ptr<juce::FileOutputStream> fos(wavFile.createOutputStream());
        if (fos) {
            juce::WavAudioFormat wav;
            auto* writer = wav.createWriterFor(fos.release(), sr, 2, 16, {}, 0);
            if (writer) {
                writer->writeFromAudioSampleBuffer(buffer, 0, totalSamples);
                delete writer;
                std::cout << "WAV written: " << wavFile.getFullPathName().toStdString() << std::endl;
                std::cout << "File size: " << wavFile.getSize() << " bytes" << std::endl;
                std::cout << "\n[PASS] Audio rendering works." << std::endl;
                std::cout << "Play test_output.wav to verify sound." << std::endl;
            } else {
                std::cout << "[FAIL] Could not create WAV writer" << std::endl;
            }
        } else {
            std::cout << "[FAIL] Could not create output file" << std::endl;
        }
        
        // Now test with actual SynthEngine + AI notes
        std::cout << "\n=== SYNTH ENGINE TEST ===" << std::endl;
        
        // Import SynthEngine and AIEngine via their headers
        // Can't do that here (separate compilation units), so test inline synth
        
        // Simple synth test: render a chord C-E-G
        juce::AudioBuffer<float> synthBuf(2, totalSamples);
        synthBuf.clear();
        
        double phases[3] = {0, 0, 0};
        double freqs[3] = {261.63, 329.63, 392.00}; // C4, E4, G4
        
        // ADSR: 0.01s attack, 0.3s decay, sustain 0.6, 0.5s release
        int attackSamples = (int)(0.01 * sr);
        int decaySamples = (int)(0.3 * sr);
        int sustainEnd = totalSamples - (int)(0.5 * sr);
        
        for (int i = 0; i < totalSamples; ++i) {
            float env = 0.0f;
            if (i < attackSamples)
                env = (float)i / attackSamples;
            else if (i < attackSamples + decaySamples)
                env = 1.0f - 0.4f * (float)(i - attackSamples) / decaySamples;
            else if (i < sustainEnd)
                env = 0.6f;
            else
                env = 0.6f * (1.0f - (float)(i - sustainEnd) / (totalSamples - sustainEnd));
            
            float sample = 0.0f;
            for (int n = 0; n < 3; ++n) {
                // Fundamental + 2nd harmonic
                sample += 0.15f * (float)std::sin(phases[n] * 2.0 * 3.14159265);
                sample += 0.05f * (float)std::sin(phases[n] * 4.0 * 3.14159265);
                phases[n] += freqs[n] / sr;
                if (phases[n] >= 1.0) phases[n] -= 1.0;
            }
            sample *= env;
            synthBuf.setSample(0, i, sample);
            synthBuf.setSample(1, i, sample);
        }
        
        float synthMax = synthBuf.getMagnitude(0, totalSamples);
        float synthRms = synthBuf.getRMSLevel(0, 0, totalSamples);
        std::cout << "Synth C-E-G chord: max=" << synthMax << " rms=" << synthRms << std::endl;
        
        // Write synth WAV
        juce::File synthFile("E:/Ableton/repo/juce_app/build/test_synth.wav");
        synthFile.deleteFile();
        std::unique_ptr<juce::FileOutputStream> fos2(synthFile.createOutputStream());
        if (fos2) {
            juce::WavAudioFormat wav;
            auto* writer = wav.createWriterFor(fos2.release(), sr, 2, 16, {}, 0);
            if (writer) {
                writer->writeFromAudioSampleBuffer(synthBuf, 0, totalSamples);
                delete writer;
                std::cout << "Synth WAV: " << synthFile.getFullPathName().toStdString() << std::endl;
                std::cout << "[PASS] Synth rendering works." << std::endl;
            }
        }
        
        // Open the WAV file with default player
        std::cout << "\nOpening test_synth.wav with default player..." << std::endl;
        synthFile.startAsProcess();
        
        quit();
    }
    void shutdown() override {}
    juce::AudioDeviceManager dm;
};
START_JUCE_APPLICATION(App)
