/*
 * MidiGPT DAW - AIPanel.cpp
 */

#include "../UI/LookAndFeel.h"
#include "AIPanel.h"

AIPanel::AIPanel(AudioEngine& engine)
    : audioEngine(engine)
{
    generateButton.setColour(juce::TextButton::buttonColourId, juce::Colour(MetallicLookAndFeel::accent));
    generateButton.onClick = [this] { onGenerate(); };
    addAndMakeVisible(generateButton);

    connectButton.onClick = [this] { onCheckServer(); };
    addAndMakeVisible(connectButton);

    temperatureSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    temperatureSlider.setRange(0.5, 1.5, 0.01);
    temperatureSlider.setValue(0.9);
    temperatureSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 45, 20);
    addAndMakeVisible(temperatureSlider);
    temperatureLabel.attachToComponent(&temperatureSlider, true);
    addAndMakeVisible(temperatureLabel);

    styleBox.addItemList({"base", "jazz", "citypop", "metal", "classical"}, 1);
    styleBox.setSelectedId(1);
    addAndMakeVisible(styleBox);
    styleLabel.attachToComponent(&styleBox, true);
    addAndMakeVisible(styleLabel);

    variationsSlider.setSliderStyle(juce::Slider::IncDecButtons);
    variationsSlider.setRange(1, 5, 1);
    variationsSlider.setValue(1);
    variationsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 40, 20);
    addAndMakeVisible(variationsSlider);
    variationsLabel.attachToComponent(&variationsSlider, true);
    addAndMakeVisible(variationsLabel);

    statusLabel.setJustificationType(juce::Justification::centred);
    statusLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible(statusLabel);

    // Sprint 48 LLL — AIPanel::timerCallback 이 GUI 스레드에서 동기 HTTP
    // checkHealth(500ms) 를 매초 호출해 "응답 없음" 을 유발했다. 근본 수정:
    //   1) 간격을 3초로 완화 (서버 상태는 초단위로 바뀌지 않음)
    //   2) 실제 요청은 probeHealthAsync() 가 juce::Thread::launch 로 백그라운드에서
    //   3) 결과는 MessageManager::callAsync 로 GUI 스레드에 post
    //   4) healthProbeInFlight 로 중첩 호출 차단 (서버 다운이면 probe 가 길어질 수 있음)
    startTimer(3000);
}

AIPanel::~AIPanel()
{
    // Sprint 48 LLL — 백그라운드 probe 가 AIPanel 사망 후 GUI 포스트하지 않도록
    // 플래그. 완전한 join 은 AIBridge 내부 AsyncWorker 가 관리; 여기선 post 후
    // captured 'this' 접근만 차단하면 충분.
    shuttingDown.store(true);
    stopTimer();
}

void AIPanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(MetallicLookAndFeel::bgPanel));

    g.setColour(juce::Colours::white);
    g.setFont(14.0f);
    g.drawText("MidiGPT AI", 8, 4, getWidth(), 20, juce::Justification::centredLeft);

    g.setColour(juce::Colour(MetallicLookAndFeel::bgHeader));
    g.drawHorizontalLine(26, 0.0f, (float)getWidth());
}

void AIPanel::resized()
{
    int y = 32;
    int labelW = 85;
    int ctrlW = getWidth() - labelW - 16;

    temperatureSlider.setBounds(labelW + 8, y, ctrlW, 22);
    y += 28;
    styleBox.setBounds(labelW + 8, y, ctrlW, 22);
    y += 28;
    variationsSlider.setBounds(labelW + 8, y, ctrlW, 22);
    y += 34;

    generateButton.setBounds(8, y, getWidth() - 16, 32);
    y += 38;
    connectButton.setBounds(8, y, getWidth() - 16, 24);
    y += 30;
    statusLabel.setBounds(8, y, getWidth() - 16, 20);
}

void AIPanel::timerCallback()
{
    // Sprint 48 LLL — 실제 HTTP 는 백그라운드. 메인은 결과 반영만.
    probeHealthAsync();
}

void AIPanel::probeHealthAsync()
{
    if (healthProbeInFlight.load()) return;
    healthProbeInFlight.store(true);

    juce::Component::SafePointer<AIPanel> safeThis(this);
    juce::Thread::launch([safeThis]()
    {
        // 경계: safeThis 이 dangling 이 아닌지는 MessageManager::callAsync 가
        // post 된 뒤 메인에서 확인. 여기서는 AIBridge 사본이 필요한데, AIBridge
        // 는 AIPanel 소유이므로 panel 생존 시에만 유효.
        bool ok = false;
        if (auto* p = safeThis.getComponent())
        {
            if (! p->shuttingDown.load())
                ok = p->aiBridge.checkHealth(500);
        }
        juce::MessageManager::callAsync([safeThis, ok]()
        {
            if (auto* p = safeThis.getComponent())
            {
                p->healthProbeInFlight.store(false);
                if (p->shuttingDown.load()) return;
                if (ok != p->serverConnected)
                {
                    p->serverConnected = ok;
                    p->statusLabel.setText(ok ? "Server Connected" : "Disconnected",
                                           juce::dontSendNotification);
                    p->statusLabel.setColour(juce::Label::textColourId,
                                              ok ? juce::Colours::limegreen : juce::Colours::grey);
                    p->generateButton.setEnabled(ok);
                }
            }
        });
    });
}

void AIPanel::onCheckServer()
{
    bool ok = aiBridge.checkHealth(2000);
    serverConnected = ok;
    statusLabel.setText(ok ? "Server Connected" : "Server not reachable",
                        juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId,
                          ok ? juce::Colours::limegreen : juce::Colours::red);
}

void AIPanel::onGenerate()
{
    if (!serverConnected) return;

    auto* track = (targetTrackId >= 0)
        ? audioEngine.getTrackModel().getTrack(targetTrackId)
        : (!audioEngine.getTrackModel().getTracks().empty()
            ? &audioEngine.getTrackModel().getTracks().front()
            : nullptr);

    if (track == nullptr || track->clips.empty())
    {
        statusLabel.setText("No MIDI clip to use as input", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, juce::Colours::orange);
        return;
    }

    auto inputSeq = track->flattenForPlayback();

    AIBridge::GenerateParams params;
    params.style = styleBox.getText();
    params.temperature = static_cast<float>(temperatureSlider.getValue());
    params.numVariations = static_cast<int>(variationsSlider.getValue());
    params.tempo = audioEngine.getTempo();

    statusLabel.setText("Generating...", juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, juce::Colours::yellow);

    aiBridge.requestVariationAsync(inputSeq, params,
        [this, trackPtr = track](AIBridge::Result result)
        {
            if (result.success)
            {
                // Add generated MIDI as a new clip on the same track.
                // Guard against the track's clip list being empty (the
                // only existing clip could have been deleted between the
                // request and this callback); default to beat 0 in that
                // case so the generated content still lands somewhere
                // sensible.
                MidiClip newClip;
                if (trackPtr != nullptr && ! trackPtr->clips.empty())
                {
                    const auto& last = trackPtr->clips.back();
                    newClip.startBeat = last.startBeat + last.lengthBeats;
                }
                else
                {
                    newClip.startBeat = 0.0;
                }
                newClip.sequence = std::move(result.generatedSequence);

                // Calculate clip length from sequence
                double maxBeat = 0;
                for (int i = 0; i < newClip.sequence.getNumEvents(); ++i)
                    maxBeat = juce::jmax(maxBeat,
                        newClip.sequence.getEventPointer(i)->message.getTimeStamp());
                newClip.lengthBeats = juce::jmax(4.0, std::ceil(maxBeat / 4.0) * 4.0);

                trackPtr->clips.push_back(std::move(newClip));

                statusLabel.setText("Generated!", juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::limegreen);
            }
            else
            {
                statusLabel.setText(result.errorMessage, juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::red);
            }
        });
}
