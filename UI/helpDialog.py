from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt
from UI import help


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent=parent)
        self.setWindowTitle("About")

        self.ui = help.Ui_Dialog()
        self.ui.setupUi(self)

    def exec(self) -> int:
        return super().exec()
