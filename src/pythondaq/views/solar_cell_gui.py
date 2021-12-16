import sys
import threading
from time import time, sleep

import numpy as np
from PyQt5 import QtWidgets, uic, QtCore
import pyqtgraph as pg
import pkg_resources
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
from pyvisa import VisaIOError
from serial import SerialException

from pythondaq.models.solar_cell_experiment import list_devices, SolarCellExperiment, p_for_u_i, \
    save_data_to_csv, model_u_i_func, \
    u_of_mosfet_sweetspot, v_out_of_mosfet_sweetspot, fit_u_i, fit_params_for_u_i_fit, \
    make_measurement_information_text, maximum_for_p


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

        # hide max power tracking graph
        self.max_pow_p_pw.setVisible(False)
        self.max_pow_r_pw.setVisible(False)
        self.periodic_tracking_cb.setVisible(False)
        self.active_tracking_cb.setVisible(False)

        # couple the max power tracking toggle to its function
        self.max_p_tracking_cb.toggled.connect(self.max_pow_tracking_toggled)
        self.periodic_tracking_cb.toggled.connect(self.periodic_tracking_toggled)
        self.active_tracking_cb.toggled.connect(self.active_tracking_toggled)

        # init a timer for reading the max power point
        self.max_pow_timer = QtCore.QTimer()
        # define a variable to carry errors across threads
        self.max_pow_error = None
        # init a timer for reading the measurements
        self.scan_timer = QtCore.QTimer()
        # define a variable to carry errors across threads
        self.scan_error = None
        # define an event that triggers when the scan is finished
        self.e_scanning = threading.Event()
        # init the experiment class to an object
        self.exp = Experiment()

        # flags for handling autorange and plot logic
        self.autorange_in_progress = False
        self.plot_in_progress = False

    def max_pow_tracking_toggled(self):
        """
        The toggled event listener for the maximum power point tracking checkbox.
        """
        if self.max_p_tracking_cb.isChecked():

            if not (self.periodic_tracking_cb.isChecked() or self.active_tracking_cb.isChecked()):
                self.active_tracking_cb.setChecked(True)

            self.max_pow_p_pw.setVisible(True)
            self.max_pow_r_pw.setVisible(True)
            self.periodic_tracking_cb.setVisible(True)
            self.active_tracking_cb.setVisible(True)

            def on_error(e):
                """
                Carries the error from the scan thread to the GUI thread.
                :param e: the error
                """
                self.max_pow_error = e

            port = self.devices_cb.currentText()
            self.exp.start_max_power_point_tracking(port, on_error=on_error)

            self.max_pow_timer.timeout.connect(self.max_pow_timer_tick)
            self.max_pow_timer.start(50)
        else:
            self.max_pow_p_pw.setVisible(False)
            self.max_pow_r_pw.setVisible(False)
            self.periodic_tracking_cb.setVisible(False)
            self.active_tracking_cb.setVisible(False)

            self.exp.stop_tracking_max_power_point()

            self.max_pow_timer.stop()

    def periodic_tracking_toggled(self):
        """
        The toggled event listener for the periodic tracking checkbox.
        """
        if not (self.periodic_tracking_cb.isChecked() or self.active_tracking_cb.isChecked()):
            self.max_p_tracking_cb.setChecked(False)
            self.exp.stop_tracking_max_power_point()
            self.max_pow_timer.stop()

        self.exp.max_p_periodic_tracking = self.periodic_tracking_cb.isChecked()

    def active_tracking_toggled(self):
        """
        The toggled event listener for the active tracking checkbox.
        """
        if not (self.periodic_tracking_cb.isChecked() or self.active_tracking_cb.isChecked()):
            self.max_p_tracking_cb.setChecked(False)
            self.exp.stop_tracking_max_power_point()
            self.max_pow_timer.stop()

        self.exp.max_p_active_tracking = self.active_tracking_cb.isChecked()

    def scan(self):
        """
        The click handler of the Scan button.
        """
        self.plot_in_progress = True
        self.perform_scan()

    def perform_scan(self, start_override=None, end_override=None, num_samples_override=None, repeat_override=None):
        """
        Takes a series of measurements of the current through and voltage across the solar panel.
        """
        start = float(self.u_start_ib.text() or 0.0)
        if not start:
            start = 0.1
        if start < 0:
            start = 0
        if start > 3.3:
            start = 3.3
        self.u_start_ib.setText(str(start))
        if start_override:
            start = start_override

        end = float(self.u_end_ib.text() or 0.0)
        if not end:
            end = 3.3
        if end < 0:
            end = 0
        if end > 3.3:
            end = 3.3
        self.u_end_ib.setText(str(end))
        if end_override:
            end = end_override

        num_samples = int(self.num_samples_ib.text() or 0)
        if not num_samples:
            num_samples = 100
            self.num_samples_ib.setText(str(num_samples))
        if num_samples_override:
            num_samples = num_samples_override

        repeat = int(self.repeat_ib.text() or 0)
        if not repeat:
            repeat = 15
            self.repeat_ib.setText(str(repeat))
        if repeat_override:
            repeat = repeat_override

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
        self.scan_timer.start(100)

    def scan_timer_tick(self):
        """
        This function gets called once every tick of the scan timer; updates the relevant listeners periodically.
        """

        if self.scan_error or not self.e_scanning.is_set():
            self.scan_btn.setEnabled(True)
            self.autorange_btn.setEnabled(True)

        if not self.e_scanning.is_set():
            self.scan_timer.stop()

        if self.scan_error:
            self.scan_timer.stop()
            self.autorange_in_progress = False

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

    def max_pow_timer_tick(self):
        """
        This function gets called once every tick of the maximum power point tracking timer.
        """
        if self.max_pow_error:
            self.exp.stop_tracking_max_power_point()

            d = QtWidgets.QMessageBox()
            d.setIcon(QtWidgets.QMessageBox.Warning)
            d.setText("Error occurred while taking measurement")
            d.setInformativeText("Try selecting another device, and avoid taking measurements while tracking the"
                                 "maximum power.")
            d.setDetailedText(str(self.scan_error))
            d.setStandardButtons(QtWidgets.QMessageBox.Ok)
            d.exec_()

            self.max_pow_error = None

            self.max_pow_timer.stop()

        self.scan_info_tb.setPlainText(make_measurement_information_text(
            max_p=self.exp.p_max,
            max_p_err=self.exp.p_max_err,
            max_r=self.exp.r_max,
            max_r_err=self.exp.r_max_err
        ))

        if not self.exp.p_r_t_rows:
            return

        p, p_err, r, r_err, t = [np.array(a) for a in zip(*self.exp.p_r_t_rows)]

        self.max_pow_p_pw.clear()
        self.max_pow_p_pw.setLabel("left", "P (W)")
        self.max_pow_p_pw.setLabel("bottom", "t (s)")

        self.max_pow_p_pw.plot(t, p, symbol='o', symbolSize=3, pen=None)

        error_bars = pg.ErrorBarItem(x=t, y=p, height=2 * np.array(p_err))
        self.max_pow_p_pw.addItem(error_bars)

        _t, _r, _r_err = [], [], []
        for j in range(len(r)):
            if np.isnan(r[j]) or np.isinf(r[j]) or np.isnan(r_err[j]) or np.isinf(r_err[j]):
                continue
            _t.append(t[j])
            _r.append(r[j])
            _r_err.append(r_err[j])

        _t = np.array(_t)
        _r = np.array(_r)
        _r_err = np.array(_r_err)

        self.max_pow_r_pw.clear()
        self.max_pow_r_pw.setLabel("left", "R (Ohm)")
        # hide this label on purpose, it is shown in the plot below
        # self.max_pow_r_pw.setLabel("bottom", "t (s)")

        self.max_pow_r_pw.plot(_t, _r, symbol='o', symbolSize=3, pen=None)

        error_bars = pg.ErrorBarItem(x=_t, y=_r, height=2 * np.array(_r_err))
        self.max_pow_r_pw.addItem(error_bars)

    def plot(self, finished_taking_measurements: bool = False):
        """
        Plots a U,I-graph and the P,R-graphs in the plot widgets.
        :param finished_taking_measurements: set to true when this is in fact the last measurement
        """
        if not self.exp.rows or (not self.plot_in_progress and not finished_taking_measurements):
            return

        u, u_err, i, i_err, r, r_err, p, p_err, v_out = [np.array(u) for u in zip(*self.exp.rows)]

        self.u_i_pw.clear()
        self.u_i_pw.setLabel("left", "I (A)")
        self.u_i_pw.setLabel("bottom", "U (V)")

        self.u_i_pw.plot(u, i, symbol='o', symbolSize=5, pen=None)

        if finished_taking_measurements:
            # find mosfet sweet spot
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

            # create trimmed arrays according to the mosfet sweetspot and other checks
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

            # fit the data to the solar panel model
            port = self.devices_cb.currentText()
            _, (I_l_init, _), _, _ = SolarCellExperiment(port).measure_u_i_r(0, 20)
            fit = fit_u_i(_u, _i, _i_err, I_l_init)

            self.fit_stats_u_i_tb.setPlainText(fit.fit_report())

            # create many datapoints according to the fit function
            x = np.array(range(int(np.min(u) * 1000), int(np.max(u) * 1000))) / 1000
            y = np.array([model_u_i_func(s, *fit_params_for_u_i_fit(fit)) for s in x])

            _x, _y = [], []
            for j in range(len(x)):
                if y[j] > 0:
                    _x.append(x[j])
                    _y.append(y[j])

            self.u_i_pw.plot(_x, _y, symbol=None, pen={"color": "k", "width": 5})

            max_p, max_r = maximum_for_p(p, r)
            _, max_p_err = maximum_for_p(p, p_err)
            _, max_r_err = maximum_for_p(p, r_err)
            self.scan_info_tb.setPlainText(make_measurement_information_text(
                max_p=max_p,
                max_p_err=max_p_err,
                max_r=max_r,
                max_r_err=max_r_err
            ))

        error_bars = pg.ErrorBarItem(x=u, y=i, width=2 * np.array(u_err), height=2 * np.array(i_err))
        self.u_i_pw.addItem(error_bars)

        self.u_u_pw.clear()
        self.u_u_pw.setLabel("left", "U (V)")
        self.u_u_pw.setLabel("bottom", "V_out (V)")

        self.u_u_pw.plot(v_out, u, symbol='o', symbolSize=5, pen=None)

        error_bars = pg.ErrorBarItem(x=v_out, y=u, height=2 * np.array(u_err))
        self.u_u_pw.addItem(error_bars)

        self.p_r_pw.clear()
        self.p_r_pw.setLabel("left", "P (W)")
        self.p_r_pw.setLabel("bottom", "R (Ohm)")

        _p, _p_err, _r, _r_err = [], [], [], []
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
        """
        Listener for the scan timer, responsible for updating the plot.
        """
        if self.scan_error or not self.e_scanning.is_set():
            self.plot_in_progress = False

        self.plot(finished_taking_measurements=(not self.plot_in_progress))

    def save(self):
        """
        Saves the recorded data to file.
        """
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(filter="CSV files (*.csv)")

        save_data_to_csv(filepath, ["U", "U_err", "I", "I_err", "R", "R_err", "P", "P_err", "V_out"], self.exp.rows)

    def autorange(self):
        """
        The click handler of the Autorange button.
        """
        self.mosfet_trim_cb.setChecked(False)

        self.autorange_in_progress = True

        self.perform_scan(start_override=0.1,
                          end_override=3.2,
                          num_samples_override=100,
                          repeat_override=3)

    def update_autorange(self):
        """
        Listener for the scan timer, responsible for eventually calculating the autorange.
        """
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
        _scan_thread: the scan tread
        _max_p_v_out: the Vout corresponding to the maximum power
        p_max: maximum power
        r_max: resistance at maximum power
        p_r_t_rows: power, resistance, time rows
        _max_pow_thread: the maximum power point tracking thread
        _kill_max_pow_thread: an event to signal the killing of _max_pow_thread
    """

    def __init__(self):
        self.rows = []
        self._scan_thread = None

        self._max_p_v_out = 0.0
        self.p_max = 0.0
        self.p_max_err = 0.0
        self.r_max = 0.0
        self.r_max_err = 0.0
        self.p_r_t_rows = []
        self._max_pow_thread = None
        self._kill_max_pow_thread = threading.Event()
        self._time_of_last_power_scan = time()
        self.max_p_active_tracking = True
        self.max_p_periodic_tracking = False

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

    def track_max_power_point(self, port: str, on_error=None):
        """
        Continuously tracks the maximum power and from time to time tries to find a better maximum.
        :param port: a string specifying the exact device port
        :param on_error: callback that gets called when an error occurs, error gets passed as an argument
        """

        try:
            with SolarCellExperiment(port) as m:
                while not self._kill_max_pow_thread.is_set():

                    def scan_for_max_power(retries=10):
                        """
                        Scans through the full output voltage range in search of the maximal power output.
                        :param retries: number of times to retry in case of a soft error
                        """
                        try:
                            u_rows, v_out_rows = [], []
                            for (u, u_err), (i, i_err), (r, r_err), v_out in m.scan_u_i_r(
                                    start_voltage=0.0,
                                    end_voltage=3.2,
                                    step_size=0.015,
                                    repeat=1
                            ):
                                p, p_err = p_for_u_i(u, u_err, i, i_err)
                                self.p_r_t_rows.append(
                                    (p, p_err, r, r_err, time())
                                )
                                self.pop_old_p_r_t_measurements()

                                u_rows.append(u)
                                v_out_rows.append(v_out)

                            v_out_start, v_out_end = v_out_of_mosfet_sweetspot(v_out_rows, u_rows)

                            u_rows, u_err_rows, i_rows, i_err_rows, r_rows, r_err_rows, v_out_rows = \
                                [], [], [], [], [], [], []
                            for (u, u_err), (i, i_err), (r, r_err), v_out in m.scan_u_i_r(
                                    start_voltage=v_out_start,
                                    end_voltage=v_out_end,
                                    step_size=0.01,
                                    repeat=4
                            ):
                                p, p_err = p_for_u_i(u, u_err, i, i_err)
                                self.p_r_t_rows.append(
                                    (p, p_err, r, r_err, time())
                                )
                                self.pop_old_p_r_t_measurements()

                                u_rows.append(u)
                                u_err_rows.append(u_err)
                                i_rows.append(i)
                                i_err_rows.append(i_err)
                                r_rows.append(r)
                                r_err_rows.append(r_err)
                                v_out_rows.append(v_out)

                            u_rows, u_err_rows, i_rows, i_err_rows, r_rows, r_err_rows, v_out_rows = [np.array(a) for a
                                                                                                      in
                                                                                                      [u_rows,
                                                                                                       u_err_rows,
                                                                                                       i_rows,
                                                                                                       i_err_rows,
                                                                                                       r_rows,
                                                                                                       r_err_rows,
                                                                                                       v_out_rows]
                                                                                                      ]

                            p_rows, p_err_rows = p_for_u_i(u_rows, u_err_rows, i_rows, i_err_rows)
                            self.p_max, self.r_max = maximum_for_p(p_rows, r_rows)
                            _, self.p_max_err = maximum_for_p(p_rows, p_err_rows)
                            _, self.r_max_err = maximum_for_p(p_rows, r_err_rows)
                            _, self._max_p_v_out = maximum_for_p(p_rows, v_out_rows)
                        # catch inner errors so that the device gets a chance to close on error
                        except (VisaIOError, SerialException) as e:
                            if on_error:
                                on_error(e)
                        # ignore trivial errors as this is a continuous function
                        except ValueError as e:
                            print(e)
                            scan_for_max_power(retries=retries - 1)

                        self._time_of_last_power_scan = time()

                    t = round(time() * 10) * 100

                    # find max power point every 7 seconds
                    if self.max_p_periodic_tracking and t % 7000 == 0:
                        scan_for_max_power()

                    # find max power point actively
                    if self.max_p_active_tracking and t % 200 and (time() - self._time_of_last_power_scan) > 2:
                        current_p = self.mean_power_in_time_range(time() - 1, time())
                        recent_p = self.mean_power_in_time_range(time() - 2, time() - 1)
                        if np.abs(current_p - recent_p) > 0.1 * recent_p:
                            scan_for_max_power()

                    # take passive measurements
                    try:
                        (u, u_err), (i, i_err), (r, r_err), _ = m.measure_u_i_r(output_voltage=self._max_p_v_out,
                                                                                repeat=6)
                        p, p_err = p_for_u_i(u, u_err, i, i_err)
                        self.p_r_t_rows.append(
                            (p, p_err, r, r_err, time())
                        )
                        self.pop_old_p_r_t_measurements()
                    except (VisaIOError, SerialException) as e:
                        if on_error:
                            on_error(e)
                    # ignore trivial errors as this is a continuous function
                    except ValueError as e:
                        print(e)
                        pass

                    # avoid spamming the output on high end hardware
                    if self.p_r_t_rows and (time() - self.p_r_t_rows[len(self.p_r_t_rows) - 1][4]) < 0.01:
                        sleep(0.03)

        # catch errors while opening the device
        except SerialException as e:
            if on_error:
                on_error(e)

    def pop_old_p_r_t_measurements(self):
        """
        Removes old measurements from the p_r_t array.
        """
        if len(self.p_r_t_rows) <= 1:
            return

        t = time()
        # remove last item while its age ([4]th element) is greater than 8 sec
        while t - self.p_r_t_rows[0][4] > 8:
            self.p_r_t_rows.pop(0)

    def mean_power_in_time_range(self, t_start, t_end):
        """
        Calculates the mean power in a given timeframe.
        :param t_start: start time
        :param t_end: end time
        :return: the mean power in the specified timeframe or 0.0 if not enough data
        """
        if p_in_range := [p for (p, _, _, _, t) in self.p_r_t_rows if t_start < t < t_end]:
            return np.mean(p_in_range)
        return 0.0

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

    def start_max_power_point_tracking(self, port: str, on_error=None):
        """
        Starts the maximum power point tracking thread.
        :param port: a string specifying the exact device port
        :param on_error: callback that gets called when an error occurs, error gets passed as an argument
        """
        self._kill_max_pow_thread.clear()
        self._max_pow_thread = threading.Thread(
            target=self.track_max_power_point, args=(port, on_error)
        )
        self._max_pow_thread.start()

    def stop_tracking_max_power_point(self):
        """
        Stops the maximum power point tracking thread.
        """
        self._kill_max_pow_thread.set()


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
