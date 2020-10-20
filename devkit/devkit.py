import argparse
import sys
from enum import Enum
from pathlib import Path

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QPoint, QTimer, Qt, QEvent, QCoreApplication
from PyQt5.QtGui import QTextCursor, QImage, QPixmap, qRgb
from PyQt5.QtWidgets import QGraphicsScene, QLabel, QFileDialog, QMessageBox

from constants import LEM1802_FONT, LEM1802_PALETTE
from decoder import gen_instructions, to_human_readable
from emulator import Emulator
from hardware import Keyboard, Sensor
import devkit_ui

from devkit_code_editor import QCodeEditor


class EmulationState(Enum):
    INITIAL = 0
    LOADED = 1
    STEP_REQUESTED = 2
    STEP_PREFORMED = 3
    RUN_FAST = 4


class DevKitApp(QtWidgets.QMainWindow, devkit_ui.Ui_MainWindow):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

        self.setupUi(self)
        self.keyboard.installEventFilter(self)

        self.emulator = None #Emulator(debug=False)
        self.emulator_state = EmulationState.INITIAL

        if filename:
            self.action_reset()
        else:
            self.gen = None

        self.display_size = (128, 96)
        self.image = QImage(self.display_size[0], self.display_size[1], QImage.Format_RGB32)
        self.scene = QGraphicsScene()
        self.xx = 0
        self.display.setScene(self.scene)

        self.display.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        emu_timer = QTimer(self)
        emu_timer.setInterval(1)
        emu_timer.timeout.connect(self.step_instruction)
        emu_timer.start()
        self.threads = [emu_timer]

        timer = QTimer(self)
        timer.setInterval(100)
        timer.timeout.connect(self.draw_display)
        timer.start()
        self.threads.append(timer)

        self.actionOpenBinFile.triggered.connect(self.action_open_file)
        self.actionStep.triggered.connect(self.action_step)
        self.actionRun.triggered.connect(self.action_run)
        self.actionReset.triggered.connect(self.action_reset)

        self.speed_multiplier = 1
        self.speed_changed()
        self.speed.currentIndexChanged.connect(self.speed_changed)

    def speed_changed(self):
        self.speed_multiplier = 10 ** self.speed.currentIndex()

    def action_open_file(self):
        home_dir = str(Path.home())
        filename = QFileDialog.getOpenFileName(self, 'Open file', home_dir, 'BIN files (*.bin)')
        if filename:
            self.filename = filename[0]
            self.action_reset()


    def action_step(self):
        self.emulator_state = EmulationState.STEP_REQUESTED

    def action_run(self):
        self.emulator_state = EmulationState.RUN_FAST

    def action_reset(self):
        self.last_frame = []
        if self.filename is None:
            return

        self.emulator = Emulator(debug=False)

        self.load_bin(self.filename)
        self.code_editor = self.setup_code_editor()

        self.emulator_state = EmulationState.LOADED

        self.emulator.preload(self.filename)
        self.gen = self.emulator.run_step()

    def eventFilter(self, source, event):
        # keyboard support
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            key = 0
            if event.key() == Qt.Key_Backspace:
                key = 0x10
            elif event.key() == Qt.Key_Enter:
                key = 0x11
            elif event.key() == Qt.Key_Insert:
                key = 0x12
            elif event.key() == Qt.Key_Delete:
                key = 0x13
            elif event.key() == Qt.Key_Up:
                key = 0x80
            elif event.key() == Qt.Key_Down:
                key = 0x81
            elif event.key() == Qt.Key_Left:
                key = 0x82
            elif event.key() == Qt.Key_Right:
                key = 0x83
            elif event.key() == Qt.Key_Shift:
                key = 0x90
            elif event.key() == Qt.Key_Control:
                key = 0x91
            else:
                try:
                    key = ord(event.text())
                except:
                    print('Bad key')

            keyboard: Keyboard = self.emulator.hardware[-2]
            keyboard.handle_key_event(key, event.type() == QEvent.KeyPress)

        return super().eventFilter(source, event)

    def setup_code_editor(self):
        better_code = QCodeEditor(self.centralwidget, self.pc_to_line)

        # TODO: hack for reset
        if self.code is None:
            self.code = self.code_editor

        font = QtGui.QFont()
        font.setFamily(self.code.font().family())
        font.setPointSize(self.code.font().pointSize())

        better_code.setFont(font)
        better_code.setObjectName("code")

        self.horizontalLayout.replaceWidget(self.code, better_code)

        self.code.deleteLater()
        self.code = None

        for line in self.lines:
            better_code.appendPlainText(line)

        cursor = better_code.cursorForPosition(QPoint(0, 0))
        better_code.setTextCursor(cursor)

        return better_code

    def load_bin(self, filename):
        self.pc_to_line = {}
        self.lines = []

        for line_num, (pc, instruction) in enumerate(gen_instructions(filename)):
            line = to_human_readable(instruction, pc, extended=False)
            self.lines.append(line)
            self.pc_to_line[pc] = line_num

    def load_palette(self):
        data = LEM1802_PALETTE
        if self.emulator.hardware[-1].palette_ram > 0:
            data = [self.emulator.ram[self.emulator.hardware[-1].palette_ram + i] for i in range(16)]

        palette = []
        for i in range(16):
            val = data[i]
            palette.append(qRgb(
                ((val & 0x0f00) >> 8) * 16,
                ((val & 0x00f0) >> 4) * 16,
                (val & 0x000f) * 16
            ))
        return palette

    last_frame = []

    def draw_display(self):
        if self.emulator is None:
            return

        palette = self.load_palette()

        vram = self.emulator.hardware[-1].video_ram
        fram = self.emulator.hardware[-1].font_ram

        if not self.last_frame:
            self.last_frame = self.emulator.ram[vram:32 * 12]

        for y in range(12):
            for x in range(32):
                val = self.emulator.ram[vram + x + y * 32]

                try:
                    if val == self.last_frame([x + y * 32]):
                        continue
                except:
                    pass

                char = val & 0x007f
                blink = val & 0x0080
                bgcolor = (val & 0x0f00) >> 8
                fgcolor = (val & 0xf000) >> 12

                char *= 2

                if fram == 0:
                    hi = LEM1802_FONT[char]
                    lo = LEM1802_FONT[char + 1]
                else:
                    hi = self.emulator.ram[fram + char]
                    lo = self.emulator.ram[fram + char + 1]

                offset_x = x*4
                offset_y = y*8
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

                        self.image.setPixel(offset_x+xx, offset_y+yy, palette[fgcolor] if v else palette[bgcolor])

        self.scene.addPixmap(QPixmap.fromImage(self.image))
        self.display.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        # set thrusters UI
        thrusters = [self.thruster0, self.thruster1, self.thruster2, self.thruster3, self.thruster4, self.thruster5, self.thruster6, self.thruster7]

        for i, thruster in enumerate(self.emulator.hardware[:8]):
            label: QLabel = thrusters[i]
            label.setText(str(thruster.power))

        # set keyboard buffer UI
        keyboard: Keyboard = self.emulator.hardware[-2]
        self.keyboard_buffer.setText(f'{",".join([chr(c) for c in keyboard.buffer])}'[:50])

        # update sensors from UI
        data = []
        for i in range(7):
            type = self.contacts.item(i, 0)
            size = self.contacts.item(i, 1)
            range_ = self.contacts.item(i, 2)
            angle = self.contacts.item(i, 3)

            try:
                data.append({
                    'type': int(type.text(), 16),
                    'size': int(size.text(), 16),
                    'range': int(range_.text(), 16),
                    'angle': int(angle.text(), 16),
                })
            except Exception:
                continue

        sensor: Sensor = self.emulator.hardware[-3]
        sensor.update_sensor(data)

    def step_instruction(self):
        if self.emulator_state not in {EmulationState.STEP_REQUESTED, EmulationState.RUN_FAST}:
            return

        if self.gen is None:
            return

        print(self.speed_multiplier)

        for i in range(self.speed_multiplier):
            # give some air to display thread
            if i % 100 == 0:
                QCoreApplication.processEvents()

            try:
                pc = next(self.gen)
            except Exception as ex:
                print(f'Exception: {ex}')
                QMessageBox.warning(self, 'Error', f'Emulator halted. Reason: {ex}')
                self.action_reset()
                break

            if self.emulator_state is EmulationState.STEP_REQUESTED:
                self.emulator_state = EmulationState.STEP_PREFORMED
                self._dump_registers()
                break

        cursor = QTextCursor(self.code_editor.document().findBlockByLineNumber(self.pc_to_line[pc]))
        self.code_editor.setTextCursor(cursor)

        self._dump_registers()

    def _dump_registers(self):
        for i, reg in enumerate(['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']):
            item = self.registers.item(i, 0)
            item.setText(f'0x{self.emulator.regs[reg]:04x}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--filename')
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = DevKitApp(args.filename)
    window.show()
    app.exec_()
