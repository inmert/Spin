# performance_monitor.py
"""
Performance monitoring and optimization for PyQt6 camera application.
"""
import time
import psutil
import threading
import numpy as np
import cv2
from collections import deque
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QCheckBox, QGroupBox, QTreeWidget, QTreeWidgetItem,
                           QProgressBar, QPushButton)

class PerformanceMonitor(QObject):
    """Monitors application performance metrics."""
    
    # Signals for PyQt6
    metrics_updated = pyqtSignal(dict)
    
    def __init__(self, history_size: int = 100):
        super().__init__()
        self.history_size = history_size
        self.metrics = {
            'fps': deque(maxlen=history_size),
            'cpu_percent': deque(maxlen=history_size),
            'memory_mb': deque(maxlen=history_size),
            'frame_processing_time': deque(maxlen=history_size),
            'dropped_frames': deque(maxlen=history_size),
        }
        
        self.camera_metrics: Dict[int, Dict] = {}
        self.last_frame_times: Dict[int, float] = {}
        self.frame_counts: Dict[int, int] = {}
        self.dropped_frame_counts: Dict[int, int] = {}
        
        self._monitoring = False
        self._monitor_thread = None
        
        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._emit_metrics)
        
    def start_monitoring(self):
        """Start performance monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        # Start Qt timer for signal emission
        self.update_timer.start(1000)  # Update every second
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self._monitoring = False
        self.update_timer.stop()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
    
    def record_frame_processed(self, camera_index: int, processing_time: float):
        """Record that a frame was processed."""
        current_time = time.time()
        
        # Initialize camera metrics if needed
        if camera_index not in self.camera_metrics:
            self.camera_metrics[camera_index] = {
                'fps': deque(maxlen=self.history_size),
                'processing_times': deque(maxlen=self.history_size),
                'last_fps_calc': current_time,
                'frames_since_calc': 0
            }
        
        metrics = self.camera_metrics[camera_index]
        metrics['processing_times'].append(processing_time)
        metrics['frames_since_calc'] += 1
        
        # Calculate FPS every second
        if current_time - metrics['last_fps_calc'] >= 1.0:
            fps = metrics['frames_since_calc'] / (current_time - metrics['last_fps_calc'])
            metrics['fps'].append(fps)
            metrics['last_fps_calc'] = current_time
            metrics['frames_since_calc'] = 0
    
    def record_dropped_frame(self, camera_index: int):
        """Record a dropped frame."""
        self.dropped_frame_counts[camera_index] = self.dropped_frame_counts.get(camera_index, 0) + 1
    
    def get_current_metrics(self) -> Dict:
        """Get current performance metrics."""
        return {
            'system_cpu': self.metrics['cpu_percent'][-1] if self.metrics['cpu_percent'] else 0,
            'system_memory_mb': self.metrics['memory_mb'][-1] if self.metrics['memory_mb'] else 0,
            'average_fps': self._get_average_fps(),
            'camera_metrics': {
                cam_idx: {
                    'fps': metrics['fps'][-1] if metrics['fps'] else 0,
                    'avg_processing_time': sum(metrics['processing_times']) / len(metrics['processing_times']) 
                              if metrics['processing_times'] else 0,
                    'dropped_frames': self.dropped_frame_counts.get(cam_idx, 0)
                }
                for cam_idx, metrics in self.camera_metrics.items()
            }
        }
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                # System metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                memory_info = psutil.virtual_memory()
                memory_mb = memory_info.used / (1024 * 1024)
                
                self.metrics['cpu_percent'].append(cpu_percent)
                self.metrics['memory_mb'].append(memory_mb)
                
                time.sleep(1.0)  # Update every second
                
            except Exception as e:
                print(f"Performance monitoring error: {e}")
                time.sleep(1.0)
    
    def _emit_metrics(self):
        """Emit metrics signal for Qt widgets."""
        self.metrics_updated.emit(self.get_current_metrics())
    
    def _get_average_fps(self) -> float:
        """Calculate average FPS across all cameras."""
        if not self.camera_metrics:
            return 0.0
        
        total_fps = 0
        active_cameras = 0
        
        for metrics in self.camera_metrics.values():
            if metrics['fps']:
                total_fps += metrics['fps'][-1]
                active_cameras += 1
        
        return total_fps / active_cameras if active_cameras > 0 else 0.0

class PerformanceWidget(QWidget):
    """PyQt6 widget for displaying performance metrics."""
    
    def __init__(self, monitor: PerformanceMonitor):
        super().__init__()
        self.monitor = monitor
        self.monitor.metrics_updated.connect(self.update_metrics)
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # System metrics group
        sys_group = QGroupBox("System Performance")
        sys_layout = QHBoxLayout()
        
        self.cpu_label = QLabel("CPU: 0%")
        self.memory_label = QLabel("Memory: 0 MB")
        self.fps_label = QLabel("Avg FPS: 0.0")
        
        sys_layout.addWidget(self.cpu_label)
        sys_layout.addWidget(self.memory_label)
        sys_layout.addWidget(self.fps_label)
        sys_layout.addStretch()
        
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)
        
        # Camera metrics tree
        camera_group = QGroupBox("Camera Performance")
        camera_layout = QVBoxLayout()
        
        self.camera_tree = QTreeWidget()
        self.camera_tree.setHeaderLabels(["Camera", "FPS", "Proc. Time", "Dropped"])
        camera_layout.addWidget(self.camera_tree)
        
        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)
        
        # Optimization controls
        opt_group = QGroupBox("Performance Optimization")
        opt_layout = QVBoxLayout()
        
        self.adaptive_quality_cb = QCheckBox("Adaptive Quality")
        self.frame_skip_cb = QCheckBox("Frame Skipping")
        self.cpu_limit_cb = QCheckBox("CPU Usage Limit")
        
        opt_layout.addWidget(self.adaptive_quality_cb)
        opt_layout.addWidget(self.frame_skip_cb)
        opt_layout.addWidget(self.cpu_limit_cb)
        
        # Reset button
        reset_btn = QPushButton("Reset Statistics")
        reset_btn.clicked.connect(self.reset_statistics)
        opt_layout.addWidget(reset_btn)
        
        opt_group.setLayout(opt_layout)
        layout.addWidget(opt_group)
        
        self.setLayout(layout)
    
    def update_metrics(self, metrics: dict):
        """Update displayed performance metrics."""
        try:
            # Update system metrics
            self.cpu_label.setText(f"CPU: {metrics['system_cpu']:.1f}%")
            self.memory_label.setText(f"Memory: {metrics['system_memory_mb']:.0f} MB")
            self.fps_label.setText(f"Avg FPS: {metrics['average_fps']:.1f}")
            
            # Update camera tree
            self._update_camera_tree(metrics['camera_metrics'])
            
        except Exception as e:
            print(f"Error updating performance metrics: {e}")
    
    def _update_camera_tree(self, camera_metrics: Dict):
        """Update camera performance tree."""
        self.camera_tree.clear()
        
        if not camera_metrics:
            item = QTreeWidgetItem(["No active cameras", "", "", ""])
            self.camera_tree.addTopLevelItem(item)
            return
        
        for cam_idx, metrics in camera_metrics.items():
            item = QTreeWidgetItem([
                f"Camera {cam_idx}",
                f"{metrics['fps']:.1f}",
                f"{metrics['avg_processing_time']*1000:.1f}ms",
                f"{metrics['dropped_frames']}"
            ])
            self.camera_tree.addTopLevelItem(item)
    
    def reset_statistics(self):
        """Reset performance statistics."""
        self.monitor.dropped_frame_counts.clear()
        for metrics in self.monitor.camera_metrics.values():
            metrics['fps'].clear()
            metrics['processing_times'].clear()
            metrics['frames_since_calc'] = 0
        
        self.monitor.metrics['cpu_percent'].clear()
        self.monitor.metrics['memory_mb'].clear()

class OptimizedFrameProcessor:
    """Optimized frame processing with adaptive quality."""
    
    def __init__(self, performance_monitor: PerformanceMonitor):
        self.monitor = performance_monitor
        self.adaptive_quality = False
        self.frame_skipping = False
        self.cpu_limit_enabled = False
        self.cpu_limit_threshold = 80.0
        self.quality_level = 1.0
        self.frame_skip_counter = {}
        
    def set_adaptive_quality(self, enabled: bool):
        """Enable/disable adaptive quality."""
        self.adaptive_quality = enabled
        
    def set_frame_skipping(self, enabled: bool):
        """Enable/disable frame skipping."""
        self.frame_skipping = enabled
        
    def set_cpu_limit(self, enabled: bool, threshold: float = 80.0):
        """Enable/disable CPU usage limiting."""
        self.cpu_limit_enabled = enabled
        self.cpu_limit_threshold = threshold
        
    def process_frame(self, camera_index: int, frame: np.ndarray, target_fps: float = 30.0) -> Tuple[Optional[np.ndarray], bool]:
        """Process frame with optimization. Returns (processed_frame, was_skipped)."""
        start_time = time.time()
        
        # Check if we should skip this frame
        if self.frame_skipping and self._should_skip_frame(camera_index, target_fps):
            self.monitor.record_dropped_frame(camera_index)
            return None, True  # Frame skipped
        
        # Apply adaptive quality
        processed_frame = frame
        if self.adaptive_quality:
            processed_frame = self._apply_adaptive_quality(processed_frame, camera_index)
        
        processing_time = time.time() - start_time
        self.monitor.record_frame_processed(camera_index, processing_time)
        
        return processed_frame, False  # Frame processed
    
    def _should_skip_frame(self, camera_index: int, target_fps: float) -> bool:
        """Determine if frame should be skipped based on performance."""
        metrics = self.monitor.get_current_metrics()
        camera_metrics = metrics['camera_metrics'].get(camera_index, {})
        
        current_fps = camera_metrics.get('fps', 0)
        cpu_usage = metrics['system_cpu']
        
        # Skip frames if CPU usage is high or FPS is below target
        should_skip = False
        
        if self.cpu_limit_enabled and cpu_usage > self.cpu_limit_threshold:
            should_skip = True
        elif current_fps < target_fps * 0.8:
            should_skip = True
        
        if should_skip:
            skip_counter = self.frame_skip_counter.get(camera_index, 0)
            self.frame_skip_counter[camera_index] = skip_counter + 1
            
            # Skip every other frame when under stress
            return skip_counter % 2 == 0
        
        return False
    
    def _apply_adaptive_quality(self, frame: np.ndarray, camera_index: int) -> np.ndarray:
        """Apply adaptive quality based on performance."""
        metrics = self.monitor.get_current_metrics()
        cpu_usage = metrics['system_cpu']
        
        # Adjust quality based on CPU usage
        if cpu_usage > 90:
            self.quality_level = 0.5
        elif cpu_usage > 70:
            self.quality_level = 0.75
        else:
            self.quality_level = 1.0
        
        if self.quality_level < 1.0:
            # Reduce resolution
            h, w = frame.shape[:2]
            new_h, new_w = int(h * self.quality_level), int(w * self.quality_level)
            
            if new_h > 0 and new_w > 0:
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                # Scale back up for display
                frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
        
        return frame