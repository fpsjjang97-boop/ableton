/*
 * MidiGPT VST3 Plugin — I18n (ko / en)
 *
 * Minimal string-table-based localisation. The plugin shipped with a lot
 * of Korean-first strings (status messages, labels) that made onboarding
 * for non-Korean testers awkward. This table exposes an English mirror so
 * the UI can switch at runtime.
 *
 * Sprint 35 ZZ3. We deliberately stay under 50 entries so every string is
 * hand-translated. Larger tables would want juce::TranslatableString / .po
 * tooling, overkill at this scope.
 *
 * Usage:
 *   I18n::setLanguage (I18n::Lang::EN);
 *   auto msg = I18n::t ("status.ready");      // → "Ready" or "준비됨"
 *
 * The caller is responsible for calling I18n::t() at render time (not
 * cache) so that language switches take effect immediately.
 */

#pragma once

#include <juce_core/juce_core.h>

class I18n
{
public:
    enum class Lang { KO, EN };

    static Lang& current() { static Lang l = Lang::KO; return l; }
    static void setLanguage (Lang l) { current() = l; }
    static bool isEnglish() { return current() == Lang::EN; }

    /** Look up a key. Unknown keys return the key itself (makes missing
        translations obvious in the UI rather than silently blanking). */
    static juce::String t (const juce::String& key)
    {
        const auto lang = current();
        for (const auto& row : table())
            if (key == row.key)
                return lang == Lang::KO ? row.ko : row.en;
        return key;
    }

private:
    struct Row { const char* key; const char* ko; const char* en; };

    static const juce::Array<Row>& table()
    {
        static const juce::Array<Row> rows
        {
            // --- Status / feedback
            { "status.ready",             "준비됨",                         "Ready" },
            { "status.generating",        "서버에 생성 요청 중...",         "Generating..." },
            { "status.generation_done",   "생성 완료",                      "Generation complete" },
            { "status.generation_fail",   "생성 실패",                      "Generation failed" },
            { "status.no_input",
              "캡처된 MIDI 가 없습니다. 재생 중 MIDI 를 입력한 뒤 다시 시도하세요.",
              "No captured MIDI. Play some MIDI in and try again." },
            { "status.cancelled",         "취소됨",                         "Cancelled" },
            { "status.lora_loading",      "LoRA 로드 중",                    "Loading LoRA" },
            { "status.lora_loaded",       "LoRA 로드 완료",                  "LoRA loaded" },
            { "status.lora_failed",       "LoRA 로드 실패",                  "LoRA load failed" },
            { "status.preset_saved",      "프리셋 저장",                     "Preset saved" },
            { "status.preset_loaded",     "프리셋 로드됨",                   "Preset loaded" },
            { "status.preset_save_fail",  "프리셋 저장 실패",                "Preset save failed" },
            { "status.undo",              "Undo — 이전 생성 결과 복원",      "Undo — reverted to prior generation" },
            { "status.redo",              "Redo — 다음 생성 결과 복원",      "Redo — restored next generation" },
            { "status.export_ok",         "내보내기 완료",                   "Export complete" },
            { "status.export_empty",      "내보낼 생성 결과가 없습니다",     "Nothing to export yet" },
            { "status.a2m_running",       "⚠ Audio2MIDI (Beta) 변환 중... 30~120초 소요", "⚠ Audio2MIDI (Beta) running... 30-120s" },
            { "status.a2m_done",          "Beta — 편집 필요",                "Beta — manual cleanup advised" },

            // --- Button labels / tooltips
            { "btn.generate",             "Generate Variation",              "Generate Variation" },
            { "btn.cancel",               "Cancel",                          "Cancel" },
            { "btn.clear",                "Clear Input",                     "Clear Input" },
            { "btn.export",               "Export MIDI",                     "Export MIDI" },
            { "btn.info",                 "Server Info",                     "Server Info" },
            { "btn.undo",                 "Undo",                            "Undo" },
            { "btn.redo",                 "Redo",                            "Redo" },
            { "btn.save_preset",          "Save Preset",                     "Save Preset" },
            { "btn.delete_preset",        "Delete",                          "Delete" },
            { "btn.theme_dark",           "Dark",                            "Dark" },
            { "btn.theme_light",          "Light",                           "Light" },

            { "tip.generate",             "현재 캡처된 MIDI 로 새 변주를 생성합니다. (Space)",
                                          "Generate a variation from captured MIDI. (Space)" },
            { "tip.cancel",               "진행 중인 생성 요청을 취소합니다. (Esc)",
                                          "Cancel an in-flight generation. (Esc)" },
            { "tip.clear",                "캡처 버퍼를 비웁니다. (Ctrl+K)",
                                          "Clear captured input buffer. (Ctrl+K)" },
            { "tip.export",               "마지막 생성 결과를 .mid 파일로 저장합니다. (Ctrl+E)",
                                          "Export last generation to .mid. (Ctrl+E)" },
            { "tip.info",                 "서버 상태와 모델 정보를 표시합니다. (Ctrl+I)",
                                          "Show server state / model info. (Ctrl+I)" },
            { "tip.undo",                 "이전 생성 결과로 복원. (Ctrl+Z)",
                                          "Restore previous generation. (Ctrl+Z)" },
            { "tip.redo",                 "다음 생성 결과로 복원. (Ctrl+Shift+Z)",
                                          "Restore next generation. (Ctrl+Shift+Z)" },
            { "tip.temperature",          "샘플링 다양성. 높을수록 창의적, 낮을수록 보수적.",
                                          "Sampling diversity. Higher = more creative, lower = safer." },
            { "tip.variations",           "한 번에 생성할 후보 수 (1-5).",
                                          "Number of candidate variations per run (1-5)." },
            { "tip.style",                "LoRA 어댑터 선택 — 변경 시 서버에서 즉시 hot-swap.",
                                          "Select LoRA adapter — hot-swapped on change." },
            { "tip.preset",               "저장된 파라미터 프리셋 로드.",
                                          "Load a saved parameter preset." },
            { "tip.save_preset",          "현재 파라미터를 프리셋으로 저장.",
                                          "Save current parameters as a preset." },
            { "tip.delete_preset",        "선택한 프리셋을 삭제.",
                                          "Delete selected preset." },
            { "tip.theme",                "다크/라이트 테마 전환.",
                                          "Toggle dark/light theme." },
            { "tip.drop",                 ".mid / .midi 파일 또는 .wav/.mp3 (Beta) 를 여기에 드롭.",
                                          "Drop .mid/.midi here, or .wav/.mp3 (Beta)." },

            // --- Piano roll placeholders
            { "roll.input.title",         "Input (Captured)",                "Input (Captured)" },
            { "roll.output.title",        "Output (Generated)",              "Output (Generated)" },
            { "roll.input.empty",
              "MIDI 재생/입력 또는 .mid 파일을 여기로 드롭",
              "Play MIDI or drop a .mid file here" },
            { "roll.output.empty",
              "Generate 버튼을 누르면 결과가 표시됩니다",
              "Press Generate to see the result" },

            // --- Tutorial (ZZ5 first-run overlay)
            { "tut.step1.title",
              "환영합니다 — MidiGPT",
              "Welcome to MidiGPT" },
            { "tut.step1.body",
              "DAW 안에서 AI 기반 MIDI 변주를 생성하는 플러그인입니다. "
              "입력 MIDI 를 받아 같은 스타일/다른 변주를 제안합니다. "
              "Next 를 눌러 둘러보세요.",
              "MidiGPT generates AI-driven MIDI variations inside your DAW. "
              "Feed it MIDI and it suggests alternative takes in the same style. "
              "Click Next for a quick tour." },
            { "tut.step2.title",
              "① MIDI 캡처",
              "1. Capture MIDI" },
            { "tut.step2.body",
              "호스트에서 재생 중인 MIDI 는 자동으로 캡처됩니다. "
              "또는 .mid / .wav 파일을 창 위로 드래그해도 됩니다.",
              "The plugin captures MIDI played by the host. "
              "You can also drag a .mid / .wav file onto the window." },
            { "tut.step3.title",
              "② 파라미터",
              "2. Parameters" },
            { "tut.step3.body",
              "Temperature 는 창의성, Style 은 LoRA 어댑터 (변경 시 자동 hot-swap). "
              "프리셋으로 조합을 저장할 수 있습니다.",
              "Temperature = creativity. Style picks a LoRA adapter (hot-swapped on change). "
              "Save parameter combos as presets." },
            { "tut.step4.title",
              "③ 생성",
              "3. Generate" },
            { "tut.step4.body",
              "Generate 버튼 또는 Space 키. 생성된 MIDI 는 다음 박자에 맞춰 재생되며, "
              "Cubase 가 바로 녹음할 수 있도록 MIDI out 으로 나갑니다.",
              "Press Generate or hit Space. The result plays back aligned to the next beat, "
              "via MIDI out so your DAW can record it directly." },
            { "tut.step5.title",
              "④ 편집 / 내보내기",
              "4. Edit / Export" },
            { "tut.step5.body",
              "마음에 안 드는 결과는 Undo (Ctrl+Z) 로 이전 후보로 돌아갈 수 있습니다. "
              "Export MIDI (Ctrl+E) 로 저장하세요.",
              "Undo (Ctrl+Z) returns to earlier candidates. "
              "Export MIDI (Ctrl+E) saves the current result to a file." },
        };
        return rows;
    }

    JUCE_DECLARE_NON_COPYABLE (I18n)
    I18n() = delete;
};
