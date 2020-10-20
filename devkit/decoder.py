import argparse
from enum import Enum
from typing import Optional

from constants import BIN2OPCODE, BIN2SPECTIAL, BIN2REGISTERS
from instuction import Instruction


class DescribeException(Exception):
    pass


class InstructionType(Enum):
    BASIC = 1
    SPECIAL = 2
    DATA = 3

    @staticmethod
    def determine(code, disasm=False):
        """ Determine instruction type.

        There are no way to predict DAT words, so code logic relates to
        `disasm` parameter:

        - True: try to figure out the DAT words (disassemble mode)
        - False: detect all words as valid opcodes (emulation mode)

        :param code: word
        :param disasm: is disasm mode or not
        """
        if disasm is True:
            if (code & 0xff00) >> 8 == 0:
                 return InstructionType.DATA

        if (code & 0x1f) != 0:
            return InstructionType.BASIC
        else:
            return InstructionType.SPECIAL


def need_next_word(operand: Optional[int]) -> bool:
    """ Detects next word demand for operand.
    :param operand: operand or None if not present
    :return: bool
    """
    if operand is None:
        return False

    return operand in {0x1a, 0x1f, 0x1e} or 0x10 <= operand <= 0x17


def describe_instruction(code, disasm=False) -> (str, int, int, bool, bool):
    """ Decodes instruction first word:

    - detect basic/special opcode or DAT
    - decodes operands:
        * (b, a) for basic
        * (a) for special
    - determines next word requirement for operand a and b if present

    :param code: word
    :param disasm: detect DAT instructions or not
    :return:
        mnemonic, operand A, operand B, next word for A (True/False), next word for B (True/False)
    """

    instruction_type = InstructionType.determine(code, disasm=disasm)

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
        if disasm:
            return 'DAT', None, None, None, None

        raise DescribeException

    return cmd, operand_b, operand_a, need_next_word(operand_b), need_next_word(operand_a)


def load_bin_file(filename):
    """ Load .bin from disk, and gen words one by one

    :param filename: .bin location
    """
    pc = 0
    with open(filename, 'rb') as f:
        code = f.read(2)
        while code:
            yield pc, int.from_bytes(code, "little")
            code = f.read(2)
            pc += 1


def gen_instructions(filename):
    """ Reads .bin from file and decode whole instructions (1-3 words)

    Produces Instruction objects.

    :param filename: .bin location
    """

    words = load_bin_file(filename)

    for pc, code in words:
        cmd, operand_b, operand_a, nw2, nw1 = describe_instruction(code, disasm=True)

        try:
            if nw1:
                _, nw1 = next(words)

            if nw2:
                _, nw2 = next(words)
        except StopIteration:
            # last instruction in the file (possible DAT) looks like
            # an instruction with next words.
            # return it like DAT
            yield pc, Instruction(code, 'DAT', None, None, None, None)
            break

        yield pc, Instruction(code, cmd, operand_b, nw2, operand_a, nw1)


def to_human_readable(instruction: Instruction, pc: int, extended=True):
    """ Present instruction like

       "CMD B, A"
    or "CMD B"
    or "DAT x"

    :param instruction: fully decoded instruction
    :param pc: PC value
    :param extended: add prefix with PC + instruction HEX + instruction BIN
    :return: human readable representation of instruction
    """
    if instruction.cmd == 'DAT':
        return to_human_readable_dat(instruction.code, pc, extended)

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
            return to_human_readable_dat(instruction.code, pc, extended)

        ops += value + ' '

    prefix = ''
    if extended:
        code = instruction.code
        prefix = f'0x{pc:04x} 0x{code:04x} 0x{code:016b}'

    return f'{prefix} {instruction.cmd} {ops}'


def to_human_readable_dat(code, pc, extended=True):
    data = chr(code) if 255 >= code >= 32 else f'0x{code:02x}'
    prefix = ''
    if extended:
        prefix = f'0x{pc:04x} 0x{code:04x} 0x{code:016b}'
    return f'{prefix} {data}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    for pc, instruction in gen_instructions(args.filename):
        print(to_human_readable(instruction, pc))
