class Operator:
    def __init__(self, op, nw):
        self.op = op
        self.nw = nw

    def __repr__(self):
        return f'<Op {self.op}/{self.nw}>'


class Instruction:
    def __init__(self, code, cmd, op_b, nw_b, op_a, nw_a):
        self.code = code
        self.cmd = cmd
        self.A = Operator(op_a, nw_a)
        self.B = Operator(op_b, nw_b) if op_b is not None else None

    def __repr__(self):
        return f'<Instruction {self.cmd} {self.B} {self.A}>'
