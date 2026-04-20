/*
 * MidiGPT DAW - AudioEngine.cpp
 */

#include "AudioEngine.h"
#include <set>
#include <algorithm>
#include <array>
#include <cmath>

AudioEngine::AudioEngine()
{
    midiEngine.setTrackModel(&trackModel);

    // Y3 — wire BusModel orphan-cleanup callback
    busModel.onBusRemoved = [this](int removedId) {
        for (auto& t : trackModel.getTracks())
        {
            if (t.outputBusId == removedId) t.outputBusId = 0;
            t.sends.erase(std::remove_if(t.sends.begin(), t.sends.end(),
                [removedId](const Track::Send& s) { return s.busId == removedId; }),
                t.sends.end());
        }
    };
}

SynthEngine& AudioEngine::getOrCreateTrackSynth(int trackId)
{
    auto it = trackSynths.find(trackId);
    if (it != trackSynths.end()) return *it->second;
    auto s = std::make_unique<SynthEngine>();
    if (currentSampleRate > 0.0)
        s->prepare(currentSampleRate, busAccum.getNumSamples() > 0 ? busAccum.getNumSamples() : 512);
    auto& ref = *s;
    trackSynths.emplace(trackId, std::move(s));
    return ref;
}

void AudioEngine::prebuildTrackSynth(int trackId)
{
    // GUI-thread alloc — must NOT be called from audio callback.
    (void)getOrCreateTrackSynth(trackId);
}

AudioEngine::~AudioEngine()
{
    shutdown();
}

// X1 — Device-thread: push to the lock-free collector. Audio thread drains.
void AudioEngine::handleIncomingMidiMessage(juce::MidiInput*,
                                            const juce::MidiMessage& message)
{
    midiInputCollector.addMessageToQueue(message);
}

void AudioEngine::initialise()
{
    // Try output-only first (most reliable), then enable input if available
    auto result = deviceManager.initialiseWithDefaultDevices(0, 2);

    if (result.isNotEmpty())
    {
        DBG("AudioEngine: default init failed: " + result);

        juce::AudioDeviceManager::AudioDeviceSetup setup;
        setup.outputChannels.setRange(0, 2, true);
        setup.inputChannels.clear();
        setup.sampleRate = 44100.0;
        setup.bufferSize = 512;
        result = deviceManager.initialise(0, 2, nullptr, true, {}, &setup);

        if (result.isNotEmpty())
            DBG("AudioEngine: fallback init also failed: " + result);
    }

    // DD1 — try to enable audio input after output is confirmed working
    if (auto* device = deviceManager.getCurrentAudioDevice())
    {
        auto setup = deviceManager.getAudioDeviceSetup();
        if (device->getInputChannelNames().size() > 0)
        {
            setup.inputChannels.setRange(0, 2, true);
            deviceManager.setAudioDeviceSetup(setup, true);
        }
    }

    deviceManager.addAudioCallback(this);

    // W6 — attach MIDI input callback to every enabled input
    auto midiInputs = juce::MidiInput::getAvailableDevices();
    for (auto& dev : midiInputs)
    {
        deviceManager.setMidiInputDeviceEnabled(dev.identifier, true);
        deviceManager.addMidiInputDeviceCallback(dev.identifier, this);
    }

    // Log which device we're using
    if (auto* device = deviceManager.getCurrentAudioDevice())
        DBG("AudioEngine: using " + device->getName() + " @ "
            + juce::String(device->getCurrentSampleRate()) + " Hz");
    else
        DBG("AudioEngine: WARNING - no audio device!");
}

void AudioEngine::shutdown()
{
    deviceManager.removeAudioCallback(this);
    // W6 — detach MIDI input callbacks
    for (auto& dev : juce::MidiInput::getAvailableDevices())
        deviceManager.removeMidiInputDeviceCallback(dev.identifier, this);
    deviceManager.closeAudioDevice();
}

void AudioEngine::play()
{
    // Auto-rewind if at the end or past all content
    if (midiEngine.getPositionBeats() > 64.0)
        midiEngine.setPositionBeats(0.0);

    // Y5 — start count-in phase: metronome on, transport stays paused until
    // pre-roll elapses (handled in audioDeviceIOCallback).
    if (countInBars > 0)
    {
        countInRemainingBeats = countInBars * 4.0;
        metronomeOn = true;
        // Do not set midiEngine playing yet.
    }
    else
    {
        midiEngine.setPlaying(true);
    }
    lastMetronomeBeat = -1.0;
    testBeepSamples = testBeepLength;
}

void AudioEngine::stop()
{
    midiEngine.setPlaying(false);
    synthEngine.allNotesOff();
    // S1 — silence all per-track synths too
    for (auto& [id, syn] : trackSynths)
        if (syn) syn->allNotesOff();
}

void AudioEngine::togglePlayStop()
{
    if (midiEngine.isPlaying()) stop(); else play();
}

void AudioEngine::rewind()
{
    midiEngine.setPositionBeats(0.0);
    synthEngine.allNotesOff();
    for (auto& [id, syn] : trackSynths)
        if (syn) syn->allNotesOff();
    lastMetronomeBeat = -1.0;
}

// ---------------------------------------------------------------------------
// audioDeviceIOCallbackWithContext
//
// Signal flow (extended for F3/F4/F7):
//   For each track:
//     1. Filter MIDI to that track's channel
//     2. Apply automation (volume/pan envelopes at current beat)
//     3. Render MIDI → trackBuf via SynthEngine
//     4. Apply track volume + pan
//     5. Run trackBuf through TrackPluginChain (track FX)
//     6. Sum into bus accumulator (per outputBusId; bus 0 = master)
//   Master bus FX (later) → master volume → output
//
// Backwards-compatible: when no plugins/automation/buses exist, behavior
// matches the previous single-synth path (just gated per-channel).
// ---------------------------------------------------------------------------
void AudioEngine::audioDeviceIOCallbackWithContext(
    const float* const* inputChannelData, int numInputChannels,
    float* const* outputChannelData, int numOutputChannels,
    int numSamples, const juce::AudioIODeviceCallbackContext&)
{
    const int outCh = juce::jmax(1, numOutputChannels);

    // D3 — guard sample rate before any division
    if (currentSampleRate <= 0.0) currentSampleRate = 44100.0;

    // DD1 — capture audio input when recording
    if (audioRecTrackId >= 0 && midiEngine.isPlaying() && numInputChannels > 0
        && midiEngine.isInPunchRegion(midiEngine.getPositionBeats())) // GG1
    {
        const int recCh = juce::jmin(2, numInputChannels);
        // Grow buffer if needed (pre-allocate ~5 min chunks)
        static constexpr double kAudioRecChunkSec = 300.0; // H1 — 5 min chunks
        const int chunkSize = (int)(currentSampleRate * kAudioRecChunkSec);
        if (audioRecBuffer.getNumSamples() == 0)
        {
            audioRecBuffer.setSize(recCh, chunkSize);
            audioRecBuffer.clear();
            audioRecWritePos = 0;
            audioRecStartBeat = midiEngine.getPositionBeats();
        }
        if (audioRecWritePos + numSamples > audioRecBuffer.getNumSamples())
        {
            // Extend buffer
            const int newSize = audioRecBuffer.getNumSamples() + chunkSize;
            audioRecBuffer.setSize(recCh, newSize, true, true, false);
        }
        for (int ch = 0; ch < recCh; ++ch)
        {
            if (inputChannelData[ch] != nullptr)
                audioRecBuffer.copyFrom(ch, audioRecWritePos, inputChannelData[ch], numSamples);
        }
        audioRecWritePos += numSamples;
    }

    // Clear output
    for (int ch = 0; ch < numOutputChannels; ++ch)
        if (outputChannelData[ch])
            juce::FloatVectorOperations::clear(outputChannelData[ch], numSamples);

    // EE1 (replaces X1) — MIDI Thru: feed incoming MIDI to armed track's synth for live monitoring
    // (even when not playing / not recording)
    {
        juce::MidiBuffer thruBuf;
        midiInputCollector.removeNextBlockOfMessages(thruBuf, numSamples);

        if (! thruBuf.isEmpty())
        {
            // Write to recording clip (existing X1 logic, GG1 — punch gate)
            if (recordingTrackId >= 0 && midiEngine.isPlaying()
                && midiEngine.isInPunchRegion(midiEngine.getPositionBeats()))
            {
                if (auto* rt = trackModel.getTrack(recordingTrackId))
                {
                    if (rt->armed && ! rt->clips.empty())
                    {
                        auto& clip = rt->clips.back();
                        const double posBeat = midiEngine.getPositionBeats();
                        const double bps = midiEngine.getTempo() / 60.0;
                        double latencySec = 0.0;
                        if (auto* dev = deviceManager.getCurrentAudioDevice())
                        {
                            const int outLat = dev->getOutputLatencyInSamples();
                            const int inLat  = dev->getInputLatencyInSamples();
                            latencySec = (outLat + inLat) / currentSampleRate;
                        }
                        latencySec += midiInputLatencyMs / 1000.0;
                        const double latencyBeats = latencySec * bps;

                        // HH1 — if not overdub, erase existing notes in this block's range
                        if (! rt->overdub)
                        {
                            const double blockStartRel = posBeat - clip.startBeat - latencyBeats;
                            const double blockEndRel = blockStartRel + (double)numSamples / currentSampleRate * bps;
                            for (int ni = clip.sequence.getNumEvents() - 1; ni >= 0; --ni)
                            {
                                auto& em = clip.sequence.getEventPointer(ni)->message;
                                if (em.isNoteOn() && em.getTimeStamp() >= blockStartRel
                                    && em.getTimeStamp() < blockEndRel)
                                    clip.sequence.deleteEvent(ni, true);
                            }
                        }

                        for (const auto meta : thruBuf)
                        {
                            auto msg = meta.getMessage();
                            const double sampleBeat = posBeat + (meta.samplePosition / currentSampleRate) * bps;
                            msg.setTimeStamp(sampleBeat - clip.startBeat - latencyBeats);
                            if (msg.getTimeStamp() >= 0.0)
                            {
                                clip.sequence.addEvent(msg);
                                if (msg.isNoteOff()) clip.sequence.updateMatchedPairs();
                            }
                        }
                    }
                }
            }

            // MIDI Thru: send to armed track's synth for immediate audition
            int thruTarget = recordingTrackId;
            if (thruTarget < 0)
            {
                // Find first armed track
                for (auto& t : trackModel.getTracks())
                    if (t.armed) { thruTarget = t.id; break; }
            }
            if (thruTarget >= 0)
            {
                auto& syn = getOrCreateTrackSynth(thruTarget);
                juce::AudioBuffer<float> thruAudio(outCh, numSamples);
                thruAudio.clear();
                syn.renderBlock(thruAudio, thruBuf);

                // Mix thru audio into output directly
                auto* t = trackModel.getTrack(thruTarget);
                float vol = (t != nullptr) ? t->volume : 1.0f;
                for (int ch = 0; ch < juce::jmin(numOutputChannels, thruAudio.getNumChannels()); ++ch)
                    if (outputChannelData[ch] != nullptr)
                        for (int s = 0; s < numSamples; ++s)
                            outputChannelData[ch][s] += thruAudio.getReadPointer(ch)[s] * vol * masterVolume;
            }
        }
    }

    // FF4 — audio input monitoring: pass input to output for armed+monitor tracks
    if (numInputChannels > 0)
    {
        for (auto& t : trackModel.getTracks())
        {
            if (!t.armed || !t.inputMonitor) continue;
            const int monCh = juce::jmin(2, numInputChannels, numOutputChannels);
            for (int ch = 0; ch < monCh; ++ch)
                if (inputChannelData[ch] != nullptr && outputChannelData[ch] != nullptr)
                    for (int s = 0; s < numSamples; ++s)
                        outputChannelData[ch][s] += inputChannelData[ch][s] * t.volume * masterVolume;
        }
    }

    // MIDI sequencer (unchanged)
    juce::MidiBuffer midiBuf;
    double beatsBefore = midiEngine.getPositionBeats();
    midiEngine.processBlock(numSamples, currentSampleRate, midiBuf);

    // Resize working buffers (no-op if already sized)
    if (busAccum.getNumChannels() != outCh || busAccum.getNumSamples() != numSamples)
        busAccum.setSize(outCh, numSamples, false, false, true);
    if (trackBuf.getNumChannels() != outCh || trackBuf.getNumSamples() != numSamples)
        trackBuf.setSize(outCh, numSamples, false, false, true);

    busAccum.clear();

    auto& tracks = trackModel.getTracks();

    // Solo gate (matches MidiEngine convention)
    bool anySolo = false;
    for (auto& t : tracks) if (t.solo) { anySolo = true; break; }

    const double curBeat = beatsBefore;

    // BB1 — helper: resolve effective mute/solo considering folder ancestors
    auto effectiveMute = [&](const Track& t) {
        if (t.mute) return true;
        int pid = t.parentTrackId;
        int safety = 0;
        while (pid >= 0 && safety++ < 8)
        {
            const Track* p = nullptr;
            for (auto& o : tracks) if (o.id == pid) { p = &o; break; }
            if (p == nullptr) break;
            if (p->mute) return true;
            pid = p->parentTrackId;
        }
        return false;
    };
    auto effectiveSolo = [&](const Track& t) {
        if (t.solo) return true;
        int pid = t.parentTrackId;
        int safety = 0;
        while (pid >= 0 && safety++ < 8)
        {
            const Track* p = nullptr;
            for (auto& o : tracks) if (o.id == pid) { p = &o; break; }
            if (p == nullptr) break;
            if (p->solo) return true;
            pid = p->parentTrackId;
        }
        return false;
    };

    for (auto& track : tracks)
    {
        if (effectiveMute(track)) continue;
        if (anySolo && ! effectiveSolo(track)) continue;

        // Apply automation envelopes (volume/pan/plugin params) at current beat
        float effVolume = track.volume;
        float effPan    = track.pan;
        for (auto& lane : track.automation)
        {
            if (! lane.enabled || lane.points.empty()) continue;
            if (lane.paramId == "volume") effVolume = lane.valueAt(curBeat, effVolume);
            else if (lane.paramId == "pan") effPan = lane.valueAt(curBeat, (effPan + 1.0f) * 0.5f) * 2.0f - 1.0f;
            else
            {
                // Z4 — plugin parameter automation: paramId = "<uid>/<paramName>"
                const auto slash = lane.paramId.indexOfChar('/');
                if (slash <= 0) continue;
                const auto uid  = lane.paramId.substring(0, slash);
                const auto name = lane.paramId.substring(slash + 1);

                // Find slot whose pluginUid matches
                for (int s = 0; s < (int)track.plugins.size(); ++s)
                {
                    if (track.plugins[s].pluginUid != uid) continue;
                    if (auto* inst = pluginChains.getPlugin(track.id, s))
                    {
                        auto& params = inst->getParameters();
                        for (auto* p : params)
                        {
                            if (p != nullptr && p->getName(64) == name)
                            {
                                p->setValueNotifyingHost(lane.valueAt(curBeat, p->getValue()));
                                break;
                            }
                        }
                    }
                    break;
                }
            }
        }
        effVolume = juce::jlimit(0.0f, 4.0f, effVolume);
        effPan    = juce::jlimit(-1.0f, 1.0f, effPan);

        // FF1 — automation Write/Latch: record current fader values as automation points
        if (midiEngine.isPlaying()
            && track.autoMode != Track::AutoMode::Read)
        {
            auto recordParam = [&](const juce::String& pid, float val) {
                // NP1 — avoid iterator invalidation: find or create by index
                int laneIdx = -1;
                for (int li = 0; li < (int)track.automation.size(); ++li)
                    if (track.automation[(size_t)li].paramId == pid) { laneIdx = li; break; }
                if (laneIdx < 0)
                {
                    AutomationLane nl;
                    nl.paramId = pid;
                    track.automation.push_back(std::move(nl));
                    laneIdx = (int)track.automation.size() - 1;
                }
                track.automation[(size_t)laneIdx].addPoint(curBeat, val);
            };

            recordParam("volume", track.volume);
            recordParam("pan", (track.pan + 1.0f) * 0.5f);
        }

        // Filter MIDI to this track's channel
        juce::MidiBuffer trackMidi;

        // userProgram override: send program change at block start
        if (track.userProgram >= 0)
        {
            auto pc = juce::MidiMessage::programChange(track.midiChannel, track.userProgram);
            trackMidi.addEvent(pc, 0);
        }

        for (const auto meta : midiBuf)
        {
            auto msg = meta.getMessage();
            if (msg.getChannel() != track.midiChannel) continue;
            // Skip MIDI file program changes when user has override
            if (msg.isProgramChange() && track.userProgram >= 0) continue;
            trackMidi.addEvent(msg, meta.samplePosition);
        }

        // Render MIDI → trackBuf via per-track synth (S1 — no cross-talk)
        trackBuf.clear();
        getOrCreateTrackSynth(track.id).renderBlock(trackBuf, trackMidi);

        // PPP4 — live input monitoring. When this track is the armed
        // audio-recording target and monitoring is on, mix the raw device
        // input into trackBuf before plugins/fader/sends so the user hears
        // what's being captured routed through the track's processing.
        if (inputMonitoringOn
            && audioRecTrackId >= 0 && audioRecTrackId == track.id
            && numInputChannels > 0)
        {
            const int monCh = juce::jmin(trackBuf.getNumChannels(), numInputChannels);
            for (int ch = 0; ch < monCh; ++ch)
            {
                if (inputChannelData[ch] != nullptr)
                    trackBuf.addFrom(ch, 0, inputChannelData[ch], numSamples);
            }
        }

        // S2 — mix audio clips at current beat into trackBuf
        if (! track.audioClips.empty())
        {
            const double beatsPerSample = midiEngine.getTempo() / (60.0 * currentSampleRate);
            for (auto& clip : track.audioClips)
            {
                if (clip.isEmpty()) continue;
                const double clipEndBeat = clip.startBeat + clip.lengthBeats;
                if (curBeat >= clipEndBeat) continue;
                if (curBeat + numSamples * beatsPerSample <= clip.startBeat) continue;

                // Sample offset in clip buffer for the start of this audio block.
                // W5 — add sourceOffsetSamples (non-destructive trim).
                const double secsIntoClip = (curBeat - clip.startBeat) * (60.0 / midiEngine.getTempo());
                const juce::int64 srcStart = clip.sourceOffsetSamples
                    + (juce::int64)(secsIntoClip * clip.sourceSampleRate);
                if (srcStart >= clip.buffer.getNumSamples()) continue;

                // NNN6 — replace the inline U4 Catmull-Rom loop with a call
                // through ResamplerWrapper (JUCE Lagrange by default;
                // r8brain when MIDIGPTDAW_WITH_R8BRAIN). Keeps the fade
                // envelope (DD2) and accumulation into trackBuf identical.
                const int dstChannels = juce::jmin(trackBuf.getNumChannels(),
                                                   clip.buffer.getNumChannels());
                if (dstChannels <= 0) continue;

                // Bake clip playbackRate + pitch into an effective source SR.
                // ResamplerWrapper uses srRatio = sourceSr / destSr; prepare()
                // per clip per block, RT-safe after reserveChannels().
                const double rateMul = clip.playbackRate
                    * (std::abs(clip.pitchSemitones) > 0.01f
                        ? std::pow(2.0, clip.pitchSemitones / 12.0) : 1.0);
                const double effSourceSr = clip.sourceSampleRate
                    * juce::jlimit(0.25, 4.0, rateMul);
                const double srRatio     = effSourceSr / currentSampleRate;

                // Bound the source slice to what the clip buffer actually
                // contains; derive the max producible output from that.
                const juce::int64 srcAvail
                    = (juce::int64)clip.buffer.getNumSamples() - srcStart;
                const int srcWanted
                    = (int)std::ceil((double)numSamples * srRatio) + 8;
                const int srcLen = (int)juce::jmin((juce::int64)srcWanted, srcAvail);
                if (srcLen < 4) continue;
                const int numOut = juce::jmin(numSamples,
                    (int)((double)(srcLen - 4) / juce::jmax(srRatio, 1.0e-6)));
                if (numOut <= 0) continue;

                // Non-owning AudioBuffer view of the source slice (avoids
                // copying the region into a scratch before resampling).
                const int viewCh = juce::jmin(dstChannels,
                                              clipScratch.getNumChannels());
                if (viewCh <= 0) continue;
                std::array<float*, 16> srcPtrs{};
                const int vCh = juce::jmin(viewCh, (int)srcPtrs.size());
                for (int ch = 0; ch < vCh; ++ch)
                    srcPtrs[(size_t)ch]
                        = const_cast<float*>(clip.buffer.getReadPointer(ch)) + srcStart;
                juce::AudioBuffer<float> srcView(srcPtrs.data(), vCh, srcLen);

                // Scratch must be wide enough; otherwise skip this clip
                // (guards against a shrinking device without re-prepare).
                if (clipScratch.getNumSamples() < numOut) continue;

                clipResampler.prepare(effSourceSr, currentSampleRate, vCh, numOut);
                // Temporarily restrict scratch to numOut so process() fills
                // exactly that many samples per channel without touching
                // beyond the valid region.
                juce::AudioBuffer<float> scratchView(
                    clipScratch.getArrayOfWritePointers(), vCh, numOut);
                clipResampler.process(srcView, scratchView);

                // DD2 — apply fade envelope and accumulate into trackBuf.
                for (int ch = 0; ch < vCh; ++ch)
                {
                    const float* scratchPtr = scratchView.getReadPointer(ch);
                    float* dst              = trackBuf.getWritePointer(ch);
                    for (int s = 0; s < numOut; ++s)
                    {
                        const double beatInClip = (curBeat - clip.startBeat)
                            + (double)s * beatsPerSample;
                        dst[s] += scratchPtr[s] * clip.fadeGainAt(beatInClip);
                    }
                }
            }
        }

        // EE3 — pre-fader sends (before volume/pan)
        for (auto& snd : track.sends)
        {
            if (snd.level <= 0.0f || !snd.preFader) continue;
            if (snd.busId == 0) continue;
            if (busModel.getBus(snd.busId) == nullptr) continue;

            auto& sbuf = busBuffers[snd.busId];
            if (sbuf.getNumChannels() != outCh || sbuf.getNumSamples() != numSamples)
                sbuf.setSize(outCh, numSamples, false, false, true);

            for (int ch = 0; ch < juce::jmin(outCh, trackBuf.getNumChannels()); ++ch)
                sbuf.addFrom(ch, 0, trackBuf, ch, 0, numSamples, snd.level);
        }

        // Apply track volume + simple constant-power pan
        const float panL = std::cos((effPan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
        const float panR = std::sin((effPan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
        if (trackBuf.getNumChannels() >= 2)
        {
            trackBuf.applyGain(0, 0, numSamples, effVolume * panL);
            trackBuf.applyGain(1, 0, numSamples, effVolume * panR);
        }
        else
        {
            trackBuf.applyGain(effVolume);
        }

        // OO4 — per-track RMS VU
        {
            float rmsL = 0.0f, rmsR = 0.0f;
            if (trackBuf.getNumChannels() >= 1)
            {
                auto* p = trackBuf.getReadPointer(0);
                double sq = 0.0;
                for (int s = 0; s < numSamples; ++s) sq += p[s] * p[s];
                rmsL = (float)std::sqrt(sq / juce::jmax(1, numSamples));
            }
            if (trackBuf.getNumChannels() >= 2)
            {
                auto* p = trackBuf.getReadPointer(1);
                double sq = 0.0;
                for (int s = 0; s < numSamples; ++s) sq += p[s] * p[s];
                rmsR = (float)std::sqrt(sq / juce::jmax(1, numSamples));
            }
            trackVuL[track.id] = trackVuL[track.id] * 0.85f + rmsL * 0.15f;
            trackVuR[track.id] = trackVuR[track.id] * 0.85f + rmsR * 0.15f;
        }

        // Run through track FX chain (no-op if track.plugins empty)
        if (! track.plugins.empty())
        {
            juce::MidiBuffer fxMidi; // separate instance, plugins may consume
            pluginChains.processTrack(track.id, track, trackBuf, fxMidi);
        }

        // S4 — accumulate into the track's target bus (0 = master).
        int targetBus = track.outputBusId;
        if (targetBus != 0 && busModel.getBus(targetBus) == nullptr)
            targetBus = 0; // unknown bus → master fallback (rules/02 입력 검증)

        auto& busBuf = busBuffers[targetBus];
        if (busBuf.getNumChannels() != outCh || busBuf.getNumSamples() != numSamples)
            busBuf.setSize(outCh, numSamples, false, false, true);

        for (int ch = 0; ch < juce::jmin(outCh, trackBuf.getNumChannels()); ++ch)
            busBuf.addFrom(ch, 0, trackBuf, ch, 0, numSamples);

        // U3 + EE3 — post-fader sends only (pre-fader already done above).
        for (auto& snd : track.sends)
        {
            if (snd.level <= 0.0f || snd.preFader) continue; // EE3
            if (snd.busId == 0) continue;
            if (busModel.getBus(snd.busId) == nullptr) continue;

            auto& sbuf = busBuffers[snd.busId];
            if (sbuf.getNumChannels() != outCh || sbuf.getNumSamples() != numSamples)
                sbuf.setSize(outCh, numSamples, false, false, true);

            for (int ch = 0; ch < juce::jmin(outCh, trackBuf.getNumChannels()); ++ch)
                sbuf.addFrom(ch, 0, trackBuf, ch, 0, numSamples, snd.level);
        }
    }

    // W3 — apply per-bus volume/pan/mute, then route to target bus (possibly
    // another user bus). Process in dependency order determined by a simple
    // topological pass with cycle detection (falls back to master on cycles).
    auto& masterBuf = busBuffers[0];
    if (masterBuf.getNumChannels() != outCh || masterBuf.getNumSamples() != numSamples)
        masterBuf.setSize(outCh, numSamples, false, false, true);

    // Build dependency depth per bus via visit + cycle detection
    std::map<int, int> depth; // 0 = routes to master, 1 = routes to depth-0 bus...
    auto computeDepth = [&](auto&& self, int busId, std::set<int>& seen) -> int {
        if (busId == 0) return -1; // master sentinel
        if (auto it = depth.find(busId); it != depth.end()) return it->second;
        if (! seen.insert(busId).second) return 0; // cycle → treat as master-routed
        auto* b = busModel.getBus(busId);
        if (b == nullptr) return 0;
        int d = self(self, b->outputBusId, seen) + 1;
        seen.erase(busId);
        depth[busId] = d;
        return d;
    };
    std::vector<int> order;
    for (auto& bus : busModel.getBuses())
    {
        if (bus.id == 0) continue;
        std::set<int> seen;
        (void)computeDepth(computeDepth, bus.id, seen);
        order.push_back(bus.id);
    }
    std::sort(order.begin(), order.end(), [&](int a, int b) {
        return depth[a] < depth[b]; // lowest depth (closest to master) first
    });

    for (int busId : order)
    {
        auto* bus = busModel.getBus(busId);
        if (bus == nullptr) continue;

        auto it = busBuffers.find(busId);
        if (it == busBuffers.end()) continue;
        auto& buf = it->second;
        if (bus->mute) { buf.clear(); continue; }

        const float panL = std::cos((bus->pan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
        const float panR = std::sin((bus->pan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
        if (buf.getNumChannels() >= 2)
        {
            buf.applyGain(0, 0, numSamples, bus->volume * panL);
            buf.applyGain(1, 0, numSamples, bus->volume * panR);
        }
        else
        {
            buf.applyGain(bus->volume);
        }

        // Route to target: 0 master, or another user bus (deeper depth already done).
        int targetId = bus->outputBusId;
        if (targetId != 0 && busModel.getBus(targetId) == nullptr) targetId = 0;
        if (targetId == busId) targetId = 0; // self-loop → master
        auto& tgtBuf = busBuffers[targetId];
        if (tgtBuf.getNumChannels() != outCh || tgtBuf.getNumSamples() != numSamples)
            tgtBuf.setSize(outCh, numSamples, false, false, true);
        for (int ch = 0; ch < juce::jmin(outCh, buf.getNumChannels()); ++ch)
            tgtBuf.addFrom(ch, 0, buf, ch, 0, numSamples);
        buf.clear();
    }

    // Apply master volume → output
    for (int ch = 0; ch < juce::jmin(numOutputChannels, masterBuf.getNumChannels()); ++ch)
    {
        auto* dest = outputChannelData[ch];
        auto* src = masterBuf.getReadPointer(ch);
        for (int s = 0; s < numSamples; ++s)
            dest[s] += src[s] * masterVolume;
    }
    masterBuf.clear();

    // Y5 — count-in pre-roll. While active, metronome ticks but the MIDI
    // sequencer is not advancing yet.
    if (countInRemainingBeats > 0.0)
    {
        const double bps = midiEngine.getTempo() / 60.0;
        const double beatsThisBlock = (double)numSamples / currentSampleRate * bps;
        const double before = countInRemainingBeats;
        countInRemainingBeats -= beatsThisBlock;

        // Synthesise metronome clicks at each whole-beat crossing during pre-roll
        const double posBeat = (double)(countInBars * 4) - before;
        const int intBefore = (int)std::floor(posBeat);
        const int intAfter  = (int)std::floor(posBeat + beatsThisBlock);
        if (intAfter > intBefore)
        {
            metronomeClickSample = 0;
            metronomeIsDownbeat = (intAfter % 4 == 0);
        }
        if (numOutputChannels >= 2)
            generateMetronomeClick(outputChannelData[0], outputChannelData[1], numSamples);

        if (countInRemainingBeats <= 0.0)
        {
            countInRemainingBeats = 0.0;
            midiEngine.setPlaying(true); // transport kicks in
        }
        return; // skip normal processing this block
    }

    // Metronome
    if (metronomeOn && midiEngine.isPlaying())
    {
        double beatsAfter = midiEngine.getPositionBeats();
        double beatFloorBefore = std::floor(beatsBefore);
        double beatFloorAfter = std::floor(beatsAfter);

        if (beatFloorAfter > beatFloorBefore || beatsBefore < 0.001)
        {
            metronomeClickSample = 0;
            // HH6 — time-sig aware downbeat detection
            auto ts = midiEngine.timeSigAt(beatsAfter);
            double barLen = (ts.den > 0) ? (double)ts.num * (4.0 / (double)ts.den) : 4.0; // D2
            metronomeIsDownbeat = (std::fmod(beatsAfter, barLen) < 1.0);
        }

        if (numOutputChannels >= 2)
            generateMetronomeClick(outputChannelData[0], outputChannelData[1], numSamples);
        else if (numOutputChannels >= 1)
            generateMetronomeClick(outputChannelData[0], outputChannelData[0], numSamples);
    }

    // Send MIDI to external output
    if (!midiBuf.isEmpty())
    {
        auto* midiOut = deviceManager.getDefaultMidiOutput();
        if (midiOut) midiOut->sendBlockOfMessagesNow(midiBuf);
    }

    // Test beep (A440, 0.5s) - verifies audio output works
    if (testBeepSamples < testBeepLength)
    {
        for (int s = 0; s < numSamples && testBeepSamples < testBeepLength; ++s, ++testBeepSamples)
        {
            float t = (float)testBeepSamples / (float)testBeepLength;
            float env = (1.0f - t) * 0.4f; // fade out
            float sample = std::sin(2.0f * juce::MathConstants<float>::pi * 440.0f
                                    * testBeepSamples / (float)currentSampleRate) * env;
            for (int ch = 0; ch < numOutputChannels; ++ch)
                outputChannelData[ch][s] += sample;
        }
    }

    // W4 — RMS VU + peak hold
    const int holdReset = (int)(currentSampleRate); // 1 second
    if (numOutputChannels >= 1)
    {
        double sqSum = 0.0; float peakL = 0.0f;
        for (int s = 0; s < numSamples; ++s)
        { const float v = outputChannelData[0][s]; sqSum += v * v; peakL = juce::jmax(peakL, std::abs(v)); }
        const float rms = (float)std::sqrt(sqSum / juce::jmax(1, numSamples));
        vuLeft = vuLeft * 0.85f + rms * 0.15f;
        if (peakL > peakHoldL) { peakHoldL = peakL; peakHoldCountdownL = holdReset; }
        else
        {
            peakHoldCountdownL -= numSamples;
            if (peakHoldCountdownL <= 0) peakHoldL *= 0.9f;
        }
    }
    if (numOutputChannels >= 2)
    {
        double sqSum = 0.0; float peakR = 0.0f;
        for (int s = 0; s < numSamples; ++s)
        { const float v = outputChannelData[1][s]; sqSum += v * v; peakR = juce::jmax(peakR, std::abs(v)); }
        const float rms = (float)std::sqrt(sqSum / juce::jmax(1, numSamples));
        vuRight = vuRight * 0.85f + rms * 0.15f;
        if (peakR > peakHoldR) { peakHoldR = peakR; peakHoldCountdownR = holdReset; }
        else
        {
            peakHoldCountdownR -= numSamples;
            if (peakHoldCountdownR <= 0) peakHoldR *= 0.9f;
        }
    }
}

void AudioEngine::generateMetronomeClick(float* left, float* right, int numSamples)
{
    const int clickDuration = static_cast<int>(currentSampleRate * 0.03); // 30ms
    const float freq = metronomeIsDownbeat ? 1500.0f : 1000.0f;
    const float vol = metronomeIsDownbeat ? 0.5f : 0.35f;

    for (int s = 0; s < numSamples; ++s)
    {
        if (metronomeClickSample < clickDuration)
        {
            float t = static_cast<float>(metronomeClickSample) / static_cast<float>(clickDuration);
            float env = std::exp(-t * 8.0f);
            float sample = std::sin(2.0f * juce::MathConstants<float>::pi * freq
                                    * metronomeClickSample / (float)currentSampleRate)
                           * env * vol;
            left[s] += sample;
            right[s] += sample;
        }
        metronomeClickSample++;
    }
}

// DD1 — finalize audio recording: trim buffer and create AudioClip on target track
void AudioEngine::finalizeAudioRecording()
{
    if (audioRecTrackId < 0 || audioRecWritePos <= 0) return;

    auto* t = trackModel.getTrack(audioRecTrackId);
    if (t != nullptr)
    {
        AudioClip clip;
        clip.sourceSampleRate = currentSampleRate;
        clip.startBeat = audioRecStartBeat;

        // Trim buffer to actual recorded length
        const int recCh = audioRecBuffer.getNumChannels();
        clip.buffer.setSize(recCh, audioRecWritePos);
        for (int ch = 0; ch < recCh; ++ch)
            clip.buffer.copyFrom(ch, 0, audioRecBuffer, ch, 0, audioRecWritePos);

        const double durationSec = (double)audioRecWritePos / currentSampleRate;
        double tempo = juce::jmax(1.0, midiEngine.getTempo()); // BC2
        clip.lengthBeats = durationSec * (tempo / 60.0);

        t->audioClips.push_back(std::move(clip));
    }

    // Reset
    audioRecTrackId = -1;
    audioRecBuffer.setSize(0, 0);
    audioRecWritePos = 0;
}

// FF2 — recompute per-track delay needed for PDC alignment
void AudioEngine::updatePDC()
{
    maxPluginLatency = 0;
    for (auto& t : trackModel.getTracks())
    {
        int lat = pluginChains.getTotalLatency(t.id);
        if (lat > maxPluginLatency) maxPluginLatency = lat;
    }
    pdcDelaySamples.clear();
    for (auto& t : trackModel.getTracks())
    {
        int lat = pluginChains.getTotalLatency(t.id);
        pdcDelaySamples[t.id] = maxPluginLatency - lat;
    }
}

void AudioEngine::audioDeviceAboutToStart(juce::AudioIODevice* device)
{
    currentSampleRate = device->getCurrentSampleRate();
    const int blockSize = device->getCurrentBufferSizeSamples();
    synthEngine.prepare(currentSampleRate, blockSize);
    pluginChains.prepareAll(currentSampleRate, blockSize);
    midiInputCollector.reset(currentSampleRate); // X1

    // S1 — prepare every per-track SynthEngine for new device params
    for (auto& [id, syn] : trackSynths)
        if (syn) syn->prepare(currentSampleRate, blockSize);

    const int outCh = juce::jmax(2, device->getActiveOutputChannels().countNumberOfSetBits());
    trackBuf.setSize(outCh, blockSize, false, false, true);
    busAccum.setSize(outCh, blockSize, false, false, true);
    for (auto& [id, buf] : busBuffers)
        buf.setSize(outCh, blockSize, false, false, true);

    // NNN6 — pre-size clip resample scratch and per-channel interpolator
    // state so the audio thread never allocates during playback. Reserve a
    // few extra channels in case a future multichannel audio clip (e.g.
    // 5.1 stem) needs them — cheap memory, avoids RT surprises.
    const int resampleCh = juce::jmax(outCh, 8);
    clipScratch.setSize(resampleCh, blockSize, false, false, true);
    clipResampler.reserveChannels(resampleCh);
}

void AudioEngine::audioDeviceStopped()
{
    currentSampleRate = 44100.0;
}
