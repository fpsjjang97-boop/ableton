/*
 * MidiGPT VST3 Plugin — AIBridge
 *
 * HTTP client that talks to the local MidiGPT inference server
 * (``midigpt/inference_server.py``). Keeps the audio thread free by
 * running network I/O on a background thread.
 *
 * Protocol:
 *   Server: FastAPI on http://127.0.0.1:8765
 *   Endpoints:
 *     GET  /health            → {"status": "ok", "model_loaded": bool}
 *     GET  /status            → model status
 *     POST /load_lora         → JSON body { "name": "jazz" }
 *     POST /generate_json     → JSON body with base64 MIDI + params
 *                                (clean-room C++ impl avoids multipart)
 *
 * References (public sources only):
 *   - JUCE URL class docs:    https://docs.juce.com/master/classURL.html
 *   - JUCE WebInputStream:    https://docs.juce.com/master/classWebInputStream.html
 *   - JUCE Thread class:      https://docs.juce.com/master/classThread.html
 *   - JUCE Base64 helpers:    https://docs.juce.com/master/classBase64.html
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#pragma once

#include <juce_core/juce_core.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include <functional>
#include <memory>

class AIBridge
{
public:
    //==========================================================================
    // Parameters passed to the server on each generation request
    //==========================================================================
    struct GenerateParams
    {
        juce::String style        { "base" };      // LoRA adapter name
        juce::String key          { "C" };         // musical key
        juce::String section      { "chorus" };    // song section hint
        double       tempo        { 120.0 };       // BPM
        float        temperature  { 0.9f };        // sampling temperature
        int          numVariations{ 1 };           // num_return_sequences
        int          maxTokens    { 1024 };
        int          minNewTokens { 256 };         // EOS suppression floor
        float        repetitionPenalty  { 1.1f };
        int          noRepeatNgramSize  { 4 };
    };

    //==========================================================================
    // Result delivered to the caller's callback
    //==========================================================================
    struct Result
    {
        bool                      success { false };
        juce::MidiMessageSequence generatedSequence;
        juce::String              errorMessage;
        int                       httpStatus { 0 };
    };

    using ResultCallback = std::function<void (Result)>;

    //==========================================================================
    AIBridge (juce::URL serverUrl = juce::URL ("http://127.0.0.1:8765"));
    ~AIBridge();

    //==========================================================================
    /** Synchronous health check. Returns true if server is reachable and
        has a model loaded. Uses a short timeout so it does not block
        the UI for long. Safe to call from the message thread. */
    bool checkHealth (int timeoutMs = 2000);

    /** Get server status as a juce::var (parsed JSON). */
    juce::var getStatus (int timeoutMs = 2000);

    /** Synchronously load a LoRA adapter on the server. Returns true
        on success. */
    bool loadLora (const juce::String& name, int timeoutMs = 10000);

    /** Asynchronously load a LoRA adapter. The callback receives (success,
        errorMessage) on the message thread.  Prefer this over the sync
        variant from UI code — LoRA load is ~1-5s and blocking the UI
        stalls the whole plugin editor.  Sprint 33 XX4 addition. */
    using LoraCallback = std::function<void (bool success, juce::String errorMessage)>;
    void loadLoraAsync (const juce::String& name, LoraCallback callback);

    /** Asynchronously request a variation. The callback is invoked on
        the message thread when the result is ready (success or failure).

        The input sequence is serialised to a Standard MIDI File byte
        stream, base64-encoded, and sent as JSON to /generate_json on
        the local server. */
    void requestVariationAsync (const juce::MidiMessageSequence& input,
                                const GenerateParams& params,
                                ResultCallback callback);

    /** Cancel any in-flight asynchronous request. Safe to call from
        the message thread. */
    void cancelPendingRequests();

private:
    //==========================================================================
    class AsyncWorker;                 // juce::Thread subclass (see .cpp)

    juce::URL serverUrl;
    std::unique_ptr<AsyncWorker> worker;

    /** Build the /generate_json request body. Exposed for testing. */
    static juce::String buildGenerateJsonBody (const juce::MemoryBlock& midiBytes,
                                               const GenerateParams& params);

    /** Serialise a MidiMessageSequence to a Standard MIDI File byte block.
        Uses juce::MidiFile under the hood. */
    static juce::MemoryBlock sequenceToMidiBytes (const juce::MidiMessageSequence& seq,
                                                  double tempo = 120.0);

    /** Parse a Standard MIDI File byte block back into a sequence. */
    static juce::MidiMessageSequence midiBytesToSequence (const juce::MemoryBlock& bytes);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AIBridge)
};
