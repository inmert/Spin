# main.py
"""Main entry point for the FLIR Camera Control application."""
import tkinter as tk
from camera_core import CameraManager
from app_gui import CameraAppGUI

def main():
    """Initializes the camera manager and GUI, then runs the app."""
    try:
        # The CameraManager is created within a 'with' block to ensure
        # that its cleanup method is called automatically on exit,
        # even if errors occur.
        with CameraManager() as manager:
            root = tk.Tk()
            app = CameraAppGUI(root, manager)
            root.mainloop()

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Application has been shut down.")

if __name__ == "__main__":
    main()