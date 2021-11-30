import csv
from typing import Generator

import numpy as np

from pythondaq.controllers.arduino_device import list_devices, device_info, ArduinoVISADevice


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
    CH_VOUT = 0
    CH_U1 = 1
    CH_U2 = 2

    R = 220.0

    def __init__(self, port):
        self.visa_controller = ArduinoVISADevice(port)

    def measure_current_through_led(self, voltage: float) -> float:
        if voltage > 0.0:
            self.visa_controller.set_output_voltage(self.CH_VOUT, voltage)

        return self.visa_controller.get_input_voltage(self.CH_U2) / self.R

    def scan_current_through_led(self, start_voltage: float, end_voltage: float, step_size: float):
        if end_voltage < start_voltage:
            raise ValueError(f"The start voltage ({start_voltage:.2f}) cannot be larger than the end voltage "
                             f"({end_voltage:.2f}). Try swapping the start and end voltage.")

        for v in np.arange(start_voltage, end_voltage + step_size, step_size):
            yield v, self.measure_current_through_led(v)

        return True

