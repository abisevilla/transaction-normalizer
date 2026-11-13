COLORS = {"surface": "#FFFFFF", "primary": "#4F46E5", "muted": "#64748B", "background": "#F8FAFC", "success": "#16A34A"}
STYLE = """
QMainWindow, QWidget#central { background: #F8FAFC; color: #182235; }
QLabel#title { font-size: 24px; font-weight: 700; }
QLabel#metrics { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; padding: 16px; font-size: 14px; }
QPushButton { background: #4F46E5; color: #FFFFFF; padding: 9px 14px; border-radius: 5px; }
QPushButton:disabled { background: #64748B; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus { border: 2px solid #4F46E5; }
QLineEdit, QComboBox { padding: 7px; background: #FFFFFF; color: #182235; border: 1px solid #64748B; border-radius: 4px; }
QComboBox:disabled { color: #64748B; background: #F1F5F9; }
QTableView, QPlainTextEdit { background: #FFFFFF; color: #182235; selection-background-color: #4F46E5; selection-color: #FFFFFF; }
QHeaderView::section { padding: 9px; background: #EEF2FF; color: #182235; border: 0; }
QLabel#success { color: #16A34A; font-size: 20px; font-weight: 700; }
"""
