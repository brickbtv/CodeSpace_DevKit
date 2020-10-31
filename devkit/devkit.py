import argparse
import sys
from enum import Enum
from functools import partial
from pathlib import Path

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QPoint, QTimer, Qt, QEvent, QCoreApplication
from PyQt5.QtGui import QTextCursor, QImage, QPixmap, qRgb, QKeySequence
from PyQt5.QtWidgets import QGraphicsScene, QLabel, QFileDialog, QMessageBox, QShortcut

from decoder import gen_instructions, to_human_readable
from emulator import Emulator
from hardware import Keyboard, Sensor, Door, Anthenna
import devkit_ui

from devkit_code_editor import QCodeEditor, PythonHighlighter
from translator import DCPUTranslator


class EmulationState(Enum):
    INITIAL = 0
    LOADED = 1
    STEP_REQUESTED = 2
    STEP_PREFORMED = 3
    RUN_FAST = 4


class DevKitMode(Enum):
    BIN = 0
    ASM = 1


class DevKitApp(QtWidgets.QMainWindow, devkit_ui.Ui_MainWindow):
    emulator = None
    image = None
    scene = None
    emulator_state = EmulationState.INITIAL
    timers = []
    mode = None

    def __init__(self, filename):
        super().__init__()

        self.next_instruction = None
        self.filename = filename

        if self.filename and self.filename.endswith('.bin'):
            self.mode = DevKitMode.BIN
        else:
            self.mode = DevKitMode.ASM

        self.setupUi(self)

        self.setup_display()
        self.setup_emulator()
        self.setup_keyboard()
        self.setup_doors()
        self.setup_hardware()

        # menu buttons
        self.actionOpenBinFile.triggered.connect(self.action_open_file)
        self.actionStep.triggered.connect(self.action_step)
        self.actionRun.triggered.connect(self.action_run)
        self.actionReset.triggered.connect(self.action_reset)

        # speed combobox
        self.speed_multiplier = 1
        self.speed_changed()
        self.speed.currentIndexChanged.connect(self.speed_changed)

    def setup_keyboard(self):
        self.keyboard.installEventFilter(self)

    def setup_emulator(self):
        if self.filename:
            self.action_reset()

        emu_timer = QTimer(self)
        emu_timer.setInterval(1)
        emu_timer.timeout.connect(self.step_instruction)
        emu_timer.start()
        self.timers.append(emu_timer)

    def setup_display(self):
        self.image = QImage(128, 96, QImage.Format_RGB32)
        self.scene = QGraphicsScene()
        self.scene.addPixmap(QPixmap.fromImage(self.image))

        self.display.setScene(self.scene)
        self.display.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        timer = QTimer(self)
        timer.setInterval(200)
        timer.timeout.connect(self.draw_display)
        timer.start()
        self.timers.append(timer)

    def setup_doors(self):
        self.door_state_head.currentIndexChanged.connect(partial(self.change_door_state, 0))
        self.door_state_left.currentIndexChanged.connect(partial(self.change_door_state, 1))
        self.door_state_right.currentIndexChanged.connect(partial(self.change_door_state, 2))

    def change_door_state(self, door_id):
        state = 0
        if door_id == 0:
            state = self.door_state_head.currentIndex()
        elif door_id == 1:
            state = self.door_state_left.currentIndex()
        elif door_id == 2:
            state = self.door_state_right.currentIndex()

        # hack
        if state == 3:
            state = 4

        doors: Door = self.emulator.get_hardware_by_name('door')
        doors.change_state(door_id, Door.States(state))

    def setup_hardware(self):
        timer = QTimer(self)
        timer.setInterval(200)
        timer.timeout.connect(self.update_hardware_ui)
        timer.start()
        self.timers.append(timer)

    def speed_changed(self):
        self.speed_multiplier = 10 ** self.speed.currentIndex()

    def action_open_file(self):
        home_dir = str(Path.home())
        filename = QFileDialog.getOpenFileName(self, 'Open file', home_dir, 'DCPU files (*.bin *.dasm)')
        if filename and filename[0]:
            self.filename = filename[0]
            if self.filename.endswith(('.bin', '.rom')):
                self.mode = DevKitMode.BIN
            else:
                self.mode = DevKitMode.ASM

            self.code.clear()
            with open(self.filename) as f:
                for line in f.readlines():
                    self.code.appendPlainText(line.rstrip())

            self.action_reset()

    def action_step(self):
        if self.code.isEnabled() and self.mode is DevKitMode.ASM:
            self.retranslate()
            self.code.setEnabled(False)

        self.emulator_state = EmulationState.STEP_REQUESTED
        self.actionReset.setEnabled(True)

    def action_run(self):
        if self.code.isEnabled() and self.mode is DevKitMode.ASM:
            self.retranslate()
            self.code.setEnabled(False)

        self.emulator_state = EmulationState.RUN_FAST
        self.actionReset.setEnabled(True)

    def action_reset(self):
        self.last_frame = []
        if self.filename is None:
            return

        self.emulator = Emulator(debug=False)

        if self.emulator_state in (EmulationState.INITIAL, EmulationState.LOADED) or self.mode is DevKitMode.BIN:
            filename = self.filename
        else:
            filename = '_tmp.asm'

        self.load_file(filename)
        self.setup_code_editor(filename)

        self.emulator_state = EmulationState.LOADED

        self.code.setEnabled(self.mode is DevKitMode.ASM)

        if self.mode is DevKitMode.BIN:
            self.emulator.preload(self.filename)

        self.next_instruction = self.emulator.run_step()
        self.actionReset.setEnabled(False)

    def eventFilter(self, source, event):
        # keyboard support
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
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
                except Exception:
                    print(f'Bad key: {event.key()}')
                    return super().eventFilter(source, event)

            keyboard: Keyboard = self.emulator.get_hardware_by_name('keyboard')
            keyboard.handle_key_event(key, event.type() == QEvent.KeyPress)

        return super().eventFilter(source, event)

    def setup_code_editor(self, filename):
        """ Replaces basic text editor widget by custom code editor widget """
        if isinstance(self.code, QCodeEditor) and self.mode is DevKitMode.ASM:
            return

        better_code = QCodeEditor(self.centralwidget, self.pc_to_line, self.mode is DevKitMode.ASM)

        font = QtGui.QFont()
        font.setFamily(self.code.font().family())
        font.setPointSize(self.code.font().pointSize())

        better_code.setFont(font)
        better_code.setObjectName("code")
        better_code.setLineWrapMode(better_code.NoWrap)
        better_code.setTabStopWidth(30)

        self.horizontalLayout.replaceWidget(self.code, better_code)

        self.code.deleteLater()
        self.code = None

        if self.mode is DevKitMode.BIN:
            for line in self.lines:
                better_code.appendPlainText(line)
            better_code.setEnabled(False)
        else:
            with open(filename) as f:
                for line in f.readlines():
                    better_code.appendPlainText(line.rstrip())

            better_code.setEnabled(True)

        cursor = better_code.cursorForPosition(QPoint(0, 0))
        better_code.setTextCursor(cursor)

        self.hl = PythonHighlighter(better_code.document())

        shortcut = QShortcut(QKeySequence("Ctrl+S"), better_code)
        shortcut.activated.connect(self.save_file)

        self.code = better_code

    def closeEvent(self, event):
        self.save_file()

    def save_file(self):
        if self.mode is DevKitMode.ASM:
            data = self.code.toPlainText()
            with open(self.filename, 'w') as f:
                f.write(data)

    def retranslate(self):
        try:
            self._retranslate()
        except Exception as ex:
            QMessageBox.warning(self, 'Translation Error', str(ex))

    def _retranslate(self):
        data = self.code.toPlainText()
        with open('_tmp.asm', 'w') as f:
            f.write(data)

        self.pc_to_line = {}

        tr = DCPUTranslator()
        with open('_tmp.bin', 'wb') as f:
            pc = 0
            for line_num, _, instructions in tr.asm2bin('_tmp.asm'):
                for code in instructions:
                    f.write(code.to_bytes(2, byteorder='little'))
                    # TODO: refactor this
                self.pc_to_line[pc] = line_num
                pc += len(instructions)

        # self.load_file('_tmp.bin')
        self.emulator.preload('_tmp.bin')

        # all steps successful, so, we can save original file
        with open(self.filename, 'w') as f:
            f.write(data)

    def load_file(self, filename):
        """ Reads .bin file, decodes instructions
            saves PC-to-instruction info.
        """
        self.pc_to_line = {}
        self.lines = []

        if filename.endswith(('.bin', '.rom')):
            for line_num, (pc, instruction) in enumerate(gen_instructions(filename)):
                line = to_human_readable(instruction, pc, extended=False)
                self.lines.append(line)
                self.pc_to_line[pc] = line_num
        else:
            # translate and then load
            translator = DCPUTranslator()
            try:
                pc = 0
                for line_num, line, instructions in translator.asm2bin(filename):
                    self.pc_to_line[pc] = line_num
                    pc += len(instructions)

            except Exception as ex:
                print(ex)

    # hack for save some cycles while drawing
    last_frame = []
    last_vram = []
    last_fram = []
    last_pram = []

    def draw_display(self):
        if self.emulator is None or self.emulator_state in (EmulationState.INITIAL, EmulationState.LOADED):
            return

        display_hw = self.emulator.get_hardware_by_name('display')

        palette = display_hw.load_palette(qRgb)

        vram = display_hw.video_ram
        fram = display_hw.font_ram
        pram = display_hw.palette_ram

        redraw = self.last_vram != vram or self.last_fram != fram or self.last_pram != pram

        if not self.last_frame or redraw:
            self.last_frame = self.emulator.ram[vram:32 * 12]
            self.last_vram = vram
            self.last_fram = fram
            self.last_pram = pram

        for y in range(12):
            for x in range(32):
                val = self.emulator.ram[vram + x + y * 32]

                if not self._is_symbol_changed(val, x, y):
                    continue

                char = val & 0x007f
                blink = val & 0x0080
                bgcolor = (val & 0x0f00) >> 8
                fgcolor = (val & 0xf000) >> 12

                hi, lo = display_hw.get_char(char)

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

        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(self.image))
        self.display.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

    def _is_symbol_changed(self, val, x, y):
        try:
            if val == self.last_frame[x + y * 32]:
                return False
            else:
                self.last_frame[x + y * 32] = val
        except IndexError:
            pass

        return True

    def update_hardware_ui(self):
        if not self.emulator:
            return
        # set thrusters UI
        thrusters = [
            self.thruster0,
            self.thruster1,
            self.thruster2,
            self.thruster3,
            self.thruster4,
            self.thruster5,
            self.thruster6,
            self.thruster7
        ]
        for i, thruster in enumerate(self.emulator.hardware[:8]):
            label: QLabel = thrusters[i]
            label.setText(str(thruster.power))

        # set keyboard buffer UI
        keyboard: Keyboard = self.emulator.get_hardware_by_name('keyboard')
        self.keyboard_buffer.setText(
            f'{",".join([chr(c) for c in keyboard.buffer])}'[:50])

        # update sensors from UI
        data = []
        for i in range(7):
            type_ = self.contacts.item(i, 0)
            size = self.contacts.item(i, 1)
            range_ = self.contacts.item(i, 2)
            angle = self.contacts.item(i, 3)

            try:
                data.append({
                    'type': int(type_.text(), 16),
                    'size': int(size.text(), 16),
                    'range': int(range_.text(), 16),
                    'angle': int(angle.text(), 16),
                })
            except Exception:
                continue

        sensor: Sensor = self.emulator.get_hardware_by_name('sensor')
        if sensor:
            sensor.update_sensor(data)

        doors: Door = self.emulator.get_hardware_by_name('door')
        if doors:
            self.door_head.setText(f'Door {doors.mode[0].name}')
            self.door_left.setText(f'Door {doors.mode[1].name}')
            self.door_right.setText(f'Door {doors.mode[2].name}')

    def step_instruction(self):
        if self.emulator_state not in {EmulationState.STEP_REQUESTED, EmulationState.RUN_FAST}:
            return

        if self.next_instruction is None:
            return

        for i in range(self.speed_multiplier):
            # give some air to display thread
            if i % 100 == 0:
                QCoreApplication.processEvents()

            try:
                if self.emulator_state not in (EmulationState.STEP_REQUESTED, EmulationState.RUN_FAST):
                    break

                pc, is_brk = next(self.next_instruction)
                if is_brk:
                    self.emulator_state = EmulationState.STEP_REQUESTED

            except Exception as ex:
                print(f'Exception: {ex}')
                QMessageBox.warning(self, 'Error', f'Emulator halted. Reason: {ex}')
                self.action_reset()
                break

            if self.emulator_state is EmulationState.STEP_REQUESTED:
                self.emulator_state = EmulationState.STEP_PREFORMED
                self._dump_registers()

                try:
                    selectline = self.pc_to_line[pc]
                except:
                    break

                cursor = QTextCursor(self.code.document().findBlockByLineNumber(selectline))
                self.code.setTextCursor(cursor)
                QCoreApplication.processEvents()
                break

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
