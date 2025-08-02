# FLIR Multi-Camera Control - PyQt6 Enhanced

A professional-grade PyQt6 application for controlling multiple FLIR cameras with advanced features including real-time video streaming, recording, performance monitoring, and comprehensive camera parameter control.

## Features

### 🎥 **Multi-Camera Support**
- Connect and control multiple FLIR cameras simultaneously
- Real-time video streaming with optimized performance
- Individual camera selection and control
- Dynamic grid layout for video feeds

### 📹 **Video Recording**
- Multi-camera video recording with configurable codecs (XVID, MJPG, H264, MP4V)
- Individual camera recording control
- Automatic timestamping and organized file structure
- Real-time recording duration display

### ⚙️ **Advanced Camera Controls**
- Real-time exposure time adjustment
- Gain control with auto/manual modes
- White balance and gamma correction
- Black level adjustment
- Comprehensive camera information display

### 📊 **Performance Monitoring**
- Real-time CPU and memory usage monitoring
- Frame rate tracking per camera
- Adaptive quality scaling based on system performance
- Frame skipping during high load periods

### 🔍 **Digital Zoom & Enhancement**
- Per-camera digital zoom (1x to 5x)
- Zoom slider and preset controls
- Click-to-select camera feeds
- Context menu for quick actions

### 💾 **Configuration Management**
- Persistent settings with JSON configuration
- Camera parameter presets
- GUI theme selection (light/dark)
- Automatic configuration saving

### 🎨 **Modern UI**
- PyQt6-based interface with professional styling
- Tabbed interface for organized controls
- Dark theme support
- Status bar with progress indicators
- Comprehensive menu system

## Requirements

### Software Dependencies
- Python 3.8+
- PyQt6 >= 6.4.0
- OpenCV >= 4.8.0
- NumPy >= 1.24.0
- psutil >= 5.9.0
- Pillow >= 9.5.0

### Hardware Requirements
- FLIR camera(s) compatible with Spinnaker SDK
- USB 3.0 or GigE connection
- Minimum 8GB RAM (16GB+ recommended for multiple cameras)
- Multi-core processor recommended

### FLIR Spinnaker SDK
**Important**: You must install the FLIR Spinnaker SDK and PySpin separately:

1. Download from [FLIR's website](https://www.flir.com/products/spinnaker-sdk/)
2. Install the Spinnaker SDK for your operating system
3. Install PySpin Python bindings (included with SDK)

PySpin cannot be installed via pip and requires manual installation from FLIR.

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd flir-camera-control-pyqt6