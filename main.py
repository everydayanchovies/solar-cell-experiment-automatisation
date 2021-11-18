import pyvisa
import matplotlib.pyplot as plt
from matplotlib import rc

rc('text', usetex=True)


class ArduinoVISADevice:
    def __init__(self, port):
        """
        Initializes a ArduinoVISADevice instance.
        :type port: String
        :param port: The port corresponding to the arduino device. For example: ASRL/dev/cu.usbmodem1301::INSTR
        """
        self.port = port
        self.rm = pyvisa.ResourceManager("@py")
        self.device = self.open_device()

    def open_device(self) -> pyvisa.Resource:
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


PORT = "ASRL/dev/cu.usbmodem1301::INSTR"

device = ArduinoVISADevice(port=PORT)

# gather U, I measurements
U_I_pairs = []
for i in range(0, 1024):
    U = (i / (1024 - 1)) * 3.3
    device.set_output_voltage(0, U)

    U_ch1 = device.get_input_voltage(1)
    U_ch2 = device.get_input_voltage(2)

    U_led = U_ch1 - U_ch2

    R = 200
    I_led = U_led / R

    U_I_pairs.append((U_led, I_led))

# turn off the led
device.set_output_voltage(0, 0)

# print gathered data
for (U_led, I_led) in U_I_pairs:
    print("%.2f %.4f" % (U_led, I_led))

# plot gathered data
plt.plot([U for U in U_I_pairs], [I for I in U_I_pairs])
plt.xlabel(r"$U_{led}$")
plt.ylabel(r"$I_{led}$")
plt.show()
