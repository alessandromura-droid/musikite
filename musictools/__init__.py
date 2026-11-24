"""OLD NAME of the package (renamed musikite on 2026-11-24, owner's decision).

This folder only keeps old notebooks and scripts working: `import musictools`,
`from musictools.midi import Midi`, `python3 -m musictools ...` give the SAME modules of
musikite (one copy in memory, not a second one). New code: `import musikite`."""
import importlib
import importlib.abc
import importlib.util
import sys

import musikite as _mk

_OLD, _NEW = "musictools", "musikite"


class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """musictools.X -> the module musikite.X itself."""

    def __init__(self):
        self._specs = {}

    def find_spec(self, name, path=None, target=None):
        if name.startswith(_OLD + ".") and name != _OLD + ".__main__":
            return importlib.util.spec_from_loader(name, self)
        return None

    def create_module(self, spec):
        mod = importlib.import_module(_NEW + spec.name[len(_OLD):])
        self._specs[spec.name] = getattr(mod, "__spec__", None)
        return mod

    def exec_module(self, module):
        # the import system gave the module the spec of the old name: give it back its own
        for old, sp in list(self._specs.items()):
            if sys.modules.get(old) is module and sp is not None:
                module.__spec__ = sp
                del self._specs[old]


if not any(isinstance(f, _Alias) for f in sys.meta_path):
    sys.meta_path.insert(0, _Alias())


def __getattr__(name):
    return getattr(_mk, name)


def __dir__():
    return dir(_mk)
