import argparse
from enum import Enum

from constants import BIN2OPCODE, BIN2SPECTIAL, BIN2REGISTERS
from instuction import Instruction


class InstructionType(Enum):
    BASIC = 1
    SPECIAL = 2
    DATA = 3

    @staticmethod
    def determine(code, exec_mode=False):
        if exec_mode is False:
            if (code & 0xff00) >> 8 == 0:
                 return InstructionType.DATA

        if (code & 0x1f) != 0:
            return InstructionType.BASIC
        else:
            return InstructionType.SPECIAL


class Decoder:
    def describe_instruction(self, code):
        instruction_type = InstructionType.determine(code, exec_mode=True)

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
        else:
            raise Exception

        nw1 = nw2 = False

        if instruction_type is InstructionType.BASIC and (operand_b in (0x1a, 0x1e, 0x1f) or 0x10 <= operand_b <= 0x17):
            nw2 = True

        if operand_a in {0x1a, 0x1f, 0x1e} or 0x10 <= operand_a <= 0x17:
            nw1 = True

        return cmd, operand_b, operand_a, nw2, nw1

    def gen_loader(self, filename):
        pc = 0
        with open(filename, 'rb') as f:
            code = f.read(2)
            while code:
                yield pc, int.from_bytes(code, "little")
                code = f.read(2)
                pc += 1

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
                    yield pc, Instruction(code, 'DAT', None, None, None, None)
                    pc += 1
                    code = f.read(2)
                    continue

                nw1 = nw2 = None

                orig_pc = pc

                if operand_a in {0x1a, 0x1f, 0x1e} or 0x10 <= operand_a <= 0x17:
                    pc += 1
                    nw1 = int.from_bytes(f.read(2), "little")

                if instruction_type is InstructionType.BASIC and (operand_b in (0x1a, 0x1e, 0x1f) or 0x10 <= operand_b <= 0x17):
                    pc += 1
                    nw2 = int.from_bytes(f.read(2), "little")

                yield orig_pc, Instruction(code, cmd, operand_b, nw2, operand_a, nw1)
                pc += 1
                code = f.read(2)

    @staticmethod
    def print_instruction(instruction, pc, extended=True):

        if instruction.cmd == 'DAT':
            return Decoder.print_dat(instruction.code, pc, extended)

        ops = ''
        for operator, is_a in [
            (instruction.B, False),
            (instruction.A, True),
        ]:
            if operator is None:
                continue

            op = operator.op
            nw = operator.nw

            if 0x00 <= op <= 0x07:
                value = BIN2REGISTERS[op]
            elif 0x08 <= op <= 0x0f:
                value = f'[{BIN2REGISTERS[op-0x08]}]'
            elif 0x10 <= op <= 0x17:
                value = f'[{BIN2REGISTERS[op-0x10]} + 0x{nw:04x}]'
            elif op == 0x18:
                value = 'POP' if is_a else 'PUSH'
            elif op == 0x19:
                value = 'PEEK'
            elif op == 0x1a:
                value = f'PEEK 0x{nw:04x}'
            elif 0x1b <= op <= 0x1d:
                value = BIN2REGISTERS[op]
            elif op == 0x1e:
                value = f'[0x{nw:04x}]'
            elif op == 0x1f:
                value = f'0x{nw:04x}'
            elif op == 0x20:
                value = '0xffff'
            elif 0x21 <= op <= 0x3f:
                value = f'{op - 0x21}'
            else:
                # raise Exception
                return Decoder.print_dat(instruction.code, pc, extended)

            ops += value + ' '

        code = instruction.code

        prefix = ''
        if extended:
            prefix = f'0x{pc:04x} 0x{code:04x} 0x{code:016b}'
        return f'{prefix} {instruction.cmd} {ops}'

    @staticmethod
    def print_dat(code, pc, extended=True):
        data = chr(code) if code >= ord(' ') else f'0x{code:02x}'
        prefix = ''
        if extended:
            prefix = f'0x{pc:04x} 0x{code:04x} 0x{code:016b}'
        return f'{prefix} {data}'

    def decode_and_print(self, filename):
        for pc, instruction in self.gen_instructions(filename):
            if instruction.cmd == 'DAT':
                print(self.print_dat(instruction.code, pc))
                continue

            print(self.print_instruction(instruction, pc))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    d = Decoder()
    d.decode_and_print(args.filename)
