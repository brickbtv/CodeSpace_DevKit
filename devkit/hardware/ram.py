from collections import defaultdict


class RAM:
    def __init__(self):
        self._ram = defaultdict(lambda: 0)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return [self[i] for i in range(*item.indices(len(self._ram)))]

        return self._ram[item]

    def __setitem__(self, key, value):
        self._ram[key] = value
