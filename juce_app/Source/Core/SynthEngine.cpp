/*
  ==============================================================================
    SynthEngine.cpp
    Multi-timbral synthesizer with GM-style program presets.
    Uses additive/subtractive synthesis with harmonics for realistic timbres.
  ==============================================================================
*/
#include "SynthEngine.h"
#include <cmath>

//==============================================================================
// GM Instrument Presets
//==============================================================================
std::vector<InstrumentPreset> SynthEngine::presets;
bool SynthEngine::presetsInitialized = false;

void SynthEngine::initPresets()
{
    if (presetsInitialized) return;
    presetsInitialized = true;
    presets.resize (128);

    // Helper lambda
    auto setPreset = [&](int prog, const char* name, int wave,
                         std::initializer_list<float> harm,
                         float a, float d, float s, float r,
                         float cutMul, float res, float det, float vibR, float vibD)
    {
        auto& p = presets[prog];
        p.name = name;
        p.waveType = wave;
        int i = 0;
        for (float h : harm) { if (i < 16) p.harmonics[i++] = h; }
        p.numHarmonics = i;
        p.attack = a; p.decay = d; p.sustain = s; p.release = r;
        p.filterCutoffMultiplier = cutMul;
        p.filterResonance = res;
        p.detuneCents = det;
        p.vibratoRate = vibR;
        p.vibratoDepth = vibD;
    };

    // --- Pianos (0-7) ---
    setPreset(0, "Acoustic Grand Piano", 0,
        {1.0f, 0.5f, 0.25f, 0.12f, 0.06f, 0.03f, 0.015f, 0.008f},
        0.005f, 0.8f, 0.3f, 0.8f, 5.0f, 0.1f, 5.0f, 0, 0);
    setPreset(1, "Bright Acoustic Piano", 0,
        {1.0f, 0.6f, 0.35f, 0.2f, 0.1f, 0.05f, 0.025f},
        0.003f, 0.6f, 0.35f, 0.7f, 7.0f, 0.15f, 6.0f, 0, 0);
    setPreset(2, "Electric Grand Piano", 0,
        {1.0f, 0.4f, 0.3f, 0.15f, 0.08f},
        0.005f, 0.5f, 0.4f, 0.6f, 6.0f, 0.1f, 8.0f, 0, 0);
    setPreset(3, "Honky-tonk Piano", 0,
        {1.0f, 0.6f, 0.3f, 0.15f, 0.08f, 0.04f},
        0.003f, 0.5f, 0.25f, 0.5f, 6.0f, 0.2f, 15.0f, 0, 0);
    setPreset(4, "Electric Piano 1", 0,
        {1.0f, 0.0f, 0.5f, 0.0f, 0.25f, 0.0f, 0.12f},
        0.008f, 0.4f, 0.5f, 0.4f, 4.0f, 0.0f, 3.0f, 0, 0);
    setPreset(5, "Electric Piano 2", 0,
        {1.0f, 0.3f, 0.0f, 0.4f, 0.0f, 0.2f},
        0.01f, 0.3f, 0.55f, 0.35f, 3.5f, 0.05f, 4.0f, 0, 0);

    // --- Chromatic Percussion (8-15) ---
    setPreset(8, "Celesta", 0,
        {1.0f, 0.0f, 0.8f, 0.0f, 0.4f},
        0.001f, 0.3f, 0.1f, 0.5f, 8.0f, 0.0f, 2.0f, 0, 0);
    setPreset(9, "Glockenspiel", 0,
        {1.0f, 0.0f, 0.6f, 0.0f, 0.3f, 0.0f, 0.15f},
        0.001f, 0.2f, 0.0f, 0.8f, 10.0f, 0.0f, 1.0f, 0, 0);
    setPreset(11, "Vibraphone", 0,
        {1.0f, 0.0f, 0.5f, 0.0f, 0.25f},
        0.005f, 0.3f, 0.4f, 0.6f, 6.0f, 0.0f, 2.0f, 5.0f, 0.1f);
    setPreset(13, "Xylophone", 0,
        {1.0f, 0.0f, 0.7f, 0.0f, 0.35f, 0.0f, 0.18f},
        0.001f, 0.15f, 0.0f, 0.3f, 12.0f, 0.0f, 0.0f, 0, 0);

    // --- Organ (16-23) ---
    setPreset(16, "Drawbar Organ", 0,
        {1.0f, 0.5f, 0.0f, 0.3f, 0.0f, 0.15f, 0.0f, 0.08f},
        0.01f, 0.05f, 0.9f, 0.1f, 6.0f, 0.0f, 0.0f, 0, 0);
    setPreset(19, "Church Organ", 0,
        {1.0f, 0.7f, 0.5f, 0.35f, 0.25f, 0.18f, 0.12f, 0.08f, 0.06f, 0.04f},
        0.05f, 0.1f, 0.95f, 0.2f, 4.0f, 0.0f, 3.0f, 0, 0);

    // --- Guitar (24-31) ---
    setPreset(24, "Nylon Guitar", 0,
        {1.0f, 0.6f, 0.35f, 0.2f, 0.1f, 0.05f},
        0.003f, 0.4f, 0.2f, 0.3f, 4.0f, 0.15f, 0.0f, 0, 0);
    setPreset(25, "Steel Guitar", 0,
        {1.0f, 0.5f, 0.4f, 0.25f, 0.15f, 0.08f, 0.04f},
        0.002f, 0.35f, 0.15f, 0.25f, 5.0f, 0.2f, 0.0f, 0, 0);
    setPreset(27, "Clean Electric Guitar", 0,
        {1.0f, 0.4f, 0.3f, 0.2f, 0.12f},
        0.003f, 0.3f, 0.3f, 0.2f, 5.0f, 0.1f, 0.0f, 0, 0);
    setPreset(29, "Overdriven Guitar", 1,
        {1.0f, 0.8f, 0.6f, 0.5f, 0.4f, 0.3f, 0.25f, 0.2f},
        0.005f, 0.1f, 0.7f, 0.2f, 3.0f, 0.3f, 8.0f, 0, 0);
    setPreset(30, "Distortion Guitar", 2,
        {1.0f, 0.9f, 0.7f, 0.6f, 0.5f, 0.4f, 0.3f},
        0.003f, 0.08f, 0.75f, 0.15f, 2.5f, 0.4f, 12.0f, 0, 0);

    // --- Bass (32-39) ---
    setPreset(32, "Acoustic Bass", 0,
        {1.0f, 0.7f, 0.4f, 0.2f, 0.1f},
        0.005f, 0.3f, 0.4f, 0.3f, 3.0f, 0.2f, 0.0f, 0, 0);
    setPreset(33, "Electric Bass (finger)", 0,
        {1.0f, 0.5f, 0.3f, 0.15f, 0.08f},
        0.005f, 0.25f, 0.5f, 0.2f, 3.5f, 0.15f, 0.0f, 0, 0);
    setPreset(34, "Electric Bass (pick)", 0,
        {1.0f, 0.6f, 0.4f, 0.25f, 0.15f, 0.08f},
        0.002f, 0.2f, 0.45f, 0.15f, 4.5f, 0.25f, 0.0f, 0, 0);
    setPreset(38, "Synth Bass 1", 1,
        {1.0f, 0.8f, 0.6f, 0.4f, 0.3f},
        0.003f, 0.15f, 0.6f, 0.1f, 3.0f, 0.3f, 5.0f, 0, 0);

    // --- Strings (40-47) ---
    setPreset(40, "Violin", 1,
        {1.0f, 0.6f, 0.3f, 0.15f, 0.08f, 0.04f},
        0.08f, 0.2f, 0.8f, 0.15f, 4.0f, 0.1f, 3.0f, 5.5f, 0.15f);
    setPreset(42, "Cello", 1,
        {1.0f, 0.7f, 0.4f, 0.2f, 0.1f, 0.05f},
        0.1f, 0.25f, 0.8f, 0.2f, 3.0f, 0.1f, 4.0f, 5.0f, 0.12f);
    setPreset(44, "Tremolo Strings", 1,
        {1.0f, 0.5f, 0.25f, 0.12f},
        0.05f, 0.15f, 0.75f, 0.2f, 3.5f, 0.1f, 5.0f, 8.0f, 0.25f);
    setPreset(48, "String Ensemble 1", 1,
        {1.0f, 0.5f, 0.3f, 0.15f, 0.08f},
        0.12f, 0.3f, 0.85f, 0.3f, 3.0f, 0.05f, 10.0f, 4.5f, 0.08f);
    setPreset(49, "String Ensemble 2", 1,
        {1.0f, 0.4f, 0.2f, 0.1f},
        0.15f, 0.35f, 0.8f, 0.4f, 2.5f, 0.05f, 12.0f, 4.0f, 0.06f);

    // --- Brass (56-63) ---
    setPreset(56, "Trumpet", 1,
        {1.0f, 0.8f, 0.6f, 0.4f, 0.3f, 0.2f, 0.15f, 0.1f},
        0.03f, 0.15f, 0.7f, 0.1f, 4.0f, 0.15f, 3.0f, 5.0f, 0.1f);
    setPreset(57, "Trombone", 1,
        {1.0f, 0.7f, 0.5f, 0.35f, 0.25f, 0.18f},
        0.04f, 0.2f, 0.7f, 0.12f, 3.0f, 0.1f, 4.0f, 4.5f, 0.08f);
    setPreset(61, "Brass Section", 1,
        {1.0f, 0.7f, 0.5f, 0.35f, 0.25f, 0.18f, 0.12f},
        0.04f, 0.2f, 0.75f, 0.15f, 3.5f, 0.1f, 8.0f, 0, 0);

    // --- Reed (64-71) ---
    setPreset(64, "Soprano Sax", 1,
        {1.0f, 0.5f, 0.4f, 0.25f, 0.15f, 0.1f},
        0.03f, 0.15f, 0.7f, 0.1f, 4.5f, 0.15f, 2.0f, 5.0f, 0.12f);
    setPreset(65, "Alto Sax", 1,
        {1.0f, 0.6f, 0.45f, 0.3f, 0.2f, 0.12f},
        0.035f, 0.2f, 0.7f, 0.12f, 4.0f, 0.15f, 3.0f, 5.0f, 0.1f);
    setPreset(71, "Clarinet", 2,
        {1.0f, 0.0f, 0.75f, 0.0f, 0.5f, 0.0f, 0.25f},
        0.03f, 0.15f, 0.75f, 0.1f, 3.5f, 0.1f, 2.0f, 5.0f, 0.08f);
    setPreset(73, "Flute", 0,
        {1.0f, 0.3f, 0.1f, 0.05f},
        0.04f, 0.1f, 0.8f, 0.1f, 5.0f, 0.0f, 1.0f, 5.0f, 0.1f);

    // --- Synth Lead (80-87) ---
    setPreset(80, "Square Lead", 2,
        {1.0f, 0.0f, 0.33f, 0.0f, 0.2f, 0.0f, 0.14f},
        0.01f, 0.1f, 0.8f, 0.1f, 4.0f, 0.2f, 5.0f, 0, 0);
    setPreset(81, "Saw Lead", 1,
        {1.0f, 0.5f, 0.33f, 0.25f, 0.2f, 0.17f, 0.14f, 0.12f},
        0.01f, 0.08f, 0.8f, 0.1f, 4.0f, 0.15f, 8.0f, 0, 0);

    // --- Synth Pad (88-95) ---
    setPreset(88, "New Age Pad", 0,
        {1.0f, 0.3f, 0.0f, 0.15f, 0.0f, 0.08f},
        0.3f, 0.5f, 0.7f, 0.8f, 2.5f, 0.0f, 6.0f, 3.0f, 0.05f);
    setPreset(89, "Warm Pad", 1,
        {1.0f, 0.4f, 0.2f, 0.1f},
        0.4f, 0.6f, 0.75f, 1.0f, 2.0f, 0.05f, 10.0f, 3.5f, 0.06f);
    setPreset(92, "Space Voice Pad", 0,
        {1.0f, 0.2f, 0.4f, 0.1f, 0.2f},
        0.5f, 0.8f, 0.6f, 1.2f, 2.0f, 0.1f, 12.0f, 4.0f, 0.08f);
    setPreset(95, "Sweep Pad", 1,
        {1.0f, 0.5f, 0.3f, 0.15f},
        0.6f, 1.0f, 0.65f, 1.5f, 2.0f, 0.3f, 15.0f, 0.5f, 0.3f);

    // Fill gaps with default piano-like preset
    for (int i = 0; i < 128; ++i)
    {
        if (presets[i].name.isEmpty())
        {
            presets[i] = presets[0]; // Copy grand piano
            presets[i].name = "Program " + juce::String (i);
        }
    }
}

const InstrumentPreset& SynthEngine::getPreset (int program)
{
    initPresets();
    return presets[juce::jlimit (0, 127, program)];
}

//==============================================================================
// SynthVoice
//==============================================================================
SynthVoice::SynthVoice() {}

bool SynthVoice::canPlaySound (juce::SynthesiserSound* sound)
{
    return dynamic_cast<SynthSound*> (sound) != nullptr;
}

void SynthVoice::startNote (int midiNoteNumber, float velocity,
                             juce::SynthesiserSound*, int pitchWheel)
{
    currentNote   = midiNoteNumber;
    noteVelocity  = velocity;
    vibratoPhase  = 0.0;

    std::fill (std::begin (phases), std::end (phases), 0.0);
    std::fill (std::begin (osc2Phases), std::end (osc2Phases), 0.0);
    std::fill (std::begin (filterLow), std::end (filterLow), 0.0f);
    std::fill (std::begin (filterBand), std::end (filterBand), 0.0f);

    double bend = (static_cast<double>(pitchWheel) - 8192.0) / 8192.0 * 2.0;
    pitchBendFactor = static_cast<float>(std::pow (2.0, bend / 12.0));
    baseFreq = noteToFrequency (currentNote) * pitchBendFactor;

    if (currentPreset)
    {
        juce::ADSR::Parameters p { currentPreset->attack, currentPreset->decay,
                                    currentPreset->sustain, currentPreset->release };
        adsr.setParameters (p);
    }
    else
    {
        adsr.setParameters ({ 0.01f, 0.3f, 0.6f, 0.5f });
    }
    adsr.setSampleRate (getSampleRate());
    adsr.noteOn();
}

void SynthVoice::stopNote (float, bool allowTailOff)
{
    if (allowTailOff) adsr.noteOff();
    else { adsr.reset(); clearCurrentNote(); }
}

void SynthVoice::pitchWheelMoved (int val)
{
    double bend = (static_cast<double>(val) - 8192.0) / 8192.0 * 2.0;
    pitchBendFactor = static_cast<float>(std::pow (2.0, bend / 12.0));
    baseFreq = noteToFrequency (currentNote) * pitchBendFactor;
}

void SynthVoice::controllerMoved (int, int) {}

float SynthVoice::generateSample (double freq, int /*channel*/)
{
    const InstrumentPreset& preset = currentPreset ? *currentPreset
        : SynthEngine::getPreset (0);

    float sample = 0.0f;
    double sr = getSampleRate();
    if (sr <= 0) return 0.0f;

    int nh = juce::jlimit (1, 16, preset.numHarmonics);

    for (int h = 0; h < nh; ++h)
    {
        double harmFreq = freq * (h + 1);
        if (harmFreq > sr * 0.45) break; // anti-aliasing: skip above Nyquist

        double phaseInc = harmFreq / sr;
        float amp = preset.harmonics[h];

        float wave = 0.0f;
        double ph = phases[h];

        switch (preset.waveType)
        {
            case 0: // Sine
                wave = static_cast<float>(std::sin (ph * 2.0 * juce::MathConstants<double>::pi));
                break;
            case 1: // Saw (band-limited via harmonics)
                wave = static_cast<float>(2.0 * (ph - std::floor (ph + 0.5)));
                break;
            case 2: // Square
                wave = ph < 0.5 ? 1.0f : -1.0f;
                break;
            case 3: // Triangle
                wave = static_cast<float>(4.0 * std::abs (ph - std::floor (ph + 0.5)) - 1.0);
                break;
            default:
                wave = static_cast<float>(std::sin (ph * 2.0 * juce::MathConstants<double>::pi));
        }

        sample += wave * amp;
        phases[h] = std::fmod (ph + phaseInc, 1.0);
    }

    // Second detuned oscillator
    if (preset.detuneCents > 0.1f)
    {
        double detuneRatio = std::pow (2.0, preset.detuneCents / 1200.0);
        float osc2Sample = 0.0f;
        for (int h = 0; h < nh; ++h)
        {
            double harmFreq = freq * detuneRatio * (h + 1);
            if (harmFreq > sr * 0.45) break;
            double phaseInc = harmFreq / sr;
            double ph = osc2Phases[h];
            float wave = static_cast<float>(std::sin (ph * 2.0 * juce::MathConstants<double>::pi));
            osc2Sample += wave * preset.harmonics[h];
            osc2Phases[h] = std::fmod (ph + phaseInc, 1.0);
        }
        sample = sample * 0.65f + osc2Sample * 0.35f;
    }

    // Normalize by number of harmonics
    if (nh > 1)
        sample /= static_cast<float>(nh) * 0.5f;

    return sample;
}

void SynthVoice::updateFilter (float& sample, int ch, float cutoff, float resonance)
{
    float sr = static_cast<float>(getSampleRate());
    if (sr <= 0) return;

    float f = 2.0f * std::sin (juce::MathConstants<float>::pi * cutoff / sr);
    f = juce::jlimit (0.0f, 1.0f, f);
    float q = 1.0f - resonance;
    q = juce::jlimit (0.2f, 1.0f, q);

    filterLow[ch]  += f * filterBand[ch];
    float high      = sample - filterLow[ch] - q * filterBand[ch];
    filterBand[ch] += f * high;
    sample = filterLow[ch];
}

void SynthVoice::renderNextBlock (juce::AudioBuffer<float>& buffer,
                                   int startSample, int numSamples)
{
    if (! isVoiceActive()) return;

    const InstrumentPreset& preset = currentPreset ? *currentPreset
        : SynthEngine::getPreset (0);

    int numCh = buffer.getNumChannels();
    double sr = getSampleRate();

    for (int i = 0; i < numSamples; ++i)
    {
        // Vibrato
        double vibMod = 0.0;
        if (preset.vibratoRate > 0.0f && preset.vibratoDepth > 0.0f)
        {
            vibMod = std::sin (vibratoPhase * 2.0 * juce::MathConstants<double>::pi)
                     * preset.vibratoDepth;
            vibratoPhase += preset.vibratoRate / sr;
            if (vibratoPhase >= 1.0) vibratoPhase -= 1.0;
        }

        double freq = baseFreq * std::pow (2.0, vibMod / 12.0);
        float rawSample = generateSample (freq, 0);

        // Filter
        float cutoff = static_cast<float>(freq * preset.filterCutoffMultiplier);
        cutoff = juce::jlimit (20.0f, static_cast<float>(sr * 0.49), cutoff);

        // Apply envelope
        float env = adsr.getNextSample();
        float shaped = rawSample * env * noteVelocity;

        // Filter per channel
        for (int ch = 0; ch < juce::jmin (numCh, 2); ++ch)
        {
            float s = shaped;
            // Slight stereo offset for width
            if (ch == 1 && preset.stereoWidth > 0.01f)
                s *= (1.0f - preset.stereoWidth * 0.5f);
            updateFilter (s, ch, cutoff, preset.filterResonance);
            buffer.addSample (ch, startSample + i, s);
        }

        if (! adsr.isActive())
        {
            clearCurrentNote();
            break;
        }
    }
}

//==============================================================================
// SynthEngine
//==============================================================================
SynthEngine::SynthEngine()
{
    initPresets();
    synth.addSound (new SynthSound());
    setNumVoices (defaultNumVoices);
}

void SynthEngine::prepareToPlay (double sampleRate, int)
{
    currentSampleRate = sampleRate;
    synth.setCurrentPlaybackSampleRate (sampleRate);
}

void SynthEngine::renderNextBlock (juce::AudioBuffer<float>& buffer,
                                    const juce::MidiBuffer& midiMessages,
                                    int startSample, int numSamples)
{
    synth.renderNextBlock (buffer, midiMessages, startSample, numSamples);
}

void SynthEngine::noteOn (int channel, int noteNumber, float velocity)
{
    synth.noteOn (channel, noteNumber, velocity);
}

void SynthEngine::noteOff (int channel, int noteNumber)
{
    synth.noteOff (channel, noteNumber, 0.0f, true);
}

void SynthEngine::allNotesOff()
{
    synth.allNotesOff (0, true);
}

void SynthEngine::setProgram (int channel, int program)
{
    if (channel >= 0 && channel < 16)
        channelPrograms[channel] = juce::jlimit (0, 127, program);

    // Update preset on all voices for this channel
    const auto* preset = &getPreset (program);
    for (int i = 0; i < synth.getNumVoices(); ++i)
    {
        if (auto* voice = dynamic_cast<SynthVoice*>(synth.getVoice(i)))
            voice->setPreset (preset);
    }
}

void SynthEngine::setNumVoices (int numVoices)
{
    synth.clearVoices();
    const auto* defaultPreset = &getPreset (0);
    for (int i = 0; i < numVoices; ++i)
    {
        auto* v = new SynthVoice();
        v->setPreset (defaultPreset);
        synth.addVoice (v);
    }
    if (currentSampleRate > 0.0)
        synth.setCurrentPlaybackSampleRate (currentSampleRate);
}
