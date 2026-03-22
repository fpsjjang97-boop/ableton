"""
관리자 (Manager) 에이전트
========================
역할: 프로젝트 설정 관리, 파이프라인 조율, 에이전트 간 조정
- settings.json 관리 (BPM, 조성, 스타일, 트랙 구성 등)
- 작곡자에게 지시 전달
- 리뷰어 피드백 반영
- 작업 로그 관리
"""

import os
import sys
import json
import glob
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")
LOG_FILE = os.path.join(PROJECT_DIR, "work_log.jsonl")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── 설정 관리 ───

DEFAULT_SETTINGS = {
    'bpm': 60,
    'key': 'A#',
    'scale': 'minor',
    'time_signature': '4/4',
    'style': 'ambient',
    'octave_range': [2, 6],
    'velocity_range': [20, 60],
    'measures': 16,
    'tracks': [
        {'name': 'Melody', 'channel': 0, 'type': 'melody'},
        {'name': 'Chords', 'channel': 1, 'type': 'chords'},
        {'name': 'Bass', 'channel': 2, 'type': 'bass'},
    ]
}

AVAILABLE_SCALES = ['major', 'minor', 'dorian', 'mixolydian', 'pentatonic', 'minor_penta', 'blues', 'chromatic']
AVAILABLE_STYLES = ['ambient', 'pop', 'cinematic', 'edm', 'jazz']
AVAILABLE_KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    log_event('settings_updated', settings)
    print(f"✓ 설정 저장: {SETTINGS_FILE}")


def log_event(event_type, data=None):
    entry = {
        'timestamp': datetime.now().isoformat(),
        'event': event_type,
        'data': data,
    }
    with open(LOG_FILE, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ─── 상태 확인 ───

def show_status():
    """프로젝트 전체 상태"""
    settings = load_settings()

    print(f"\n{'='*50}")
    print(f"📊 프로젝트 상태")
    print(f"{'='*50}")

    # 현재 설정
    print(f"\n[현재 설정]")
    print(f"  Key: {settings['key']} {settings['scale']}")
    print(f"  BPM: {settings['bpm']}")
    print(f"  Style: {settings['style']}")
    print(f"  박자: {settings['time_signature']}")
    print(f"  마디: {settings['measures']}")
    print(f"  음역: 옥타브 {settings['octave_range'][0]}~{settings['octave_range'][1]}")
    print(f"  벨로시티: {settings['velocity_range'][0]}~{settings['velocity_range'][1]}")

    # 트랙 구성
    print(f"\n[트랙 구성]")
    for t in settings.get('tracks', []):
        print(f"  - {t['name']} (ch={t['channel']}, type={t['type']})")

    # 결과물 목록
    midi_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.mid')))
    meta_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.meta.json')))

    print(f"\n[결과물]")
    if midi_files:
        for mf in midi_files:
            basename = os.path.basename(mf)
            # 메타데이터 확인
            meta_path = mf + '.meta.json'
            status = '?'
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
                    status = meta.get('status', '?')
            print(f"  {basename} [{status}]")
    else:
        print(f"  (아직 없음)")

    # 작업 로그 최근 5개
    if os.path.exists(LOG_FILE):
        print(f"\n[최근 작업 로그]")
        with open(LOG_FILE) as f:
            lines = f.readlines()
        for line in lines[-5:]:
            entry = json.loads(line)
            print(f"  {entry['timestamp'][:19]} | {entry['event']}")


def show_settings():
    settings = load_settings()
    print(json.dumps(settings, indent=2, ensure_ascii=False))


def update_setting(key, value):
    """개별 설정 업데이트"""
    settings = load_settings()

    # 타입 변환
    if key == 'bpm':
        value = int(value)
        if not 20 <= value <= 300:
            print(f"✗ BPM은 20~300 사이여야 합니다")
            return
    elif key == 'key':
        value = value.upper()
        if value not in AVAILABLE_KEYS:
            print(f"✗ 사용 가능한 키: {', '.join(AVAILABLE_KEYS)}")
            return
    elif key == 'scale':
        if value not in AVAILABLE_SCALES:
            print(f"✗ 사용 가능한 스케일: {', '.join(AVAILABLE_SCALES)}")
            return
    elif key == 'style':
        if value not in AVAILABLE_STYLES:
            print(f"✗ 사용 가능한 스타일: {', '.join(AVAILABLE_STYLES)}")
            return
    elif key == 'measures':
        value = int(value)
    elif key in ('octave_range', 'velocity_range'):
        value = list(map(int, value.split(',')))

    settings[key] = value
    save_settings(settings)
    print(f"✓ {key} = {value}")


def init_settings():
    """11.mid 분석 기반으로 초기 설정 생성"""
    settings = DEFAULT_SETTINGS.copy()
    # 11.mid 기반 값 (이미 분석한 결과)
    settings['bpm'] = 60
    settings['key'] = 'A#'
    settings['scale'] = 'minor'
    settings['style'] = 'ambient'
    settings['octave_range'] = [2, 6]
    settings['velocity_range'] = [1, 68]
    settings['measures'] = 16

    save_settings(settings)
    log_event('project_initialized', {'based_on': '11.mid'})
    print("✓ 11.mid 분석 기반 초기 설정 완료")
    return settings


def add_track(name, channel, track_type):
    """트랙 추가"""
    settings = load_settings()
    settings['tracks'].append({
        'name': name,
        'channel': int(channel),
        'type': track_type,
    })
    save_settings(settings)
    print(f"✓ 트랙 추가: {name} (ch={channel}, type={track_type})")


def remove_track(name):
    """트랙 제거"""
    settings = load_settings()
    settings['tracks'] = [t for t in settings['tracks'] if t['name'] != name]
    save_settings(settings)
    print(f"✓ 트랙 제거: {name}")


# ─── CLI ───

def print_help():
    print("""
명령어:
  status           - 프로젝트 상태 확인
  settings         - 현재 설정 출력
  init             - 11.mid 기반 초기 설정 생성
  set <key> <val>  - 설정 변경 (예: set bpm 120)
  add-track <name> <ch> <type> - 트랙 추가
  rm-track <name>  - 트랙 제거
  log              - 전체 작업 로그
  help             - 도움말
  quit             - 종료

설정 가능 항목:
  bpm, key, scale, style, time_signature, measures,
  octave_range (예: 2,6), velocity_range (예: 20,60)

스타일: ambient, pop, cinematic, edm, jazz
스케일: major, minor, dorian, mixolydian, pentatonic, minor_penta, blues
""")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'init':
            init_settings()
        elif cmd == 'status':
            show_status()
        elif cmd == 'settings':
            show_settings()
        elif cmd == 'set' and len(sys.argv) >= 4:
            update_setting(sys.argv[2], sys.argv[3])
        else:
            print_help()
    else:
        print("="*50)
        print("📊 관리자 에이전트 (Manager)")
        print("="*50)
        print_help()

        while True:
            try:
                cmd = input("manager> ").strip()
                if not cmd:
                    continue
                elif cmd == 'quit':
                    break
                elif cmd == 'status':
                    show_status()
                elif cmd == 'settings':
                    show_settings()
                elif cmd == 'init':
                    init_settings()
                elif cmd.startswith('set '):
                    parts = cmd.split(maxsplit=2)
                    if len(parts) >= 3:
                        update_setting(parts[1], parts[2])
                    else:
                        print("사용법: set <key> <value>")
                elif cmd.startswith('add-track '):
                    parts = cmd.split()
                    if len(parts) >= 4:
                        add_track(parts[1], parts[2], parts[3])
                    else:
                        print("사용법: add-track <name> <channel> <type>")
                elif cmd.startswith('rm-track '):
                    parts = cmd.split(maxsplit=1)
                    remove_track(parts[1])
                elif cmd == 'log':
                    if os.path.exists(LOG_FILE):
                        with open(LOG_FILE) as f:
                            for line in f:
                                entry = json.loads(line)
                                print(f"{entry['timestamp'][:19]} | {entry['event']}")
                    else:
                        print("로그 없음")
                elif cmd == 'help':
                    print_help()
                else:
                    print(f"알 수 없는 명령: {cmd} (help로 도움말)")
            except (EOFError, KeyboardInterrupt):
                print()
                break
