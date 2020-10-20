from collections import defaultdict


class RAM:
    def __init__(self):
        self._ram = defaultdict(lambda: 0)

    def __getitem__(self, item):
        return self._ram[item]

    def __setitem__(self, key, value):
        self._ram[key] = value
