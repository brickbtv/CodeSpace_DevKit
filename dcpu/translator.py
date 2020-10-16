import argparse
from enum import Enum

from constants import MNEMONIC_TO_CODE, SPECIAL_MNEMONICS_TO_CODE, REGISTERS


class OperandType(Enum):
    UNKNOWN = -1
    NONE = 1
    REGISTER = 2
    DECIMAL = 3
    HEX = 4
    REGISTER_POINTER = 5
    REGISTER_PLUS_NEXT_WORD = 6
    LABEL = 7
    LABEL_POINTER = 8
    STRING = 9

    @staticmethod
    def determine(operand: str, labels: dict):
        if operand is None:
            return OperandType.NONE
        elif operand in REGISTERS:
            return OperandType.REGISTER
        elif operand.isdigit():
            return OperandType.DECIMAL
        elif operand.startswith('0x'):
            return OperandType.HEX
        elif operand[0] == '[' and operand[-1] == ']' and '+' in operand:
            return OperandType.REGISTER_PLUS_NEXT_WORD
        elif operand in labels:
            return OperandType.LABEL
        elif operand[0] == '[' and operand[-1] == ']':
            operand = operand[1:-1]
            if operand in REGISTERS:
                return OperandType.REGISTER_POINTER

            if operand in labels:
                return OperandType.LABEL_POINTER

        elif operand.startswith(('"', "'")) and operand.endswith(('"', "'")):
            return OperandType.STRING

        return OperandType.UNKNOWN


class DCPUTranslator:
    """ .dcpu16 -> .bin """

    OPCODE_LEN = 3

    def parse_line(self, line: str):
        command, args = line[:self.OPCODE_LEN], line[self.OPCODE_LEN:]

        params = args.split(',')[:2]

        param_1 = params[0].strip() if len(params) >= 1 else None
        param_2 = params[1].strip() if len(params) == 2 else None

        return command.strip().upper(), param_1, param_2

    def extract_labels(self, filename):
        with open(filename, 'r') as f:
            return {line.strip()[1:]: 0 for line in f.readlines() if line.startswith(':')}

    def operand2bin(self, operand: str, labels: dict):
        operand_type = OperandType.determine(operand, labels)

        if operand_type is OperandType.NONE:
            return 0, None
        elif operand_type is OperandType.REGISTER:
            return REGISTERS[operand], None
        elif operand_type is OperandType.DECIMAL:
            return 0x1f, int(operand)
        elif operand_type is OperandType.HEX:
            return 0x1f, int(operand, 16)
        elif operand_type is OperandType.REGISTER_POINTER:
            return 0x08 + REGISTERS.get(operand[1:-1]), None
        elif operand_type is OperandType.REGISTER_PLUS_NEXT_WORD:
            reg, label = operand[1:-1].split('+')[:2]
            return 0x10 + REGISTERS.get(reg.strip()), labels.get(label.strip())
        elif operand_type is OperandType.LABEL:
            return 0x1f, labels.get(operand)
        elif operand_type is OperandType.LABEL_POINTER:
            return 0x1e, labels.get(operand[1:-1])

        raise Exception

    def gen_lines(self, filename):
        with open(filename, 'r') as f:
            for line in f.readlines():
                line = line.strip()
                if not line or line.startswith(';'):
                    continue

                if line.startswith(':'):
                    yield line, '__LABEL', line.strip()[1:], None
                    continue

                cmd, param1, param2 = self.parse_line(line)
                yield line, cmd, param1, param2

    def asm2bin(self, filename):
        relocations, _ = self.translate(filename, relocations_info=None)
        _, program = self.translate(filename, relocations_info=relocations)
        # from pprint import pprint
        # pprint(relocations)

        return program

    def translate(self, filename, relocations_info=None):
        if relocations_info is None:
            relocations_info = self.extract_labels(filename)

        labels_addr = {}

        program = []

        label_pc = 0
        for line, cmd, param1, param2 in self.gen_lines(filename):
            # pseudo command for symbol names translation
            if cmd == '__LABEL':
                labels_addr[param1] = label_pc
                continue

            if cmd == 'DAT':
                instructions = []
                for param in [param1, param2]:
                    data_type = OperandType.determine(param, labels={})

                    if data_type is OperandType.DECIMAL:
                        instructions.append(int(param))
                    elif data_type is OperandType.HEX:
                        instructions.append(int(param, 16))
                    elif data_type is OperandType.STRING:
                        for c in param[1:-1]:
                            instructions.append(ord(c))

                if instructions:
                    program.append((line, instructions))

                label_pc += len(instructions)

                continue

            is_basic_op = True
            code = MNEMONIC_TO_CODE.get(cmd)
            if not code:
                code = SPECIAL_MNEMONICS_TO_CODE.get(cmd) << 5
                is_basic_op = False

            param1coded, nw1 = self.operand2bin(param1, relocations_info)
            param2coded, nw2 = self.operand2bin(param2, relocations_info)

            if is_basic_op:
                code = code | param1coded << 5 | param2coded << 10
            else:
                code = code | param1coded << 10

            instructions = [code]

            if nw2 is not None:
                instructions.append(nw2)

            if nw1 is not None:
                instructions.append(nw1)

            program.append((line, instructions))

            label_pc += len(instructions)

        return labels_addr, program


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    translator = DCPUTranslator()
    if args.debug:
        print('PC     HEX    BIN                ASM')
        pc = 0
        for line, instructions in translator.asm2bin(args.filename):
            for instruction_num, code in enumerate(instructions):
                if instruction_num == 0:
                    print('0x{:04x}'.format(pc), '0x{:04x}'.format(code), '0x{:016b}'.format(code), line)
                else:
                    print('0x{:04x}'.format(pc), '0x{:04x}'.format(code), '0x{:016b}'.format(code))

                pc += 1

    if args.output:
        print('Translation started')
        with open(args.output, 'wb') as f:
            for line, instructions in translator.asm2bin(args.filename):
                for code in instructions:
                    f.write(code.to_bytes(2, byteorder='little'))

        print('Translation done')
