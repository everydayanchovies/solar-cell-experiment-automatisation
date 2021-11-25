from typing import Union

from pythondaq.controllers.meta_manager import MetaManager


class DiodeExperiment:
    def __init__(self):
        self.mm = MetaManager()

    def list_devices(self, filter_q: str) -> list[str]:
        return self.mm.list_devices(filter_q)

    def device_info(self, search_q: str) -> Union[str, bool, list[str]]:
        matching_devices = self.mm.list_devices(search_q)
        if not matching_devices:
            return False
        elif len(matching_devices) > 1:
            return matching_devices

        return self.mm.info(matching_devices[0])
