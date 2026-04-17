/*
 * MidiGPT VST3 Plugin — AIBridge.cpp
 *
 * Implementation of the HTTP client to the local MidiGPT inference
 * server. Design goals:
 *   - Audio thread never blocks on network
 *   - UI thread never blocks on network for > 2s (health check only)
 *   - Async variation requests run on a dedicated worker thread
 *   - Server protocol is plain JSON with base64 MIDI bytes — no
 *     multipart/form-data complexity on the C++ side
 *
 * References (public sources only):
 *   - JUCE URL + WebInputStream tutorial:
 *     https://juce.com/learn/tutorials/juce-tutorial-web-downloads/
 *   - JUCE MidiFile class docs:
 *     https://docs.juce.com/master/classMidiFile.html
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include "AIBridge.h"
#include <juce_audio_formats/juce_audio_formats.h>
#include <juce_events/juce_events.h>

//==============================================================================
// AsyncWorker — background thread that processes one generation request
//==============================================================================
class AIBridge::AsyncWorker  : public juce::Thread
{
public:
    AsyncWorker (AIBridge& ownerRef)
        : juce::Thread ("MidiGPT-AIBridge"), owner (ownerRef) {}

    ~AsyncWorker() override
    {
        stopThread (3000);
    }

    void startRequest (juce::MemoryBlock midiBytes,
                       GenerateParams params,
                       ResultCallback cb)
    {
        const juce::ScopedLock lock (mutex);
        pendingMidiBytes = std::move (midiBytes);
        pendingParams = std::move (params);
        pendingCallback = std::move (cb);
        hasPending = true;
        notify();                 // wake the run() loop
        if (! isThreadRunning())
            startThread();
    }

    void run() override
    {
        while (! threadShouldExit())
        {
            juce::MemoryBlock midiBytes;
            GenerateParams params;
            ResultCallback callback;

            {
                const juce::ScopedLock lock (mutex);
                if (! hasPending)
                {
                    // Nothing to do; wait for a signal or shutdown.
                    mutex.exit();
                    wait (1000);
                    mutex.enter();
                    continue;
                }
                midiBytes = std::move (pendingMidiBytes);
                params = std::move (pendingParams);
                callback = std::move (pendingCallback);
                hasPending = false;
            }

            Result result = performGenerate (midiBytes, params);

            // Hop back to the message thread so UI updates are safe.
            if (callback)
            {
                juce::MessageManager::callAsync (
                    [cb = std::move (callback), result = std::move (result)]() mutable
                    {
                        cb (std::move (result));
                    });
            }
        }
    }

private:
    Result performGenerate (const juce::MemoryBlock& midiBytes,
                            const GenerateParams& params)
    {
        Result r;

        auto body = AIBridge::buildGenerateJsonBody (midiBytes, params);

        auto url = owner.serverUrl.getChildURL ("generate_json")
                                  .withPOSTData (body);

        auto options = juce::URL::InputStreamOptions (
                            juce::URL::ParameterHandling::inPostData)
                       .withExtraHeaders ("Content-Type: application/json\r\n")
                       .withConnectionTimeoutMs (60000);   // model can be slow

        int statusCode = 0;
        juce::StringPairArray responseHeaders;
        auto stream = url.createInputStream (options.withStatusCode (&statusCode)
                                                    .withResponseHeaders (&responseHeaders));
        r.httpStatus = statusCode;

        if (stream == nullptr)
        {
            r.errorMessage = "서버 연결 실패 (http://127.0.0.1:8765). "
                             "inference_server.py 가 실행 중인지 확인하세요.";
            return r;
        }

        juce::MemoryBlock response;
        stream->readIntoMemoryBlock (response);

        if (statusCode >= 400)
        {
            r.errorMessage = "서버 오류 " + juce::String (statusCode)
                           + ": " + response.toString();
            return r;
        }

        // The /generate_json endpoint returns a JSON object with a
        // base64 "midi" field. Parse it.
        auto parsed = juce::JSON::parse (response.toString());
        if (! parsed.isObject())
        {
            r.errorMessage = "서버 응답을 파싱할 수 없습니다.";
            return r;
        }

        auto midiB64 = parsed.getProperty ("midi_base64", "").toString();
        if (midiB64.isEmpty())
        {
            r.errorMessage = "서버 응답에 MIDI 데이터가 없습니다.";
            return r;
        }

        juce::MemoryOutputStream decoded;
        if (! juce::Base64::convertFromBase64 (decoded, midiB64))
        {
            r.errorMessage = "Base64 디코딩 실패.";
            return r;
        }

        juce::MemoryBlock midiOut (decoded.getData(), decoded.getDataSize());
        r.generatedSequence = AIBridge::midiBytesToSequence (midiOut);
        r.success = true;
        return r;
    }

    AIBridge& owner;
    juce::CriticalSection mutex;
    bool hasPending { false };
    juce::MemoryBlock  pendingMidiBytes;
    GenerateParams     pendingParams;
    ResultCallback     pendingCallback;
};

//==============================================================================
// AIBridge public API
//==============================================================================
AIBridge::AIBridge (juce::URL url)
    : serverUrl (std::move (url)),
      worker (std::make_unique<AsyncWorker> (*this))
{
}

AIBridge::~AIBridge() = default;

bool AIBridge::checkHealth (int timeoutMs)
{
    auto url = serverUrl.getChildURL ("health");
    auto options = juce::URL::InputStreamOptions (
                        juce::URL::ParameterHandling::inAddress)
                   .withConnectionTimeoutMs (timeoutMs);

    auto stream = url.createInputStream (options);
    if (stream == nullptr) return false;

    auto text = stream->readEntireStreamAsString();
    auto parsed = juce::JSON::parse (text);
    if (! parsed.isObject()) return false;

    return parsed.getProperty ("status", "").toString() == "ok"
        && (bool) parsed.getProperty ("model_loaded", false);
}

juce::var AIBridge::getStatus (int timeoutMs)
{
    auto url = serverUrl.getChildURL ("status");
    auto options = juce::URL::InputStreamOptions (
                        juce::URL::ParameterHandling::inAddress)
                   .withConnectionTimeoutMs (timeoutMs);

    auto stream = url.createInputStream (options);
    if (stream == nullptr) return {};

    return juce::JSON::parse (stream->readEntireStreamAsString());
}

bool AIBridge::loadLora (const juce::String& name, int timeoutMs)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty ("name", name);
    auto body = juce::JSON::toString (juce::var (obj.get()));

    auto url = serverUrl.getChildURL ("load_lora").withPOSTData (body);
    auto options = juce::URL::InputStreamOptions (
                        juce::URL::ParameterHandling::inPostData)
                   .withExtraHeaders ("Content-Type: application/json\r\n")
                   .withConnectionTimeoutMs (timeoutMs);

    int statusCode = 0;
    auto stream = url.createInputStream (options.withStatusCode (&statusCode));
    return stream != nullptr && statusCode == 200;
}

void AIBridge::loadLoraAsync (const juce::String& name, LoraCallback callback)
{
    // Sprint 33 XX4: offload the blocking HTTP call to a detached thread
    // so the plugin editor doesn't freeze while a LoRA loads (typical
    // 1-5s). We use juce::Thread::launch (free function) rather than a
    // persistent worker — load requests are rare (user toggling style)
    // and never overlap generation, so the extra thread is fine.
    //
    // serverUrl is captured by value to avoid a dangling reference if the
    // bridge is destroyed mid-request. The callback hops to the message
    // thread via MessageManager::callAsync so UI updates are safe.
    auto urlCopy = serverUrl;
    juce::Thread::launch (
        [urlCopy, name, callback = std::move (callback)]() mutable
        {
            juce::DynamicObject::Ptr obj = new juce::DynamicObject();
            obj->setProperty ("name", name);
            auto body = juce::JSON::toString (juce::var (obj.get()));

            auto url = urlCopy.getChildURL ("load_lora").withPOSTData (body);
            auto options = juce::URL::InputStreamOptions (
                                juce::URL::ParameterHandling::inPostData)
                           .withExtraHeaders ("Content-Type: application/json\r\n")
                           .withConnectionTimeoutMs (15000);   // LoRA load can be slow

            int statusCode = 0;
            auto stream = url.createInputStream (options.withStatusCode (&statusCode));

            bool success = stream != nullptr && statusCode == 200;
            juce::String err;
            if (! success)
            {
                err = stream == nullptr
                          ? juce::String ("LoRA 서버 연결 실패")
                          : juce::String ("LoRA 로드 실패 (HTTP ")
                              + juce::String (statusCode) + ")";
            }

            if (callback)
            {
                juce::MessageManager::callAsync (
                    [cb = std::move (callback), success, err = std::move (err)]() mutable
                    {
                        cb (success, std::move (err));
                    });
            }
        });
}

void AIBridge::requestVariationAsync (const juce::MidiMessageSequence& input,
                                      const GenerateParams& params,
                                      ResultCallback callback)
{
    auto midiBytes = sequenceToMidiBytes (input, params.tempo);
    worker->startRequest (std::move (midiBytes), params, std::move (callback));
}

void AIBridge::requestAudioToMidiAsync (const juce::MemoryBlock& audioBytes,
                                        const juce::String& filename,
                                        ResultCallback callback)
{
    // Sprint 35 ZZ1b: audio2midi sits on a detached thread like LoRA —
    // the server call can take 30-120s (Demucs + Basic Pitch), far beyond
    // acceptable UI-blocking time. We don't reuse the AsyncWorker because
    // that serialises generation requests; audio2midi is user-initiated and
    // should be independent.
    auto urlCopy = serverUrl;
    // Capture by value: JUCE MemoryBlock is ref-counted-copy via move, so
    // this is O(1) on the calling thread.
    juce::MemoryBlock audioCopy = audioBytes;

    juce::Thread::launch (
        [urlCopy, audioCopy = std::move (audioCopy), filename,
         callback = std::move (callback)]() mutable
        {
            Result r;

            // Build JSON body with base64-encoded audio
            juce::MemoryOutputStream b64;
            juce::Base64::convertToBase64 (b64, audioCopy.getData(), audioCopy.getSize());

            juce::DynamicObject::Ptr obj = new juce::DynamicObject();
            obj->setProperty ("audio_base64", b64.toString());
            obj->setProperty ("filename",     filename);
            obj->setProperty ("keep_vocals",  false);
            obj->setProperty ("rerank_with_midigpt", true);
            auto body = juce::JSON::toString (juce::var (obj.get()));

            auto url = urlCopy.getChildURL ("audio_to_midi").withPOSTData (body);
            auto options = juce::URL::InputStreamOptions (
                                juce::URL::ParameterHandling::inPostData)
                           .withExtraHeaders ("Content-Type: application/json\r\n")
                           .withConnectionTimeoutMs (180000);   // 3 min for audio2midi

            int statusCode = 0;
            auto stream = url.createInputStream (options.withStatusCode (&statusCode));
            r.httpStatus = statusCode;

            if (stream == nullptr)
            {
                r.errorMessage = "Audio2MIDI 서버 연결 실패 (/audio_to_midi).";
            }
            else
            {
                juce::MemoryBlock response;
                stream->readIntoMemoryBlock (response);
                if (statusCode >= 400)
                {
                    r.errorMessage = "Audio2MIDI 서버 오류 " + juce::String (statusCode)
                                   + ": " + response.toString();
                }
                else
                {
                    auto parsed = juce::JSON::parse (response.toString());
                    auto midiB64 = parsed.getProperty ("midi_base64", "").toString();
                    if (midiB64.isEmpty())
                    {
                        r.errorMessage = "Audio2MIDI 응답에 MIDI 데이터가 없습니다.";
                    }
                    else
                    {
                        juce::MemoryOutputStream decoded;
                        if (juce::Base64::convertFromBase64 (decoded, midiB64))
                        {
                            juce::MemoryBlock midiOut (decoded.getData(), decoded.getDataSize());
                            r.generatedSequence = AIBridge::midiBytesToSequence (midiOut);
                            r.success = true;
                        }
                        else
                        {
                            r.errorMessage = "Audio2MIDI Base64 디코딩 실패.";
                        }
                    }
                }
            }

            if (callback)
            {
                juce::MessageManager::callAsync (
                    [cb = std::move (callback), r = std::move (r)]() mutable
                    {
                        cb (std::move (r));
                    });
            }
        });
}

void AIBridge::cancelPendingRequests()
{
    // Nothing graceful we can do during a blocking HTTP read in JUCE —
    // the best we can do is signal the worker to stop and let the
    // current request finish naturally.
    if (worker != nullptr)
        worker->signalThreadShouldExit();
}

//==============================================================================
// Static helpers
//==============================================================================
juce::String AIBridge::buildGenerateJsonBody (const juce::MemoryBlock& midiBytes,
                                              const GenerateParams& params)
{
    juce::MemoryOutputStream b64;
    juce::Base64::convertToBase64 (b64, midiBytes.getData(), midiBytes.getSize());

    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty ("midi_base64",   b64.toString());
    obj->setProperty ("style",         params.style);
    obj->setProperty ("key",           params.key);
    obj->setProperty ("section",       params.section);
    obj->setProperty ("tempo",         params.tempo);
    obj->setProperty ("temperature",   params.temperature);
    obj->setProperty ("num_variations",params.numVariations);
    obj->setProperty ("max_tokens",    params.maxTokens);
    obj->setProperty ("min_new_tokens",params.minNewTokens);
    obj->setProperty ("repetition_penalty", params.repetitionPenalty);
    obj->setProperty ("no_repeat_ngram_size", params.noRepeatNgramSize);

    return juce::JSON::toString (juce::var (obj.get()));
}

juce::MemoryBlock AIBridge::sequenceToMidiBytes (const juce::MidiMessageSequence& seq,
                                                 double tempo)
{
    juce::MidiFile mf;
    mf.setTicksPerQuarterNote (480);

    // Tempo track
    juce::MidiMessageSequence tempoTrack;
    auto tempoMsg = juce::MidiMessage::tempoMetaEvent (
                        static_cast<int> (60000000.0 / tempo));
    tempoMsg.setTimeStamp (0.0);
    tempoTrack.addEvent (tempoMsg);
    mf.addTrack (tempoTrack);

    mf.addTrack (seq);

    juce::MemoryOutputStream out;
    mf.writeTo (out);
    return juce::MemoryBlock (out.getData(), out.getDataSize());
}

juce::MidiMessageSequence AIBridge::midiBytesToSequence (const juce::MemoryBlock& bytes)
{
    juce::MidiMessageSequence combined;
    juce::MemoryInputStream in (bytes, false);

    juce::MidiFile mf;
    if (! mf.readFrom (in))
        return combined;

    // Flatten all tracks into a single sequence with absolute timestamps.
    for (int t = 0; t < mf.getNumTracks(); ++t)
    {
        if (auto* track = mf.getTrack (t))
        {
            for (int e = 0; e < track->getNumEvents(); ++e)
            {
                auto* evt = track->getEventPointer (e);
                combined.addEvent (evt->message, 0.0);
            }
        }
    }
    combined.updateMatchedPairs();
    return combined;
}
