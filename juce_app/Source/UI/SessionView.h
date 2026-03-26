#pragma once
#include <JuceHeader.h>
#include "LookAndFeel.h"

//==============================================================================
// ClipSlot - A single clip slot in the session grid
//==============================================================================
class ClipSlot : public juce::Component
{
public:
    ClipSlot (int trackIndex, int sceneIndex);

    void paint (juce::Graphics& g) override;
    void mouseDown (const juce::MouseEvent& e) override;
    void mouseDoubleClick (const juce::MouseEvent& e) override;

    void setClipName (const juce::String& name);
    void setPlaying (bool isPlaying);
    void setSelected (bool selected);
    void setClipColour (juce::Colour colour);
    bool hasClip() const { return clipName.isNotEmpty(); }

    std::function<void (int, int)>          onClipTriggered;  // track, scene
    std::function<void (int, int)>          onClipDoubleClick;
    std::function<void (int, int, bool)>    onClipSelected;

private:
    int track, scene;
    juce::String clipName;
    juce::Colour colour { MetallicLookAndFeel::clipColour };
    bool isPlaying = false;
    bool selected  = false;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (ClipSlot)
};

//==============================================================================
// TrackHeader - Track name, colour, M/S buttons
//==============================================================================
class TrackHeader : public juce::Component
{
public:
    TrackHeader (int trackIndex, const juce::String& name, juce::Colour colour);

    void paint (juce::Graphics& g) override;
    void resized() override;
    void mouseDoubleClick (const juce::MouseEvent& e) override;

    void setTrackName (const juce::String& name);
    void setTrackColour (juce::Colour colour);
    void setMuted (bool muted);
    void setSoloed (bool soloed);

    std::function<void (int, bool)> onMuteChanged;
    std::function<void (int, bool)> onSoloChanged;
    std::function<void (int, const juce::String&)> onNameChanged;

private:
    int trackIdx;
    juce::String trackName;
    juce::Colour trackColour;
    juce::TextButton muteButton { "M" };
    juce::TextButton soloButton { "S" };
    juce::Label nameLabel;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (TrackHeader)
};

//==============================================================================
// MixerStrip - Per-track volume fader, pan knob, M/S
//==============================================================================
class MixerStrip : public juce::Component
{
public:
    MixerStrip (int trackIndex, const juce::String& name, juce::Colour colour);

    void paint (juce::Graphics& g) override;
    void resized() override;
    void setLevel (float levelL, float levelR);

    std::function<void (int, float)> onVolumeChanged;
    std::function<void (int, float)> onPanChanged;

private:
    int trackIdx;
    juce::String trackName;
    juce::Colour trackColour;
    juce::Slider volumeSlider;
    juce::Slider panKnob;
    juce::TextButton muteButton { "M" };
    juce::TextButton soloButton { "S" };
    juce::Label nameLabel;
    float meterL = 0.0f, meterR = 0.0f;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MixerStrip)
};

//==============================================================================
// SessionView - Main session view with clip grid, headers, mixer
//==============================================================================
class SessionView : public juce::Component,
                    public juce::Timer
{
public:
    SessionView();
    ~SessionView() override;

    void paint (juce::Graphics& g) override;
    void resized() override;
    void timerCallback() override;

    // ── Track management ────────────────────────────────────────────────────
    void addTrack (const juce::String& name, juce::Colour colour);
    void removeTrack (int index);
    int  getNumTracks() const { return trackHeaders.size(); }

    // ── Clip management ─────────────────────────────────────────────────────
    void setClip (int track, int scene, const juce::String& name);
    void clearClip (int track, int scene);
    void setClipPlaying (int track, int scene, bool playing);
    void setClipState (int trackIdx, int sceneIdx, bool hasClip);
    void clearTracks();

    // ── Scene management ────────────────────────────────────────────────────
    int  getNumScenes() const { return numScenes; }
    void setNumScenes (int scenes);

    // ── Callbacks ───────────────────────────────────────────────────────────
    std::function<void (int, int)>    onClipTriggered;
    std::function<void (int, int)>    onClipDoubleClicked;
    std::function<void (int)>         onSceneLaunched;
    std::function<void (int, float)>  onVolumeChanged;
    std::function<void (int, float)>  onPanChanged;
    std::function<void (int, bool)>   onTrackMuteToggled;
    std::function<void (int, bool)>   onTrackSoloToggled;

private:
    static constexpr int numScenes      = 8;
    static constexpr int trackWidth     = 100;
    static constexpr int headerHeight   = 40;
    static constexpr int slotHeight     = 28;
    static constexpr int mixerHeight    = 120;
    static constexpr int sceneColWidth  = 30;

    juce::OwnedArray<TrackHeader>  trackHeaders;
    juce::OwnedArray<MixerStrip>   mixerStrips;
    juce::OwnedArray<ClipSlot>     clipSlots;
    juce::OwnedArray<juce::TextButton> sceneLaunchButtons;

    juce::Viewport gridViewport;
    juce::Component gridContainer;
    juce::Component headerContainer;
    juce::Component mixerContainer;

    void rebuildLayout();
    ClipSlot* getSlot (int track, int scene);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (SessionView)
};
