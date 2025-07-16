from PyQt5.QtCore import QFile, pyqtSignal, QTextStream, Qt, QIODevice
from PyQt5.QtWidgets import QMainWindow, QDialog, QFontDialog, QApplication, QFileDialog, QColorDialog
import sys
import os.path

# Import your Laced Column class
from .design_type.compression_member.laced_column import LacedColumn
from .gui.ui_template import Ui_ModuleWindow

class MainController(QMainWindow):
    closed = pyqtSignal()
    
    def __init__(self, Ui_ModuleWindow, main, folder):
        super(MainController, self).__init__()
        QMainWindow.__init__(self)
        self.ui = Ui_ModuleWindow()
        self.ui.setupUi(self, main)  # 'main' is now LacedColumn
        self.folder = folder

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Use a path that exists on the current user's system
    folder_path = os.path.join(os.path.expanduser('~'), 'Desktop', 'OsdagWorkspace')
    if not os.path.exists(folder_path):
        os.mkdir(folder_path, 0o755)

    image_folder_path = os.path.join(folder_path, 'images_html')
    if not os.path.exists(image_folder_path):
        os.mkdir(image_folder_path, 0o755)

    # Replace FinPlateConnection with LacedColumn
    window = MainController(Ui_ModuleWindow, LacedColumn(), folder_path)
    window.setWindowTitle("Laced Column")
    window.show()

    try:
        sys.exit(app.exec_())
    except:
        print("ERROR")
