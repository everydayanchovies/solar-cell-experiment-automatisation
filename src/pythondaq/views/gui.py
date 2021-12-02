import sys

from PyQt5 import QtWidgets, uic
import pyqtgraph as pg
import pkg_resources


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        ui = pkg_resources.resource_stream("pythondaq.views.ui", "diode.ui")
        uic.loadUi(ui, self)


def main():
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
