/*
 * MidiGPT DAW - AudioEngine.cpp
 */

#include "AudioEngine.h"
#include <set>
#include <algorithm>

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
    // Try default devices first
    auto result = deviceManager.initialiseWithDefaultDevices(0, 2);

    if (result.isNotEmpty())
    {
        DBG("AudioEngine: default init failed: " + result);

        // Fallback: try with explicit setup
        juce::AudioDeviceManager::AudioDeviceSetup setup;
        setup.outputChannels.setRange(0, 2, true);
        setup.inputChannels.clear();
        setup.sampleRate = 44100.0;
        setup.bufferSize = 512;
        result = deviceManager.initialise(0, 2, nullptr, true, {}, &setup);

        if (result.isNotEmpty())
            DBG("AudioEngine: fallback init also failed: " + result);
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
}

void AudioEngine::togglePlayStop()
{
    if (midiEngine.isPlaying()) stop(); else play();
}

void AudioEngine::rewind()
{
    midiEngine.setPositionBeats(0.0);
    synthEngine.allNotesOff();
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
    const float* const*, int,
    float* const* outputChannelData, int numOutputChannels,
    int numSamples, const juce::AudioIODeviceCallbackContext&)
{
    const int outCh = juce::jmax(1, numOutputChannels);

    // Clear output
    for (int ch = 0; ch < numOutputChannels; ++ch)
        if (outputChannelData[ch])
            juce::FloatVectorOperations::clear(outputChannelData[ch], numSamples);

    // X1 — drain MIDI input collector and write into the armed track's clip.
    // Still touches MidiMessageSequence from the audio thread (GUI readers
    // are short-lived and only during paint); acceptable tradeoff without
    // a full message queue to the GUI.
    {
        juce::MidiBuffer inBuf;
        midiInputCollector.removeNextBlockOfMessages(inBuf, numSamples);
        if (! inBuf.isEmpty()
            && recordingTrackId >= 0
            && midiEngine.isPlaying())
        {
            if (auto* rt = trackModel.getTrack(recordingTrackId))
            {
                if (rt->armed && ! rt->clips.empty())
                {
                    auto& clip = rt->clips.back();
                    const double posBeat = midiEngine.getPositionBeats();
                    const double bps = midiEngine.getTempo() / 60.0;

                    // Z6 + AA4 — subtract device latency + user-specified
                    // MIDI input port latency so recorded events align with
                    // what the performer heard.
                    double latencySec = 0.0;
                    if (auto* dev = deviceManager.getCurrentAudioDevice())
                    {
                        const int outLatency = dev->getOutputLatencyInSamples();
                        const int inLatency  = dev->getInputLatencyInSamples();
                        latencySec = (outLatency + inLatency) / currentSampleRate;
                    }
                    latencySec += midiInputLatencyMs / 1000.0; // AA4
                    const double latencyBeats = latencySec * bps;

                    for (const auto meta : inBuf)
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

        // Filter MIDI to this track's channel
        juce::MidiBuffer trackMidi;
        for (const auto meta : midiBuf)
        {
            auto msg = meta.getMessage();
            if (msg.getChannel() != track.midiChannel) continue;
            trackMidi.addEvent(msg, meta.samplePosition);
        }

        // Render MIDI → trackBuf via per-track synth (S1 — no cross-talk)
        trackBuf.clear();
        getOrCreateTrackSynth(track.id).renderBlock(trackBuf, trackMidi);

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

                const double srRatio = clip.sourceSampleRate / currentSampleRate;
                const int dstChannels = juce::jmin(trackBuf.getNumChannels(), clip.buffer.getNumChannels());
                const juce::int64 srcLen = clip.buffer.getNumSamples();
                for (int ch = 0; ch < dstChannels; ++ch)
                {
                    auto* src = clip.buffer.getReadPointer(ch);
                    auto* dst = trackBuf.getWritePointer(ch);
                    // U4 — 4-tap Catmull-Rom (Hermite) cubic interpolation
                    for (int s = 0; s < numSamples; ++s)
                    {
                        const double srcPos = (double)srcStart + (double)s * srRatio;
                        const juce::int64 i1 = (juce::int64)std::floor(srcPos);
                        const juce::int64 i0 = i1 - 1;
                        const juce::int64 i2 = i1 + 1;
                        const juce::int64 i3 = i1 + 2;
                        if (i0 < 0 || i3 >= srcLen) continue;

                        const float t  = (float)(srcPos - (double)i1);
                        const float y0 = src[(int)i0];
                        const float y1 = src[(int)i1];
                        const float y2 = src[(int)i2];
                        const float y3 = src[(int)i3];

                        // Catmull-Rom polynomial
                        const float a = -0.5f*y0 + 1.5f*y1 - 1.5f*y2 + 0.5f*y3;
                        const float b =  y0 - 2.5f*y1 + 2.0f*y2 - 0.5f*y3;
                        const float c = -0.5f*y0 + 0.5f*y2;
                        const float d =  y1;
                        dst[s] += ((a*t + b)*t + c)*t + d;
                    }
                }
            }
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

        // U3 — post-fader sends. Adds a scaled copy of trackBuf to each send bus.
        for (auto& snd : track.sends)
        {
            if (snd.level <= 0.0f) continue;
            if (snd.busId == 0) continue; // sending to master = duplicate path
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
            metronomeIsDownbeat = (std::fmod(beatsAfter, 4.0) < 1.0);
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
}

void AudioEngine::audioDeviceStopped()
{
    currentSampleRate = 44100.0;
}
