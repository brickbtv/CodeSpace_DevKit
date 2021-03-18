import json
import os
from pathlib import Path


class Project:
    def __init__(self, location: str, name: str):
        self.location = location
        self.description_path = Path(self.location) / f'{name}.codespace'
        self.name = name

        self.data = {
            'files': [],
            'properties': {},
            'main_file': None,
        }

    def save(self):
        with self.description_path.open('w') as f:
            json.dump(self.data, f)

    def load(self):
        with self.description_path.open('r') as f:
            self.data = json.load(f)

    @staticmethod
    def load_from_file(filename: str):
        location, projfile = os.path.split(filename)
        name = os.path.splitext(projfile)[0]

        project = Project(location, name)
        project.load()

        return project

    def add_file(self, filename):
        self.data['files'].append(filename)

    def remove_file(self, filename):
        self.data['files'].append(filename)

    @property
    def main_file(self) -> str:
        return self.data['main_file']

    @main_file.setter
    def main_file(self, filename):
        self.data['main_file'] = filename

    @property
    def main_file_full(self):
        return os.path.join(self.location, self.main_file)

    @property
    def files(self):
        return self.data['files']

    def set_property(self, name, value):
        self.data['properties'][name] = value

    def get_property(self, name):
        return self.data['properties'].get(name)
