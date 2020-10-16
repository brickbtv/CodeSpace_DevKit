import argparse

from constants import MNEMONIC_TO_CODE, SPECIAL_MNEMONICS_TO_CODE, REGISTERS, LITERAL, TESTSET


class ParserException(Exception):
    pass


def parse_line(line: str):
    command, args = line[:3], line[3:]
    params = args.split(',')[:2]
    param1 = params[0].strip() if len(params) >= 1 else None
    param2 = params[1].strip() if len(params) == 2 else None

    return command.strip().upper(), param1, param2


def parse_labels(filename):
    labels = {}

    with open(filename, 'r') as f:
        pc = 0
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith(';'):
                continue

            if line.startswith(':'):
                labels[line.strip()[1:]] = pc
                continue

            pc += 1

    return labels


def param2bin(param: str, labels: dict):
    if not param:
        return 0, None

    value = REGISTERS.get(param)
    if value is not None:
        return value, None

    try:
        if param == '0xffff':
            return 0x1f, 0xffff

        base = 10
        if param.startswith('0x'):
            base = 16

        value = int(param, base)
        return 0x1f, value
    except (ValueError, TypeError, KeyError):
        pass

    value = labels.get(param)
    if value is not None:
        return 0x1f, 0xdead#value

    if param[0] == '[' and param[-1] == ']':
        value = REGISTERS.get(param[1:-1])
        if value is not None:
            return value + 0x08, None

        value = labels.get(param[1:-1])
        if value:
            return 0x1e, 0xdead#value

    if '+' in param:
        reg, label = param[1:-1].split('+')[0:2]
        reg = reg.strip()
        value = REGISTERS.get(reg)
        return 0x10+value, 0xdead#param2bin(label, labels)[0]

    return 0, None


def asm2bin(filename, labels):
    with open(filename, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith((';', ':')):
                continue

            cmd, param1, param2 = parse_line(line)

            if cmd == 'DAT':
                for param in [param1, param2]:
                    if param is None:
                        continue

                    if param.isdigit():
                        print('0x{:04x}'.format(int(param)), '0x{:016b}'.format(int(param)), cmd, param)
                        yield int(param)
                        continue

                    if param.startswith('0x'):
                        p = int(param, 16)
                        print('0x{:04x}'.format(p), '0x{:016b}'.format(p), cmd, param)
                        yield p
                        continue

                    if param.startswith(('"', "'")):
                        for c in param[1:-1]:
                            cc = ord(c)
                            print('0x{:04x}'.format(cc), '0x{:016b}'.format(cc), cmd, c)
                            yield cc

                continue


            is_spec = False
            code = MNEMONIC_TO_CODE.get(cmd)
            if not code:
                code = SPECIAL_MNEMONICS_TO_CODE.get(cmd) << 5
                is_spec = True

            if not code:
                print(cmd)
                raise Exception

            param1coded, nw1 = param2bin(param1, labels)
            param2coded, nw2 = param2bin(param2, labels)

            if not is_spec:
                # workaround
                if param2coded == 31 or param2 in REGISTERS or param1 in REGISTERS:
                    param1coded, param2coded = param2coded, param1coded

                code = code | param2coded << 5 | param1coded << 10
            else:
                code = code | param1coded << 10

            print('0x{:04x}'.format(code), '0x{:016b}'.format(code), cmd, param1, param2, '({} , {})'.format(param1coded, param2coded))
            yield code

            if nw2 is not None:
                print('0x{:04x}'.format(nw2), '0x{:016b}'.format(nw2))
                yield nw2

            if nw1 is not None:
                print('0x{:04x}'.format(nw1), '0x{:016b}'.format(nw1))
                yield nw1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    labels = parse_labels(args.filename)
    from pprint import pprint
    pprint(labels)
    for i, instr in enumerate(asm2bin(args.filename, labels)):
        if instr != int(TESTSET[i], 16):
            if instr != 0xdead:
                print('0x{:04x} 0x{:016b}      expected'.format(int(TESTSET[i], 16), int(TESTSET[i], 16)))
           #     raise Exception()

        # print('0x{:04x}'.format(instr), end=' ')
        # if i % 4 == 0:
        #     print()
