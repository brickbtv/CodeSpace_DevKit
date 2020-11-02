import time

from hardware.common import Hardware
from hardware import Registers, RAM


class Clock(Hardware):
    ID = 0x12d0b402
    VERSION = 0x0001
    VENDOR = 0x54482B2B
    TYPE = 'clock'

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)
        self.interval = 0
        self.period = 0
        self.last_call = time.time()
        self.last_call_to_0 = time.time()

        self.irq_enabled = False
        self.irq_code = None
        self.interruptions = []

    def handle_interruption(self):
        code = self.regs.A

        if code == 0:
            self.interval = self.regs.B
            if self.interval > 0:
                self.period = 60/self.interval
            else:
                self.period = 0

            self.last_call_to_0 = time.time()
        elif code == 1:
            if self.period > 0:
                self.regs.C = (time.time() - self.last_call_to_0) / self.period
            else:
                self.regs.C = 0
        elif code == 2:
            self.irq_code = self.regs.B
            self.irq_enabled = bool(self.irq_code != 0)

    def update(self):
        if self.irq_enabled and self.interval > 0:
            if time.time() - self.last_call >= self.period:
                self.interruptions.append(self.irq_code)
                self.last_call = time.time()
