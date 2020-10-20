import argparse
from functools import wraps

from constants import BIN2REGISTERS
from decoder import load_bin_file, to_human_readable, to_human_readable_dat, describe_instruction
from hardware import Display, Keyboard, RAM, Registers, Sensor, Thruster
from instuction import Operator, Instruction


HANDLERS = {}


def instruction(func):
    """ Decorator for instructions.

        Wrapped function should return bool value, which means to
        increase PC counter or not after performing the instruction.

        Defaults to False.
    """
    @wraps(func)
    def wrapper(self, instruction: Instruction, value_b: int, value_a: int):
        do_increase_pc = func(self, instruction, value_b, value_a)
        if do_increase_pc is None:
            return False

        return do_increase_pc

    HANDLERS[func.__name__.replace('_', '').upper()] = wrapper
    return wrapper


class Emulator:
    def __init__(self, debug):
        self._debug = debug

        self.ram = RAM()
        self.regs = Registers()
        self.regs.SP = 0xffff + 1

        self.hardware = []
        self.hardware.extend([Thruster(self.regs, self.ram) for _ in range(8)])
        self.hardware.extend([Sensor(self.regs, self.ram)])
        self.hardware.extend([Keyboard(self.regs, self.ram), Display(self.regs, self.ram)])
        self.on_interruption_now = False

    def gen_instructions(self):
        while True:
            keyboard = self.hardware[-2]
            if keyboard.interruptions and self.on_interruption_now is False:
                self.push(self.regs.PC)
                self.push(self.regs.A)

                self.regs.A = keyboard.interruptions.pop()
                self.regs.PC = self.regs.IA
                self.on_interruption_now = True

            origin_pc = self.regs.PC
            code = self.ram[self.regs.PC]
            if code == 0:
                break

            cmd, op_b, op_a, nw_b, nw_a = describe_instruction(code)

            if nw_a is True:
                self.regs.PC += 1
                nw_a = self.ram[self.regs.PC]

            if nw_b is True:
                self.regs.PC += 1
                nw_b = self.ram[self.regs.PC]

            yield origin_pc, Instruction(code, cmd, op_b, nw_b, op_a, nw_a)

    def run(self, filename):
        for step in self.step_run(filename):
            if self._debug:
                print(self.regs)

    def step_run(self, filename):
        print('Loading program to RAM...')
        for pc, code in load_bin_file(filename):
            self.ram[pc] = code
        print('Loading done.')

        for pc, instruction in self.gen_instructions():
            if self._debug:
                print(to_human_readable(instruction, pc))

            try:
                value_b = self.get_value_from_op(instruction.B, do_pop=False)
                value_a = self.get_value_from_op(instruction.A, do_pop=True)
            except:
                to_human_readable_dat(instruction.code, pc, True)

            do_not_inc_pc = self.exec_instruction(instruction, value_b, value_a)

            if do_not_inc_pc is False:
                self.regs.PC += 1

            yield pc

    @instruction
    def add(self, inst, b, a):
        self.set(inst.B, value=a + b)

        if b + a > 0xffff:
            self.regs.EX = 0x0001
        else:
            self.regs.EX = 0x0000

    @instruction
    def sub(self, inst, b, a):
        self.set(inst.B, value=b - a)

        if b - a < 0x0000:
            self.regs.EX = 0xffff
        else:
            self.regs.EX = 0x0000

    @instruction
    def set(self, inst, _, a):
        self.set(inst.B, a)
        return inst.B.op == 0x1c  # SET PC, x must not increase PC

    @instruction
    def mul(self, inst, b, a):
        self.set(inst.B, value=b * a)
        self.regs.EX = ((b * a) >> 16) & 0xffff

    @instruction
    def mli(self, inst, b, a):
        print('**TODO**')
        return self.mul(inst, b, a)

    @instruction
    def div(self, inst, b, a):
        if a == 0x0:
            self.set(inst.B, value=0)
        else:
            self.set(inst.B, value=int(b / a))

    @instruction
    def dvi(self, inst, b, a):
        print('**TODO**')
        return self.div(inst, b, a)

    @instruction
    def mod(self, inst, b, a):
        if a == 0x0:
            self.set(inst.B, value=0)
        else:
            self.set(inst.B, value=b % a)

    @instruction
    def mdi(self, inst, b, a):
        return self.mod(inst, b, a)

    @instruction
    def and_(self, inst, b, a):
        print('**TODO**')
        self.set(inst.B, value=b & a)

    @instruction
    def bor(self, inst, b, a):
        self.set(inst.B, value=b | a)

    @instruction
    def xor(self, inst, b, a):
        self.set(inst.B, value=b ^ a)

    @instruction
    def shr(self, inst, b, a):
        self.set(inst.B, value=b >> a)

    @instruction
    def shl(self, inst, b, a):
        self.set(inst.B, value=b << a)

    @instruction
    def ifb(self, _, b, a):
        if b & a == 0:
            self.skip_next_instruction()

    @instruction
    def ifc(self, _, b, a):
        if b & a != 0:
            self.skip_next_instruction()

    @instruction
    def ife(self, _, b, a):
        if b != a:
            self.skip_next_instruction()

    @instruction
    def ifn(self, _, b, a):
        if b == a:
            self.skip_next_instruction()

    @instruction
    def ifg(self, _, b, a):
        if b <= a:
            self.skip_next_instruction()

    @instruction
    def ifa(self, _, b, a):
        print('**TODO**')
        return self.ifg(_, b, a)

    @instruction
    def ifl(self, _, b, a):
        if b >= a:
            self.skip_next_instruction()

    @instruction
    def ifu(self, _, b, a):
        print('**TODO**')
        return self.ifl(_, b, a)

    @instruction
    def adx(self, inst, b, a):
        tmp = b + a + self.regs.EX
        self.set(inst.B, value=tmp)
        if tmp > 0xffff:
            self.regs.EX = 0x0001
        else:
            self.regs.EX = 0x0000

    @instruction
    def sbx(self, inst, b, a):
        tmp = b - a + self.regs.EX
        self.set(inst.B, value=tmp)
        if tmp < 0x0000:
            self.regs.EX = 0xffff
        else:
            self.regs.EX = 0x0000

    @instruction
    def sti(self, inst, _, a):
        self.set(inst.B, value=a)
        self.regs.I += 1
        self.regs.J += 1

    @instruction
    def sdi(self, inst, _, a):
        self.set(inst.B, value=a)
        self.regs.I -= 1
        self.regs.J -= 1

    @instruction
    def jsr(self, _, __, a):
        self.push(self.regs.PC + 1)
        self.regs.PC = a
        return True

    @instruction
    def int_(self, inst, b, a):
        print('**TODO**')

    @instruction
    def iag(self, inst, _, __):
        self.set(inst.A, value=self.regs.IA)

    @instruction
    def ias(self, _, __, a):
        self.regs.IA = a

    @instruction
    def rfi(self, _, __, ___):
        self.regs.A = self.pop()
        self.regs.PC = self.pop()
        self.on_interruption_now = False

        return True

    @instruction
    def iaq(self, inst, b, a):
        print('**TODO**')

    @instruction
    def hwn(self, inst, _, __):
        self.set(inst.A, value=len(self.hardware))

    @instruction
    def hwq(self, _, __, a):
        hwnum = a
        hwid = self.hardware[hwnum].ID
        vendor = self.hardware[hwnum].VENDOR

        self.regs.A = hwid & 0xffff
        self.regs.B = hwid >> 16

        self.regs.C = self.hardware[hwnum].VERSION
        self.regs.X = vendor & 0xffff
        self.regs.Y = vendor >> 16

    @instruction
    def hwi(self, _, __, a):
        hwnum = a
        device = self.hardware[hwnum]
        device.handle_interruption()

    def exec_instruction(self, inst, b, a):
        cmd = inst.cmd

        if cmd in HANDLERS:
            return HANDLERS[cmd](self, inst, b, a)
        else:
            raise Exception

    def skip_next_instruction(self):
        code = self.ram[self.regs.PC + 1]
        cmd, op_b, op_a, nw_b, nw_a = describe_instruction(code)
        skip = 1
        if nw_a:
            skip += 1
        if nw_b:
            skip += 1

        self.regs.PC += skip

        if cmd.startswith('IF'):
            self.skip_next_instruction()

    def set(self, operator: Operator, value=None):
        value = value & 0xffff

        op = operator.op
        nw = operator.nw
        if 0x00 <= op <= 0x07:
            self.regs[BIN2REGISTERS[op]] = value
        elif 0x08 <= op <= 0x0f:
            self.ram[self.regs[BIN2REGISTERS[op - 0x08]]] = value
        elif 0x10 <= op <= 0x17:
            self.ram[self.regs[BIN2REGISTERS[op - 0x10]] + nw] = value
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

    def get_value_from_op(self, operator, do_pop=False):
        if operator is None:
            return None

        op = operator.op
        nw = operator.nw

        if 0x00 <= op <= 0x07:
            return self.regs[BIN2REGISTERS[op]]
        elif 0x08 <= op <= 0x0f:
            return self.ram[self.regs[BIN2REGISTERS[op - 0x08]]]
        elif 0x10 <= op <= 0x17:
            return self.ram[self.regs[BIN2REGISTERS[op - 0x10]] + nw]
        elif op == 0x18:
            return self.pop() if do_pop else None
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
        elif op == 0x20:
            return 0xffff
        elif 0x21 <= op <= 0x3f:
            return op - 0x21
        else:
            raise Exception

    def push(self, value):
        self.regs.SP -= 1
        self.ram[self.regs.SP] = value

    def pop(self):
        value = self.ram[self.regs.SP]
        self.regs.SP += 1
        return value

    def peek(self, n=0):
        return self.ram[self.regs.SP + n]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    e = Emulator(args.debug)
    e.run(args.filename)
