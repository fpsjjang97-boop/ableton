"""
Settings Dialog — Audio/MIDI/UI preferences.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTabWidget, QWidget, QGroupBox, QSpinBox,
    QCheckBox, QListWidget, QListWidgetItem, QLineEdit,
)
from config import COLORS
C = COLORS


def _dialog_style():
    return f"""
        QDialog {{ background: {C['bg_darkest']}; color: {C['text_primary']}; }}
        QGroupBox {{
            background: {C['bg_mid']}; border: 1px solid {C['border']};
            border-radius: 4px; margin-top: 10px; padding-top: 14px;
            font-weight: bold; color: {C['text_secondary']};
        }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
        QComboBox, QSpinBox, QLineEdit {{
            background: {C['bg_input']}; color: {C['text_primary']};
            border: 1px solid {C['border']}; border-radius: 3px; padding: 3px 6px;
        }}
        QComboBox:hover, QSpinBox:hover {{ border-color: {C['text_secondary']}; }}
        QPushButton {{
            background: {C['bg_input']}; color: {C['text_primary']};
            border: 1px solid {C['border']}; border-radius: 4px; padding: 5px 14px;
        }}
        QPushButton:hover {{ border-color: {C['text_secondary']}; }}
        QTabWidget::pane {{ border: 1px solid {C['border']}; background: {C['bg_darkest']}; }}
        QTabBar::tab {{
            background: {C['bg_mid']}; color: {C['text_secondary']};
            padding: 6px 14px; border: 1px solid {C['border']}; border-bottom: none;
        }}
        QTabBar::tab:selected {{ background: {C['bg_darkest']}; color: {C['text_primary']}; }}
        QListWidget {{
            background: {C['bg_input']}; color: {C['text_primary']};
            border: 1px solid {C['border']}; border-radius: 3px;
        }}
        QCheckBox {{ color: {C['text_primary']}; }}
        QLabel {{ color: {C['text_primary']}; }}
    """


class SettingsDialog(QDialog):
    """Application settings dialog."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 450)
        self.setStyleSheet(_dialog_style())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Audio tab
        tabs.addTab(self._build_audio_tab(), "Audio")
        # MIDI tab
        tabs.addTab(self._build_midi_tab(), "MIDI")
        # Appearance tab
        tabs.addTab(self._build_appearance_tab(), "Appearance")
        # File tab
        tabs.addTab(self._build_file_tab(), "File")

        layout.addWidget(tabs)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._apply_and_close)
        btns.addWidget(ok_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply)
        btns.addWidget(apply_btn)
        layout.addLayout(btns)

    def _build_audio_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # Audio Device
        grp = QGroupBox("Audio Device")
        gl = QVBoxLayout(grp)

        row = QHBoxLayout()
        row.addWidget(QLabel("Driver:"))
        self._driver_combo = QComboBox()
        self._driver_combo.addItems(["ASIO", "WASAPI", "DirectSound", "CoreAudio"])
        self._driver_combo.setFixedWidth(150)
        row.addWidget(self._driver_combo)
        row.addStretch()
        gl.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Output Device:"))
        self._output_device = QComboBox()
        self._output_device.addItem("Default")
        try:
            from core.audio_io import RecordingManager
            for dev in RecordingManager.get_output_devices():
                self._output_device.addItem(dev['name'])
        except Exception:
            pass
        self._output_device.setFixedWidth(250)
        row2.addWidget(self._output_device)
        row2.addStretch()
        gl.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Input Device:"))
        self._input_device = QComboBox()
        self._input_device.addItem("Default")
        try:
            from core.audio_io import RecordingManager
            for dev in RecordingManager.get_input_devices():
                self._input_device.addItem(dev['name'])
        except Exception:
            pass
        self._input_device.setFixedWidth(250)
        row3.addWidget(self._input_device)
        row3.addStretch()
        gl.addLayout(row3)

        layout.addWidget(grp)

        # Buffer & Sample Rate
        grp2 = QGroupBox("Performance")
        gl2 = QVBoxLayout(grp2)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Sample Rate:"))
        self._sample_rate = QComboBox()
        self._sample_rate.addItems(["44100", "48000", "88200", "96000"])
        self._sample_rate.setFixedWidth(100)
        row4.addWidget(self._sample_rate)
        row4.addStretch()
        gl2.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(QLabel("Buffer Size:"))
        self._buffer_size = QComboBox()
        self._buffer_size.addItems(["64", "128", "256", "512", "1024", "2048"])
        self._buffer_size.setCurrentText("512")
        self._buffer_size.setFixedWidth(100)
        row5.addWidget(self._buffer_size)
        self._latency_label = QLabel("Latency: 11.6 ms")
        self._latency_label.setStyleSheet(f"color: {C['text_dim']};")
        row5.addWidget(self._latency_label)
        self._buffer_size.currentTextChanged.connect(self._update_latency)
        row5.addStretch()
        gl2.addLayout(row5)

        row6 = QHBoxLayout()
        row6.addWidget(QLabel("Bit Depth:"))
        self._bit_depth = QComboBox()
        self._bit_depth.addItems(["16", "24", "32"])
        self._bit_depth.setFixedWidth(80)
        row6.addWidget(self._bit_depth)
        row6.addStretch()
        gl2.addLayout(row6)

        layout.addWidget(grp2)
        layout.addStretch()
        return page

    def _build_midi_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        # MIDI Input
        grp = QGroupBox("MIDI Input Devices")
        gl = QVBoxLayout(grp)
        self._midi_inputs = QListWidget()
        try:
            from core.midi_io import MIDIInputManager
            for port in MIDIInputManager.get_input_ports():
                item = QListWidgetItem(port)
                item.setCheckState(Qt.CheckState.Unchecked)
                self._midi_inputs.addItem(item)
        except Exception:
            self._midi_inputs.addItem("(No MIDI devices found)")
        gl.addWidget(self._midi_inputs)
        layout.addWidget(grp)

        # MIDI Output
        grp2 = QGroupBox("MIDI Output Devices")
        gl2 = QVBoxLayout(grp2)
        self._midi_outputs = QListWidget()
        try:
            from core.midi_io import MIDIInputManager
            for port in MIDIInputManager.get_output_ports():
                item = QListWidgetItem(port)
                item.setCheckState(Qt.CheckState.Unchecked)
                self._midi_outputs.addItem(item)
        except Exception:
            self._midi_outputs.addItem("(No MIDI devices found)")
        gl2.addWidget(self._midi_outputs)
        layout.addWidget(grp2)

        # MIDI Options
        grp3 = QGroupBox("Options")
        gl3 = QVBoxLayout(grp3)
        self._midi_thru = QCheckBox("MIDI Thru (forward input to output)")
        gl3.addWidget(self._midi_thru)
        self._midi_clock = QCheckBox("Send MIDI Clock")
        gl3.addWidget(self._midi_clock)
        layout.addWidget(grp3)

        layout.addStretch()
        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        grp = QGroupBox("Display")
        gl = QVBoxLayout(grp)

        row = QHBoxLayout()
        row.addWidget(QLabel("UI Scale:"))
        self._ui_scale = QComboBox()
        self._ui_scale.addItems(["100%", "125%", "150%"])
        self._ui_scale.setFixedWidth(80)
        row.addWidget(self._ui_scale)
        row.addStretch()
        gl.addLayout(row)

        self._show_cpu = QCheckBox("Show CPU meter")
        self._show_cpu.setChecked(True)
        gl.addWidget(self._show_cpu)

        self._show_tooltips = QCheckBox("Show tooltips")
        self._show_tooltips.setChecked(True)
        gl.addWidget(self._show_tooltips)

        layout.addWidget(grp)
        layout.addStretch()
        return page

    def _build_file_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        grp = QGroupBox("Auto-save")
        gl = QVBoxLayout(grp)
        self._autosave = QCheckBox("Enable auto-save")
        self._autosave.setChecked(True)
        gl.addWidget(self._autosave)

        row = QHBoxLayout()
        row.addWidget(QLabel("Interval (minutes):"))
        self._autosave_interval = QSpinBox()
        self._autosave_interval.setRange(1, 30)
        self._autosave_interval.setValue(3)
        self._autosave_interval.setFixedWidth(60)
        row.addWidget(self._autosave_interval)
        row.addStretch()
        gl.addLayout(row)
        layout.addWidget(grp)

        grp2 = QGroupBox("Export")
        gl2 = QVBoxLayout(grp2)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Default export format:"))
        self._export_fmt = QComboBox()
        self._export_fmt.addItems(["WAV (16-bit)", "WAV (24-bit)", "WAV (32-bit)", "MP3 (192k)", "MP3 (320k)"])
        self._export_fmt.setFixedWidth(130)
        row2.addWidget(self._export_fmt)
        row2.addStretch()
        gl2.addLayout(row2)
        layout.addWidget(grp2)

        layout.addStretch()
        return page

    def _update_latency(self, text):
        try:
            buf = int(text)
            sr = int(self._sample_rate.currentText())
            ms = buf / sr * 1000
            self._latency_label.setText(f"Latency: {ms:.1f} ms")
        except ValueError:
            pass

    def _apply(self):
        settings = {
            'sample_rate': int(self._sample_rate.currentText()),
            'buffer_size': int(self._buffer_size.currentText()),
            'bit_depth': int(self._bit_depth.currentText()),
            'midi_thru': self._midi_thru.isChecked(),
            'midi_clock': self._midi_clock.isChecked(),
            'autosave': self._autosave.isChecked(),
            'autosave_interval': self._autosave_interval.value(),
        }
        self.settings_changed.emit(settings)

    def _apply_and_close(self):
        self._apply()
        self.accept()
