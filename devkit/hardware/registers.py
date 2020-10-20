from collections import defaultdict


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
            raise Exception(f'Unrecognized register {key}')

        self._regs[key] = value

    def __repr__(self):
        regs_data = ', '.join([f'{reg}=0x{self.__getattr__(reg):04x}' for reg in self.REGS])
        return f'<Registers: {regs_data}>'
