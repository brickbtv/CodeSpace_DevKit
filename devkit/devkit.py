import sys

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QPoint, QTimer, Qt, QEvent
from PyQt5.QtGui import QTextCursor, QImage, QPixmap, qRgb
from PyQt5.QtWidgets import QGraphicsScene, QLabel

from constants import LEM1802_FONT, LEM1802_PALETTE
from decoder import gen_instructions, to_human_readable
from emulator import Emulator
from hardware import Keyboard, Sensor
import devkit_ui

from devkit_code_editor import QCodeEditor


filename = 'testbin/mghelm1.8.bin'
# filename = 'mghelm1.8.bin'
# filename = 'o1.bin'


class DevKitApp(QtWidgets.QMainWindow, devkit_ui.Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.keyboard.installEventFilter(self)

        self.load_bin()

        self.better_code = self.setup_code_editor()

        self.emulator = Emulator(debug=False)

        self.registers_view = self.registers
        self.code_editor = self.better_code

        self.emulator.preload(filename)
        self.gen = self.emulator.run_step()

        self.display_size = (128, 96)
        self.image = QImage(self.display_size[0], self.display_size[1], QImage.Format_RGB32)
        self.scene = QGraphicsScene()
        self.xx = 0
        self.display.setScene(self.scene)

        # self.display.fitInView(QRectF(self.display.rect()), Qt.KeepAspectRatio)
        self.display.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)

        # self.display.scale(self.width() / 128 / 2, self.height() / 96 / 2)

        # self.keyboard.textChanged.connect(self.keyboard_input)

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

    def load_bin(self):
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

    def draw_display(self):
        palette = self.load_palette()

        for y in range(12):
            for x in range(32):
                vram = self.emulator.hardware[-1].video_ram
                val = self.emulator.ram[vram + x + y * 32]

                char = val & 0x007f
                blink = val & 0x0080
                bgcolor = (val & 0x0f00) >> 8
                fgcolor = (val & 0xf000) >> 12

                char *= 2

                fram = self.emulator.hardware[-1].font_ram
                if fram == 0:
                    hi = LEM1802_FONT[char]
                    lo = LEM1802_FONT[char + 1]
                else:
                    hi = self.emulator.ram[fram + char]
                    lo = self.emulator.ram[fram + char + 1]

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
        for i in range(1000):
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
