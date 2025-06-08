import sys
from PyQt5.QtWidgets import QApplication
from main_window import MainWindow

def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start event loop
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()