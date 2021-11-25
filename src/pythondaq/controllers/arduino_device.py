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

import pyvisa
from pyvisa.highlevel import ResourceInfo


def resource_manager():
    return pyvisa.ResourceManager("@py")


def list_devices(filter_q) -> list[str]:
    return [d for d in resource_manager().list_resources()
            if not filter_q or filter_q.lower() in d.lower()]


def device_info(resource_name) -> ResourceInfo:
    return resource_manager().resource_info(resource_name)


class ArduinoVISADevice:
    def __init__(self, port):
        """
        Initializes a ArduinoVISADevice instance.
        :type port: String
        :param port: The port corresponding to the arduino device. For example: ASRL/dev/cu.usbmodem1301::INSTR
        """
        self.port = port
        self.rm = resource_manager()
        self.device = self.__open_device()

    def __open_device(self) -> pyvisa.Resource:
        """
        Opens a device through the PyVISA resource manager.
        :return: The opened device.
        """
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
        self.device.query(f"OUT:CH{channel}:VOLT {value}")

    def get_output_voltage(self, channel) -> float:
        """
        Get the output voltage of a certain channel.
        :type channel: int
        :param channel: The channel of which the output voltage will be read. For example, 1.
        :return: The output voltage of the specified channel.
        """
        return float(self.device.query(f"OUT:CH{channel}:VOLT?"))

    def get_input_voltage(self, channel) -> float:
        """
        Get the input voltage of a certain channel.
        :type channel: int
        :param channel: The channel of which the input voltage will be read. For example, 1.
        :return: The input voltage of the specified channel.
        """
        return float(self.device.query(f"MEAS:CH{channel}:VOLT?"))

