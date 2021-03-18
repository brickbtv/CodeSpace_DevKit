import argparse
import os
import sys
from enum import Enum
from functools import partial
from pathlib import Path
from typing import List

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QTimer, Qt, QEvent, QCoreApplication, QMutex
from PyQt5.QtGui import QImage, QPixmap, qRgb
from PyQt5.QtWidgets import QGraphicsScene, QLabel, QFileDialog, QMessageBox, QDesktopWidget

from editor_window import EditorWindow
from emulator import Emulator
from hardware import Keyboard, Sensor, Door, DockingClamp, Antenna, Clock
import devkit_ui

from project.project import Project
from translator import DCPUTranslator


class EmulationState(Enum):
    INITIAL = 0
    LOADED = 1
    STEP_REQUESTED = 2
    STEP_PREFORMED = 3
    RUN_FAST = 4


class DevKitMode(Enum):
    ASM = 1


class DevKitApp(QtWidgets.QMainWindow, devkit_ui.Ui_MainWindow):
    emulator = None
    image = None
    scene = None
    emulator_state = EmulationState.INITIAL
    timers = []
    mode = None
    close_mutex = QMutex()

    def __init__(self, project_file):
        super().__init__()

        self.next_instruction = None
        self.project_file = project_file
        self.editor_windows = {}

        self.setupUi(self)
        self.move_window_to_center()

        # project tree
        self.project_view_model = QtGui.QStandardItemModel()
        self.project_view_model.setHorizontalHeaderLabels(['Name'])
        self.project_view.setModel(self.project_view_model)
        self.project_view.doubleClicked.connect(self.select_file_to_edit)

        if project_file:
            self.project = Project.load_from_file(project_file)
            self.setup_project_tree()

        self.setup_display()
        self.setup_emulator()
        self.setup_keyboard()
        self.setup_doors()
        self.setup_antenna()
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

    def select_file_to_edit(self, index):
        item = self.project_view.selectedIndexes()[0]

        filename = item.model().itemFromIndex(index).text()

        if filename in self.editor_windows:
            self.editor_windows[filename].activateWindow()
            return

        editor_window = EditorWindow(self.project.location, filename, self.remove_editor_window)
        editor_window.show()

        self.editor_windows[filename] = editor_window

    def remove_editor_window(self, filename):
        if self.close_mutex.tryLock() is False:
            return

        if filename in self.editor_windows:
            self.editor_windows.pop(filename)

        self.close_mutex.unlock()

    def move_window_to_center(self):
        center_point = QDesktopWidget().availableGeometry().center()
        rect = self.frameGeometry()
        rect.moveCenter(center_point)
        self.move(rect.topLeft())

    def setup_project_tree(self):
        self.project_view_model.setRowCount(0)
        for filename in self.project.files:
            self.project_view_model.appendRow(QtGui.QStandardItem(filename))

    def setup_keyboard(self):
        self.keyboard.installEventFilter(self)

    def setup_antenna(self):
        self.send_msg.pressed.connect(self.send_antenna_msg)

    def send_antenna_msg(self):
        antennas: List[Antenna] = self.emulator.get_all_hardware_by_name('antenna')
        for antenna in antennas:
            antenna.recv_message([ord(c) for c in self.recv_buffer.text()])
            self.recv_buffer.clear()

    def setup_emulator(self):
        if self.project_file:
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
        filename = QFileDialog.getOpenFileName(
            self, 'Open file', home_dir, 'project files (*.codespace)', options=QFileDialog.DontUseNativeDialog,
        )

        if filename and filename[0]:
            self.project = Project.load_from_file(filename[0])
            self.setup_project_tree()
            self.action_reset()

    def action_step(self):
        self.retranslate()

        self.emulator_state = EmulationState.STEP_REQUESTED
        self.actionReset.setEnabled(True)

    def action_run(self):
        self.retranslate()

        self.emulator_state = EmulationState.RUN_FAST
        self.actionReset.setEnabled(True)

    def action_reset(self):
        self.last_frame = []
        if self.project_file is None:
            return

        self.emulator = Emulator(debug=False)
        self.load_project_files()

        self.emulator_state = EmulationState.LOADED

        self.next_instruction = self.emulator.run_step()
        self.actionReset.setEnabled(False)

    def eventFilter(self, source, event):
        # keyboard support
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease):
            if event.key() == Qt.Key_Backspace:
                key = 0x10
            elif event.key() == Qt.Key_Enter:
                key = 0x11
            elif event.key() == Qt.Key_Return:
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

    def closeEvent(self, event):
        self.close_mutex.lock()
        for editor in self.editor_windows.values():
            editor.close()

        self.close_mutex.unlock()

    def retranslate(self):
        try:
            self._retranslate()
        except Exception as ex:
            QMessageBox.warning(self, 'Translation Error', str(ex))

    def _retranslate(self):

        # save all changes
        for editor in self.editor_windows.values():
            editor.save_file()



        self.pc_to_line = {}

        tr = DCPUTranslator()
        bin_location = os.path.join(self.project.location, f'{self.project.name}.bin')
        with open(bin_location, 'wb') as f:
            pc = 0
            for line_num, _, instructions in tr.asm2bin(self.project.location, self.project.main_file):
                for code in instructions:
                    f.write(code.to_bytes(2, byteorder='little'))
                    # TODO: refactor this
                self.pc_to_line[pc] = line_num
                pc += len(instructions)

        self.emulator.preload(bin_location)

    def load_project_files(self):
        """ Reads .bin file, decodes instructions
            saves PC-to-instruction info.
        """
        self.pc_to_line = {}
        self.lines = []

        # translate and then load
        translator = DCPUTranslator()
        try:
            pc = 0
            for line_num, line, instructions in translator.asm2bin(self.project.location, self.project.main_file):
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
            self.thruster7,
        ]
        for i, thruster in enumerate(self.emulator.hardware[:8]):
            label: QLabel = thrusters[i]
            label.setText(str(thruster.power))

        # set keyboard buffer UI
        keyboard: Keyboard = self.emulator.get_hardware_by_name('keyboard')
        self.keyboard_buffer.setText(
            f'{",".join([chr(c) for c in keyboard.buffer])}'[:50])

        # update sensors from UI

        sensors: List[Sensor] = self.emulator.get_all_hardware_by_name('sensor')

        for num, contacts in enumerate([self.contacts, self.contacts_2]):
            data = []
            for i in range(7):
                type_ = contacts.item(i, 0)
                id_ = contacts.item(i, 1)
                size = contacts.item(i, 2)
                range_ = contacts.item(i, 3)
                angle = contacts.item(i, 4)

                try:
                    data.append({
                        'type': int(type_.text(), 16),
                        'id': int(id_.text(), 16),
                        'size': int(size.text(), 16),
                        'range': int(range_.text(), 16),
                        'angle': int(angle.text(), 16),
                    })
                except Exception:
                    continue

            try:
                sensor = sensors[num]
                if sensor:
                    sensor.update_sensor(data)
            except IndexError:
                pass

        doors: Door = self.emulator.get_hardware_by_name('door')
        if doors:
            self.door_head.setText(f'Door {doors.mode[0].name}')
            self.door_left.setText(f'Door {doors.mode[1].name}')
            self.door_right.setText(f'Door {doors.mode[2].name}')

        clamps: DockingClamp = self.emulator.get_hardware_by_name('docking_clamp')
        if clamps:
            self.clamp_l_u.setText(f'Clamp {clamps.mode[0].name}')
            self.clamp_l_d.setText(f'Clamp {clamps.mode[1].name}')
            self.clamp_r_u.setText(f'Clamp {clamps.mode[2].name}')
            self.clamp_r_d.setText(f'Clamp {clamps.mode[3].name}')

        antenna: Antenna = self.emulator.get_hardware_by_name('anthenna')
        if antenna:
            self.send_buffer.setText(str(antenna.send_buffer))

    def step_instruction(self):
        if self.emulator_state not in {EmulationState.STEP_REQUESTED, EmulationState.RUN_FAST}:
            return

        if self.next_instruction is None:
            return

        break_at = self.stop_at.text()
        try:
            if len(break_at) == 6:
                break_at = int(break_at, 16)
            else:
                break_at = None
        except:
            break_at = None

        for i in range(self.speed_multiplier):
            # give some air to display thread
            if i % 100 == 0:
                QCoreApplication.processEvents()

            try:
                if self.emulator_state not in (EmulationState.STEP_REQUESTED, EmulationState.RUN_FAST):
                    break

                pc, is_brk = next(self.next_instruction)
                if is_brk or pc == break_at:
                    self.emulator_state = EmulationState.STEP_REQUESTED

                clock: Clock = self.emulator.get_hardware_by_name('clock')
                clock.update()

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

                if self.project.main_file in self.editor_windows:
                    self.editor_windows[self.project.main_file].select_line(selectline)

                QCoreApplication.processEvents()
                break

        self._dump_registers()

    def _dump_registers(self):
        for i, reg in enumerate(['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']):
            item = self.registers.item(i, 0)
            item.setText(f'0x{self.emulator.regs[reg]:04x}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-file')
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = DevKitApp(args.project_file)
    window.show()
    app.exec_()
