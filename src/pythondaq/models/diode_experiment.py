from typing import Union

from pyvisa.highlevel import ResourceInfo

from pythondaq.controllers.arduino_device import list_devices, device_info as _device_info


def device_info(search_q: str) -> Union[ResourceInfo, bool, list[str]]:
    matching_devices = list_devices(search_q)
    if not matching_devices:
        return False
    elif len(matching_devices) > 1:
        return matching_devices

    return _device_info(matching_devices[0])


def measure_current_through_led(voltage: float) -> float:
    return 0.0


class DiodeExperiment:
    pass
