"""
Shared data models for the MIDI AI Workstation.
All modules reference these types for consistency.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import copy


TICKS_PER_BEAT = 480

# ── 연주 해석 상수 (Troubleshooter 이슈 #3, #5 대응) ──

ARTICULATION_TYPES = [
    "sustain",    # 기본 서스테인
    "staccato",   # 짧게 끊어치기
    "legato",     # 이어치기
    "accent",     # 악센트
    "mute",       # 뮤트
    "slap",       # 슬랩 (베이스)
    "palm_mute",  # 팜뮤트 (기타)
    "harmonic",   # 하모닉스
    "tremolo",    # 트레몰로
    "trill",      # 트릴
]

NOTE_ROLES = [
    "melody",     # 멜로디 음
    "root",       # 코드 루트
    "third",      # 3도
    "fifth",      # 5도
    "seventh",    # 7도
    "tension",    # 텐션 (9, 11, 13도)
    "passing",    # 경과음
    "neighbor",   # 보조음
    "pedal",      # 페달 톤 (지속음)
    "bass",       # 베이스 라인
]

TRANSITION_TYPES = [
    "none",       # 일반 시작
    "slide_up",   # 슬라이드 업
    "slide_down", # 슬라이드 다운
    "hammer_on",  # 해머온
    "pull_off",   # 풀오프
    "bend_up",    # 벤드 업
    "bend_down",  # 벤드 다운
    "ghost",      # 고스트 노트
    "grace",      # 장식음
]

SCALE_INTERVALS = {
    "major":        [0, 2, 4, 5, 7, 9, 11],
    "minor":        [0, 2, 3, 5, 7, 8, 10],
    "dorian":       [0, 2, 3, 5, 7, 9, 10],
    "mixolydian":   [0, 2, 4, 5, 7, 9, 10],
    "pentatonic":   [0, 2, 4, 7, 9],
    "minor_penta":  [0, 3, 5, 7, 10],
    "blues":        [0, 3, 5, 6, 7, 10],
    "chromatic":    list(range(12)),
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

TRACK_COLORS = [
    "#B0B0B0", "#8C8C8C", "#C8C8C8", "#9A9A9A",
    "#707070", "#D4D4D4", "#A0A0A0", "#787878",
    "#606060", "#E0E0E0", "#888888", "#C0C0C0",
    "#585858", "#CACACA", "#969696", "#B8B8B8",
]


def note_name_to_midi(name: str) -> int:
    """Convert note name like 'C4' or 'A#3' to MIDI number."""
    for i, n in enumerate(NOTE_NAMES):
        if name.upper().startswith(n) and len(n) == len(name) - 1:
            octave = int(name[len(n):])
            return (octave + 1) * 12 + i
    return 60


def midi_to_note_name(midi_num: int) -> str:
    """Convert MIDI number to note name like 'C4'."""
    octave = (midi_num // 12) - 1
    note = NOTE_NAMES[midi_num % 12]
    return f"{note}{octave}"


def key_name_to_root(key: str) -> int:
    """Convert key name to pitch class (0-11). e.g., 'A#' -> 10."""
    key = key.strip().upper()
    if key in NOTE_NAMES:
        return NOTE_NAMES.index(key)
    aliases = {"Bb": "A#", "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#"}
    key_title = key.title()
    if key_title in aliases:
        return NOTE_NAMES.index(aliases[key_title])
    return 0


def get_scale_pitches(root: int, scale_name: str) -> list[int]:
    """Get all valid MIDI pitches for a scale across all octaves."""
    intervals = SCALE_INTERVALS.get(scale_name, SCALE_INTERVALS["minor"])
    pitches = []
    for octave_base in range(0, 128, 12):
        for iv in intervals:
            p = octave_base + root + iv
            if 0 <= p < 128:
                pitches.append(p)
    return sorted(set(pitches))


@dataclass
class Note:
    """A single MIDI note event with performance interpretation."""
    pitch: int = 60
    velocity: int = 80
    start_tick: int = 0
    duration_ticks: int = TICKS_PER_BEAT
    channel: int = 0
    # 연주 해석 필드 (Troubleshooter 이슈 #3, #5)
    articulation: str = "sustain"   # ARTICULATION_TYPES 참조
    role: str = "melody"            # NOTE_ROLES 참조
    transition: str = "none"        # TRANSITION_TYPES 참조

    @property
    def end_tick(self) -> int:
        return self.start_tick + self.duration_ticks

    @property
    def name(self) -> str:
        return midi_to_note_name(self.pitch)

    def copy(self) -> Note:
        return copy.copy(self)


@dataclass
class CCEvent:
    """A MIDI Control Change event."""
    tick: int = 0
    control: int = 0      # CC number (0-127, e.g. 64=sustain pedal)
    value: int = 0         # CC value (0-127)
    channel: int = 0

    def copy(self) -> CCEvent:
        return copy.copy(self)


@dataclass
class Track:
    """A MIDI track containing notes and metadata."""
    name: str = "Track 1"
    channel: int = 0
    notes: list[Note] = field(default_factory=list)
    cc_events: list[CCEvent] = field(default_factory=list)
    muted: bool = False
    solo: bool = False
    volume: int = 100
    pan: int = 64
    color: str = "#B0B0B0"
    instrument: int = 0  # GM program number

    def copy(self) -> Track:
        t = copy.copy(self)
        t.notes = [n.copy() for n in self.notes]
        t.cc_events = [cc.copy() for cc in self.cc_events]
        return t

    def get_notes_in_range(self, start_tick: int, end_tick: int) -> list[Note]:
        return [n for n in self.notes if n.end_tick > start_tick and n.start_tick < end_tick]

    def add_note(self, note: Note) -> None:
        self.notes.append(note)
        self.notes.sort(key=lambda n: n.start_tick)

    def remove_note(self, note: Note) -> None:
        if note in self.notes:
            self.notes.remove(note)

    @property
    def duration_ticks(self) -> int:
        if not self.notes:
            return 0
        return max(n.end_tick for n in self.notes)


# ── 스트링 모델 (Troubleshooter 이슈 #2 대응) ──
# 노트 구조(보이싱/배치)와 표현(CC) 레이어를 분리

STRING_PARTS = ["violin1", "violin2", "viola", "cello", "contrabass"]

# GM 프로그램 번호
STRING_GM_PROGRAMS = {
    "violin1": 40,     # Violin
    "violin2": 40,     # Violin
    "viola": 41,       # Viola
    "cello": 42,       # Cello
    "contrabass": 43,  # Contrabass
}

# 각 파트의 실용 음역 (MIDI 번호)
STRING_RANGES = {
    "violin1":    (55, 100),  # G3 ~ E7
    "violin2":    (55, 93),   # G3 ~ A6
    "viola":      (48, 84),   # C3 ~ C6
    "cello":      (36, 72),   # C2 ~ C5
    "contrabass": (28, 60),   # E1 ~ C4
}

STRING_ARTICULATIONS = [
    "sustain",      # 보통 롱 노트
    "legato",       # 이어치기
    "detache",      # 활 분리
    "staccato",     # 짧게 끊기
    "spiccato",     # 튀기기
    "pizzicato",    # 뜯기
    "tremolo",      # 트레몰로
    "trill",        # 트릴
    "con_sordino",  # 뮤트
    "harmonics",    # 하모닉스
    "col_legno",    # 활 나무쪽으로
]

# CC 컨트롤러 번호 매핑 (표현 레이어)
STRING_CC_MAP = {
    "expression": 11,     # CC11 — 다이나믹 표현
    "modulation": 1,      # CC1  — 비브라토
    "dynamics": 11,       # CC11 (= expression)
    "vibrato_rate": 76,   # CC76
    "vibrato_depth": 77,  # CC77
    "sustain_pedal": 64,  # CC64
}


@dataclass
class StringPartVoicing:
    """스트링 한 파트의 보이싱 할당 — 특정 코드에서 어떤 음을 담당하는지."""
    part: str = "violin1"         # STRING_PARTS 참조
    role: str = "melody"          # melody / root / third / fifth / seventh / tension / doubling
    octave_preference: int = 4    # 선호 옥타브


@dataclass
class StringArrangement:
    """스트링 편곡 설정 — 섹션별로 다르게 적용 가능."""
    voicing_map: list[StringPartVoicing] = field(default_factory=list)
    texture: str = "homophonic"   # homophonic / polyphonic / unison / antiphonal
    density: float = 0.5          # 0.0 ~ 1.0
    articulation: str = "sustain" # 기본 아티큘레이션
    use_divisi: bool = False      # 디비지 사용 여부
    section_name: str = ""        # 연결된 섹션

    @staticmethod
    def default_arrangement() -> StringArrangement:
        """기본 4성부 배치 반환."""
        return StringArrangement(
            voicing_map=[
                StringPartVoicing("violin1", "melody", 5),
                StringPartVoicing("violin2", "third", 4),
                StringPartVoicing("viola", "fifth", 4),
                StringPartVoicing("cello", "root", 3),
                StringPartVoicing("contrabass", "root", 2),
            ],
            texture="homophonic",
        )


# ── 기타 모델 (Troubleshooter 이슈 #5 대응) ──
# MIDI 노트만으로 표현 불가능한 기타 고유 정보를 메타로 보존

GUITAR_TYPES = ["acoustic", "electric_clean", "electric_drive", "nylon", "bass_guitar"]

# 표준 튜닝 (6현→1현, MIDI 번호)
GUITAR_STANDARD_TUNING = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4

GUITAR_ARTICULATIONS = [
    "downstroke",     # 다운 스트로크
    "upstroke",       # 업 스트로크
    "fingerpick",     # 핑거피킹
    "palm_mute",      # 팜뮤트
    "mute_stroke",    # 뮤트 스트로크 (데드 노트)
    "hammer_on",      # 해머온
    "pull_off",       # 풀오프
    "slide_up",       # 슬라이드 업
    "slide_down",     # 슬라이드 다운
    "bend",           # 벤드
    "vibrato",        # 비브라토
    "harmonic",       # 하모닉스 (자연/인공)
    "tap",            # 탭핑
    "tremolo_pick",   # 트레몰로 피킹
    "arpeggio",       # 아르페지오
    "let_ring",       # 울려놓기
    "chord_hit",      # 한번에 치기 (블록 코드)
]

STRUM_DIRECTIONS = ["down", "up", "down_up", "up_down"]


@dataclass
class GuitarChordShape:
    """기타 코드 폼 — 같은 코드명이라도 폼에 따라 다른 소리."""
    chord_name: str = "C"            # 코드 이름 (e.g. "Am7")
    fret_positions: list[int] = field(default_factory=list)  # 6현 프렛 위치 (-1=안침, 0=개방현)
    # e.g. C Major open: [-1, 3, 2, 0, 1, 0]
    barre_fret: int = -1             # 바레 프렛 (-1 = 바레 없음)
    position: int = 0                # 포지션 (0=개방, 5=5프렛 등)
    uses_open_strings: bool = True

    def to_midi_pitches(self, tuning: list[int] = None) -> list[int]:
        """코드 폼 → MIDI 피치 리스트 변환."""
        if tuning is None:
            tuning = GUITAR_STANDARD_TUNING
        pitches = []
        for string_idx, fret in enumerate(self.fret_positions):
            if fret >= 0 and string_idx < len(tuning):
                pitches.append(tuning[string_idx] + fret)
        return pitches


@dataclass
class GuitarStrum:
    """기타 스트럼 이벤트 — 시간차 + 방향 + 강도."""
    direction: str = "down"          # STRUM_DIRECTIONS 참조
    spread_ticks: int = 15           # 줄 간 시간차 (틱), 0이면 블록 코드
    velocity_curve: str = "even"     # even / accent_first / accent_last / crescendo
    muted_strings: list[int] = field(default_factory=list)  # 뮤트할 줄 인덱스

    def get_string_timing(self, num_strings: int = 6) -> list[int]:
        """각 줄의 상대적 시작 시간 반환."""
        if self.spread_ticks == 0:
            return [0] * num_strings
        if self.direction == "down":
            return [i * self.spread_ticks for i in range(num_strings)]
        elif self.direction == "up":
            return [(num_strings - 1 - i) * self.spread_ticks for i in range(num_strings)]
        else:
            return [i * self.spread_ticks for i in range(num_strings)]

    def get_velocity_multipliers(self, num_strings: int = 6) -> list[float]:
        """각 줄의 벨로시티 배수 반환."""
        if self.velocity_curve == "even":
            return [1.0] * num_strings
        elif self.velocity_curve == "accent_first":
            return [1.2] + [0.85] * (num_strings - 1)
        elif self.velocity_curve == "accent_last":
            return [0.85] * (num_strings - 1) + [1.2]
        elif self.velocity_curve == "crescendo":
            return [0.6 + 0.4 * (i / max(num_strings - 1, 1)) for i in range(num_strings)]
        return [1.0] * num_strings


@dataclass
class GuitarEvent:
    """기타 연주 이벤트 — Note + 기타 고유 메타데이터를 결합."""
    chord_shape: Optional[GuitarChordShape] = None
    strum: Optional[GuitarStrum] = None
    articulation: str = "downstroke"    # GUITAR_ARTICULATIONS 참조
    guitar_type: str = "acoustic"       # GUITAR_TYPES 참조
    start_tick: int = 0
    duration_ticks: int = TICKS_PER_BEAT
    velocity: int = 80
    has_transition_noise: bool = False  # 코드 이동 시 마찰음
    let_ring: bool = False             # 울려놓기

    def to_notes(self, tuning: list[int] = None) -> list[Note]:
        """기타 이벤트 → Note 리스트 변환 (MIDI 출력용)."""
        if not self.chord_shape:
            return []
        pitches = self.chord_shape.to_midi_pitches(tuning)
        strum = self.strum or GuitarStrum()
        timings = strum.get_string_timing(len(pitches))
        vel_mults = strum.get_velocity_multipliers(len(pitches))
        muted = set(strum.muted_strings)

        notes = []
        for i, (pitch, timing, vel_mult) in enumerate(zip(pitches, timings, vel_mults)):
            if i in muted:
                # 뮤트 스트링: 매우 짧은 노트 + 낮은 벨로시티
                notes.append(Note(
                    pitch=pitch,
                    velocity=max(10, int(self.velocity * 0.3)),
                    start_tick=self.start_tick + timing,
                    duration_ticks=min(30, self.duration_ticks // 8),
                    articulation="mute",
                    role="melody",
                    transition="none",
                ))
            else:
                notes.append(Note(
                    pitch=pitch,
                    velocity=max(10, min(127, int(self.velocity * vel_mult))),
                    start_tick=self.start_tick + timing,
                    duration_ticks=self.duration_ticks,
                    articulation=self.articulation if self.articulation in ARTICULATION_TYPES else "sustain",
                    role="melody",
                    transition="none",
                ))
        return notes


@dataclass
class TimeSignature:
    numerator: int = 4
    denominator: int = 4


# ── 섹션/편곡 구조 (Troubleshooter 이슈 #4, #6 대응) ──

SECTION_TYPES = [
    "intro", "verse", "pre_chorus", "chorus", "post_chorus",
    "bridge", "breakdown", "buildup", "drop", "interlude",
    "solo", "outro", "ending",
]

ENERGY_LEVELS = ["very_low", "low", "medium", "high", "very_high"]

TRACK_ROLES = [
    "lead",       # 주 멜로디
    "comp",       # 반주/컴핑
    "bass",       # 베이스 라인
    "pad",        # 패드/서스테인
    "arpeggio",   # 아르페지오
    "rhythm",     # 리듬 (드럼 등)
    "fill",       # 필인/장식
    "counter",    # 대선율
    "silent",     # 해당 섹션에서 쉼
]


@dataclass
class Section:
    """곡의 한 섹션 (verse, chorus 등)."""
    name: str = "verse"                 # SECTION_TYPES 참조
    start_tick: int = 0
    end_tick: int = TICKS_PER_BEAT * 16  # 기본 4마디
    energy: str = "medium"              # ENERGY_LEVELS 참조
    chord_progression: list[str] = field(default_factory=list)  # e.g. ["Cm", "Fm", "G7", "Cm"]
    description: str = ""               # 자유 메모

    @property
    def duration_ticks(self) -> int:
        return self.end_tick - self.start_tick


@dataclass
class TrackRole:
    """특정 섹션에서 특정 트랙의 역할."""
    track_name: str = "Piano"
    section_name: str = "verse"
    role: str = "comp"                  # TRACK_ROLES 참조
    octave_range: tuple[int, int] = (3, 5)
    density: float = 0.5               # 0.0 ~ 1.0


@dataclass
class SongContext:
    """전체 곡 편곡 컨텍스트 — 모든 악기가 공유하는 상위 구조.

    Troubleshooter 이슈 #6 핵심:
    모든 악기 생성 시 이 컨텍스트를 참조하여
    섹션/화성/에너지/역할이 동기화된 결과를 만든다.
    """
    sections: list[Section] = field(default_factory=list)
    role_matrix: list[TrackRole] = field(default_factory=list)
    global_key: str = "C"
    global_scale: str = "minor"
    tempo_map: list[tuple[int, float]] = field(default_factory=list)  # [(tick, bpm), ...]

    def get_section_at(self, tick: int) -> Optional[Section]:
        """특정 tick 위치의 섹션 반환."""
        for s in self.sections:
            if s.start_tick <= tick < s.end_tick:
                return s
        return None

    def get_energy_at(self, tick: int) -> str:
        """특정 tick 위치의 에너지 레벨 반환."""
        section = self.get_section_at(tick)
        return section.energy if section else "medium"

    def get_chords_at(self, tick: int) -> list[str]:
        """특정 tick 위치의 코드 진행 반환."""
        section = self.get_section_at(tick)
        return section.chord_progression if section else []

    def get_track_role(self, track_name: str, tick: int) -> Optional[TrackRole]:
        """특정 트랙의 특정 시점 역할 반환."""
        section = self.get_section_at(tick)
        if not section:
            return None
        for tr in self.role_matrix:
            if tr.track_name == track_name and tr.section_name == section.name:
                return tr
        return None

    def get_section_names(self) -> list[str]:
        """섹션 이름 순서 반환."""
        return [s.name for s in self.sections]

    def total_ticks(self) -> int:
        if not self.sections:
            return 0
        return max(s.end_tick for s in self.sections)


@dataclass
class ProjectState:
    """Complete state of a project."""
    name: str = "Untitled"
    file_path: Optional[str] = None
    tracks: list[Track] = field(default_factory=list)
    bpm: float = 120.0
    time_signature: TimeSignature = field(default_factory=TimeSignature)
    key: str = "C"
    scale: str = "minor"
    ticks_per_beat: int = TICKS_PER_BEAT
    loop_start: int = 0
    loop_end: int = TICKS_PER_BEAT * 16
    loop_enabled: bool = False
    modified: bool = False
    song_context: Optional[SongContext] = None  # 편곡 컨텍스트

    @property
    def total_ticks(self) -> int:
        if not self.tracks:
            return self.ticks_per_beat * self.time_signature.numerator * 16
        return max((t.duration_ticks for t in self.tracks), default=self.ticks_per_beat * 64)

    @property
    def total_beats(self) -> float:
        return self.total_ticks / self.ticks_per_beat

    @property
    def total_seconds(self) -> float:
        return (self.total_ticks / self.ticks_per_beat) * (60.0 / self.bpm)

    def ticks_to_seconds(self, ticks: int) -> float:
        return (ticks / self.ticks_per_beat) * (60.0 / self.bpm)

    def seconds_to_ticks(self, seconds: float) -> int:
        return int(seconds * (self.bpm / 60.0) * self.ticks_per_beat)

    def ticks_to_beats(self, ticks: int) -> float:
        return ticks / self.ticks_per_beat

    def beats_to_ticks(self, beats: float) -> int:
        return int(beats * self.ticks_per_beat)


@dataclass
class UndoAction:
    """Represents a reversible action for undo/redo."""
    description: str
    old_state: ProjectState
    new_state: ProjectState


class UndoManager:
    """Manages undo/redo history."""

    def __init__(self, max_history: int = 100):
        self._history: list[UndoAction] = []
        self._position: int = -1
        self._max = max_history

    def push(self, description: str, old_state: ProjectState, new_state: ProjectState):
        self._history = self._history[: self._position + 1]
        action = UndoAction(description, old_state, new_state)
        self._history.append(action)
        if len(self._history) > self._max:
            self._history.pop(0)
        self._position = len(self._history) - 1

    def undo(self) -> Optional[ProjectState]:
        if self._position < 0:
            return None
        state = self._history[self._position].old_state
        self._position -= 1
        return state

    def redo(self) -> Optional[ProjectState]:
        if self._position >= len(self._history) - 1:
            return None
        self._position += 1
        return self._history[self._position].new_state

    @property
    def can_undo(self) -> bool:
        return self._position >= 0

    @property
    def can_redo(self) -> bool:
        return self._position < len(self._history) - 1

    def clear(self):
        self._history.clear()
        self._position = -1
