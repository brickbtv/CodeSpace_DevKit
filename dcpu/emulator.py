import argparse

from constants import BIN2OPCODE, BIN2SPECTIAL

class Decoder:
    def decode(self, filename):
        pc = 0
        with open(filename, 'rb') as f:
            code = f.read(2)
            while code:
                code = int.from_bytes(code, "little")
                is_basic = True

                opcode = code & 0x1f
                if opcode != 0:
                    operand_b = (code & 0x3e0) >> 5
                    cmd = BIN2OPCODE.get(opcode, 'unknown')
                else:
                    is_basic = False
                    opcode = code & 0x3e0
                    opcode >>= 5
                    cmd = BIN2SPECTIAL.get(opcode, 'unknown')

                if (code & 0xff00) >> 8 == 0:
                    print('0x{:04x}'.format(pc), '0x{:04x} 0x{:016b}'.format(code, code), 'DAT?', chr(code) if code >= ord(' ') else '0x{:02x}'.format(code))
                    pc += 1
                    code = f.read(2)
                    continue

                operand_a = (code & 0xfc00) >> 10

                nw1 = nw2 = None

                if is_basic and operand_b == 0x1e:
                    pc += 1
                    nw2 = int.from_bytes(f.read(2), "little")

                if operand_a == 0x1f:
                    pc += 1
                    nw1 = int.from_bytes(f.read(2), "little")

                print('0x{:04x}'.format(pc), '0x{:04x} 0x{:016b}'.format(code, code), '0x{:2x}'.format(opcode), '{} 0x{:02x} 0x{:02x}'.format(cmd, operand_b, operand_a))
                if nw2 is not None:
                    print('0x{:04x}'.format(pc), '0x{:04x} 0x{:016b}'.format(code, nw2))
                if nw1 is not None:
                    print('0x{:04x}'.format(pc), '0x{:04x} 0x{:016b}'.format(code, nw1))

                pc += 1
                code = f.read(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('--debug', action='store_true', default=False)
    args = parser.parse_args()

    d = Decoder()
    d.decode(args.filename)
