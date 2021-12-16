import sys
import threading

import numpy as np
from PyQt5 import QtWidgets, uic, QtCore, Qt
import pyqtgraph as pg
import pkg_resources
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
from pyvisa import VisaIOError
from serial import SerialException

from pythondaq.models.solar_cell_experiment import list_devices, device_info, SolarCellExperiment, p_for_u_i, \
    plot_u_i, plot_p_r, save_data_to_csv, plot_u_r, v_out_for_mosfet_u, model_u_i_func, \
    u_of_mosfet_sweetspot, v_out_of_mosfet_sweetspot, fit_u_i, fit_params_for_u_i_fit, fit_stats_for_u_i_fit


class UserInterface(QtWidgets.QMainWindow):
    """UserInterface is responsible for rendering the UI and handling input events.
    """

    def __init__(self):
        super().__init__()

        # set plot colours
        pg.setConfigOption("background", 'w')
        pg.setConfigOption("foreground", 'b')

        # load UI from file
        ui = pkg_resources.resource_stream("pythondaq.views.ui", "solarcell.ui")
        uic.loadUi(ui, self)

        # init the devices combo box
        self.devices_cb.addItems(list_devices())
        self.devices_cb.setCurrentIndex(5)

        # init the start and end input boxes, limit input to floats
        float_only_regex = QRegExp("[+-]?([0-9]*[.])?[0-9]+")
        self.u_start_ib.setValidator(QRegExpValidator(float_only_regex))
        self.u_end_ib.setValidator(QRegExpValidator(float_only_regex))

        # init the samples and repeat input boxes, limit to integers
        int_only_regex = QRegExp("\\d+")
        self.num_samples_ib.setValidator(QRegExpValidator(int_only_regex))
        self.repeat_ib.setValidator(QRegExpValidator(int_only_regex))

        # couple the buttons to their functions
        self.scan_btn.clicked.connect(self.scan)
        self.save_btn.clicked.connect(self.save)
        self.autorange_btn.clicked.connect(self.autorange)

        # init a timer for reading the measurements
        self.scan_timer = QtCore.QTimer()
        # define a variable to carry errors across threads
        self.scan_error = None
        # define an event that triggers when the scan is finished
        self.e_scanning = threading.Event()
        # init the experiment class to an object
        self.exp = Experiment()

        self.autorange_in_progress = False
        self.plot_in_progress = False

    def scan(self):
        self.plot_in_progress = True
        self.perform_scan()

    def perform_scan(self, start_override=None, end_override=None, num_samples_override=None, repeat_override=None):
        """
        Takes a series of measurements of the current through and voltage across the LED.
        """
        start = float(self.u_start_ib.text() or 0.0)
        if not start or start_override:
            start = start_override or 0.1
            self.u_start_ib.setText(str(start))

        end = float(self.u_end_ib.text() or 0.0)
        if not end or end_override:
            end = end_override or 3.2
            self.u_end_ib.setText(str(end))

        num_samples = int(self.num_samples_ib.text() or 0)
        if not num_samples or num_samples_override:
            num_samples = num_samples_override or 100
            self.num_samples_ib.setText(str(num_samples))

        repeat = int(self.repeat_ib.text() or 0)
        if not repeat or repeat_override:
            repeat = repeat_override or 3
            self.repeat_ib.setText(str(repeat))

        def on_error(e):
            """
            Carries the error from the scan thread to the GUI thread.
            :param e: the error
            """
            self.scan_error = e

        self.scan_btn.setEnabled(False)
        self.autorange_btn.setEnabled(False)

        port = self.devices_cb.currentText()
        self.exp.start_scan(port, start, end, num_samples, repeat, self.e_scanning, on_error)

        self.scan_timer.timeout.connect(self.scan_timer_tick)
        self.scan_timer.start(20)

    def scan_timer_tick(self):
        """
        This function gets called once every tick of the timer that updates the plot periodically.
        """

        if self.scan_error or not self.e_scanning.is_set():
            self.scan_btn.setEnabled(True)
            self.autorange_btn.setEnabled(True)

        if not self.e_scanning.is_set():
            self.scan_timer.stop()

        if self.scan_error:
            self.scan_timer.stop()
            d = QtWidgets.QMessageBox()
            d.setIcon(QtWidgets.QMessageBox.Warning)
            d.setText("Error occurred while taking measurement")
            d.setInformativeText("Try selecting another device.")
            d.setDetailedText(str(self.scan_error))
            d.setStandardButtons(QtWidgets.QMessageBox.Ok)
            d.exec_()
            self.scan_error = None

        if self.plot_in_progress:
            self.update_plot()
        if self.autorange_in_progress:
            self.update_autorange()

    def plot(self, fit: bool = False):
        """
        Plots a U,I-graph in the plot widget.
        :param rows: a list of (u, u_err, i, i_err) tuples
        """
        if not self.exp.rows or (not self.plot_in_progress and not fit):
            return

        u, u_err, i, i_err, r, r_err, p, p_err, v_out = [np.array(u) for u in zip(*self.exp.rows)]

        self.u_i_pw.clear()
        self.u_i_pw.setLabel("left", "I (A)")
        self.u_i_pw.setLabel("bottom", "U (V)")

        self.u_i_pw.plot(u, i, symbol='o', symbolSize=5, pen=None)

        if fit:
            u_sweetspot_start, u_sweetspot_end = None, None

            try:
                if self.mosfet_trim_cb.isChecked():
                    u_sweetspot_start, u_sweetspot_end = u_of_mosfet_sweetspot(v_out, u)
            except ValueError as e:
                d = QtWidgets.QMessageBox()
                d.setIcon(QtWidgets.QMessageBox.Warning)
                d.setText("Error occurred while fitting")
                d.setInformativeText("The dynamic range of the mosfet could not be determined.")
                d.setDetailedText(str(e))
                d.setStandardButtons(QtWidgets.QMessageBox.Ok)
                d.exec_()

            _u, _i, _i_err = [], [], []
            for j in range(len(u)):
                if np.isnan(u[j]) or np.isnan(i[j]) or np.isnan(i_err[j]):
                    continue
                if u_sweetspot_start and u_sweetspot_end and not (u_sweetspot_start > u[j] > u_sweetspot_end):
                    continue
                _u.append(u[j])
                _i.append(i[j])
                _i_err.append(max(i_err[j], 1E-12))

            _u = np.array(_u)
            _i = np.array(_i)
            _i_err = np.array(_i_err)

            port = self.devices_cb.currentText()
            _, (I_l_init, _), _, _ = SolarCellExperiment(port).measure_u_i_r(0, 20)

            fit = fit_u_i(_u, _i, _i_err, I_l_init)

            self.fit_stats_u_i_tb.setPlainText(fit_stats_for_u_i_fit(fit))

            x = np.array(range(int(np.min(u) * 1000), int(np.max(u) * 1000))) / 1000
            y = np.array([model_u_i_func(s, *fit_params_for_u_i_fit(fit)) for s in x])

            _x, _y = [], []
            for j in range(len(x)):
                if y[j] > 0:
                    _x.append(x[j])
                    _y.append(y[j])

            self.u_i_pw.plot(_x, _y, symbol=None, pen={"color": "k", "width": 5})

        error_bars = pg.ErrorBarItem(x=u, y=i, width=2 * np.array(u_err), height=2 * np.array(i_err))
        self.u_i_pw.addItem(error_bars)

        self.p_r_pw.clear()
        self.p_r_pw.setLabel("left", "P (W)")
        self.p_r_pw.setLabel("bottom", "R (Ohm)")

        _p = []
        _p_err = []
        _r = []
        _r_err = []
        for j in range(len(p)):
            if not np.isinf(r[j]) and not np.isnan(r[j]) and not np.isinf(r_err[j]) and not np.isnan(r_err[j]):
                _p.append(p[j])
                _p_err.append(p_err[j])
                _r.append(r[j])
                _r_err.append(r_err[j])

        _p = np.array(_p)
        _p_err = np.array(_p_err)
        _r = np.array(_r)
        _r_err = np.array(_r_err)

        self.p_r_pw.plot(_r, _p, symbol='o', symbolSize=5, pen=None)

        error_bars = pg.ErrorBarItem(x=_r, y=_p, width=2 * np.array(_r_err), height=2 * np.array(_p_err))
        self.p_r_pw.addItem(error_bars)

    def update_plot(self):
        if self.scan_error or not self.e_scanning.is_set():
            self.plot_in_progress = False

        self.plot(fit=(not self.plot_in_progress))

    def save(self):
        """
        Saves the recorded data to file.
        """
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(filter="CSV files (*.csv)")

        save_data_to_csv(filepath, ["U", "U_err", "I", "I_err", "R", "R_err", "P", "P_err", "V_out"], self.exp.rows)

    def autorange(self):
        self.mosfet_trim_cb.setChecked(False)

        self.autorange_in_progress = True

        self.perform_scan(start_override=0.1,
                          end_override=3.2,
                          num_samples_override=100,
                          repeat_override=3)

    def update_autorange(self):
        if self.scan_error or not self.e_scanning.is_set():
            self.autorange_in_progress = False

        if self.e_scanning.is_set():
            return

        u, u_err, i, i_err, r, r_err, p, p_err, v_out = [np.array(u) for u in zip(*self.exp.rows)]

        sweetspot_v_out_start, sweetspot_v_out_end = v_out_of_mosfet_sweetspot(v_out, u)

        self.u_start_ib.setText(f"{sweetspot_v_out_start:.2f}")
        self.u_end_ib.setText(f"{sweetspot_v_out_end:.2f}")


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
            with SolarCellExperiment(port) as m:
                try:
                    step_size = (end - start) / steps
                    for ((u, u_err), (i, i_err), (r, r_err), v_out) in m.scan_u_i_r(start, end, step_size, repeat):
                        p, p_err = p_for_u_i(u, u_err, i, i_err)
                        self.rows.append((u, u_err, i, i_err, r, r_err, p, p_err, v_out))
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
