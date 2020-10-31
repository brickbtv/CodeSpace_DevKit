from hardware import Registers, RAM
from hardware.common import Hardware


class Anthenna(Hardware):
    """
        Antenna
        =======

        Hardware-ID    : 0x74cfc5a3
        Version        : 0x0007
        Manufacturer-ID: 0x54482b2b

        A  | Function
        ===+===============================================================
        0  | Set interrupt message to B. B = 0 disables interrupts.
           | Antenna will request an interrupt every time it receives
           | one or more messages. More than one message may be received
           | at a time.
        ---+---------------------------------------------------------------
        1  | Set current channel to B (hi word), C (lo word).
        ---+---------------------------------------------------------------
        2  | Get current channel in B (hi word), C (lo word).
        ---+---------------------------------------------------------------
        3  | Send I words starting at memory address B. I must be in
           | range 1-256 inclusive. Operation takes I cycles to complete.
        ---+---------------------------------------------------------------
        4  | Retrieve next message from receive buffer and write it into
           | memory starting at B. Sets I to the number of received words.
           | Messages are guaranteed to be 1-256 words in length.
           | Sets X to the signal strength. Sets Y to the direction of
           | the sender relative to the antennas orientation.
           | If no message was in the buffer, sets I, X and Y to 0.
           | Operation takes I cycles to complete.
        ---+---------------------------------------------------------------
        5  | Clears the receive buffer.
        ---+---------------------------------------------------------------
        """

    ID = 0x74CFC5A3
    VERSION = 0x0001
    VENDOR = 0x54482b2b
    TYPE = 'anthenna'

    def __init__(self, regs: Registers, ram: RAM):
        super().__init__(regs, ram)
        # TODO: a variable amount of clams

        self.channel = 0
        self.send_buffer = []
        self.recv_buffer = []

        self.irq_enabled = False
        self.irq_code = None
        self.interruptions = []

    def handle_interruption(self):
        code = self.regs.A
        if code == 0:
            self.irq_code = self.regs.B
            self.irq_enabled = bool(self.irq_code != 0)
        elif code == 1:
            self.channel = (self.regs.B << 16) & self.regs.C
        elif code == 2:
            self.regs.B = self.channel >> 16
            self.regs.C = self.channel & 0xffff
        elif code == 3:
            words = min(256, self.regs.I)

            self.send_buffer.append(self.ram[self.regs.B + i] for i in range(words))
        elif code == 4:
            if not self.recv_buffer:
                self.regs.I = 0
                self.regs.X = 0
                self.regs.Y = 0

                return

            msg = self.recv_buffer[0]
            self.regs.I = len(msg)
            self.regs.X = 0x0001
            self.regs.Y = 0x0001

            for i, word in enumerate(msg):
                self.ram[self.regs.B + i] = word
        elif code == 5:
            self.recv_buffer = []
        else:
            raise Exception(
                f'[{self.TYPE}] Unexpected interruption code: {code}')

    def recv_message(self, data):
        assert isinstance(data, list)
        self.recv_buffer.append(data)
