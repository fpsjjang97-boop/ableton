"""
오케스트레이터 (Orchestrator)
=============================
전체 파이프라인 통합 관리:
  MP3/WAV → [Demucs 음원분리] → [Basic Pitch MIDI 변환]
         → [패턴분석/변형] → [작곡/리믹스] → [리뷰]
         → [Ableton MCP 전송]

워크플로우:
  1. audio2midi: MP3/WAV → 소스분리 → MIDI 변환
  2. composer:   설정 기반 신규 MIDI 작곡
  3. transformer: 패턴분석, 연속생성, 스타일변환, 하모니
  4. reviewer:   품질 검증
  5. ableton:    Ableton Live 전송
"""

import os
import sys
import json
import glob
import subprocess
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(PROJECT_DIR, "agents")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
INPUT_DIR = os.path.join(PROJECT_DIR, "input")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")
VENV_PYTHON = os.path.expanduser("~/audio2midi_env/bin/python3")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")


# ─── 파이프라인 단계들 ───

def step_audio_to_midi(audio_path, keep_stems=False):
    """Step 1: MP3/WAV → MIDI (Demucs + Basic Pitch)"""
    log(f"🎤 STEP 1: 오디오 → MIDI 변환")
    log(f"   입력: {audio_path}")

    basename = os.path.splitext(os.path.basename(audio_path))[0]
    output_midi = os.path.join(OUTPUT_DIR, f"converted_{basename}.mid")

    cmd = [
        VENV_PYTHON,
        os.path.join(AGENTS_DIR, "audio2midi.py"),
        audio_path,
        "-o", output_midi,
        "--model", "htdemucs_ft",
    ]
    if keep_stems:
        cmd.append("--keep-stems")

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        log(f"   ✗ 변환 실패 (exit code: {result.returncode})")
        return None

    if os.path.exists(output_midi):
        log(f"   ✓ 변환 완료: {output_midi}")

        # 메타데이터 저장
        meta = {
            'filename': os.path.basename(output_midi),
            'source_audio': os.path.basename(audio_path),
            'method': 'demucs_basic_pitch',
            'created_at': datetime.now().isoformat(),
            'status': 'pending_review',
        }
        with open(output_midi + '.meta.json', 'w') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        return output_midi
    else:
        log(f"   ✗ 출력 파일 없음")
        return None


def step_analyze(midi_path):
    """Step 2: MIDI 패턴 분석"""
    log(f"🔍 STEP 2: 패턴 분석")

    sys.path.insert(0, AGENTS_DIR)
    from music_transformer import extract_patterns, analyze_patterns

    patterns = extract_patterns(midi_path)
    analyze_patterns(patterns)
    return patterns


def step_compose(settings=None):
    """Step 3: 설정 기반 신규 작곡"""
    log(f"🎵 STEP 3: 신규 작곡")

    sys.path.insert(0, AGENTS_DIR)
    from composer import compose

    filepath, meta = compose(settings)
    return filepath


def step_transform(midi_path, mode='continue', **kwargs):
    """Step 4: 변형 (연속생성/스타일변환/하모니)"""
    log(f"🧠 STEP 4: 변형 ({mode})")

    sys.path.insert(0, AGENTS_DIR)
    from music_transformer import continue_midi, transform_style, harmonize

    if mode == 'continue':
        measures = kwargs.get('measures', 8)
        return continue_midi(midi_path, measures)
    elif mode == 'style':
        style = kwargs.get('style', 'ambient')
        return transform_style(midi_path, style)
    elif mode == 'harmonize':
        h_type = kwargs.get('harmony_type', 'thirds')
        return harmonize(midi_path, h_type)
    else:
        log(f"   ✗ 알 수 없는 모드: {mode}")
        return None


def step_review(midi_path):
    """Step 5: 품질 리뷰"""
    log(f"📋 STEP 5: 품질 리뷰")

    sys.path.insert(0, AGENTS_DIR)
    from reviewer import review_midi

    return review_midi(midi_path)


def step_push_ableton(midi_path):
    """Step 6: Ableton Live 전송"""
    log(f"🔌 STEP 6: Ableton 전송")

    sys.path.insert(0, AGENTS_DIR)
    from ableton_bridge import AbletonBridge

    bridge = AbletonBridge()
    if bridge.connect():
        bridge.push_midi_to_ableton(midi_path)
        bridge.disconnect()
        return True
    return False


# ─── 통합 파이프라인 ───

def pipeline_audio_full(audio_path, push_ableton=False):
    """
    전체 파이프라인: Audio → MIDI → 분석 → 변형 → 리뷰 → (Ableton)
    """
    log(f"{'='*60}")
    log(f"🚀 전체 파이프라인 시작")
    log(f"   입력: {audio_path}")
    log(f"{'='*60}")

    # 1. Audio → MIDI
    midi_path = step_audio_to_midi(audio_path, keep_stems=True)
    if not midi_path:
        log("✗ 파이프라인 중단: 변환 실패")
        return

    # 2. 패턴 분석
    step_analyze(midi_path)

    # 3. 연속 생성
    continued = step_transform(midi_path, mode='continue', measures=8)

    # 4. 리뷰
    if continued:
        review = step_review(continued)
    else:
        review = step_review(midi_path)

    # 5. Ableton 전송 (선택)
    if push_ableton:
        target = continued or midi_path
        step_push_ableton(target)

    log(f"\n{'='*60}")
    log(f"✅ 파이프라인 완료")
    log(f"{'='*60}")


def pipeline_compose_full(push_ableton=False):
    """
    작곡 파이프라인: 설정 → 작곡 → 변형 → 리뷰 → (Ableton)
    """
    log(f"{'='*60}")
    log(f"🚀 작곡 파이프라인 시작")
    log(f"{'='*60}")

    # 1. 작곡
    midi_path = step_compose()

    # 2. 하모니 추가
    harmonized = step_transform(midi_path, mode='harmonize', harmony_type='thirds')

    # 3. 리뷰
    target = harmonized or midi_path
    review = step_review(target)

    # 4. Ableton 전송 (선택)
    if push_ableton:
        step_push_ableton(target)

    log(f"\n{'='*60}")
    log(f"✅ 작곡 파이프라인 완료")
    log(f"{'='*60}")


def pipeline_remix(midi_path, target_style, push_ableton=False):
    """
    리믹스 파이프라인: 기존 MIDI → 스타일변환 → 하모니 → 리뷰 → (Ableton)
    """
    log(f"{'='*60}")
    log(f"🚀 리믹스 파이프라인 시작")
    log(f"   소스: {midi_path}")
    log(f"   스타일: {target_style}")
    log(f"{'='*60}")

    # 1. 패턴 분석
    step_analyze(midi_path)

    # 2. 스타일 변환
    styled = step_transform(midi_path, mode='style', style=target_style)

    # 3. 하모니 추가
    if styled:
        harmonized = step_transform(styled, mode='harmonize', harmony_type='fifths')
    else:
        harmonized = None

    # 4. 리뷰
    target = harmonized or styled or midi_path
    step_review(target)

    # 5. Ableton 전송 (선택)
    if push_ableton:
        step_push_ableton(target)

    log(f"\n{'='*60}")
    log(f"✅ 리믹스 파이프라인 완료")
    log(f"{'='*60}")


# ─── CLI ───

def show_status():
    """전체 시스템 상태"""
    print(f"\n{'='*60}")
    print(f"📊 MIDI → 음악 프로젝트 전체 상태")
    print(f"{'='*60}")

    # 입력 파일
    audio_files = glob.glob(os.path.join(INPUT_DIR, '*.mp3')) + \
                  glob.glob(os.path.join(INPUT_DIR, '*.wav')) + \
                  glob.glob(os.path.join(INPUT_DIR, '*.flac'))
    print(f"\n[입력 오디오] ({len(audio_files)}개)")
    for f in audio_files:
        size = os.path.getsize(f) / 1024 / 1024
        print(f"  {os.path.basename(f)} ({size:.1f}MB)")
    if not audio_files:
        print(f"  (input/ 디렉토리에 MP3/WAV 파일을 넣으세요)")

    # 출력 MIDI
    midi_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.mid')))
    print(f"\n[출력 MIDI] ({len(midi_files)}개)")
    for f in midi_files:
        meta_path = f + '.meta.json'
        status = '?'
        method = '?'
        if os.path.exists(meta_path):
            with open(meta_path) as mf:
                meta = json.load(mf)
                status = meta.get('status', '?')
                method = meta.get('method', '?')
        icon = {'pending_review': '⏳', 'approved': '✅', 'needs_revision': '⚠️'}.get(status, '?')
        print(f"  {icon} {os.path.basename(f)} [{method}] [{status}]")

    # 설정
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            settings = json.load(f)
        print(f"\n[현재 설정]")
        print(f"  Key: {settings.get('key')} {settings.get('scale')}")
        print(f"  BPM: {settings.get('bpm')}")
        print(f"  Style: {settings.get('style')}")

    # 환경
    print(f"\n[환경]")
    venv_ok = os.path.exists(VENV_PYTHON)
    print(f"  audio2midi venv: {'✓' if venv_ok else '✗ (~/audio2midi_env 없음)'}")
    print(f"  Demucs/Basic Pitch: {'사용 가능' if venv_ok else '설치 필요'}")


def print_help():
    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MIDI → 음악 프로젝트 오케스트레이터
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

파이프라인:
  audio <file>         - Audio→MIDI 전체 변환 (Demucs+BasicPitch→분석→변형→리뷰)
  compose              - 설정 기반 작곡 (작곡→하모니→리뷰)
  remix <file> <style> - 리믹스 (분석→스타일변환→하모니→리뷰)

개별 단계:
  convert <file>       - MP3/WAV → MIDI 변환만
  analyze <file>       - MIDI 패턴 분석만
  continue <file> [n]  - 연속 생성만 (n마디)
  style <file> <style> - 스타일 변환만
  harmonize <file>     - 하모니 추가만
  review <file>        - 리뷰만
  push <file>          - Ableton 전송만

관리:
  status               - 전체 상태 확인
  list                 - 출력 파일 목록
  help                 - 도움말
  quit                 - 종료

스타일: ambient, pop, cinematic, edm, jazz
""")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'audio' and len(sys.argv) > 2:
            pipeline_audio_full(sys.argv[2])
        elif cmd == 'compose':
            pipeline_compose_full()
        elif cmd == 'remix' and len(sys.argv) > 3:
            pipeline_remix(sys.argv[2], sys.argv[3])
        elif cmd == 'status':
            show_status()
        else:
            print_help()
    else:
        print("="*50)
        print("🎼 오케스트레이터")
        print("="*50)
        print_help()

        while True:
            try:
                cmd = input("orchestrator> ").strip()
                if not cmd:
                    continue
                elif cmd == 'quit':
                    break
                elif cmd == 'status':
                    show_status()
                elif cmd == 'help':
                    print_help()
                elif cmd.startswith('audio '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        candidate = os.path.join(INPUT_DIR, filepath)
                        if os.path.exists(candidate):
                            filepath = candidate
                    pipeline_audio_full(filepath)
                elif cmd == 'compose':
                    pipeline_compose_full()
                elif cmd.startswith('remix '):
                    parts = cmd.split()
                    if len(parts) >= 3:
                        filepath = parts[1]
                        if not os.path.isabs(filepath):
                            for d in [OUTPUT_DIR, PROJECT_DIR]:
                                c = os.path.join(d, filepath)
                                if os.path.exists(c):
                                    filepath = c
                                    break
                        pipeline_remix(filepath, parts[2])
                    else:
                        print("사용법: remix <file> <style>")
                elif cmd.startswith('convert '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        candidate = os.path.join(INPUT_DIR, filepath)
                        if os.path.exists(candidate):
                            filepath = candidate
                    step_audio_to_midi(filepath, keep_stems=True)
                elif cmd.startswith('analyze '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        for d in [OUTPUT_DIR, PROJECT_DIR]:
                            c = os.path.join(d, filepath)
                            if os.path.exists(c):
                                filepath = c
                                break
                    step_analyze(filepath)
                elif cmd.startswith('continue '):
                    parts = cmd.split()
                    filepath = parts[1]
                    measures = int(parts[2]) if len(parts) > 2 else 8
                    if not os.path.isabs(filepath):
                        for d in [OUTPUT_DIR, PROJECT_DIR]:
                            c = os.path.join(d, filepath)
                            if os.path.exists(c):
                                filepath = c
                                break
                    step_transform(filepath, 'continue', measures=measures)
                elif cmd.startswith('style '):
                    parts = cmd.split()
                    if len(parts) >= 3:
                        filepath = parts[1]
                        if not os.path.isabs(filepath):
                            for d in [OUTPUT_DIR, PROJECT_DIR]:
                                c = os.path.join(d, filepath)
                                if os.path.exists(c):
                                    filepath = c
                                    break
                        step_transform(filepath, 'style', style=parts[2])
                elif cmd.startswith('harmonize '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        for d in [OUTPUT_DIR, PROJECT_DIR]:
                            c = os.path.join(d, filepath)
                            if os.path.exists(c):
                                filepath = c
                                break
                    step_transform(filepath, 'harmonize')
                elif cmd.startswith('review '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        for d in [OUTPUT_DIR, PROJECT_DIR]:
                            c = os.path.join(d, filepath)
                            if os.path.exists(c):
                                filepath = c
                                break
                    step_review(filepath)
                elif cmd.startswith('push '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        for d in [OUTPUT_DIR, PROJECT_DIR]:
                            c = os.path.join(d, filepath)
                            if os.path.exists(c):
                                filepath = c
                                break
                    step_push_ableton(filepath)
                elif cmd == 'list':
                    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.mid')))
                    for f in files:
                        print(f"  {os.path.basename(f)}")
                    if not files:
                        print("  (없음)")
                else:
                    print(f"알 수 없는 명령: {cmd} (help 입력)")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            except Exception as e:
                log(f"✗ 오류: {e}")
