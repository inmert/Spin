# config.py
"""Centralized configuration for the camera application."""

# Screen resolution presets (Width, Height)
RESOLUTION_PRESETS = {
    '4K': (3840, 2160),
    'FHD': (1920, 1080),
    'HD': (1280, 720),
    'VGA': (640, 480),
}

# Default camera settings
DEFAULT_SETTINGS = {
    'resolution': 'HD',
    'frame_rate': 30.0,
}

# GUI update interval in milliseconds
# A lower value gives smoother video but uses more CPU.
GUI_UPDATE_MS = 15