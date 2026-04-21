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

    // 2026-04-21 결함 #2 — 생성 단위 UI.
    taskBox.addItem("Variation",         1);
    taskBox.addItem("Continuation",      2);
    taskBox.addItem("Bar infill",        3);
    taskBox.addItem("Track completion",  4);
    taskBox.setSelectedId(1);
    taskBox.setTooltip("생성 작업 유형. 긴 이어쓰기(variation/continuation)와 "
                        "부분 보완(infill/completion) 구분.");
    addAndMakeVisible(taskBox);
    taskLabel.attachToComponent(&taskBox, true);
    addAndMakeVisible(taskLabel);

    startBarSlider.setSliderStyle(juce::Slider::IncDecButtons);
    startBarSlider.setRange(0, 63, 1);
    startBarSlider.setValue(0);
    startBarSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 40, 20);
    startBarSlider.setTooltip("생성 시작 bar (0-based). bar_infill / "
                               "track_completion 에서 사용.");
    addAndMakeVisible(startBarSlider);
    startBarLabel.attachToComponent(&startBarSlider, true);
    addAndMakeVisible(startBarLabel);

    endBarSlider.setSliderStyle(juce::Slider::IncDecButtons);
    endBarSlider.setRange(1, 64, 1);
    endBarSlider.setValue(8);
    endBarSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 40, 20);
    endBarSlider.setTooltip("생성 끝 bar (exclusive). end - start ≤ 8 권장.");
    addAndMakeVisible(endBarSlider);
    endBarLabel.attachToComponent(&endBarSlider, true);
    addAndMakeVisible(endBarLabel);

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
    y += 28;
    // 2026-04-21 결함 #2 — task + bar range 위젯.
    taskBox.setBounds(labelW + 8, y, ctrlW, 22);
    y += 28;
    startBarSlider.setBounds(labelW + 8, y, ctrlW, 22);
    y += 28;
    endBarSlider.setBounds(labelW + 8, y, ctrlW, 22);
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

    // 2026-04-21 결함 #2 — task + bar range 전달. taskBox selection ID
    // 에 맞춰 서버 측 task 문자열. 서버가 모르는 값이면 GenerateParams
    // 기본(backward-compat) 로 폴백.
    switch (taskBox.getSelectedId())
    {
        case 2: params.task = "continuation";      break;
        case 3: params.task = "bar_infill";        break;
        case 4: params.task = "track_completion";  break;
        case 1:
        default: params.task = "variation";        break;
    }
    params.startBar = (int) startBarSlider.getValue();
    params.endBar   = juce::jmax (params.startBar + 1,
                                   (int) endBarSlider.getValue());
    // min_bars 는 end-start 로 유추해 EOS 가드를 task 범위와 일치시킴.
    params.minBars = juce::jmax (1, params.endBar - params.startBar);

    statusLabel.setText("Generating...", juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, juce::Colours::yellow);

    aiBridge.requestVariationAsync(inputSeq, params,
        [this, trackPtr = track, task = params.task,
         startBar = params.startBar, endBar = params.endBar]
        (AIBridge::Result result)
        {
            if (! result.success)
            {
                statusLabel.setText(result.errorMessage, juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::red);
                return;
            }
            if (trackPtr == nullptr)
            {
                statusLabel.setText("Target track disappeared", juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::orange);
                return;
            }

            // Sprint UUU — task-specific placement (partner review §20-2).
            // bar_infill / track_completion replace the selected bar range
            // on an existing clip; continuation / variation still append
            // a new clip (since continuation is semantically "what comes
            // after"). This matches the product shape the partner wants:
            // a DAW composer cursor that edits the selected region, not
            // a tape recorder that adds to the end.
            const double beatsPerBar = 4.0; // meter-aware variant in WWW
            const double rangeStart = startBar * beatsPerBar;
            const double rangeEnd   = juce::jmax(rangeStart + beatsPerBar,
                                                  endBar * beatsPerBar);

            const bool inPlace = (task == "bar_infill"
                                   || task == "track_completion");

            if (inPlace && ! trackPtr->clips.empty())
            {
                // Find the clip that overlaps the target range (first hit).
                MidiClip* host = nullptr;
                for (auto& c : trackPtr->clips)
                {
                    if (rangeStart < c.startBeat + c.lengthBeats
                        && rangeEnd > c.startBeat)
                    { host = &c; break; }
                }
                if (host == nullptr) host = &trackPtr->clips.front();

                // Delete events inside the range (clip-relative coords).
                const double relStart = rangeStart - host->startBeat;
                const double relEnd   = rangeEnd   - host->startBeat;
                for (int i = host->sequence.getNumEvents() - 1; i >= 0; --i)
                {
                    const double t = host->sequence.getEventPointer(i)
                                         ->message.getTimeStamp();
                    if (t >= relStart && t < relEnd)
                        host->sequence.deleteEvent(i, true);
                }

                // Splice generated events into the cleared window. The
                // server returns events timestamped from 0; shift by
                // relStart so they land inside the range.
                for (int i = 0; i < result.generatedSequence.getNumEvents(); ++i)
                {
                    auto m = result.generatedSequence.getEventPointer(i)->message;
                    m.setTimeStamp(m.getTimeStamp() + relStart);
                    host->sequence.addEvent(m);
                }
                host->sequence.updateMatchedPairs();
                host->sequence.sort();

                // Extend clip length if the splice overruns.
                host->lengthBeats = juce::jmax(host->lengthBeats, relEnd);

                statusLabel.setText("In-place generate OK ("
                                     + juce::String((int) (endBar - startBar))
                                     + " bars)",
                                     juce::dontSendNotification);
                statusLabel.setColour(juce::Label::textColourId, juce::Colours::limegreen);
                return;
            }

            // Non-infill tasks keep the historical "append" behavior.
            MidiClip newClip;
            if (! trackPtr->clips.empty())
            {
                const auto& last = trackPtr->clips.back();
                newClip.startBeat = last.startBeat + last.lengthBeats;
            }
            newClip.sequence = std::move(result.generatedSequence);

            double maxBeat = 0;
            for (int i = 0; i < newClip.sequence.getNumEvents(); ++i)
                maxBeat = juce::jmax(maxBeat,
                    newClip.sequence.getEventPointer(i)->message.getTimeStamp());
            newClip.lengthBeats = juce::jmax(4.0, std::ceil(maxBeat / 4.0) * 4.0);

            trackPtr->clips.push_back(std::move(newClip));

            statusLabel.setText("Generated!", juce::dontSendNotification);
            statusLabel.setColour(juce::Label::textColourId, juce::Colours::limegreen);
        });
}
