import argparse
from enum import Enum

from constants import BIN2OPCODE, BIN2SPECTIAL, BIN2REGISTERS


class InstructionType(Enum):
    BASIC = 1
    SPECIAL = 2
    DATA = 3

    @staticmethod
    def determine(code):
        if (code & 0xff00) >> 8 == 0:
            return InstructionType.DATA

        if (code & 0x1f) != 0:
            return InstructionType.BASIC
        else:
            return InstructionType.SPECIAL

class Decoder:
    def is_instruction_basic(self, code) -> bool:
        return (code & 0x1f) != 0

    def gen_instructions(self, filename):
        pc = 0
        with open(filename, 'rb') as f:
            code = f.read(2)
            while code:
                code = int.from_bytes(code, "little")

                instruction_type = InstructionType.determine(code)

                if instruction_type is InstructionType.BASIC:
                    opcode = code & 0x1f
                    operand_b = (code & 0x3e0) >> 5
                    operand_a = (code & 0xfc00) >> 10

                    cmd = BIN2OPCODE[opcode]

                elif instruction_type is InstructionType.SPECIAL:
                    opcode = (code & 0x3e0) >> 5
                    operand_b = None
                    operand_a = (code & 0xfc00) >> 10

                    cmd = BIN2SPECTIAL[opcode]
                elif instruction_type is InstructionType.DATA:
                    yield pc, code, 'DAT', None, None, None, None
                    pc += 1
                    code = f.read(2)
                    continue

                nw1 = nw2 = None

                if instruction_type is InstructionType.BASIC and operand_b == 0x1e:
                    pc += 1
                    nw2 = int.from_bytes(f.read(2), "little")

                if operand_a == 0x1f:
                    pc += 1
                    nw1 = int.from_bytes(f.read(2), "little")

                yield pc, code, cmd, operand_b, operand_a, nw2, nw1
                code = f.read(2)

    def decode(self, filename):
        for pc, code, cmd, op_b, op_a, nw_b, nw_a in self.gen_instructions(filename):
            if cmd == 'DAT':
                self.print_dat(code, pc)
                continue

            self.print_instruction(cmd, code, nw_a, nw_b, op_a, op_b, pc)

    def print_instruction(self, cmd, code, nw_a, nw_b, op_a, op_b, pc):
        ops = ''
        ops += '0x{:02x} '.format(op_b) if op_b else ''
        ops += '0x{:02x}'.format(op_a) if op_a else ''

        next_words = ''
        next_words += '0x{:04x} '.format(nw_b) if nw_b else ''
        next_words += '0x{:04x}'.format(nw_a) if nw_a else ''
        next_words = '[{}]'.format(next_words) if next_words else ''

        print(
            '0x{:04x}'.format(pc),
            '0x{:04x} 0x{:016b}'.format(code, code),
            cmd, ops, next_words,
        )

    def print_dat(self, code, pc):
        print(
            '0x{:04x}'.format(pc),
            '0x{:04x} 0x{:016b}'.format(code, code),
            chr(code) if code >= ord(' ') else '0x{:02x}'.format(code)
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    d = Decoder()
    d.decode(args.filename)
