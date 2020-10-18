import sys
import time

from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QTextCursor

from decoder import Decoder
from instuction import Instruction
from emulator import Emulator
import emulator_ui

from devkit_code_editor import QCodeEditor


filename = 'o1.bin'


class EmulatorThread(QtCore.QThread):
    def __init__(
            self,
            registers_view: QtWidgets.QTableWidget,
            code_editor: QtWidgets.QPlainTextEdit,
            pc_to_line: dict,
    ):
        super().__init__()
        self.decoder = Decoder()
        self.emulator = Emulator(True)
        self.pc_to_line = pc_to_line

        self.registers_view = registers_view
        self.code_editor = code_editor

    def run(self):
        try:
            self._run()
        except Exception as ex:
            print(ex)

    def _run(self):
        for pc in self.emulator.step_run(filename):
            if not self.isRunning():
                return

            cursor = QTextCursor(self.code_editor.document().findBlockByLineNumber(self.pc_to_line[pc]))
            self.code_editor.setTextCursor(cursor)

            for i, reg in enumerate(['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']):
                item = self.registers_view.item(i, 0)
                item.setText(f'0x{self.emulator.regs[reg]:04x}')

            time.sleep(0.9)


class DevKitApp(QtWidgets.QMainWindow, emulator_ui.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.better_code = self.setup_code_editor()

        self.decoder = Decoder()
        self.load_bin()

        emu_thread = EmulatorThread(
            self.registers, self.better_code, self.pc_to_line,
        )
        emu_thread.start()
        self.threads = [emu_thread]

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


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = DevKitApp()
    window.show()
    app.exec_()
