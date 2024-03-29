import argparse
import os
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
    BINARY = 10
    MEM_ADDRESS = 11

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
        elif operand.startswith('0b'):
            return OperandType.BINARY
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

            return OperandType.MEM_ADDRESS

        elif operand.startswith(('"', "'")) and operand.endswith(('"', "'")):
            return OperandType.STRING

        return OperandType.UNKNOWN


class TranslationError(Exception):
    def __init__(self, file, line, message):
        super().__init__()
        self.file = file
        self.line = line
        self.message = message


class DCPUTranslator:
    """ .dcpu16 -> .bin """

    OPCODE_LEN = 3

    def parse_line(self, line: str):
        line = line.strip()
        command, args = line[:self.OPCODE_LEN], line[self.OPCODE_LEN:]

        params = args.split(',')

        param_1 = params[0].strip() if len(params) >= 1 else None
        param_2 = params[1].strip() if len(params) == 2 else None

        if len(params) > 2:
            param_1 = [p.strip() for p in params]

        return command.strip().upper(), param_1, param_2

    def extract_labels(self, workdir, filename):
        with open(os.path.join(workdir, filename), 'r') as f:
            labels = {}
            for line in f.readlines():
                line = line.strip()
                if line.startswith(':'):
                    other_instr = line.find(' ')
                    if other_instr != -1:
                        labels[line[1:other_instr]] = 0
                    else:
                        labels[line[1:]] = 0

                if line.startswith('.include '):
                    if ';' in line:
                        line = line[0:line.find(';')]

                    include_file = line[len('.include '):].strip()
                    include_file = include_file[1:-1]
                    labels.update(self.extract_labels(workdir, include_file))

            return labels

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
        elif operand_type is OperandType.BINARY:
            return 0x1f, int(operand, 2)
        elif operand_type is OperandType.REGISTER_POINTER:
            return 0x08 + REGISTERS.get(operand[1:-1]), None
        elif operand_type is OperandType.REGISTER_PLUS_NEXT_WORD:
            reg, label = operand[1:-1].split('+')[:2]
            return 0x10 + REGISTERS.get(reg.strip()), labels.get(label.strip())
        elif operand_type is OperandType.LABEL:
            return 0x1f, labels.get(operand)
        elif operand_type is OperandType.LABEL_POINTER:
            return 0x1e, labels.get(operand[1:-1])
        elif operand_type is OperandType.MEM_ADDRESS:
            return 0x1e, int(operand[1:-1], 16)

        raise Exception

    def gen_lines(self, workdir, filename):
        with open(os.path.join(workdir, filename), 'r') as f:
            for line_num, line in enumerate(f.readlines()):
                line = line.strip()

                pos = line.find(';')
                if pos >= 0:
                    line = line[:pos]
                    line = line.strip()

                if not line or line.startswith(';'):
                    continue

                if line.startswith('.include '):
                    include_file = line[len('.include '):].strip()
                    include_file = include_file[1:-1]
                    for inc_filename, inc_linenum, inc_line, cmd, param1, param2 in self.gen_lines(workdir, include_file):
                        yield inc_filename, inc_linenum, inc_line, cmd, param1, param2

                    continue

                if line.startswith(':'):
                    other_command = line.find(' ')

                    if other_command != -1:
                        yield filename, line_num, line, '__LABEL', line.strip()[1:other_command], None
                        line = line[other_command:]
                    else:
                        yield filename, line_num, line, '__LABEL', line.strip()[1:], None
                        continue

                cmd, param1, param2 = self.parse_line(line)
                yield filename, line_num, line, cmd, param1, param2

    def asm2bin(self, workdir, filename):
        relocations, _ = self.translate(workdir, filename, relocations_info=None)
        _, program = self.translate(workdir, filename, relocations_info=relocations)

        return program

    def translate(self, workdir, filename, relocations_info=None, dat_labels_out=None):
        if relocations_info is None:
            relocations_info = self.extract_labels(workdir, filename)

        labels_addr = {}

        program = []

        label_pc = 0
        prev_cmd = ''
        prev_label = ''
        for resolver_filename, line_num, line, cmd, param1, param2 in self.gen_lines(workdir, filename):
            try:
                # pseudo command for symbol names translation
                if cmd == '__LABEL':
                    labels_addr[param1] = label_pc
                    if dat_labels_out is not None:
                        prev_label = param1
                        prev_cmd = cmd
                    continue

                if cmd == 'DAT':
                    # store DAT labels
                    if prev_cmd == '__LABEL' and dat_labels_out is not None:
                        dat_labels_out.append(prev_label)

                    instructions = []

                    params = [param1, param2]
                    if isinstance(param1, list):
                        params = param1

                    for param in params:
                        data_type = OperandType.determine(param, labels={})

                        if data_type is OperandType.DECIMAL:
                            instructions.append(int(param))
                        elif data_type is OperandType.HEX:
                            instructions.append(int(param, 16))
                        elif data_type is OperandType.STRING:
                            for c in param[1:-1]:
                                instructions.append(ord(c))

                    if instructions:
                        program.append((resolver_filename, line_num, line, instructions))

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

                program.append((resolver_filename, line_num, line, instructions))

                label_pc += len(instructions)

                prev_cmd = cmd
            except Exception as ex:
                raise TranslationError(
                    resolver_filename,
                    line_num,
                    f'FILE: {resolver_filename}    LINE:  {line_num}     {line}    ERROR: {ex}',
                )

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
        for _, line_num, line, instructions in translator.asm2bin('', args.filename):
            for instruction_num, code in enumerate(instructions):
                if instruction_num == 0:
                    print('0x{:04x}'.format(pc), '0x{:04x}'.format(code), '0x{:016b}'.format(code), line)
                else:
                    print('0x{:04x}'.format(pc), '0x{:04x}'.format(code), '0x{:016b}'.format(code))

                pc += 1

    if args.output:
        print('Translation started')
        with open(args.output, 'wb') as f:
            for _, __, line, instructions in translator.asm2bin('', args.filename):
                for code in instructions:
                    f.write(code.to_bytes(2, byteorder='little'))

        print('Translation done')
