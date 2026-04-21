# DAW 캡처 스키마 v1 (Sprint XXX)

종합 리뷰 §12 "사용자 데이터 입력/캡처 기능" 및 §20-9 "user data capture
스키마 설계" 대응.

DAW 의 "Capture" 기능이 호출될 때, 프로젝트/트랙/구간/AI 상호작용 정보를
이 스키마에 맞춰 JSON 으로 저장한다. 이후 retrieval / preference /
user adapter 학습의 공통 포맷.

## 파일 위치

- 기본: `%APPDATA%/MidiGPT/captures/` (Windows), `~/.midigpt/captures/` (Linux)
- 파일명: `capture_{session_id}_{timestamp}.json`
- MIDI / WAV 원본은 같은 디렉토리에 `capture_{session_id}.mid` / `.wav` 로 병렬 저장

## 최상위 구조

```json
{
  "schema_version": 1,
  "session_id":     "uuid-v4",
  "captured_at":    "2026-04-21T14:30:00Z",
  "user_id":        "local:jisu",
  "project":  { ... },
  "tracks":   [ ... ],
  "region":   { ... },
  "ai_interaction": { ... },
  "audio_refs":     [ ... ],
  "notes":          "(자유 텍스트)"
}
```

## `project` — 프로젝트 단위 메타

| 필드 | 타입 | 설명 |
|------|------|------|
| `genre` | string | 장르 ("pop", "edm", "orchestral", …) |
| `bpm` | float | BPM |
| `time_sig_num` | int | 박자표 분자 |
| `time_sig_den` | int | 박자표 분모 |
| `key` | string | "C" / "Am" 등 |
| `section_map` | array | `[[start_bar, "verse"], [8, "chorus"], …]` |
| `mood` | string | 분위기 ("dark", "uplifting", …) |
| `energy` | float | 0.0~1.0 |
| `daw_version` | string | 빌드/버전 문자열 |

## `tracks` — 트랙별 메타 (array)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | int | DAW 내부 track id |
| `name` | string | 트랙 표시 이름 |
| `kind` | string | `midi` / `audio` / `audio_loop` / `one_shot` |
| `instrument_family` | string | TRACK_TYPES 원소 (drums, bass, …) |
| `role` | string | `melody` / `counter` / `accomp` / `bass_foundation` / `rhythmic_hook` / `pad_sustain` / `lead` / `arp` / `fill` / `fx` |
| `human_playable` | bool | 사람 연주감 중요 여부 (피아노/기타 등) |
| `main` | bool | 메인 트랙(true) vs 보조(false) |
| `midi_channel` | int? | MIDI 트랙 한정 |
| `plugins` | array | `[{"name": str, "uid": str, "bypass": bool}]` |

## `region` — 캡처 대상 구간

| 필드 | 타입 | 설명 |
|------|------|------|
| `track_id` | int | 선택된 타겟 트랙 |
| `start_bar` | int | 시작 마디 (inclusive) |
| `end_bar` | int | 끝 마디 (exclusive) |
| `role_in_section` | string | `intro_fill` / `verse_groove` / `pre_chorus_lift` / `chorus_support` / `outro_tail` |
| `important_context_tracks` | int[] | 이 구간에서 주요 참고 트랙 id 들 |
| `expected_task` | string | UUU 의 task 어휘와 동일 (`variation` / `continuation` / `bar_infill` / `track_completion` / …) |

## `ai_interaction` — AI 와 어떤 상호작용이 있었는가

| 필드 | 타입 | 설명 |
|------|------|------|
| `request` | object | 서버에 보낸 `GenerateJsonRequest` snapshot |
| `proposal` | object | 서버가 반환한 중간 안 (MIDI base64 / metadata) |
| `accepted` | bool | 사용자가 채택했는가 |
| `user_edits` | object? | 채택 후 사용자가 수정한 MIDI 의 diff (optional) |
| `reject_reason` | string? | 거절 시 자유 텍스트 |

## `audio_refs`

샘플/오디오 트랙이 region 안에 있을 때의 참조. 파일명, 역할 태그만 기록
(오디오 분석은 Phase 4 에서).

```json
[{
  "file": "kick_loop_A.wav",
  "role": "groove_foundation",
  "offset_beats": 0.0
}]
```

## 호환성 규칙

- `schema_version` 필드는 반드시 유지. 증가 시 업그레이드 스크립트 제공.
- 모든 필드는 선택적 (`project.genre` 누락 등 허용). 소비 측은 방어적으로 읽는다.
- 추가 필드는 무시 (forward-compatible).
- 이 문서는 Rule 01 (파일·데이터 계약) 의 일부로 취급.
