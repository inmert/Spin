# main.py
"""
Main entry point for the enhanced FLIR Camera Control application using PyQt6.
"""
import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# Import our application modules
from app_gui import MainCameraGUI
from config import ConfigManager

def setup_logging():
    """Setup application logging."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / "camera_app.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def check_dependencies():
    """Check if all required dependencies are available."""
    missing_deps = []
    
    try:
        import PySpin
    except ImportError:
        missing_deps.append("PySpin (Spinnaker SDK)")
    
    try:
        import cv2
    except ImportError:
        missing_deps.append("OpenCV (cv2)")
    
    try:
        import numpy
    except ImportError:
        missing_deps.append("NumPy")
    
    try:
        import psutil
    except ImportError:
        missing_deps.append("psutil")
    
    if missing_deps:
        error_msg = "Missing required dependencies:\n" + "\n".join(f"- {dep}" for dep in missing_deps)
        error_msg += "\n\nPlease install the missing packages and try again."
        return False, error_msg
    
    return True, ""

def main():
    """Main application entry point."""
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting FLIR Camera Control application")
    
    # Check dependencies
    deps_ok, error_msg = check_dependencies()
    if not deps_ok:
        print(f"Dependency Error: {error_msg}")
        return 1
    
    try:
        # Create QApplication
        app = QApplication(sys.argv)
        
        # Set application properties
        app.setApplicationName("FLIR Camera Control Enhanced")
        app.setApplicationVersion("2.0.0")
        app.setOrganizationName("Camera Control Solutions")
        app.setOrganizationDomain("cameracontrol.com")
        
        # Enable high DPI scaling (PyQt6 compatible way)
        try:
            # For PyQt6 6.0+, high DPI is enabled by default
            # Only set if the attribute exists (older versions)
            if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
                app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
            if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
                app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        except AttributeError:
            # These attributes don't exist in newer PyQt6 versions
            # High DPI scaling is enabled by default
            pass
        
        # Load and apply theme from config
        config_manager = ConfigManager()
        gui_settings = config_manager.get_gui_settings()
        
        if gui_settings.theme == "dark":
            # Apply dark theme
            dark_style = """
            QWidget {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QMainWindow {
                background-color: #2b2b2b;
            }
            QMenuBar {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background-color: #555555;
            }
            QMenu {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
            }
            QMenu::item:selected {
                background-color: #555555;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 4px;
                border-radius: 3px;
            }
            QGroupBox {
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #404040;
                border: 1px solid #555555;
                padding: 6px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #2b2b2b;
                border-bottom: 1px solid #2b2b2b;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 8px;
                background: #404040;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #888888;
                border: 1px solid #555555;
                width: 18px;
                margin: -2px 0;
                border-radius: 3px;
            }
            QTreeWidget {
                background-color: #404040;
                alternate-background-color: #505050;
                border: 1px solid #555555;
            }
            QListWidget {
                background-color: #404040;
                alternate-background-color: #505050;
                border: 1px solid #555555;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 3px;
                text-align: center;
                background-color: #404040;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            QStatusBar {
                background-color: #3c3c3c;
                border-top: 1px solid #555555;
            }
            """
            app.setStyleSheet(dark_style)
        
        # Create and show main window
        logger.info("Creating main window")
        window = MainCameraGUI()
        window.show()
        
        logger.info("Application started successfully")
        
        # Run the application
        return app.exec()
        
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        
        # Show error dialog if possible
        try:
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Icon.Critical)
            error_box.setWindowTitle("Application Error")
            error_box.setText("An unexpected error occurred:")
            error_box.setDetailedText(str(e))
            error_box.exec()
        except:
            print(f"Critical error: {e}")
        
        return 1
    
    finally:
        logger.info("Application shutting down")

if __name__ == "__main__":
    sys.exit(main())