"""
Tool registry: the GUI is only a container; every tool declares itself here
once and the menus are built from this list.

kind:
  'session'   interactive tool opened in its own tab (exercises, ear training);
              factory(app) -> QWidget
  'transform' tool that takes the objects selected in Objects (if it has
              inputs) and returns new objects; func(*objects, **params) -> object
  'planned'   a menu item of a tool still to write (owner: "so I remember them"):
              it only writes in the Log that it is not there yet
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

CATEGORIES = ("Generate", "Convert", "Practice", "Analyse")


@dataclass
class Param:
    """One option of a transform tool; the GUI builds the matching control.
    kind: 'int', 'float', 'bool', 'str', 'choice' (one of choices),
    'multi' (any subset of choices; empty = None), 'tracks' (check list of the tracks of the
    first selected input: choices(obj) -> [(index, label, checked)], maximum = how many at
    most; value = the indices); for 'int', choices=("text",) = the text shown for the
    minimum (e.g. "start"). default: a value or a function.
    LINKED FIELDS (owner, 2026-11-13: duet / canon Key and Chords): `button` = text of a
    button beside the field ('str' / 'choice'), `action(values)` -> {name: new value} run by
    it; `on_change(old, new, values)` -> {name: new value} run when the field changes (a
    choice at once, a text when its editing ends); the values it returns are set without
    starting other on_change. Plain functions without Qt (Android)."""
    name: str
    kind: str
    default: object = None
    label: str = ""
    choices: tuple = ()
    minimum: float = None
    maximum: float = None
    step: float = None
    help: str = ""
    button: str = ""
    action: Optional[Callable] = None
    on_change: Optional[Callable] = None

    def value(self):
        """The default value; `default` may be a function, read each time (e.g. a value
        from Settings, so the panel always starts from the current setting)."""
        return self.default() if callable(self.default) else self.default


@dataclass
class Tool:
    name: str                          # identifier, e.g. 'intervals'
    label: str                         # menu text
    category: str                      # one of CATEGORIES
    kind: str = "session"
    factory: Optional[Callable] = None # session: factory(app) -> QWidget
    func: Optional[Callable] = None    # transform: func(*objects, **params)
    inputs: tuple = ()                 # transform: object types accepted; the input is the
                                       # selection in Objects (the tool runs once per object)
    multi: bool = False                # transform: one run with all the selected objects
    params: list = field(default_factory=list)   # list of Param
    name_fn: Optional[Callable] = None # transform: name of the new object from params
    help: str = ""
    submenu: str = ""                  # menus: put the tool in this submenu of its category
    # INSTRUMENT (owner, 2026-11-18): available(instrument key) -> bool; False = the menu item
    # is disabled for the instrument chosen beside the user (lip slurs only on valve brass,
    # long tones only on wind instruments). None = every instrument.
    available: Optional[Callable] = None
    # session: opener(app) -> widget, called by open_tool INSTEAD of "the tab already open
    # comes to the front" (Play over MIDI, 2026-11-23: a new MIDI selected must give a new
    # tab, not the one of the previous piece). None = the usual one tab per tool.
    opener: Optional[Callable] = None
    # INSTRUMENT FAMILIES the tool is for (catalogue families: 'brass', 'woodwind', 'sax',
    # 'keyboard'); () = families_of(): every instrument unless listed in _FAMILY_BY_NAME.
    # Another instrument beside the user = the menu item greyed (owner, 2026-11-24).
    families: tuple = ()


TOOLS = {}

# NO FAMILY SUBMENUS (owner, 2026-11-24, replaces the "All instruments / Brass / Woodwinds
# / Piano" submenus of the same day): Practice and Generate list every tool; a tool that is
# not for the instrument beside the user is greyed and cannot be chosen. Families of the
# catalogue (instruments.CATALOGUE 'family'); lip slurs and long tones use `available`.
_FAMILY_BY_NAME = {
    "duet": ("brass",), "canon": ("brass",), "brass_ensemble": ("brass",),
    "free_player": ("keyboard",),
}


def families_of(tool):
    """Instrument families the tool is for; () = every instrument."""
    return tuple(tool.families) or _FAMILY_BY_NAME.get(tool.name, ())


def register(tool):
    if tool.category not in CATEGORIES:
        raise ValueError(f"unknown category {tool.category}")
    TOOLS[tool.name] = tool
    return tool


def by_category(category):
    return [t for t in TOOLS.values() if t.category == category]


def is_available(tool, instrument):
    """The tool fits the instrument chosen beside the user."""
    try:
        fams = families_of(tool)
        if fams:
            from .. import instruments as ins
            if ins.row(instrument)["family"] not in fams:
                return False
        return tool.available is None or bool(tool.available(instrument))
    except Exception:
        return True


def for_instrument(kind):
    """available() of a drill kind: lip slurs = valve brass, long tones = wind instruments."""
    from .. import instruments as ins
    if kind == "lip_slurs":
        return ins.has_lip_slurs
    if kind == "long_tones":
        return ins.is_wind
    return None
