# camera_core.py
"""
Enhanced core module for FLIR camera interaction using PySpin.
Includes advanced parameter control and error handling.
"""
import time
import logging
import gc
from typing import Optional, Dict, List, Tuple, Any
from enum import Enum

import numpy as np
import PySpin

from config import RESOLUTION_PRESETS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CameraError(Exception):
    """Custom exception for camera-related errors."""
    pass

class CameraState(Enum):
    """Camera state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ACQUIRING = "acquiring"
    ERROR = "error"

class FLIRCamera:
    """Enhanced wrapper for a single PySpin Camera object."""

    def __init__(self, pyspin_cam_obj, index: int):
        self.cam: PySpin.CameraPtr = pyspin_cam_obj
        self.index = index
        self.state = CameraState.DISCONNECTED
        self.last_error = None
        
        try:
            self.cam.Init()
            self.state = CameraState.CONNECTED
            
            # Get camera info
            serial_node = PySpin.CStringPtr(self.cam.GetTLDeviceNodeMap().GetNode('DeviceSerialNumber'))
            self.serial = serial_node.GetValue() if PySpin.IsReadable(serial_node) else f"UNKNOWN_{index}"
            
            model_node = PySpin.CStringPtr(self.cam.GetTLDeviceNodeMap().GetNode('DeviceModelName'))
            self.model = model_node.GetValue() if PySpin.IsReadable(model_node) else "Unknown Model"
            
            # Initialize parameters
            self._initialize_parameters()
            
        except PySpin.SpinnakerException as e:
            self.state = CameraState.ERROR
            self.last_error = str(e)
            logging.error(f"[Cam {self.index}] Initialization failed: {e}")

    def _initialize_parameters(self):
        """Initialize camera parameters to safe defaults."""
        try:
            # Set acquisition mode
            self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
            
            # Set buffer handling mode
            s_node_map = self.cam.GetTLStreamNodeMap()
            handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode('StreamBufferHandlingMode'))
            if PySpin.IsWritable(handling_mode):
                handling_mode.SetIntValue(
                    PySpin.CEnumEntryPtr(handling_mode.GetEntryByName('NewestOnly')).GetValue()
                )
            
            logging.info(f"[Cam {self.index}] Parameters initialized.")
            
        except PySpin.SpinnakerException as e:
            logging.warning(f"[Cam {self.index}] Parameter initialization warning: {e}")

    @property
    def is_acquiring(self) -> bool:
        return self.state == CameraState.ACQUIRING

    @property
    def is_connected(self) -> bool:
        return self.state in [CameraState.CONNECTED, CameraState.ACQUIRING]

    def configure(self, resolution: str = 'HD', frame_rate: float = 30.0) -> bool:
        """Configure camera resolution and frame rate."""
        if self.state == CameraState.ACQUIRING:
            logging.warning(f"[Cam {self.index}] Cannot configure while acquiring images.")
            return False
        
        if self.state != CameraState.CONNECTED:
            logging.error(f"[Cam {self.index}] Camera not connected.")
            return False
        
        try:
            # Set resolution
            if resolution in RESOLUTION_PRESETS:
                width, height = RESOLUTION_PRESETS[resolution]
                
                # Check if dimensions are valid
                max_width = self.cam.WidthMax.GetValue()
                max_height = self.cam.HeightMax.GetValue()
                
                if width <= max_width and height <= max_height:
                    self.cam.Width.SetValue(width)
                    self.cam.Height.SetValue(height)
                else:
                    logging.warning(f"[Cam {self.index}] Requested resolution {width}x{height} exceeds maximum {max_width}x{max_height}")
                    return False

            # Set frame rate
            if PySpin.IsWritable(self.cam.AcquisitionFrameRateEnable):
                self.cam.AcquisitionFrameRateEnable.SetValue(True)
                
                if PySpin.IsWritable(self.cam.AcquisitionFrameRate):
                    max_fps = self.cam.AcquisitionFrameRate.GetMax()
                    min_fps = self.cam.AcquisitionFrameRate.GetMin()
                    frame_rate = max(min_fps, min(max_fps, frame_rate))
                    self.cam.AcquisitionFrameRate.SetValue(frame_rate)

            logging.info(f"[Cam {self.index}] Configured to {resolution} @ {frame_rate}fps.")
            return True
            
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Configuration failed: {e}")
            self.last_error = str(e)
            return False

    def set_exposure_time(self, exposure_us: float) -> bool:
        """Set exposure time in microseconds."""
        try:
            if PySpin.IsWritable(self.cam.ExposureTime):
                # Ensure auto exposure is off
                if PySpin.IsWritable(self.cam.ExposureAuto):
                    self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                
                min_exp = self.cam.ExposureTime.GetMin()
                max_exp = self.cam.ExposureTime.GetMax()
                exposure_us = max(min_exp, min(max_exp, exposure_us))
                
                self.cam.ExposureTime.SetValue(exposure_us)
                return True
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Failed to set exposure: {e}")
        return False

    def get_exposure_time(self) -> Optional[float]:
        """Get current exposure time in microseconds."""
        try:
            if PySpin.IsReadable(self.cam.ExposureTime):
                return self.cam.ExposureTime.GetValue()
        except PySpin.SpinnakerException:
            pass
        return None

    def set_gain(self, gain_db: float) -> bool:
        """Set gain in dB."""
        try:
            if PySpin.IsWritable(self.cam.Gain):
                # Ensure auto gain is off
                if PySpin.IsWritable(self.cam.GainAuto):
                    self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
                
                min_gain = self.cam.Gain.GetMin()
                max_gain = self.cam.Gain.GetMax()
                gain_db = max(min_gain, min(max_gain, gain_db))
                
                self.cam.Gain.SetValue(gain_db)
                return True
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Failed to set gain: {e}")
        return False

    def get_gain(self) -> Optional[float]:
        """Get current gain in dB."""
        try:
            if PySpin.IsReadable(self.cam.Gain):
                return self.cam.Gain.GetValue()
        except PySpin.SpinnakerException:
            pass
        return None

    def set_auto_exposure(self, enabled: bool) -> bool:
        """Enable/disable auto exposure."""
        try:
            if PySpin.IsWritable(self.cam.ExposureAuto):
                mode = PySpin.ExposureAuto_Continuous if enabled else PySpin.ExposureAuto_Off
                self.cam.ExposureAuto.SetValue(mode)
                return True
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Failed to set auto exposure: {e}")
        return False

    def get_auto_exposure(self) -> bool:
        """Get auto exposure status."""
        try:
            if PySpin.IsReadable(self.cam.ExposureAuto):
                return self.cam.ExposureAuto.GetValue() == PySpin.ExposureAuto_Continuous
        except PySpin.SpinnakerException:
            pass
        return False

    def get_camera_info(self) -> Dict[str, Any]:
        """Get comprehensive camera information."""
        info = {
            'index': self.index,
            'serial': self.serial,
            'model': self.model,
            'state': self.state.value,
            'last_error': self.last_error
        }
        
        if self.state in [CameraState.CONNECTED, CameraState.ACQUIRING]:
            try:
                # Image dimensions
                if PySpin.IsReadable(self.cam.Width):
                    info['width'] = self.cam.Width.GetValue()
                if PySpin.IsReadable(self.cam.Height):
                    info['height'] = self.cam.Height.GetValue()
                
                # Frame rate
                if PySpin.IsReadable(self.cam.AcquisitionFrameRate):
                    info['frame_rate'] = self.cam.AcquisitionFrameRate.GetValue()
                
                # Exposure
                info['exposure_time'] = self.get_exposure_time()
                info['auto_exposure'] = self.get_auto_exposure()
                
                # Gain
                info['gain'] = self.get_gain()
                
                # Pixel format
                if PySpin.IsReadable(self.cam.PixelFormat):
                    info['pixel_format'] = self.cam.PixelFormat.GetCurrentEntry().GetSymbolic()
                
            except PySpin.SpinnakerException as e:
                info['info_error'] = str(e)
        
        return info

    def start_acquisition(self) -> bool:
        """Start image acquisition."""
        if self.state != CameraState.CONNECTED:
            return False
        
        try:
            self.cam.BeginAcquisition()
            self.state = CameraState.ACQUIRING
            logging.info(f"[Cam {self.index}] Acquisition started.")
            return True
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Failed to start acquisition: {e}")
            self.last_error = str(e)
            self.state = CameraState.ERROR
            return False

    def stop_acquisition(self) -> bool:
        """Stop image acquisition."""
        if self.state != CameraState.ACQUIRING:
            return True
        
        try:
            self.cam.EndAcquisition()
            self.state = CameraState.CONNECTED
            logging.info(f"[Cam {self.index}] Acquisition stopped.")
            return True
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Failed to stop acquisition: {e}")
            self.last_error = str(e)
            return False

    def get_image(self, timeout: int = 1000) -> Optional[np.ndarray]:
        """Get the next image from the camera."""
        if self.state != CameraState.ACQUIRING:
            return None
        
        try:
            image_result = self.cam.GetNextImage(timeout)
            if image_result.IsIncomplete():
                image_result.Release()
                return None
            
            image_data = np.copy(image_result.GetNDArray())
            image_result.Release()
            return image_data
            
        except PySpin.SpinnakerException:
            return None

    def cleanup(self):
        """Clean up camera resources."""
        try:
            if self.state == CameraState.ACQUIRING:
                self.stop_acquisition()
            
            if self.cam.IsInitialized():
                self.cam.DeInit()
            
            self.state = CameraState.DISCONNECTED
            logging.info(f"[Cam {self.index}] Cleaned up.")
            
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Cleanup error: {e}")

class CameraManager:
    """Enhanced camera manager with better error handling and diagnostics."""
    
    def __init__(self):
        self.system: PySpin.System = PySpin.System.GetInstance()
        self.cameras: Dict[int, FLIRCamera] = {}
        self.camera_list: Optional[PySpin.CameraList] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def discover_cameras(self) -> List[Tuple[int, str, str]]:
        """Discover available cameras. Returns list of (index, serial, model)."""
        try:
            self.camera_list = self.system.GetCameras()
            num_cameras = self.camera_list.GetSize()
            
            if num_cameras == 0:
                logging.warning("No cameras detected.")
                return []
            
            discovered = []
            for i in range(num_cameras):
                try:
                    cam = self.camera_list.GetByIndex(i)
                    nodemap = cam.GetTLDeviceNodeMap()
                    
                    serial_node = PySpin.CStringPtr(nodemap.GetNode('DeviceSerialNumber'))
                    serial = serial_node.GetValue() if PySpin.IsReadable(serial_node) else f"UNKNOWN_{i}"
                    
                    model_node = PySpin.CStringPtr(nodemap.GetNode('DeviceModelName'))
                    model = model_node.GetValue() if PySpin.IsReadable(model_node) else "Unknown Model"
                    
                    discovered.append((i, serial, model))
                    
                except PySpin.SpinnakerException as e:
                    logging.error(f"Error accessing camera {i}: {e}")
                    discovered.append((i, f"ERROR_{i}", "Error"))
            
            return discovered
            
        except PySpin.SpinnakerException as e:
            logging.error(f"Camera discovery failed: {e}")
            return []

    def connect_all(self) -> bool:
        """Connect to all discovered cameras."""
        self.disconnect_all()
        discovered = self.discover_cameras()
        
        if not discovered:
            return False

        success_count = 0
        for index, serial, model in discovered:
            try:
                pyspin_cam = self.camera_list.GetByIndex(index)
                flir_cam = FLIRCamera(pyspin_cam, index)
                
                if flir_cam.is_connected:
                    self.cameras[index] = flir_cam
                    success_count += 1
                    logging.info(f"Successfully connected to camera {index} ({model}, SN: {serial}).")
                else:
                    logging.error(f"Failed to initialize camera {index}")
                    
            except Exception as e:
                logging.error(f"Failed to connect to camera {index}: {e}")
        
        return success_count > 0

    def configure_all(self, resolution: str, frame_rate: float) -> int:
        """Configure all cameras. Returns number of successfully configured cameras."""
        success_count = 0
        for cam in self.cameras.values():
            if cam.configure(resolution, frame_rate):
                success_count += 1
        return success_count

    def start_all_acquisition(self) -> int:
        """Start acquisition on all cameras. Returns number of successfully started cameras."""
        success_count = 0
        for cam in self.cameras.values():
            if cam.start_acquisition():
                success_count += 1
        return success_count

    def stop_all_acquisition(self) -> int:
        """Stop acquisition on all cameras. Returns number of successfully stopped cameras."""
        success_count = 0
        for cam in self.cameras.values():
            if cam.stop_acquisition():
                success_count += 1
        return success_count
            
    def disconnect_all(self):
        """Disconnect all cameras."""
        self.stop_all_acquisition()
        
        for index in list(self.cameras.keys()):
            self.cameras[index].cleanup()
        
        self.cameras.clear()
        gc.collect()
        logging.info("All cameras disconnected.")

    def get_system_info(self) -> Dict[str, Any]:
        """Get PySpin system information."""
        try:
            library_version = self.system.GetLibraryVersion()
            return {
                'spinnaker_version': f"{library_version.major}.{library_version.minor}.{library_version.type}.{library_version.build}",
                'num_cameras': len(self.cameras),
                'connected_cameras': [cam.serial for cam in self.cameras.values() if cam.is_connected]
            }
        except Exception as e:
            return {'error': str(e)}

    def cleanup(self):
        """Clean up camera manager resources."""
        self.disconnect_all()
        
        if self.camera_list:
            self.camera_list.Clear()
        
        self.system.ReleaseInstance()
        logging.info("Camera manager cleaned up.")