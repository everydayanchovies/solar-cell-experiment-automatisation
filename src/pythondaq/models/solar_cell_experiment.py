import csv

import numpy as np
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


def clean_float_arr(a):
    return np.array([s if isinstance(s, (int, float)) else 0 for s in a])


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
    Shows a matplotlib plot of the provided U, I data.
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


def plot_u_r(u, u_err, i, i_err):
    _u = u
    _u_err = u_err
    _r = np.array(_u) / np.array(i)
    _r_err = np.array(_u_err) / np.array(i_err)

    u = []
    u_err = []
    r = []
    r_err = []
    for i in range(len(_u)):
        if np.isnan(_r[i]) or np.isinf(_r[i]):
            continue
        r.append(_r[i])
        r_err.append(_r_err[i])
        u.append(_u[i])
        u_err.append(_u_err[i])

    plt.scatter(u, r)
    plt.errorbar(u, r, xerr=u_err, yerr=r_err, linestyle='')
    plt.xlabel(r"$U_{solarcell}$ [V]")
    plt.ylabel(r"$R_{solarcell}$ [$\Omega$]")

    plt.show()


def p_for_u_i(u, u_err, i, i_err):
    p = u * i
    p_err = p * np.sqrt(u_err ** 2 + i_err ** 2)
    return p, p_err


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
        Takes a (repeated) measurement of the voltage and current (with uncertainty) across and through the LED.
        Also sets the output voltage of the LED prior to taking the measurement.
        :param output_voltage: sets this voltage as the LED voltage prior to measurement
        :param repeat: number of times to repeat the measurement (for calculating uncertainty)
        :return: a tuple of tuples ((u, u_err), (i, i_err), (r, r_err)
        """
        if output_voltage > 0.0:
            self.visa.set_output_voltage(CH_VOUT, output_voltage)

        u_i_r_pairs = [res for res in self.__recursive_u_i_r_measurement(repeat)]

        u, i, r = list(zip(*u_i_r_pairs))

        def value_with_uncertainty(values):
            return np.mean(values), np.std(values) / np.sqrt(len(values))

        return value_with_uncertainty(u), value_with_uncertainty(i), value_with_uncertainty(r), output_voltage

    def __recursive_u_i_r_measurement(self, repeat: int = 1):
        """
        Private function which recursively measures the current and voltage through and over the LED.
        I implemented the logic like this (instead of a for loop) to challenge myself.
        :param repeat: carry variable containing the number of times to still repeat the measurement
        :return: yields a single measurement (u, i) continuously
        """
        if repeat <= 0:
            return False

        voltage = self.visa.get_input_voltage(CH_U1) * 3.0  # 1:3 voltage splitter
        current = self.visa.get_input_voltage(CH_U2) / 4.7
        if current:
            resistance = voltage / current
        else:
            resistance = np.inf

        yield voltage, current, resistance
        yield from self.__recursive_u_i_r_measurement(repeat - 1)

    def scan_u_i_r(self, start_voltage: float, end_voltage: float, step_size: float, repeat: int = 1):
        """
        Take a series of voltage and current measurements of the LED while varying the output voltage.
        :param start_voltage: beginning output voltage
        :param end_voltage: final output voltage
        :param step_size: step size of the varying voltage
        :param repeat: number of times to repeat each single measurement
        :return: yields a single measurement ((u, u_err), (i, i_err), (r, r_err)) continuously
        """
        if end_voltage < start_voltage:
            raise ValueError(f"The start voltage ({start_voltage:.2f}) cannot be larger than the end voltage "
                             f"({end_voltage:.2f}). Try swapping the start and end voltage.")

        for u in np.arange(start_voltage, end_voltage + step_size, step_size):
            yield self.measure_u_i_r(u, repeat)

        self.visa.set_output_voltage(CH_VOUT, 0)

        return True

    def find_optimal_v_out(self):
        pass


