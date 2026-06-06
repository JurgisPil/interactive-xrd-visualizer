import sys
from PyQt6.QtWidgets import QApplication
from gui import XRDGui

def main():
    app = QApplication(sys.argv)
    
    # Set dark theme for a modern look
    app.setStyle("Fusion")
    
    window = XRDGui()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
