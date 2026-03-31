"""
MIDI 재생기 — pygame 기반
사용법: python play_midi.py [midi_file]
인자 없으면 output/ 폴더의 최신 파일 자동 재생
"""
import sys
import os
import time
import glob
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def find_latest_midi():
    """output 폴더에서 가장 최근 MIDI 파일 찾기"""
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    files = glob.glob(os.path.join(output_dir, '*.mid'))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def play(midi_path):
    import pygame
    import pygame.midi

    pygame.init()
    pygame.mixer.init()

    print(f"File: {os.path.basename(midi_path)}")
    print(f"Path: {midi_path}")

    # MIDI 정보 출력
    try:
        import mido
        mid = mido.MidiFile(midi_path)
        track_names = [t.name for t in mid.tracks if t.name]
        print(f"Tracks: {track_names}")
        print(f"Duration: {mid.length:.1f}s ({mid.length/60:.1f}min)")
        print(f"Type: {mid.type}")
    except Exception:
        pass

    print()
    print("=" * 50)
    print("  PLAYING")
    print("  Ctrl+C to stop")
    print("=" * 50)
    print()

    try:
        pygame.mixer.music.load(midi_path)
        pygame.mixer.music.play()

        # 재생 중 대기
        while pygame.mixer.music.get_busy():
            time.sleep(0.5)
            pos = pygame.mixer.music.get_pos() / 1000.0
            mins = int(pos // 60)
            secs = int(pos % 60)
            print(f"\r  {mins:02d}:{secs:02d}", end="", flush=True)

        print("\n\nPlayback finished.")

    except KeyboardInterrupt:
        pygame.mixer.music.stop()
        print("\n\nStopped.")
    finally:
        pygame.mixer.quit()
        pygame.quit()


def main():
    if len(sys.argv) > 1:
        midi_path = str(Path(sys.argv[1]).resolve())
    else:
        midi_path = find_latest_midi()

    if not midi_path or not os.path.isfile(midi_path):
        print("MIDI file not found.")
        print("Usage: python play_midi.py [path_to_midi]")
        return

    play(midi_path)


if __name__ == '__main__':
    main()
