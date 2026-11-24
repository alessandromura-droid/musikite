"""
Practice > Exercise from library (owner, 2026-11-19). Logic in library.py / translate.py (no
Qt). The tab lists EVERY melody of the library (system + user) for the instrument chosen
beside the user, ordered by its difficulty for that instrument (in the key without
accidentals; selector Difficulty: All / 0 … 10), the ones never done by the user (any key)
in BOLD, the done ones in normal type (box "To do only" hides them). KEY: Auto (a key
signature with few accidentals for an easy level, many for a hard one: the level selected,
else the melody's difficulty) or a written tonic (the melody's mode is kept). Add to
Objects or a DRAG onto Objects > Exercises puts the EXERCISE there — the melody in that
key, translated for the instrument — (if it is already there it is selected); DOUBLE CLICK
and Do it put it there AND open it (owner, 2026-11-20). The difficulty for an instrument is
computed once (a few at a time, the tab stays usable) and kept.

COLUMNS (owner, 2026-11-20): Title, Difficulty, Key (written), Bars, Type (original, the
transformation of a transformed melody — "dorian", "inversion", "retrograde, lydian"… —,
crossed, generated, user: `library.type_label`); every column SORTABLE by a click on its
header, again = the other way (numbers as numbers, titles in natural order, keys C … B).
At start: by difficulty.

Right click in Objects on a MIDI ♪ (its melody) or on an exercise ♩ (Read & play / Listen &
repeat) > Add to library…: only a name is asked (`add_to_library_dialog`).

From code:  w = app.open_tool('library'); w.set_level(3); w.add_ids([...])
"""
import json

from . import registry

MIME = "application/x-musikite-library"
CHUNK = 60                      # difficulties computed per timer tick
LEVELS = ["All"] + [str(k) for k in range(11)]
COLUMNS = ["Title", "Difficulty", "Key (written)", "Bars", "Type"]
COL_TITLE, COL_DIFFICULTY = 0, 1


def natural_key(text):
    """Natural order of a text: case ignored, numbers inside it as numbers ("Etude 2"
    before "Etude 10")."""
    import re
    return [(0, int(t), "") if t.isdigit() else (1, 0, t.casefold())
            for t in re.split(r"(\d+)", str(text or "")) if t]


def add_entries(app, ids, instrument=None, tonic=None, level=None):
    """Library exercises into Objects > Exercises (for `instrument`, default the one beside
    the user; tonic: written tonic 0-11 or None = Auto for `level`, None = the melody's
    difficulty); one already there is selected, not added twice. Returns names."""
    from .. import library, instruments as ins
    instrument = instrument or ins.current()
    lib = library.get()
    by_uid = {}
    for n, o in app.objects.items():
        u = getattr(o, "uid", None)
        if u:
            by_uid[u] = n
    names = []
    for lid in ids:
        e = lib.entry(lid)
        if e is None:
            app.log(f"library: exercise {lid} not found")
            continue
        lv = level if level is not None else lib.known_difficulty(e, instrument)
        t = library.chosen_tonic(e, instrument, tonic, lv)
        uid = library.exercise_uid(lid, instrument, t)
        if uid in by_uid:
            names.append(by_uid[uid])
            continue
        try:
            ph = lib.exercise(e, instrument, t)
        except Exception as ex:
            app.log(f"library: {e.get('title')}: {type(ex).__name__}: {ex}")
            continue
        if not ph.practice_bpm:
            ph.practice_bpm = float(e.get("bpm") or ph.bpm)
        name = app.add_object(ph, ph.title)
        by_uid[uid] = name
        names.append(name)
    if names:
        app.select(*names)
        app.refresh_exercises()
    return names


def add_to_library_dialog(app, ph):
    """Right click > Add to library… (a MIDI or a Read & play / Listen & repeat exercise):
    a name is asked; the metadata (key, range, difficulty…) are computed."""
    from PySide6.QtWidgets import QInputDialog
    from .. import library
    name, ok = QInputDialog.getText(app.win, "Add to library",
                                    "Name of the melody in the library:",
                                    text=getattr(ph, "title", "") or "")
    if not ok or not name.strip():
        return None
    try:
        e, added = library.get().add(ph, name.strip())
    except Exception as ex:
        app.log(f"add to library: {type(ex).__name__}: {ex}")
        return None
    if added:
        d = e.get("difficulty")
        app.log(f"added to the library: {e['title']} (difficulty "
                f"{'-' if d is None else f'{d:.1f}'}, {e['bars']} bars, {e['notes']} notes)")
    else:
        app.log(f"already in the library: {e['title']}")
    w = app.tool_widgets.get("library")
    if w is not None and hasattr(w, "refresh"):
        w.refresh()
    return e


def drop_filter(app):
    """Event filter of the Objects > Exercises list: it TAKES library exercises dragged
    from the library tab (MIME), nothing else (the list itself stays drag-only)."""
    from PySide6.QtCore import QObject, QEvent, Qt

    class LibraryDrop(QObject):
        def eventFilter(self, obj, ev):
            t = ev.type()
            if t in (QEvent.DragEnter, QEvent.DragMove):
                if ev.mimeData().hasFormat(MIME):
                    ev.setDropAction(Qt.CopyAction)
                    ev.accept()
                else:
                    ev.ignore()
                return True
            if t == QEvent.DragLeave:
                return True
            if t == QEvent.Drop:
                if ev.mimeData().hasFormat(MIME):
                    try:
                        d = json.loads(bytes(ev.mimeData().data(MIME)).decode("utf-8"))
                        add_entries(app, d.get("ids") or [], d.get("instrument"),
                                    d.get("tonic"), d.get("level"))
                    except Exception as ex:
                        app.log(f"library drop: {type(ex).__name__}: {ex}")
                    ev.setDropAction(Qt.CopyAction)
                    ev.accept()
                else:
                    ev.ignore()
                return True
            return False

    return LibraryDrop(app.win)


def _widget_class():
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                                   QCheckBox, QTreeWidget, QTreeWidgetItem, QAbstractItemView,
                                   QHeaderView)
    from PySide6.QtCore import Qt, QTimer, QMimeData, QByteArray
    from .bar import action_bar

    class LibraryItem(QTreeWidgetItem):
        """A row; `keys` = sort key of every column (sorting by a header click; equal
        values: by title)."""

        def __lt__(self, other):
            tw = self.treeWidget()
            c = tw.sortColumn() if tw is not None else COL_DIFFICULTY
            a = getattr(self, "keys", None)
            b = getattr(other, "keys", None)
            if a is None or b is None or not 0 <= c < len(a):
                return super().__lt__(other)
            return (a[c], a[COL_TITLE]) < (b[c], b[COL_TITLE])

    class LibraryTree(QTreeWidget):
        """The list GIVES its selection as library ids (drag onto Objects > Exercises)."""

        def __init__(self, owner):
            super().__init__()
            self.owner = owner

        def mimeTypes(self):
            return [MIME]

        def mimeData(self, items):
            ids = [it.data(0, Qt.UserRole) for it in items if it.data(0, Qt.UserRole)]
            md = QMimeData()
            md.setData(MIME, QByteArray(json.dumps(dict(
                ids=ids, instrument=self.owner.instrument, tonic=self.owner.tonic(),
                level=self.owner.level_value())).encode("utf-8")))
            return md

    class LibraryWidget(QWidget):
        def __init__(self, app):
            super().__init__()
            from .. import library, instruments as ins
            self.app = app
            self.lib = library.get()
            self.instrument = ins.current()
            self.bar, _ = action_bar([
                ("Add to Objects", self.add_selected, "the selected exercises into Objects > "
                                                      "Exercises (also: drag them there)"),
                ("Do it", self.do_selected, "add the selected exercise and do it (also: "
                                            "double click)"),
                ("Refresh", self.refresh, "read the library and the results again")])
            lay = QVBoxLayout(self)
            row = QHBoxLayout()
            self.instr_lbl = QLabel("")
            self.level = QComboBox()
            self.level.addItems(LEVELS)
            self.level.setToolTip("difficulty 0-10 for this instrument (rounded)")
            from ..library import WRITTEN_TONICS
            self.key = QComboBox()
            self.key.addItem("Auto", None)
            for t, name in enumerate(WRITTEN_TONICS):
                self.key.addItem(name, t)
            self.key.setToolTip("written tonic of the exercises (the mode of each melody is "
                                "kept); Auto: few accidentals for an easy level, many for a "
                                "hard one")
            self.todo_only = QCheckBox("To do only")
            self.todo_only.setToolTip("hide the exercises you have already done")
            self.status = QLabel("")
            for w in (self.instr_lbl, QLabel("Difficulty:"), self.level, QLabel("Key:"),
                      self.key, self.todo_only):
                row.addWidget(w)
            row.addStretch()
            row.addWidget(self.status)
            lay.addLayout(row)
            self.tree = LibraryTree(self)
            self.tree.setHeaderLabels(COLUMNS)
            self.tree.setRootIsDecorated(False)
            self.tree.setUniformRowHeights(True)
            self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
            self.tree.setDragEnabled(True)
            self.tree.setDragDropMode(QAbstractItemView.DragOnly)
            self.tree.header().setSectionResizeMode(COL_TITLE, QHeaderView.Stretch)
            # every column sortable (owner, 2026-11-20); at start by difficulty
            self.tree.setSortingEnabled(True)
            self.tree.sortByColumn(COL_DIFFICULTY, Qt.AscendingOrder)
            # double click = into Objects > Exercises AND open (owner, 2026-11-20)
            self.tree.itemDoubleClicked.connect(lambda it, col: self.do_ids(
                [it.data(0, Qt.UserRole)]))
            lay.addWidget(self.tree, 1)
            self.timer = QTimer(self)
            self.timer.setInterval(0)
            self.timer.timeout.connect(self._compute_some)
            self._pending = []
            self._total = 0
            self.level.currentTextChanged.connect(lambda _t: self.fill())
            self.key.currentIndexChanged.connect(lambda _i: self.fill())
            self.todo_only.toggled.connect(lambda _v: self.fill())
            self._listener = self._attempt
            app._attempt_listeners.append(self._listener)
            self.refresh()

        def _attempt(self, obj):
            """An attempt on an exercise: done / to do redrawn (only when the tab is seen)."""
            try:
                if self.isVisible():
                    self.fill()
            except RuntimeError:                      # the tab is gone
                pass

        # ------------------------------------------------------ data
        def refresh(self):
            from .. import instruments as ins, library
            self.lib = library.get().reload()
            self.instr_lbl.setText(f"Instrument: <b>{ins.label(self.instrument)}</b>")
            self.timer.stop()
            self._pending = self.lib.pending(self.instrument)
            self._total = len(self._pending)
            if self._pending:
                self.timer.start()
            self.fill()
            return self

        def _compute_some(self):
            for e in self._pending[:CHUNK]:
                self.lib.difficulty(e, self.instrument)
            self._pending = self._pending[CHUNK:]
            done = self._total - len(self._pending)
            if done % 1200 < CHUNK:
                self.lib.save_cache()
            if self._pending:
                self.status.setText(f"difficulty for this instrument: {done}/{self._total}")
                return
            self.timer.stop()
            self.lib.save_cache()
            self.fill()

        def _difficulty(self, e):
            d = self.lib.known_difficulty(e, self.instrument)
            return (e.get("difficulty") if d is None else d), d is not None

        def tonic(self):
            """Written tonic chosen (0-11) or None = Auto."""
            return self.key.currentData()

        def level_value(self):
            t = self.level.currentText()
            return None if t == "All" else int(t)

        def fill(self):
            from .. import library
            entries = self.lib.entries()
            done = self.lib.done_uids(self.app.user)
            lvl = self.level.currentText()
            rows = []
            for e in entries:
                d, known = self._difficulty(e)
                if lvl != "All" and (d is None or int(round(d)) != int(lvl)):
                    continue
                is_done = self.lib.is_done(e, self.instrument, done)
                if is_done and self.todo_only.isChecked():
                    continue
                rows.append((e, d, known, is_done))
            self.tree.setUpdatesEnabled(False)
            self.tree.setSortingEnabled(False)          # rows added unsorted, sorted once
            self.tree.clear()
            items = []
            n_todo = 0
            lv_sel = self.level_value()
            for e, d, known, is_done in rows:
                t = library.chosen_tonic(e, self.instrument, self.tonic(),
                                         lv_sel if lv_sel is not None else d)
                mode = e.get("mode", "ionian")
                kind = library.type_label(e)
                it = LibraryItem([e["title"],
                                  "" if d is None else f"{d:.1f}" + ("" if known else " …"),
                                  library.key_name(t, mode), str(e.get("bars", "")), kind])
                it.keys = [natural_key(e["title"]),
                           (0, float(d)) if d is not None else (1, 0.0),
                           (int(t) % 12, mode),
                           int(e.get("bars") or 0),
                           natural_key(kind)]
                it.setData(0, Qt.UserRole, e["id"])
                if not is_done:
                    n_todo += 1
                    f = it.font(COL_TITLE)
                    f.setBold(True)
                    for c in range(len(COLUMNS)):
                        it.setFont(c, f)
                if e.get("user"):
                    it.setToolTip(COL_TITLE, "added to the library by a user")
                items.append(it)
            self.tree.addTopLevelItems(items)
            self.tree.setSortingEnabled(True)           # by the column of the header
            self.tree.setUpdatesEnabled(True)
            if not entries:
                self.status.setText("the library is empty (scripts/build_library.py)")
            elif not self._pending:
                self.status.setText(f"{len(rows)} exercises, {n_todo} to do")
            return len(rows)

        # ------------------------------------------------------ actions
        def selected_ids(self):
            return [it.data(0, Qt.UserRole) for it in self.tree.selectedItems()]

        def add_ids(self, ids):
            return add_entries(self.app, [i for i in ids if i], self.instrument, self.tonic(),
                               self.level_value())

        def add_selected(self):
            ids = self.selected_ids()
            if not ids:
                self.status.setText("select one or more exercises")
                return []
            return self.add_ids(ids)

        def do_selected(self):
            names = self.add_selected()
            if names:
                return self.app.open_exercise(names[0])
            return None

        def do_ids(self, ids):
            """Double click (owner, 2026-11-20): into Objects > Exercises and opened."""
            names = self.add_ids(ids)
            if names:
                return self.app.open_exercise(names[0])
            return None

        def set_level(self, level):
            self.level.setCurrentText("All" if level in (None, "All") else str(int(level)))
            return self

        # ------------------------------------------------------ app hooks
        def instrument_changed(self, key):
            self.instrument = key
            self.refresh()

        def user_changed(self, name):
            self.fill()

        def closing(self):
            self.timer.stop()
            self.lib.save_cache()
            try:
                self.app._attempt_listeners.remove(self._listener)
            except ValueError:
                pass

    return LibraryWidget


registry.register(registry.Tool(
    name="library", label="Exercise from library", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="Every melody of the library for your instrument, ordered by difficulty (click a "
         "column header to sort by it); the ones never done in bold; Key: Auto (by "
         "difficulty) or a tonic. Add to Objects or drag one onto Objects > Exercises: the "
         "exercise is made in that key for your instrument; double click or Do it: made "
         "and opened."))
