from enum import Enum

from hardware import Registers, RAM
from hardware.common import Hardware


class DockingClamp(Hardware):
    """
        TODO: spec
    """
    ID = 0x7877A3DF
    VERSION = 0x0001
    VENDOR = 0x54482b2b
    TYPE = 'docking_clamp'

    AMOUNT = 4

    class Modes(Enum):
        OFF = 0
        PULL = 1
        LOCK = 2

    class States(Enum):
        # TODO: find out
        DEFAULT = 0

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)
        # TODO: a variable amount of clams
        self.mode = [DockingClamp.Modes.PULL, DockingClamp.Modes.PULL, DockingClamp.Modes.PULL, DockingClamp.Modes.PULL]
        self.state = [DockingClamp.States.DEFAULT, DockingClamp.States.DEFAULT, DockingClamp.States.DEFAULT, DockingClamp.States.DEFAULT]

        self.irq_enabled = False
        self.irq_code = None
        self.interruptions = []

    def handle_interruption(self):
        code = self.regs.A
        if code == 0:
            clamp = self.regs.I
            if clamp > 4:
                return
            self.regs.B = (self.mode[clamp].value << 8) & self.state[clamp].value
        elif code == 1:
            clamp = self.regs.I
            if clamp > 4:
                return
            self.mode[clamp] = DockingClamp.Modes(self.regs.B)
        elif code == 2:
            self.irq_code = self.regs.B
            self.irq_enabled = bool(self.irq_code != 0)
        else:
            raise Exception(f'[{self.TYPE}] Unexpected interruption code: {code}')

    def change_state(self, clamp: int, state: States):
        if clamp > 4:
            return

        self.state[clamp] = state
        if self.irq_enabled:
            self.interruptions.append(self.irq_code)

    def change_mode(self, clamp: int, mode: Modes):
        if clamp > 4:
            return

        self.mode[clamp] = mode

