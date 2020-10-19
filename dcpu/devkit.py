import sys
import time

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QPoint, QTimer, QRect, Qt, QCoreApplication
from PyQt5.QtGui import QTextCursor, QColor, QImage, QPixmap, qRgb
from PyQt5.QtWidgets import QGraphicsScene

from constants import LEM1802_FONT, LEM1802_PALETTE
from decoder import Decoder
from emulator import Emulator
import devkit_ui

from devkit_code_editor import QCodeEditor


filename = 'testbin/admiral.bin'


# class EmulatorThread(QtCore.QThread):
#     def __init__(
#             self,
#             registers_view: QtWidgets.QTableWidget,
#             code_editor: QtWidgets.QPlainTextEdit,
#             emulator: Emulator,
#             pc_to_line: dict,
#     ):
#         super().__init__()
#         self.decoder = Decoder()
#         self.emulator = emulator
#         self.pc_to_line = pc_to_line
#
#         self.registers_view = registers_view
#         self.code_editor = code_editor
#
#     def run(self):
#         try:
#             self._run()
#         except Exception as ex:
#             print(ex)
#
#     def _run(self):
#         for pc in self.emulator.step_run(filename):
#             if not self.isRunning():
#                 return
#
#             cursor = QTextCursor(self.code_editor.document().findBlockByLineNumber(self.pc_to_line[pc]))
#             self.code_editor.setTextCursor(cursor)
#
#             for i, reg in enumerate(['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']):
#                 item = self.registers_view.item(i, 0)
#                 item.setText(f'0x{self.emulator.regs[reg]:04x}')
#
#             time.sleep(0.0001)


class DevKitApp(QtWidgets.QMainWindow, devkit_ui.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.better_code = self.setup_code_editor()

        self.decoder = Decoder()
        self.load_bin()

        self.emulator = Emulator(True)

        # emu_thread = EmulatorThread(
        #     self.registers, self.better_code, self.emulator, self.pc_to_line,
        # )
        # emu_thread.start()

        self.decoder = Decoder()

        self.registers_view = self.registers
        self.code_editor = self.better_code

        self.gen = self.emulator.step_run(filename)

        emu_timer = QTimer(self)
        emu_timer.setInterval(1)
        emu_timer.timeout.connect(self.step_instruction)
        emu_timer.start()
        self.threads = [emu_timer]

        self.display_size = (128, 96)
        self.image = QImage(self.display_size[0], self.display_size[1], QImage.Format_RGB32)
        self.scene = QGraphicsScene()
        self.xx = 0
        self.display.setScene(self.scene)
        timer = QTimer(self)
        timer.setInterval(10)
        timer.timeout.connect(self.draw_display)
        timer.start()
        self.threads.append(timer)

    def setup_code_editor(self):
        better_code = QCodeEditor(self.centralwidget)

        font = QtGui.QFont()
        font.setFamily(self.code.font().family())
        font.setPointSize(self.code.font().pointSize())

        better_code.setFont(font)
        better_code.setObjectName("code")

        self.horizontalLayout.replaceWidget(self.code, better_code)

        self.code.deleteLater()
        self.code = None

        return better_code

    def load_bin(self):
        self.pc_to_line = {}

        for line_num, (pc, instruction) in enumerate(self.decoder.gen_instructions(filename)):
            line = self.decoder.print_instruction(instruction, pc, extended=False)
            self.better_code.appendPlainText(line)
            self.pc_to_line[pc] = line_num

        cursor = self.better_code.cursorForPosition(QPoint(0, 0))
        self.better_code.setTextCursor(cursor)

    def load_palette(self):
        data = LEM1802_PALETTE
        if self.emulator.hardware[-1].pram > 0:
            data = self.emulator.hardware[-1].pram

        palette = []
        for i in range(16):
            val = data[i]
            palette.append(qRgb(
                ((val & 0x0f00) >> 8) * 16,
                ((val & 0x00f0) >> 4) * 16,
                (val & 0x000f) * 16
            ))
        return palette

    def draw_display(self):
        palette = self.load_palette()

        for y in range(12):
            for x in range(32):
                vram = self.emulator.hardware[-1].vram
                val = self.emulator.ram[vram + x + y * 32]

                char = val & 0x007f
                blink = val & 0x0080
                bgcolor = (val & 0x0f00) >> 8
                fgcolor = (val & 0xf000) >> 12

                char *= 2
                hi = LEM1802_FONT[char]
                lo = LEM1802_FONT[char+1]

                for xx in range(4):
                    for yy in range(8):
                        b = 2 ** yy
                        if xx == 0:
                            v = hi >> 8 & b
                        elif xx == 1:
                            v = hi & b
                        elif xx == 2:
                            v = lo >> 8 & b
                        else:
                            v = lo & b

                        self.image.setPixel(x*4+xx, y*8+yy, palette[fgcolor] if v else palette[bgcolor])

        self.scene.addPixmap(QPixmap.fromImage(self.image))

        self.xx += 1

    def step_instruction(self):
        for i in range(2):
            pc = next(self.gen)

            cursor = QTextCursor(self.code_editor.document().findBlockByLineNumber(self.pc_to_line[pc]))
            self.code_editor.setTextCursor(cursor)

            for i, reg in enumerate(['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']):
                item = self.registers_view.item(i, 0)
                item.setText(f'0x{self.emulator.regs[reg]:04x}')



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DevKitApp()
    window.show()
    app.exec_()
