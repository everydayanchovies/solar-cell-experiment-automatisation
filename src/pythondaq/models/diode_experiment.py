import csv

import numpy as np
from matplotlib import pyplot as plt

from pythondaq.controllers.arduino_device import list_devices, device_info, ArduinoVISADevice

CH_VOUT = 0
CH_U1 = 1
CH_U2 = 2

R = 220.0


def save_data_to_csv(filepath: str, headers: list[str], data: list[tuple]):
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
    plt.scatter(u, i)
    plt.errorbar(u, i, xerr=u_err, yerr=i_err, linestyle='')
    plt.xlabel(r"$U_{led}$ [V]")
    plt.ylabel(r"$I_{led}$ [A]")
    plt.show()


class DiodeExperiment:
    def __init__(self, port: str, dummy: bool = False):
        self.visa = ArduinoVISADevice(port, dummy)

    def measure_led_current_and_voltage(self, output_voltage: float, repeat: int = 1) \
            -> ((float, float), (float, float)):
        if output_voltage > 0.0:
            self.visa.set_output_voltage(CH_VOUT, output_voltage)

        u_i_pairs = [res for res in self.__recursive_led_measurement(repeat) if res]

        voltage = [u for (u, _) in u_i_pairs]
        current = [i for (_, i) in u_i_pairs]

        def value_with_uncertainty(values):
            return np.mean(values), np.std(values) / np.sqrt(len(values))

        return value_with_uncertainty(voltage), value_with_uncertainty(current)

    def __recursive_led_measurement(self, repeat: int = 1):
        if repeat == 0:
            return False

        voltage = self.visa.get_input_voltage(CH_U1) - self.visa.get_input_voltage(CH_U2)
        yield voltage, self.visa.get_input_voltage(CH_U2) / R

        yield from self.__recursive_led_measurement(repeat - 1)

    def scan_current_through_led(self, start_voltage: float, end_voltage: float, step_size: float, repeat: int = 1):
        if end_voltage < start_voltage:
            raise ValueError(f"The start voltage ({start_voltage:.2f}) cannot be larger than the end voltage "
                             f"({end_voltage:.2f}). Try swapping the start and end voltage.")

        for v in np.arange(start_voltage, end_voltage + step_size, step_size):
            yield self.measure_led_current_and_voltage(v, repeat)

        return True
