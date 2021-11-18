import pyvisa

RESOLUTION = 1024
V_OUT = 3.3

rm = pyvisa.ResourceManager("@py")

device = rm.open_resource(
    "ASRL/dev/cu.usbmodem1301::INSTR",
    read_termination="\r\n",
    write_termination="\n"
)

for i in range(0, 1024):
    raw_ch0 = float(device.query(f"OUT:CH0 {i}"))
    volt_ch0 = (raw_ch0 / RESOLUTION) * V_OUT

    raw_ch2 = float(device.query("MEAS:CH2?"))
    volt_ch2 = (raw_ch2 / RESOLUTION) * V_OUT

    print("CH0 raw: %d\tCH0 volt: %.1f\tCH2 raw: %d\tCH2 volt: %.1f" % (raw_ch0, volt_ch0, raw_ch2, volt_ch2))

