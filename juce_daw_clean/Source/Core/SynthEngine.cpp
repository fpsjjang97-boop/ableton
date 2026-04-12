/*
 * MidiGPT DAW - SynthEngine.cpp
 */

#include "SynthEngine.h"

SynthEngine::SynthEngine()
{
    channelProgram.fill(0);
    initPresets();
}

void SynthEngine::initPresets()
{
    // Default: all presets start as sine piano
    for (auto& p : presets)
    {
        p.waveType = 0;
        p.attack = 0.005f;
        p.decay = 0.3f;
        p.sustain = 0.4f;
        p.release = 0.3f;
        p.harmonics = {{ 1.0f, 0.5f, 0.25f, 0.12f, 0.06f, 0.03f, 0.0f, 0.0f }};
        p.filterCutoff = 6.0f;
        p.filterQ = 0.2f;
    }

    // 0-7: Pianos
    for (int i = 0; i <= 7; ++i)
    {
        presets[i].harmonics = {{ 1.0f, 0.6f, 0.3f, 0.15f, 0.08f, 0.04f, 0.02f, 0.01f }};
        presets[i].decay = 0.4f;
        presets[i].sustain = 0.3f;
        presets[i].release = 0.4f;
        presets[i].filterCutoff = 8.0f;
    }
    presets[1].filterCutoff = 12.0f; // Bright piano
    presets[4].waveType = 0; // EP1
    presets[4].harmonics = {{ 1.0f, 0.3f, 0.1f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f }};
    presets[4].decay = 0.8f;
    presets[4].sustain = 0.2f;

    // 8-15: Chromatic percussion
    for (int i = 8; i <= 15; ++i)
    {
        presets[i].attack = 0.001f;
        presets[i].decay = 0.5f;
        presets[i].sustain = 0.0f;
        presets[i].release = 0.3f;
        presets[i].filterCutoff = 10.0f;
    }

    // 16-23: Organ
    for (int i = 16; i <= 23; ++i)
    {
        presets[i].attack = 0.01f;
        presets[i].decay = 0.05f;
        presets[i].sustain = 0.9f;
        presets[i].release = 0.08f;
        presets[i].harmonics = {{ 1.0f, 0.8f, 0.6f, 0.4f, 0.3f, 0.2f, 0.15f, 0.1f }};
    }

    // 24-31: Guitar
    for (int i = 24; i <= 31; ++i)
    {
        presets[i].waveType = 1; // saw
        presets[i].attack = 0.002f;
        presets[i].decay = 0.5f;
        presets[i].sustain = 0.2f;
        presets[i].release = 0.2f;
        presets[i].filterCutoff = 5.0f;
        presets[i].filterQ = 0.3f;
        presets[i].detuneCents = 5.0f;
    }

    // 32-39: Bass
    for (int i = 32; i <= 39; ++i)
    {
        presets[i].harmonics = {{ 1.0f, 0.7f, 0.3f, 0.1f, 0.0f, 0.0f, 0.0f, 0.0f }};
        presets[i].attack = 0.003f;
        presets[i].decay = 0.3f;
        presets[i].sustain = 0.5f;
        presets[i].release = 0.15f;
        presets[i].filterCutoff = 3.0f;
    }
    presets[38].waveType = 1; // synth bass = saw
    presets[38].filterCutoff = 4.0f;
    presets[38].filterQ = 0.5f;

    // 40-49: Strings
    for (int i = 40; i <= 49; ++i)
    {
        presets[i].waveType = 1;
        presets[i].attack = 0.08f;
        presets[i].decay = 0.2f;
        presets[i].sustain = 0.7f;
        presets[i].release = 0.3f;
        presets[i].detuneCents = 8.0f;
        presets[i].filterCutoff = 5.0f;
    }

    // 56-63: Brass
    for (int i = 56; i <= 63; ++i)
    {
        presets[i].waveType = 1;
        presets[i].attack = 0.03f;
        presets[i].decay = 0.15f;
        presets[i].sustain = 0.8f;
        presets[i].release = 0.12f;
        presets[i].filterCutoff = 6.0f;
        presets[i].filterQ = 0.4f;
    }

    // 64-79: Reeds/Pipes
    for (int i = 64; i <= 79; ++i)
    {
        presets[i].waveType = 2; // square
        presets[i].attack = 0.02f;
        presets[i].sustain = 0.7f;
        presets[i].filterCutoff = 4.0f;
    }
    // Flute
    presets[73].waveType = 0;
    presets[73].harmonics = {{ 1.0f, 0.1f, 0.05f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f }};
    presets[73].filterCutoff = 10.0f;

    // 80-87: Synth leads
    for (int i = 80; i <= 87; ++i)
    {
        presets[i].waveType = (i % 2 == 0) ? 2 : 1;
        presets[i].attack = 0.005f;
        presets[i].sustain = 0.8f;
        presets[i].filterCutoff = 6.0f;
        presets[i].detuneCents = 10.0f;
    }

    // 88-95: Synth pads
    for (int i = 88; i <= 95; ++i)
    {
        presets[i].waveType = 1;
        presets[i].attack = 0.2f;
        presets[i].decay = 0.3f;
        presets[i].sustain = 0.8f;
        presets[i].release = 0.5f;
        presets[i].detuneCents = 12.0f;
        presets[i].filterCutoff = 4.0f;
    }
}

void SynthEngine::prepare(double sr, int /*blockSize*/)
{
    sampleRate = sr;
    allNotesOff();
}

void SynthEngine::allNotesOff()
{
    for (auto& v : voices)
    {
        v.active = false;
        v.envStage = Voice::Off;
        v.envLevel = 0.0f;
    }
}

void SynthEngine::setProgramForChannel(int channel, int program)
{
    if (channel >= 0 && channel < 16 && program >= 0 && program < 128)
        channelProgram[static_cast<size_t>(channel)] = program;
}

SynthEngine::Voice* SynthEngine::findFreeVoice()
{
    for (auto& v : voices)
        if (!v.active) return &v;

    // Steal oldest releasing voice
    Voice* quietest = nullptr;
    float minLevel = 999.0f;
    for (auto& v : voices)
    {
        if (v.envStage == Voice::Release && v.envLevel < minLevel)
        {
            minLevel = v.envLevel;
            quietest = &v;
        }
    }
    if (quietest) return quietest;

    // Steal quietest voice overall
    for (auto& v : voices)
    {
        if (v.envLevel < minLevel)
        {
            minLevel = v.envLevel;
            quietest = &v;
        }
    }
    return quietest;
}

void SynthEngine::noteOn(int channel, int note, float velocity)
{
    auto* v = findFreeVoice();
    if (!v) return;

    int prog = channelProgram[static_cast<size_t>(channel & 15)];
    auto& preset = presets[static_cast<size_t>(prog)];

    v->active = true;
    v->note = note;
    v->channel = channel;
    v->velocity = velocity;
    v->phase1 = 0.0;
    v->phase2 = 0.0;

    double freq = 440.0 * std::pow(2.0, (note - 69) / 12.0);
    v->phaseInc = freq / sampleRate;

    v->envStage = Voice::Attack;
    v->envLevel = 0.0f;

    v->attack = preset.attack;
    v->decay = preset.decay;
    v->sustainLvl = preset.sustain;
    v->release = preset.release;
    v->waveType = preset.waveType;
    v->detuneCents = preset.detuneCents;
    v->filterCutoffMul = preset.filterCutoff;
    v->filterQ = preset.filterQ;
    v->filterLp = 0.0f;
    v->filterBp = 0.0f;
}

void SynthEngine::noteOff(int channel, int note)
{
    for (auto& v : voices)
    {
        if (v.active && v.note == note && v.channel == channel
            && v.envStage != Voice::Release)
        {
            v.envStage = Voice::Release;
        }
    }
}

void SynthEngine::advanceEnvelope(Voice& v)
{
    float rate;
    switch (v.envStage)
    {
        case Voice::Attack:
            rate = v.attack > 0.0f ? 1.0f / (v.attack * (float)sampleRate) : 1.0f;
            v.envLevel += rate;
            if (v.envLevel >= 1.0f) { v.envLevel = 1.0f; v.envStage = Voice::Decay; }
            break;
        case Voice::Decay:
            rate = v.decay > 0.0f ? 1.0f / (v.decay * (float)sampleRate) : 1.0f;
            v.envLevel -= rate * (1.0f - v.sustainLvl);
            if (v.envLevel <= v.sustainLvl) { v.envLevel = v.sustainLvl; v.envStage = Voice::Sustain; }
            break;
        case Voice::Sustain:
            break;
        case Voice::Release:
            rate = v.release > 0.0f ? 1.0f / (v.release * (float)sampleRate) : 1.0f;
            v.envLevel -= rate;
            if (v.envLevel <= 0.0f) { v.envLevel = 0.0f; v.active = false; v.envStage = Voice::Off; }
            break;
        default:
            break;
    }
}

float SynthEngine::renderVoiceSample(Voice& v)
{
    double pi2 = juce::MathConstants<double>::twoPi;
    float sample = 0.0f;

    // Primary oscillator
    switch (v.waveType)
    {
        case 0: // sine with harmonics
        {
            // Approximate harmonic richness
            sample = static_cast<float>(std::sin(pi2 * v.phase1));
            sample += 0.5f * static_cast<float>(std::sin(pi2 * v.phase1 * 2.0));
            sample += 0.25f * static_cast<float>(std::sin(pi2 * v.phase1 * 3.0));
            sample *= 0.5f;
            break;
        }
        case 1: // saw
            sample = static_cast<float>(2.0 * v.phase1 - 1.0);
            break;
        case 2: // square
            sample = (v.phase1 < 0.5) ? 0.7f : -0.7f;
            break;
        case 3: // triangle
            sample = static_cast<float>(4.0 * std::abs(v.phase1 - 0.5) - 1.0);
            break;
    }

    // Detuned second oscillator
    if (v.detuneCents > 0.0f)
    {
        float s2;
        switch (v.waveType)
        {
            case 1: s2 = static_cast<float>(2.0 * v.phase2 - 1.0); break;
            case 2: s2 = (v.phase2 < 0.5) ? 0.7f : -0.7f; break;
            default: s2 = static_cast<float>(std::sin(pi2 * v.phase2)); break;
        }
        sample = sample * 0.65f + s2 * 0.35f;
    }

    // Simple low-pass filter (state variable)
    float freq = static_cast<float>(v.phaseInc * sampleRate) * v.filterCutoffMul;
    float f = 2.0f * std::sin(juce::MathConstants<float>::pi * juce::jmin(freq / (float)sampleRate, 0.45f));
    float q = 1.0f - v.filterQ;

    v.filterLp += f * v.filterBp;
    float hp = sample - v.filterLp - q * v.filterBp;
    v.filterBp += f * hp;
    sample = v.filterLp;

    // Advance phases
    v.phase1 += v.phaseInc;
    if (v.phase1 >= 1.0) v.phase1 -= 1.0;

    double detuneRatio = std::pow(2.0, v.detuneCents / 1200.0);
    v.phase2 += v.phaseInc * detuneRatio;
    if (v.phase2 >= 1.0) v.phase2 -= 1.0;

    // Apply envelope and velocity (ensure audible output)
    advanceEnvelope(v);
    sample *= v.envLevel * (0.3f + v.velocity * 0.7f) * 1.5f;

    return sample;
}

void SynthEngine::renderBlock(juce::AudioBuffer<float>& buffer, const juce::MidiBuffer& midi)
{
    // Process MIDI events
    for (const auto metadata : midi)
    {
        auto msg = metadata.getMessage();
        int ch = msg.getChannel() - 1;

        if (msg.isNoteOn())
            noteOn(ch, msg.getNoteNumber(), msg.getFloatVelocity());
        else if (msg.isNoteOff())
            noteOff(ch, msg.getNoteNumber());
        else if (msg.isProgramChange())
            setProgramForChannel(ch, msg.getProgramChangeNumber());
        else if (msg.isAllNotesOff() || msg.isAllSoundOff())
            allNotesOff();
    }

    // Render audio
    int numSamples = buffer.getNumSamples();
    int numChannels = buffer.getNumChannels();

    for (int s = 0; s < numSamples; ++s)
    {
        float mixL = 0.0f;
        float mixR = 0.0f;

        for (auto& v : voices)
        {
            if (!v.active) continue;
            float sample = renderVoiceSample(v);
            mixL += sample;
            mixR += sample;
        }

        // Soft clip (gentle)
        mixL = std::tanh(mixL) * 0.8f;
        mixR = std::tanh(mixR) * 0.8f;

        if (numChannels >= 1) buffer.addSample(0, s, mixL);
        if (numChannels >= 2) buffer.addSample(1, s, mixR);
    }
}
