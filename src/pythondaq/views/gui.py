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
    """UserInterface is responsible for rendering the UI and handling input events.
    """

    def __init__(self):
        super().__init__()

        # set plot colours
        pg.setConfigOption("background", 'w')
        pg.setConfigOption("foreground", 'b')

        # load UI from file
        ui = pkg_resources.resource_stream("pythondaq.views.ui", "diode.ui")
        uic.loadUi(ui, self)

        # init the devices combo box
        self.devices_cb.addItems(list_devices())

        # init the start and end input boxes, limit input to floats
        float_only_regex = QRegExp("[+-]?([0-9]*[.])?[0-9]+")
        self.u_start_ib.setValidator(QRegExpValidator(float_only_regex))
        self.u_end_ib.setValidator(QRegExpValidator(float_only_regex))

        # init the samples and repeat input boxes, limit to integers
        int_only_regex = QRegExp("\\d+")
        self.num_samples_ib.setValidator(QRegExpValidator(int_only_regex))
        self.repeat_ib.setValidator(QRegExpValidator(int_only_regex))

        # couple the buttons to their functions
        self.scan_btn.clicked.connect(self.perform_scan)
        self.save_btn.clicked.connect(self.save)

        # init a timer for reading the measurements
        self.plot_timer = QtCore.QTimer()
        # define a variable to carry errors across threads
        self.plot_error = None
        # define an event that triggers when the scan is finished
        self.e_scanning = threading.Event()
        # init the experiment class to an object
        self.exp = Experiment()

    def perform_scan(self):
        """
        Takes a series of measurements of the current through and voltage across the LED.
        """
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

        def on_error(e):
            """
            Carries the error from the scan thread to the GUI thread.
            :param e: the error
            """
            self.plot_error = e

        self.scan_btn.setEnabled(False)

        port = self.devices_cb.currentText()
        self.exp.start_scan(port, start, end, num_samples, repeat, self.e_scanning, on_error)

        self.plot_timer.timeout.connect(self.update_plot)
        self.plot_timer.start(10)

    def plot(self, rows: list[(float, float, float, float)]):
        """
        Plots a U,I-graph in the plot widget.
        :param rows: a list of (u, u_err, i, i_err) tuples
        """
        if not rows:
            return

        x, x_err, y, y_err = [np.array(u) for u in zip(*rows)]

        self.plot_widget.clear()
        self.plot_widget.setLabel("left", "I (A)")
        self.plot_widget.setLabel("bottom", "U (V)")

        self.plot_widget.plot(x, y, symbol='o', symbolSize=5, pen=None)

        error_bars = pg.ErrorBarItem(x=x, y=y, width=2 * np.array(x_err), height=2 * np.array(y_err))
        self.plot_widget.addItem(error_bars)

    def update_plot(self):
        """
        This function gets called once every tick of the timer that updates the plot periodically.
        """
        if not self.e_scanning.is_set():
            self.scan_btn.setEnabled(True)
            self.plot_timer.stop()

        if self.plot_error:
            self.scan_btn.setEnabled(True)
            self.plot_timer.stop()
            d = QtWidgets.QMessageBox()
            d.setIcon(QtWidgets.QMessageBox.Warning)
            d.setText("Error occurred while taking measurement")
            d.setInformativeText("Try selecting another device.")
            d.setDetailedText(str(self.plot_error))
            d.setStandardButtons(QtWidgets.QMessageBox.Ok)
            d.exec_()
            self.plot_error = None

        self.plot(self.exp.rows)

    def save(self):
        """
        Saves the recorded data to file.
        """
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(filter="CSV files (*.csv)")

        save_data_to_csv(filepath, ["U", "U_err", "I", "I_err"], self.exp.rows)


class Experiment:
    """Experiment is responsible for managing the thread that performs the measurements.

    Attributes:
        rows: a list containing the measurements
        _scan_thread: the tread
    """
    def __init__(self):
        self.rows = []
        self._scan_thread = None

    def scan(self, port: str, start: float, end: float, steps: int, repeat: int,
             e_scanning: threading.Event = None, on_error=None):
        """
        Performs the series of measurements.
        :param port: a string specifying the exact device port
        :param start: start voltage
        :param end: end voltage
        :param steps: voltage step size
        :param repeat: number of times to repeat each measurement
        :param e_scanning: event that gets set at the start and cleared at the end of the measurement series
        :param on_error: callback that gets called when an error occurs, error gets passed as an argument
        """
        e_scanning.set()

        self.rows = []
        try:
            with DiodeExperiment(port) as m:
                try:
                    step_size = (end - start) / steps
                    for ((u, u_err), (i, i_err)) in m.scan_led(start, end, step_size, repeat):
                        self.rows.append((u, u_err, i, i_err))
                # catch inner errors so that the device gets a chance to close on error
                except (VisaIOError, SerialException) as e:
                    on_error(e)
        # catch errors while opening the device
        except SerialException as e:
            on_error(e)

        e_scanning.clear()

    def start_scan(self, port: str, start: float, end: float, steps: int, repeat: int,
                   e_scanning: threading.Event = None, on_error=None):
        """
        Perform the series of measurements on a separate thread.
        :param port: a string specifying the exact device port
        :param start: start voltage
        :param end: end voltage
        :param steps: voltage step size
        :param repeat: number of times to repeat each measurement
        :param e_scanning: event that gets set at the start and cleared at the end of the measurement series
        :param on_error: callback that gets called when an error occurs, error gets passed as an argument
        """
        self._scan_thread = threading.Thread(
            target=self.scan, args=(port, start, end, steps, repeat, e_scanning, on_error)
        )
        self._scan_thread.start()


def main():
    """
    Initializes and shows the UI.
    """
    app = QtWidgets.QApplication(sys.argv)
    ui = UserInterface()
    ui.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
