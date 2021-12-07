import csv

import numpy as np
from matplotlib import pyplot as plt

from pythondaq.controllers.arduino_device import list_devices, device_info, ArduinoVISADevice

CH_VOUT = 0
CH_U1 = 1
CH_U2 = 2

R = 220.0


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


def plot_current_against_voltage(u, u_err, i, i_err):
    """
    Shows a matplotlib plot of the provided U, I data.
    :param u: voltage data (array like)
    :param u_err: error on voltage data (array like)
    :param i: current data (array like)
    :param i_err: error on current data (array like)
    """
    plt.scatter(u, i)
    plt.errorbar(u, i, xerr=u_err, yerr=i_err, linestyle='')
    plt.xlabel(r"$U_{led}$ [V]")
    plt.ylabel(r"$I_{led}$ [A]")
    plt.show()


class DiodeExperiment:
    """DiodeExperiment is a model representing an experiment with an LED and a resistor in series.

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

    def measure_led(self, output_voltage: float, repeat: int = 1) -> ((float, float), (float, float)):
        """
        Takes a (repeated) measurement of the voltage and current (with uncertainty) across and through the LED.
        Also sets the output voltage of the LED prior to taking the measurement.
        :param output_voltage: sets this voltage as the LED voltage prior to measurement
        :param repeat: number of times to repeat the measurement (for calculating uncertainty)
        :return: a tuple of tuples ((u, u_err), (i, i_err))
        """
        if output_voltage > 0.0:
            self.visa.set_output_voltage(CH_VOUT, output_voltage)

        u_i_pairs = [res for res in self.__recursive_led_measurement(repeat)]

        voltage, current = list(zip(*u_i_pairs))

        def value_with_uncertainty(values):
            return np.mean(values), np.std(values) / np.sqrt(len(values))

        return value_with_uncertainty(voltage), value_with_uncertainty(current)

    def __recursive_led_measurement(self, repeat: int = 1):
        """
        Private function which recursively measures the current and voltage through and over the LED.
        I implemented the logic like this (instead of a for loop) to challenge myself.
        :param repeat: carry variable containing the number of times to still repeat the measurement
        :return: yields a single measurement (u, i) continuously
        """
        if repeat == 0:
            return False

        voltage = self.visa.get_input_voltage(CH_U1) - self.visa.get_input_voltage(CH_U2)
        current = self.visa.get_input_voltage(CH_U2) / R

        yield voltage, current
        yield from self.__recursive_led_measurement(repeat - 1)

    def scan_led(self, start_voltage: float, end_voltage: float, step_size: float, repeat: int = 1):
        """
        Take a series of voltage and current measurements of the LED while varying the output voltage.
        :param start_voltage: beginning output voltage
        :param end_voltage: final output voltage
        :param step_size: step size of the varying voltage
        :param repeat: number of times to repeat each single measurement
        :return: yields a single measurement ((u, u_err), (i, i_err)) continuously
        """
        if end_voltage < start_voltage:
            raise ValueError(f"The start voltage ({start_voltage:.2f}) cannot be larger than the end voltage "
                             f"({end_voltage:.2f}). Try swapping the start and end voltage.")

        for v in np.arange(start_voltage, end_voltage + step_size, step_size):
            yield self.measure_led(v, repeat)

        self.visa.set_output_voltage(CH_VOUT, 0)

        return True
