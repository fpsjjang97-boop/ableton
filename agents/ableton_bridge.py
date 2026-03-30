"""
Ableton MCP 브릿지 에이전트
===========================
역할: Composer가 생성한 MIDI를 Ableton Live에 전송
- ableton-mcp 소켓 통신으로 Ableton Live 제어
- MIDI 파일 → Ableton 클립 변환
- 세션 정보 조회/제어
- 실시간 재생/정지
"""

import socket
import json
import os
import sys
from pathlib import Path

import mido

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")

ABLETON_HOST = "localhost"
ABLETON_PORT = 9877


class AbletonBridge:
    def __init__(self, host=ABLETON_HOST, port=ABLETON_PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False

    def connect(self):
        """Ableton Remote Script에 연결"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10.0)
            self.sock.connect((self.host, self.port))
            self.connected = True
            print(f"✓ Ableton 연결 성공 ({self.host}:{self.port})")
            return True
        except Exception as e:
            self.connected = False
            print(f"✗ Ableton 연결 실패: {e}")
            print(f"  → Ableton Live가 실행 중이고 AbletonMCP Remote Script가 로드되어 있는지 확인하세요")
            return False

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            self.connected = False
            print("✓ Ableton 연결 해제")

    def _validate_response(self, result):
        """Validate JSON response structure from Ableton MCP."""
        if not isinstance(result, dict):
            print(f"  [warn] 응답이 dict가 아님: {type(result).__name__}")
            return None
        return result

    def send_command(self, cmd_type, params=None):
        """Ableton에 명령 전송"""
        if not self.connected:
            if not self.connect():
                return None

        command = {"type": cmd_type, "params": params or {}}

        try:
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            self.sock.settimeout(15.0)

            chunks = []
            while True:
                try:
                    chunk = self.sock.recv(8192)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    data = b''.join(chunks)
                    try:
                        result = json.loads(data.decode('utf-8'))
                        return self._validate_response(result)
                    except json.JSONDecodeError:
                        continue
                except socket.timeout:
                    break

            if chunks:
                raw = json.loads(b''.join(chunks).decode('utf-8'))
                return self._validate_response(raw)
        except Exception as e:
            print(f"✗ 명령 전송 실패: {e}")
            self.connected = False
            return None

    # ─── Ableton 제어 함수들 ───

    def get_session_info(self):
        """세션 정보 조회"""
        result = self.send_command("get_session_info")
        if result and result.get("status") != "error":
            info = result.get("result", result)
            print(f"\n[Ableton 세션 정보]")
            print(f"  템포: {info.get('tempo', '?')} BPM")
            print(f"  박자: {info.get('time_signature', '?')}")
            print(f"  트랙 수: {info.get('track_count', '?')}")
            if 'tracks' in info:
                for t in info['tracks']:
                    print(f"    - {t.get('name', '?')} (type={t.get('type', '?')})")
            return info
        return None

    def set_tempo(self, bpm):
        """BPM 설정"""
        result = self.send_command("set_tempo", {"tempo": bpm})
        if result:
            print(f"✓ 템포 설정: {bpm} BPM")
        return result

    def create_midi_track(self, index=-1):
        """MIDI 트랙 생성"""
        result = self.send_command("create_midi_track", {"index": index})
        if result:
            print(f"✓ MIDI 트랙 생성")
        return result

    def set_track_name(self, track_index, name):
        """트랙 이름 설정"""
        result = self.send_command("set_track_name", {"track_index": track_index, "name": name})
        if result:
            print(f"✓ 트랙 {track_index} 이름: {name}")
        return result

    def create_clip(self, track_index, clip_index, length=4.0):
        """클립 생성"""
        result = self.send_command("create_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "length": length,
        })
        if result:
            print(f"✓ 클립 생성 (트랙={track_index}, 슬롯={clip_index}, 길이={length}beats)")
        return result

    def add_notes(self, track_index, clip_index, notes):
        """클립에 노트 추가"""
        result = self.send_command("add_notes_to_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
            "notes": notes,
        })
        if result:
            print(f"✓ {len(notes)}개 노트 추가 (트랙={track_index}, 슬롯={clip_index})")
        return result

    def fire_clip(self, track_index, clip_index):
        """클립 재생"""
        result = self.send_command("fire_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        if result:
            print(f"▶ 클립 재생 (트랙={track_index}, 슬롯={clip_index})")
        return result

    def stop_clip(self, track_index, clip_index):
        """클립 정지"""
        result = self.send_command("stop_clip", {
            "track_index": track_index,
            "clip_index": clip_index,
        })
        if result:
            print(f"⏹ 클립 정지")
        return result

    def start_playback(self):
        result = self.send_command("start_playback")
        if result:
            print(f"▶ 재생 시작")
        return result

    def stop_playback(self):
        result = self.send_command("stop_playback")
        if result:
            print(f"⏹ 재생 정지")
        return result

    def load_instrument(self, track_index, uri):
        """악기/이펙트 로드"""
        result = self.send_command("load_browser_item", {
            "track_index": track_index,
            "item_uri": uri,
        })
        if result:
            print(f"✓ 악기 로드 (트랙={track_index})")
        return result

    # ─── MIDI → Ableton 변환 ───

    def midi_to_ableton_notes(self, midi_path, track_filter=None):
        """MIDI 파일을 Ableton 노트 포맷으로 변환"""
        mid = mido.MidiFile(midi_path)
        tpb = mid.ticks_per_beat

        tracks_data = []

        for i, track in enumerate(mid.tracks):
            if track_filter is not None and i != track_filter:
                continue

            notes = []
            abs_tick = 0
            active_notes = {}  # pitch → (start_tick, velocity)

            for msg in track:
                abs_tick += msg.time

                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = (abs_tick, msg.velocity)
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_tick, vel = active_notes.pop(msg.note)
                        start_beat = start_tick / tpb
                        duration_beat = (abs_tick - start_tick) / tpb
                        notes.append({
                            "pitch": msg.note,
                            "start_time": round(start_beat, 4),
                            "duration": round(max(0.0625, duration_beat), 4),
                            "velocity": vel,
                            "mute": False,
                        })

            if notes:
                total_beats = abs_tick / tpb
                tracks_data.append({
                    'track_index': i,
                    'track_name': track.name or f'Track {i}',
                    'notes': notes,
                    'length_beats': total_beats,
                })

        return tracks_data

    def push_midi_to_ableton(self, midi_path):
        """MIDI 파일 전체를 Ableton에 로드"""
        print(f"\n🎵 MIDI → Ableton 전송: {os.path.basename(midi_path)}")

        tracks_data = self.midi_to_ableton_notes(midi_path)

        if not tracks_data:
            print("✗ 전송할 노트 데이터 없음")
            return False

        # 설정에서 BPM 가져오기
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE) as f:
                settings = json.load(f)
            self.set_tempo(settings.get('bpm', 120))

        for td in tracks_data:
            track_idx = td['track_index']
            name = td['track_name']
            notes = td['notes']
            length = max(n['start_time'] + n['duration'] for n in notes) if notes else 4.0
            # 클립 길이를 4의 배수로 올림
            clip_length = max(4.0, ((length // 4) + 1) * 4)

            print(f"\n  트랙: {name} ({len(notes)} 노트, {clip_length} beats)")

            self.create_midi_track()
            # 새로 생성된 트랙의 인덱스는 마지막
            # 실제 Ableton과 통신할 때 인덱스 확인 필요
            self.create_clip(track_idx, 0, clip_length)
            self.set_track_name(track_idx, name)

            # 노트를 배치로 전송 (한번에 50개씩)
            batch_size = 50
            for j in range(0, len(notes), batch_size):
                batch = notes[j:j+batch_size]
                self.add_notes(track_idx, 0, batch)

        print(f"\n✓ 전송 완료: {len(tracks_data)}개 트랙")
        return True


# ─── CLI ───

def print_help():
    print("""
명령어:
  connect       - Ableton 연결
  disconnect    - 연결 해제
  session       - 세션 정보 조회
  tempo <bpm>   - BPM 설정
  push <file>   - MIDI 파일 → Ableton 전송
  play          - 재생
  stop          - 정지
  list          - output/ MIDI 파일 목록
  help          - 도움말
  quit          - 종료
""")


if __name__ == '__main__':
    bridge = AbletonBridge()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'push' and len(sys.argv) > 2:
            bridge.connect()
            bridge.push_midi_to_ableton(str(Path(sys.argv[2]).resolve()))
        elif cmd == 'session':
            bridge.connect()
            bridge.get_session_info()
        else:
            print_help()
    else:
        print("="*50)
        print("🔌 Ableton MCP 브릿지")
        print("="*50)
        print_help()

        while True:
            try:
                cmd = input("ableton> ").strip()
                if not cmd:
                    continue
                elif cmd == 'quit':
                    bridge.disconnect()
                    break
                elif cmd == 'connect':
                    bridge.connect()
                elif cmd == 'disconnect':
                    bridge.disconnect()
                elif cmd == 'session':
                    bridge.get_session_info()
                elif cmd.startswith('tempo '):
                    bpm = float(cmd.split()[1])
                    bridge.set_tempo(bpm)
                elif cmd.startswith('push '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        # output/ 디렉토리에서 찾기
                        candidate = os.path.join(OUTPUT_DIR, filepath)
                        if os.path.exists(candidate):
                            filepath = candidate
                        elif not os.path.exists(filepath):
                            filepath = os.path.join(PROJECT_DIR, filepath)
                    filepath = str(Path(filepath).resolve())
                    bridge.push_midi_to_ableton(filepath)
                elif cmd == 'play':
                    bridge.start_playback()
                elif cmd == 'stop':
                    bridge.stop_playback()
                elif cmd == 'list':
                    import glob
                    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.mid')))
                    if files:
                        for f in files:
                            print(f"  {os.path.basename(f)}")
                    else:
                        print("  (파일 없음)")
                elif cmd == 'help':
                    print_help()
                else:
                    print(f"알 수 없는 명령: {cmd}")
            except (EOFError, KeyboardInterrupt):
                print()
                bridge.disconnect()
                break
