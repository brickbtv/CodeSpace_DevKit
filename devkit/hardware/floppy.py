from hardware.common import Hardware
from hardware import Registers, RAM


class Floppy(Hardware):
    ID = 0x4FD524C5
    VERSION = 0x0001
    VENDOR = 0x54482B2B
    TYPE = 'clock'

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)

    def handle_interruption(self):
        raise NotImplemented('Clock device not implemented')
