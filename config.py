# config.py
"""Enhanced configuration management for the PyQt6 camera application."""

import json
import os
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, asdict

# Screen resolution presets (Width, Height)
RESOLUTION_PRESETS = {
    '4K': (3840, 2160),
    'FHD': (1920, 1080),
    'HD': (1280, 720),
    'VGA': (640, 480),
}

@dataclass
class CameraSettings:
    resolution: str = 'HD'
    frame_rate: float = 30.0
    exposure_time: float = 10000.0  # microseconds
    gain: float = 0.0
    auto_exposure: bool = True
    
@dataclass
class GUISettings:
    window_width: int = 1400
    window_height: int = 900
    update_interval_ms: int = 15
    zoom_step: float = 0.2
    max_zoom: float = 5.0
    theme: str = "default"  # default, dark

@dataclass
class RecordingSettings:
    codec: str = 'XVID'
    fps: float = 30.0
    quality: int = 80
    auto_timestamp: bool = True
    max_duration_sec: float = 300.0  # 5 minutes default

@dataclass
class AppConfig:
    camera: CameraSettings
    gui: GUISettings
    recording: RecordingSettings
    save_directory: str = "./snapshots"
    recording_directory: str = "./recordings"
    log_level: str = "INFO"

class ConfigManager:
    """Manages application configuration with persistence."""
    
    def __init__(self, config_file: str = "camera_config.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self) -> AppConfig:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                return AppConfig(
                    camera=CameraSettings(**data.get('camera', {})),
                    gui=GUISettings(**data.get('gui', {})),
                    recording=RecordingSettings(**data.get('recording', {})),
                    save_directory=data.get('save_directory', './snapshots'),
                    recording_directory=data.get('recording_directory', './recordings'),
                    log_level=data.get('log_level', 'INFO')
                )
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading config: {e}. Using defaults.")
        
        return AppConfig(CameraSettings(), GUISettings(), RecordingSettings())
    
    def save_config(self):
        """Save current configuration to file."""
        try:
            # Create directories
            Path(self.config.save_directory).mkdir(exist_ok=True)
            Path(self.config.recording_directory).mkdir(exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                json.dump(asdict(self.config), f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get_camera_settings(self) -> CameraSettings:
        return self.config.camera
    
    def get_gui_settings(self) -> GUISettings:
        return self.config.gui
    
    def get_recording_settings(self) -> RecordingSettings:
        return self.config.recording
    
    def update_camera_setting(self, key: str, value: Any):
        """Update a camera setting and save."""
        if hasattr(self.config.camera, key):
            setattr(self.config.camera, key, value)
            self.save_config()
    
    def update_gui_setting(self, key: str, value: Any):
        """Update a GUI setting and save."""
        if hasattr(self.config.gui, key):
            setattr(self.config.gui, key, value)
            self.save_config()
    
    def update_recording_setting(self, key: str, value: Any):
        """Update a recording setting and save."""
        if hasattr(self.config.recording, key):
            setattr(self.config.recording, key, value)
            self.save_config()