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

# ─── Cubase 15 기반 다크 테마 ───
COLORS = {
    # Backgrounds (blue-gray undertones like Cubase)
    "bg_darkest":      "#0A0A0C",    # Deepest background
    "bg_dark":         "#121215",    # Main panel background
    "bg_mid":          "#1A1A1F",    # Widget backgrounds
    "bg_panel":        "#161619",    # Panel backgrounds
    "bg_widget":       "#111114",    # Input widget bg
    "bg_input":        "#0D0D10",    # Text input bg
    "bg_header":       "#18181C",    # Header/title bar
    "bg_transport":    "#0F0F12",    # Transport bar
    "bg_selected":     "#2A3040",    # Selection highlight (blue tint)
    "bg_hover":        "#222228",    # Hover state
    "bg_inspector":    "#141417",    # Inspector panel bg
    "bg_lower_zone":   "#131316",    # Lower zone bg

    # Accent colors (Cubase uses subtle blue/cyan accents)
    "accent":          "#4A90D9",    # Primary accent (Cubase blue)
    "accent_light":    "#6AAFEF",    # Light accent
    "accent_secondary":"#3A6B99",    # Secondary accent
    "accent_dim":      "#2A4A6A",    # Dim accent for borders
    "accent_green":    "#4CAF50",    # Record/active green
    "accent_yellow":   "#FFC107",    # Warning/solo yellow
    "accent_orange":   "#FF9800",    # Alert orange
    "accent_red":      "#F44336",    # Record red
    "accent_purple":   "#9C27B0",    # MIDI/instrument purple

    # Text
    "text_primary":    "#D8D8DC",    # Primary text
    "text_secondary":  "#808088",    # Secondary text
    "text_dim":        "#484850",    # Dim/disabled text
    "text_accent":     "#FFFFFF",    # Bright white text

    # Grid (Cubase subtle grid lines)
    "grid_line":       "#1A1A1E",
    "grid_bar":        "#2A2A30",
    "grid_beat":       "#1E1E24",

    # Notes (velocity-colored)
    "note_default":    "#4A90D9",    # Default note color
    "note_selected":   "#6AAFEF",    # Selected note
    "note_velocity":   "#3A6B99",    # Velocity indicator

    # Transport
    "playhead":        "#FFFFFF",
    "loop_region":     "#4A90D920",  # Semi-transparent blue

    # Scrollbar
    "scrollbar_bg":    "#0A0A0C",
    "scrollbar_handle":"#2A2A30",

    # Borders (Cubase-style subtle separators)
    "border":          "#222228",
    "border_focus":    "#4A90D9",    # Blue focus border
    "separator":       "#1C1C20",

    # Meters (Cubase-style colored meters)
    "meter_green":     "#4CAF50",
    "meter_yellow":    "#FFC107",
    "meter_red":       "#F44336",
    "meter_bg":        "#0A0A0C",

    # Piano roll keys
    "white_key":       "#1E1E24",
    "black_key":       "#141418",
    "key_pressed":     "#4A90D9",
    "key_label":       "#606068",
    "octave_line":     "#2A2A30",

    # Track colors (Cubase track color palette)
    "track_blue":      "#2979FF",
    "track_cyan":      "#00BCD4",
    "track_green":     "#4CAF50",
    "track_yellow":    "#FFC107",
    "track_orange":    "#FF9800",
    "track_red":       "#F44336",
    "track_pink":      "#E91E63",
    "track_purple":    "#9C27B0",
    "track_indigo":    "#3F51B5",
    "track_teal":      "#009688",
    "track_brown":     "#795548",
    "track_gray":      "#607D8B",

    # Inspector specific
    "inspector_section_bg":     "#18181C",
    "inspector_section_border": "#252530",
    "inspector_knob_arc":       "#4A90D9",
    "inspector_label":          "#808088",
}

# FluidSynth
DEFAULT_SOUNDFONT = "FluidR3_GM.sf2"
SOUNDFONT_SEARCH_PATHS = [
    ".",
    "./resources",
    "C:/soundfonts",
    "E:/Ableton/repo/resources",
    "/usr/share/sounds/sf2",
    "/usr/share/soundfonts",
]

# FluidSynth DLL 경로 (Windows)
FLUIDSYNTH_DLL_PATH = "E:/Ableton/repo/fluidsynth/bin"

# AI
AI_VARIATION_TYPES = [
    "Rhythm",
    "Melody",
    "Harmony",
    "Dynamics",
    "Ornament",
    "Mixed",
]

# Cubase 15 스타일 확장
AI_STYLES = [
    "ambient", "classical", "pop", "cinematic", "edm", "jazz", "lo-fi",
    "experimental", "hiphop", "rnb", "latin", "reggae", "funk", "metal",
    "folk", "orchestral",
]

# Zone visibility defaults
ZONE_DEFAULTS = {
    "left_inspector": True,
    "right_mediabay": False,
    "lower_zone": True,
    "file_browser": True,
}

# Inspector sections
INSPECTOR_SECTIONS = [
    "Track", "Inserts", "Sends", "Strip", "Quick Controls", "Expression Map",
]

# Keyboard shortcut presets (from Cubase 15)
KEYCOMMAND_PRESETS = ["Default", "Pro Tools", "Logic Pro", "Ableton Live", "Sonar"]
