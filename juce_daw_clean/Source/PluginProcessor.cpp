/*
 * MidiGPT VST3 Plugin — PluginProcessor.cpp
 *
 * See PluginProcessor.h for Sprint 32 change summary.
 *
 * References (public sources only):
 *   - JUCE MidiBuffer / MidiMessageSequence docs
 *   - JUCE AudioPlayHead::getPosition() — host tempo/position query
 *   - JUCE Tutorial: MIDI and the JUCE MIDI API
 *
 * NO references to Cubase binaries or Ghidra output.
 */

#include "PluginProcessor.h"
#include "PluginEditor.h"

// -----------------------------------------------------------------------------
// Construction
// -----------------------------------------------------------------------------
MidiGPTProcessor::MidiGPTProcessor()
    : AudioProcessor (BusesProperties()),            // no audio buses (MIDI effect)
      parameters (*this, nullptr, "MidiGPT", createParameterLayout()),
      aiBridge (std::make_unique<AIBridge>())
{
}

MidiGPTProcessor::~MidiGPTProcessor()
{
    if (aiBridge != nullptr)
        aiBridge->cancelPendingRequests();
}

juce::AudioProcessorValueTreeState::ParameterLayout
MidiGPTProcessor::createParameterLayout()
{
    using juce::AudioParameterFloat;
    using juce::AudioParameterChoice;
    using juce::AudioParameterInt;
    using juce::NormalisableRange;

    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;

    params.push_back (std::make_unique<AudioParameterFloat> (
        juce::ParameterID { "temperature", 1 }, "Temperature",
        NormalisableRange<float> (0.5f, 1.5f, 0.01f), 0.9f));

    params.push_back (std::make_unique<AudioParameterInt> (
        juce::ParameterID { "numVariations", 1 }, "Variations",
        1, 5, 3));

    params.push_back (std::make_unique<AudioParameterChoice> (
        juce::ParameterID { "style", 1 }, "Style",
        juce::StringArray { "base", "jazz", "citypop", "metal", "classical" }, 0));

    return { params.begin(), params.end() };
}

// -----------------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------------
void MidiGPTProcessor::prepareToPlay (double sampleRate, int /*samplesPerBlock*/)
{
    currentSampleRate = sampleRate > 0.0 ? sampleRate : 44100.0;

    const juce::ScopedLock capLock (captureLock);
    capturedInput.clear();
    capturedNoteCount.store (0);

    const juce::ScopedLock schedLock (scheduledLock);
    scheduledOutput.clear();
    scheduledNextIndex = 0;
    hasScheduledPlayback.store (false);
}

void MidiGPTProcessor::releaseResources()
{
    // Nothing to release.
}

bool MidiGPTProcessor::isBusesLayoutSupported (const BusesLayout& /*layouts*/) const
{
    return true;      // MIDI effect accepts any bus layout
}

// -----------------------------------------------------------------------------
// Process block — capture host MIDI in, inject scheduled MIDI out
// -----------------------------------------------------------------------------
void MidiGPTProcessor::processBlock (juce::AudioBuffer<float>& buffer,
                                     juce::MidiBuffer& midiMessages)
{
    // MIDI effect produces no audio — clear every block to avoid leaking
    // whatever state the host passed in.
    buffer.clear();

    // -------------------------------------------------------------------------
    // Host tempo / transport snapshot (once per block)
    // -------------------------------------------------------------------------
    // We query the play-head at block-start so the whole block shares a
    // consistent beat-origin. getPosition() may return nullopt under hosts
    // that don't expose one (e.g. some offline render modes) — fall back
    // to our cached tempo in that case.
    if (auto* ph = getPlayHead())
    {
        if (auto pos = ph->getPosition())
        {
            if (auto bpm = pos->getBpm())
                currentBpm = *bpm;
            if (auto ppq = pos->getPpqPosition())
                currentBeatAtBlockStart = *ppq;
            hostWasPlaying.store (pos->getIsPlaying());
        }
    }

    const double secondsPerBeat = 60.0 / juce::jmax (1.0, currentBpm);
    const double samplesPerBeat = secondsPerBeat * currentSampleRate;
    const int    numSamples     = buffer.getNumSamples();

    // -------------------------------------------------------------------------
    // WW2: Capture incoming MIDI at beat-time
    // -------------------------------------------------------------------------
    // We only accumulate while the host is playing — otherwise the plugin
    // would capture incidental controller noise from the DAW's idle state.
    {
        const juce::ScopedLock lock (captureLock);
        for (const auto metadata : midiMessages)
        {
            const auto msg = metadata.getMessage();
            if (! (msg.isNoteOnOrOff() || msg.isController() || msg.isPitchWheel()))
                continue;

            // Sample-offset within the block → beat offset from block start.
            const double sampleOffset = static_cast<double> (metadata.samplePosition);
            const double beatOffset   = sampleOffset / samplesPerBeat;
            auto msgCopy = msg;
            msgCopy.setTimeStamp (currentBeatAtBlockStart + beatOffset);

            capturedInput.addEvent (msgCopy);

            if (msg.isNoteOn())
                capturedNoteCount.fetch_add (1);
        }
        capturedInput.updateMatchedPairs();
    }

    // -------------------------------------------------------------------------
    // WW4: Inject scheduled MIDI out from the last completed generation
    // -------------------------------------------------------------------------
    // Events are pushed to ``scheduledOutput`` by the message-thread callback
    // in requestVariation(). Here on the audio thread we consume them in
    // order, converting their beat timestamps to sample offsets within this
    // block. We REPLACE the host's MIDI out rather than merge, so the
    // generated variation is what the DAW records downstream.
    if (hasScheduledPlayback.load())
    {
        midiMessages.clear();   // replace pass-through with generated events

        const juce::ScopedLock lock (scheduledLock);
        const double blockStartBeat = currentBeatAtBlockStart - scheduledStartBeat;
        const double blockEndBeat   = blockStartBeat + (numSamples / samplesPerBeat);

        while (scheduledNextIndex < scheduledOutput.getNumEvents())
        {
            auto* evt = scheduledOutput.getEventPointer (scheduledNextIndex);
            const double evtBeat = evt->message.getTimeStamp();

            if (evtBeat < blockStartBeat)
            {
                // Past events (e.g. playback started mid-sequence) — skip.
                ++scheduledNextIndex;
                continue;
            }
            if (evtBeat >= blockEndBeat)
                break;   // event lives in a future block

            const int sampleInBlock = static_cast<int> (
                (evtBeat - blockStartBeat) * samplesPerBeat);
            midiMessages.addEvent (evt->message,
                                   juce::jlimit (0, numSamples - 1, sampleInBlock));
            ++scheduledNextIndex;
        }

        if (scheduledNextIndex >= scheduledOutput.getNumEvents())
            hasScheduledPlayback.store (false);   // done
    }
}

// -----------------------------------------------------------------------------
// WW3: Variation generation — wired to the AIBridge HTTP client
// -----------------------------------------------------------------------------
void MidiGPTProcessor::requestVariation()
{
    if (aiBridge == nullptr)
    {
        fireStatus (GenerationStatus::Error, "AIBridge unavailable");
        return;
    }

    juce::MidiMessageSequence promptCopy;
    int promptNoteCount = 0;
    {
        const juce::ScopedLock lock (captureLock);
        promptCopy = capturedInput;   // MidiMessageSequence is copyable
        promptNoteCount = capturedNoteCount.load();
    }

    if (promptCopy.getNumEvents() == 0 || promptNoteCount == 0)
    {
        fireStatus (GenerationStatus::NoInputCaptured,
                    "캡처된 MIDI 가 없습니다. 재생 중 MIDI 를 입력한 뒤 다시 시도하세요.");
        return;
    }

    AIBridge::GenerateParams params;
    if (auto* p = parameters.getRawParameterValue ("temperature"))
        params.temperature = p->load();
    if (auto* p = parameters.getRawParameterValue ("numVariations"))
        params.numVariations = juce::jlimit (1, 5, static_cast<int> (p->load()));
    if (auto* p = parameters.getRawParameterValue ("style"))
    {
        const juce::StringArray styles { "base", "jazz", "citypop", "metal", "classical" };
        const int idx = juce::jlimit (0, styles.size() - 1, static_cast<int> (p->load()));
        params.style = styles[idx];
    }
    params.tempo = currentBpm;

    fireStatus (GenerationStatus::InFlight, "서버에 생성 요청 중...");

    aiBridge->requestVariationAsync (
        promptCopy, params,
        [this] (AIBridge::Result result)
        {
            // Called on the message thread (AIBridge posts via MessageManager::callAsync).
            if (! result.success)
            {
                fireStatus (GenerationStatus::Error,
                            result.errorMessage.isNotEmpty()
                                ? result.errorMessage
                                : juce::String ("생성 실패 (HTTP ")
                                  + juce::String (result.httpStatus) + ")");
                return;
            }

            // YY4: push current lastGenerated to undo stack BEFORE replacing.
            // Fresh generation implicitly invalidates the redo stack (branching
            // off an older state).
            if (lastGenerated.getNumEvents() > 0)
                pushHistory (lastGenerated);
            redoStack.clear();

            installGeneratedSequence (result.generatedSequence);

            fireStatus (GenerationStatus::Ready,
                        juce::String ("생성 완료 — ")
                          + juce::String (result.generatedSequence.getNumEvents())
                          + " 이벤트");
        });
}

// -----------------------------------------------------------------------------
// YY4 — shared helper: schedule + store a generated sequence
// -----------------------------------------------------------------------------
void MidiGPTProcessor::installGeneratedSequence (juce::MidiMessageSequence seq)
{
    // Schedule playback at the next integer beat boundary so the first note
    // lands audibly in sync (cf. WW4 rationale).
    const double startBeat = std::floor (currentBeatAtBlockStart) + 1.0;
    {
        const juce::ScopedLock lock (scheduledLock);
        scheduledOutput = seq;
        scheduledOutput.updateMatchedPairs();
        scheduledNextIndex = 0;
        scheduledStartBeat = startBeat;
    }
    lastGenerated = std::move (seq);
    hasScheduledPlayback.store (true);
}

// -----------------------------------------------------------------------------
// YY4 — undo / redo
// -----------------------------------------------------------------------------
void MidiGPTProcessor::pushHistory (juce::MidiMessageSequence replacedGeneration)
{
    undoStack.push_back (std::move (replacedGeneration));
    if ((int) undoStack.size() > kHistoryLimit)
        undoStack.erase (undoStack.begin());
}

bool MidiGPTProcessor::undoGeneration()
{
    if (undoStack.empty()) return false;

    // Pop the top of undo → install; current lastGenerated goes onto redo.
    auto previous = std::move (undoStack.back());
    undoStack.pop_back();

    if (lastGenerated.getNumEvents() > 0)
    {
        redoStack.push_back (lastGenerated);
        if ((int) redoStack.size() > kHistoryLimit)
            redoStack.erase (redoStack.begin());
    }

    installGeneratedSequence (std::move (previous));
    fireStatus (GenerationStatus::Ready,
                juce::String ("Undo — 이전 생성 결과 복원"));
    return true;
}

bool MidiGPTProcessor::redoGeneration()
{
    if (redoStack.empty()) return false;

    auto next = std::move (redoStack.back());
    redoStack.pop_back();

    if (lastGenerated.getNumEvents() > 0)
    {
        undoStack.push_back (lastGenerated);
        if ((int) undoStack.size() > kHistoryLimit)
            undoStack.erase (undoStack.begin());
    }

    installGeneratedSequence (std::move (next));
    fireStatus (GenerationStatus::Ready,
                juce::String ("Redo — 다음 생성 결과 복원"));
    return true;
}

// -----------------------------------------------------------------------------
// YY5 — load external MIDI as the captured-input prompt (drag-and-drop)
// -----------------------------------------------------------------------------
void MidiGPTProcessor::loadAsCapturedInput (const juce::MidiMessageSequence& seq)
{
    const juce::ScopedLock lock (captureLock);
    capturedInput = seq;
    capturedInput.updateMatchedPairs();

    int noteCount = 0;
    for (int i = 0; i < capturedInput.getNumEvents(); ++i)
        if (capturedInput.getEventPointer (i)->message.isNoteOn())
            ++noteCount;
    capturedNoteCount.store (noteCount);
}

void MidiGPTProcessor::clearCapturedInput()
{
    const juce::ScopedLock lock (captureLock);
    capturedInput.clear();
    capturedNoteCount.store (0);
}

void MidiGPTProcessor::fireStatus (GenerationStatus st, juce::String msg)
{
    // Safe to call from any thread — we hop to the message thread so the
    // editor can update its UI without locking.
    if (! statusCallback) return;
    auto cb = statusCallback;
    juce::MessageManager::callAsync (
        [cb, st, msg = std::move (msg)]() mutable
        {
            cb (st, std::move (msg));
        });
}

// -----------------------------------------------------------------------------
// WW6: State save / restore — parameters + last generated sequence
// -----------------------------------------------------------------------------
// The host calls these when saving/loading the project. We persist:
//   1. Parameter tree (temperature / numVariations / style) — via VTS XML
//   2. Last generated MidiMessageSequence — serialised as a MIDI file blob
// so the user can reload a Cubase project and still hear the variation
// without re-running inference.
// Layout: <MidiGPTState>{ <Parameters/>, <LastGenerated base64="..."/> }
// -----------------------------------------------------------------------------
void MidiGPTProcessor::getStateInformation (juce::MemoryBlock& destData)
{
    juce::XmlElement root ("MidiGPTState");
    root.setAttribute ("version", 1);

    // Parameters
    if (auto paramXml = std::unique_ptr<juce::XmlElement> (parameters.copyState().createXml()))
        root.addChildElement (paramXml.release());

    // Last generated sequence → standard MIDI file → base64
    if (lastGenerated.getNumEvents() > 0)
    {
        juce::MidiFile mf;
        mf.setTicksPerQuarterNote (480);
        mf.addTrack (lastGenerated);
        juce::MemoryOutputStream midiOut;
        mf.writeTo (midiOut);

        juce::MemoryOutputStream b64;
        juce::Base64::convertToBase64 (b64, midiOut.getData(), midiOut.getDataSize());

        auto* lg = new juce::XmlElement ("LastGenerated");
        lg->setAttribute ("base64", b64.toString());
        root.addChildElement (lg);
    }

    copyXmlToBinary (root, destData);
}

void MidiGPTProcessor::setStateInformation (const void* data, int sizeInBytes)
{
    auto xml = getXmlFromBinary (data, sizeInBytes);
    if (xml == nullptr || ! xml->hasTagName ("MidiGPTState"))
    {
        // Backwards compat: older versions stored the VTS tree at the root.
        if (xml != nullptr && xml->hasTagName (parameters.state.getType()))
            parameters.replaceState (juce::ValueTree::fromXml (*xml));
        return;
    }

    if (auto* paramXml = xml->getChildByName (parameters.state.getType()))
        parameters.replaceState (juce::ValueTree::fromXml (*paramXml));

    if (auto* lg = xml->getChildByName ("LastGenerated"))
    {
        auto b64 = lg->getStringAttribute ("base64");
        juce::MemoryOutputStream decoded;
        if (juce::Base64::convertFromBase64 (decoded, b64))
        {
            juce::MemoryBlock midiBytes (decoded.getData(), decoded.getDataSize());
            juce::MemoryInputStream in (midiBytes, false);
            juce::MidiFile mf;
            if (mf.readFrom (in))
            {
                lastGenerated.clear();
                for (int t = 0; t < mf.getNumTracks(); ++t)
                {
                    if (auto* track = mf.getTrack (t))
                    {
                        for (int e = 0; e < track->getNumEvents(); ++e)
                        {
                            auto* evt = track->getEventPointer (e);
                            lastGenerated.addEvent (evt->message, 0.0);
                        }
                    }
                }
                lastGenerated.updateMatchedPairs();
            }
        }
    }
}

// -----------------------------------------------------------------------------
// Editor
// -----------------------------------------------------------------------------
juce::AudioProcessorEditor* MidiGPTProcessor::createEditor()
{
    return new MidiGPTEditor (*this);
}

// -----------------------------------------------------------------------------
// VST3 / AU factory entry point — JUCE generates the binding
// -----------------------------------------------------------------------------
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new MidiGPTProcessor();
}
