from constants import LEM1802_FONT, LEM1802_PALETTE


class Hardware:
    ID = None
    VERSION = None
    VENDOR = None

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        self.regs = regs
        self.ram = ram

    def interrupt(self):
        raise NotImplemented


class Display(Hardware):
    """LEM1802"""
    ID = 0x7349f615
    VERSION = 0x1802
    VENDOR = 0x1c6c8b36

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        super().__init__(regs, ram)
        self.vram = 0
        self.fram = 0
        self.pram = 0
        self.border_color = 0

    def interrupt(self):
        code = self.regs.A

        if code == 0:
            self.vram = self.regs.B
        elif code == 1:
            self.fram = self.regs.B
        elif code == 2:
            self.pram = self.regs.B
        elif code == 3:
            self.border_color = self.regs.B
        elif code == 4:
            for i, data in enumerate(LEM1802_FONT):
                self.ram[self.regs.B + i] = data
        elif code == 5:
            for i, data in enumerate(LEM1802_PALETTE):
                self.ram[self.regs.B + i] = data
        else:
            raise Exception

    def dump(self):
        print('-'*32)
        for y in range(12):
            for x in range(32):
                data = self.ram[self.vram + x + y*32]
                print(chr(data & 0xff), end='')
            print()
        print('-'*32)


class Keyboard(Hardware):
    """"""
    ID = 0x30cf7406
    VERSION = 0x1
    VENDOR = 0x0

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        super().__init__(regs, ram)
        self.buffer = []
        self.irq_enabled = False
        self.irq_code = None
        self.int_counter = 0

    def interrupt(self):
        code = self.regs.A
        if code == 0:
            self.buffer = []
        elif code == 1:
            if self.buffer:
                self.regs.C = self.buffer[0]
                self.buffer = self.buffer[1:]
            else:
                self.regs.C = 0
        elif code == 2:
            if self.buffer and self.buffer[0] == self.regs.B:
                self.regs.C = 1
                self.buffer = self.buffer[1:]
            else:
                self.regs.C = 0
        elif code == 3:
            if self.regs.B == 0:
                self.irq_enabled = False
                self.irq_code = None
            else:
                self.irq_enabled = True
                self.irq_code = self.regs.B

    def add_key(self, key):
        if key:
            self.buffer.append(key)

        if self.irq_enabled:
            self.int_counter += 1


class Thruster(Hardware):
    ID = 0xa4748683
    VERSION = 0x0001
    VENDOR = 0x54482b2b

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        super().__init__(regs, ram)
        self.power = 0

    def interrupt(self):
        code = self.regs.A
        if code == 0:
            self.power = self.regs.B & 0xff
            # print(self.power)
