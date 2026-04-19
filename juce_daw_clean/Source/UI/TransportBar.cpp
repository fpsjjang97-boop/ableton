/*
 * MidiGPT DAW - TransportBar.cpp
 */

#include "TransportBar.h"

TransportBar::TransportBar(AudioEngine& engine)
    : audioEngine(engine)
{
    // Sprint 47 KKK2 — 툴팁 일괄 (TooltipWindow 가 MainWindow 레벨에서 active 하면
    // 자동 표시. 신규 위젯 추가 시 setTooltip() 호출로 사용자 도움말 통일).
    rewindButton.setTooltip("맨 앞으로 (Home)");
    playButton.setTooltip("재생 (Space). 정지 상태에서는 맨 앞에서 시작");
    stopButton.setTooltip("정지 + 맨 앞으로 (Ctrl+.)");
    recordButton.setTooltip("녹음 arm — 첫 트랙에 1 bar count-in 후 녹음 (R)");
    loopButton.setTooltip("루프 토글 (Enter)");
    metroButton.setTooltip("메트로놈 on/off (Ctrl+M)");
    tempoSlider.setTooltip("BPM — 20~300, 0.1 단위");
    positionLabel.setTooltip("현재 위치 (bar.beat.tick)");
    timeLabel.setTooltip("경과 시간 (mm:ss.ms)");
    keySelector.setTooltip("키 — 생성 시 harmonic 제약과 step seq 스케일 기반");
    scaleSelector.setTooltip("스케일 — major/minor/mixolydian 등");
    snapSelector.setTooltip("퀀타이즈 그리드");
    countInSelector.setTooltip("녹음 시작 전 대기 마디 수 (Ctrl+Shift+M 로 순환)");
    tapButton.setTooltip("두 번 이상 탭해서 BPM 감지");

    rewindButton.onClick  = [this] { audioEngine.rewind(); };
    addAndMakeVisible(rewindButton);

    playButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xFF2E7D32));
    playButton.onClick = [this] {
        if (!audioEngine.isPlaying())
        {
            audioEngine.rewind();  // Always start from beginning
            audioEngine.play();
        }
    };
    addAndMakeVisible(playButton);

    stopButton.onClick = [this] { audioEngine.stop(); };
    addAndMakeVisible(stopButton);

    recordButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xFFC62828));
    recordButton.setClickingTogglesState(true);
    recordButton.onClick = [this] {
        auto& tracks = audioEngine.getTrackModel().getTracks();
        if (tracks.empty()) return;
        auto& t = tracks.front();
        t.armed = recordButton.getToggleState();
        audioEngine.setRecordingTargetTrack(recordButton.getToggleState() ? t.id : -1);
        // Y5 — arm record implies 1-bar count-in by default
        audioEngine.setCountInBars(recordButton.getToggleState() ? 1 : 0);
        if (recordButton.getToggleState() && ! audioEngine.isPlaying())
            audioEngine.play();
    };
    addAndMakeVisible(recordButton);

    loopButton.setClickingTogglesState(true);
    loopButton.onClick = [this] {
        audioEngine.getMidiEngine().setLooping(loopButton.getToggleState());
    };
    addAndMakeVisible(loopButton);

    // Z3 — count-in selector
    countInSelector.addItem("No count-in",  1);
    countInSelector.addItem("1 bar pre",    2);
    countInSelector.addItem("2 bars pre",   3);
    countInSelector.addItem("4 bars pre",   5);
    countInSelector.setSelectedId(2, juce::dontSendNotification);
    countInSelector.onChange = [this] {
        const int id = countInSelector.getSelectedId();
        const int bars = (id == 1 ? 0 : id == 2 ? 1 : id == 3 ? 2 : 4);
        audioEngine.setCountInBars(bars);
    };
    addAndMakeVisible(countInSelector);

    metroButton.setClickingTogglesState(true);
    metroButton.onClick = [this] {
        audioEngine.setMetronome(metroButton.getToggleState());
    };
    addAndMakeVisible(metroButton);

    // BPM
    tempoSlider.setSliderStyle(juce::Slider::IncDecButtons);
    tempoSlider.setRange(20, 300, 0.1);
    tempoSlider.setValue(120.0);
    tempoSlider.setTextBoxStyle(juce::Slider::TextBoxLeft, false, 48, 20);
    tempoSlider.onValueChange = [this] { audioEngine.setTempo(tempoSlider.getValue()); };
    addAndMakeVisible(tempoSlider);

    // Position
    positionLabel.setFont(juce::Font(juce::Font::getDefaultMonospacedFontName(), 14.0f, juce::Font::bold));
    positionLabel.setColour(juce::Label::textColourId, juce::Colour(0xFFE0E0E0));
    positionLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(positionLabel);

    timeLabel.setFont(juce::Font(juce::Font::getDefaultMonospacedFontName(), 12.0f, 0));
    timeLabel.setColour(juce::Label::textColourId, juce::Colour(0xFF909090));
    timeLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(timeLabel);

    // Key selector
    keySelector.addItemList({"C","C#","D","D#","E","F","F#","G","G#","A","A#","B"}, 1);
    keySelector.setSelectedId(1);
    addAndMakeVisible(keySelector);

    // Scale selector
    scaleSelector.addItemList({"Major","Minor","Dorian","Mixolydian","Pentatonic",
                               "Blues","Harmonic Min","Chromatic"}, 1);
    scaleSelector.setSelectedId(1);
    addAndMakeVisible(scaleSelector);

    // Snap selector
    snapSelector.addItemList({"Off","1/1","1/2","1/4","1/8","1/16","1/32"}, 1);
    snapSelector.setSelectedId(6); // 1/16 default
    addAndMakeVisible(snapSelector);

    // OO5 — click position label to toggle format
    positionLabel.addMouseListener(this, false);
    timeLabel.addMouseListener(this, false);

    // FF6 — tempo tap button
    tapButton.onClick = [this] { handleTap(); };
    addAndMakeVisible(tapButton);

    startTimerHz(30);
}

// FF6 — tempo tap: average intervals of last 4-8 taps
void TransportBar::handleTap()
{
    double now = juce::Time::getMillisecondCounterHiRes() / 1000.0;
    tapTimes.push_back(now);

    // Expire taps older than 3 seconds
    while (tapTimes.size() > 1 && (now - tapTimes.front()) > 3.0)
        tapTimes.erase(tapTimes.begin());

    if (tapTimes.size() >= 2)
    {
        double totalInterval = tapTimes.back() - tapTimes.front();
        double avgInterval = totalInterval / (double)(tapTimes.size() - 1);
        if (avgInterval > 0.0)
        {
            double bpm = 60.0 / avgInterval;
            bpm = juce::jlimit(20.0, 300.0, bpm);
            tempoSlider.setValue(bpm);
            audioEngine.setTempo(bpm);
        }
    }
}

void TransportBar::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xFF1C1C1C));

    // Top metallic sheen
    g.setGradientFill(juce::ColourGradient(
        juce::Colours::white.withAlpha(0.02f), 0, 0,
        juce::Colours::transparentWhite, 0, (float)getHeight(), false));
    g.fillRect(getLocalBounds());

    // Bottom border
    g.setColour(juce::Colour(0xFF2A2A2A));
    g.drawHorizontalLine(getHeight() - 1, 0.0f, (float)getWidth());
}

void TransportBar::resized()
{
    auto area = getLocalBounds().reduced(4, 2);

    tempoSlider.setBounds(area.removeFromLeft(100));
    area.removeFromLeft(6);

    rewindButton.setBounds(area.removeFromLeft(36));
    area.removeFromLeft(2);
    playButton.setBounds(area.removeFromLeft(44));
    area.removeFromLeft(2);
    stopButton.setBounds(area.removeFromLeft(40));
    area.removeFromLeft(2);
    recordButton.setBounds(area.removeFromLeft(36));

    area.removeFromLeft(12);

    positionLabel.setBounds(area.removeFromLeft(80));
    timeLabel.setBounds(area.removeFromLeft(70));

    area.removeFromLeft(12);

    keySelector.setBounds(area.removeFromLeft(52));
    area.removeFromLeft(2);
    scaleSelector.setBounds(area.removeFromLeft(100));

    area.removeFromLeft(8);

    snapSelector.setBounds(area.removeFromLeft(60));

    area.removeFromLeft(8);

    loopButton.setBounds(area.removeFromLeft(44));
    area.removeFromLeft(2);
    metroButton.setBounds(area.removeFromLeft(48));
    area.removeFromLeft(6);
    countInSelector.setBounds(area.removeFromLeft(80));   // Z3
    area.removeFromLeft(4);
    tapButton.setBounds(area.removeFromLeft(36)); // FF6
}

// OO5 — toggle time display format on click
void TransportBar::mouseDown(const juce::MouseEvent& e)
{
    auto posArea = positionLabel.getBounds().expanded(4);
    auto timeArea = timeLabel.getBounds().expanded(4);
    if (posArea.contains(e.getPosition()) || timeArea.contains(e.getPosition()))
        showTimeFormat = ! showTimeFormat;
}

// SS2 — double-click position label → direct beat input
void TransportBar::mouseDoubleClick(const juce::MouseEvent& e)
{
    auto posArea = positionLabel.getBounds().expanded(4);
    if (posArea.contains(e.getPosition()))
    {
        auto* aw = new juce::AlertWindow("Go to Position", "Enter beat number:",
                                          juce::MessageBoxIconType::NoIcon);
        aw->addTextEditor("beat", juce::String(audioEngine.getPositionBeats(), 2));
        aw->addButton("Go", 1);
        aw->addButton("Cancel", 0);
        aw->enterModalState(true, juce::ModalCallbackFunction::create(
            [this, aw](int r) {
                if (r == 1)
                {
                    double beat = juce::jmax(0.0, aw->getTextEditorContents("beat").getDoubleValue());
                    audioEngine.getMidiEngine().setPositionBeats(beat);
                }
                delete aw;
            }), false);
    }
}

void TransportBar::timerCallback()
{
    double beats = audioEngine.getPositionBeats();

    // KK4 — time-sig aware bar/beat calculation
    auto& me = audioEngine.getMidiEngine();
    int bar = 1;
    double remaining = beats;
    double pos = 0.0;
    for (int safety = 0; safety < 10000 && remaining > 0.001; ++safety)
    {
        auto ts = me.timeSigAt(pos);
        double barLen = (ts.den > 0) ? (double)ts.num * (4.0 / (double)ts.den) : 4.0; // D2
        if (remaining < barLen) break;
        remaining -= barLen;
        pos += barLen;
        ++bar;
    }
    auto curTs = me.timeSigAt(pos);
    double beatUnit = 4.0 / (double)curTs.den;
    int beat = (int)(remaining / beatUnit) + 1;
    int tick = (int)(std::fmod(remaining, beatUnit) / beatUnit * 480.0);
    double seconds = beats * 60.0 / audioEngine.getTempo();
    int mins = static_cast<int>(seconds) / 60;
    int secs = static_cast<int>(seconds) % 60;
    int ms   = static_cast<int>(std::fmod(seconds, 1.0) * 1000.0);

    // OO5 — swap primary/secondary display based on format toggle
    if (showTimeFormat)
    {
        positionLabel.setText(juce::String::formatted("%d:%02d.%03d", mins, secs, ms),
                              juce::dontSendNotification);
        timeLabel.setText(juce::String::formatted("%d.%d.%03d", bar, beat, tick),
                          juce::dontSendNotification);
    }
    else
    {
        positionLabel.setText(juce::String::formatted("%d.%d.%03d", bar, beat, tick),
                              juce::dontSendNotification);
        timeLabel.setText(juce::String::formatted("%d:%02d.%03d", mins, secs, ms),
                          juce::dontSendNotification);
    }

    // Update play button colour
    playButton.setColour(juce::TextButton::buttonColourId,
                         audioEngine.isPlaying() ? juce::Colour(0xFF4CAF50)
                                                 : juce::Colour(0xFF2E7D32));

    // UU4 — sync tempo slider to current effective tempo
    {
        double effTempo = audioEngine.getMidiEngine().tempoAt(audioEngine.getPositionBeats());
        if (! tempoSlider.isMouseButtonDown()
            && std::abs(tempoSlider.getValue() - effTempo) > 0.2)
            tempoSlider.setValue(effTempo, juce::dontSendNotification);
    }

    // RR4 — count-in visual: flash record button during pre-roll
    if (audioEngine.getCountInBars() > 0 && ! audioEngine.isPlaying()
        && recordButton.getToggleState())
    {
        bool flash = ((int)(juce::Time::getMillisecondCounter() / 250) % 2) == 0;
        recordButton.setColour(juce::TextButton::buttonColourId,
            flash ? juce::Colour(0xFFFF5722) : juce::Colour(0xFFC62828));
    }
    else
    {
        recordButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xFFC62828));
    }
}
