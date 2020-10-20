from hardware.common import Hardware
from hardware import Registers, RAM


class Sensor(Hardware):
    """
        Sensor
        ===============
        Hardware-ID: ID 0x1F12E306
        Manufacturer: 0x54482B2B
        Version: 0x0001

        Scans up to 2000m with a 120 degree arc.

        Behavior depends on the A register when the HWI is sent.

        0: Returns the first contact from the scan.
            Sets B to the type of contact,
            Z the diameter of the contact,
            Y the range to contact,
            and X the angle to contact.

                  0x0000-0x7FFF represent 0-60 degrees to the right,
            while 0xFFFF-0x8000 represent 0-60 degrees to the left.
        1: Clears the scanners internal memory then preforms
            a scan loading loading contacts into the scanners internal memory.
    """

    ID = 0x1F12E306
    VERSION = 0x0001
    VENDOR = 0x54482B2B
    TYPE = 'sensor'

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)
        self.contacts = []
        self.actual_situation = []

    def handle_interruption(self):
        code = self.regs.A
        if code == 1:
            self.contacts = self.actual_situation
        elif code == 0:
            try:
                contact = self.contacts.pop()
                self.regs.B = contact['type']
                self.regs.X = contact['angle']
                self.regs.Y = contact['range']
                self.regs.Z = contact['size']
            except IndexError:
                self.regs.B = 0
                self.regs.X = 0
                self.regs.Y = 0
                self.regs.Z = 0
        else:
            raise Exception(f'Unexpected interruption code: {code}')

    def update_sensor(self, data):
        self.actual_situation = data
