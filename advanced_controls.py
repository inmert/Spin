# advanced_controls.py
"""
Advanced camera controls widget for PyQt6.
"""
from typing import Dict, Optional, Any
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                           QSlider, QPushButton, QComboBox, QCheckBox,
                           QGroupBox, QGridLayout, QTreeWidget, QTreeWidgetItem,
                           QSpinBox, QDoubleSpinBox, QTabWidget)
import PySpin

class AdvancedCameraControls(QWidget):
    """Widget for advanced camera parameter control."""
    
    def __init__(self, camera_manager):
        super().__init__()
        self.manager = camera_manager
        self.selected_camera = None
        self.parameter_widgets = {}
        
        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_parameter_values)
        self.update_timer.start(2000)  # Update every 2 seconds
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Camera selection
        selection_group = QGroupBox("Camera Selection")
        selection_layout = QHBoxLayout()
        
        selection_layout.addWidget(QLabel("Select Camera:"))
        self.camera_combo = QComboBox()
        self.camera_combo.currentTextChanged.connect(self.on_camera_selected)
        selection_layout.addWidget(self.camera_combo)
        selection_layout.addStretch()
        
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)
        
        # Create tabbed interface for different parameter categories
        self.tab_widget = QTabWidget()
        
        # Exposure tab
        self.exposure_tab = self.create_exposure_tab()
        self.tab_widget.addTab(self.exposure_tab, "Exposure")
        
        # Gain tab
        self.gain_tab = self.create_gain_tab()
        self.tab_widget.addTab(self.gain_tab, "Gain")
        
        # Image tab
        self.image_tab = self.create_image_tab()
        self.tab_widget.addTab(self.image_tab, "Image")
        
        # Info tab
        self.info_tab = self.create_info_tab()
        self.tab_widget.addTab(self.info_tab, "Camera Info")
        
        layout.addWidget(self.tab_widget)
        
        # Reset all button
        reset_btn = QPushButton("Reset All Parameters")
        reset_btn.clicked.connect(self.reset_all_parameters)
        layout.addWidget(reset_btn)
        
        self.setLayout(layout)
    
    def create_exposure_tab(self) -> QWidget:
        """Create the exposure control tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Auto exposure
        auto_group = QGroupBox("Auto Exposure")
        auto_layout = QVBoxLayout()
        
        self.auto_exposure_cb = QCheckBox("Enable Auto Exposure")
        self.auto_exposure_cb.toggled.connect(self.on_auto_exposure_changed)
        auto_layout.addWidget(self.auto_exposure_cb)
        
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # Manual exposure
        manual_group = QGroupBox("Manual Exposure")
        manual_layout = QGridLayout()
        
        # Exposure time
        manual_layout.addWidget(QLabel("Exposure Time (μs):"), 0, 0)
        self.exposure_value_label = QLabel("0")
        manual_layout.addWidget(self.exposure_value_label, 0, 1)
        
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setRange(100, 50000)
        self.exposure_slider.setValue(10000)
        self.exposure_slider.valueChanged.connect(self.on_exposure_changed)
        manual_layout.addWidget(self.exposure_slider, 1, 0, 1, 2)
        
        # Quick exposure presets
        preset_layout = QHBoxLayout()
        presets = [("Fast", 1000), ("Medium", 10000), ("Slow", 30000)]
        for name, value in presets:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, v=value: self.set_exposure_preset(v))
            preset_layout.addWidget(btn)
        
        manual_layout.addLayout(preset_layout, 2, 0, 1, 2)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_gain_tab(self) -> QWidget:
        """Create the gain control tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Auto gain
        auto_group = QGroupBox("Auto Gain")
        auto_layout = QVBoxLayout()
        
        self.auto_gain_cb = QCheckBox("Enable Auto Gain")
        self.auto_gain_cb.toggled.connect(self.on_auto_gain_changed)
        auto_layout.addWidget(self.auto_gain_cb)
        
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # Manual gain
        manual_group = QGroupBox("Manual Gain")
        manual_layout = QGridLayout()
        
        # Gain value
        manual_layout.addWidget(QLabel("Gain (dB):"), 0, 0)
        self.gain_value_label = QLabel("0.0")
        manual_layout.addWidget(self.gain_value_label, 0, 1)
        
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 400)  # 0-40 dB with 0.1 dB resolution
        self.gain_slider.setValue(0)
        self.gain_slider.valueChanged.connect(self.on_gain_changed)
        manual_layout.addWidget(self.gain_slider, 1, 0, 1, 2)
        
        manual_group.setLayout(manual_layout)
        layout.addWidget(manual_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_image_tab(self) -> QWidget:
        """Create the image quality control tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # White balance
        wb_group = QGroupBox("White Balance")
        wb_layout = QVBoxLayout()
        
        self.auto_wb_cb = QCheckBox("Auto White Balance")
        self.auto_wb_cb.toggled.connect(self.on_auto_wb_changed)
        wb_layout.addWidget(self.auto_wb_cb)
        
        wb_group.setLayout(wb_layout)
        layout.addWidget(wb_group)
        
        # Gamma correction
        gamma_group = QGroupBox("Gamma Correction")
        gamma_layout = QGridLayout()
        
        gamma_layout.addWidget(QLabel("Gamma:"), 0, 0)
        self.gamma_value_label = QLabel("1.0")
        gamma_layout.addWidget(self.gamma_value_label, 0, 1)
        
        self.gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(40, 200)  # 0.4 to 2.0 with 0.01 resolution
        self.gamma_slider.setValue(100)
        self.gamma_slider.valueChanged.connect(self.on_gamma_changed)
        gamma_layout.addWidget(self.gamma_slider, 1, 0, 1, 2)
        
        gamma_group.setLayout(gamma_layout)
        layout.addWidget(gamma_group)
        
        # Black level
        black_group = QGroupBox("Black Level")
        black_layout = QGridLayout()
        
        black_layout.addWidget(QLabel("Black Level:"), 0, 0)
        self.black_level_spinbox = QSpinBox()
        self.black_level_spinbox.setRange(0, 100)
        self.black_level_spinbox.valueChanged.connect(self.on_black_level_changed)
        black_layout.addWidget(self.black_level_spinbox, 0, 1)
        
        black_group.setLayout(black_layout)
        layout.addWidget(black_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_info_tab(self) -> QWidget:
        """Create the camera information tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Camera info tree
        info_group = QGroupBox("Camera Information")
        info_layout = QVBoxLayout()
        
        self.info_tree = QTreeWidget()
        self.info_tree.setHeaderLabels(["Property", "Value"])
        info_layout.addWidget(self.info_tree)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Info")
        refresh_btn.clicked.connect(self.refresh_camera_info)
        info_layout.addWidget(refresh_btn)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        widget.setLayout(layout)
        return widget
    
    def update_camera_list(self):
        """Update the camera selection dropdown."""
        self.camera_combo.clear()
        
        for idx, cam in self.manager.cameras.items():
            display_text = f"Camera {idx} ({cam.serial})"
            self.camera_combo.addItem(display_text, idx)
        
        # Auto-select first camera if available
        if self.camera_combo.count() > 0:
            self.camera_combo.setCurrentIndex(0)
            self.on_camera_selected()
    
    def on_camera_selected(self):
        """Handle camera selection change."""
        current_data = self.camera_combo.currentData()
        if current_data is not None:
            cam_idx = current_data
            self.selected_camera = self.manager.cameras.get(cam_idx)
            self.update_parameter_values()
            self.refresh_camera_info()
        else:
            self.selected_camera = None
    
    def update_parameter_values(self):
        """Update UI with current camera parameter values."""
        if not self.selected_camera or not self.selected_camera.is_connected:
            return
        
        try:
            # Update exposure
            exposure = self.selected_camera.get_exposure_time()
            if exposure is not None:
                self.exposure_slider.setValue(int(exposure))
                self.exposure_value_label.setText(f"{exposure:.0f}")
            
            # Update auto exposure
            auto_exp = self.selected_camera.get_auto_exposure()
            self.auto_exposure_cb.setChecked(auto_exp)
            self.exposure_slider.setEnabled(not auto_exp)
            
            # Update gain
            gain = self.selected_camera.get_gain()
            if gain is not None:
                self.gain_slider.setValue(int(gain * 10))  # Convert to 0.1 dB resolution
                self.gain_value_label.setText(f"{gain:.1f}")
            
            # Update auto gain (if available)
            try:
                if hasattr(self.selected_camera.cam, 'GainAuto'):
                    auto_gain = self.selected_camera.cam.GainAuto.GetValue() == PySpin.GainAuto_Continuous
                    self.auto_gain_cb.setChecked(auto_gain)
                    self.gain_slider.setEnabled(not auto_gain)
            except:
                pass
            
        except Exception as e:
            print(f"Error updating parameter values: {e}")
    
    def on_auto_exposure_changed(self, checked: bool):
        """Handle auto exposure toggle."""
        if self.selected_camera:
            self.selected_camera.set_auto_exposure(checked)
            self.exposure_slider.setEnabled(not checked)
    
    def on_exposure_changed(self, value: int):
        """Handle exposure slider change."""
        if self.selected_camera and not self.auto_exposure_cb.isChecked():
            self.selected_camera.set_exposure_time(float(value))
            self.exposure_value_label.setText(f"{value}")
    
    def set_exposure_preset(self, value: int):
        """Set exposure to a preset value."""
        if self.selected_camera:
            self.exposure_slider.setValue(value)
            self.on_exposure_changed(value)
    
    def on_auto_gain_changed(self, checked: bool):
        """Handle auto gain toggle."""
        if self.selected_camera:
            try:
                if hasattr(self.selected_camera.cam, 'GainAuto'):
                    mode = PySpin.GainAuto_Continuous if checked else PySpin.GainAuto_Off
                    self.selected_camera.cam.GainAuto.SetValue(mode)
                    self.gain_slider.setEnabled(not checked)
            except Exception as e:
                print(f"Error setting auto gain: {e}")
    
    def on_gain_changed(self, value: int):
        """Handle gain slider change."""
        if self.selected_camera and not self.auto_gain_cb.isChecked():
            gain_db = value / 10.0  # Convert from 0.1 dB resolution
            self.selected_camera.set_gain(gain_db)
            self.gain_value_label.setText(f"{gain_db:.1f}")
    
    def on_auto_wb_changed(self, checked: bool):
        """Handle auto white balance toggle."""
        if self.selected_camera:
            try:
                if hasattr(self.selected_camera.cam, 'BalanceWhiteAuto'):
                    mode = PySpin.BalanceWhiteAuto_Continuous if checked else PySpin.BalanceWhiteAuto_Off
                    self.selected_camera.cam.BalanceWhiteAuto.SetValue(mode)
            except Exception as e:
                print(f"Error setting auto white balance: {e}")
    
    def on_gamma_changed(self, value: int):
        """Handle gamma slider change."""
        if self.selected_camera:
            gamma = value / 100.0  # Convert from slider value
            self.gamma_value_label.setText(f"{gamma:.2f}")
            
            try:
                if hasattr(self.selected_camera.cam, 'Gamma') and PySpin.IsWritable(self.selected_camera.cam.Gamma):
                    self.selected_camera.cam.Gamma.SetValue(gamma)
            except Exception as e:
                print(f"Error setting gamma: {e}")
    
    def on_black_level_changed(self, value: int):
        """Handle black level change."""
        if self.selected_camera:
            try:
                if hasattr(self.selected_camera.cam, 'BlackLevel') and PySpin.IsWritable(self.selected_camera.cam.BlackLevel):
                    self.selected_camera.cam.BlackLevel.SetValue(float(value))
            except Exception as e:
                print(f"Error setting black level: {e}")
    
    def refresh_camera_info(self):
        """Refresh camera information display."""
        self.info_tree.clear()
        
        if not self.selected_camera:
            return
        
        info = self.selected_camera.get_camera_info()
        
        # Add basic info
        basic_item = QTreeWidgetItem(["Basic Information", ""])
        self.info_tree.addTopLevelItem(basic_item)
        
        for key, value in info.items():
            if key not in ['width', 'height', 'frame_rate', 'exposure_time', 'gain', 'pixel_format']:
                item = QTreeWidgetItem([key.replace('_', ' ').title(), str(value)])
                basic_item.addChild(item)
        
        # Add acquisition info
        if self.selected_camera.is_connected:
            acq_item = QTreeWidgetItem(["Acquisition Settings", ""])
            self.info_tree.addTopLevelItem(acq_item)
            
            acq_settings = [
                ("Width", info.get('width', 'N/A')),
                ("Height", info.get('height', 'N/A')),
                ("Frame Rate", f"{info.get('frame_rate', 0):.1f} fps"),
                ("Pixel Format", info.get('pixel_format', 'N/A')),
                ("Exposure Time", f"{info.get('exposure_time', 0):.0f} μs"),
                ("Gain", f"{info.get('gain', 0):.1f} dB"),
                ("Auto Exposure", str(info.get('auto_exposure', False)))
            ]
            
            for name, value in acq_settings:
                item = QTreeWidgetItem([name, str(value)])
                acq_item.addChild(item)
        
        # Expand all items
        self.info_tree.expandAll()
    
    def reset_all_parameters(self):
        """Reset all parameters to default values."""
        if not self.selected_camera:
            return
        
        # Reset exposure
        self.exposure_slider.setValue(10000)
        self.on_exposure_changed(10000)
        
        # Reset gain
        self.gain_slider.setValue(0)
        self.on_gain_changed(0)
        
        # Reset gamma
        self.gamma_slider.setValue(100)
        self.on_gamma_changed(100)
        
        # Reset black level
        self.black_level_spinbox.setValue(0)
        self.on_black_level_changed(0)
        
        # Enable auto modes
        self.auto_exposure_cb.setChecked(True)
        self.auto_gain_cb.setChecked(True)
        self.auto_wb_cb.setChecked(True)