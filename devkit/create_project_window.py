import os
from pathlib import Path

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog, QMessageBox

from project.project import Project


class CreateProjectWindow(QDialog):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self):
        super().__init__()

        self.setWindowModality(QtCore.Qt.ApplicationModal)

        self.layout = QVBoxLayout()

        self.project_name_label = QLabel('Enter project name:')
        self.project_name = QLineEdit()
        self.project_location_label = QLabel('Select project location:')
        self.project_location_selected_label = QLabel('')
        self.project_location_select = QPushButton('Browse...')

        self.project_done = QPushButton('Done')

        self.layout.addWidget(self.project_name_label)
        self.layout.addWidget(self.project_name)
        self.layout.addWidget(self.project_location_label)
        self.layout.addWidget(self.project_location_select)
        self.layout.addWidget(self.project_location_selected_label)
        self.layout.addWidget(self.project_done)

        self.setLayout(self.layout)

        self.project_location_select.clicked.connect(self.browse)
        self.project_done.clicked.connect(self.create_project)

        self.project_location = ''
        self.success = False

    def browse(self):
        home_dir = str(Path.home())
        dirname = QFileDialog.getExistingDirectory(
            self, 'Select directory', home_dir, options=QFileDialog.DontUseNativeDialog,
        )

        if not dirname:
            return

        self.project_location_selected_label.setText(dirname)

    def create_project(self):
        name = self.project_name.text()
        location = self.project_location_selected_label.text()

        if not name:
            QMessageBox.warning(self, 'Project name', 'Project name is required')

        if not location:
            QMessageBox.warning(self, 'Project name', 'Project location is required')

        proj = Project(location, name)
        proj.save()

        self.project_location = proj.description_path
        self.success = True

        self.close()
