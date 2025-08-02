# recording_system.py
"""
Video recording and playback system for PyQt6 camera application.
"""
import cv2
import threading
import time
import numpy as np
from pathlib import Path
from typing import Dict, Optional, Tuple
from queue import Queue, Empty
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QGroupBox, QComboBox, QSpinBox,
                           QCheckBox, QProgressBar, QListWidget, QListWidgetItem)

class VideoRecorder(QObject):
    """Handles video recording for multiple cameras with PyQt6 signals."""
    
    # Signals
    recording_started = pyqtSignal(int, str)  # camera_index, filename
    recording_stopped = pyqtSignal(int)       # camera_index
    recording_error = pyqtSignal(int, str)    # camera_index, error_message
    
    def __init__(self, save_directory: str = "./recordings"):
        super().__init__()
        self.save_dir = Path(save_directory)
        self.save_dir.mkdir(exist_ok=True)
        
        self.writers: Dict[int, cv2.VideoWriter] = {}
        self.recording_threads: Dict[int, threading.Thread] = {}
        self.frame_queues: Dict[int, Queue] = {}
        self.recording_active: Dict[int, bool] = {}
        self.recording_start_times: Dict[int, float] = {}
        
        # Default settings
        self.codec = 'XVID'
        self.fps = 30.0
        self.quality = 80
        self.max_duration_sec = None
        self.auto_timestamp = True
    
    def configure(self, codec: str = 'XVID', fps: float = 30.0, 
                 quality: int = 80, max_duration_sec: Optional[float] = None):
        """Configure recording parameters."""
        self.codec = codec
        self.fps = fps
        self.quality = quality
        self.max_duration_sec = max_duration_sec
    
    def start_recording(self, camera_index: int, frame_size: Tuple[int, int], 
                       filename: Optional[str] = None) -> bool:
        """Start recording for a specific camera."""
        if camera_index in self.recording_active and self.recording_active[camera_index]:
            return False  # Already recording
        
        # Generate filename if not provided
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S") if self.auto_timestamp else ""
            filename = f"cam_{camera_index}_{timestamp}.avi"
        
        filepath = self.save_dir / filename
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*self.codec)
        writer = cv2.VideoWriter(
            str(filepath), fourcc, self.fps, frame_size
        )
        
        if not writer.isOpened():
            self.recording_error.emit(camera_index, f"Failed to open video writer for {filename}")
            return False
        
        self.writers[camera_index] = writer
        self.frame_queues[camera_index] = Queue(maxsize=100)
        self.recording_active[camera_index] = True
        self.recording_start_times[camera_index] = time.time()
        
        # Start recording thread
        thread = threading.Thread(
            target=self._recording_worker,
            args=(camera_index,),
            daemon=True
        )
        self.recording_threads[camera_index] = thread
        thread.start()
        
        self.recording_started.emit(camera_index, filename)
        return True
    
    def stop_recording(self, camera_index: int):
        """Stop recording for a specific camera."""
        if camera_index not in self.recording_active:
            return
        
        self.recording_active[camera_index] = False
        
        # Wait for thread to finish
        if camera_index in self.recording_threads:
            self.recording_threads[camera_index].join(timeout=5.0)
            del self.recording_threads[camera_index]
        
        # Clean up
        if camera_index in self.writers:
            self.writers[camera_index].release()
            del self.writers[camera_index]
        
        if camera_index in self.frame_queues:
            del self.frame_queues[camera_index]
        
        if camera_index in self.recording_start_times:
            del self.recording_start_times[camera_index]
        
        self.recording_stopped.emit(camera_index)
    
    def add_frame(self, camera_index: int, frame: np.ndarray):
        """Add a frame to the recording queue."""
        if (camera_index in self.recording_active and 
            self.recording_active[camera_index] and
            camera_index in self.frame_queues):
            
            try:
                # Non-blocking put - drop frame if queue is full
                self.frame_queues[camera_index].put_nowait(frame.copy())
            except:
                pass  # Queue full, drop frame
    
    def is_recording(self, camera_index: int) -> bool:
        """Check if a camera is currently recording."""
        return self.recording_active.get(camera_index, False)
    
    def get_recording_duration(self, camera_index: int) -> float:
        """Get recording duration in seconds."""
        if camera_index in self.recording_start_times:
            return time.time() - self.recording_start_times[camera_index]
        return 0.0
    
    def stop_all_recordings(self):
        """Stop all active recordings."""
        for camera_index in list(self.recording_active.keys()):
            self.stop_recording(camera_index)
    
    def _recording_worker(self, camera_index: int):
        """Worker thread for writing frames to video file."""
        start_time = time.time()
        frame_queue = self.frame_queues[camera_index]
        writer = self.writers[camera_index]
        
        while self.recording_active.get(camera_index, False):
            try:
                # Check duration limit
                if (self.max_duration_sec and 
                    time.time() - start_time > self.max_duration_sec):
                    break
                
                # Get frame with timeout
                frame = frame_queue.get(timeout=1.0)
                
                # Convert to BGR if needed
                if len(frame.shape) == 3 and frame.shape[2] == 3:
                    # Assume RGB, convert to BGR
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                elif len(frame.shape) == 2:
                    # Grayscale to BGR
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                
                writer.write(frame)
                
            except Empty:
                continue  # Timeout, check if still active
            except Exception as e:
                self.recording_error.emit(camera_index, f"Recording error: {str(e)}")
                break

class RecordingControlWidget(QWidget):
    """PyQt6 widget for recording controls."""
    
    def __init__(self, recorder: VideoRecorder, camera_manager):
        super().__init__()
        self.recorder = recorder
        self.camera_manager = camera_manager
        self.camera_widgets = {}
        
        # Connect signals
        self.recorder.recording_started.connect(self.on_recording_started)
        self.recorder.recording_stopped.connect(self.on_recording_stopped)
        self.recorder.recording_error.connect(self.on_recording_error)
        
        # Timer for updating recording durations
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_recording_times)
        self.update_timer.start(1000)  # Update every second
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Recording settings group
        settings_group = QGroupBox("Recording Settings")
        settings_layout = QVBoxLayout()
        
        # Codec selection
        codec_layout = QHBoxLayout()
        codec_layout.addWidget(QLabel("Codec:"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(['XVID', 'MJPG', 'H264', 'MP4V'])
        self.codec_combo.currentTextChanged.connect(self.on_codec_changed)
        codec_layout.addWidget(self.codec_combo)
        codec_layout.addStretch()
        settings_layout.addLayout(codec_layout)
        
        # FPS setting
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("FPS:"))
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(30)
        self.fps_spinbox.valueChanged.connect(self.on_fps_changed)
        fps_layout.addWidget(self.fps_spinbox)
        fps_layout.addStretch()
        settings_layout.addLayout(fps_layout)
        
        # Auto timestamp
        self.auto_timestamp_cb = QCheckBox("Auto Timestamp")
        self.auto_timestamp_cb.setChecked(True)
        self.auto_timestamp_cb.toggled.connect(self.on_auto_timestamp_changed)
        settings_layout.addWidget(self.auto_timestamp_cb)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Global controls
        global_group = QGroupBox("Global Controls")
        global_layout = QHBoxLayout()
        
        self.start_all_btn = QPushButton("Start All Recording")
        self.start_all_btn.clicked.connect(self.start_all_recording)
        global_layout.addWidget(self.start_all_btn)
        
        self.stop_all_btn = QPushButton("Stop All Recording")
        self.stop_all_btn.clicked.connect(self.stop_all_recording)
        global_layout.addWidget(self.stop_all_btn)
        
        global_group.setLayout(global_layout)
        layout.addWidget(global_group)
        
        # Individual camera controls
        self.cameras_group = QGroupBox("Camera Controls")
        self.cameras_layout = QVBoxLayout()
        self.cameras_group.setLayout(self.cameras_layout)
        layout.addWidget(self.cameras_group)
        
        # Recording list
        list_group = QGroupBox("Active Recordings")
        list_layout = QVBoxLayout()
        
        self.recording_list = QListWidget()
        list_layout.addWidget(self.recording_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        self.setLayout(layout)
    
    def update_camera_controls(self):
        """Update recording controls for available cameras."""
        # Clear existing controls
        for widget in self.camera_widgets.values():
            widget.setParent(None)
        self.camera_widgets.clear()
        
        # Create controls for each camera
        for cam_index, camera in self.camera_manager.cameras.items():
            widget = self.create_camera_control_widget(cam_index, camera)
            self.cameras_layout.addWidget(widget)
            self.camera_widgets[cam_index] = widget
    
    def create_camera_control_widget(self, cam_index: int, camera):
        """Create control widget for a single camera."""
        widget = QWidget()
        layout = QHBoxLayout()
        
        # Camera label
        label = QLabel(f"Camera {cam_index} ({camera.serial}):")
        label.setMinimumWidth(200)
        layout.addWidget(label)
        
        # Status label
        status_label = QLabel("Stopped")
        status_label.setMinimumWidth(80)
        layout.addWidget(status_label)
        
        # Duration label
        duration_label = QLabel("00:00")
        duration_label.setMinimumWidth(60)
        layout.addWidget(duration_label)
        
        # Record button
        record_btn = QPushButton("Start Recording")
        record_btn.clicked.connect(lambda: self.toggle_recording(cam_index))
        layout.addWidget(record_btn)
        
        layout.addStretch()
        widget.setLayout(layout)
        
        # Store references for easy access
        widget.status_label = status_label
        widget.duration_label = duration_label
        widget.record_btn = record_btn
        widget.cam_index = cam_index
        
        return widget
    
    def toggle_recording(self, camera_index: int):
        """Toggle recording for a specific camera."""
        if self.recorder.is_recording(camera_index):
            self.recorder.stop_recording(camera_index)
        else:
            self.start_camera_recording(camera_index)
    
    def start_camera_recording(self, camera_index: int):
        """Start recording for a specific camera."""
        camera = self.camera_manager.cameras.get(camera_index)
        if not camera or not camera.is_acquiring:
            return
        
        # Get frame size
        test_frame = camera.get_image()
        if test_frame is not None:
            h, w = test_frame.shape[:2]
            self.recorder.start_recording(camera_index, (w, h))
    
    def start_all_recording(self):
        """Start recording for all active cameras."""
        for cam_index, camera in self.camera_manager.cameras.items():
            if camera.is_acquiring and not self.recorder.is_recording(cam_index):
                self.start_camera_recording(cam_index)
    
    def stop_all_recording(self):
        """Stop all recordings."""
        self.recorder.stop_all_recordings()
    
    def update_recording_times(self):
        """Update recording duration displays."""
        for cam_index, widget in self.camera_widgets.items():
            if self.recorder.is_recording(cam_index):
                duration = self.recorder.get_recording_duration(cam_index)
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                widget.duration_label.setText(f"{minutes:02d}:{seconds:02d}")
            else:
                widget.duration_label.setText("00:00")
    
    def on_recording_started(self, camera_index: int, filename: str):
        """Handle recording started signal."""
        if camera_index in self.camera_widgets:
            widget = self.camera_widgets[camera_index]
            widget.status_label.setText("Recording")
            widget.record_btn.setText("Stop Recording")
            widget.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Add to recording list
        item = QListWidgetItem(f"Camera {camera_index}: {filename}")
        item.setData(1, camera_index)  # Store camera index
        self.recording_list.addItem(item)
    
    def on_recording_stopped(self, camera_index: int):
        """Handle recording stopped signal."""
        if camera_index in self.camera_widgets:
            widget = self.camera_widgets[camera_index]
            widget.status_label.setText("Stopped")
            widget.record_btn.setText("Start Recording")
            widget.status_label.setStyleSheet("")
            widget.duration_label.setText("00:00")
        
        # Remove from recording list
        for i in range(self.recording_list.count()):
            item = self.recording_list.item(i)
            if item.data(1) == camera_index:
                self.recording_list.takeItem(i)
                break
    
    def on_recording_error(self, camera_index: int, error_message: str):
        """Handle recording error signal."""
        print(f"Recording error for camera {camera_index}: {error_message}")
        # Could show a message box here
    
    def on_codec_changed(self, codec: str):
        """Handle codec change."""
        self.recorder.codec = codec
    
    def on_fps_changed(self, fps: int):
        """Handle FPS change."""
        self.recorder.fps = float(fps)
    
    def on_auto_timestamp_changed(self, checked: bool):
        """Handle auto timestamp change."""
        self.recorder.auto_timestamp = checked