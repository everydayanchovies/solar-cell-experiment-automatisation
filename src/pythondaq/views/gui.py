import sys

import numpy as np
from PyQt5 import QtWidgets, uic
import pyqtgraph as pg
import pkg_resources

from pythondaq.models.diode_experiment import DiodeExperiment


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        pg.setConfigOption("background", 'w')
        pg.setConfigOption("foreground", 'b')

        ui = pkg_resources.resource_stream("pythondaq.views.ui", "diode.ui")
        uic.loadUi(ui, self)

        self.scan_btn.clicked.connect(self.perform_scan)

    def perform_scan(self):
        m = DiodeExperiment("ASRL::SIMLED::INSTR")

        rows = []
        for ((u, u_err), (i, i_err)) in m.scan_led(0.0, 3.2, 0.1, 2):
            rows.append((u, u_err, i, i_err))

        self.plot_widget.plot([u for (u, _, _, _) in rows], [i for (_, _, i, _) in rows],
                              symbol=None, pen={"color": 'k', "width": 5})
        self.plot_widget.setLabel("left", "I (A)")
        self.plot_widget.setLabel("bottom", "U (V)")


def main():
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
