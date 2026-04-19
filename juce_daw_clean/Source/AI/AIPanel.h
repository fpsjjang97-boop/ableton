/*
 * MidiGPT DAW - AIPanel
 *
 * UI panel for MidiGPT LLM controls: style, temperature,
 * generate button, server status.
 */

#pragma once

#include <atomic>

#include <juce_gui_basics/juce_gui_basics.h>
#include "AIBridge.h"
#include "../Core/AudioEngine.h"

class AIPanel : public juce::Component,
                public juce::Timer
{
public:
    AIPanel(AudioEngine& engine);
    ~AIPanel() override;

    void paint(juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    /** Set the clip that AI generation will target. */
    void setTargetTrackId(int id) { targetTrackId = id; }

private:
    AudioEngine& audioEngine;
    AIBridge aiBridge;

    int targetTrackId { -1 };
    bool serverConnected { false };

    // Sprint 48 LLL 수정: 동기 HTTP 를 GUI 스레드에서 돌리던 것이 "응답 없음"
    // 트리거였음. 한 번에 최대 하나의 백그라운드 probe 만 돌게 guard + 결과는
    // MessageManager::callAsync 로 메인에 post.
    std::atomic<bool> healthProbeInFlight { false };
    std::atomic<bool> shuttingDown { false };
    void probeHealthAsync();

    juce::TextButton generateButton { "Generate Variation" };
    juce::TextButton connectButton  { "Check Server" };

    juce::Slider temperatureSlider;
    juce::Label  temperatureLabel { {}, "Temperature" };

    juce::ComboBox styleBox;
    juce::Label    styleLabel { {}, "Style" };

    juce::Slider variationsSlider;
    juce::Label  variationsLabel { {}, "Variations" };

    juce::Label statusLabel { {}, "Disconnected" };

    void onGenerate();
    void onCheckServer();

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AIPanel)
};
