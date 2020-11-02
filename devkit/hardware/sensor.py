from hardware.common import Hardware
from hardware import Registers, RAM


class Sensor(Hardware):
    """
        Sensor
        ======

        Hardware-ID    : 0x1f12e306
        Version        : 0x0002
        Manufacturer-ID: 0x54482b2b

        A  | Function
        ===+===============================================================
        0  | Scan and put all contacts into contact buffer,
           | sorted by distance, from close to far.
        ---+---------------------------------------------------------------
        1  | Pulls next contact from the buffer. Sets registers as follows:
           | A: Type sssssssstttttttt (s: subtype, t: type*)
           | B: Identifier* (hi word)
           | C: Identifier (lo word)
           | X: Direction of contact, relative to sensor's orientation
           | Y: Distance*
           | Z: Approximate diameter in meters
           |
           | Sets A,B,C,X,Y,Z to 0 when no more contacts in the buffer.
        ---+---------------------------------------------------------------

        * Common object types are (among others)
          0x01: Asteroid
          0x03: Structure
          0x08: Buoy

        * Identifier is an optional identifier specified by the contact,
          usually through a transponder.
          Not guaranteed to be unique.

        * Distance is expressed relative to the Sensor's scan range, which
          is usually declared somewhere on the device.
          0x0000 means distance of 0 meters
          0xffff means distance of (max-range) meters
          This gives short range Sensors a higher resolution than long range
          (>1000000 meter) Sensors.

        Object size can affect visibility for the Sensor. The Sensor may
        be unable to detect small objects even inside the Sensor's range
        unless they are close enough.
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
        if code == 0:
            self.contacts = self.actual_situation
        elif code == 1:
            try:
                contact = self.contacts.pop()
                self.regs.A = contact['type']
                self.regs.B = contact['id'] >> 16
                self.regs.C = contact['id'] & 0xffff
                self.regs.X = contact['angle']
                self.regs.Y = contact['range']
                self.regs.Z = contact['size']
            except IndexError:
                self.regs.A = 0
                self.regs.B = 0
                self.regs.C = 0
                self.regs.X = 0
                self.regs.Y = 0
                self.regs.Z = 0
        else:
            print(f'[{self.TYPE}] Unexpected interruption code: {code}')

    def update_sensor(self, data):
        self.actual_situation = data
