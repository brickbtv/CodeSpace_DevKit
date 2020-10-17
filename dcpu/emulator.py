import argparse
from collections import defaultdict

from constants import BIN2REGISTERS
from decoder import Decoder


class Operator:
    def __init__(self, op, nw):
        self.op = op
        self.nw = nw


class Instruction:
    def __init__(self, code, cmd, op_b, nw_b, op_a, nw_a):
        self.code = code
        self.cmd = cmd
        self.A = Operator(op_a, nw_a)
        self.B = Operator(op_b, nw_b) if op_b else None


class Registers:
    REGS = ['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']

    def __init__(self):
        self._regs = defaultdict(lambda: 0)

    def __getitem__(self, item):
        return self.__getattr__(item)

    def __setitem__(self, key, value):
        return self.__setattr__(key, value)

    def __getattr__(self, item):
        if item not in self.REGS:
            raise Exception
        return self._regs[item]

    def __setattr__(self, key, value):
        if key == '_regs':
            super.__setattr__(self, key, value)
            return

        if key not in self.REGS:
            raise Exception
        self._regs[key] = value

    def __repr__(self):
        regs_data = ', '.join([f'{reg}=0x{self.__getattr__(reg):04x}' for reg in self.REGS])
        return f'<Registers: {regs_data}>'


class RAM:
    def __init__(self, debug=False):
        self._ram = {}
        self._debug = debug

    def __getitem__(self, item):
        if item not in self._ram:
            self._ram[item] = 0

        if self._debug:
            print('<- [0x{:04x}] - 0x{:04x}'.format(item, self._ram[item]))

        return self._ram[item]

    def __setitem__(self, key, value):
        if self._debug:
            print('-> [0x{:04x}] = 0x{:04x}'.format(key, value))

        self._ram[key] = value


class Emulator:
    def __init__(self, debug):
        self._debug = debug

        self.decoder = Decoder()
        self.ram = RAM(False)
        self.regs = Registers()
        self.regs.SP = 0xffff+1

    def gen_instrucions(self):
        while True:
            code = self.ram[self.regs.PC]
            cmd, op_b, op_a, nw_b, nw_a = self.decoder.describe_instruction(code)

            if nw_a is True:
                self.regs.PC += 1
                nw_a = self.ram[self.regs.PC]

            if nw_b is True:
                self.regs.PC += 1
                nw_b = self.ram[self.regs.PC]

            yield Instruction(code, cmd, op_b, nw_b, op_a, nw_a)

    def run(self, filename):
        print('Loading program to RAM...')
        for pc, code in self.decoder.gen_loader(filename):
            self.ram[pc] = code
        print('Loading done.')

        for instruction in self.gen_instrucions():
            if self._debug:
                self.decoder.print_instruction(instruction, self.regs.PC)

            value_b = self.get_value_from_op(instruction.B, is_a=False)
            value_a = self.get_value_from_op(instruction.A, is_a=True)

            do_not_inc_pc = self.exec_instruction(instruction, value_b, value_a)

            if self._debug:
                print(self.regs)

            if do_not_inc_pc is False:
                self.regs.PC += 1

    def exec_instruction(self, instruction, value_b, value_a):
        cmd = instruction.cmd

        do_not_inc_pc = False
        if cmd == 'SET':
            self.set(instruction.B, value_a)
            if instruction.B.op == 0x1c:  # PC
                do_not_inc_pc = True
        elif cmd == 'ADD':
            self.set(instruction.B, value=value_a + value_b)

            if value_a + value_b > 0xffff:
                self.regs.EX = 0x0001
            else:
                self.regs.EX = 0x0000

        elif cmd == 'SUB':
            self.set(instruction.B, value=value_b - value_a)

            if value_b - value_a < 0x0000:
                self.regs.EX = 0xffff
            else:
                self.regs.EX = 0x0000
        elif cmd == 'MUL' or cmd == 'MLI':  # ?
            self.set(instruction.B, value=value_b * value_a)
            self.regs.EX = ((value_b * value_a) >> 16) & 0xffff
        elif cmd == 'DIV' or cmd == 'DVI':
            if value_a == 0x0:
                self.set(instruction.B, value=0)
            else:
                self.set(instruction.B, value=int(value_b / value_a))
        elif cmd == 'MOD' or cmd == 'MDI':
            if value_a == 0x0:
                self.set(instruction.B, value=0)
            else:
                self.set(instruction.B, value=value_b % value_a)
        elif cmd == 'AND':
            self.set(instruction.B, value=value_b & value_a)
        elif cmd == 'BOR':
            self.set(instruction.B, value=value_b | value_a)
        elif cmd == 'XOR':
            self.set(instruction.B, value=value_b ^ value_a)
        elif cmd == 'SHR':
            self.set(instruction.B, value=value_b >> value_a)
        elif cmd == 'SHL':
            self.set(instruction.B, value=value_b << value_a)

        elif cmd == 'IFB':
            if value_a & value_b == 0:
                self.skip_next_instruction()
        elif cmd == 'IFB':
            if value_a & value_b != 0:
                self.skip_next_instruction()
        elif cmd == 'IFE':
            if value_a != value_b:
                self.skip_next_instruction()
        elif cmd == 'IFN':
            if value_a == value_b:
                self.skip_next_instruction()
        elif cmd == 'IFG' or cmd == 'IFA':
            if value_a <= value_b:
                self.skip_next_instruction()
        elif cmd == 'IFL' or cmd == 'IFU':
            if value_a >= value_b:
                self.skip_next_instruction()

        elif cmd == 'ADX':
            tmp = value_b + value_a + self.regs.EX
            self.set(instruction.B, value=tmp)
            if tmp > 0xffff:
                self.regs.EX = 0x0001
            else:
                self.regs.EX = 0x0000
        elif cmd == 'SBX':
            tmp = value_b - value_a + self.regs.EX
            self.set(instruction.B, value=tmp)
            if tmp < 0x0000:
                self.regs.EX = 0xffff
            else:
                self.regs.EX = 0x0000
        elif cmd == 'STI':
            self.set(instruction.B, value=value_a)
            self.regs.I += 1
            self.regs.J += 1
        elif cmd == 'SDI':
            self.set(instruction.B, value=value_a)
            self.regs.I -= 1
            self.regs.J -= 1

        # special
        elif cmd == 'JSR':
            self.push(self.regs.PC + 1)
            self.regs.PC = instruction.A.nw
            do_not_inc_pc = True

        elif cmd == 'INT':
            print(' ** todo **')
            pass
        elif cmd == 'IAG':
            self.set(instruction.A, value=self.regs.IA)
        elif cmd == 'IAS':
            self.regs.IA = value_a
        elif cmd == 'RFI':
            print(' ** todo **')
            self.regs.A = self.pop()
            self.regs.PC = self.pop()
            do_not_inc_pc = True
        elif cmd == 'IAQ':
            print(' ** todo **')
            pass
        elif cmd == 'HWN':
            print(' ** todo **')
            pass
        elif cmd == 'HWQ':
            print(' ** todo **')
            pass
        elif cmd == 'HWI':
            print(' ** todo **')
            pass
        else:
            raise Exception
        return do_not_inc_pc

    def skip_next_instruction(self):
        code = self.ram[self.regs.PC + 1]
        cmd, op_b, op_a, nw_b, nw_a = self.decoder.describe_instruction(code)
        skip = 1
        if nw_a:
            skip += 1
        if nw_b:
            skip += 1

        self.regs.PC += skip

    def set(self, operator: Operator, value=None):
        op = operator.op
        nw = operator.nw
        if 0x00 <= op <= 0x07:
            self.regs[BIN2REGISTERS[op]] = value
        elif 0x08 <= op <= 0x0f:
            self.ram[self.regs[BIN2REGISTERS[op - 0x08]]] = value
        elif 0x10 <= op <= 0x17:
            self.ram[self.regs[BIN2REGISTERS[op - 0x10] + nw]] = value
        elif op == 0x18:
            self.push(value)
        elif op == 0x19:
            self.ram[self.regs.SP] = value
        elif op == 0x1a:
            self.ram[self.regs.SP + nw] = value
        elif 0x1b <= op <= 0x1d:
            self.regs[BIN2REGISTERS[op]] = value
        elif op == 0x1e:
            self.ram[nw] = value
        elif op == 0x1f:
            raise Exception
        else:
            raise Exception

    def get_value_from_op(self, operator, is_a=False):
        if operator is None:
            return None

        op = operator.op
        nw = operator.nw

        if 0x00 <= op <= 0x07:
            return self.regs[BIN2REGISTERS[op]]
        elif 0x08 <= op <= 0x0f:
            return self.ram[self.regs[BIN2REGISTERS[op - 0x08]]]
        elif 0x10 <= op <= 0x17:
            return self.ram[self.regs[BIN2REGISTERS[op - 0x10] + nw]]
        elif op == 0x18:
            return self.pop() if is_a else None
        elif op == 0x19:
            return self.peek()
        elif op == 0x1a:
            return self.peek(nw)
        elif 0x1b <= op <= 0x1d:
            return self.regs[BIN2REGISTERS[op]]
        elif op == 0x1e:
            return self.ram[nw]
        elif op == 0x1f:
            return nw
        else:
            raise Exception

    def push(self, value):
        self.regs.SP -= 1
        self.ram[self.regs.SP] = value
        self._dump_stack()

    def pop(self):
        self._dump_stack()
        value = self.ram[self.regs.SP]
        self.regs.SP += 1
        return value

    def peek(self, n=0):
        return self.ram[self.regs.SP + n]

    def _dump_stack(self):
        i = 0xffff
        print('Stack: ')

        while i >= self.regs.SP:
            pointer = '<--------------' if i == self.regs.SP else ''

            print(f'[0x{i:04x}] 0x{self.ram[i]:04x} {pointer}')
            i -= 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    e = Emulator(args.debug)
    e.run(args.filename)
