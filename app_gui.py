# app_gui.py
"""
GUI for the FLIR Camera Controller application using Tkinter.
Supports multi-camera view and digital zoom.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional
from PIL import Image, ImageTk
import numpy as np
import cv2
import time
from functools import partial

from camera_core import CameraManager
from config import RESOLUTION_PRESETS, DEFAULT_SETTINGS, GUI_UPDATE_MS

class CameraAppGUI:
    def __init__(self, root: tk.Tk, manager: CameraManager):
        self.root = root
        self.manager = manager
        
        # State Management
        self.video_labels: Dict[int, ttk.Label] = {}
        self.zoom_levels: Dict[int, float] = {}
        self.selected_feed_index: Optional[int] = None
        
        self.root.title("FLIR Multi-Camera Control")
        self.root.geometry("1280x720")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Variables
        self.resolution_selection = tk.StringVar(value=DEFAULT_SETTINGS['resolution'])
        self.framerate_var = tk.StringVar(value=str(DEFAULT_SETTINGS['frame_rate']))
        
        self._create_widgets()
        self._update_video_feed()

    def _create_widgets(self):
        # Main layout
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Left-side control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        main_frame.grid_rowconfigure(0, weight=1)

        # Right-side video panel
        self.video_frame = ttk.Frame(main_frame)
        self.video_frame.grid(row=0, column=1, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)

        # --- Control Widgets ---
        row = 0
        # Connection
        ttk.Button(control_frame, text="Connect All Cameras", command=self._connect_all).grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1
        ttk.Button(control_frame, text="Disconnect All", command=self._disconnect_all).grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        
        # Settings
        row += 1
        ttk.Label(control_frame, text="Resolution:").grid(row=row, column=0, sticky="w")
        res_dropdown = ttk.Combobox(control_frame, textvariable=self.resolution_selection, values=list(RESOLUTION_PRESETS.keys()), state="readonly")
        res_dropdown.grid(row=row, column=1, sticky="ew", pady=2)
        
        row += 1
        ttk.Label(control_frame, text="Frame Rate:").grid(row=row, column=0, sticky="w")
        ttk.Entry(control_frame, textvariable=self.framerate_var).grid(row=row, column=1, sticky="ew", pady=2)
        
        row += 1
        ttk.Button(control_frame, text="Apply Settings to All", command=self._apply_settings).grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        
        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)

        # Acquisition
        row += 1
        ttk.Button(control_frame, text="Start All Streams", command=self._start_all).grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Button(control_frame, text="Stop All Streams", command=self._stop_all).grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
        row += 1
        ttk.Button(control_frame, text="Save All Snapshots", command=self._save_all_snapshots).grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)

        row += 1
        ttk.Separator(control_frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)

        # Zoom Controls
        row += 1
        self.zoom_label = ttk.Label(control_frame, text="Zoom: (select a feed)")
        self.zoom_label.grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        ttk.Button(control_frame, text="Zoom In (+)", command=self._zoom_in).grid(row=row, column=0, sticky="ew")
        ttk.Button(control_frame, text="Zoom Out (-)", command=self._zoom_out).grid(row=row, column=1, sticky="ew")

    def _connect_all(self):
        if self.manager.connect_all():
            self._recreate_video_grid()
            messagebox.showinfo("Success", f"Connected to {len(self.manager.cameras)} camera(s).")
        else:
            messagebox.showwarning("Warning", "No cameras found or failed to connect.")

    def _disconnect_all(self):
        self.manager.disconnect_all()
        self._recreate_video_grid() # This will clear the grid
        self.selected_feed_index = None
        self.zoom_levels.clear()
        self.zoom_label.config(text="Zoom: (select a feed)")

    def _recreate_video_grid(self):
        # Clear existing video labels
        for widget in self.video_frame.winfo_children():
            widget.destroy()
        self.video_labels.clear()

        # Determine grid size (e.g., 2 columns)
        num_cams = len(self.manager.cameras)
        if num_cams == 0: return
        cols = 2 if num_cams > 1 else 1
        
        # Create a new grid of video labels
        for i, (cam_index, cam) in enumerate(self.manager.cameras.items()):
            row, col = divmod(i, cols)
            
            label_frame = ttk.LabelFrame(self.video_frame, text=f"Camera {cam_index}: {cam.serial}")
            label_frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            self.video_frame.grid_rowconfigure(row, weight=1)
            self.video_frame.grid_columnconfigure(col, weight=1)

            video_label = ttk.Label(label_frame, anchor="center")
            video_label.pack(fill="both", expand=True)
            
            # Bind click event for zoom selection
            click_handler = partial(self._on_feed_click, cam_index, label_frame)
            label_frame.bind("<Button-1>", click_handler)
            video_label.bind("<Button-1>", click_handler)

            self.video_labels[cam_index] = label_frame
            self.zoom_levels[cam_index] = 1.0 # Default zoom

    def _apply_settings(self):
        if not self.manager.cameras:
            messagebox.showwarning("Warning", "No cameras connected.")
            return
        
        is_any_acquiring = any(cam.is_acquiring for cam in self.manager.cameras.values())
        if is_any_acquiring:
            messagebox.showerror("Error", "Stop all streams before changing settings.")
            return
            
        try:
            resolution = self.resolution_selection.get()
            frame_rate = float(self.framerate_var.get())
            self.manager.configure_all(resolution, frame_rate)
        except ValueError:
            messagebox.showerror("Settings Error", "Invalid frame rate value.")

    def _start_all(self): self.manager.start_all_acquisition()
    def _stop_all(self): self.manager.stop_all_acquisition()
    
    def _update_video_feed(self):
        """Periodically gets an image from all cameras and updates the GUI."""
        for cam_index, cam in self.manager.cameras.items():
            if not cam.is_acquiring:
                continue

            img_np = cam.get_image()
            if img_np is not None:
                # 1. Apply digital zoom by cropping the numpy array
                zoom = self.zoom_levels.get(cam_index, 1.0)
                if zoom > 1.0:
                    h, w = img_np.shape[:2]
                    crop_w, crop_h = int(w / zoom), int(h / zoom)
                    mid_x, mid_y = w // 2, h // 2
                    x1, x2 = mid_x - crop_w // 2, mid_x + crop_w // 2
                    y1, y2 = mid_y - crop_h // 2, mid_y + crop_h // 2
                    img_np = img_np[y1:y2, x1:x2]

                # 2. Convert to PIL Image
                img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB if len(img_np.shape) > 2 else cv2.COLOR_GRAY2RGB)
                img_pil = Image.fromarray(img_rgb)

                # 3. Resize to fit the exact widget size to prevent layout changes
                label_frame = self.video_labels[cam_index]
                widget_w = label_frame.winfo_width()
                widget_h = label_frame.winfo_height()

                if widget_w > 1 and widget_h > 1:
                    # Use resize() instead of thumbnail() for fixed output dimensions
                    img_pil = img_pil.resize((widget_w, widget_h), Image.LANCZOS)
                    
                    img_tk = ImageTk.PhotoImage(image=img_pil)
                    video_label = label_frame.winfo_children()[0]
                    video_label.config(image=img_tk)
                    video_label.image = img_tk  # Keep a reference

        self.root.after(GUI_UPDATE_MS, self._update_video_feed)

    def _on_feed_click(self, cam_index, label_frame, event):
        """Handles user clicking on a video feed to select it for zoom."""
        # Reset border on old selection
        if self.selected_feed_index is not None and self.selected_feed_index in self.video_labels:
            self.video_labels[self.selected_feed_index].config(style="TLabelframe")

        # Set new selection
        self.selected_feed_index = cam_index
        
        # Apply border to new selection
        style = ttk.Style()
        style.configure("Selected.TLabelframe", bordercolor="blue", borderwidth=3)
        label_frame.config(style="Selected.TLabelframe")

        zoom = self.zoom_levels.get(cam_index, 1.0)
        self.zoom_label.config(text=f"Zoom Cam {cam_index}: {zoom:.1f}x")

    def _zoom_in(self):
        if self.selected_feed_index is not None:
            self.zoom_levels[self.selected_feed_index] = min(5.0, self.zoom_levels[self.selected_feed_index] + 0.2)
            zoom = self.zoom_levels[self.selected_feed_index]
            self.zoom_label.config(text=f"Zoom Cam {self.selected_feed_index}: {zoom:.1f}x")

    def _zoom_out(self):
        if self.selected_feed_index is not None:
            self.zoom_levels[self.selected_feed_index] = max(1.0, self.zoom_levels[self.selected_feed_index] - 0.2)
            zoom = self.zoom_levels[self.selected_feed_index]
            self.zoom_label.config(text=f"Zoom Cam {self.selected_feed_index}: {zoom:.1f}x")

    def _save_all_snapshots(self):
        timestamp = int(time.time())
        saved_count = 0
        for idx, cam in self.manager.cameras.items():
            if cam.is_acquiring:
                img = cam.get_image()
                if img is not None:
                    filename = f"snapshot_cam{idx}_{timestamp}.png"
                    cv2.imwrite(filename, img)
                    saved_count += 1
        messagebox.showinfo("Saved", f"Saved {saved_count} snapshot(s).")
    
    def _on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit? This will disconnect all cameras."):
            self.manager.cleanup()
            self.root.destroy()