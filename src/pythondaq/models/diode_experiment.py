import csv
from typing import Generator

import numpy as np

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


class DiodeExperiment:
    def __init__(self, port):
        self.visa = ArduinoVISADevice(port)

    def measure_led_current_and_voltage(self, voltage: float, repeat: int = 1) -> (float, float):
        u_i_pairs = [res for res in self.__recursive_led_measurement(voltage, repeat) if res]

        print(u_i_pairs)

        return 0, 0

    def __recursive_led_measurement(self, output_voltage: float, repeat: int = 1):
        if repeat == 0:
            return False

        if output_voltage > 0.0:
            self.visa.set_output_voltage(CH_VOUT, output_voltage)

        voltage = self.visa.get_input_voltage(CH_U1) - self.visa.get_input_voltage(CH_U2)
        yield voltage, self.visa.get_input_voltage(CH_U2) / R

        yield from self.__recursive_led_measurement(voltage, repeat - 1)

    def scan_current_through_led(self, start_voltage: float, end_voltage: float, step_size: float):
        if end_voltage < start_voltage:
            raise ValueError(f"The start voltage ({start_voltage:.2f}) cannot be larger than the end voltage "
                             f"({end_voltage:.2f}). Try swapping the start and end voltage.")

        for v in np.arange(start_voltage, end_voltage + step_size, step_size):
            yield self.measure_led_current_and_voltage(v)

        return True
