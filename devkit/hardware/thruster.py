from hardware import Registers, RAM
from hardware.common import Hardware


class Thruster(Hardware):
    """
        Thruster
        =========
        Hardware-ID: 0xa4748683
        Version    : 0x0001
        Manufaturer: 0x54482b2b

        Hardware interrupt with register A set to 0 will set the thrust
        depending on the value of B. Only the low 8 bits of B are used.
    """
    ID = 0xa4748683
    VERSION = 0x0001
    VENDOR = 0x54482b2b

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)
        self.power = 0

    def handle_interruption(self):
        code = self.regs.A
        if code == 0:
            self.power = self.regs.B & 0xff
        else:
            raise Exception(f'Unexpected interruption code: {code}')
