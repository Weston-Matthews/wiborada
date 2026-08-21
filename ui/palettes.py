"""
Color palettes & styles
"""

from database.db_manager import DatabaseManager


db = DatabaseManager();

LIGHT_PALETTE = {
    "bg":        "#FFFFFF",   # white
    "sidebar":   "#16213E",   # gray
    "card":      "#0F3460",   # card background
    "accent":    "#E94560",   # vivid red-pink
    "accent2":   "#533483",   # purple
    "text":      "#E0E0E0",   # light grey text
    "text_dim":  "#8892A4",   # muted text
    "success":   "#06D6A0",   # green
    "warn":      "#FFD166",   # yellow
    "entry_bg":  "#0D1B2A",   # input background
    "border":    "#1E3A5F",   # subtle border
}

DARK_PALETTE = {
    "bg":        "#1A1A2E",   # deep navy
    "sidebar":   "#16213E",   # slightly lighter navy
    "card":      "#0F3460",   # card background
    "accent":    "#E94560",   # vivid red-pink
    "accent2":   "#533483",   # purple
    "text":      "#E0E0E0",   # light grey text
    "text_dim":  "#8892A4",   # muted text
    "success":   "#06D6A0",   # green
    "warn":      "#FFD166",   # yellow
    "entry_bg":  "#0D1B2A",   # input background
    "border":    "#1E3A5F",   # subtle border
}

PALETTE = {}

palette_setting = db.get_setting("palette_setting", "light");
if palette_setting == "light":
    PALETTE = LIGHT_PALETTE;
else:
    PALETTE = DARK_PALETTE;

STATUS_COLORS = {
    "read":    "#06D6A0",
    "reading": "#FFD166",
    "unread":  "#8892A4",
    "wishlist":"#E94560",
}

COVER_PRESETS = [
    "#E94560","#533483","#0F3460","#06D6A0","#FFD166",
    "#2C3E50","#8E44AD","#2980B9","#E67E22","#27AE60",
]

STATUS_OPTIONS = ["unread", "reading", "read", "wishlist"]