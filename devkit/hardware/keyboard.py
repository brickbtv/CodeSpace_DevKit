from hardware.common import Hardware


class Keyboard(Hardware):
    """ Generic Keyboard (compatible) """
    ID = 0x30cf7406
    VERSION = 0x1
    VENDOR = 0x0

    def __init__(self, regs: 'Registers', ram: 'RAM'):
        super().__init__(regs, ram)
        self.buffer = []
        self.irq_enabled = False
        self.irq_code = None
        self.pressed_keys = set()

        self.interruptions = []

    def handle_interruption(self):
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
            if self.regs.B in self.pressed_keys:
                self.regs.C = 1
            else:
                self.regs.C = 0
        elif code == 3:
            if self.regs.B == 0:
                self.irq_enabled = False
                self.irq_code = None
            else:
                self.irq_enabled = True
                self.irq_code = self.regs.B
        else:
            raise Exception(f'Unexpected interruption code: {code}')

    def handle_key_event(self, key, pressed: bool):
        """ Manage keyboard events.

        :param key: Key code. Special keys must be mapped already.
        :param pressed: Is button pressed? Used for A==2 interruption.
        """
        if pressed:
            self.buffer.append(key)
            self.pressed_keys.add(key)
        else:
            if key in self.pressed_keys:
                self.pressed_keys.remove(key)

        if self.irq_enabled:
            self.interruptions.append(self.irq_code)

    def __repr__(self):
        return f'<Keyboard IntQueue: {len(self.interruptions)} Buffer: {"".join(self.buffer)}>'
