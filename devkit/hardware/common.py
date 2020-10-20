from abc import ABC


class Hardware(ABC):
    ID = None
    VERSION = None
    VENDOR = None
    TYPE = None

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        self.regs = regs
        self.ram = ram

    def handle_interruption(self):
        raise NotImplemented
