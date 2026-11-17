"""
Settings window (VLC style): on the left a tree of sections, on the right the
settings of the selected one. Every setting of the app is here:

    Folders
    Audio                 output, test sound, microphone (+ level meter), MIDI input (+ test)
      Soundfont
    Instruments           range of the exercises (written pitch) for trumpet and piano
    Exercises             how points and grades are computed
      Intervals
      Interval reading
      Read & play         questions, points, default bars, bpm, input, show first note
      Listen & repeat     questions, points, default bars, bpm, input, show first note

Save writes every page; Reset puts the defaults in the page shown.
"""
from ..exercise import (DEFAULTS, KINDS, KIND_LABELS, KIND_DEFAULTS, exercise_settings,
                        set_exercise_settings, clear_exercise_settings)

LABELS = dict(n_questions=("Questions per exercise", 1, 100, 1),
              base=("Points per right answer", 1, 10000, 10),
              harmonic_factor=("× harmonic", 0.1, 5, 0.1),
              melodic_factor=("× melodic", 0.1, 5, 0.1),
              fast_s=("Full points within (s)", 0, 60, 0.5),
              slow_s=("Minimum points from (s)", 0.5, 300, 0.5),
              slow_factor=("Minimum time factor", 0, 1, 0.05),
              replay_factor=("× for each replay", 0, 1, 0.05),
              bars=("Default bars per exercise", 1, 64, 1),
              bpm=("Tempo (bpm)", 30, 240, 1))
# settings shown for every exercise type
KIND_FIELDS = {
    "intervals": list(DEFAULTS),
    "interval_reading": list(DEFAULTS),
    "chords": list(DEFAULTS),
    "flashcards": list(DEFAULTS),
    "play_reading": ["n_questions", "base", "bars", "bpm", "input", "show_first_note", "click"],
    "listen_repeat": ["n_questions", "base", "bars", "bpm", "input", "show_first_note", "click"],
}
INPUTS = ("Microphone", "MIDI keyboard")


def _exercise_page(app, kind):
    from PySide6.QtWidgets import (QWidget, QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox,
                                   QLabel, QVBoxLayout, QCheckBox)
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel(f"<b>{KIND_LABELS[kind]}</b>"))
    form = QFormLayout()
    ctl = {}

    def build(cfg):
        for k in KIND_FIELDS[kind]:
            if k == "input":
                c = QComboBox()
                c.addItems(INPUTS)
                ctl[k] = c
                form.addRow("Input", c)
                continue
            if k == "show_first_note":
                c = QCheckBox("write the first note in the bar (e.g. G4; C4 = middle C)")
                ctl[k] = c
                form.addRow("Show first note", c)
                continue
            if k == "click":
                c = QCheckBox("metronome clicks during the exercise (count-in and beats)")
                ctl[k] = c
                form.addRow("Click", c)
                continue
            label, lo, hi, step = LABELS[k]
            c = QSpinBox() if k in ("n_questions", "bars", "bpm") else QDoubleSpinBox()
            c.setRange(lo, hi)
            if isinstance(c, QDoubleSpinBox):
                c.setDecimals(2)
                c.setSingleStep(step)
            ctl[k] = c
            form.addRow(label, c)

    def load(cfg):
        for k, c in ctl.items():
            if k == "input":
                c.setCurrentText(str(cfg.get(k, INPUTS[0])))
            elif k in ("show_first_note", "click"):
                c.setChecked(bool(cfg.get(k, k == "click")))
            elif isinstance(c, QDoubleSpinBox):
                c.setValue(float(cfg[k]))
            else:
                c.setValue(int(cfg[k]))

    build(None)
    load(exercise_settings(kind))
    lay.addLayout(form)
    if kind in ("play_reading", "listen_repeat"):
        lay.addWidget(QLabel("points = base × fraction of the notes recognised\n"
                             "Default bars: used by Generate > Generate exercises"))
    else:
        lay.addWidget(QLabel("points = base × harmonic/melodic × time factor × replay factor^replays"))
    lay.addWidget(QLabel("grade = 10 × points / (questions × max points); not answered = 0"))
    lay.addStretch()

    def values():
        return {k: (c.currentText() if k == "input" else c.isChecked()
                    if k in ("show_first_note", "click") else c.value()) for k, c in ctl.items()}

    def save():
        set_exercise_settings(kind, **values())

    def reset():
        cfg = dict(DEFAULTS)
        cfg.update(KIND_DEFAULTS.get(kind, {}))
        load(cfg)

    w.save, w.reset, w.values = save, reset, values
    return w


def _general_exercise_page(app):
    from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFormLayout, QComboBox
    from ..tasks import TODO_RULES, TODO_RULE, todo_rule
    w = QWidget()
    lay = QVBoxLayout(w)
    t = QLabel("<b>Exercises</b><br><br>Every exercise type has its own settings (choose it on "
               "the left).<br>An exercise is a block of N questions; at the end the grade is "
               "10 × points / (questions × max points).")
    t.setWordWrap(True)
    lay.addWidget(t)
    form = QFormLayout()
    rule = QComboBox()
    rule.addItems(list(TODO_RULES))
    rule.setCurrentText(todo_rule())
    rule.setToolTip("which exercises are shown TO DO in Objects (bold on grey)")
    form.addRow("To do in Objects", rule)
    from PySide6.QtWidgets import QSpinBox
    from .routine_ui import AUTO_S, auto_seconds
    auto = QSpinBox()
    auto.setRange(1, 120)
    auto.setSuffix(" s")
    auto.setValue(int(round(auto_seconds())))
    auto.setToolTip("routines with Auto-advance: seconds after an attempt before the next "
                    "exercise opens")
    form.addRow("Routine: next exercise after", auto)
    from ..staffview import CURSOR_MODES, cursor_mode
    cur = QComboBox()
    for k, label in CURSOR_MODES.items():
        cur.addItem(label, k)
    cur.setCurrentIndex(list(CURSOR_MODES).index(cursor_mode()))
    cur.setToolTip("how the red cursor moves on every staff: over each note / rest when it "
                   "starts, or from bar line to bar line at constant speed (on the bar "
                   "line at the downbeat, with the click)")
    form.addRow("Cursor", cur)
    lay.addLayout(form)
    lay.addStretch()

    def save():
        from ..progress import save_setting
        save_setting("todo_rule", rule.currentText())
        save_setting("routine_auto_s", auto.value())
        save_setting("cursor_mode", cur.currentData())
        if hasattr(app, "refresh_exercises"):
            app.refresh_exercises()

    def reset():
        rule.setCurrentText(TODO_RULE)
        auto.setValue(AUTO_S)
        cur.setCurrentIndex(0)
    w.save, w.reset = save, reset
    return w


def _pick(app, widget, title, start, folder_only=False, filters=""):
    """File / folder chooser: the NATIVE dialog of the system (macOS Finder panel),
    attached to the MAIN window, not to Settings: attached to Settings, its closing
    reached Settings as Cancel on macOS. Settings is brought back to the front
    afterwards. Returns the path or ''."""
    from PySide6.QtWidgets import QFileDialog
    parent = getattr(app, "win", None) or widget.window()
    if folder_only:
        p = QFileDialog.getExistingDirectory(parent, title, start or "")
    else:
        p = QFileDialog.getOpenFileName(parent, title, start or "", filters)[0]
    win = widget.window()
    if win is not None:
        win.show()
        win.raise_()
        win.activateWindow()
    return p or ""


def _plain_button(text):
    """A page button that can never act as the default (Return) button of the window."""
    from PySide6.QtWidgets import QPushButton
    b = QPushButton(text)
    b.setAutoDefault(False)
    b.setDefault(False)
    return b


def _folders_page(app):
    import os
    from PySide6.QtWidgets import (QWidget, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
                                   QVBoxLayout, QLabel, QFileDialog)
    from ..progress import FOLDERS, FOLDER_LABELS, FILES_HOME, folder, set_folder
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel(f"<b>Folders</b> of the user {app.user or '(none)'} — defaults in "
                         f"{FILES_HOME}, shared by all users"))
    form = QFormLayout()
    edits = {}
    for k in FOLDERS:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        e = QLineEdit(folder(k, create=False))
        e.setMinimumWidth(320)
        b = _plain_button("…")
        b.clicked.connect(lambda checked=False, e=e, k=k: (
            lambda p: e.setText(p) if p else None)(
            _pick(app, w, FOLDER_LABELS[k], e.text(), folder_only=True)))
        h.addWidget(e)
        h.addWidget(b)
        edits[k] = e
        form.addRow(FOLDER_LABELS[k], row)
    lay.addLayout(form)
    lay.addStretch()

    def save():
        for k, e in edits.items():
            p = e.text().strip()
            default = os.path.join(FILES_HOME, k)
            set_folder(k, None if (not p or os.path.expanduser(p) == default) else p)

    def reset():
        for k, e in edits.items():
            e.setText(os.path.join(FILES_HOME, k))

    w.save, w.reset, w.edits = save, reset, edits
    return w


def _instruments_page(app):
    """Range of the exercises per instrument (WRITTEN pitch): notes outside it are moved
    by octaves into it, one by one, when the exercises are generated."""
    from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QVBoxLayout, QLabel
    from ..phrase import INSTRUMENTS, RANGE_DEFAULT, instrument_range, set_instrument_range
    from ..notes import note_name
    w = QWidget()
    lay = QVBoxLayout(w)
    t = QLabel("<b>Instruments</b> — range of the generated exercises, written pitch "
               "(C4 = middle C). Notes outside it are moved by octaves into it, one by one. "
               "Exercises already generated do not change.")
    t.setWordWrap(True)
    lay.addWidget(t)
    form = QFormLayout()
    pitches = list(range(36, 97))                       # C2 .. C7
    ctl = {}
    for inst in INSTRUMENTS:
        short = inst.split("(")[-1].rstrip(")")         # trumpet, piano
        for i, what in enumerate(("Min", "Max")):
            c = QComboBox()
            c.addItems([note_name(p) for p in pitches])
            ctl[(inst, i)] = c
            form.addRow(f"{what} for {short}", c)
    lay.addLayout(form)
    msg = QLabel("")
    msg.setStyleSheet("color: red")
    lay.addWidget(msg)
    lay.addStretch()

    def load(get):
        for inst in INSTRUMENTS:
            lo_hi = get(inst)
            for i in (0, 1):
                ctl[(inst, i)].setCurrentIndex(pitches.index(min(max(lo_hi[i], 36), 96)))

    load(instrument_range)

    def values():
        return {inst: (pitches[ctl[(inst, 0)].currentIndex()],
                       pitches[ctl[(inst, 1)].currentIndex()]) for inst in INSTRUMENTS}

    def save():
        for inst, (lo, hi) in values().items():
            try:
                set_instrument_range(inst, lo, hi)
            except ValueError as e:
                msg.setText(f"{inst}: {e}")
                raise

    w.save, w.reset, w.values = save, (lambda: load(lambda i: RANGE_DEFAULT[i])), values
    return w


def _soundfont_page(app):
    from PySide6.QtWidgets import (QWidget, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout,
                                   QLabel, QFileDialog)
    from ..midi import Midi
    from ..progress import folder
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("<b>Soundfont</b> (.sf2) used to play objects, exercises and clicks"))
    row = QHBoxLayout()
    e = QLineEdit(Midi._default_sf2 or "")
    b = _plain_button("Browse…")
    status = QLabel("")
    status.setWordWrap(True)

    def load(p):
        """Load and save the soundfont AT ONCE (no need to press Save)."""
        import os
        p = os.path.expanduser(p.strip())
        if not p:
            return False
        if not os.path.isfile(p):
            status.setStyleSheet("color: red")
            status.setText(f"file not found: {p}")
            app.log(f"soundfont not loaded: file not found: {p}")
            return False
        try:
            app.set_soundfont(p)
        except Exception as ex:
            status.setStyleSheet("color: red")
            status.setText(f"not loaded: {type(ex).__name__}: {ex}")
            app.log(f"soundfont not loaded: {p}: {type(ex).__name__}: {ex}")
            return False
        status.setStyleSheet("color: green")
        status.setText(f"loaded and saved: {Midi._default_sf2}")
        return True

    def browse():
        start = os.path.dirname(e.text().strip()) if e.text().strip() else folder("soundfonts")
        p = _pick(app, w, "Soundfont", start, filters="SoundFont (*.sf2 *.sf3);;All files (*)")
        if p:
            e.setText(p)
            load(p)

    import os
    b.clicked.connect(browse)
    e.returnPressed.connect(lambda: load(e.text()))
    row.addWidget(e, 1)
    row.addWidget(b)
    lay.addLayout(row)
    lay.addWidget(status)
    lay.addStretch()

    def save():
        p = e.text().strip()
        if p and p != (Midi._default_sf2 or ""):
            load(p)

    w.save, w.reset, w.edit, w.load, w.status = save, (lambda: None), e, load, status
    return w


def settings_dialog(app, page=None):
    """The Settings window; page: 'Folders', 'Audio', 'Soundfont', 'Exercises' or the
    label of an exercise type."""
    from PySide6.QtWidgets import (QDialog, QTreeWidget, QTreeWidgetItem, QStackedWidget,
                                   QHBoxLayout, QVBoxLayout, QPushButton, QSplitter)
    from PySide6.QtCore import Qt
    from .audiodialog import audio_page
    d = QDialog(app.win)
    d.setWindowTitle("Settings")
    d.resize(900, 620)
    lay = QVBoxLayout(d)
    split = QSplitter()
    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.setMinimumWidth(200)
    stack = QStackedWidget()
    split.addWidget(tree)
    split.addWidget(stack)
    split.setStretchFactor(1, 1)
    lay.addWidget(split, 1)
    pages, items = {}, {}

    def add(label, widget, parent=None):
        it = QTreeWidgetItem([label])
        (parent.addChild(it) if parent is not None else tree.addTopLevelItem(it))
        stack.addWidget(widget)
        pages[label] = widget
        items[label] = it
        it.setData(0, Qt.UserRole, label)
        return it

    add("Folders", _folders_page(app))
    audio = add("Audio", audio_page(app))
    add("Soundfont", _soundfont_page(app), audio)
    add("Instruments", _instruments_page(app))
    ex = add("Exercises", _general_exercise_page(app))
    for k in KINDS:
        add(KIND_LABELS[k], _exercise_page(app, k), ex)
    tree.expandAll()
    tree.currentItemChanged.connect(
        lambda cur, prev: stack.setCurrentWidget(pages[cur.data(0, Qt.UserRole)]) if cur else None)
    tree.setCurrentItem(items.get(page or "Folders", items["Folders"]))

    def save_all():
        bad = []
        for name, p in pages.items():
            try:
                p.save()
            except Exception as e:
                bad.append(name)
                app.log(f"settings ({name}): {type(e).__name__}: {e}")
        if bad:                                   # stay open on the page to correct
            tree.setCurrentItem(items[bad[0]])
            return
        app.log("settings saved")
        d.accept()

    def reset_page():
        stack.currentWidget().reset()

    row = QHBoxLayout()
    for text, fn in (("Reset page", reset_page),):
        b = QPushButton(text)
        b.clicked.connect(fn)
        row.addWidget(b)
    row.addStretch()
    for text, fn in (("Cancel", d.reject), ("Save", save_all)):
        b = QPushButton(text)
        b.clicked.connect(fn)
        if text == "Save":
            b.setDefault(True)
        row.addWidget(b)
    lay.addLayout(row)
    d.finished.connect(lambda *_: getattr(pages["Audio"], "stop", lambda: None)())
    d.rejected.connect(lambda: app.log("settings closed without saving (Cancel / Esc / window "
                                       "closed); a soundfont chosen with Browse is already saved"))
    for btn in d.findChildren(QPushButton):          # only Save answers to Return
        if btn.text() != "Save":
            btn.setAutoDefault(False)
    d.pages, d.tree, d.save_all = pages, tree, save_all

    def select(name):
        tree.setCurrentItem(items[name])
    d.select = select
    return d


# compatibility: the old separate dialogs open the right page
def exercise_dialog(app):
    return settings_dialog(app, page="Exercises")


def folders_dialog(app):
    return settings_dialog(app, page="Folders")
