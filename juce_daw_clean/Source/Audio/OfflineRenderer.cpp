#include "OfflineRenderer.h"
#include <map>
#include <memory>

bool OfflineRenderer::renderToWav(TrackModel& tracks,
                                  double tempoBpm,
                                  double lengthBeats,
                                  double sampleRate,
                                  const juce::File& wavFile,
                                  juce::String& errorOut,
                                  int blockSize,
                                  TrackPluginChain* pluginChains,
                                  BusModel* busModel)
{
    errorOut.clear();

    if (lengthBeats <= 0.0)
    { errorOut = "lengthBeats must be > 0"; return false; }
    if (sampleRate <= 0.0)
    { errorOut = "sampleRate must be > 0"; return false; }

    wavFile.deleteFile();
    wavFile.getParentDirectory().createDirectory();

    auto fos = std::make_unique<juce::FileOutputStream>(wavFile);
    if (! fos->openedOk())
    { errorOut = "Cannot open output file: " + wavFile.getFullPathName(); return false; }

    juce::WavAudioFormat wav;
    std::unique_ptr<juce::AudioFormatWriter> writer(
        wav.createWriterFor(fos.get(), sampleRate, 2, 16, {}, 0));

    if (writer == nullptr)
    { errorOut = "Failed to create WAV writer"; return false; }
    fos.release(); // writer takes ownership

    // Set up engine in offline mode.
    MidiEngine midi;
    midi.setTrackModel(&tracks);
    midi.setTempo(tempoBpm);
    midi.setPositionBeats(0.0);
    midi.setPlaying(true);

    // T3 — per-track synths to mirror live audio path
    std::map<int, std::unique_ptr<SynthEngine>> trackSynths;
    auto getSynth = [&](int trackId) -> SynthEngine& {
        auto it = trackSynths.find(trackId);
        if (it != trackSynths.end()) return *it->second;
        auto s = std::make_unique<SynthEngine>();
        s->prepare(sampleRate, blockSize);
        auto& ref = *s;
        trackSynths.emplace(trackId, std::move(s));
        return ref;
    };
    if (pluginChains != nullptr)
        pluginChains->prepareAll(sampleRate, blockSize);

    const double beatsPerSample = tempoBpm / (60.0 * sampleRate);
    const juce::int64 totalSamples =
        (juce::int64)std::ceil(lengthBeats / beatsPerSample);

    juce::AudioBuffer<float> mixBuf(2, blockSize);
    juce::AudioBuffer<float> trackBuf(2, blockSize);
    std::map<int, juce::AudioBuffer<float>> busBufs; // V3 — per-bus accumulators
    juce::MidiBuffer midiBuf;

    juce::int64 written = 0;
    double curBeat = 0.0;
    while (written < totalSamples)
    {
        const int thisBlock = (int)juce::jmin((juce::int64)blockSize,
                                              totalSamples - written);
        mixBuf.setSize(2, thisBlock, false, false, true);
        trackBuf.setSize(2, thisBlock, false, false, true);
        mixBuf.clear();
        midiBuf.clear();

        midi.processBlock(thisBlock, sampleRate, midiBuf);

        bool anySolo = false;
        for (auto& t : tracks.getTracks()) if (t.solo) { anySolo = true; break; }

        for (auto& track : tracks.getTracks())
        {
            if (track.mute) continue;
            if (anySolo && ! track.solo) continue;

            // Apply automation (volume/pan) at curBeat
            float effVol = track.volume, effPan = track.pan;
            for (auto& lane : track.automation)
            {
                if (! lane.enabled || lane.points.empty()) continue;
                if (lane.paramId == "volume") effVol = lane.valueAt(curBeat, effVol);
                else if (lane.paramId == "pan") effPan = lane.valueAt(curBeat, (effPan + 1.0f) * 0.5f) * 2.0f - 1.0f;
            }
            effVol = juce::jlimit(0.0f, 4.0f, effVol);
            effPan = juce::jlimit(-1.0f, 1.0f, effPan);

            juce::MidiBuffer trackMidi;
            for (const auto meta : midiBuf)
            {
                auto msg = meta.getMessage();
                if (msg.getChannel() != track.midiChannel) continue;
                trackMidi.addEvent(msg, meta.samplePosition);
            }

            trackBuf.clear();
            getSynth(track.id).renderBlock(trackBuf, trackMidi);

            const float panL = std::cos((effPan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
            const float panR = std::sin((effPan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
            trackBuf.applyGain(0, 0, thisBlock, effVol * panL);
            trackBuf.applyGain(1, 0, thisBlock, effVol * panR);

            if (pluginChains && ! track.plugins.empty())
            {
                juce::MidiBuffer fxMidi;
                pluginChains->processTrack(track.id, track, trackBuf, fxMidi);
            }

            // V3 — route to bus (0 = master)
            int targetBus = track.outputBusId;
            if (busModel && targetBus != 0 && busModel->getBus(targetBus) == nullptr)
                targetBus = 0;

            if (busModel && targetBus != 0)
            {
                auto& b = busBufs[targetBus];
                if (b.getNumChannels() != 2 || b.getNumSamples() != thisBlock)
                    b.setSize(2, thisBlock, false, false, true);
                for (int ch = 0; ch < 2; ++ch)
                    b.addFrom(ch, 0, trackBuf, ch, 0, thisBlock);
            }
            else
            {
                for (int ch = 0; ch < 2; ++ch)
                    mixBuf.addFrom(ch, 0, trackBuf, ch, 0, thisBlock);
            }

            // V3 — post-fader sends
            if (busModel)
            {
                for (auto& snd : track.sends)
                {
                    if (snd.level <= 0.0f || snd.busId == 0) continue;
                    if (busModel->getBus(snd.busId) == nullptr) continue;
                    auto& b = busBufs[snd.busId];
                    if (b.getNumChannels() != 2 || b.getNumSamples() != thisBlock)
                        b.setSize(2, thisBlock, false, false, true);
                    for (int ch = 0; ch < 2; ++ch)
                        b.addFrom(ch, 0, trackBuf, ch, 0, thisBlock, snd.level);
                }
            }
        }

        // V3 — apply bus vol/pan/mute, sum into mixBuf (master)
        if (busModel)
        {
            for (auto& bus : busModel->getBuses())
            {
                if (bus.id == 0) continue;
                auto it = busBufs.find(bus.id);
                if (it == busBufs.end()) continue;
                auto& b = it->second;
                if (bus.mute) { b.clear(); continue; }
                const float panL = std::cos((bus.pan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
                const float panR = std::sin((bus.pan + 1.0f) * 0.25f * juce::MathConstants<float>::pi);
                b.applyGain(0, 0, thisBlock, bus.volume * panL);
                b.applyGain(1, 0, thisBlock, bus.volume * panR);
                for (int ch = 0; ch < 2; ++ch)
                    mixBuf.addFrom(ch, 0, b, ch, 0, thisBlock);
                b.clear();
            }
        }

        if (! writer->writeFromAudioSampleBuffer(mixBuf, 0, thisBlock))
        { errorOut = "WAV write failed at sample " + juce::String(written); return false; }

        written += thisBlock;
        curBeat  += thisBlock * beatsPerSample;
    }

    writer->flush();
    return true;
}
