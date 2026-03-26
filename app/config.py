"""
Application configuration constants.
"""

APP_NAME = "MIDI AI Workstation"
APP_VERSION = "1.0.0"
APP_ORG = "MidiAI"
WINDOW_MIN_WIDTH = 1280
WINDOW_MIN_HEIGHT = 720

# Timing
DEFAULT_BPM = 120.0
DEFAULT_TICKS_PER_BEAT = 480
MIN_BPM = 20.0
MAX_BPM = 300.0

# Piano Roll
PIANO_KEY_COUNT = 128
PIANO_KEY_WIDTH = 48
NOTE_HEIGHT = 14
BEAT_WIDTH = 80
MIN_NOTE_DURATION_TICKS = 30
VELOCITY_BAR_HEIGHT = 60

# Zoom
MIN_BEAT_WIDTH = 20
MAX_BEAT_WIDTH = 400
MIN_NOTE_HEIGHT = 4
MAX_NOTE_HEIGHT = 30

# Snap grid
SNAP_VALUES = {
    "Off": 0,
    "1/1": 4,
    "1/2": 2,
    "1/4": 1,
    "1/8": 0.5,
    "1/16": 0.25,
    "1/32": 0.125,
}

# Quantize
QUANTIZE_STRENGTHS = [25, 50, 75, 100]

# Track limits
MAX_TRACKS = 64
DEFAULT_TRACK_HEIGHT = 80
MIN_TRACK_HEIGHT = 40
MAX_TRACK_HEIGHT = 200

# Colors — Metallic dark theme (silver / black / white)
COLORS = {
    "bg_darkest":      "#0E0E0E",
    "bg_dark":         "#161616",
    "bg_mid":          "#1E1E1E",
    "bg_panel":        "#1A1A1A",
    "bg_widget":       "#141414",
    "bg_input":        "#111111",
    "bg_header":       "#1C1C1C",
    "bg_transport":    "#131313",
    "bg_selected":     "#3A3A3A",
    "bg_hover":        "#2A2A2A",

    "accent":          "#C0C0C0",
    "accent_light":    "#E0E0E0",
    "accent_secondary":"#888888",
    "accent_green":    "#7A7A7A",
    "accent_yellow":   "#B0B0B0",
    "accent_orange":   "#999999",

    "text_primary":    "#E8E8E8",
    "text_secondary":  "#909090",
    "text_dim":        "#505050",
    "text_accent":     "#FFFFFF",

    "grid_line":       "#1C1C1C",
    "grid_bar":        "#333333",
    "grid_beat":       "#232323",

    "note_default":    "#A8A8A8",
    "note_selected":   "#FFFFFF",
    "note_velocity":   "#D0D0D0",

    "playhead":        "#FFFFFF",
    "loop_region":     "#FFFFFF18",

    "scrollbar_bg":    "#0E0E0E",
    "scrollbar_handle":"#3A3A3A",

    "border":          "#2A2A2A",
    "border_focus":    "#808080",
    "separator":       "#222222",

    "meter_green":     "#8C8C8C",
    "meter_yellow":    "#B0B0B0",
    "meter_red":       "#D4D4D4",

    "white_key":       "#242424",
    "black_key":       "#181818",
    "key_pressed":     "#C0C0C0",
    "key_label":       "#707070",
    "octave_line":     "#383838",
}

# FluidSynth
DEFAULT_SOUNDFONT = "GeneralUser_GS.sf2"
SOUNDFONT_SEARCH_PATHS = [
    ".",
    "./resources",
    "C:/soundfonts",
    "/usr/share/sounds/sf2",
    "/usr/share/soundfonts",
]

# AI
AI_VARIATION_TYPES = [
    "Rhythm",
    "Melody",
    "Harmony",
    "Dynamics",
    "Ornament",
    "Mixed",
]

AI_STYLES = [
    "ambient",
    "classical",
    "pop",
    "cinematic",
    "edm",
    "jazz",
    "lo-fi",
    "experimental",
]
