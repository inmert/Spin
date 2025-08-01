# camera_core.py
"""
Core module for FLIR camera interaction using PySpin.
This module is designed to be independent of the user interface.
"""
import time
import logging
import gc
from typing import Optional, Dict, List, Tuple

import numpy as np
import PySpin

from config import RESOLUTION_PRESETS

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CameraError(Exception):
    """Custom exception for camera-related errors."""
    pass

class FLIRCamera:
    """A wrapper for a single PySpin Camera object."""

    def __init__(self, pyspin_cam_obj, index: int):
        self.cam: PySpin.CameraPtr = pyspin_cam_obj
        self.index = index
        self.is_acquiring = False
        self.cam.Init()
        serial_node = PySpin.CStringPtr(self.cam.GetTLDeviceNodeMap().GetNode('DeviceSerialNumber'))
        self.serial = serial_node.GetValue() if PySpin.IsReadable(serial_node) else f"UNKNOWN_{index}"

    def configure(self, resolution: str = 'HD', frame_rate: float = 30.0) -> bool:
        """Configures camera resolution and frame rate."""
        if self.is_acquiring:
            logging.warning(f"[Cam {self.index}] Cannot configure while acquiring images.")
            return False
        try:
            self.cam.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
            if resolution in RESOLUTION_PRESETS:
                width, height = RESOLUTION_PRESETS[resolution]
                self.cam.Width.SetValue(width)
                self.cam.Height.SetValue(height)

            self.cam.AcquisitionFrameRateEnable.SetValue(True)
            self.cam.AcquisitionFrameRate.SetValue(frame_rate)
            s_node_map = self.cam.GetTLStreamNodeMap()
            handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode('StreamBufferHandlingMode'))
            handling_mode.SetIntValue(PySpin.CEnumEntryPtr(handling_mode.GetEntryByName('NewestOnly')).GetValue())

            logging.info(f"[Cam {self.index}] Configured to {resolution} @ {frame_rate}fps.")
            return True
        except PySpin.SpinnakerException as e:
            logging.error(f"[Cam {self.index}] Configuration failed: {e}")
            return False

    def start_acquisition(self):
        if not self.is_acquiring:
            self.cam.BeginAcquisition()
            self.is_acquiring = True
            logging.info(f"[Cam {self.index}] Acquisition started.")

    def stop_acquisition(self):
        if self.is_acquiring:
            self.cam.EndAcquisition()
            self.is_acquiring = False
            logging.info(f"[Cam {self.index}] Acquisition stopped.")

    def get_image(self, timeout: int = 1000) -> Optional[np.ndarray]:
        if not self.is_acquiring: return None
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
        self.stop_acquisition()
        if self.cam.IsInitialized():
            self.cam.DeInit()
        logging.info(f"[Cam {self.index}] Cleaned up.")

class CameraManager:
    """Manages system-level camera discovery and connections."""
    
    def __init__(self):
        self.system: PySpin.System = PySpin.System.GetInstance()
        self.cameras: Dict[int, FLIRCamera] = {}
        self.camera_list: Optional[PySpin.CameraList] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def discover_cameras(self) -> List[Tuple[int, str]]:
        self.camera_list = self.system.GetCameras()
        num_cameras = self.camera_list.GetSize()
        if num_cameras == 0:
            logging.warning("No cameras detected.")
            return []
        
        discovered = []
        for i in range(num_cameras):
            cam = self.camera_list.GetByIndex(i)
            serial_node = PySpin.CStringPtr(cam.GetTLDeviceNodeMap().GetNode('DeviceSerialNumber'))
            serial = serial_node.GetValue() if PySpin.IsReadable(serial_node) else f"UNKNOWN_{i}"
            discovered.append((i, serial))
        return discovered

    def connect_all(self) -> bool:
        """Connects to all discovered cameras."""
        self.disconnect_all()
        discovered = self.discover_cameras()
        if not discovered: return False

        for index, serial in discovered:
            try:
                pyspin_cam = self.camera_list.GetByIndex(index)
                flir_cam = FLIRCamera(pyspin_cam, index)
                self.cameras[index] = flir_cam
                logging.info(f"Successfully connected to camera {index} (SN: {serial}).")
            except PySpin.SpinnakerException as e:
                logging.error(f"Failed to connect to camera {index}: {e}")
        return len(self.cameras) > 0

    def configure_all(self, resolution: str, frame_rate: float):
        for cam in self.cameras.values():
            cam.configure(resolution, frame_rate)

    def start_all_acquisition(self):
        for cam in self.cameras.values():
            cam.start_acquisition()

    def stop_all_acquisition(self):
        for cam in self.cameras.values():
            cam.stop_acquisition()
            
    def disconnect_all(self):
        """Disconnects all cameras."""
        self.stop_all_acquisition()
        for index in list(self.cameras.keys()):
            self.cameras[index].cleanup()
        self.cameras.clear()
        gc.collect()
        logging.info("All cameras disconnected.")

    def cleanup(self):
        self.disconnect_all()
        if self.camera_list:
            self.camera_list.Clear()
        self.system.ReleaseInstance()
        logging.info("Camera manager cleaned up.")