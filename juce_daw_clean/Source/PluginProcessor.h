/*
 * MidiGPT VST3 Plugin — PluginProcessor
 *
 * Clean room JUCE AudioProcessor implementation for the MidiGPT LLM.
 * This is a MIDI Effect plugin: MIDI in → MidiGPT LLM → MIDI out.
 *
 * Sprint 32 (2026-04-17) added:
 *   WW2 host-tempo-aware MIDI capture into capturedInput (beat-based)
 *   WW3 requestVariation() wired to AIBridge HTTP client
 *   WW4 pendingGenerated queue injected back into processBlock MIDI out
 *   WW5 error reporting to editor via listener callback
 *   WW6 getState/setState persists last generated sequence (not just params)
 *
 * References (public sources only):
 *   - JUCE AudioProcessor API docs: https://docs.juce.com/master/classAudioProcessor.html
 *   - JUCE AudioPlayHead::PositionInfo: https://docs.juce.com/master/classAudioPlayHead.html
 *   - VST3 SDK public docs: https://steinbergmedia.github.io/vst3_dev_portal/
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <atomic>
#include <functional>
#include <memory>
#include "AI/AIBridge.h"

class MidiGPTProcessor : public juce::AudioProcessor
{
public:
    MidiGPTProcessor();
    ~MidiGPTProcessor() override;

    // -------------------------------------------------------------------------
    // AudioProcessor lifecycle
    // -------------------------------------------------------------------------
    void prepareToPlay (double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    void processBlock (juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    bool isBusesLayoutSupported (const BusesLayout& layouts) const override;

    // -------------------------------------------------------------------------
    // Plugin info
    // -------------------------------------------------------------------------
    const juce::String getName() const override { return "MidiGPT"; }
    bool acceptsMidi() const override  { return true; }
    bool producesMidi() const override { return true; }
    bool isMidiEffect() const override { return true; }
    double getTailLengthSeconds() const override { return 0.0; }

    // -------------------------------------------------------------------------
    // Program / preset handling
    // -------------------------------------------------------------------------
    int getNumPrograms() override        { return 1; }
    int getCurrentProgram() override     { return 0; }
    void setCurrentProgram (int) override {}
    const juce::String getProgramName (int) override { return {}; }
    void changeProgramName (int, const juce::String&) override {}

    // -------------------------------------------------------------------------
    // State save / restore (host saves these into the project file)
    // -------------------------------------------------------------------------
    void getStateInformation (juce::MemoryBlock& destData) override;
    void setStateInformation (const void* data, int sizeInBytes) override;

    // -------------------------------------------------------------------------
    // Editor
    // -------------------------------------------------------------------------
    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    // =========================================================================
    // MidiGPT-specific API (called from editor)
    // =========================================================================
    /** Status reported back to the editor for UI feedback. */
    enum class GenerationStatus
    {
        Idle,
        NoInputCaptured,
        InFlight,
        Ready,
        Error
    };

    /** Called on the message thread whenever generation status changes. */
    using StatusCallback = std::function<void (GenerationStatus, juce::String message)>;

    void setStatusCallback (StatusCallback cb) { statusCallback = std::move (cb); }

    /** Trigger a variation generation request against the server. Non-blocking.
        Uses the MIDI accumulated in capturedInput as the prompt. Reports
        progress through the status callback. Safe to call from the UI thread. */
    void requestVariation();

    /** Clear the captured-input buffer (e.g. before a fresh take). */
    void clearCapturedInput();

    /** Read-only view of the last generated sequence (for debug / export). */
    const juce::MidiMessageSequence& getLastGenerated() const { return lastGenerated; }

    /** Returns the captured input size (for editor "notes captured" display). */
    int getCapturedNoteCount() const { return capturedNoteCount.load(); }

    /** Thread-safe copy of the captured-input sequence (for editor visualisation).
        Takes captureLock, so it's safe to call concurrently with processBlock. */
    juce::MidiMessageSequence getCapturedInputCopy() const
    {
        const juce::ScopedLock lock (captureLock);
        return capturedInput;   // MidiMessageSequence is copyable
    }

    // =========================================================================
    // Sprint 34 YY5 — load an external MIDI sequence as the current prompt
    // =========================================================================
    /** Replace the captured-input buffer with an externally-supplied sequence
        (e.g. drag-and-dropped .mid file). Timestamps should already be in
        beats. Called on the message thread. */
    void loadAsCapturedInput (const juce::MidiMessageSequence& seq);

    // =========================================================================
    // Sprint 34 YY4 — generation-result undo/redo history
    // =========================================================================
    /** Push the previous lastGenerated onto history before replacing it.
        Keeps at most ``kHistoryLimit`` entries. Called internally on
        successful generation. */
    void pushHistory (juce::MidiMessageSequence replacedGeneration);

    /** Restore a previous generation. Returns true if an older entry was
        available. Safe to call from the message thread. */
    bool undoGeneration();
    bool redoGeneration();
    int  undoDepth() const { return static_cast<int> (undoStack.size()); }
    int  redoDepth() const { return static_cast<int> (redoStack.size()); }

    // Public parameter tree (exposed to host automation)
    juce::AudioProcessorValueTreeState parameters;

private:
    static juce::AudioProcessorValueTreeState::ParameterLayout createParameterLayout();

    // ---- AI bridge (HTTP client to inference_server.py) ---------------------
    std::unique_ptr<AIBridge> aiBridge;

    // ---- Host-position tracking ---------------------------------------------
    // Samples-per-beat at the current sample rate; refreshed each block
    // from the host play-head (when available). Used to convert audio-sample
    // time to beat-time for capture + playback scheduling.
    double currentSampleRate { 44100.0 };
    double currentBpm        { 120.0 };
    double currentBeatAtBlockStart { 0.0 };   // host play position
    std::atomic<bool> hostWasPlaying { false };

    // ---- Captured-input buffer (from host MIDI in) --------------------------
    // CriticalSection because the UI thread reads it for serialisation while
    // the audio thread writes into it. Kept short: one lock per block start.
    // Mutable so const accessors (e.g. getCapturedInputCopy) can still lock.
    mutable juce::CriticalSection captureLock;
    juce::MidiMessageSequence capturedInput;
    std::atomic<int> capturedNoteCount { 0 };

    // ---- Pending generated events to inject into MIDI out -------------------
    // Written by the message-thread callback (from AIBridge) under
    // scheduledLock, read by the audio thread every block.
    juce::CriticalSection scheduledLock;
    juce::MidiMessageSequence scheduledOutput;
    double scheduledStartBeat { 0.0 };       // beat-time at which to begin playback
    int    scheduledNextIndex { 0 };         // monotonic cursor into scheduledOutput
    std::atomic<bool> hasScheduledPlayback { false };

    // ---- Last finished generation (persisted via getStateInformation) -------
    juce::MidiMessageSequence lastGenerated;

    // ---- YY4 Undo / redo history of lastGenerated ---------------------------
    // History is message-thread only — push happens in the AIBridge result
    // callback and undo is driven by the editor. No audio-thread access.
    static constexpr int kHistoryLimit = 10;
    std::vector<juce::MidiMessageSequence> undoStack;
    std::vector<juce::MidiMessageSequence> redoStack;

    // ---- Editor feedback ----------------------------------------------------
    StatusCallback statusCallback;

    void fireStatus (GenerationStatus st, juce::String msg);
    void installGeneratedSequence (juce::MidiMessageSequence seq);   // shared by generate + undo

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (MidiGPTProcessor)
};
