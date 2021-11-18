import pyvisa
import matplotlib.pyplot as plt
from matplotlib import rc

rc('text', usetex=True)


RESOLUTION = 1024
V_OUT = 3.3

rm = pyvisa.ResourceManager("@py")

device = rm.open_resource(
    "ASRL/dev/cu.usbmodem1301::INSTR",
    read_termination="\r\n",
    write_termination="\n"
)

# 5.2
# for i in range(0, 1024):
#     raw_ch0 = float(device.query(f"OUT:CH0 {i}"))
#     volt_ch0 = (raw_ch0 / RESOLUTION) * V_OUT
#
#     raw_ch2 = float(device.query("MEAS:CH2?"))
#     volt_ch2 = (raw_ch2 / RESOLUTION) * V_OUT
#
#     print("%d %.1f %d %.1f" % (raw_ch0, volt_ch0, raw_ch2, volt_ch2))

# 5.3

# gather U, I measurements
U_I_pairs = []
for i in range(0, 1024):
    raw_ch0 = float(device.query(f"OUT:CH0 {i}"))
    U_ch0 = (raw_ch0 / RESOLUTION) * V_OUT

    raw_ch2 = float(device.query("MEAS:CH2?"))
    U_ch2 = (raw_ch2 / RESOLUTION) * V_OUT

    U_led = U_ch0 - U_ch2

    I_led = U_led / 200

    U_I_pairs.append((U_led, I_led))

# turn off the led
device.query(f"OUT:CH0 0")

# print gathered data
for (U_led, I_led) in U_I_pairs:
    print("%.2f %.4f" % (U_led, I_led))

# plot gathered data
plt.plot([U for U in U_I_pairs], [I for I in U_I_pairs])
plt.xlabel(r"$U_{led}$")
plt.ylabel(r"$I_{led}$")
plt.show()

