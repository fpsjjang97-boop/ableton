/*
 * MidiGPT DAW — MIDI transforms
 *
 * Self-contained header of note-level sequence transforms. Each function
 * operates on a juce::MidiMessageSequence in place and honors an optional
 * selection (event indices). If selection is empty, the transform applies
 * to every note-on/note-off pair in the sequence.
 *
 * All transforms keep note-on/note-off pairs consistent by calling
 * updateMatchedPairs() after mutation.
 *
 * Scope:
 *   - reverse: time-reverse around the sequence center (or selection range)
 *   - invert:  pitch-invert around a pivot (default = selection median)
 *   - transpose: shift pitches by N semitones (clamped to 0..127)
 *   - humanize: apply small random timing + velocity jitter
 */

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <random>
#include <vector>
#include <algorithm>

namespace MidiTransforms
{
    inline bool isTarget (int i, const std::vector<int>& sel)
    {
        if (sel.empty()) return true;
        for (int s : sel) if (s == i) return true;
        return false;
    }

    /** Time-reverse within [rangeStart, rangeEnd). If the range is empty
     *  (end <= start), uses the full extent of the selected / all notes.
     *  Note durations are preserved (reflect onset across the midpoint,
     *  then push onset back by duration so the note still ends inside
     *  the range). */
    inline void reverse (juce::MidiMessageSequence& seq,
                         const std::vector<int>& selection = {},
                         double rangeStart = 0.0,
                         double rangeEnd   = -1.0)
    {
        // Compute bounds if not supplied.
        if (rangeEnd <= rangeStart)
        {
            bool found = false;
            double minB = 0.0, maxB = 0.0;
            for (int i = 0; i < seq.getNumEvents(); ++i)
            {
                if (! isTarget (i, selection)) continue;
                auto* e = seq.getEventPointer (i);
                if (! e->message.isNoteOn()) continue;
                const double t0 = e->message.getTimeStamp();
                const double t1 = e->noteOffObject
                                      ? e->noteOffObject->message.getTimeStamp()
                                      : t0 + 0.25;
                if (! found) { minB = t0; maxB = t1; found = true; }
                else { minB = juce::jmin (minB, t0); maxB = juce::jmax (maxB, t1); }
            }
            if (! found) return;
            rangeStart = minB;
            rangeEnd   = maxB;
        }

        const double span = rangeEnd - rangeStart;
        if (span <= 0.0) return;

        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            if (! isTarget (i, selection)) continue;
            auto* e = seq.getEventPointer (i);
            if (! e->message.isNoteOn()) continue;

            const double t0 = e->message.getTimeStamp();
            const double t1 = e->noteOffObject
                                  ? e->noteOffObject->message.getTimeStamp()
                                  : t0 + 0.25;
            const double dur = juce::jmax (0.0625, t1 - t0);

            // New onset so that the note still ends inside the range.
            const double newT0 = rangeStart + (rangeEnd - t1);
            e->message.setTimeStamp (newT0);
            if (e->noteOffObject != nullptr)
                e->noteOffObject->message.setTimeStamp (newT0 + dur);
        }

        seq.updateMatchedPairs();
        seq.sort();
    }

    /** Pitch-invert around a pivot. If pivotPitch < 0, uses the median
     *  of the selected (or all) note-on pitches. Resulting pitches are
     *  clamped to [0, 127]; out-of-range notes are dropped rather than
     *  wrapped. */
    inline void invert (juce::MidiMessageSequence& seq,
                        const std::vector<int>& selection = {},
                        int pivotPitch = -1)
    {
        if (pivotPitch < 0)
        {
            std::vector<int> pitches;
            for (int i = 0; i < seq.getNumEvents(); ++i)
            {
                if (! isTarget (i, selection)) continue;
                auto* e = seq.getEventPointer (i);
                if (e->message.isNoteOn())
                    pitches.push_back (e->message.getNoteNumber());
            }
            if (pitches.empty()) return;
            std::sort (pitches.begin(), pitches.end());
            pivotPitch = pitches[pitches.size() / 2];
        }

        for (int i = seq.getNumEvents() - 1; i >= 0; --i)
        {
            if (! isTarget (i, selection)) continue;
            auto* e = seq.getEventPointer (i);
            if (! (e->message.isNoteOn() || e->message.isNoteOff())) continue;

            const int oldN = e->message.getNoteNumber();
            const int newN = 2 * pivotPitch - oldN;
            if (newN < 0 || newN > 127)
            {
                if (e->message.isNoteOn())
                    seq.deleteEvent (i, true);
                continue;
            }
            e->message.setNoteNumber (newN);
        }

        seq.updateMatchedPairs();
        seq.sort();
    }

    /** Transpose by `semitones`. Out-of-range notes are dropped. */
    inline void transpose (juce::MidiMessageSequence& seq,
                           int semitones,
                           const std::vector<int>& selection = {})
    {
        if (semitones == 0) return;

        for (int i = seq.getNumEvents() - 1; i >= 0; --i)
        {
            if (! isTarget (i, selection)) continue;
            auto* e = seq.getEventPointer (i);
            if (! (e->message.isNoteOn() || e->message.isNoteOff())) continue;

            const int n = e->message.getNoteNumber() + semitones;
            if (n < 0 || n > 127)
            {
                if (e->message.isNoteOn())
                    seq.deleteEvent (i, true);
                continue;
            }
            e->message.setNoteNumber (n);
        }

        seq.updateMatchedPairs();
    }

    /** Apply small random jitter to timing (beats) and velocity.
     *  timingJitterBeats = max absolute shift; velJitter = max delta
     *  (0..1 where 1.0 = ±127). Uses a deterministic seed derived from
     *  the sequence pointer so repeated calls behave differently but
     *  reproducibly within a session. */
    inline void humanize (juce::MidiMessageSequence& seq,
                          double timingJitterBeats,
                          float  velJitter,
                          const std::vector<int>& selection = {},
                          unsigned seed = 0)
    {
        if (timingJitterBeats <= 0.0 && velJitter <= 0.0f) return;

        std::mt19937 rng (seed != 0 ? seed
                                    : (unsigned) (size_t) (&seq));
        std::uniform_real_distribution<double> tDist (-timingJitterBeats,
                                                       timingJitterBeats);
        std::uniform_real_distribution<float>  vDist (-velJitter, velJitter);

        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            if (! isTarget (i, selection)) continue;
            auto* e = seq.getEventPointer (i);
            if (! e->message.isNoteOn()) continue;

            if (timingJitterBeats > 0.0)
            {
                const double delta = tDist (rng);
                const double t0    = e->message.getTimeStamp();
                const double newT  = juce::jmax (0.0, t0 + delta);
                e->message.setTimeStamp (newT);
                if (e->noteOffObject != nullptr)
                {
                    const double t1 = e->noteOffObject->message.getTimeStamp();
                    e->noteOffObject->message.setTimeStamp (t1 + (newT - t0));
                }
            }

            if (velJitter > 0.0f)
            {
                const int oldVel = e->message.getVelocity();
                const float delta = vDist (rng);
                const int newVel = juce::jlimit (1, 127,
                    (int) std::round ((float) oldVel + delta * 127.0f));
                e->message.setVelocity ((float) newVel / 127.0f);
            }
        }

        seq.updateMatchedPairs();
        seq.sort();
    }
}
