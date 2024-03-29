from hardware.common import Hardware
from hardware import Registers, RAM


class Boot(Hardware):
    ID = 0xEC418001
    VERSION = 0x0001
    VENDOR = 0x54482B2B
    TYPE = 'boot'

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)

    def handle_interruption(self):
        print('Boot device not implemented')
