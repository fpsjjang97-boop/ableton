/*
  ==============================================================================

    AIEngine.h
    MIDI AI Workstation - AI Music Generation Engine

    Self-contained music generation engine ported from the Python ai_engine.py.
    Provides melody, chord, bass generation, variations, humanisation, and
    analysis -- all using deterministic weighted-random algorithms.

  ==============================================================================
*/

#pragma once
#include <JuceHeader.h>
#include <map>
#include <vector>
#include <set>
#include <algorithm>
#include <cmath>

//==============================================================================
// Forward-compatible Note type used throughout the AI engine.
// Mirrors the Python Note dataclass and TrackProcessor::Note.
//==============================================================================
namespace ai
{

struct Note
{
    int pitch          = 60;
    int velocity       = 80;
    int startTick      = 0;
    int durationTicks  = 480;
    int channel        = 0;

    int endTick() const { return startTick + durationTicks; }
};

} // namespace ai

//==============================================================================
/**
    AIEngine -- high-level, musically-aware MIDI generation and variation engine.

    Every public method returns a **new** vector of notes and never modifies its
    inputs.  Uses juce::Random for all stochastic operations.
*/
class AIEngine
{
public:
    AIEngine();
    explicit AIEngine (int seed);

    //==========================================================================
    // Constants
    //==========================================================================

    static constexpr int TICKS_PER_BEAT = 480;

    //==========================================================================
    // Generation
    //==========================================================================

    std::vector<ai::Note> generateMelody (
        const juce::String& key, const juce::String& scale,
        int lengthBeats, const juce::String& style = "pop",
        float density = 0.6f, int octave = 5);

    std::vector<ai::Note> generateChords (
        const juce::String& key, const juce::String& scale,
        int lengthBeats, const juce::String& style = "pop",
        int octave = 3);

    std::vector<ai::Note> generateBass (
        const juce::String& key, const juce::String& scale,
        int lengthBeats, const juce::String& style = "pop",
        int octave = 2);

    //==========================================================================
    // Variation
    //==========================================================================

    /** Create a variation of a note sequence.
        @param type  One of "rhythm", "melody", "harmony", "dynamics",
                     "ornament", "mixed".
    */
    std::vector<ai::Note> generateVariation (
        const std::vector<ai::Note>& source,
        const juce::String& type,
        float intensity,
        const juce::String& key, const juce::String& scale);

    //==========================================================================
    // Humanise
    //==========================================================================

    std::vector<ai::Note> humanize (
        const std::vector<ai::Note>& source,
        float timingAmount, float velocityAmount);

    //==========================================================================
    // Analysis
    //==========================================================================

    struct AnalysisResult
    {
        int noteCount        = 0;
        int pitchMin         = 0;
        int pitchMax         = 0;
        float pitchMean      = 0.0f;
        int velocityMin      = 0;
        int velocityMax      = 0;
        float velocityMean   = 0.0f;
        int scaleConsistency = 0;   // 0-100
        int velocityDynamics = 0;
        int rhythmRegularity = 0;
        int noteDiversity    = 0;
        int score            = 0;   // 0-100
        juce::String grade;         // A / B / C / D
        juce::StringArray issues;
    };

    AnalysisResult analyzeTrack (
        const std::vector<ai::Note>& notes,
        const juce::String& key, const juce::String& scale);

private:
    juce::Random rng;

    //==========================================================================
    // Scale data
    //==========================================================================

    static const std::map<juce::String, std::vector<int>> scaleIntervals;
    static const juce::StringArray noteNames;

    static int  keyNameToRoot     (const juce::String& key);
    static std::vector<int> getScalePitches (int root, const juce::String& scale);
    static int  snapToScale       (int pitch, const std::vector<int>& scalePitches);
    static int  clampPitch        (int p);
    static int  clampVelocity     (int v);
    static int  closestIdx        (const std::vector<int>& vec, int value);

    //==========================================================================
    // Chord helpers
    //==========================================================================

    static int  scaleDegreeToPitch (int degree, int root,
                                    const juce::String& scale, int octave);
    static std::vector<int> buildChordPitches (int degree, int root,
                                               const juce::String& scale,
                                               int octave,
                                               const juce::String& voicing);

    //==========================================================================
    // Melody style config
    //==========================================================================

    struct MelodyStyle
    {
        int grid;
        float density;
        int maxStep;
        std::vector<int> durations;
    };

    static MelodyStyle melodyStyleConfig (const juce::String& style, float density);

    //==========================================================================
    // Progression data
    //==========================================================================

    static const std::vector<std::vector<int>>& getMajorProgressions();
    static const std::vector<std::vector<int>>& getMinorProgressions();

    //==========================================================================
    // Variation sub-routines
    //==========================================================================

    std::vector<ai::Note> varRhythm   (const std::vector<ai::Note>& src, float intensity,
                                        const juce::String& key, const juce::String& scale);
    std::vector<ai::Note> varMelody   (const std::vector<ai::Note>& src, float intensity,
                                        const juce::String& key, const juce::String& scale);
    std::vector<ai::Note> varHarmony  (const std::vector<ai::Note>& src, float intensity,
                                        const juce::String& key, const juce::String& scale);
    std::vector<ai::Note> varDynamics (const std::vector<ai::Note>& src, float intensity,
                                        const juce::String& key, const juce::String& scale);
    std::vector<ai::Note> varOrnament (const std::vector<ai::Note>& src, float intensity,
                                        const juce::String& key, const juce::String& scale);

    //==========================================================================
    // Bass sub-patterns
    //==========================================================================

    std::vector<ai::Note> bassWalking   (int root, int barStart,
                                          const std::vector<int>& sp);
    std::vector<ai::Note> bassSustained (int root, int barStart);
    std::vector<ai::Note> bassOctave    (int root, int barStart);
    std::vector<ai::Note> bassPop       (int root, int barStart,
                                          const std::vector<int>& sp);

    std::vector<int> extractBarRoots (const std::vector<ai::Note>* chordNotes,
                                      int bars, const std::vector<int>& spBass);

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (AIEngine)
};
