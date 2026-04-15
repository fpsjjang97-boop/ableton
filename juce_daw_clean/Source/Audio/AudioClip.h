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

    bool isEmpty() const { return buffer.getNumSamples() == 0; }
};
