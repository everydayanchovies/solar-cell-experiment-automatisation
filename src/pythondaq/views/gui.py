import sys

import numpy as np
from PyQt5 import QtWidgets, uic
import pyqtgraph as pg
import pkg_resources
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator

from pythondaq.models.diode_experiment import DiodeExperiment


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        pg.setConfigOption("background", 'w')
        pg.setConfigOption("foreground", 'b')

        ui = pkg_resources.resource_stream("pythondaq.views.ui", "diode.ui")
        uic.loadUi(ui, self)

        float_only_regex = QRegExp("[+-]?([0-9]*[.])?[0-9]+")
        self.u_start_ib.setValidator(QRegExpValidator(float_only_regex))
        self.u_end_ib.setValidator(QRegExpValidator(float_only_regex))

        int_only_regex = QRegExp("\\d+")
        self.num_samples_ib.setValidator(QRegExpValidator(int_only_regex))
        self.repeat_ib.setValidator(QRegExpValidator(int_only_regex))

        self.scan_btn.clicked.connect(self.perform_scan)

    def perform_scan(self):
        m = DiodeExperiment("ASRL::SIMLED::INSTR")

        start = float(self.u_start_ib.text() or 0.0)
        if not start:
            start = 0.0
            self.u_start_ib.setText(str(start))

        end = float(self.u_end_ib.text() or 0.0)
        if not end:
            end = 3.2
            self.u_end_ib.setText(str(end))

        num_samples = int(self.num_samples_ib.text() or 0)
        if not num_samples:
            num_samples = 10
            self.num_samples_ib.setText(str(num_samples))

        step_size = (end - start) / num_samples

        repeat = int(self.repeat_ib.text() or 0)
        if not repeat:
            repeat = 2
            self.repeat_ib.setText(str(repeat))

        print(start, end, step_size, repeat)

        rows = []
        for ((u, u_err), (i, i_err)) in m.scan_led(start, end, step_size, repeat):
            rows.append((u, u_err, i, i_err))

        self.plot_widget.clear()
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
