from functools import lru_cache

from constants import LEM1802_FONT, LEM1802_PALETTE
from hardware.common import Hardware


class Display(Hardware):
    """ LEM1802 """
    ID = 0x7349f615
    VERSION = 0x1802
    VENDOR = 0x1c6c8b36
    TYPE = 'display'

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        super().__init__(regs, ram)
        self.video_ram = 0
        self.font_ram = 0
        self.palette_ram = 0
        self.border_color = 0

    def handle_interruption(self):
        code = self.regs.A

        if code == 0:
            self.video_ram = self.regs.B
        elif code == 1:
            self.font_ram = self.regs.B
            # self.get_char.cache_clear()
        elif code == 2:
            self.palette_ram = self.regs.B
            self.load_palette.cache_clear()
        elif code == 3:
            self.border_color = self.regs.B & 0xf
        elif code == 4:
            for i, data in enumerate(LEM1802_FONT):
                self.ram[self.regs.B + i] = data
        elif code == 5:
            for i, data in enumerate(LEM1802_PALETTE):
                self.ram[self.regs.B + i] = data
        else:
            raise Exception(f'[{self.TYPE}] Unexpected interruption code: {code}')

    @lru_cache
    def load_palette(self, rgbfunc):
        """ Convert palette memory to actual colors using rgbfunc """
        data = LEM1802_PALETTE

        if self.palette_ram > 0:
            data = [self.ram[self.palette_ram + i] for i in range(16)]

        palette = []
        for i in range(16):
            val = data[i]
            palette.append(rgbfunc(
                ((val & 0x0f00) >> 8) * 16,
                ((val & 0x00f0) >> 4) * 16,
                (val & 0x000f) * 16
            ))
        return palette

    def get_char(self, char):
        char *= 2
        if self.font_ram == 0:
            hi = LEM1802_FONT[char]
            lo = LEM1802_FONT[char + 1]
        else:
            hi = self.ram[self.font_ram + char]
            lo = self.ram[self.font_ram + char + 1]

        return hi, lo

    def __repr__(self):
        return f'<Display VRAM: 0x{self.video_ram:04x} FRAM: 0x{self.font_ram:04x} ' \
               f'PRAM: 0x{self.palette_ram:04x} Border: 0x{self.border_color:01x}>'
