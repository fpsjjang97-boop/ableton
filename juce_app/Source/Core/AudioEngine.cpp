/*
  ==============================================================================

    AudioEngine.cpp
    MIDI AI Workstation - Core Audio Engine

  ==============================================================================
*/

#include "AudioEngine.h"
#include "TrackProcessor.h"
#include "SynthEngine.h"

//==============================================================================
AudioEngine::AudioEngine()
{
    synthEngine = std::make_unique<SynthEngine>();
}

AudioEngine::~AudioEngine()
{
    releaseResources();
}

//==============================================================================
void AudioEngine::prepareToPlay (int samplesPerBlockExpected, double newSampleRate)
{
    sampleRate     = newSampleRate;
    samplesPerBlock = samplesPerBlockExpected;

    synthEngine->prepareToPlay (newSampleRate, samplesPerBlockExpected);

    metronomeSamplesRemaining = 0;
    metronomePhase = 0.0f;
}

void AudioEngine::releaseResources()
{
    synthEngine->allNotesOff();
}

void AudioEngine::getNextAudioBlock (const juce::AudioSourceChannelInfo& bufferToFill)
{
    bufferToFill.clearActiveBufferRegion();

    if (! playing.load())
        return;

    auto* buffer = bufferToFill.buffer;
    const int numSamples   = bufferToFill.numSamples;
    const int startSample  = bufferToFill.startSample;

    // ===== TEST TONE: 440Hz sine to verify audio pipeline works =====
    // Remove this block once audio is confirmed working.
    {
        static double testPhase = 0.0;
        double testFreq = 440.0;
        double testInc = testFreq / sampleRate;
        for (int i = 0; i < numSamples; ++i)
        {
            float s = 0.2f * static_cast<float>(std::sin(testPhase * 2.0 * juce::MathConstants<double>::pi));
            for (int ch = 0; ch < buffer->getNumChannels(); ++ch)
                buffer->addSample(ch, startSample + i, s);
            testPhase += testInc;
            if (testPhase >= 1.0) testPhase -= 1.0;
        }
    }
    // ===== END TEST TONE =====
    const double currentBpm = bpm.load();

    // Calculate beat range for this block
    double blockStartSamples = currentPositionInSamples.load();
    double blockStartBeat    = samplesToBeats (blockStartSamples);
    double blockEndSamples   = blockStartSamples + numSamples;
    double blockEndBeat      = samplesToBeats (blockEndSamples);

    // Handle looping: if we cross the loop end, wrap around
    const bool isLooping     = looping.load();
    const double loopStart   = loopStartBeat.load();
    const double loopEnd     = loopEndBeat.load();

    if (isLooping && blockEndBeat > loopEnd && loopEnd > loopStart)
    {
        // Process in two segments: before loop end, after wrap
        double loopEndInSamples = beatsToSamples (loopEnd);
        int samplesBeforeLoop   = static_cast<int> (loopEndInSamples - blockStartSamples);

        if (samplesBeforeLoop < 0)
            samplesBeforeLoop = 0;

        if (samplesBeforeLoop > numSamples)
            samplesBeforeLoop = numSamples;

        // --- First segment: up to loop end ---
        if (samplesBeforeLoop > 0)
        {
            juce::MidiBuffer combinedMidi;

            {
                const juce::ScopedLock sl (lock);

                for (auto& track : tracks)
                {
                    if (track == nullptr || track->muted)
                        continue;

                    auto trackMidi = track->getMidiEventsInRange (
                        blockStartBeat, loopEnd, sampleRate, currentBpm);

                    for (const auto metadata : trackMidi)
                        combinedMidi.addEvent (metadata.getMessage(), metadata.samplePosition);
                }
            }

            // Forward to external MIDI output if connected
            if (midiOutput != nullptr)
            {
                for (const auto metadata : combinedMidi)
                    midiOutput->sendMessageNow (metadata.getMessage());
            }

            synthEngine->renderNextBlock (*buffer, combinedMidi, startSample, samplesBeforeLoop);
        }

        // --- Wrap position to loop start ---
        double wrappedSamples = beatsToSamples (loopStart);
        double wrappedBeat    = loopStart;
        double remainingBeats = samplesToBeats (static_cast<double> (numSamples - samplesBeforeLoop));
        double wrappedEndBeat = wrappedBeat + remainingBeats;
        int samplesAfterLoop  = numSamples - samplesBeforeLoop;

        // Notify synth to stop lingering notes at loop boundary
        synthEngine->allNotesOff();

        if (samplesAfterLoop > 0)
        {
            juce::MidiBuffer combinedMidi;

            {
                const juce::ScopedLock sl (lock);

                for (auto& track : tracks)
                {
                    if (track == nullptr || track->muted)
                        continue;

                    auto trackMidi = track->getMidiEventsInRange (
                        wrappedBeat, wrappedEndBeat, sampleRate, currentBpm);

                    // Offset sample positions to account for the first segment
                    juce::MidiBuffer offsetMidi;
                    for (const auto metadata : trackMidi)
                        offsetMidi.addEvent (metadata.getMessage(),
                                             metadata.samplePosition + samplesBeforeLoop);

                    for (const auto metadata : offsetMidi)
                        combinedMidi.addEvent (metadata.getMessage(), metadata.samplePosition);
                }
            }

            if (midiOutput != nullptr)
            {
                for (const auto metadata : combinedMidi)
                    midiOutput->sendMessageNow (metadata.getMessage());
            }

            synthEngine->renderNextBlock (*buffer, combinedMidi,
                                          startSample + samplesBeforeLoop, samplesAfterLoop);
        }

        // Generate metronome for the full block (using the beat range before wrap)
        if (metronomeEnabled.load())
            generateMetronomeClick (*buffer, startSample, numSamples,
                                    blockStartBeat, blockStartBeat + samplesToBeats (numSamples));

        // Update position: loop start + however far we went past it
        currentPositionInSamples.store (wrappedSamples + (numSamples - samplesBeforeLoop));
    }
    else
    {
        // --- Normal (non-wrapping) block ---
        juce::MidiBuffer combinedMidi;

        {
            const juce::ScopedLock sl (lock);

            // Check for solo: if any track is soloed, only play soloed tracks
            bool anySolo = false;
            for (const auto& track : tracks)
            {
                if (track != nullptr && track->solo)
                {
                    anySolo = true;
                    break;
                }
            }

            for (auto& track : tracks)
            {
                if (track == nullptr)
                    continue;

                if (track->muted)
                    continue;

                if (anySolo && ! track->solo)
                    continue;

                auto trackMidi = track->getMidiEventsInRange (
                    blockStartBeat, blockEndBeat, sampleRate, currentBpm);

                for (const auto metadata : trackMidi)
                    combinedMidi.addEvent (metadata.getMessage(), metadata.samplePosition);
            }
        }

        // Forward to external MIDI output
        if (midiOutput != nullptr)
        {
            for (const auto metadata : combinedMidi)
                midiOutput->sendMessageNow (metadata.getMessage());
        }

        // Debug: log first few blocks
        static int debugCount = 0;
        if (debugCount < 10 && ! combinedMidi.isEmpty())
        {
            DBG ("AudioBlock: beat " << blockStartBeat << "-" << blockEndBeat
                 << " midiEvents=" << combinedMidi.getNumEvents());
            debugCount++;
        }

        // Render synth audio
        synthEngine->renderNextBlock (*buffer, combinedMidi, startSample, numSamples);

        // Generate metronome
        if (metronomeEnabled.load())
            generateMetronomeClick (*buffer, startSample, numSamples,
                                    blockStartBeat, blockEndBeat);

        // Advance position
        currentPositionInSamples.store (blockEndSamples);
    }

    // Apply master volume
    const float vol = masterVolume.load();
    if (std::abs (vol - 1.0f) > 0.0001f)
    {
        buffer->applyGain (startSample, numSamples, vol);
    }
}

//==============================================================================
// Transport
//==============================================================================

void AudioEngine::play()
{
    // Set program change for each track's instrument
    {
        const juce::ScopedLock sl (lock);
        for (auto& track : tracks)
        {
            if (track != nullptr)
                synthEngine->setProgram (track->channel, track->instrument);
        }
    }
    playing.store (true);
}

void AudioEngine::stop()
{
    playing.store (false);
    currentPositionInSamples.store (0.0);
    synthEngine->allNotesOff();
}

void AudioEngine::pause()
{
    playing.store (false);
    synthEngine->allNotesOff();
}

void AudioEngine::setPosition (double positionInBeats)
{
    currentPositionInSamples.store (beatsToSamples (positionInBeats));
    synthEngine->allNotesOff();
}

double AudioEngine::getPositionInBeats() const
{
    return samplesToBeats (currentPositionInSamples.load());
}

double AudioEngine::getPositionInSeconds() const
{
    return currentPositionInSamples.load() / sampleRate;
}

bool AudioEngine::isPlaying() const
{
    return playing.load();
}

//==============================================================================
// Settings
//==============================================================================

void AudioEngine::setBPM (double newBpm)
{
    // Clamp to reasonable range
    newBpm = juce::jlimit (20.0, 999.0, newBpm);

    // Maintain current beat position when BPM changes
    double currentBeat = getPositionInBeats();
    bpm.store (newBpm);
    currentPositionInSamples.store (beatsToSamples (currentBeat));
}

double AudioEngine::getBPM() const
{
    return bpm.load();
}

void AudioEngine::setTimeSignature (int numerator, int denominator)
{
    const juce::ScopedLock sl (lock);
    timeSignatureNum = juce::jlimit (1, 32, numerator);
    timeSignatureDen = juce::jlimit (1, 32, denominator);
}

void AudioEngine::setLooping (bool shouldLoop, double loopStart, double loopEnd)
{
    loopStartBeat.store (loopStart);
    loopEndBeat.store (loopEnd);
    looping.store (shouldLoop);
}

//==============================================================================
// Track management
//==============================================================================

void AudioEngine::addTrack (std::shared_ptr<TrackProcessor> track)
{
    const juce::ScopedLock sl (lock);
    tracks.push_back (std::move (track));
}

void AudioEngine::removeTrack (int index)
{
    const juce::ScopedLock sl (lock);

    if (index >= 0 && index < static_cast<int> (tracks.size()))
        tracks.erase (tracks.begin() + index);
}

int AudioEngine::getNumTracks() const
{
    const juce::ScopedLock sl (lock);
    return static_cast<int> (tracks.size());
}

TrackProcessor* AudioEngine::getTrack (int index) const
{
    const juce::ScopedLock sl (lock);

    if (index >= 0 && index < static_cast<int> (tracks.size()))
        return tracks[static_cast<size_t> (index)].get();

    return nullptr;
}

//==============================================================================
// Master
//==============================================================================

void AudioEngine::setMasterVolume (float volume)
{
    masterVolume.store (juce::jlimit (0.0f, 2.0f, volume));
}

float AudioEngine::getMasterVolume() const
{
    return masterVolume.load();
}

//==============================================================================
// MIDI output
//==============================================================================

void AudioEngine::setMidiOutput (juce::MidiOutput* output)
{
    const juce::ScopedLock sl (lock);
    midiOutput = output;
}

//==============================================================================
// Metronome
//==============================================================================

void AudioEngine::setMetronomeEnabled (bool enabled)
{
    metronomeEnabled.store (enabled);
}

bool AudioEngine::isMetronomeEnabled() const
{
    return metronomeEnabled.load();
}

//==============================================================================
// Private helpers
//==============================================================================

double AudioEngine::beatsToSamples (double beats) const
{
    // beats * (seconds/beat) * (samples/second)
    // seconds/beat = 60 / bpm
    return beats * (60.0 / bpm.load()) * sampleRate;
}

double AudioEngine::samplesToBeats (double samples) const
{
    // samples * (seconds/sample) * (beats/second)
    // beats/second = bpm / 60
    return samples / sampleRate * (bpm.load() / 60.0);
}

void AudioEngine::generateMetronomeClick (juce::AudioBuffer<float>& buffer,
                                           int startSample, int numSamples,
                                           double blockStartBeat, double blockEndBeat)
{
    // Duration of a click in samples (~30ms)
    const int clickDurationSamples = static_cast<int> (sampleRate * 0.030);
    const float clickVolume = 0.35f;

    // Check each beat boundary in this block
    int firstBeat = static_cast<int> (std::ceil (blockStartBeat));
    int lastBeat  = static_cast<int> (std::floor (blockEndBeat));

    for (int beat = firstBeat; beat <= lastBeat; ++beat)
    {
        if (static_cast<double> (beat) < blockStartBeat
            || static_cast<double> (beat) > blockEndBeat)
            continue;

        // Sample offset of this beat within the block
        double beatSamples = beatsToSamples (static_cast<double> (beat));
        double blockStartInSamples = beatsToSamples (blockStartBeat);
        int offsetInBlock = static_cast<int> (beatSamples - blockStartInSamples);

        if (offsetInBlock < 0 || offsetInBlock >= numSamples)
            continue;

        // Determine if this is a downbeat (accent)
        bool isDownbeat = (beat % timeSignatureNum) == 0;
        float freq = isDownbeat ? 1500.0f : 1000.0f;
        float vol  = isDownbeat ? clickVolume * 1.4f : clickVolume;

        // Synthesize click directly into buffer
        int clickSamples = juce::jmin (clickDurationSamples,
                                        numSamples - offsetInBlock);
        float phase = 0.0f;
        float phaseIncrement = freq / static_cast<float> (sampleRate);

        for (int s = 0; s < clickSamples; ++s)
        {
            // Sine wave with exponential decay envelope
            float envelope = std::exp (-static_cast<float> (s) / (static_cast<float> (clickDurationSamples) * 0.3f));
            float sample   = std::sin (2.0f * juce::MathConstants<float>::pi * phase) * envelope * vol;
            phase += phaseIncrement;

            if (phase >= 1.0f)
                phase -= 1.0f;

            int bufferIndex = startSample + offsetInBlock + s;

            for (int ch = 0; ch < buffer.getNumChannels(); ++ch)
                buffer.addSample (ch, bufferIndex, sample);
        }
    }
}
