import sys
import threading

import numpy as np
from PyQt5 import QtWidgets, uic, QtCore
import pyqtgraph as pg
import pkg_resources
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
from pyvisa import VisaIOError
from serial import SerialException

from pythondaq.models.diode_experiment import DiodeExperiment, save_data_to_csv, list_devices


class UserInterface(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        pg.setConfigOption("background", 'w')
        pg.setConfigOption("foreground", 'b')

        ui = pkg_resources.resource_stream("pythondaq.views.ui", "diode.ui")
        uic.loadUi(ui, self)

        self.devices_cb.addItems(list_devices())

        float_only_regex = QRegExp("[+-]?([0-9]*[.])?[0-9]+")
        self.u_start_ib.setValidator(QRegExpValidator(float_only_regex))
        self.u_end_ib.setValidator(QRegExpValidator(float_only_regex))

        int_only_regex = QRegExp("\\d+")
        self.num_samples_ib.setValidator(QRegExpValidator(int_only_regex))
        self.repeat_ib.setValidator(QRegExpValidator(int_only_regex))

        self.scan_btn.clicked.connect(self.perform_scan)
        self.save_btn.clicked.connect(self.save)

    def perform_scan(self):
        start = float(self.u_start_ib.text() or 0.0)
        if not start:
            start = 0.1
            self.u_start_ib.setText(str(start))

        end = float(self.u_end_ib.text() or 0.0)
        if not end:
            end = 3.2
            self.u_end_ib.setText(str(end))

        num_samples = int(self.num_samples_ib.text() or 0)
        if not num_samples:
            num_samples = 10
            self.num_samples_ib.setText(str(num_samples))

        repeat = int(self.repeat_ib.text() or 0)
        if not repeat:
            repeat = 2
            self.repeat_ib.setText(str(repeat))

        port = self.devices_cb.currentText()
        exp = Experiment()

        error = None

        def on_error(e):
            nonlocal error
            error = e

        self.scan_btn.setEnabled(False)

        e_scanning = threading.Event()
        exp.start_scan(port, start, end, num_samples, repeat, e_scanning, on_error)

        plot_timer = QtCore.QTimer()

        def update_plot():
            nonlocal plot_timer, error
            self.plot(exp.rows)
            if not e_scanning.is_set():
                plot_timer.stop()
                self.scan_btn.setEnabled(True)
            if error:
                plot_timer.stop()
                self.scan_btn.setEnabled(True)
                d = QtWidgets.QMessageBox()
                d.setIcon(QtWidgets.QMessageBox.Warning)
                d.setText("Error occurred while taking measurement")
                d.setInformativeText("Try selecting another device.")
                d.setDetailedText(str(error))
                d.setStandardButtons(QtWidgets.QMessageBox.Ok)
                d.exec_()

        plot_timer.timeout.connect(update_plot)
        plot_timer.start(100)

    def plot(self, rows: list[(float, float)]):
        self.plot_widget.clear()
        self.plot_widget.plot([u for (u, _, _, _) in rows], [i for (_, _, i, _) in rows],
                              symbol='o', symbolSize=5, pen=None)
        self.plot_widget.setLabel("left", "I (A)")
        self.plot_widget.setLabel("bottom", "U (V)")

    def save(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(filter="CSV files (*.csv)")

        save_data_to_csv(filepath, ["U", "U_err", "I", "I_err"], self.rows)


class Experiment:
    def __init__(self):
        self.rows = []
        self._scan_thread = None

    def scan(self, port: str, start: float, end: float, steps: int, repeat: int,
             e_scanning: threading.Event = None, on_error=None):
        e_scanning.set()

        self.rows = []
        try:
            with DiodeExperiment(port) as m:
                step_size = (end - start) / steps
                for ((u, u_err), (i, i_err)) in m.scan_led(start, end, step_size, repeat):
                    self.rows.append((u, u_err, i, i_err))
        except (VisaIOError, SerialException) as e:
            on_error(e)

        e_scanning.clear()

    def start_scan(self, port: str, start: float, end: float, steps: int, repeat: int,
                   e_scanning: threading.Event = None, on_error=None):
        self._scan_thread = threading.Thread(
            target=self.scan, args=(port, start, end, steps, repeat, e_scanning, on_error)
        )
        self._scan_thread.start()

    def join_scan_thread(self):
        self._scan_thread.join()


def main():
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
