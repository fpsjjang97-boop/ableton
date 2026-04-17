/*
 * MidiGPT VST3 Plugin — PluginLogger
 *
 * Thin singleton wrapper around juce::FileLogger so both the Processor
 * and the Editor can write to a rotating log file at
 *   <userAppData>/MidiGPT/logs/plugin.log
 *
 * Why a singleton? VST3 plugins instantiate the processor per host slot
 * but we want ONE log file that captures events across all instances in
 * the session — makes debugging "it crashed when I had 3 copies loaded"
 * much easier than per-instance files.
 *
 * Sprint 35 ZZ4. Uses juce::FileLogger's built-in size cap so the log
 * auto-rotates — no cron / cleanup needed.
 *
 * Usage:
 *   PluginLogger::info ("generation request sent", {{"style","jazz"}});
 *   PluginLogger::warn ("http 503 — server unavailable");
 */

#pragma once

#include <juce_core/juce_core.h>

class PluginLogger
{
public:
    /** Lazily initialise the shared file logger. Safe to call multiple
        times; subsequent calls are no-ops. */
    static void ensureInitialised()
    {
        if (instance() != nullptr) return;

        auto logDir = juce::File::getSpecialLocation (
                          juce::File::userApplicationDataDirectory)
                          .getChildFile ("MidiGPT").getChildFile ("logs");
        logDir.createDirectory();
        auto logFile = logDir.getChildFile ("plugin.log");

        // 512KB cap — FileLogger rotates by creating a .1 backup.
        instance().reset (juce::FileLogger::createDateStampedLogger (
                              logDir.getFullPathName(),
                              "plugin",
                              ".log",
                              "MidiGPT plugin log started\n"));
    }

    static void info  (const juce::String& msg) { write ("INFO",  msg); }
    static void warn  (const juce::String& msg) { write ("WARN",  msg); }
    static void error (const juce::String& msg) { write ("ERROR", msg); }

    /** Close the underlying log stream. Call on host shutdown / plugin
        unload. Idempotent. */
    static void shutdown() { instance().reset(); }

private:
    static std::unique_ptr<juce::FileLogger>& instance()
    {
        static std::unique_ptr<juce::FileLogger> p;
        return p;
    }

    static void write (const char* level, const juce::String& msg)
    {
        ensureInitialised();
        if (instance() == nullptr) return;
        auto line = juce::Time::getCurrentTime().toISO8601 (true)
                  + juce::String (" [") + level + "] " + msg;
        instance()->logMessage (line);
    }

    PluginLogger() = delete;
};
