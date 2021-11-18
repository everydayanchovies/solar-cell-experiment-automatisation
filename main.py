import matplotlib.pyplot as plt
from matplotlib import rc
from pythondaq.controllers.arduino_device import ArduinoVISADevice

rc('text', usetex=True)

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

    R = 220
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
