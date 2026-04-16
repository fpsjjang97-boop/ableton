/*
 * MidiGPT DAW — AudioClip
 *
 * Audio counterpart to MidiClip. Holds decoded sample buffer (float, stereo)
 * + start position in beats + length in beats. Audio file import goes
 * through MainWindow::loadAudioFile which uses AudioFormatManager to read
 * wav/aif/mp3 into an AudioBuffer<float> stored here.
 *
 * Sample rate stored separately so playback can resample if device SR
 * differs (Sprint 2 — Sprint 1 assumes match).
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

struct AudioClip
{
    double  startBeat   { 0.0 };
    double  lengthBeats { 0.0 };
    double  sourceSampleRate { 44100.0 };
    juce::AudioBuffer<float> buffer;  // [channels][samples]

    /** W5 — sample offset inside `buffer` where playback starts. Allows
     *  non-destructive trim: keep the full decoded buffer but begin
     *  playback from a later sample. Default 0 (play from start). */
    juce::int64 sourceOffsetSamples { 0 };

    /** DD2 — fade in/out in beats. Applied as linear gain ramp during playback. */
    double fadeInBeats  { 0.0 };
    double fadeOutBeats { 0.0 };

    /** DD2 — compute fade gain at a given beat position within the clip (0-based). */
    float fadeGainAt(double beatInClip) const
    {
        float gain = 1.0f;
        if (fadeInBeats > 0.0 && beatInClip < fadeInBeats)
            gain *= (float)(beatInClip / fadeInBeats);
        if (fadeOutBeats > 0.0 && beatInClip > lengthBeats - fadeOutBeats)
            gain *= (float)((lengthBeats - beatInClip) / fadeOutBeats);
        return juce::jlimit(0.0f, 1.0f, gain);
    }

    /** PP1 — pitch shift in semitones (-24..+24). Implemented via playback rate change. */
    float pitchSemitones { 0.0f };
    /** PP1 — playback rate multiplier (0.25..4.0). 1.0 = original speed. */
    double playbackRate { 1.0 };

    /** PP1 — effective sample rate ratio including pitch and rate adjustments. */
    double effectiveSrRatio(double deviceSr) const
    {
        if (deviceSr <= 0.0) return 1.0; // D1 — guard division by zero
        double rate = juce::jlimit(0.25, 4.0, playbackRate);
        if (std::abs(pitchSemitones) > 0.01f)
            rate *= std::pow(2.0, pitchSemitones / 12.0);
        return (sourceSampleRate * rate) / deviceSr;
    }

    /** LL6 — source file name for display in arrangement view. */
    juce::String sourceName;

    bool isEmpty() const { return buffer.getNumSamples() == 0; }
};
