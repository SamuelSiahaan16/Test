import sys
from PySide6.QtWidgets import QApplication
from app.gui.main_window import Window
from app.core.runner import Runner
from app.utils.validators import video_id, parse_views, short_target, ended_success

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
