/*
  ==============================================================================

    AIEngine.cpp
    MIDI AI Workstation - AI Music Generation Engine

    Faithful C++ port of the Python ai_engine.py.  All musical logic
    (weighted random walk melody, common progressions, bass patterns,
    6 variation types, humanisation, analysis with scoring) is preserved.

  ==============================================================================
*/

#include "AIEngine.h"
#include <numeric>
#include <cmath>

//==============================================================================
// Constants mirroring the Python module
//==============================================================================

static constexpr int _BEAT   = AIEngine::TICKS_PER_BEAT;         // 480
static constexpr int _BAR    = _BEAT * 4;                        // 1920
static constexpr int _PHRASE = _BAR * 4;                         // 7680

//==============================================================================
// Static data
//==============================================================================

const std::map<juce::String, std::vector<int>> AIEngine::scaleIntervals =
{
    { "major",       { 0, 2, 4, 5, 7, 9, 11 } },
    { "minor",       { 0, 2, 3, 5, 7, 8, 10 } },
    { "dorian",      { 0, 2, 3, 5, 7, 9, 10 } },
    { "mixolydian",  { 0, 2, 4, 5, 7, 9, 10 } },
    { "pentatonic",  { 0, 2, 4, 7, 9 } },
    { "minor_penta", { 0, 3, 5, 7, 10 } },
    { "blues",       { 0, 3, 5, 6, 7, 10 } },
    { "chromatic",   { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 } },
};

const juce::StringArray AIEngine::noteNames =
{
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
};

//==============================================================================
// Progression templates (1-indexed scale degrees)
//==============================================================================

const std::vector<std::vector<int>>& AIEngine::getMajorProgressions()
{
    static const std::vector<std::vector<int>> p =
    {
        { 1, 5, 6, 4 },   // I-V-vi-IV
        { 1, 4, 5, 4 },   // I-IV-V-IV
        { 1, 6, 4, 5 },   // I-vi-IV-V
        { 1, 4, 6, 5 },   // I-IV-vi-V
        { 1, 5, 4, 5 },   // I-V-IV-V
    };
    return p;
}

const std::vector<std::vector<int>>& AIEngine::getMinorProgressions()
{
    static const std::vector<std::vector<int>> p =
    {
        { 1, 4, 7, 3 },   // i-iv-VII-III
        { 1, 6, 3, 7 },   // i-VI-III-VII
        { 1, 4, 5, 1 },   // i-iv-v-i
        { 1, 7, 6, 7 },   // i-VII-VI-VII
        { 1, 3, 4, 5 },   // i-III-iv-v
    };
    return p;
}

//==============================================================================
// Constructor
//==============================================================================

AIEngine::AIEngine()
    : rng (static_cast<juce::int64> (juce::Time::currentTimeMillis()))
{
}

AIEngine::AIEngine (int seed)
    : rng (seed)
{
}

//==============================================================================
// Static utilities
//==============================================================================

int AIEngine::keyNameToRoot (const juce::String& key)
{
    auto k = key.trim().toUpperCase();

    for (int i = 0; i < noteNames.size(); ++i)
        if (k == noteNames[i])
            return i;

    // Flat aliases
    static const std::map<juce::String, juce::String> aliases =
    {
        { "BB", "A#" }, { "DB", "C#" }, { "EB", "D#" },
        { "GB", "F#" }, { "AB", "G#" },
    };

    auto it = aliases.find (k);
    if (it != aliases.end())
    {
        for (int i = 0; i < noteNames.size(); ++i)
            if (noteNames[i] == it->second)
                return i;
    }

    return 0; // default C
}

std::vector<int> AIEngine::getScalePitches (int root, const juce::String& scale)
{
    auto it = scaleIntervals.find (scale);
    const auto& intervals = (it != scaleIntervals.end())
                                ? it->second
                                : scaleIntervals.at ("minor");

    std::set<int> pitchSet;
    for (int octBase = 0; octBase < 128; octBase += 12)
    {
        for (int iv : intervals)
        {
            int p = octBase + root + iv;
            if (p >= 0 && p < 128)
                pitchSet.insert (p);
        }
    }

    return { pitchSet.begin(), pitchSet.end() };
}

int AIEngine::snapToScale (int pitch, const std::vector<int>& scalePitches)
{
    if (scalePitches.empty())
        return clampPitch (pitch);

    // Check membership first (fast path)
    for (int sp : scalePitches)
        if (sp == pitch)
            return pitch;

    // Find nearest
    int best     = scalePitches[0];
    int bestDist = std::abs (pitch - best);

    for (size_t i = 1; i < scalePitches.size(); ++i)
    {
        int d = std::abs (pitch - scalePitches[i]);
        if (d < bestDist)
        {
            bestDist = d;
            best     = scalePitches[i];
        }
    }

    return best;
}

int AIEngine::clampPitch (int p)    { return juce::jlimit (0, 127, p); }
int AIEngine::clampVelocity (int v) { return juce::jlimit (1, 127, v); }

int AIEngine::closestIdx (const std::vector<int>& vec, int value)
{
    if (vec.empty())
        return 0;

    int bestIdx  = 0;
    int bestDist = std::abs (value - vec[0]);

    for (int i = 1; i < static_cast<int> (vec.size()); ++i)
    {
        int d = std::abs (value - vec[i]);
        if (d < bestDist)
        {
            bestDist = d;
            bestIdx  = i;
        }
    }

    return bestIdx;
}

//==============================================================================
// Chord helpers
//==============================================================================

int AIEngine::scaleDegreeToPitch (int degree, int root,
                                  const juce::String& scale, int octave)
{
    auto it = scaleIntervals.find (scale);
    const auto& intervals = (it != scaleIntervals.end())
                                ? it->second
                                : scaleIntervals.at ("minor");

    int n         = static_cast<int> (intervals.size());
    int idx       = ((degree - 1) % n + n) % n;   // safe modulo
    int octOffset = (degree - 1) / n;

    return clampPitch ((octave + 1 + octOffset) * 12 + root + intervals[idx]);
}

std::vector<int> AIEngine::buildChordPitches (int degree, int root,
                                              const juce::String& scale,
                                              int octave,
                                              const juce::String& voicing)
{
    auto degPitch = [&] (int d) -> int
    {
        auto it = scaleIntervals.find (scale);
        const auto& intervals = (it != scaleIntervals.end())
                                    ? it->second
                                    : scaleIntervals.at ("minor");
        int n   = static_cast<int> (intervals.size());
        int idx = ((d - 1) % n + n) % n;
        int oc  = (d - 1) / n;
        return clampPitch ((octave + 1 + oc) * 12 + root + intervals[idx]);
    };

    std::vector<int> pitches;
    pitches.push_back (degPitch (degree));

    if (voicing == "triad" || voicing == "seventh" || voicing == "spread")
    {
        pitches.push_back (degPitch (degree + 2));   // 3rd
        pitches.push_back (degPitch (degree + 4));   // 5th
    }

    if (voicing == "seventh")
        pitches.push_back (degPitch (degree + 6));   // 7th

    if (voicing == "spread")
    {
        // Drop middle note down an octave for open voicing
        if (pitches.size() >= 3)
            pitches[1] = clampPitch (pitches[1] - 12);
    }

    std::sort (pitches.begin(), pitches.end());
    return pitches;
}

//==============================================================================
// Melody style configuration
//==============================================================================

AIEngine::MelodyStyle AIEngine::melodyStyleConfig (const juce::String& style,
                                                   float density)
{
    if (style == "ambient")
    {
        return {
            _BEAT,                                              // grid
            std::max (0.45f, density * 0.7f),                   // density
            2,                                                  // maxStep
            { _BEAT * 2, _BEAT * 3, _BEAT * 4 }                // durations
        };
    }

    if (style == "edm")
    {
        return {
            _BEAT / 2,
            std::min (1.0f, density * 1.3f),
            4,
            { _BEAT / 2, _BEAT, _BEAT / 4 }
        };
    }

    // pop / default
    return {
        _BEAT / 2,
        density,
        3,
        { _BEAT / 2, _BEAT, _BEAT * 2 }
    };
}

//==============================================================================
// 1. Melody generation
//==============================================================================

std::vector<ai::Note> AIEngine::generateMelody (
    const juce::String& key, const juce::String& scale,
    int lengthBeats, const juce::String& style,
    float density, int octave)
{
    int root = keyNameToRoot (key);
    auto sp  = getScalePitches (root, scale);

    // Restrict to a comfortable range around the target octave
    int lo = (octave + 1) * 12 - 6;
    int hi = (octave + 1) * 12 + 18;

    std::vector<int> spRange;
    for (int p : sp)
        if (p >= lo && p <= hi)
            spRange.push_back (p);

    if (spRange.empty())
        spRange = sp;

    auto cfg        = melodyStyleConfig (style, density);
    int totalTicks  = lengthBeats * _BEAT;
    int cursor      = 0;
    int idx         = static_cast<int> (spRange.size()) / 2;   // middle
    int phraseLen   = _PHRASE;

    std::vector<ai::Note> notes;

    while (cursor < totalTicks)
    {
        // Phrase-level tension curve
        float phrasePos = static_cast<float> (cursor % phraseLen)
                        / static_cast<float> (phraseLen);
        float tension   = std::sin (phrasePos * juce::MathConstants<float>::pi);

        // Decide note vs rest
        float noteProb = cfg.density * (0.7f + 0.3f * tension);
        if (rng.nextFloat() > noteProb)
        {
            cursor += cfg.grid;
            continue;
        }

        // Weighted random walk
        int step = rng.nextInt (juce::Range<int> (-cfg.maxStep, cfg.maxStep + 1));

        // Bias toward resolution at phrase end
        if (phrasePos > 0.85f)
        {
            int tonicIdx = closestIdx (spRange, (octave + 1) * 12 + root);
            int sign     = (tonicIdx > idx) ? 1 : ((tonicIdx < idx) ? -1 : 0);
            step         = sign * std::max (1, std::abs (step));
        }

        idx = juce::jlimit (0, static_cast<int> (spRange.size()) - 1, idx + step);

        // Duration (random choice from style durations)
        int durIdx = rng.nextInt (static_cast<int> (cfg.durations.size()));
        int dur    = cfg.durations[durIdx];
        dur        = std::min (dur, totalTicks - cursor);
        if (dur <= 0)
            break;

        int vel = static_cast<int> (60.0f + 30.0f * tension)
                + rng.nextInt (juce::Range<int> (-8, 9));

        ai::Note n;
        n.pitch         = spRange[idx];
        n.velocity      = clampVelocity (vel);
        n.startTick     = cursor;
        n.durationTicks = dur;
        notes.push_back (n);

        cursor += std::max (cfg.grid, dur);
    }

    return notes;
}

//==============================================================================
// 2. Chord generation
//==============================================================================

std::vector<ai::Note> AIEngine::generateChords (
    const juce::String& key, const juce::String& scale,
    int lengthBeats, const juce::String& style, int octave)
{
    int root = keyNameToRoot (key);

    // Choose progression family
    bool isMinor = (scale == "minor" || scale == "dorian" || scale == "minor_penta");
    const auto& progs = isMinor ? getMinorProgressions() : getMajorProgressions();
    auto prog = progs[rng.nextInt (static_cast<int> (progs.size()))];

    int totalTicks = lengthBeats * _BEAT;
    int bars       = std::max (1, totalTicks / _BAR);

    // Tile the 4-chord progression to fill all bars
    std::vector<int> fullProg;
    while (static_cast<int> (fullProg.size()) < bars)
        fullProg.insert (fullProg.end(), prog.begin(), prog.end());
    fullProg.resize (static_cast<size_t> (bars));

    // Random voicing
    static const juce::String voicings[] = { "triad", "seventh", "spread" };
    auto voicing = voicings[rng.nextInt (3)];

    std::vector<ai::Note> notes;

    for (int barIdx = 0; barIdx < bars; ++barIdx)
    {
        int barStart = barIdx * _BAR;
        int degree   = fullProg[barIdx];
        auto pitches = buildChordPitches (degree, root, scale, octave, voicing);

        if (style == "ambient")
        {
            // Whole-bar sustained chords
            for (int p : pitches)
            {
                ai::Note n;
                n.pitch         = p;
                n.velocity      = clampVelocity (55 + rng.nextInt (juce::Range<int> (-5, 6)));
                n.startTick     = barStart;
                n.durationTicks = _BAR - _BEAT / 4;
                notes.push_back (n);
            }
        }
        else if (style == "edm")
        {
            // Pumping quarter-note chords
            for (int beat = 0; beat < 4; ++beat)
            {
                for (int p : pitches)
                {
                    ai::Note n;
                    n.pitch         = p;
                    n.velocity      = clampVelocity (beat == 0 ? 80 : 65);
                    n.startTick     = barStart + beat * _BEAT;
                    n.durationTicks = _BEAT / 2;
                    notes.push_back (n);
                }
            }
        }
        else
        {
            // Pop/default: half-note strums
            for (int half = 0; half < 2; ++half)
            {
                int velBase     = (half == 0) ? 75 : 65;
                int strumOffset = 0;

                for (int p : pitches)
                {
                    ai::Note n;
                    n.pitch         = p;
                    n.velocity      = clampVelocity (velBase + rng.nextInt (juce::Range<int> (-4, 5)));
                    n.startTick     = barStart + half * _BEAT * 2 + strumOffset;
                    n.durationTicks = _BEAT * 2 - _BEAT / 8;
                    notes.push_back (n);

                    strumOffset += rng.nextInt (_BEAT / 16 + 1);
                }
            }
        }
    }

    return notes;
}

//==============================================================================
// 3. Bass-line generation
//==============================================================================

std::vector<int> AIEngine::extractBarRoots (const std::vector<ai::Note>* chordNotes,
                                            int bars,
                                            const std::vector<int>& spBass)
{
    if (chordNotes != nullptr && ! chordNotes->empty())
    {
        std::vector<int> roots;
        for (int b = 0; b < bars; ++b)
        {
            int barStart = b * _BAR;
            int barEnd   = barStart + _BAR;

            int lowest = -1;
            for (const auto& n : *chordNotes)
            {
                if (n.endTick() > barStart && n.startTick < barEnd)
                {
                    if (lowest < 0 || n.pitch < lowest)
                        lowest = n.pitch;
                }
            }

            if (lowest >= 0)
            {
                int bassOctBase = spBass.empty() ? 36 : (spBass[0] / 12) * 12;
                roots.push_back (snapToScale (lowest % 12 + bassOctBase, spBass));
            }
            else
            {
                roots.push_back (spBass.empty() ? 36 : spBass[0]);
            }
        }
        return roots;
    }

    return std::vector<int> (static_cast<size_t> (bars),
                             spBass.empty() ? 36 : spBass[0]);
}

std::vector<ai::Note> AIEngine::bassWalking (int root, int barStart,
                                              const std::vector<int>& sp)
{
    std::vector<ai::Note> notes;
    int idx = closestIdx (sp, root);

    for (int beat = 0; beat < 4; ++beat)
    {
        ai::Note n;
        n.pitch         = sp[idx];
        n.velocity      = clampVelocity (85 + rng.nextInt (juce::Range<int> (-6, 7)));
        n.startTick     = barStart + beat * _BEAT;
        n.durationTicks = _BEAT - _BEAT / 8;
        notes.push_back (n);

        // Walking step choices: -1, 1, 1, 2  (biased upward)
        static const int steps[] = { -1, 1, 1, 2 };
        int step = steps[rng.nextInt (4)];
        idx = juce::jlimit (0, static_cast<int> (sp.size()) - 1, idx + step);
    }

    return notes;
}

std::vector<ai::Note> AIEngine::bassSustained (int root, int barStart)
{
    ai::Note n;
    n.pitch         = root;
    n.velocity      = 80;
    n.startTick     = barStart;
    n.durationTicks = _BAR - _BEAT / 4;
    return { n };
}

std::vector<ai::Note> AIEngine::bassOctave (int root, int barStart)
{
    int upper = clampPitch (root + 12);
    int pattern[] = { root, upper, root, upper };

    std::vector<ai::Note> notes;
    for (int i = 0; i < 4; ++i)
    {
        ai::Note n;
        n.pitch         = pattern[i];
        n.velocity      = clampVelocity ((i % 2 == 0) ? 80 : 70);
        n.startTick     = barStart + i * _BEAT;
        n.durationTicks = _BEAT - _BEAT / 8;
        notes.push_back (n);
    }

    return notes;
}

std::vector<ai::Note> AIEngine::bassPop (int root, int barStart,
                                          const std::vector<int>& sp)
{
    int idx      = closestIdx (sp, root);
    int fifthIdx = std::min (idx + 4, static_cast<int> (sp.size()) - 1);

    std::vector<ai::Note> notes;

    // Beat 1: root
    {
        ai::Note n;
        n.pitch         = sp[idx];
        n.velocity      = 85;
        n.startTick     = barStart;
        n.durationTicks = _BEAT;
        notes.push_back (n);
    }

    // Beat 3: fifth
    {
        ai::Note n;
        n.pitch         = sp[fifthIdx];
        n.velocity      = 75;
        n.startTick     = barStart + 2 * _BEAT;
        n.durationTicks = _BEAT;
        notes.push_back (n);
    }

    // Optional ghost note on off-beat
    if (rng.nextFloat() > 0.4f)
    {
        ai::Note n;
        n.pitch         = sp[idx];
        n.velocity      = 55;
        n.startTick     = barStart + static_cast<int> (1.5f * _BEAT);
        n.durationTicks = _BEAT / 2;
        notes.push_back (n);
    }

    return notes;
}

std::vector<ai::Note> AIEngine::generateBass (
    const juce::String& key, const juce::String& scale,
    int lengthBeats, const juce::String& style, int octave)
{
    int root = keyNameToRoot (key);
    auto sp  = getScalePitches (root, scale);

    int lo = (octave + 1) * 12 - 2;
    int hi = (octave + 1) * 12 + 14;

    std::vector<int> spBass;
    for (int p : sp)
        if (p >= lo && p <= hi)
            spBass.push_back (p);

    if (spBass.empty())
        spBass = sp;

    int totalTicks = lengthBeats * _BEAT;
    int bars       = std::max (1, totalTicks / _BAR);

    auto barRoots = extractBarRoots (nullptr, bars, spBass);

    std::vector<ai::Note> notes;

    for (int barIdx = 0; barIdx < bars; ++barIdx)
    {
        int barStart = barIdx * _BAR;
        int br       = barRoots[barIdx];

        std::vector<ai::Note> barNotes;

        if (style == "walking")
            barNotes = bassWalking (br, barStart, spBass);
        else if (style == "sustained")
            barNotes = bassSustained (br, barStart);
        else if (style == "octave")
            barNotes = bassOctave (br, barStart);
        else
            barNotes = bassPop (br, barStart, spBass);

        notes.insert (notes.end(), barNotes.begin(), barNotes.end());
    }

    return notes;
}

//==============================================================================
// 4. Variation
//==============================================================================

std::vector<ai::Note> AIEngine::generateVariation (
    const std::vector<ai::Note>& source,
    const juce::String& type, float intensity,
    const juce::String& key, const juce::String& scale)
{
    intensity = juce::jlimit (0.0f, 1.0f, intensity);

    if (type == "rhythm")   return varRhythm   (source, intensity, key, scale);
    if (type == "melody")   return varMelody   (source, intensity, key, scale);
    if (type == "harmony")  return varHarmony  (source, intensity, key, scale);
    if (type == "dynamics") return varDynamics (source, intensity, key, scale);
    if (type == "ornament") return varOrnament (source, intensity, key, scale);

    if (type == "mixed")
    {
        // Apply 2+ random variation types
        juce::StringArray allTypes = { "rhythm", "melody", "harmony", "dynamics", "ornament" };
        int numToApply = std::max (2, static_cast<int> (allTypes.size() * intensity));

        // Shuffle and pick
        std::vector<int> indices (allTypes.size());
        std::iota (indices.begin(), indices.end(), 0);
        for (int i = static_cast<int> (indices.size()) - 1; i > 0; --i)
        {
            int j = rng.nextInt (i + 1);
            std::swap (indices[i], indices[j]);
        }

        auto result = source;
        for (int i = 0; i < std::min (numToApply, static_cast<int> (indices.size())); ++i)
        {
            auto vt = allTypes[indices[i]];

            if (vt == "rhythm")        result = varRhythm   (result, intensity, key, scale);
            else if (vt == "melody")   result = varMelody   (result, intensity, key, scale);
            else if (vt == "harmony")  result = varHarmony  (result, intensity, key, scale);
            else if (vt == "dynamics") result = varDynamics (result, intensity, key, scale);
            else if (vt == "ornament") result = varOrnament (result, intensity, key, scale);
        }

        return result;
    }

    // Unknown type -- return copy
    return source;
}

//==============================================================================
// Variation: Rhythm
//==============================================================================

std::vector<ai::Note> AIEngine::varRhythm (
    const std::vector<ai::Note>& src, float intensity,
    const juce::String& /*key*/, const juce::String& /*scale*/)
{
    auto out      = src;
    int maxShift  = static_cast<int> (_BEAT * intensity);
    int grid      = std::max (1, _BEAT / 4);

    for (auto& note : out)
    {
        int shift = rng.nextInt (juce::Range<int> (-maxShift, maxShift + 1));
        // Quantise the shift to the grid
        shift = static_cast<int> (std::round (static_cast<float> (shift) / grid)) * grid;
        note.startTick = std::max (0, note.startTick + shift);

        float durScale = 1.0f + rng.nextFloat() * 0.8f * intensity - 0.4f * intensity;
        note.durationTicks = std::max (grid, static_cast<int> (note.durationTicks * durScale));
    }

    // Sort by start tick
    std::sort (out.begin(), out.end(),
               [] (const ai::Note& a, const ai::Note& b)
               { return a.startTick < b.startTick; });

    return out;
}

//==============================================================================
// Variation: Melody
//==============================================================================

std::vector<ai::Note> AIEngine::varMelody (
    const std::vector<ai::Note>& src, float intensity,
    const juce::String& key, const juce::String& scale)
{
    int root = keyNameToRoot (key);
    auto sp  = getScalePitches (root, scale);
    auto out = src;

    int maxSteps = std::max (1, static_cast<int> (7 * intensity));

    for (auto& note : out)
    {
        if (rng.nextFloat() < 0.3f + 0.5f * intensity)
        {
            int idx  = closestIdx (sp, note.pitch);
            int step = rng.nextInt (juce::Range<int> (-maxSteps, maxSteps + 1));
            int newIdx = juce::jlimit (0, static_cast<int> (sp.size()) - 1, idx + step);
            note.pitch = sp[newIdx];
        }
    }

    return out;
}

//==============================================================================
// Variation: Harmony
//==============================================================================

std::vector<ai::Note> AIEngine::varHarmony (
    const std::vector<ai::Note>& src, float intensity,
    const juce::String& key, const juce::String& scale)
{
    int root = keyNameToRoot (key);
    auto sp  = getScalePitches (root, scale);

    auto it = scaleIntervals.find (scale);
    const auto& intervals = (it != scaleIntervals.end())
                                ? it->second
                                : scaleIntervals.at ("minor");
    int nIv = static_cast<int> (intervals.size());

    auto out = src;
    std::vector<ai::Note> newNotes;

    for (const auto& note : out)
    {
        if (rng.nextFloat() > intensity)
            continue;

        int idx = closestIdx (sp, note.pitch);
        float choice = rng.nextFloat();

        int hIdx;
        if (choice < 0.4f)
            hIdx = std::min (idx + 2, static_cast<int> (sp.size()) - 1);      // 3rd
        else if (choice < 0.7f)
            hIdx = std::min (idx + 4, static_cast<int> (sp.size()) - 1);      // 5th
        else
            hIdx = std::min (idx + nIv, static_cast<int> (sp.size()) - 1);    // octave

        int hPitch = sp[hIdx];
        if (hPitch != note.pitch)
        {
            ai::Note hn;
            hn.pitch         = hPitch;
            hn.velocity      = clampVelocity (note.velocity - 10);
            hn.startTick     = note.startTick;
            hn.durationTicks = note.durationTicks;
            hn.channel       = note.channel;
            newNotes.push_back (hn);
        }
    }

    out.insert (out.end(), newNotes.begin(), newNotes.end());
    std::sort (out.begin(), out.end(),
               [] (const ai::Note& a, const ai::Note& b)
               { return a.startTick < b.startTick; });

    return out;
}

//==============================================================================
// Variation: Dynamics
//==============================================================================

std::vector<ai::Note> AIEngine::varDynamics (
    const std::vector<ai::Note>& src, float intensity,
    const juce::String& /*key*/, const juce::String& /*scale*/)
{
    auto out = src;
    if (out.empty())
        return out;

    int total = out.back().endTick();
    if (total <= 0)
        total = 1;

    for (auto& note : out)
    {
        // Sinusoidal swell across the track
        float phase = static_cast<float> (note.startTick) / total
                    * juce::MathConstants<float>::twoPi;
        float swell = std::sin (phase) * 30.0f * intensity;

        int jitterRange = static_cast<int> (20 * intensity);
        int jitter = (jitterRange > 0)
                         ? rng.nextInt (juce::Range<int> (-jitterRange, jitterRange + 1))
                         : 0;

        note.velocity = clampVelocity (
            static_cast<int> (note.velocity + swell + jitter));
    }

    return out;
}

//==============================================================================
// Variation: Ornament
//==============================================================================

std::vector<ai::Note> AIEngine::varOrnament (
    const std::vector<ai::Note>& src, float intensity,
    const juce::String& key, const juce::String& scale)
{
    int root = keyNameToRoot (key);
    auto sp  = getScalePitches (root, scale);
    auto out = src;

    std::vector<ai::Note> ornaments;
    int graceDur = std::max (1, _BEAT / 8);

    for (auto& note : out)
    {
        if (rng.nextFloat() > intensity * 0.6f)
            continue;

        int idx  = closestIdx (sp, note.pitch);
        float kind = rng.nextFloat();

        if (kind < 0.45f)
        {
            // Grace note from below
            int gIdx = std::max (0, idx - 1);
            ai::Note gn;
            gn.pitch         = sp[gIdx];
            gn.velocity      = clampVelocity (note.velocity - 15);
            gn.startTick     = std::max (0, note.startTick - graceDur);
            gn.durationTicks = graceDur;
            gn.channel       = note.channel;
            ornaments.push_back (gn);
        }
        else if (kind < 0.75f)
        {
            // Trill: two rapid alternations above
            int above    = std::min (idx + 1, static_cast<int> (sp.size()) - 1);
            int trillDur = std::max (1, _BEAT / 6);

            for (int t = 0; t < 3; ++t)
            {
                int p = (t % 2 == 0) ? sp[above] : note.pitch;
                ai::Note tn;
                tn.pitch         = p;
                tn.velocity      = clampVelocity (note.velocity - 20);
                tn.startTick     = note.startTick + t * trillDur;
                tn.durationTicks = trillDur;
                tn.channel       = note.channel;
                ornaments.push_back (tn);
            }

            // Shorten original
            note.startTick    += 3 * trillDur;
            note.durationTicks = std::max (graceDur, note.durationTicks - 3 * trillDur);
        }
        else
        {
            // Turn: upper-main-lower-main
            int above   = std::min (idx + 1, static_cast<int> (sp.size()) - 1);
            int below   = std::max (0, idx - 1);
            int turnDur = std::max (1, _BEAT / 8);

            int pitchSeq[] = { sp[above], note.pitch, sp[below], note.pitch };
            for (int i = 0; i < 4; ++i)
            {
                ai::Note tn;
                tn.pitch         = pitchSeq[i];
                tn.velocity      = clampVelocity (note.velocity - 10);
                tn.startTick     = note.startTick + i * turnDur;
                tn.durationTicks = turnDur;
                tn.channel       = note.channel;
                ornaments.push_back (tn);
            }

            note.startTick    += 4 * turnDur;
            note.durationTicks = std::max (graceDur, note.durationTicks - 4 * turnDur);
        }
    }

    out.insert (out.end(), ornaments.begin(), ornaments.end());
    std::sort (out.begin(), out.end(),
               [] (const ai::Note& a, const ai::Note& b)
               { return a.startTick < b.startTick; });

    return out;
}

//==============================================================================
// 5. Humanise
//==============================================================================

std::vector<ai::Note> AIEngine::humanize (
    const std::vector<ai::Note>& source,
    float timingAmount, float velocityAmount)
{
    auto out = source;

    timingAmount   = juce::jlimit (0.0f, 1.0f, timingAmount);
    velocityAmount = juce::jlimit (0.0f, 1.0f, velocityAmount);

    int maxTickOffset = static_cast<int> (_BEAT * 0.08f * timingAmount * 10.0f);
    int maxVelOffset  = static_cast<int> (20.0f * velocityAmount);

    for (auto& note : out)
    {
        if (maxTickOffset > 0)
        {
            int offset = rng.nextInt (juce::Range<int> (-maxTickOffset, maxTickOffset + 1));
            note.startTick = std::max (0, note.startTick + offset);
        }

        if (maxVelOffset > 0)
        {
            int vOff = rng.nextInt (juce::Range<int> (-maxVelOffset, maxVelOffset + 1));
            note.velocity = clampVelocity (note.velocity + vOff);
        }
    }

    std::sort (out.begin(), out.end(),
               [] (const ai::Note& a, const ai::Note& b)
               { return a.startTick < b.startTick; });

    return out;
}

//==============================================================================
// 6. Analysis
//==============================================================================

AIEngine::AnalysisResult AIEngine::analyzeTrack (
    const std::vector<ai::Note>& notes,
    const juce::String& key, const juce::String& scale)
{
    AnalysisResult r;

    if (notes.empty())
    {
        r.grade = "D";
        r.issues.add ("Track is empty");
        return r;
    }

    r.noteCount = static_cast<int> (notes.size());

    //----------------------------------------------------------------------
    // Pitch statistics
    //----------------------------------------------------------------------
    int pMin = 127, pMax = 0;
    double pSum = 0.0;

    for (const auto& n : notes)
    {
        if (n.pitch < pMin) pMin = n.pitch;
        if (n.pitch > pMax) pMax = n.pitch;
        pSum += n.pitch;
    }

    r.pitchMin  = pMin;
    r.pitchMax  = pMax;
    r.pitchMean = static_cast<float> (pSum / notes.size());

    //----------------------------------------------------------------------
    // Velocity statistics
    //----------------------------------------------------------------------
    int vMin = 127, vMax = 0;
    double vSum = 0.0;

    for (const auto& n : notes)
    {
        if (n.velocity < vMin) vMin = n.velocity;
        if (n.velocity > vMax) vMax = n.velocity;
        vSum += n.velocity;
    }

    r.velocityMin  = vMin;
    r.velocityMax  = vMax;
    r.velocityMean = static_cast<float> (vSum / notes.size());

    //----------------------------------------------------------------------
    // Scale consistency
    //----------------------------------------------------------------------
    int root = keyNameToRoot (key);
    auto spSet = getScalePitches (root, scale);
    std::set<int> scaleSet (spSet.begin(), spSet.end());

    int inScale = 0;
    for (const auto& n : notes)
        if (scaleSet.count (n.pitch))
            ++inScale;

    r.scaleConsistency = static_cast<int> (
        std::round (static_cast<double> (inScale) / notes.size() * 100.0));

    //----------------------------------------------------------------------
    // Velocity dynamics
    //----------------------------------------------------------------------
    {
        int velRange = vMax - vMin;
        // Compute velocity std dev
        double velMean = vSum / notes.size();
        double sumSq   = 0.0;
        for (const auto& n : notes)
        {
            double d = n.velocity - velMean;
            sumSq += d * d;
        }
        double velStd = std::sqrt (sumSq / notes.size());

        double velStdScore   = std::min (100.0, velStd / 30.0 * 100.0);
        double velRangeScore = std::min (100.0, velRange / 80.0 * 100.0);
        r.velocityDynamics   = static_cast<int> (
            std::round (velStdScore * 0.5 + velRangeScore * 0.5));
    }

    //----------------------------------------------------------------------
    // Rhythm regularity (coefficient of variation of inter-onset intervals)
    //----------------------------------------------------------------------
    {
        std::vector<int> starts;
        starts.reserve (notes.size());
        for (const auto& n : notes)
            starts.push_back (n.startTick);
        std::sort (starts.begin(), starts.end());

        if (starts.size() > 1)
        {
            std::vector<double> onsetIntervals;
            for (size_t i = 1; i < starts.size(); ++i)
            {
                double diff = static_cast<double> (starts[i] - starts[i - 1]);
                if (diff > 0.0)
                    onsetIntervals.push_back (diff);
            }

            if (onsetIntervals.size() > 1)
            {
                double mean = std::accumulate (onsetIntervals.begin(),
                                               onsetIntervals.end(), 0.0)
                            / onsetIntervals.size();
                double sumSq = 0.0;
                for (double v : onsetIntervals)
                    sumSq += (v - mean) * (v - mean);
                double sd = std::sqrt (sumSq / onsetIntervals.size());
                double cv = (mean > 0.0) ? sd / mean : 1.0;
                r.rhythmRegularity = static_cast<int> (
                    std::round (std::max (0.0, std::min (100.0,
                        (1.0 - cv / 1.5) * 100.0))));
            }
            else
            {
                r.rhythmRegularity = 100;
            }
        }
        else
        {
            r.rhythmRegularity = 100;
        }
    }

    //----------------------------------------------------------------------
    // Note diversity (unique pitch classes / 12)
    //----------------------------------------------------------------------
    {
        std::set<int> pitchClasses;
        for (const auto& n : notes)
            pitchClasses.insert (n.pitch % 12);

        r.noteDiversity = static_cast<int> (
            std::round (static_cast<double> (pitchClasses.size()) / 12.0 * 100.0));
    }

    //----------------------------------------------------------------------
    // Overall score (weighted average)
    //----------------------------------------------------------------------
    r.score = static_cast<int> (std::round (
          r.scaleConsistency * 0.30
        + r.velocityDynamics * 0.20
        + r.rhythmRegularity * 0.25
        + r.noteDiversity    * 0.25));

    //----------------------------------------------------------------------
    // Grade
    //----------------------------------------------------------------------
    if (r.score >= 80)       r.grade = "A";
    else if (r.score >= 60)  r.grade = "B";
    else if (r.score >= 40)  r.grade = "C";
    else                     r.grade = "D";

    //----------------------------------------------------------------------
    // Issues detection
    //----------------------------------------------------------------------
    if (r.scaleConsistency < 60)
        r.issues.add ("Low scale consistency");

    if (pMax - pMin < 12)
        r.issues.add ("Narrow pitch range");

    if (r.velocityDynamics < 30)
        r.issues.add ("Low velocity dynamics -- notes feel flat");

    if (r.noteDiversity < 30)
        r.issues.add ("Low note diversity -- few distinct pitch classes");

    if (r.rhythmRegularity < 30)
        r.issues.add ("Irregular rhythm -- timing is erratic");

    if (static_cast<int> (notes.size()) < 4)
        r.issues.add ("Very few notes -- track may be too sparse");

    return r;
}
