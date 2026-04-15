/*
 * MidiGPT DAW — Automation
 *
 * Time-anchored parameter envelopes. AutomationPoint = (beat, value, shape).
 * AutomationLane is owned by a Track and targets a string parameter id
 * ("volume", "pan", or pluginUid + "/" + paramName for plugin params).
 *
 * Sprint scope:
 *   - Data model + linear interpolation between points
 *   - AutomationEngine::applyAtBeat() — called from MidiEngine block boundary
 *     to set Track::volume / pan, or push parameter changes to plugin instances
 *   - Editing UI is minimal: ArrangementView shows lanes as polylines.
 *     Drawing/editing points by mouse is added in Sprint 3 (see TODO).
 */

#pragma once

#include <juce_core/juce_core.h>
#include <vector>
#include <algorithm>

struct AutomationPoint
{
    double beat   { 0.0 };
    float  value  { 0.0f }; // normalized 0..1
};

struct AutomationLane
{
    juce::String paramId;          // "volume" / "pan" / "<pluginUid>/<paramName>"
    std::vector<AutomationPoint> points;
    bool enabled { true };

    /** Linear-interpolated value at `beat`. Returns defaultValue if lane is
     *  empty. Out-of-range beats clamp to first/last point. */
    float valueAt(double beat, float defaultValue = 0.0f) const
    {
        if (points.empty() || ! enabled) return defaultValue;
        if (beat <= points.front().beat) return points.front().value;
        if (beat >= points.back().beat)  return points.back().value;

        // Binary search for surrounding pair
        auto it = std::upper_bound(points.begin(), points.end(), beat,
            [](double b, const AutomationPoint& p) { return b < p.beat; });
        if (it == points.begin() || it == points.end()) return defaultValue;

        auto& hi = *it;
        auto& lo = *(it - 1);
        const double span = hi.beat - lo.beat;
        if (span <= 0.0) return lo.value;
        const double t = (beat - lo.beat) / span;
        return lo.value + (hi.value - lo.value) * (float)t;
    }

    void addPoint(double beat, float value)
    {
        AutomationPoint p { beat, juce::jlimit(0.0f, 1.0f, value) };
        // Insert sorted by beat
        auto it = std::lower_bound(points.begin(), points.end(), p,
            [](const AutomationPoint& a, const AutomationPoint& b)
            { return a.beat < b.beat; });
        points.insert(it, p);
    }

    void clear() { points.clear(); }
};
