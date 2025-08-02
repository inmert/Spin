# main_gui.py
"""
Main PyQt6 GUI application for FLIR camera control.
Enhanced with all advanced features.
"""
import sys
import time
import cv2
import numpy as np
from typing import Dict, Optional
from pathlib import Path
from functools import partial

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                           QComboBox, QLineEdit, QGroupBox, QGridLayout,
                           QMessageBox, QStatusBar, QProgressBar, QSlider,
                           QCheckBox, QSplitter, QFrame, QMenu, QMenuBar)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QThreadPool, QRunnable
from PyQt6.QtGui import QPixmap, QImage, QAction, QPalette, QFont

from camera_core import CameraManager
from config import ConfigManager, RESOLUTION_PRESETS
from performance_monitor import PerformanceMonitor, PerformanceWidget, OptimizedFrameProcessor
from recording_system import VideoRecorder, RecordingControlWidget
from advanced_controls import AdvancedCameraControls

class CameraWorker(QRunnable):
    """Worker for camera operations in thread pool."""
    
    def __init__(self, func, callback=None, error_callback=None, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.callback = callback
        self.error_callback = error_callback
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            if self.callback:
                self.callback(result)
        except Exception as e:
            if self.error_callback:
                self.error_callback(str(e))

class VideoFeedWidget(QLabel):
    """Custom widget for displaying camera video feed with zoom and selection."""
    
    clicked = pyqtSignal(int)  # Emits camera index when clicked
    
    def __init__(self, camera_index: int):
        super().__init__()
        self.camera_index = camera_index
        self.setMinimumSize(320, 240)
        self.setStyleSheet("border: 2px solid gray; background-color: black;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(f"Camera {camera_index}\nNo Signal")
        self.setScaledContents(True)
        
        # Context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def mousePressEvent(self, event):
        """Handle mouse click for selection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.camera_index)
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """Set selection state."""
        if selected:
            self.setStyleSheet("border: 3px solid blue; background-color: black;")
        else:
            self.setStyleSheet("border: 2px solid gray; background-color: black;")
    
    def show_context_menu(self, position):
        """Show context menu."""
        menu = QMenu(self)
        
        snapshot_action = menu.addAction("Save Snapshot")
        reset_zoom_action = menu.addAction("Reset Zoom")
        menu.addSeparator()
        properties_action = menu.addAction("Camera Properties")
        
        action = menu.exec(self.mapToGlobal(position))
        
        # Get the main window reference
        main_window = self.window()
        
        if action == snapshot_action:
            main_window.save_single_snapshot(self.camera_index)
        elif action == reset_zoom_action:
            main_window.reset_single_zoom(self.camera_index)
        elif action == properties_action:
            main_window.show_camera_properties(self.camera_index)

class MainCameraGUI(QMainWindow):
    """Main PyQt6 GUI application for FLIR camera control."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize managers and components
        self.config_manager = ConfigManager()
        self.camera_manager = CameraManager()
        self.performance_monitor = PerformanceMonitor()
        self.frame_processor = OptimizedFrameProcessor(self.performance_monitor)
        self.recorder = VideoRecorder(self.config_manager.config.recording_directory)
        
        # GUI state
        self.video_feeds: Dict[int, VideoFeedWidget] = {}
        self.zoom_levels: Dict[int, float] = {}
        self.selected_camera_index: Optional[int] = None
        
        # Thread pool for background operations
        self.thread_pool = QThreadPool()
        
        # Timer for video updates
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self.update_video_feeds)
        
        self.init_ui()
        self.setup_connections()
        self.start_systems()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Load GUI settings
        gui_settings = self.config_manager.get_gui_settings()
        
        self.setWindowTitle("FLIR Multi-Camera Control - PyQt6 Enhanced")
        self.setGeometry(100, 100, gui_settings.window_width, gui_settings.window_height)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel - Controls
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Video feeds and tabs
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([350, 1000])
        
        main_layout.addWidget(splitter)
        central_widget.setLayout(main_layout)
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        save_config_action = QAction('Save Configuration', self)
        save_config_action.triggered.connect(self.config_manager.save_config)
        file_menu.addAction(save_config_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Camera menu
        camera_menu = menubar.addMenu('Camera')
        
        connect_action = QAction('Connect All Cameras', self)
        connect_action.triggered.connect(self.connect_cameras_threaded)
        camera_menu.addAction(connect_action)
        
        disconnect_action = QAction('Disconnect All Cameras', self)
        disconnect_action.triggered.connect(self.disconnect_cameras)
        camera_menu.addAction(disconnect_action)
        
        camera_menu.addSeparator()
        
        start_action = QAction('Start All Acquisition', self)
        start_action.triggered.connect(self.start_all_acquisition)
        camera_menu.addAction(start_action)
        
        stop_action = QAction('Stop All Acquisition', self)
        stop_action.triggered.connect(self.stop_all_acquisition)
        camera_menu.addAction(stop_action)
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        dark_theme_action = QAction('Toggle Dark Theme', self)
        dark_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(dark_theme_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_left_panel(self) -> QWidget:
        """Create the left control panel."""
        panel = QWidget()
        panel.setMaximumWidth(350)
        layout = QVBoxLayout()
        
        # Connection controls
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout()
        
        self.connect_btn = QPushButton("Connect All Cameras")
        self.connect_btn.clicked.connect(self.connect_cameras_threaded)
        conn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect All")
        self.disconnect_btn.clicked.connect(self.disconnect_cameras)
        conn_layout.addWidget(self.disconnect_btn)
        
        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)
        
        # Camera settings
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QGridLayout()
        
        settings_layout.addWidget(QLabel("Resolution:"), 0, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(list(RESOLUTION_PRESETS.keys()))
        self.resolution_combo.setCurrentText(self.config_manager.get_camera_settings().resolution)
        self.resolution_combo.currentTextChanged.connect(self.on_resolution_changed)
        settings_layout.addWidget(self.resolution_combo, 0, 1)
        
        settings_layout.addWidget(QLabel("Frame Rate:"), 1, 0)
        self.framerate_edit = QLineEdit(str(self.config_manager.get_camera_settings().frame_rate))
        settings_layout.addWidget(self.framerate_edit, 1, 1)
        
        apply_btn = QPushButton("Apply Settings")
        apply_btn.clicked.connect(self.apply_camera_settings)
        settings_layout.addWidget(apply_btn, 2, 0, 1, 2)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Acquisition controls
        acq_group = QGroupBox("Acquisition")
        acq_layout = QVBoxLayout()
        
        start_btn = QPushButton("Start All Streams")
        start_btn.clicked.connect(self.start_all_acquisition)
        acq_layout.addWidget(start_btn)
        
        stop_btn = QPushButton("Stop All Streams")
        stop_btn.clicked.connect(self.stop_all_acquisition)
        acq_layout.addWidget(stop_btn)
        
        snapshot_btn = QPushButton("Save All Snapshots")
        snapshot_btn.clicked.connect(self.save_all_snapshots)
        acq_layout.addWidget(snapshot_btn)
        
        acq_group.setLayout(acq_layout)
        layout.addWidget(acq_group)
        
        # Zoom controls
        zoom_group = QGroupBox("Zoom Controls")
        zoom_layout = QVBoxLayout()
        
        self.zoom_label = QLabel("Zoom: (select a camera)")
        zoom_layout.addWidget(self.zoom_label)
        
        zoom_btn_layout = QHBoxLayout()
        
        zoom_in_btn = QPushButton("Zoom In (+)")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_btn_layout.addWidget(zoom_in_btn)
        
        zoom_out_btn = QPushButton("Zoom Out (-)")
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_btn_layout.addWidget(zoom_out_btn)
        
        reset_zoom_btn = QPushButton("Reset")
        reset_zoom_btn.clicked.connect(self.reset_zoom)
        zoom_btn_layout.addWidget(reset_zoom_btn)
        
        zoom_layout.addLayout(zoom_btn_layout)
        
        # Zoom slider
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 50)  # 1.0x to 5.0x zoom
        self.zoom_slider.setValue(10)
        self.zoom_slider.valueChanged.connect(self.on_zoom_slider_changed)
        zoom_layout.addWidget(self.zoom_slider)
        
        zoom_group.setLayout(zoom_layout)
        layout.addWidget(zoom_group)
        
        layout.addStretch()
        panel.setLayout(layout)
        return panel
    
    def create_right_panel(self) -> QWidget:
        """Create the right panel with video feeds and tabs."""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # Video feeds tab
        self.video_tab = QWidget()
        self.video_layout = QGridLayout()
        self.video_tab.setLayout(self.video_layout)
        self.tab_widget.addTab(self.video_tab, "Camera Feeds")
        
        # Advanced controls tab
        self.advanced_controls = AdvancedCameraControls(self.camera_manager)
        self.tab_widget.addTab(self.advanced_controls, "Advanced Controls")
        
        # Recording tab
        self.recording_widget = RecordingControlWidget(self.recorder, self.camera_manager)
        self.tab_widget.addTab(self.recording_widget, "Recording")
        
        # Performance tab
        self.performance_widget = PerformanceWidget(self.performance_monitor)
        self.tab_widget.addTab(self.performance_widget, "Performance")
        
        layout.addWidget(self.tab_widget)
        panel.setLayout(layout)
        return panel
    
    def setup_connections(self):
        """Setup signal connections."""
        # Performance optimization connections
        self.performance_widget.adaptive_quality_cb.toggled.connect(
            self.frame_processor.set_adaptive_quality
        )
        self.performance_widget.frame_skip_cb.toggled.connect(
            self.frame_processor.set_frame_skipping
        )
        self.performance_widget.cpu_limit_cb.toggled.connect(
            lambda checked: self.frame_processor.set_cpu_limit(checked, 80.0)
        )
    
    def start_systems(self):
        """Start background systems."""
        self.performance_monitor.start_monitoring()
        
        # Start video update timer
        gui_settings = self.config_manager.get_gui_settings()
        self.video_timer.start(gui_settings.update_interval_ms)
    
    def show_status(self, message: str, duration: int = 0, show_progress: bool = False):
        """Show status message."""
        self.status_bar.showMessage(message, duration)
        if show_progress:
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setVisible(False)
    
    def connect_cameras_threaded(self):
        """Connect to cameras in background thread."""
        self.show_status("Connecting to cameras...", show_progress=True)
        self.connect_btn.setEnabled(False)
        
        def on_success(success):
            self.progress_bar.setVisible(False)
            self.connect_btn.setEnabled(True)
            
            if success:
                self.create_video_feeds()
                self.advanced_controls.update_camera_list()
                self.recording_widget.update_camera_controls()
                
                num_cameras = len(self.camera_manager.cameras)
                self.show_status(f"Connected to {num_cameras} camera(s)", 3000)
                
                QMessageBox.information(self, "Success", 
                                      f"Connected to {num_cameras} camera(s).")
            else:
                self.show_status("No cameras found", 3000)
                QMessageBox.warning(self, "Warning", "No cameras found or failed to connect.")
        
        def on_error(error_msg):
            self.progress_bar.setVisible(False)
            self.connect_btn.setEnabled(True)
            self.show_status("Connection failed", 3000)
            QMessageBox.critical(self, "Connection Error", f"Failed to connect: {error_msg}")
        
        worker = CameraWorker(self.camera_manager.connect_all, on_success, on_error)
        self.thread_pool.start(worker)
    
    def disconnect_cameras(self):
        """Disconnect all cameras."""
        self.recorder.stop_all_recordings()
        self.camera_manager.disconnect_all()
        self.clear_video_feeds()
        self.advanced_controls.update_camera_list()
        self.recording_widget.update_camera_controls()
        self.selected_camera_index = None
        self.zoom_levels.clear()
        self.zoom_label.setText("Zoom: (select a camera)")
        self.show_status("All cameras disconnected", 3000)
    
    def create_video_feeds(self):
        """Create video feed widgets for connected cameras."""
        self.clear_video_feeds()
        
        num_cameras = len(self.camera_manager.cameras)
        if num_cameras == 0:
            return
        
        # Calculate grid layout
        cols = 2 if num_cameras > 1 else 1
        
        for i, (cam_index, camera) in enumerate(self.camera_manager.cameras.items()):
            row, col = divmod(i, cols)
            
            # Create video feed widget
            feed_widget = VideoFeedWidget(cam_index)
            feed_widget.clicked.connect(self.on_camera_selected)
            
            self.video_layout.addWidget(feed_widget, row, col)
            self.video_feeds[cam_index] = feed_widget
            self.zoom_levels[cam_index] = 1.0
    
    def clear_video_feeds(self):
        """Clear all video feed widgets."""
        for widget in self.video_feeds.values():
            widget.setParent(None)
        self.video_feeds.clear()
    
    def on_camera_selected(self, camera_index: int):
        """Handle camera selection."""
        # Clear previous selection
        if self.selected_camera_index is not None:
            if self.selected_camera_index in self.video_feeds:
                self.video_feeds[self.selected_camera_index].set_selected(False)
        
        # Set new selection
        self.selected_camera_index = camera_index
        self.video_feeds[camera_index].set_selected(True)
        
        # Update zoom controls
        zoom = self.zoom_levels.get(camera_index, 1.0)
        self.zoom_label.setText(f"Zoom Cam {camera_index}: {zoom:.1f}x")
        self.zoom_slider.setValue(int(zoom * 10))
    
    def update_video_feeds(self):
        """Update all video feed displays."""
        for cam_index, camera in self.camera_manager.cameras.items():
            if not camera.is_acquiring or cam_index not in self.video_feeds:
                continue
            
            img_np = camera.get_image()
            if img_np is not None:
                # Process frame with optimization
                processed_frame, was_skipped = self.frame_processor.process_frame(
                    cam_index, img_np, 
                    target_fps=float(self.framerate_edit.text() or "30")
                )
                
                if was_skipped:
                    continue
                
                if processed_frame is not None:
                    # Add frame to recording if active
                    if self.recorder.is_recording(cam_index):
                        self.recorder.add_frame(cam_index, processed_frame)
                    
                    # Apply digital zoom
                    zoom = self.zoom_levels.get(cam_index, 1.0)
                    if zoom > 1.0:
                        h, w = processed_frame.shape[:2]
                        crop_w, crop_h = int(w / zoom), int(h / zoom)
                        mid_x, mid_y = w // 2, h // 2
                        x1, x2 = mid_x - crop_w // 2, mid_x + crop_w // 2
                        y1, y2 = mid_y - crop_h // 2, mid_y + crop_h // 2
                        processed_frame = processed_frame[max(0, y1):min(h, y2), 
                                                        max(0, x1):min(w, x2)]
                    
                    # Convert to QImage and display
                    self.display_frame(cam_index, processed_frame)
    
    def display_frame(self, cam_index: int, frame: np.ndarray):
        """Display frame in the corresponding video widget."""
        if cam_index not in self.video_feeds:
            return
        
        try:
            # Convert to RGB if needed
            if len(frame.shape) == 3:
                if frame.shape[2] == 3:
                    # BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                else:
                    frame_rgb = frame
            else:
                # Grayscale to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            
            qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Scale to widget size while maintaining aspect ratio
            widget = self.video_feeds[cam_index]
            widget_size = widget.size()
            
            if widget_size.width() > 1 and widget_size.height() > 1:
                scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                    widget_size, Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                widget.setPixmap(scaled_pixmap)
        
        except Exception as e:
            print(f"Error displaying frame for camera {cam_index}: {e}")
    
    def on_resolution_changed(self, resolution: str):
        """Handle resolution change."""
        self.config_manager.update_camera_setting('resolution', resolution)
    
    def apply_camera_settings(self):
        """Apply camera settings to all cameras."""
        if not self.camera_manager.cameras:
            QMessageBox.warning(self, "Warning", "No cameras connected.")
            return
        
        # Check if any camera is acquiring
        if any(cam.is_acquiring for cam in self.camera_manager.cameras.values()):
            QMessageBox.critical(self, "Error", "Stop all streams before changing settings.")
            return
        
        try:
            resolution = self.resolution_combo.currentText()
            frame_rate = float(self.framerate_edit.text())
            
            # Save to config
            self.config_manager.update_camera_setting('resolution', resolution)
            self.config_manager.update_camera_setting('frame_rate', frame_rate)
            
            success_count = self.camera_manager.configure_all(resolution, frame_rate)
            
            if success_count > 0:
                self.show_status(f"Settings applied to {success_count} camera(s)", 3000)
            else:
                QMessageBox.warning(self, "Warning", "Failed to apply settings to any camera.")
                
        except ValueError:
            QMessageBox.critical(self, "Settings Error", "Invalid frame rate value.")
    
    def start_all_acquisition(self):
        """Start acquisition on all cameras."""
        success_count = self.camera_manager.start_all_acquisition()
        self.show_status(f"Started acquisition on {success_count} camera(s)", 3000)
    
    def stop_all_acquisition(self):
        """Stop acquisition on all cameras."""
        success_count = self.camera_manager.stop_all_acquisition()
        self.show_status(f"Stopped acquisition on {success_count} camera(s)", 3000)
    
    def save_all_snapshots(self):
        """Save snapshots from all acquiring cameras."""
        timestamp = int(time.time())
        saved_count = 0
        save_dir = Path(self.config_manager.config.save_directory)
        save_dir.mkdir(exist_ok=True)
        
        for cam_index, camera in self.camera_manager.cameras.items():
            if camera.is_acquiring:
                img = camera.get_image()
                if img is not None:
                    filename = save_dir / f"snapshot_cam{cam_index}_{timestamp}.png"
                    cv2.imwrite(str(filename), img)
                    saved_count += 1
        
        if saved_count > 0:
            self.show_status(f"Saved {saved_count} snapshot(s)", 3000)
            QMessageBox.information(self, "Saved", f"Saved {saved_count} snapshot(s).")
        else:
            QMessageBox.warning(self, "Warning", "No images to save.")
    
    def save_single_snapshot(self, cam_index: int):
        """Save snapshot from a specific camera."""
        if cam_index in self.camera_manager.cameras:
            camera = self.camera_manager.cameras[cam_index]
            if camera.is_acquiring:
                img = camera.get_image()
                if img is not None:
                    timestamp = int(time.time())
                    save_dir = Path(self.config_manager.config.save_directory)
                    save_dir.mkdir(exist_ok=True)
                    filename = save_dir / f"snapshot_cam{cam_index}_{timestamp}.png"
                    cv2.imwrite(str(filename), img)
                    self.show_status(f"Snapshot saved: {filename.name}", 3000)
    
    def zoom_in(self):
        """Zoom in on selected camera."""
        if self.selected_camera_index is not None:
            current_zoom = self.zoom_levels[self.selected_camera_index]
            new_zoom = min(5.0, current_zoom + 0.2)
            self.zoom_levels[self.selected_camera_index] = new_zoom
            self.update_zoom_display()
    
    def zoom_out(self):
        """Zoom out on selected camera."""
        if self.selected_camera_index is not None:
            current_zoom = self.zoom_levels[self.selected_camera_index]
            new_zoom = max(1.0, current_zoom - 0.2)
            self.zoom_levels[self.selected_camera_index] = new_zoom
            self.update_zoom_display()
    
    def reset_zoom(self):
        """Reset zoom on selected camera."""
        if self.selected_camera_index is not None:
            self.zoom_levels[self.selected_camera_index] = 1.0
            self.update_zoom_display()
    
    def reset_single_zoom(self, cam_index: int):
        """Reset zoom for a specific camera."""
        if cam_index in self.zoom_levels:
            self.zoom_levels[cam_index] = 1.0
            if self.selected_camera_index == cam_index:
                self.update_zoom_display()
    
    def on_zoom_slider_changed(self, value: int):
        """Handle zoom slider change."""
        if self.selected_camera_index is not None:
            zoom = value / 10.0  # Convert slider value to zoom level
            self.zoom_levels[self.selected_camera_index] = zoom
            self.update_zoom_display()
    
    def update_zoom_display(self):
        """Update zoom level display."""
        if self.selected_camera_index is not None:
            zoom = self.zoom_levels[self.selected_camera_index]
            self.zoom_label.setText(f"Zoom Cam {self.selected_camera_index}: {zoom:.1f}x")
            self.zoom_slider.setValue(int(zoom * 10))
    
    def show_camera_properties(self, cam_index: int):
        """Show camera properties dialog."""
        # Switch to advanced controls tab and update
        self.tab_widget.setCurrentWidget(self.advanced_controls)
        self.advanced_controls.update_camera_list()
        
        # Select the camera in the combo box
        for i in range(self.advanced_controls.camera_combo.count()):
            if self.advanced_controls.camera_combo.itemData(i) == cam_index:
                self.advanced_controls.camera_combo.setCurrentIndex(i)
                break
    
    def toggle_theme(self):
        """Toggle between light and dark theme."""
        current_theme = self.config_manager.get_gui_settings().theme
        new_theme = "dark" if current_theme == "default" else "default"
        
        self.config_manager.update_gui_setting('theme', new_theme)
        
        QMessageBox.information(self, "Theme Changed", 
                              "Theme changed. Restart the application to see full effect.")
    
    def show_about(self):
        """Show about dialog."""
        about_text = """
        <h3>FLIR Multi-Camera Control</h3>
        <p>Enhanced PyQt6 application for controlling multiple FLIR cameras</p>
        <p><b>Features:</b></p>
        <ul>
        <li>Multi-camera video streaming</li>
        <li>Advanced camera parameter control</li>
        <li>Video recording with multiple codecs</li>
        <li>Performance monitoring and optimization</li>
        <li>Digital zoom and image enhancement</li>
        <li>Configurable settings with persistence</li>
        </ul>
        <p><b>Requirements:</b> PySpin, PyQt6, OpenCV, NumPy</p>
        """
        QMessageBox.about(self, "About", about_text)
    
    def closeEvent(self, event):
        """Handle application close event."""
        reply = QMessageBox.question(self, 'Quit', 
                                   'Are you sure you want to quit?\nThis will disconnect all cameras and stop recordings.',
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.show_status("Shutting down...", show_progress=True)
            
            # Stop all systems
            self.video_timer.stop()
            self.recorder.stop_all_recordings()
            self.performance_monitor.stop_monitoring()
            self.camera_manager.cleanup()
            
            # Save configuration
            self.config_manager.save_config()
            
            event.accept()
        else:
            event.ignore()

def main():
   """Main application entry point."""
   app = QApplication(sys.argv)
   
   # Set application properties
   app.setApplicationName("FLIR Camera Control")
   app.setApplicationVersion("2.0")
   app.setOrganizationName("Camera Control Solutions")
   
   # Create and show main window
   window = MainCameraGUI()
   window.show()
   
   # Run application
   sys.exit(app.exec())

if __name__ == "__main__":
   main()