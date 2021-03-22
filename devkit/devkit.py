import argparse
import os
import sys
import time
from enum import Enum
from functools import partial
from pathlib import Path
from typing import List

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import QTimer, Qt, QEvent, QCoreApplication, QPoint
from PyQt5.QtGui import QImage, QPixmap, qRgb, QPalette, QColor, QIcon
from PyQt5.QtWidgets import QGraphicsScene, QLabel, QFileDialog, QMessageBox, QDesktopWidget, QMenu, QTableWidgetItem

from create_project_window import CreateProjectWindow
from editor_window import EditorWindow
from emulator import Emulator
from hardware import Keyboard, Sensor, Door, DockingClamp, Antenna, Clock
import devkit_ui

from project.project import Project
from translator import DCPUTranslator, TranslationError


class EmulationState(Enum):
    INITIAL = 0
    LOADED = 1
    STEP_REQUESTED = 2
    STEP_PREFORMED = 3
    RUN_FAST = 4


class DevKitApp(QtWidgets.QMainWindow, devkit_ui.Ui_MainWindow):
    emulator = None
    image = None
    scene = None
    emulator_state = EmulationState.INITIAL
    timers = []
    mode = None

    def __init__(self, project_file):
        super().__init__()

        self.last_go_to_definition = time.time()

        self.next_instruction = None
        self.project_file = project_file
        self.editor_windows = {}

        self.setupUi(self)
        self.move_window_to_center()

        self.setup_editor()

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
        self.actionCreateProject.triggered.connect(self.action_create_project)
        self.actionOpenBinFile.triggered.connect(self.action_open_file)
        self.actionStep.triggered.connect(self.action_step)
        self.actionRun.triggered.connect(self.action_run)
        self.actionReset.triggered.connect(self.action_reset)

        # speed combobox
        self.speed_multiplier = 1
        self.speed_changed()
        self.speed.currentIndexChanged.connect(self.speed_changed)

    def setup_editor(self):
        self.project_view_model = QtGui.QStandardItemModel()
        self.project_view_model.setHorizontalHeaderLabels(['Name'])

        self.project_view.setModel(self.project_view_model)
        self.project_view.doubleClicked.connect(self.project_tree_double_click)
        self.project_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.project_view.customContextMenuRequested.connect(self.project_tree_context_menu)

        self.editor_tabs.tabCloseRequested.connect(self.close_source_file)

    def project_tree_context_menu(self, point: QPoint):
        index = self.project_view.indexAt(point)
        if index.isValid():
            menu = QMenu()
            set_action = menu.addAction('Set as Main')
            remove_action = menu.addAction('Remove File')

            filename = self.project_view_model.itemFromIndex(index).text()

            res = menu.exec(self.project_view.viewport().mapToGlobal(point))
            if res not in {set_action, remove_action}:
                return

            if res == set_action:
                self.project.main_file = filename
                self.project.save()
                self.setup_project_tree()

            if res == remove_action:
                self.project.remove_file(filename)
                self.project.save()
                self.setup_project_tree()
        else:
            menu = QMenu()
            add_action = menu.addAction('Add File')

            res = menu.exec(self.project_view.viewport().mapToGlobal(point))

            if res != add_action:
                return

            home_dir = str(self.project.location)
            filename = QFileDialog.getOpenFileName(
                self, 'Open file', home_dir, 'code files (*.asm *.dasm)', options=QFileDialog.DontUseNativeDialog,
            )

            if not filename or not filename[0]:
                return

            sourcefile = os.path.relpath(filename[0], self.project.location)

            self.project.add_file(sourcefile)
            self.project.save()
            self.setup_project_tree()

    def project_tree_double_click(self, index):
        item = self.project_view.selectedIndexes()[0]

        filename = item.model().itemFromIndex(index).text()
        self.open_source_file_in_editor(filename)
        self.editor_tabs.setCurrentWidget(self.editor_windows[filename])

    def open_source_file_in_editor(self, filename):
        if filename in self.editor_windows:
            self.editor_windows[filename].activateWindow()
            return

        editor_window = EditorWindow(self.project.location, filename, self.go_to_definition)
        editor_window.show()

        self.editor_tabs.addTab(editor_window, filename)

        self.editor_windows[filename] = editor_window

    def go_to_definition(self, text):
        if time.time() - self.last_go_to_definition < 1:
            return

        self.last_go_to_definition = time.time()
        for file in self.project.files:
            with open(os.path.join(self.project.location, file), 'r') as f:
                for line_num, line in enumerate(f.readlines()):
                    if line.strip().split(' ')[0] == f':{text}':
                        self.select_line_in_editor(file, line_num)
                        return

    def close_source_file(self, index):
        editor: EditorWindow = self.editor_tabs.widget(index)
        editor.close()

        self.editor_windows.pop(editor.filename, None)

        self.editor_tabs.removeTab(index)

    def move_window_to_center(self):
        center_point = QDesktopWidget().availableGeometry().center()
        rect = self.frameGeometry()
        rect.moveCenter(center_point)
        self.move(rect.topLeft())

    def setup_project_tree(self):
        icon_file = QIcon(os.path.join('img', 'asm_file.png'))
        icon_main_file = QIcon(os.path.join('img', 'main_asm_file.png'))

        self.project_view_model.setRowCount(0)
        self.project_view.setRootIsDecorated(False)
        for filename in self.project.files:
            icon = icon_main_file if self.project.main_file == filename else icon_file
            self.project_view_model.appendRow(QtGui.QStandardItem(icon, filename))

        while self.editor_tabs.count():
            self.editor_tabs.removeTab(0)

        self.editor_windows.clear()

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
        timer.setInterval(16)
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
        timer.setInterval(16)
        timer.timeout.connect(self.update_hardware_ui)
        timer.start()
        self.timers.append(timer)

    def speed_changed(self):
        self.speed_multiplier = 10 ** self.speed.currentIndex()

    def action_create_project(self):
        self.create_project_window = CreateProjectWindow()
        self.create_project_window.exec_()
        if self.create_project_window.success:
            self.project = Project.load_from_file(self.create_project_window.project_location)
            self.project_file = self.create_project_window.project_location
            self.setup_project_tree()
            self.action_reset()

    def action_open_file(self):
        home_dir = str(Path.home())
        filename = QFileDialog.getOpenFileName(
            self, 'Open file', home_dir, 'project files (*.codespace)', options=QFileDialog.DontUseNativeDialog,
        )

        if filename and filename[0]:
            self.project = Project.load_from_file(filename[0])
            self.project_file = filename[0]
            self.setup_project_tree()
            self.action_reset()

    def action_step(self):
        if not self.emulator.regs.PC != 0:
            self.retranslate()

        self.emulator_state = EmulationState.STEP_REQUESTED
        self.actionReset.setEnabled(True)

    def action_run(self):
        if not self.emulator.regs.PC != 0:
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
        for editor in self.editor_windows.values():
            editor.close()

    def retranslate(self):
        try:
            self._retranslate()
        except TranslationError as err:
            self.select_line_in_editor(err.file, err.line)
            QMessageBox.warning(self, 'Translation Error', err.message)
        except Exception as ex:
            QMessageBox.warning(self, 'Unknown Translation Error', str(ex))

    def _retranslate(self):
        # save all changes
        for editor in self.editor_windows.values():
            editor.save_file()

        self.pc_to_line = {}

        tr = DCPUTranslator()

        bin_location = os.path.join(self.project.location, f'{self.project.name}.bin')
        with open(bin_location, 'wb') as f:
            pc = 0
            for file, line_num, _, instructions in tr.asm2bin(self.project.location, self.project.main_file):
                for code in instructions:
                    f.write(code.to_bytes(2, byteorder='little'))
                    # TODO: refactor this
                self.pc_to_line[pc] = (file, line_num)
                pc += len(instructions)

        self.emulator.preload(bin_location)

    def load_project_files(self):
        """ Reads .bin file, decodes instructions
            saves PC-to-instruction info.
        """
        self.pc_to_line = {}

        # translate and then load
        translator = DCPUTranslator()
        try:
            pc = 0
            for file, line_num, line, instructions in translator.asm2bin(self.project.location, self.project.main_file):
                self.pc_to_line[pc] = (file, line_num)
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
                    select_file, select_line = self.pc_to_line[pc]
                except:
                    break

                self.select_line_in_editor(select_file, select_line)

                QCoreApplication.processEvents()
                break

        self._dump_registers()

    def select_line_in_editor(self, select_file, select_line):
        if select_file not in self.editor_windows:
            self.open_source_file_in_editor(select_file)
        self.editor_windows[select_file].select_line(select_line)
        self.editor_tabs.setCurrentWidget(self.editor_windows[select_file])

    def _dump_registers(self):
        for i, reg in enumerate(['A', 'B', 'C', 'X', 'Y', 'Z', 'I', 'J', 'SP', 'PC', 'EX', 'IA']):
            item = self.registers.item(i, 0)
            item.setText(f'0x{self.emulator.regs[reg]:04x}')

        # variables hack
        tr = DCPUTranslator()
        dat_labels = []
        try:
            labels, _ = tr.translate(self.project.location, self.project.main_file, None, dat_labels)

            self.variables.setRowCount(0)

            for k in sorted(labels.keys()):
                if k in dat_labels:
                    value = labels[k]
                    row_position = self.variables.rowCount()
                    self.variables.insertRow(row_position)
                    self.variables.setItem(row_position, 0, QTableWidgetItem(k))
                    self.variables.setItem(row_position, 1, QTableWidgetItem(f'0x{self.emulator.ram[value]:04x}'))
        except TranslationError:
            print('Failed to dump variables')
            pass


def force_dark_mode():
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.black)
    palette.setColor(QPalette.ToolTipText, Qt.white)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project-file')
    parser.add_argument('--dark-mode', action='store_true', default=False)
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    app.setStyle("Fusion")
    if args.dark_mode:
        force_dark_mode()

    window = DevKitApp(args.project_file)
    window.show()
    app.exec_()
