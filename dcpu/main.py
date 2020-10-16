import argparse

from constants import TESTSET
from translator import DCPUTranslator


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

