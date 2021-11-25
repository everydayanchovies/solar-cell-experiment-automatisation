from pythondaq.controllers.arduino_device import list_devices, device_info, ArduinoVISADevice


class DiodeExperiment:
    CH_VOUT = 0
    CH_U1 = 1
    CH_U2 = 2

    R = 220

    def __init__(self, port):
        self.visa_controller = ArduinoVISADevice(port)

    def measure_current_through_led(self, voltage: float) -> float:
        if voltage > 0.0:
            self.visa_controller.set_output_voltage(self.CH_VOUT, voltage)

        return self.visa_controller.get_output_voltage(self.CH_U2) / self.R
