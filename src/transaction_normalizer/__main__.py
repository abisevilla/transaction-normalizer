import sys
from PySide6.QtWidgets import QApplication
from .ui.window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Normalizador de transacciones")
    app.setStyle("Fusion")
    window = MainWindow(autoload=True)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
