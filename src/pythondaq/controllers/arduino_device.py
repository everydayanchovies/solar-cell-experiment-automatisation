"""Enables communication with a device running a VISA compatible firmware.

    Typical usage example:

    PORT = "ASRL/dev/cu.usbmodem1301::INSTR"

    device = ArduinoVISADevice(port=PORT)

    # an led is connected to the output channel 0
    CH_LED = 0

    # turn the led on
    device.set_output_voltage(CH_LED, 1023)

    # turn the led off
    device.set_output_voltage(CH_LED, 0)
"""
from typing import Union

import numpy as np
import pyvisa
from pyvisa.highlevel import ResourceInfo


def resource_manager():
    return pyvisa.ResourceManager("@py")


def list_devices(filter_q: str, dummy: bool = False) -> list[str]:
    if dummy:
        return ["dummy"]

    return [d for d in resource_manager().list_resources()
            if not filter_q or filter_q.lower() in d.lower()]


def device_info(resource_name) -> ResourceInfo:
    return resource_manager().resource_info(resource_name)


class ArduinoVISADevice:
    def __init__(self, port: str, dummy: bool = False):
        """
        Initializes a ArduinoVISADevice instance.
        :type port: String
        :param port: The port corresponding to the arduino device. For example: ASRL/dev/cu.usbmodem1301::INSTR
        """
        self.port = port
        self.dummy = dummy
        self.rm = resource_manager()
        self.device = self.__open_device()

        if dummy:
            print("WARNING: not connecting to an actual device, will return dummy values.")

    def __open_device(self) -> Union[pyvisa.Resource, None]:
        """
        Opens a device through the PyVISA resource manager.
        :return: The opened device.
        """
        if self.dummy:
            return None

        return self.rm.open_resource(
            resource_name=self.port,
            read_termination="\r\n",
            write_termination="\n"
        )

    def set_output_voltage(self, channel, value):
        """
        Sets the output voltage of a certain channel.
        :type channel: int
        :param channel: The output channel of which the voltage should be set. For example: 0.
        :type value: float
        :param value: The voltage to set the output channel to. For example: 2.2.
        """
        if self.dummy:
            return

        self.device.query(f"OUT:CH{channel}:VOLT {value}")

    def get_output_voltage(self, channel, v=False) -> float:
        """
        Get the output voltage of a certain channel.
        :param v: verbose
        :type channel: int
        :param channel: The channel of which the output voltage will be read. For example, 1.
        :return: The output voltage of the specified channel.
        """
        if self.dummy:
            return np.random.randint(33) / 10

        q = f"OUT:CH{channel}:VOLT?"
        if v:
            print(f"SEND COMMAND: {q}")

        res = self.device.query(q)
        if v:
            print(f"RECEIVED RESPONSE: {res}")

        return float(res)

    def get_input_voltage(self, channel, v=False) -> float:
        """
        Get the input voltage of a certain channel.
        :param v: verbose
        :type channel: int
        :param channel: The channel of which the input voltage will be read. For example, 1.
        :return: The input voltage of the specified channel.
        """
        if self.dummy:
            return np.random.randint(33) / 10

        q = f"MEAS:CH{channel}:VOLT?"
        if v:
            print(f"SEND COMMAND: {q}")

        res = self.device.query(q)
        if v:
            print(f"RECEIVED RESPONSE: {res}")

        return float(res)

