import os

from PyQt5 import QtGui
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QKeySequence, QTextCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QShortcut

from devkit_code_editor import QCodeEditor, DCPUHighlighter


class EditorWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self, workdir, filename, close_cback):
        super().__init__()
        self.setWindowTitle(filename)
        self.layout = QVBoxLayout()

        self.pc_to_line = {}
        self.hl = None
        self.filename = filename
        self.close_cback = close_cback

        self.file_full = os.path.join(workdir, filename)
        self.code = self.setup_code_editor(self.file_full)
        self.layout.addWidget(self.code)

        self.setLayout(self.layout)

        self.resize(400, 1000)

    def setup_code_editor(self, filename):
        """ Replaces basic text editor widget by custom code editor widget """

        better_code = QCodeEditor(self, self.pc_to_line, True)

        font = QtGui.QFont()
        font.setFamily('Ubuntu')
        font.setPointSize(11)

        better_code.setFont(font)
        better_code.setObjectName("code")
        better_code.setLineWrapMode(better_code.NoWrap)
        better_code.setTabStopWidth(30)

        with open(filename) as f:
            for line in f.readlines():
                better_code.appendPlainText(line.rstrip())

        better_code.setEnabled(True)

        cursor = better_code.cursorForPosition(QPoint(0, 0))
        better_code.setTextCursor(cursor)

        self.hl = DCPUHighlighter(better_code.document())

        shortcut = QShortcut(QKeySequence("Ctrl+S"), better_code)
        shortcut.activated.connect(self.save_file)

        return better_code

    def closeEvent(self, event):
        self.close_cback(self.filename)
        self.save_file()

    def select_line(self, selectline):
        cursor = QTextCursor(self.code.document().findBlockByLineNumber(selectline))
        self.code.setTextCursor(cursor)

    def enable(self):
        self.code.setDisabled(False)

    def disable(self):
        self.code.setDisabled(True)

    def save_file(self):
        data = self.code.toPlainText()
        with open(self.file_full, 'w') as f:
            f.write(data)
