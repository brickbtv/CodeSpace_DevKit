from enum import Enum

from hardware import Registers, RAM
from hardware.common import Hardware

class Door(Hardware):
    """
        Door controller (8 slots)
        =========================

        Hardware-ID    : 0x387890c7
        Version        : 0x0001
        Manufacturer-ID: 0x54482b2b

        A  | Function
        ===+===============================================================
        0  | Sets B to mmmmmmmmssssssss (m: mode, s: state) of door I.
           | Sets B to 0 if no door is connected at slot I.
        ---+---------------------------------------------------------------
        1  | Set operation mode of door I to B.
           | Has no effect if no door is connected at slot I.
        ---+---------------------------------------------------------------
        2  | Sets interrupt message to B. Disables interrupts if B = 0.
        ---+---------------------------------------------------------------

        Door controller will raise an interrupt whenever state of any
        connected door changes.

        Modes:
        0:    Keep door closed
              (for safety reasons, doors won't close as long as they are
              blocked by a person)
        1:    Open on proximity (inside only)
        2:    Open on proximity
        3:    Keep door open

        States:
        0x01: Proximity detected inside
        0x02: Proximity detected outside
        0x04: Door is currently open
    """
    ID = 0x387890c7
    VERSION = 0x0001
    VENDOR = 0x54482b2b
    TYPE = 'door'

    AMOUNT = 3

    class Modes(Enum):
        CLOSED = 0
        PROXIMITY_INSIDE = 1
        PROXIMITY = 2
        OPEN = 3

    class States(Enum):
        DEFAULT = 0
        PROXIMITY_DETECTED_INSIDE = 1
        PROXIMITY_DETECTED = 2
        IS_OPENED = 4

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)
        # TODO: a variable amount of doors
        self.mode = [Door.Modes.PROXIMITY, Door.Modes.PROXIMITY, Door.Modes.PROXIMITY]
        self.state = [Door.States.DEFAULT, Door.States.DEFAULT, Door.States.DEFAULT]

        self.irq_enabled = False
        self.irq_code = None
        self.interruptions = []

    def handle_interruption(self):
        code = self.regs.A
        if code == 0:
            door = self.regs.I
            if door > 3:
                return

            self.regs.B = (self.mode[door].value << 8) | self.state[door].value
        elif code == 1:
            door = self.regs.I
            if door > 3:
                return
            self.mode[door] = self.Modes(self.regs.B)
        elif code == 2:
            self.irq_code = self.regs.B
            self.irq_enabled = bool(self.irq_code != 0)
        else:
            print(f'[{self.TYPE}] Unexpected interruption code: {code}')

    def change_state(self, door: int, state: States):
        if door > 3:
            return

        self.state[door] = state
        if self.irq_enabled:
            self.interruptions.append(self.irq_code)

    def change_mode(self, door: int, mode: Modes):
        if door > 3:
            return

        self.mode[door] = mode

