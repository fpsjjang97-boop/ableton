/*
 * MidiGPT DAW — Groove template
 *
 * Per-step timing + velocity offsets that can be stamped onto a MidiClip
 * to give a mechanical grid "feel". Modeled after the MPC / Linn-drum
 * groove templates that every modern DAW (Ableton, Logic, FL) carries.
 *
 * stepsPerBar   = grid resolution (e.g. 16 for 16th-note grooves)
 * timingOffsets = signed fraction of a step. +0.5 on a step means the
 *                 note lands halfway to the next step; -0.25 pulls it
 *                 earlier. Clamped to [-0.5, +0.5] inside apply().
 * velocityFactor= per-step multiplier for velocity (1.0 = unchanged).
 *
 * Templates are content, not code — adding a new one is "append to
 * registry()". MVP ships four: Straight (no-op baseline for testing),
 * MPC 16 Swing 55, Linn 8 Shuffle, Hard Shuffle 8.
 */

#pragma once

#include <juce_core/juce_core.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include "TrackModel.h"
#include <vector>

struct GrooveTemplate
{
    juce::String       name;
    int                stepsPerBar   { 16 };
    std::vector<float> timingOffsets;    // size == stepsPerBar
    std::vector<float> velocityFactor;   // size == stepsPerBar

    static const std::vector<GrooveTemplate>& registry()
    {
        static const std::vector<GrooveTemplate> list = []
        {
            std::vector<GrooveTemplate> r;

            GrooveTemplate straight;
            straight.name = "Straight";
            straight.stepsPerBar   = 16;
            straight.timingOffsets.assign (16, 0.0f);
            straight.velocityFactor.assign (16, 1.0f);
            r.push_back (straight);

            // MPC 55% swing: odd 16ths pushed ~10% of a step, slightly
            // softer than even 16ths. Standard hip-hop groove.
            GrooveTemplate mpc;
            mpc.name = "MPC 16 Swing 55";
            mpc.stepsPerBar = 16;
            mpc.timingOffsets.assign (16, 0.0f);
            mpc.velocityFactor.assign (16, 1.0f);
            for (int i = 1; i < 16; i += 2)
            {
                mpc.timingOffsets[(size_t)i]  = 0.10f;
                mpc.velocityFactor[(size_t)i] = 0.88f;
            }
            r.push_back (mpc);

            // Linn 8 shuffle: classic drum-machine 8th-note swing.
            GrooveTemplate linn;
            linn.name = "Linn 8 Shuffle";
            linn.stepsPerBar = 8;
            linn.timingOffsets.assign (8, 0.0f);
            linn.velocityFactor.assign (8, 1.0f);
            for (int i = 1; i < 8; i += 2)
            {
                linn.timingOffsets[(size_t)i]  = 0.18f;
                linn.velocityFactor[(size_t)i] = 0.92f;
            }
            r.push_back (linn);

            // Hard 8 shuffle — heavier push, weaker offbeats. Funk feel.
            GrooveTemplate hard;
            hard.name = "Hard Shuffle 8";
            hard.stepsPerBar = 8;
            hard.timingOffsets.assign (8, 0.0f);
            hard.velocityFactor.assign (8, 1.0f);
            for (int i = 1; i < 8; i += 2)
            {
                hard.timingOffsets[(size_t)i]  = 0.28f;
                hard.velocityFactor[(size_t)i] = 0.78f;
            }
            r.push_back (hard);

            return r;
        }();
        return list;
    }

    static const GrooveTemplate* findByName (const juce::String& n)
    {
        for (auto& g : registry())
            if (g.name == n) return &g;
        return nullptr;
    }

    /** Stamp this groove onto `seq` over the range [startBeat, startBeat+lengthBeats).
     *  strength 0..1 scales both timing and velocity deltas.
     *  beatsPerBar comes from the project time signature (numerator).
     *  selection: if non-empty, only those event indices are affected;
     *  otherwise all note-on events in range are affected. */
    void apply (juce::MidiMessageSequence& seq,
                double startBeat,
                double lengthBeats,
                double strength,
                const std::vector<int>& selection = {},
                double beatsPerBar = 4.0) const
    {
        if (timingOffsets.empty() || velocityFactor.empty()) return;
        strength = juce::jlimit (0.0, 1.0, strength);
        if (strength <= 0.0) return;

        const double stepBeats = beatsPerBar / (double) stepsPerBar;
        if (stepBeats <= 0.0) return;

        auto eligible = [&] (int i)
        {
            if (selection.empty()) return true;
            for (int s : selection) if (s == i) return true;
            return false;
        };

        for (int i = 0; i < seq.getNumEvents(); ++i)
        {
            if (! eligible (i)) continue;
            auto* evt = seq.getEventPointer (i);
            if (evt == nullptr || ! evt->message.isNoteOn()) continue;

            const double t = evt->message.getTimeStamp();
            if (t < startBeat || t >= startBeat + lengthBeats) continue;

            // Nearest step slot within the bar.
            const double local     = t - startBeat;
            const double beatInBar = std::fmod (local, beatsPerBar);
            const int    slot      = ((int) std::round (beatInBar / stepBeats))
                                      % stepsPerBar;

            const float offFrac = juce::jlimit (-0.5f, 0.5f,
                                      timingOffsets[(size_t) slot]);
            const float velMul  = velocityFactor[(size_t) slot];

            const double delta      = offFrac * stepBeats * strength;
            const double newStart   = t + delta;
            const double velScaled  = 1.0 + (velMul - 1.0f) * strength;

            evt->message.setTimeStamp (newStart);
            if (evt->noteOffObject != nullptr)
            {
                const double off = evt->noteOffObject->message.getTimeStamp();
                evt->noteOffObject->message.setTimeStamp (off + delta);
            }

            const int oldVel = evt->message.getVelocity();
            const int newVel = juce::jlimit (1, 127,
                                   (int) std::round ((double) oldVel * velScaled));
            if (newVel != oldVel)
                evt->message.setVelocity ((float) newVel / 127.0f);
        }

        seq.updateMatchedPairs();
        seq.sort();
    }
};
