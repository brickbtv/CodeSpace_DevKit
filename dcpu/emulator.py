import argparse

from constants import BIN2REGISTERS
from decoder import Decoder


class Registers:
    def __init__(self):
        pass

    def _g_temh


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
        self.ram = RAM(debug)
        self.regs = {reg: 0x0 for reg in ['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX']}
        self.regs['SP'] = 0xffff

    def run(self, filename):
        if self._debug:
            print('Loading program to RAM...')

        for pc, code in self.decoder.gen_loader(filename):
            self.ram[pc] = code

        if self._debug:
            print('Loading done.')

        while True:
            code = self.ram[self.regs['PC']]
            cmd, op_b, op_a, nw_b, nw_a = self.decoder.describe_instruction(code)

            if nw_a is True:
                self.regs['PC'] += 1
                nw_a = self.ram[self.regs['PC']]

            if nw_b is True:
                self.regs['PC'] += 1
                nw_b = self.ram[self.regs['PC']]

            if self._debug:
                print('Executing 0x{:04x} "{} {} {} {} {}"'.format(self.regs['PC'], cmd, op_b, op_a, nw_b, nw_a))

                if cmd == 'SET':
                    self.set(op_b, op_a, nw_b, nw_a)
                elif cmd == 'JSR':
                    self.push(self.regs['PC'] + 1)
                    self.regs['PC'] = nw_a
                    continue
                elif cmd == 'ADD':
                    value_b = self.get_value_from_op(nw_b, op_b)
                    value_a = self.get_value_from_op(nw_a, op_a)
                    self.set(op_b, nw_b, exact_value=value_a + value_b)
                else:
                    raise Exception

            print(self.regs)
            self.regs['PC'] += 1

    def set(self, op_b, op_a=None, nw_b=None, nw_a=None, exact_value=None):
        value = self.get_value_from_op(nw_a, op_a)
        if exact_value:
            value = exact_value

        if 0x00 <= op_b <= 0x07:
            self.regs[BIN2REGISTERS[op_b]] = value
        elif 0x08 <= op_b <= 0x0f:
            self.ram[self.regs[BIN2REGISTERS[op_b]]] = value
        elif 0x10 <= op_b <= 0x17:
            self.ram[self.regs[BIN2REGISTERS[op_b] + nw_b]] = value
        elif op_b == 0x18:
            self.push(value)
        elif op_b == 0x19:
            self.ram[self.regs['SP']] = value
        elif op_b == 0x1a:
            self.ram[self.regs['SP'] + nw_b] = value
        elif 0x1b <= op_b <= 0x1d:
            self.regs[BIN2REGISTERS[op_b]] = value
        elif op_b == 0x1e:
            self.ram[nw_b] = value
        elif op_b == 0x1f:
            raise Exception
        else:
            raise Exception

    def get_value_from_op(self, nw_a, op_a):
        if 0x00 <= op_a <= 0x07:
            value = self.regs[BIN2REGISTERS[op_a]]
        elif 0x08 <= op_a <= 0x0f:
            value = self.ram[self.regs[BIN2REGISTERS[op_a]]]
        elif 0x10 <= op_a <= 0x17:
            value = self.ram[self.regs[BIN2REGISTERS[op_a] + nw_a]]
        elif op_a == 0x18:
            value = self.pop()
        elif op_a == 0x19:
            value = self.peek()
        elif op_a == 0x1a:
            value = self.peek(nw_a)
        elif 0x1b <= op_a <= 0x1d:
            value = self.regs[BIN2REGISTERS[op_a]]
        elif op_a == 0x1e:
            value = self.ram[nw_a]
        elif op_a == 0x1f:
            value = nw_a
        else:
            raise Exception
        return value

    def push(self, value):
        self.regs['SP'] -= 1
        self.ram[self.regs['SP']] = value

    def pop(self):
        value = self.ram[self.regs['SP']]
        self.regs['SP'] += 1
        return value

    def peek(self, n=0):
        return self.ram[self.regs['SP'] + n]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    e = Emulator(args.debug)
    e.run(args.filename)
