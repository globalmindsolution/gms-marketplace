"""One JSON document on disk, written atomically (see docs/adr/0001)."""

import json
import os
import tempfile

EMPTY = {"products": {}, "stock": {}, "orders": {}, "charges": {}}


class Store:
    def __init__(self, path):
        self.path = path
        self.data = {k: dict(v) for k, v in EMPTY.items()}
        if os.path.exists(path):
            with open(path) as fh:
                loaded = json.load(fh)
            for key in EMPTY:
                self.data[key] = dict(loaded.get(key, {}))

    def save(self):
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".store-", suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def section(self, name):
        if name not in self.data:
            raise KeyError("unknown section %r" % name)
        return self.data[name]
