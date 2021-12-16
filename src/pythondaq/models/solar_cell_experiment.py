import csv

import lmfit.lineshapes
import numpy as np
import scipy.interpolate
from lmfit import models, Parameters
from matplotlib import pyplot as plt

from pythondaq.controllers.arduino_device import list_devices, device_info, ArduinoVISADevice

CH_VOUT = 0
CH_U1 = 1
CH_U2 = 2


def save_data_to_csv(filepath: str, headers: list[str], data: list[tuple]):
    """
    Saves the provided data to a csv file on disk.
    :param filepath: the filepath of the file to be created
    :param headers: a list of csv headers (strings)
    :param data: a list of data rows (list of tuples)
    """
    with open(filepath, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        writer.writeheader()

        def make_row(data_row):
            row = {}
            for i in range(len(data_row)):
                row[headers[i]] = data_row[i]
            return row

        [writer.writerow(make_row(data_row)) for data_row in data]


def plot_u_i(u, u_err, i, i_err):
    """
    Shows a matplotlib plot of the provided U, I data.
    :param u: voltage data (array like)
    :param u_err: error on voltage data (array like)
    :param i: current data (array like)
    :param i_err: error on current data (array like)
    """
    plt.scatter(u, i)
    plt.errorbar(u, i, xerr=u_err, yerr=i_err, linestyle='')
    plt.xlabel(r"$U_{solarcell}$ [V]")
    plt.ylabel(r"$I_{solarcell}$ [A]")

    plt.show()


def plot_p_r(p, p_err, r, r_err):
    """
    Shows a matplotlib plot of the provided P, R data.
    :param p: power (array like)
    :param p_err: error on power (array like)
    :param r: resistance (array like)
    :param r_err: error on resistance (array like)
    """
    plt.scatter(r, p)
    plt.errorbar(r, p, xerr=r_err, yerr=p_err, linestyle='')
    plt.ylabel(r"$R_{solarcell}$ [$\Omega$]")
    plt.xlabel(r"$P_{solarcell}$ [W]")

    plt.show()


def p_for_u_i(u, u_err, i, i_err):
    """
    Calculate power P given voltage U and current I (lists, or single values).
    :param u: voltage
    :param u_err: voltage uncertainty
    :param i: current
    :param i_err: current uncertainty
    :return: power with uncertainty (p, p_err)
    """
    p = u * i
    p_err = p * np.sqrt(u_err ** 2 + i_err ** 2)
    return p, p_err


def v_out_for_mosfet_u(u_rows, v_out_rows, u):
    """
    Calculates the output voltage corresponding to the given voltage across the mosfet.
    :param u_rows: voltage across mosfet (list like)
    :param v_out_rows: output voltage (list like)
    :param u: query voltage across mosfet
    :return: corresponding output voltage
    """
    return scipy.interpolate.interp1d(u_rows, v_out_rows)(u)


def mosfet_u_for_v_out(u_rows, v_out_rows, v_out):
    """
    Calculates the voltage across the mosfet corresponding to the given output voltage.
    :param u_rows: voltage across mosfet (list like)
    :param v_out_rows: output voltage (list like)
    :param v_out: query output voltage
    :return: corresponding voltage across the mosfet
    """
    return scipy.interpolate.interp1d(v_out_rows, u_rows)(v_out)


def model_u_i_func(U, Il, I0, n, T):
    """
    The function relating the current flow through the solar panel to the voltage across it.
    :param U: voltage across solar panel
    :param Il: current running through solar panel when the voltage across the solar panel is 0V
    :param I0: the leak current of the diode virtual element of the solar panel
    :param n: efficiency factor
    :param T: temperature
    :return: current running through the solar panel
    """
    e = 1.602E-19
    k = 1.381E-23
    return Il - I0 * (np.exp((e * U) / (n * k * T)) - 1)


def fit_u_i(u, i, i_err, I_l_init):
    """
    Performs a fit on the given voltage and current data.
    :param u: voltage data
    :param i: current data
    :param i_err: uncertainty on current data
    :param I_l_init: current running through solar panel when voltage across it is 0V
    :return: a fit
    """
    m = lmfit.model.Model(model_u_i_func)

    params = Parameters()
    params.add("Il", value=I_l_init, min=1E-20, max=10, vary=True)
    params.add("I0", value=1E-6, min=1E-50, max=10)
    params.add("n", value=11, min=5, max=20)
    params.add("T", value=273, vary=False)

    _u, _i, _i_err = [], [], []
    for j in range(len(u)):
        if not np.isnan(i[j]) and not np.isinf(i[j]) \
                and not np.isnan(i_err[j]) and not np.isinf(i_err[j]):
            _u.append(u[j])
            _i.append(i[j])
            _i_err.append(i_err[j])

    return m.fit(_i, U=_u, params=params, weights=1 / i_err)


def fit_params_for_u_i_fit(fit):
    """
    Returns the fit parameter values for a given U,I-fit as a tuple.
    :param fit: the fit object
    :return: a tuple of (Il, I0, n, T)
    """
    return fit.params["Il"].value, fit.params["I0"].value, fit.params["n"].value, fit.params["T"].value


def v_out_of_mosfet_sweetspot(v_out, u):
    """
    Finds the output voltages between which the resistance of the mosfet changes significantly.
    :param v_out: output voltage data (list like)
    :param u: voltage across mosfet data (list like)
    :return: a range of voltages as a tuple (start, end)
    """
    v_out = np.array(v_out)
    u = np.array(u)

    u_rms = np.sqrt(np.mean(u ** 2))

    last_u = u[0]
    window_len = int(round(len(u) * 0.1))
    for i in range(window_len, len(v_out), window_len):
        if np.abs(last_u - u[i]) > u_rms:
            return v_out[i] - 0.5, v_out[i]

    raise ValueError("No sweetspot found!")


def u_of_mosfet_sweetspot(v_out, u):
    """
    Finds the voltages across the mosfet between which the resistance of the mosfet changes significantly.
    :param v_out: output voltage data (list like)
    :param u: voltage across mosfet data (list like)
    :return: a range of voltages as a tuple (start, end)
    """
    sweetspot_v_out_start, sweetspot_v_out_end = v_out_of_mosfet_sweetspot(v_out, u)

    u_sweetspot_start = mosfet_u_for_v_out(u, v_out, sweetspot_v_out_start)
    u_sweetspot_end = mosfet_u_for_v_out(u, v_out, sweetspot_v_out_end)

    return u_sweetspot_start, u_sweetspot_end


def maximum_for_p(p, arbt_arr):
    p_max, y_max = 0, 0
    for i in range(len(p)):
        if p[i] > p_max:
            p_max = p[i]
            y_max = arbt_arr[i]

    return p_max, y_max


def make_measurement_information_text(max_p, max_r):
    return f"Maximum power is {max_p:.6f} W when the solar panel senses a resistance of {max_r:.2f} Ohm."


class SolarCellExperiment:
    """SolarCellExperiment is a model representing an experiment with an LED and a resistor in series.

    Attributes:
        visa: an instance of the ArduinoVISADevice controller
        """

    def __init__(self, port: str):
        self.visa = ArduinoVISADevice(port)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.visa.close_device()
        except AttributeError:
            # ignore error while closing simulated device
            pass

    def measure_u_i_r(self, output_voltage: float, repeat: int = 1) -> \
            ((float, float), (float, float), (float, float), float):
        """
        Takes a (repeated) measurement of the voltage, current and resistance (with uncertainty) of the solar panel.
        Also sets the output voltage of the circuit prior to taking the measurement.
        :param output_voltage: sets this voltage as the circuit output voltage prior to measurement
        :param repeat: number of times to repeat the measurement (for calculating uncertainty)
        :return: a tuple of tuples and v_out ((u, u_err), (i, i_err), (r, r_err), v_out)
        """
        if output_voltage > 0.0:
            self.visa.set_output_voltage(CH_VOUT, output_voltage)

        u_i_r_pairs = [res for res in self.__recursive_u_i_r_measurement(repeat)]

        u, i, r = list(zip(*u_i_r_pairs))

        def value_with_uncertainty(values):
            if np.isinf(values).any() or np.isnan(values).any():
                return np.mean(values), np.inf
            return np.mean(values), np.std(values) / np.sqrt(len(values))

        return value_with_uncertainty(u), value_with_uncertainty(i), value_with_uncertainty(r), output_voltage

    def __recursive_u_i_r_measurement(self, repeat: int = 1):
        """
        Private function which recursively takes measurements of the solar panel.
        I implemented the logic like this (instead of a for loop) to challenge myself.
        :param repeat: carry variable containing the number of times to still repeat the measurement
        :return: yields a single measurement (u, i) continuously
        """
        if repeat <= 0:
            return False

        Upv = self.visa.get_input_voltage(CH_U1) * 3.0  # 1:3 voltage splitter
        U2 = self.visa.get_input_voltage(CH_U2)
        Ipv = U2 / 4.7
        if Ipv:
            resistance = np.abs((Upv - U2) / Ipv) + 4.7
        else:
            resistance = np.inf

        yield Upv, Ipv, resistance
        yield from self.__recursive_u_i_r_measurement(repeat - 1)

    def scan_u_i_r(self, start_voltage: float, end_voltage: float, step_size: float, repeat: int = 1):
        """
        Take a series of voltage, current and resistance measurements of the solar panel while varying the
        output voltage.
        :param start_voltage: beginning output voltage
        :param end_voltage: final output voltage
        :param step_size: step size of the varying voltage
        :param repeat: number of times to repeat each single measurement
        :return: yields a single measurement ((u, u_err), (i, i_err), (r, r_err), v_out) continuously
        """
        if end_voltage < start_voltage:
            raise ValueError(f"The start voltage ({start_voltage:.2f}) cannot be larger than the end voltage "
                             f"({end_voltage:.2f}). Try swapping the start and end voltage.")

        for u in np.arange(start_voltage, end_voltage + step_size, step_size):
            yield self.measure_u_i_r(u, repeat)

        self.visa.set_output_voltage(CH_VOUT, 0)

        # return True
