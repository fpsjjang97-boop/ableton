"""
AudioToMIDI GUI — 드래그&드롭 / 파일 선택으로 Audio → MIDI 변환

동업자가 Python 설치 없이 EXE로 실행 가능.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# tkinter (Python 기본 내장, 추가 설치 불필요)
# ---------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ---------------------------------------------------------------------------
# Import convert pipeline
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from convert import (
    check_deps, MISSING,
    separate_audio,
    convert_stems_to_midi,
    merge_midi_tracks,
    AUDIO_EXTENSIONS,
)


class AudioToMidiApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AudioToMIDI — Audio → MIDI 변환기")
        self.root.geometry("720x600")
        self.root.resizable(True, True)

        # State
        self.input_files: list[Path] = []
        self.output_dir = Path("./audio_to_midi_output")
        self.is_running = False

        self._build_ui()

    def _build_ui(self):
        # ── Top frame: 파일 선택 ──
        top = ttk.LabelFrame(self.root, text="입력", padding=10)
        top.pack(fill="x", padx=10, pady=(10, 5))

        btn_frame = ttk.Frame(top)
        btn_frame.pack(fill="x")

        ttk.Button(btn_frame, text="파일 선택", command=self._select_files).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="폴더 선택", command=self._select_folder).pack(side="left", padx=(0, 5))
        ttk.Button(btn_frame, text="초기화", command=self._clear_files).pack(side="left")

        self.file_label = ttk.Label(top, text="선택된 파일: 없음", foreground="gray")
        self.file_label.pack(fill="x", pady=(5, 0))

        # ── Mid frame: 옵션 ──
        mid = ttk.LabelFrame(self.root, text="옵션", padding=10)
        mid.pack(fill="x", padx=10, pady=5)

        # Output dir
        out_frame = ttk.Frame(mid)
        out_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(out_frame, text="출력 폴더:").pack(side="left")
        self.out_var = tk.StringVar(value=str(self.output_dir))
        ttk.Entry(out_frame, textvariable=self.out_var, width=40).pack(side="left", padx=5, fill="x", expand=True)
        ttk.Button(out_frame, text="찾아보기", command=self._select_output).pack(side="left")

        # Options row
        opt_frame = ttk.Frame(mid)
        opt_frame.pack(fill="x")

        self.keep_vocals_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="보컬도 MIDI로 변환", variable=self.keep_vocals_var).pack(side="left", padx=(0, 15))

        self.no_merge_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="트랙 개별 MIDI 유지", variable=self.no_merge_var).pack(side="left", padx=(0, 15))

        ttk.Label(opt_frame, text="Demucs 모델:").pack(side="left")
        self.model_var = tk.StringVar(value="htdemucs_6s")
        model_combo = ttk.Combobox(opt_frame, textvariable=self.model_var, width=15, state="readonly",
                                   values=["htdemucs_6s", "htdemucs", "htdemucs_ft", "mdx_extra"])
        model_combo.pack(side="left", padx=5)

        # ── Run button ──
        run_frame = ttk.Frame(self.root)
        run_frame.pack(fill="x", padx=10, pady=5)

        self.run_btn = ttk.Button(run_frame, text="변환 시작", command=self._start_convert)
        self.run_btn.pack(side="left")

        self.progress = ttk.Progressbar(run_frame, mode="indeterminate", length=200)
        self.progress.pack(side="left", padx=10, fill="x", expand=True)

        self.status_label = ttk.Label(run_frame, text="대기 중", foreground="gray")
        self.status_label.pack(side="right")

        # ── Log area ──
        log_frame = ttk.LabelFrame(self.root, text="로그", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill="both", expand=True)

    # ── File selection ──
    def _select_files(self):
        exts = " ".join(f"*{e}" for e in AUDIO_EXTENSIONS)
        files = filedialog.askopenfilenames(
            title="오디오 파일 선택",
            filetypes=[("Audio Files", exts), ("All Files", "*.*")],
        )
        if files:
            self.input_files = [Path(f) for f in files]
            self._update_file_label()

    def _select_folder(self):
        folder = filedialog.askdirectory(title="오디오 폴더 선택")
        if folder:
            folder_path = Path(folder)
            self.input_files = sorted([
                f for f in folder_path.rglob("*")
                if f.suffix.lower() in AUDIO_EXTENSIONS
            ])
            self._update_file_label()

    def _select_output(self):
        folder = filedialog.askdirectory(title="출력 폴더 선택")
        if folder:
            self.out_var.set(folder)

    def _clear_files(self):
        self.input_files = []
        self.file_label.config(text="선택된 파일: 없음", foreground="gray")

    def _update_file_label(self):
        n = len(self.input_files)
        if n == 0:
            self.file_label.config(text="선택된 파일: 없음", foreground="gray")
        elif n <= 3:
            names = ", ".join(f.name for f in self.input_files)
            self.file_label.config(text=f"선택: {names}", foreground="black")
        else:
            self.file_label.config(text=f"선택: {n}개 파일", foreground="black")

    # ── Logging ──
    def _log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── Redirect stdout to GUI log ──
    class _StdoutRedirector:
        def __init__(self, log_func):
            self._log = log_func
            self._buffer = ""

        def write(self, text):
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self._log(line)

        def flush(self):
            if self._buffer.strip():
                self._log(self._buffer)
                self._buffer = ""

    # ── Conversion ──
    def _start_convert(self):
        if self.is_running:
            return

        if not self.input_files:
            messagebox.showwarning("경고", "파일을 먼저 선택하세요.")
            return

        if MISSING:
            messagebox.showerror("오류",
                f"필요한 라이브러리가 없습니다:\n{', '.join(MISSING)}\n\n"
                f"pip install {' '.join(MISSING)}")
            return

        self.is_running = True
        self.run_btn.config(state="disabled")
        self.progress.start()
        self.status_label.config(text="변환 중...", foreground="blue")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        # Run in background thread
        thread = threading.Thread(target=self._run_convert, daemon=True)
        thread.start()

    def _run_convert(self):
        output_dir = Path(self.out_var.get())
        output_dir.mkdir(parents=True, exist_ok=True)

        keep_vocals = self.keep_vocals_var.get()
        no_merge = self.no_merge_var.get()
        model = self.model_var.get()

        # Redirect stdout
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirector = self._StdoutRedirector(lambda msg: self.root.after(0, self._log, msg))
        sys.stdout = redirector
        sys.stderr = redirector

        success = 0
        errors = 0
        total = len(self.input_files)

        try:
            for idx, audio_path in enumerate(self.input_files):
                self.root.after(0, self.status_label.config,
                    {"text": f"[{idx+1}/{total}] {audio_path.name}", "foreground": "blue"})

                self._log(f"\n{'='*50}")
                self._log(f"  [{idx+1}/{total}] {audio_path.name}")
                self._log(f"{'='*50}")

                try:
                    song_name = audio_path.stem
                    song_output = output_dir / song_name
                    song_output.mkdir(parents=True, exist_ok=True)

                    # Step 1
                    stem_paths = separate_audio(audio_path, song_output, model_name=model)

                    # Step 2
                    midi_paths = convert_stems_to_midi(stem_paths, song_output, keep_vocals=keep_vocals)

                    if not midi_paths:
                        self._log(f"[ERROR] MIDI 변환 실패")
                        errors += 1
                        continue

                    # Step 3
                    if not no_merge:
                        final_path = song_output / f"{song_name}_converted.mid"
                        merge_midi_tracks(midi_paths, final_path, song_name=song_name)

                    success += 1

                except Exception as e:
                    self._log(f"[ERROR] {e}")
                    errors += 1

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            # Update UI on main thread
            def _finish():
                self.progress.stop()
                self.is_running = False
                self.run_btn.config(state="normal")

                if errors == 0:
                    self.status_label.config(text=f"완료! {success}/{total} 성공", foreground="green")
                    self._log(f"\n완료! {success}/{total} 파일 변환 성공")
                    self._log(f"출력 폴더: {output_dir}")
                    self._log(f"\n다음 단계: DAW에서 MIDI 파일을 열어 보정 후 midi_data/에 저장하세요.")
                else:
                    self.status_label.config(text=f"완료 ({errors}건 오류)", foreground="orange")
                    self._log(f"\n완료: {success} 성공, {errors} 실패")

            self.root.after(0, _finish)


def main():
    root = tk.Tk()
    app = AudioToMidiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
