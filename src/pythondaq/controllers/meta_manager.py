import pyvisa


class MetaManager:
    def __init__(self):
        self.rm = pyvisa.ResourceManager("@py")

    def list_devices(self, filter_q=""):
        return [p for p in self.rm.list_resources()
                if not filter_q or filter_q.lower() in p.lower()]

    def info(self, resource_name):
        return self.rm.resource_info(resource_name)