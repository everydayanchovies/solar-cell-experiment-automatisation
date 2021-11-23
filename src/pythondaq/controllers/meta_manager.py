import pyvisa


class MetaManager:
    def __init__(self):
        self.rm = pyvisa.ResourceManager("@py")

    def list_devices(self, query="?*::INSTR"):
        return self.rm.list_resources(query)

    def info(self, resource_name):
        return self.rm.resource_info(resource_name)