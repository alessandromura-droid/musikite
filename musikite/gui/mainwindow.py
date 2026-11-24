"""
Main window: a container of tools.

  menus      File, Edit, View, Generate/Convert/Practice/Analyse (built from the
             tool registry), Audio, Help
  toolbar    current user (results are saved per user) + new user
  left       Objects: Midi/Score/Notes/Pdf, exercise sets (expandable groups of
             phrases) and exercise results, each type with its colour and symbol;
             several can be selected: transform tools work on the selection
  centre     tabs: one per open session tool or view (fixed, cannot be closed)
  right      Tools: options of the current transform tool (title "Tools" for every tool)
  bottom     Log

Drivable from Jupyter (show() switches on the Qt loop like %gui qt):

    app = musikite.gui()
    app.set_user('Teresa')
    w = app.open_tool('intervals')
    app.add_object(score, 'Duetto')
    name = app.run_tool('duet', level=2, seed=5)     # Generate > Duet
    app.view_object(name); app.play_object(name); app.save_object(name, 'd.mid')
    app.open_file('parte.pdf'); app.run_tool('pdf2midi', 'parte')
"""
import os

from ..progress import (Progress, settings, save_setting, set_current_user, current_user,
                        last_user, users as _users, folder, workspace_path)
from . import registry


ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "icon.png")


def _app():
    """The QApplication, with the MusiKitE icon (windows and, on macOS, the Dock)."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    app = QApplication.instance() or QApplication([])
    if os.path.isfile(ICON):
        app.setWindowIcon(QIcon(ICON))
    return app


APP_NAME = "MusiKitE"
# default soundfont in musikite/data (S. Christian Collins, free licence): used when the
# user has chosen none (owner, 2026-11-17)
DEFAULT_SF2 = "GeneralUser-GS.sf2"


def _close_filter_class():
    from PySide6.QtCore import QObject, QEvent

    class CloseFilter(QObject):
        """Calls fn when the main window is closed (automatic workspace save)."""

        def __init__(self, fn):
            super().__init__()
            self.fn = fn

        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Close:
                self.fn()
            return False
    return CloseFilter


def _CloseFilter(fn):
    return _close_filter_class()(fn)


def _exercise_instrument(obj):
    """The instrument an exercise object is played on ('trumpet', 'piano'…; a group or a
    routine: its first exercise that has one), None = any instrument."""
    try:
        items = getattr(obj, "items", None)
        if isinstance(items, list) and items and isinstance(items[0], dict):
            for it in items:
                i = _exercise_instrument(it.get("obj"))
                if i:
                    return i
            return None
        phrases = getattr(obj, "phrases", None)
        if isinstance(phrases, list):
            for ph in phrases:
                i = _exercise_instrument(ph)
                if i:
                    return i
            return None
        i = getattr(obj, "instrument", None)
        return i if isinstance(i, str) and i != "other" else None
    except Exception:
        return None


def _busy(w):
    """Is a tab doing something that a preview must not interrupt (an exercise, a take, a
    recording, Play over MIDI playing)?"""
    for attr in ("busy", "_running"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                if f():
                    return True
            except Exception:
                pass
    return False


def _key_filter(app):
    """COMPUTER KEYBOARD (owner, 2026-11-17): the keys a w s e d f t g y h u j k o l p ò
    (z x octave, c v velocity) go to midiin.ComputerKeyboard while a KeyboardSynth has it
    open (Free player, an exercise take, Test MIDI) and no text / number field has the
    focus; Cmd / Ctrl / Alt shortcuts stay as they are. Leaving the program releases the
    keys held (no hanging note)."""
    from PySide6.QtCore import QObject, QEvent, Qt
    from PySide6.QtWidgets import (QApplication, QLineEdit, QAbstractSpinBox, QTextEdit,
                                   QPlainTextEdit, QComboBox, QCheckBox, QRadioButton,
                                   QAbstractButton, QAbstractItemView)

    class KeyFilter(QObject):
        def eventFilter(self, obj, ev):
            t = ev.type()
            if t == QEvent.ApplicationDeactivate:
                try:
                    from ..midiin import ComputerKeyboard
                    ComputerKeyboard.release_all()
                except Exception:
                    pass
                return False
            if t not in (QEvent.KeyPress, QEvent.KeyRelease):
                return False
            # SPACE BAR = STOP (owner, 2026-11-18): while an object is played with Play, the
            # space bar stops it (not while typing in a field). SPACE BAR = START / STOP OF
            # THE AUDIO (owner's rule, 2026-11-23): otherwise the tab in front decides, if it
            # has space_bar() -> True when used (Play over MIDI: its Start / Stop)
            try:
                if t == QEvent.KeyPress and ev.key() == Qt.Key_Space and not ev.isAutoRepeat() \
                        and not (ev.modifiers() & (Qt.ControlModifier | Qt.MetaModifier
                                                   | Qt.AltModifier)):
                    fw = QApplication.focusWidget()
                    typing = isinstance(fw, (QLineEdit, QAbstractSpinBox, QTextEdit,
                                             QPlainTextEdit)) or \
                        (isinstance(fw, QComboBox) and fw.isEditable())
                    if not typing:
                        if app.is_playing():
                            app.stop_sound()
                            return True
                        w = app.tabs.currentWidget() if getattr(app, "tabs", None) else None
                        f = getattr(w, "space_bar", None)
                        if callable(f) and f():
                            return True
                # THE SPACE BAR NEVER TICKS / UNTICKS A BOX (owner's rule, 2026-11-23): on a
                # check box, radio button, checkable button or list / tree (checkable items)
                # with the focus, press AND release of the space bar are eaten
                if ev.key() == Qt.Key_Space:
                    fw = QApplication.focusWidget()
                    if isinstance(fw, (QCheckBox, QRadioButton, QAbstractItemView)) or (
                            isinstance(fw, QAbstractButton) and fw.isCheckable()):
                        return True
            except Exception:
                pass
            try:
                from ..midiin import ComputerKeyboard as CK
                if not CK.active():
                    return False
                if ev.modifiers() & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier):
                    return False
                fw = QApplication.focusWidget()
                if isinstance(fw, (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)) or (
                        isinstance(fw, QComboBox) and fw.isEditable()):
                    return False                    # typing in a field: keys are letters
                text = ev.text()
                if not text:
                    return False
                if t == QEvent.KeyPress:
                    done = CK.key_press(text, ev.isAutoRepeat())
                    if done and text.lower() in ("z", "x", "c", "v") and not ev.isAutoRepeat():
                        msg = (f"Computer keyboard: {CK.range_text()}" if text.lower() in "zx"
                               else f"Computer keyboard: velocity {CK.velocity}")
                        try:
                            app.win.statusBar().showMessage(msg, 3000)
                        except Exception:
                            pass
                    return done
                return CK.key_release(text, ev.isAutoRepeat())
            except Exception:
                return False
    return KeyFilter()


# folder of the file dialogs by object type / file extension
TYPE_FOLDER = {"Pdf": "pdf", "Score": "scores", "ExerciseSet": "exercises", "Phrase": "exercises",
               "Task": "exercises", "Routine": "exercises", "TaskGroup": "exercises", "PlayOver": "exercises", "Notes": "midi", "Midi": "midi"}


REPEAT_COLOR = "#2e7d32"


TYPE_STYLE = (            # (class name, symbol, colour) — first match wins (subclasses first)
    ("PlayOver", "♬", "#00695c"),
    ("TaskGroup", "▦", "#6a1b9a"),
    ("Routine", "↻", "#283593"),
    ("Task", "◆", "#7b1fa2"),
    ("ExerciseSet", "▦", "#e65100"),
    ("Phrase", "♩", "#ef6c00"),
    ("Notes", "≈", "#546e7a"),
    ("Midi", "♪", "#1565c0"),
    ("Score", "♫", "#00838f"),
    ("Pdf", "▤", "#c62828"),
)
_ICONS = {}


def _is_temporary(path):
    """A file in the system temporary folder (e.g. a PDF just made with the fingerings):
    Save asks where to put it."""
    import tempfile
    try:
        return os.path.commonpath([os.path.realpath(path),
                                   os.path.realpath(tempfile.gettempdir())]) == \
            os.path.realpath(tempfile.gettempdir())
    except (ValueError, TypeError):
        return False


def _type_of(obj):
    names = {c.__name__ for c in type(obj).__mro__}
    for cls, sym, col in TYPE_STYLE:
        if cls in names:
            return cls, sym, col
    return type(obj).__name__, "•", "#424242"


def _icon(sym, col):
    """Small coloured square with the symbol of the object type."""
    if (sym, col) in _ICONS:
        return _ICONS[(sym, col)]
    from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon, QFont
    from PySide6.QtCore import Qt, QRectF
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(col))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(1, 1, 30, 30), 7, 7)
    f = QFont()
    f.setPixelSize(22)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, 32, 32), Qt.AlignCenter, sym)
    p.end()
    _ICONS[(sym, col)] = QIcon(pm)
    return _ICONS[(sym, col)]


# COLOURS OF THE EXERCISES (owner, 2026-11-19): every exercise kind has its own hue (some
# may be similar; the same hues as the practice diary, `diaryview.KIND_COLORS`); TO DO = a
# DARK shade of it on the light grey background, done = a LIGHT shade of it on the dark
# background of the app (on a light background the dark shade). No instrument is above
# another: exercises of every instrument are drawn the same way (no fading).
TODO_BACKGROUND = "#e6e6e6"
ROUTINE_HUE = "#5c6bc0"
PLAYOVER_HUE = "#00897b"
# the grade after the name (owner, 2026-11-19: dark blue on black could not be read):
# light sky blue on the dark background, dark blue on the light grey of the to-do items
GRADE_LIGHT = "#8fd8ff"
GRADE_DARK = "#0d47a1"
GRADE_ROLE = 0x0100 + 41            # Qt.UserRole + 41: where the grade starts in the text


def _exercise_hue(obj):
    """Base colour of an exercise object: by its kind (Read & play, Listen & repeat,
    intervals, lip slurs…); a group its first exercise; a routine / Play over MIDI their
    own."""
    from .diaryview import KIND_COLORS
    cls = type(obj).__name__
    if cls == "PlayOver":
        return PLAYOVER_HUE
    if cls == "TaskGroup":
        ph = list(getattr(obj, "phrases", None) or [])
        return _exercise_hue(ph[0]) if ph else ROUTINE_HUE
    if cls == "Routine":
        return ROUTINE_HUE
    if cls in ("Phrase", "ExerciseSet"):
        kind = "listen_repeat" if getattr(obj, "purpose", "") == "repeat" else "play_reading"
        return KIND_COLORS.get(kind, "#ef6c00")
    return KIND_COLORS.get(getattr(obj, "kind", ""), "#7b1fa2")


def _shade(col, dark):
    """The hue `col` made dark (lightness 0.27) or light (0.76), saturation kept."""
    from PySide6.QtGui import QColor
    c = QColor(col)
    h, s, _l, _a = c.getHslF()
    return QColor.fromHslF(max(0.0, h), min(1.0, max(s, 0.45)), 0.27 if dark else 0.76)


def _dark_base(widget):
    """The list is drawn on a dark background (the app's dark look)."""
    from PySide6.QtGui import QPalette
    try:
        return widget.palette().color(QPalette.Base).lightnessF() < 0.5
    except Exception:
        return True


def _grade_delegate_class():
    """Exercises list: the grade after the name in its own colour (GRADE_ROLE = where it
    starts in the text); the rest drawn as usual."""
    from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle, QApplication
    from PySide6.QtGui import QColor, QFontMetrics, QPalette, QBrush
    from PySide6.QtCore import Qt

    class GradeDelegate(QStyledItemDelegate):
        def paint(self, p, option, index):
            pos = index.data(GRADE_ROLE)
            if pos is None:
                return super().paint(p, option, index)
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            text = opt.text
            pos = max(0, min(int(pos), len(text)))
            name, grade = text[:pos], text[pos:]
            opt.text = ""
            w = opt.widget
            style = w.style() if w is not None else QApplication.style()
            style.drawControl(QStyle.CE_ItemViewItem, opt, p, w)
            r = style.subElementRect(QStyle.SE_ItemViewItemText, opt, w)
            selected = bool(opt.state & QStyle.State_Selected)
            fg = index.data(Qt.ForegroundRole)
            if selected:
                col = opt.palette.color(QPalette.HighlightedText)
                gcol = col
            else:
                col = fg.color() if isinstance(fg, QBrush) else (
                    QColor(fg) if fg is not None else opt.palette.color(QPalette.Text))
                bg = index.data(Qt.BackgroundRole)
                if isinstance(bg, QBrush) and bg.style() != Qt.NoBrush:
                    light_bg = bg.color().lightnessF() >= 0.5        # to do: light grey
                else:
                    light_bg = w is not None and not _dark_base(w)  # the list's own
                gcol = QColor(GRADE_DARK if light_bg else GRADE_LIGHT)
            p.save()
            p.setFont(opt.font)
            fm = QFontMetrics(opt.font)
            gw = fm.horizontalAdvance(grade)
            shown = fm.elidedText(name, Qt.ElideRight, max(0, r.width() - gw))
            p.setPen(col)
            p.drawText(r, Qt.AlignVCenter | Qt.AlignLeft, shown)
            r2 = r.adjusted(fm.horizontalAdvance(shown), 0, 0, 0)
            p.setPen(gcol)
            p.drawText(r2, Qt.AlignVCenter | Qt.AlignLeft, grade)
            p.restore()

    return GradeDelegate


def _style(item, obj):
    from PySide6.QtGui import QColor
    cls, sym, col = _type_of(obj)
    if cls in ("Phrase", "ExerciseSet") and getattr(obj, "purpose", "") == "repeat":
        col = REPEAT_COLOR                         # Listen & repeat exercises: green
    item.setIcon(0, _icon(sym, col))
    item.setForeground(0, QColor(col))
    item.setToolTip(0, f"{item.text(0)}\n{cls}")


def _is_set(obj):
    """An expandable group: phrases ▦ (ExerciseSet) or exercises ◆ (tasks.TaskGroup)."""
    return type(obj).__name__ in ("ExerciseSet", "TaskGroup")


def _short(ph, st):
    """Label of a phrase inside its group (without the source name)."""
    t = ph.title
    if st.source and t.startswith(st.source + " – "):
        t = t[len(st.source) + 3:]
    return t


def user_dialog(parent=None, forced=False):
    """NEW USER (owner, 2026-11-18): a name different from every other user (letters, digits,
    spaces) and the INSTRUMENTS PLAYED (the piano is for everybody); RECOVER USER (owner,
    2026-11-20): one deleted user chosen from the list, back with his data. forced (no user
    at all: first start, the last one deleted): "Cancel and exit". Returns ('new', name,
    instruments), ('recover', name, None) or None."""
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
                                   QCheckBox, QPushButton, QGroupBox, QGridLayout, QComboBox)
    from .. import instruments as ins
    from ..progress import same_user, valid_user_name, deleted_users
    d = QDialog(parent)
    d.setWindowTitle("First user" if forced else "New user")
    lay = QVBoxLayout(d)
    if forced:
        t = QLabel("MusiKitE needs a user: create one (or recover a deleted one).")
        t.setWordWrap(True)
        lay.addWidget(t)
    lay.addWidget(QLabel("Name (letters, digits and spaces):"))
    name = QLineEdit()
    lay.addWidget(name)
    box = QGroupBox("Instruments played (the piano is for everybody)")
    g = QGridLayout(box)
    checks = {}
    keys = [k for k in ins.KEYS if k != ins.PIANO]
    for i, k in enumerate(keys):
        c = QCheckBox(ins.label(k))
        checks[k] = c
        g.addWidget(c, i // 3, i % 3)              # three columns: many instruments
    pc = QCheckBox(ins.label(ins.PIANO))
    pc.setChecked(True)
    pc.setEnabled(False)
    g.addWidget(pc, (len(keys) + 2) // 3, 0)
    lay.addWidget(box)
    gone = deleted_users()
    rec = None
    if gone:
        rbox = QGroupBox("Recover user (a deleted user, with his data)")
        rl = QHBoxLayout(rbox)
        rec = QComboBox()
        rec.addItems(gone)
        rl.addWidget(rec, 1)
        rb = QPushButton("Recover")
        rb.setAutoDefault(False)
        rl.addWidget(rb)
        lay.addWidget(rbox)
    msg = QLabel("")
    msg.setStyleSheet("color: red")
    msg.setWordWrap(True)
    lay.addWidget(msg)
    row = QHBoxLayout()
    row.addStretch()
    cancel = QPushButton("Cancel and exit" if forced else "Cancel")
    cancel.setAutoDefault(False)
    create = QPushButton("Create")
    create.setDefault(True)
    row.addWidget(cancel)
    row.addWidget(create)
    lay.addLayout(row)
    answer = {}

    def ok():
        n = name.text().strip()
        why = valid_user_name(n)                  # letters, digits, spaces only
        if why:
            msg.setText(why)
            return
        other = same_user(n)
        if other is not None:
            msg.setText(f"a user named '{other}' already exists: choose another name")
            return
        answer["r"] = ("new", n, [k for k, c in checks.items() if c.isChecked()])
        d.accept()

    def recover():
        n = rec.currentText()
        other = same_user(n)
        if other is not None:
            msg.setText(f"a user named '{other}' already exists")
            return
        answer["r"] = ("recover", n, None)
        d.accept()

    create.clicked.connect(ok)
    cancel.clicked.connect(d.reject)
    if rec is not None:
        rb.clicked.connect(recover)
    if d.exec() != QDialog.Accepted:
        return None
    return answer.get("r")


class App:
    def __init__(self):
        from PySide6.QtWidgets import (QMainWindow, QTabWidget, QDockWidget, QTreeWidget,
                                       QPlainTextEdit, QToolBar, QLabel, QComboBox,
                                       QPushButton, QAbstractItemView)
        from PySide6.QtCore import Qt
        from ..midi import Midi
        _app()
        from . import intervals, interval_reading, chords, ear_more, library_ui, flashcards, play_reading, freeplayer, tools_basic, drills_ui, diaryview  # noqa: F401  (register the tools)
        self.progress = Progress()
        self.objects = {}                      # name -> object
        self._attempt_listeners = []           # fn(obj) after an attempt (routine runner)
        self.tool_widgets = {}                 # tool name -> widget
        self.views = {}                        # tab widget -> StaffView (to stop it on close)
        # A USER IS ALWAYS THERE (owner, 2026-11-20): at the first start (no users) the first
        # user must be created (or a deleted one recovered); "Cancel and exit" closes the app
        if not _users():
            r = user_dialog(None, forced=True)
            if r is None:
                raise SystemExit(0)
            set_current_user(self._make_user(r))   # it becomes the last user
        start_user = last_user() if last_user() in _users() else _users()[0]
        set_current_user(start_user)           # settings, results, workspace of this user
        self._apply_user_settings()

        w = self.win = QMainWindow()
        w.setWindowTitle(APP_NAME)
        self._key_filter = _key_filter(self)          # the computer keyboard as a keyboard
        from PySide6.QtWidgets import QApplication as _QApp
        _QApp.instance().installEventFilter(self._key_filter)
        self._close_filter = _CloseFilter(self._on_close)
        w.installEventFilter(self._close_filter)
        w.resize(1100, 750)
        # central area: tabs (MIDI, PDF, exercises… open together); every tab has its
        # buttons on top, under the tab bar (gui/bar.py)
        from .bar import tabs_class
        self.tabs = tabs_class()()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.on_close_all = self.close_all          # last tab "Close all" (2+ tabs)
        w.setCentralWidget(self.tabs)
        # PREVIEW (owner, 2026-11-20): one click on an object shows it in ONE tab "Preview"
        # (never more than one), which disappears when another tab comes in front
        from PySide6.QtCore import QTimer as _QTimer
        from PySide6.QtWidgets import QApplication as _QA
        self._preview = None                   # the Preview tab (widget) or None
        self._preview_name = None              # object waiting to be previewed
        self._preview_quiet = False            # selection changed by code: no preview
        self._preview_switching = False        # the preview itself is being shown
        self._preview_block = 0.0              # no preview until (after a double click)
        self._preview_blank = False            # the Preview shows the empty page only
        self._new_preview = None               # (name, tab in front) of a NEW object to show
        self._new_preview_pending = False
        self._hold_new_preview = False         # run_tool: show only the last one, at the end
        self._preview_timer = _QTimer(w)
        self._preview_timer.setSingleShot(True)
        # waits for a possible second click (double click = open, not preview)
        self._preview_timer.setInterval(_QA.doubleClickInterval() + 20)
        self._preview_timer.timeout.connect(self._preview_now)
        self.tabs.currentChanged.connect(self._tab_changed)

        from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QSplitter, QLabel as _QL
        # Objects = TWO lists one above the other (owner, 2026-11-07): Material (MIDI, PDF,
        # scores, recordings) and Exercises (every exercise object, routines); own scrolling,
        # the divider can be moved (its position is saved)
        self.mat_list, self.ex_list = QTreeWidget(), QTreeWidget()
        self.split = QSplitter(Qt.Vertical)
        for title, lst in (("Material", self.mat_list), ("Exercises", self.ex_list)):
            lst.setHeaderHidden(True)
            lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
            # ONE CLICK = PREVIEW, DOUBLE CLICK = open / do it (owner, 2026-11-20)
            lst.itemDoubleClicked.connect(lambda it, col: self._double_clicked(it))
            lst.itemClicked.connect(lambda it, col: self._clicked(it))
            lst.currentItemChanged.connect(self._current_changed)
            lst.itemSelectionChanged.connect(lambda lst=lst: self._selection_in(lst))
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(lambda pos, lst=lst: self._object_menu(pos, lst))
            pane = QWidget()
            pane.setMinimumHeight(60)                 # a list never shrinks to nothing
            pl = QVBoxLayout(pane)
            pl.setContentsMargins(0, 0, 0, 0)
            pl.setSpacing(1)
            lab = _QL(f"<b>{title}</b>")
            pl.addWidget(lab)
            pl.addWidget(lst)
            self.split.addWidget(pane)
        self.split.setChildrenCollapsible(False)   # neither list can disappear (owner, 2026-11-08)
        # DRAG an exercise into an open routine (owner, 2026-11-08): the Exercises list only
        # GIVES its selection (DragOnly: never reordered by a drag); the runner takes it
        self._grade_delegate = _grade_delegate_class()(self.ex_list)
        self.ex_list.setItemDelegate(self._grade_delegate)
        self.ex_list.setDragEnabled(True)
        self.ex_list.setDragDropMode(QAbstractItemView.DragOnly)
        self.ex_list.setDefaultDropAction(Qt.CopyAction)
        # it TAKES only the exercises dragged from Practice > Exercise from library (owner,
        # 2026-11-19): the viewport accepts drops, the filter keeps only the library's
        from .library_ui import drop_filter
        self._library_drop = drop_filter(self)
        self.ex_list.viewport().setAcceptDrops(True)
        self.ex_list.viewport().installEventFilter(self._library_drop)
        # the Material list GIVES its selection too (owner, 2026-11-17): a MIDI / PDF / score
        # dragged into an empty Play over MIDI tab
        self.mat_list.setDragEnabled(True)
        self.mat_list.setDragDropMode(QAbstractItemView.DragOnly)
        self.mat_list.setDefaultDropAction(Qt.CopyAction)
        self._active_list = self.mat_list
        self._restore_split()
        self.split.splitterMoved.connect(lambda *_: self._save_split())
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(2, 2, 2, 2)
        bl.addWidget(self.split, 1)
        grid = QGridLayout()
        self.obj_buttons = {}
        for i, (text, tip, fn) in enumerate((
                ("View", "show it in the main window", lambda: self.view_object()),
                ("Play", "listen to it (press again to stop)", self.toggle_play),
                ("Save", "save it in its file (first time: choose the file); several "
                         "selected: each one, the new ones in a folder chosen once",
                 lambda: self.save_selected(quick=True)),
                ("Save as…", "save it in a new file; several selected: all in a folder",
                 lambda: self.save_selected(quick=False)))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            self.obj_buttons[text] = b
            grid.addWidget(b, i // 2, i % 2)
        self._play_timer = None
        bl.addLayout(grid)
        self.dock_objects = QDockWidget("Objects")
        self.dock_objects.setWidget(box)
        w.addDockWidget(Qt.LeftDockWidgetArea, self.dock_objects)

        self.dock_tool = QDockWidget("Tools")
        w.addDockWidget(Qt.RightDockWidgetArea, self.dock_tool)
        self.dock_tool.hide()
        self.tool_panel = None
        self._side_owner = None                # tab whose panel is in the dock (Edit…)
        self._side_on_close = None

        self.logbox = QPlainTextEdit()
        self._install_excepthook()
        self.logbox.setReadOnly(True)
        self.dock_log = QDockWidget("Log")
        self.dock_log.setWidget(self.logbox)
        w.addDockWidget(Qt.BottomDockWidgetArea, self.dock_log)

        tb = QToolBar("User")
        w.addToolBar(tb)
        tb.addWidget(QLabel(" User: "))
        self.user_box = QComboBox()
        self.user_box.setMinimumWidth(160)
        self.user_box.currentTextChanged.connect(self._user_changed)
        tb.addWidget(self.user_box)
        b = QPushButton("New user…")
        b.clicked.connect(self.new_user_dialog)
        tb.addWidget(b)
        # INSTRUMENT beside the user (owner, 2026-11-18): the instrument studied now;
        # exercises are proposed / generated for it (no Instrument field in the exercises)
        tb.addWidget(QLabel("  Instrument: "))
        self.instr_box = QComboBox()
        self.instr_box.setMinimumWidth(150)
        self.instr_box.setToolTip("the instrument you are studying now: exercises are made for "
                                  "it; the instruments played: Settings > Instruments")
        self.instr_box.currentIndexChanged.connect(self._instrument_chosen)
        tb.addWidget(self.instr_box)
        self._fill_users(start_user)
        self._user_prev = self.user_box.currentText() or None
        self._fill_instruments()

        self._build_menus()
        self._update_tool_actions()
        w.resizeDocks([self.dock_log], [110], Qt.Vertical)
        # the Log is hidden at start (owner, 2026-11-17): View > Log shows it; everything is
        # still written to ~/.musikite/log.txt
        self.dock_log.hide()
        w.resizeDocks([self.dock_objects], [180], Qt.Horizontal)
        self._update_title()
        from ..progress import FOLDERS
        for k in FOLDERS:                          # ~/musikite/<kind> (or the user's choice)
            folder(k)
        self.load_user_workspace()
        from PySide6.QtCore import QTimer
        from ..diary import day_of
        self._today = day_of()
        self._day_timer = QTimer(self.win)         # new day at 04:00: all to do again
        self._day_timer.setInterval(60000)
        self._day_timer.timeout.connect(self._day_watch)
        self._day_timer.start()
        self._lock_user(self.user)
        self.log(f"{APP_NAME} ready. User: {self.user or 'none'}. Soundfont: "
                 + (Midi._default_sf2 or "none (Settings > Soundfont…)"))
        for m in getattr(self, "_early_log", []):
            self.log(m)
        self._early_log = []
        from ..check import report, text
        r = report()
        if r["errors"] or r["warnings"]:
            self.log(text(r))

    # ---------------------------------------------------------- menus
    def _build_menus(self):
        from PySide6.QtGui import QAction
        mb = self.win.menuBar()

        def add(menu, text, fn, shortcut=None):
            a = QAction(text, self.win)
            a.setMenuRole(QAction.NoRole)      # macOS: keep "Settings…" where it is
            a.triggered.connect(fn)
            if shortcut:
                a.setShortcut(shortcut)
            menu.addAction(a)
            return a

        m = mb.addMenu("&File")
        add(m, "Open…", lambda: self.open_file(), "Ctrl+O")
        add(m, "Save object as…", lambda: self.save_object(), "Ctrl+S")
        add(m, "Print…", lambda: self.print_object(), "Ctrl+P")
        m.addSeparator()
        add(m, "New workspace", self.new_workspace)
        add(m, "Open workspace…", lambda: self.open_workspace())
        add(m, "Save workspace as…", lambda: self.save_workspace_as())
        m.addSeparator()
        add(m, "Close tab", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W")
        m.addSeparator()
        add(m, "Quit", self.win.close, "Ctrl+Q")

        m = mb.addMenu("&Edit")
        add(m, "Rename object…", self.rename_object_dialog)
        add(m, "Remove object", self.remove_selected_object)

        m = mb.addMenu("&View")
        add(m, "View object", lambda: self.view_object())
        add(m, "Play object", lambda: self.play_object())
        add(m, "Stop sound", self.stop_sound, "Esc")
        self._loop_action = add(m, "Loop playback", lambda on=False: self.set_play_loop(on))
        self._loop_action.setCheckable(True)
        self._loop_action.setChecked(self.play_loop())
        m.addSeparator()
        m.addAction(self.dock_objects.toggleViewAction())
        m.addAction(self.dock_tool.toggleViewAction())
        m.addAction(self.dock_log.toggleViewAction())

        self._tool_actions = getattr(self, "_tool_actions", {})
        self._tool_action_list = getattr(self, "_tool_action_list", [])
        for cat in registry.CATEGORIES:
            tools = registry.by_category(cat)
            m = mb.addMenu(cat)
            if not tools:
                a = m.addAction("(no tools yet)")
                a.setEnabled(False)
            # FAMILY SUBMENUS (owner, 2026-11-24): Practice and Generate are split into
            # "All instruments", "Brass", "Woodwinds", "Piano" (empty ones not shown)
            fam = {}
            if cat in registry.FAMILY_CATEGORIES:
                for f in registry.FAMILY_MENUS:
                    if any(f in registry.families_of(t) for t in tools):
                        fam[f] = m.addMenu(f)
            subs = {}
            for t in tools:
                parents = ([fam[f] for f in registry.families_of(t) if f in fam]
                           if fam else [m])
                for parent in parents:
                    target = parent
                    if t.submenu:
                        key = (id(parent), t.submenu)
                        if key not in subs:
                            subs[key] = parent.addMenu(t.submenu)
                        target = subs[key]
                    a = add(target, t.label + (" (to do)" if t.kind == "planned" else ""),
                            lambda checked=False, n=t.name: self.open_tool(n))
                    self._tool_actions.setdefault(t.name, a)
                    self._tool_action_list.append((t.name, a))

        m = mb.addMenu("&Settings")             # one window with every setting (VLC style)
        add(m, "Settings…", lambda: self.settings(), "Ctrl+,")

        m = mb.addMenu("&Help")
        add(m, "Manual", lambda: self.open_manual(), "F1")
        add(m, "About", lambda: self.message(APP_NAME,
                                            "Container of music tools.\nTools: " +
                                            ", ".join(t.label for t in registry.TOOLS.values())))

    # ---------------------------------------------------------- users
    def _fill_users(self, select=None):
        self.user_box.blockSignals(True)
        self.user_box.clear()
        self.user_box.addItems(self.progress.users())
        if select and select in self.progress.users():
            self.user_box.setCurrentText(select)
        self.user_box.blockSignals(False)

    def _user_changed(self, name):
        """Another user = another installation: the workspace of the previous user is
        saved, then settings, results and the last workspace of the new one are loaded."""
        prev = getattr(self, "_user_prev", None)
        if not name or name == prev:
            return
        for w in list(self.tool_widgets.values()):
            if hasattr(w, "user_changed"):
                w.user_changed(name)
        self.save_user_workspace()                 # still under the previous user
        self.clear_workspace()
        from ..progress import unlock_user
        unlock_user(prev)
        set_current_user(name)                     # the instrument: the user's preferred one
        self._user_prev = name
        self._apply_user_settings()
        self._fill_instruments()
        if getattr(self, "_loop_action", None) is not None:
            self._loop_action.setChecked(self.play_loop())
        self._update_title()
        self.log(f"user: {name}")
        self._lock_user(name)
        self.load_user_workspace()
        self._instrument_changed()

    # ---------------------------------------------------------- instrument
    def _fill_instruments(self):
        """The instruments played by the current user; the current one selected."""
        from .. import instruments as ins
        box = getattr(self, "instr_box", None)
        if box is None:
            return
        mine = ins.user_instruments()
        if ins.current() not in mine:              # removed in Settings: the preferred one
            ins.set_current(None)
        ins.set_current(ins.current())             # fixed for the session (no disk reads)
        box.blockSignals(True)
        box.clear()
        for k in mine:
            box.addItem(ins.label(k), k)
        box.setCurrentIndex(max(0, box.findData(ins.current())))
        box.blockSignals(False)

    def _instrument_chosen(self, *_):
        k = self.instr_box.currentData()
        if k:
            self.set_instrument(k)

    @property
    def instrument(self):
        """Key of the instrument studied now ('Bb (trumpet)', 'C (piano)'…)."""
        from .. import instruments as ins
        return ins.current()

    def set_instrument(self, key):
        """Choose the instrument studied now (one of the user's instruments)."""
        from .. import instruments as ins
        if key not in ins.user_instruments():
            raise ValueError(f"{key} is not among the instruments of {self.user or 'this user'}")
        ins.set_current(key)
        i = self.instr_box.findData(key)
        if i >= 0 and self.instr_box.currentIndex() != i:
            self.instr_box.blockSignals(True)
            self.instr_box.setCurrentIndex(i)
            self.instr_box.blockSignals(False)
        self.log(f"instrument: {ins.label(key)}")
        self._instrument_changed()
        return key

    def _instrument_changed(self):
        """Menus, exercises in Objects, title and the open Practice tabs follow the instrument."""
        from .. import instruments as ins
        key = ins.current()
        self._update_tool_actions()
        self.refresh_exercises()
        self._update_title()
        for w in list(self.tool_widgets.values()):
            if hasattr(w, "instrument_changed"):
                try:
                    w.instrument_changed(key)
                except Exception as e:
                    self.log(f"instrument change: {type(e).__name__}: {e}")

    def _update_tool_actions(self):
        """Menu items of the tools that do not fit the instrument are disabled (lip slurs:
        valve brass only; long tones: wind instruments only)."""
        from .. import instruments as ins
        key = ins.current()
        for name, a in getattr(self, "_tool_action_list", []):
            t = registry.TOOLS.get(name)
            if t is not None:
                ok = registry.is_available(t, key)
                a.setEnabled(ok)
                a.setToolTip("" if ok else f"not for {ins.label(key)}")

    # ---------------------------------------------------------- open on another computer
    def _lock_user(self, name):
        """The user is marked open on this computer; if it is open on another one (the same
        data folder in Dropbox) the user is warned: the two would overwrite each other."""
        from ..progress import lock_user, user_open_elsewhere
        if not name:
            return
        other = user_open_elsewhere(name)
        lock_user(name)
        if other:
            self.log(f"WARNING: the user {name} is also open on {other}")
            try:
                self.message("User open on another computer",
                             f"The user {name} is open on {other} too.\nClose it there: "
                             "the two computers would overwrite each other's results and "
                             "workspace.")
            except Exception:
                pass

    def _on_close(self):
        from ..progress import unlock_user
        if getattr(self, "_no_save", False):     # "Cancel and exit" without a user
            return
        self.save_user_workspace()
        unlock_user(self.user)

    def change_data_folder(self, path):
        """Settings > Folders > Data folder: users, settings, results, diary, workspaces
        from now on in `path` (copied there if it has none; used as it is if the other
        computer already put them there); the users are loaded again from it."""
        from ..progress import set_data_home, unlock_user, last_user, users as _u
        self.save_user_workspace()
        unlock_user(self.user)
        msg = set_data_home(path)
        self.log(msg)
        if not _u():                               # a data folder without users: one is needed
            r = user_dialog(self.win, forced=True)
            if r is None:
                self._no_save = True
                from PySide6.QtWidgets import QApplication
                self.win.close()
                QApplication.instance().quit()
                return msg
            set_current_user(self._make_user(r))
        start = last_user() if last_user() in _u() else _u()[0]
        self._user_prev = None
        self.clear_workspace(log=False)
        set_current_user(start)
        self._fill_users(start)
        self._user_prev = self.user_box.currentText() or None
        if self._user_prev != start:
            set_current_user(self._user_prev)
        self._apply_user_settings()
        self._fill_instruments()
        self._update_title()
        self._lock_user(self.user)
        self.load_user_workspace()
        self._instrument_changed()
        return msg

    def _apply_user_settings(self):
        """Settings that live outside the dialogs: soundfont, running synths."""
        from ..midi import Midi
        from .. import realtime
        from ..progress import local
        sf2 = local(settings().get("sf2"))
        if not (sf2 and os.path.isfile(sf2)):
            # the soundfont of the package (GeneralUser GS, in the app too), if any
            sf2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", DEFAULT_SF2)
        Midi._default_sf2 = sf2 if sf2 and os.path.isfile(sf2) else None
        try:                                       # practice diary: old results once, freeze days
            from ..diary import get
            from ..progress import current_user
            u = current_user()
            n = get(u).import_progress(self.progress.exercises(u) if u else [])
            msg = f"practice diary: {n} old results imported" if n else None
        except Exception as e:
            msg = f"practice diary: {type(e).__name__}: {e}"
        if msg:
            if getattr(self, "logbox", None) is not None:
                self.log(msg)
            else:
                self._early_log = getattr(self, "_early_log", []) + [msg]
        try:
            realtime.close_players()               # the next sound uses this user's audio settings
        except Exception:
            pass

    def _update_title(self):
        from .. import instruments as ins
        t = f"{APP_NAME} – {self.user}" if self.user else APP_NAME
        try:
            t += f" – {ins.label(ins.current())}"
        except Exception:
            pass
        self.win.setWindowTitle(t)

    # ---------------------------------------------------------- workspace
    def save_user_workspace(self):
        """Automatic save of the current user's workspace (exit, user change)."""
        from ..workspace import save_workspace
        try:
            skipped = save_workspace(workspace_path(), self.objects, current_user())
            if skipped:
                self.log(f"workspace: not saved (type not supported): {', '.join(skipped)}")
        except Exception as e:
            self.log(f"workspace not saved: {type(e).__name__}: {e}")

    def load_user_workspace(self):
        """Load the last workspace of the current user (automatic at start)."""
        path = workspace_path()
        if os.path.isfile(path):
            self._load_workspace_file(path, replace=True)

    def _load_workspace_file(self, path, replace=True):
        from ..workspace import load_workspace
        try:
            objs, warn = load_workspace(path)
        except Exception as e:
            self.log(f"workspace {path}: {type(e).__name__}: {e}")
            return None
        if replace:
            self.clear_workspace(log=False)
        for name, obj in objs:
            self.add_object(obj, name, log=False)
        for w in warn:
            self.log(f"workspace: {w}")
        self.log(f"workspace loaded: {len(objs)} objects ({path})")
        return [n for n, _ in objs]

    def new_workspace(self):
        """Empty workspace (the current one is not saved: use Save workspace as… first)."""
        self.clear_workspace()
        return self

    def open_workspace(self, path=None):
        from PySide6.QtWidgets import QFileDialog
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self.win, "Open workspace", folder("workspaces"),
                                                  "MusiKitE workspace (*.json)")
            if not path:
                return None
        return self._load_workspace_file(path, replace=True)

    def save_workspace_as(self, path=None):
        from PySide6.QtWidgets import QFileDialog
        from ..workspace import save_workspace
        if path is None:
            start = os.path.join(folder("workspaces"), self._prefixed("workspace") + ".json")
            path, _ = QFileDialog.getSaveFileName(self.win, "Save workspace", start,
                                                  "MusiKitE workspace (*.json)")
            if not path:
                return None
        if not path.lower().endswith(".json"):
            path += ".json"
        skipped = save_workspace(path, self.objects, current_user())
        if skipped:
            self.log(f"workspace: not saved (type not supported): {', '.join(skipped)}")
        self.log(f"workspace saved: {path}")
        return path

    def _prefixed(self, name):
        """File name proposed for a user's own file: 'User – name'."""
        name = name.replace(os.sep, "_")
        return f"{self.user} – {name}" if self.user else name

    @property
    def user(self):
        return self.user_box.currentText() or None

    def set_user(self, name):
        """Select a user (created if new)."""
        self.progress.add_user(name)
        self._fill_users(name)
        self._user_changed(name)
        return self

    def new_user_dialog(self):
        """New user… (toolbar): a new user, or a deleted one recovered (owner, 2026-11-20)."""
        r = user_dialog(self.win)
        if r is None:
            return None
        return self._apply_user_choice(r)

    def _make_user(self, r):
        """Create (or recover) the user of a user_dialog answer, without selecting it."""
        from .. import instruments as ins
        kind, name, instruments = r
        if kind == "recover":
            self.progress.recover_user(name)
        else:
            self.progress.add_user(name)
            ins.set_user_instruments(list(instruments or ()), user=name)
        return name

    def _apply_user_choice(self, r):
        name = self._make_user(r)
        self._fill_users(name)
        self.set_user(name)
        self.log(("user recovered: " if r[0] == "recover" else "new user: ") + name)
        return name

    def _require_user(self):
        """No user left (the last one deleted, a data folder without users): a user must be
        created or recovered; "Cancel and exit" closes the app (owner, 2026-11-20)."""
        r = user_dialog(self.win, forced=True)
        if r is None:
            self._no_save = True                  # nobody to save the workspace for
            from PySide6.QtWidgets import QApplication
            self.win.close()
            QApplication.instance().quit()
            return None
        return self._apply_user_choice(r)

    def delete_user(self, name):
        """Settings > Users > Delete user (owner, 2026-11-20): the user leaves the list, his
        folder (settings, results, diary, workspace) STAYS: New user… > Recover user gives
        him back. The current user deleted: another one is opened; the last one: a new user
        must be created (or the app closes)."""
        from ..progress import users as _u
        if name not in _u():
            return None
        current = name == self.user
        self.progress.remove_user(name)
        self.log(f"user deleted: {name} (its data are kept: New user… > Recover user)")
        left = _u()
        if not current:
            self._fill_users(self.user)
            return self.user
        if left:
            self.set_user(left[0])                # the deleted user's workspace saved first
            return left[0]
        self._fill_users(None)
        return self._require_user()

    def new_user(self, name, instruments=()):
        """Create a user with the instruments played (+ the piano) and select it."""
        from .. import instruments as ins
        from ..progress import same_user
        if same_user(name) is not None:
            raise ValueError(f"a user named '{same_user(name)}' already exists")
        self.progress.add_user(name)
        ins.set_user_instruments(list(instruments), user=name)
        self.set_user(name)
        return name

    # ---------------------------------------------------------- tools and tabs
    def open_tool(self, name):
        """Open a session tool in a tab (or bring it to front); returns its widget."""
        t = registry.TOOLS[name]
        if t.kind == "planned":                      # menu item of a tool still to write
            self.log(f"{t.label}: not there yet (planned: {t.help})")
            return None
        if t.kind == "transform":
            from .toolpanel import tool_panel
            self.close_side_panel()
            self.tool_panel = tool_panel(self, t)
            self.dock_tool.setWidget(self.tool_panel)
            self.dock_tool.show()
            return self.tool_panel
        # THE TOOLS PANEL DISAPPEARS WHEN NO LONGER NEEDED (owner, 2026-11-13: the practice
        # diary opened with the "Transpose" panel still there): every tool that opens in a
        # tab (Practice, Analyse, …) closes it; it opens again with the next Generate /
        # Convert tool chosen
        self.close_side_panel()
        self.dock_tool.hide()
        if t.opener is not None:                     # the tool decides which tab (Play over)
            return t.opener(self)
        w = self.tool_widgets.get(name)
        if w is None or self.tabs.indexOf(w) < 0:
            w = t.factory(self)
            self.tool_widgets[name] = w
            self.tabs.addTab(w, t.label.replace("&", "&&"))     # '&' is not a shortcut
        self.tabs.setCurrentWidget(w)
        return w

    def _show_bar(self, *_):
        self.tabs._show_bar()

    def open_manual(self, page=None):
        """Help > Manual (F1): the pages of docs/ in a tab (gui/manual.py); page =
        'drills.md' or 'settings.md#audio'."""
        w = self.tool_widgets.get("manual")
        if w is None or self.tabs.indexOf(w) < 0:
            from .manual import manual_widget
            w = manual_widget(self, page)
            self.tool_widgets["manual"] = w
            self.add_tab(w, "Manual")
        else:
            if page:
                w.open(page)
            self.tabs.setCurrentWidget(w)
        return w

    def add_tab(self, widget, title):
        self.close_side_panel()
        self.dock_tool.hide()                    # a new tab: the Tools panel is no longer needed
        self.tabs.addTab(widget, title.replace("&", "&&"))
        self.tabs.setCurrentWidget(widget)
        return widget

    def close_tab(self, i):
        if i < 0:
            return
        w = self.tabs.widget(i)
        if hasattr(w, "closing"):
            w.closing()
        self.close_side_panel(w)                  # its panel on the right goes with it
        sv = self.views.pop(w, None)
        if sv is not None:
            sv.stop()
        self.tabs.removeTab(i)
        if w is self._preview:
            self._preview = None
            w.deleteLater()
        for k, v in list(self.tool_widgets.items()):
            if v is w:
                del self.tool_widgets[k]

    def close_all(self):
        """Tab "Close all": every tab closed (as with its own close button); objects stay."""
        n = self.tabs.count()
        self.stop_sound()
        while self.tabs.count():
            self.close_tab(self.tabs.count() - 1)
        self.log(f"closed all tabs ({n})")
        return self

    # ---------------------------------------------------------- objects
    def add_object(self, obj, name=None, log=True, select=None, preview=None):
        """Add an object to Objects. A NEW OBJECT IS SELECTED (owner, 2026-11-20: "the
        default for every creation"): select None = as `log` (objects loaded with a
        workspace are not selected one by one). A NEW OBJECT GOES IN THE PREVIEW (owner,
        2026-11-20: "by any method, otherwise one does not see it was made"): preview None
        = as the selection; False for the objects of a Practice tab that shows them itself
        (quick exercise, variant, Keep, drills, Play over MIDI)."""
        name = name or getattr(obj, "title", None) or type(obj).__name__
        base, k = name, 2
        while name in self.objects:
            name = f"{base} ({k})"
            k += 1
        self.objects[name] = obj
        if not getattr(obj, "title", None):
            try:
                obj.title = name                  # used e.g. as source name of exercises
            except AttributeError:
                pass
        it = self._make_item(name, obj)
        self._list_for(obj).addTopLevelItem(it)
        if log:
            self.log(f"object added: {name} ({type(obj).__name__}"
                     + (f", {len(obj)} exercises)" if _is_set(obj) else ")"))
        sel = log if select is None else select
        if sel:
            self.select(name)                     # (select() itself does no Preview)
        else:
            self._refresh_panel()
        if sel if preview is None else preview:
            self._preview_new(name)
        return name

    def _preview_new(self, name):
        """A NEW object in the Preview, after the current event (several made together:
        the last one), unless another tab came in front meanwhile (e.g. an exercise opened
        by a double click in the library) or the tab in front is busy."""
        from PySide6.QtCore import QTimer
        self._new_preview = (name, self.tabs.currentWidget())
        if self._hold_new_preview or self._new_preview_pending:
            return
        self._new_preview_pending = True
        QTimer.singleShot(0, self._preview_new_now)

    def _preview_new_now(self):
        self._new_preview_pending = False
        if self._new_preview is None:
            return None
        (name, front), self._new_preview = self._new_preview, None
        cur = self.tabs.currentWidget()
        if cur is not front and cur is not self._preview:
            return None
        self._preview_timer.stop()
        self._preview_name = None
        if not self._can_preview(name):
            return None
        return self.preview_object(name)

    # ------------------------------------------------ object lists (types, groups, selection)
    def _lists(self):
        return (self.mat_list, self.ex_list)

    def _list_for(self, obj):
        """Exercises (♩ ▦ ◆ ↻) go in the lower list, everything else in Material."""
        from ..tasks import is_exercise
        return self.ex_list if is_exercise(obj) else self.mat_list

    @property
    def obj_list(self):
        """The list in use (the last one where something was selected)."""
        return self._active_list

    def _selection_in(self, lst):
        """Selecting in one list clears the selection of the other one."""
        if lst.selectedItems():
            self._active_list = lst
            other = self.ex_list if lst is self.mat_list else self.mat_list
            if other.selectedItems():
                other.blockSignals(True)
                other.clearSelection()
                other.blockSignals(False)
        self._close_unfit_panel()
        self._refresh_panel()

    def _close_unfit_panel(self):
        """Owner, 2026-11-08: an exercise selected after Generate must not show the tool that
        made it ("Input: select…" in red): when the selection holds nothing the open Tools
        panel accepts (e.g. the exercise just generated), the panel closes."""
        tp = self.tool_panel
        t = getattr(tp, "tool", None)
        if tp is None or t is None or not t.inputs or not self.dock_tool.isVisible():
            return
        if self.selected_names() and not self.selected_objects(tuple(t.inputs)):
            self.dock_tool.hide()

    def _restore_split(self):
        try:
            sizes = settings().get("objects_split")
            if sizes and len(sizes) == 2 and min(int(x) for x in sizes) >= 60:
                self.split.setSizes([int(x) for x in sizes])
        except Exception:
            pass

    def _save_split(self):
        try:
            save_setting("objects_split", list(self.split.sizes()))
        except Exception:
            pass

    def _make_item(self, name, obj):
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        it = QTreeWidgetItem([name])
        it.setData(0, Qt.UserRole, name)
        _style(it, obj)
        if _is_set(obj):
            for k, ph in enumerate(obj.phrases):
                ch = QTreeWidgetItem([self._phrase_label(k, ph, obj)])
                ch.setData(0, Qt.UserRole, f"{name} #{k + 1}")
                _style(ch, ph)
                it.addChild(ch)
        self._decorate(it, obj)
        return it

    def _phrase_label(self, k, ph, st):
        """'#k  part – bars a-b (transform)' + the grade of the current user."""
        from ..tasks import shown_grade
        g = shown_grade(ph, self.user)
        return f"#{k + 1}  {_short(ph, st)}" + (f"   – {g:.1f}" if g is not None else "")

    def _decorate(self, it, obj=None):
        """Text and look of an exercise item: the name with the grade of the current user
        (best of today, else the last one); TO DO (never done today, tasks.TODO_RULE) =
        bold on a grey background, normal once done today."""
        from PySide6.QtGui import QColor, QBrush
        from ..tasks import is_exercise, to_do, shown_grade
        name = self._item_name(it)
        if obj is None:
            try:
                obj = self.get_object(name)
            except KeyError:
                return
        if not is_exercise(obj):
            return
        user = self.user
        if it.parent() is not None:
            st = self.objects.get(self._item_name(it.parent()))
            k = it.parent().indexOfChild(it)
            text = self._phrase_label(k, obj, st) if st is not None else name
            pos = text.rfind("   – ") if shown_grade(obj, user) is not None else -1
        else:
            g = shown_grade(obj, user)
            text = name + (f"   – {g:.1f}" if g is not None else
                           "   – n/a" if not getattr(obj, "graded", True) else "")
            pos = len(name) if len(text) > len(name) else -1
        it.setText(0, text)
        it.setData(0, GRADE_ROLE, pos if pos >= 0 else None)   # grade in its own colour
        todo = to_do(obj, user)
        f = it.font(0)
        f.setBold(todo)
        it.setFont(0, f)
        it.setBackground(0, QBrush(QColor(TODO_BACKGROUND)) if todo else QBrush())
        # colour of the kind: dark on the light grey (to do), light on the dark background
        # (done) — owner, 2026-11-19; every instrument drawn the same way
        hue = _exercise_hue(obj)
        it.setForeground(0, QBrush(_shade(hue, dark=todo or not _dark_base(self.ex_list))))
        try:
            inst = _exercise_instrument(obj)
        except Exception:
            inst = None
        if inst:
            it.setToolTip(0, f"{text}\nexercise for {inst}")
        for i in range(it.childCount()):
            self._decorate(it.child(i))

    def refresh_exercises(self):
        """Grades and to-do look of every exercise (after an attempt, a new user, a new day)."""
        for i in range(self.ex_list.topLevelItemCount()):
            self._decorate(self.ex_list.topLevelItem(i))
        for w in list(getattr(self, "tool_widgets", {}).values()):
            if hasattr(w, "refresh_routine"):
                w.refresh_routine()
        return self

    def _day_watch(self):
        """At 04:00 a new day starts: every exercise is to do again."""
        from ..diary import day_of
        d = day_of()
        try:
            from ..progress import lock_user
            lock_user(self.user)                   # still open on this computer
        except Exception:
            pass
        if d != getattr(self, "_today", None):
            self._today = d
            self.refresh_exercises()

    # ------------------------------------------------ attempts
    def attempt_added(self, obj):
        """An attempt was added to an exercise object: grades / to-do redrawn, listeners
        (the routine runner) told."""
        self.refresh_exercises()
        for fn in list(self._attempt_listeners):
            try:
                fn(obj)
            except Exception as e:
                self.log(f"attempt listener: {type(e).__name__}: {e}")
        return obj

    def _all_phrases(self):
        """Every phrase of the workspace, also inside groups and routines."""
        from ..phrase import Phrase, ExerciseSet
        from ..tasks import Routine
        for obj in self.objects.values():
            if isinstance(obj, Phrase):
                yield obj
            elif isinstance(obj, ExerciseSet):
                yield from obj.phrases
            elif isinstance(obj, Routine):
                for it in obj.items:
                    if isinstance(it["obj"], Phrase):
                        yield it["obj"]
        for ph in getattr(self, "_loose_phrases", []):
            yield ph

    def phrase_attempt(self, uid, grade, user=None, **extra):
        """Read & play / Listen & repeat: one take of the phrase `uid` = one attempt on the
        exercise object (no new object); its name shows the best of today."""
        from ..tasks import add_result
        user = user if user is not None else (self.user or "")
        found = None
        for ph in self._all_phrases():
            if ph.uid == uid:
                add_result(ph, user, grade, **extra)
                found = ph
        if found is not None:
            self.attempt_added(found)
        return found

    def clear_workspace(self, log=True):
        """Remove every object and close every tab."""
        self.stop_sound()
        while self.tabs.count():
            self.close_tab(0)
        self.objects.clear()
        for lst in self._lists():
            lst.clear()
        self.tool_panel = None
        self.dock_tool.hide()
        if log:
            self.log("workspace cleared")
        return self

    def _item_name(self, it):
        from PySide6.QtCore import Qt
        return it.data(0, Qt.UserRole) if it is not None else None

    def get_object(self, name):
        """Object by name; 'set name #k' = phrase k of an exercise set."""
        if name in self.objects:
            return self.objects[name]
        if " #" in name:
            base, k = name.rsplit(" #", 1)
            obj = self.objects.get(base)
            if _is_set(obj) and k.isdigit() and 1 <= int(k) <= len(obj):
                return obj.phrases[int(k) - 1]
        raise KeyError(name)

    def _walk(self):
        """Every item of both lists (tree order: Material, then Exercises)."""
        def walk(it):
            yield it
            for i in range(it.childCount()):
                yield from walk(it.child(i))
        for lst in self._lists():
            for i in range(lst.topLevelItemCount()):
                yield from walk(lst.topLevelItem(i))

    def selected_names(self):
        """Names of the selected objects (tree order)."""
        return [self._item_name(it) for it in self._walk() if it.isSelected()]

    def selected_objects(self, types=None):
        """Selected objects (optionally only those of the given types); a selected
        group and its phrases are not repeated."""
        out, seen = [], set()
        names = self.selected_names()
        for n in names:
            o = self.get_object(n)
            if id(o) in seen:
                continue
            if " #" in n and n.rsplit(" #", 1)[0] in names:
                continue                                  # phrase of a selected group
            seen.add(id(o))
            if types is None or isinstance(o, types):
                out.append(o)
        return out

    def selected_phrases(self):
        """Phrases of the selected exercise sets and the selected phrases."""
        from ..phrase import Phrase, ExerciseSet
        out = []
        for o in self.selected_objects((Phrase, ExerciseSet)):
            out += list(o.phrases) if isinstance(o, ExerciseSet) else [o]
        return out

    def select(self, *names):
        """Select objects by name (clears the previous selection)."""
        from PySide6.QtCore import QItemSelectionModel
        for lst in self._lists():
            lst.blockSignals(True)
            lst.clearSelection()
            lst.blockSignals(False)
        self._preview_quiet = True                # selected by code: no preview
        try:
            for n in names:
                it = self._find_item(n)
                if it is not None:
                    lst = it.treeWidget()
                    lst.setCurrentItem(it, 0, QItemSelectionModel.NoUpdate)
                    it.setSelected(True)
                    self._active_list = lst
        finally:
            self._preview_quiet = False
        self._close_unfit_panel()                 # as a selection made by hand
        self._refresh_panel()
        return self

    def _find_item(self, name):
        for it in self._walk():
            if self._item_name(it) == name:
                return it
        return None

    def selected_object(self):
        """Name of the current object (the last one clicked)."""
        it = self.obj_list.currentItem()
        if it is not None and it.isSelected():
            return self._item_name(it)
        names = self.selected_names()
        return names[0] if names else None

    def _name(self, name):
        name = name or self.selected_object()
        if name is None:
            self.log("select an object first")
        return name

    def _refresh_panel(self):
        if self.tool_panel is not None and hasattr(self.tool_panel, "refresh_inputs"):
            self.tool_panel.refresh_inputs()
        for w in list(getattr(self, "tool_widgets", {}).values()):
            if hasattr(w, "selection_changed"):
                w.selection_changed()

    # ------------------------------------------------ Play / Stop, Save, context menu
    def toggle_play(self):
        """Objects > Play: LISTEN to the selected object — its staff in the central panel,
        the red cursor moving and the sound (owner's rule: Play only here; the central
        panel has Start only, in the exercises). While it plays the button is Stop."""
        b = self.obj_buttons["Play"]
        if b.text() == "Stop":
            self.stop_sound()
            return self
        name = self._name(None)
        if name is None:
            return self
        sv = self.play_object(name)
        if sv is None:
            return self
        return self._mark_playing()

    def _mark_playing(self):
        """Objects > Play becomes Stop while an object is listened to."""
        self.obj_buttons["Play"].setText("Stop")
        from PySide6.QtCore import QTimer
        if self._play_timer is None:
            self._play_timer = QTimer(self.win)
            self._play_timer.setInterval(300)
            self._play_timer.timeout.connect(self._play_watch)
        self._play_timer.start()
        return self

    def is_playing(self):
        """An object is being listened to with Play (Objects)."""
        sv = getattr(self, "_playing", None)
        try:
            return sv is not None and getattr(sv, "timer", None) is not None and \
                sv.timer.isActive()
        except RuntimeError:                  # its view was replaced (Preview) and deleted
            return False

    def play_loop(self):
        """LOOP (owner, 2026-11-18): Play in Objects plays A (count-in of a backing) once, B
        repeated for about 10 minutes, C (its ending) once, as ONE sequence (no gap);
        Stop / Esc / the space bar stop it; default on, View > Loop playback (per user)."""
        return bool(settings().get("play_loop", True))

    def set_play_loop(self, on):
        save_setting("play_loop", bool(on))
        a = getattr(self, "_loop_action", None)
        if a is not None and a.isChecked() != bool(on):
            a.setChecked(bool(on))
        return bool(on)

    def _play_again(self, sv):
        """End of an object played with Play: again from the start (loop on)."""
        if getattr(self, "_playing", None) is not sv or not self.play_loop():
            return
        try:
            sv.set_position(0)
            sv.listen()
        except Exception as e:
            self.log(f"loop: {type(e).__name__}: {e}")

    def _play_watch(self):
        """Play button back to 'Play' when the listened object has finished."""
        if not self.is_playing():
            self._play_timer.stop()
            self.obj_buttons["Play"].setText("Play")

    def save_object_quick(self, name=None):
        """Objects > Save: in the file it was opened from / last saved to (same
        format); the first time (or for a generated object) = Save as…."""
        name = self._name(name)
        if name is None:
            return None
        obj = self.get_object(name)
        path = getattr(obj, "_saved_path", None)
        if path is None:
            from ..midi import Midi
            from ..pdf import Pdf
            src = getattr(obj, "source", None) if isinstance(obj, Midi) else None
            if isinstance(obj, Pdf) and not _is_temporary(obj.path):
                self.log(f"{name}: already in its file {obj.path}")
                return obj.path
            if src and os.path.isfile(src) and src.lower().endswith((".mid", ".midi")):
                path = src
        if path is None:
            return self.save_object(name)
        return self.save_object(name, path)

    def _object_menu(self, pos, lst=None):
        """Right click on an object: everything that can be done with it."""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QItemSelectionModel
        lst = lst or self.obj_list
        it = lst.itemAt(pos)
        if it is None:
            return None
        if not it.isSelected():                       # right click on another object: select it
            self._preview_quiet = True                # (no preview: the menu has View)
            try:
                lst.clearSelection()
                lst.setCurrentItem(it, 0, QItemSelectionModel.NoUpdate)
                it.setSelected(True)
            finally:
                self._preview_quiet = False
        self._active_list = lst
        objs = self.selected_objects()
        menu = QMenu(self.win)

        def add(text, fn, enabled=True):
            a = menu.addAction(text)
            a.triggered.connect(lambda checked=False: fn())
            a.setEnabled(enabled)
            return a

        single = len(objs) == 1
        from ..tasks import is_exercise
        if single and is_exercise(objs[0]):
            add("Do it", lambda: self.open_object())      # = double click
        add("View", lambda: self.view_object(), single)
        add("Stop" if self.obj_buttons["Play"].text() == "Stop" else "Play", self.toggle_play, single)
        add("Save", lambda: self.save_selected(quick=True))
        add("Save as…", lambda: self.save_selected(quick=False))
        from ..pdf import Pdf
        from ..midi import Midi
        from ..score import Score
        from ..phrase import Phrase
        if single and isinstance(objs[0], (Midi, Score, Phrase, Pdf)):
            add("Print…", lambda: self.print_object())
        if single and (isinstance(objs[0], Midi) or (isinstance(objs[0], Phrase) and
                                                    objs[0].purpose in ("reading", "repeat"))):
            from .library_ui import add_to_library_dialog          # owner, 2026-11-19
            add("Add to library…", lambda ph=objs[0]: add_to_library_dialog(self, ph))
        menu.addSeparator()
        add("Rename…", self.rename_object_dialog, single and it.parent() is None)
        add("Remove", self.remove_selected_object)
        for cat in registry.CATEGORIES:                  # tools that accept the selection
            from .. import instruments as _ins
            tools = [t for t in registry.by_category(cat)
                     if t.inputs and any(isinstance(o, tuple(t.inputs)) for o in objs)
                     and registry.is_available(t, _ins.current())]
            if tools:
                menu.addSeparator()
                subs = {}
                for t in tools:
                    if t.submenu:                         # e.g. Generate exercises > Read & play
                        if t.submenu not in subs:
                            subs[t.submenu] = menu.addMenu(t.submenu)
                        a = subs[t.submenu].addAction(f"{t.label}…")
                        a.triggered.connect(lambda checked=False, n=t.name: self.open_tool(n))
                    else:
                        add(f"{cat}: {t.label}…", lambda n=t.name: self.open_tool(n))
        menu.exec(lst.viewport().mapToGlobal(pos))
        return menu

    def open_object(self, name=None):
        """Double click: an exercise object is DONE in its own tab (♩ / ▦ Read & play or
        Listen & repeat, ◆ intervals / interval reading / drills, ↻ the routine runner);
        any other object is viewed."""
        from ..tasks import is_exercise
        name = self._name(name)
        if name is None:
            return None
        obj = self.get_object(name)
        if is_exercise(obj):
            w = self.practise(obj, name, key=f"open: {name}")
            if w is not None:
                return w
        return self.view_object(name)

    def open_exercise(self, name, tool=None):
        """A tab of its own for an exercise / group / exercise object (= double click)."""
        return self.practise(self.get_object(name), name, key=f"open: {name}", tool=tool)

    def practise(self, obj, title, key=None, tool=None):
        """Tab doing an exercise object (also one that is not in Objects, e.g. an item of a
        routine): Phrase / ExerciseSet -> Read & play or Listen & repeat bound to it;
        Task -> its tool bound to it (bind_task); Routine -> the routine runner. If the tab
        is already open it comes to the front. The Tools panel on the right is closed (it
        opens again with the next tool chosen). Returns the widget."""
        from ..phrase import ExerciseSet, Phrase
        from ..tasks import Task, Routine
        key = key or f"open: {id(obj)}"
        self.dock_tool.hide()        # owner, 2026-11-08: the Tools panel is no use while
                                     # practising and took the room of the staff
        w = self.tool_widgets.get(key)
        if w is not None and self.tabs.indexOf(w) >= 0:
            self.tabs.setCurrentWidget(w)
            return w
        if isinstance(obj, (Phrase, ExerciseSet)):
            tool = tool or {"reading": "play_reading", "repeat": "listen_repeat"}.get(obj.purpose)
            if tool is None:
                self.log(f"{title}: no exercise for '{obj.purpose}'")
                return None
            w = registry.TOOLS[tool].factory(self)
            w.bind(obj.phrases if isinstance(obj, ExerciseSet) else [obj])
        elif isinstance(obj, Task):
            tool = obj.kind if obj.is_quiz else f"drill_{obj.kind}"
            w = registry.TOOLS[tool].factory(self)
            w.bind_task(obj)
        elif isinstance(obj, Routine):
            from .routine_ui import routine_widget
            w = routine_widget(self, obj)
        elif type(obj).__name__ == "PlayOver":
            from .playover_ui import playover_widget
            w = playover_widget(self, obj)
        else:
            return None
        self.tool_widgets[key] = w
        short = title if len(title) <= 40 else "…" + title[-39:]
        self.add_tab(w, short)
        return w

    # ---------------------------------------------------------- side panel of a tab
    def show_side_panel(self, widget, owner, on_close=None):
        """A panel of a TAB in the right dock (owner, 2026-11-20: Edit of Read & play =
        Make a variant): it stays while that tab is in front; it closes when another tab
        comes to the front, when the tab is closed, when the tab asks (Run), when a Tools
        panel or a new tab takes its place — never because of a click in Objects.
        on_close() is called when it closes."""
        self.close_side_panel()
        self._side_owner, self._side_on_close = owner, on_close
        self.tool_panel = widget                 # no `tool`: _close_unfit_panel leaves it
        self.dock_tool.setWidget(widget)
        self.dock_tool.show()
        return widget

    def side_panel_owner(self):
        return self._side_owner

    def close_side_panel(self, owner=None):
        """Close the side panel (only that of `owner` if given)."""
        if self._side_owner is None or (owner is not None and owner is not self._side_owner):
            return
        cb = self._side_on_close
        self._side_owner = self._side_on_close = None
        self.tool_panel = None
        self.dock_tool.hide()
        if callable(cb):
            try:
                cb()
            except Exception as e:
                self.log(f"side panel: {type(e).__name__}: {e}")

    # ---------------------------------------------------------- preview (one click)
    def _clicked(self, it):
        """ONE CLICK = PREVIEW (owner, 2026-11-20): the object clicked is shown in the tab
        "Preview" (after the double-click time: a double click opens it instead)."""
        self._schedule_preview(it)

    def _current_changed(self, cur, prev):
        """Moving with the arrow keys in Objects previews each object (a mouse click is
        handled by _clicked; a selection made by code previews nothing)."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        if cur is None or self._preview_quiet or QApplication.mouseButtons() != Qt.NoButton:
            return
        self._schedule_preview(cur)

    def _schedule_preview(self, it):
        import time
        if it is None or time.monotonic() < self._preview_block:
            return
        name = self._preview_name = self._item_name(it)
        # FIRST THE EMPTY PAGE, AT ONCE (owner, 2026-11-20: the old content stayed for the
        # double-click time, then a flash of empty page): shown now, the content is made
        # when the double-click time is over
        if self._can_preview(name):
            self._blank_preview(name)
        self._preview_timer.start()

    def _double_clicked(self, it):
        """Double click: open / do it, no preview (also not from its second click)."""
        import time
        self._preview_timer.stop()
        self._preview_name = None
        self._preview_block = time.monotonic() + 1.0
        self.open_object(self._item_name(it))
        pv = self._preview                        # the empty page of its first click
        if pv is not None and self._preview_blank and self.tabs.indexOf(pv) >= 0:
            self.close_tab(self.tabs.indexOf(pv))

    def _can_preview(self, name):
        """The object can be shown in the Preview now."""
        if not name or self._find_item(name) is None:
            return False
        cur = self.tabs.currentWidget()
        if (cur is not None and cur is self._preview and not self._preview_blank
                and name == getattr(self, "_preview_of", None)):
            return False                      # already shown
        if cur is not None and cur is not self._preview and _busy(cur):
            return False                      # an exercise / a recording is going on
        if cur is not None and cur is self._side_owner:
            return False                      # its Edit panel is open: a click keeps it
        return True

    def _preview_now(self):
        name, self._preview_name = self._preview_name, None
        if not self._can_preview(name):
            return None
        return self.preview_object(name)

    def _tab_changed(self, i):
        """Another tab in front: the Preview tab disappears (owner, 2026-11-20), and so
        does the side panel of another tab (Edit)."""
        so = self._side_owner
        if so is not None and self.tabs.currentWidget() is not so:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda so=so: (self.tabs.currentWidget() is not so)
                              and self.close_side_panel(so))
        pv = self._preview
        if pv is None or self._preview_switching or self.tabs.indexOf(pv) < 0:
            return
        if self.tabs.currentWidget() is not pv:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._close_preview)

    def _close_preview(self):
        pv = self._preview
        if pv is None:
            return
        i = self.tabs.indexOf(pv)
        if i < 0:
            self._preview = None
        elif self.tabs.currentWidget() is not pv:
            self.close_tab(i)

    def _set_preview(self, name, widget, sv=None, bar=None):
        """The ONE tab "Preview" (created if needed, never a second one) now shows
        `widget` (sv: its StaffView, stopped when replaced); it comes to the front. The
        Tools panel stays as it is (a Generate input may be chosen with a click)."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        pv = self._preview
        self._preview_switching = True
        try:
            if pv is None or self.tabs.indexOf(pv) < 0:
                pv = self._preview = QWidget()
                QVBoxLayout(pv).setContentsMargins(0, 0, 0, 0)
                self.tabs.addTab(pv, "Preview")
            old = self.views.pop(pv, None)
            if old is not None:
                old.stop()
            lay = pv.layout()
            while lay.count():
                w = lay.takeAt(0).widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()
            lay.addWidget(widget)
            if sv is not None:
                sv.obj_name = name
                self.views[pv] = sv
            self.tabs.set_bar(pv, bar)
            self.tabs.setTabText(self.tabs.indexOf(pv),
                                 f"Preview: {name}"[:60].replace("&", "&&"))
            self.tabs.setCurrentWidget(pv)
        finally:
            self._preview_switching = False
        self._preview_of = name
        self._preview_blank = False
        return pv

    def _blank_preview(self, name):
        """FIRST AN EMPTY PAGE (owner, 2026-11-20: "when another object is clicked, first a
        blank page, so one sees that something else is loading"): the Preview shows an
        empty page (the background of the app) and is drawn on screen at once, then the
        new content is made."""
        from PySide6.QtWidgets import QApplication, QLabel
        from PySide6.QtCore import QEventLoop, Qt as _Qt
        # "Preparing preview…" in grey in the middle (owner, 2026-11-20)
        w = QLabel("Preparing preview…")
        w.setAlignment(_Qt.AlignCenter)
        w.setStyleSheet("color: #888888; font-size: 15px;")
        self._set_preview(name, w)
        self._preview_blank = True
        try:
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass

    def _staff_preview(self, name, obj):
        from PySide6.QtCore import Qt
        from ..staffview import StaffView
        sv = StaffView(obj, title=name)
        sv.win.setWindowFlags(Qt.Widget)
        sv.hide_toolbar()
        self._double_click_plays(sv, name)
        self._set_preview(name, sv.win, sv, sv.make_bar())
        return sv

    def _show_preview(self, name, score):
        """An exercise's staff in the Preview tab (View, Play of an exercise)."""
        return self._staff_preview(name, score)

    def _info_widget(self, html):
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
        from PySide6.QtCore import Qt
        box = QWidget()
        lay = QVBoxLayout(box)
        lab = QLabel(html)
        lab.setTextFormat(Qt.RichText)
        lab.setWordWrap(True)
        lab.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(lab)
        lay.addStretch(1)
        return box

    def _group_info(self, name, obj):
        """Text of the Preview for a group ▦ ◆, a routine ↻, Play over MIDI ♬ (owner,
        2026-11-20: "a text with information on that group"): name and type, number of
        exercises, instrument(s), where they come from, difficulty (mean, max), done
        today and the mean grade of today."""
        import html
        from ..phrase import ExerciseSet, Phrase
        from ..tasks import Routine, TaskGroup, Task, done_today, shown_grade, kind_label
        from .. import instruments as ins
        user = self.user
        rows = []
        purposes = {"reading": "Read & play", "repeat": "Listen & repeat"}
        if isinstance(obj, ExerciseSet):
            typ = f"Group of {purposes.get(obj.purpose, obj.purpose)} exercises"
            items = list(obj.phrases)
        elif isinstance(obj, TaskGroup):
            typ = "Group of exercises"
            items = list(obj.phrases)
        elif isinstance(obj, Routine):
            typ = "Routine"
            items = [it["obj"] for it in obj.items]
        elif type(obj).__name__ == "PlayOver":
            typ = "Play over MIDI (not graded)"
            items = []
            tracks = []
            for i in getattr(obj, "tracks", []) or []:
                try:
                    tracks.append(obj.track_label(i))
                except Exception:
                    tracks.append(str(i))
            rows.append(("Tracks shown and muted", ", ".join(tracks) or "none chosen"))
            bars = (f"{obj.bar_from or 'start'} to {obj.bar_to or 'end'}")
            rows.append(("Bars", bars))
            rows.append(("Tempo", f"{obj.tempo_pct} %"))
            if getattr(obj, "source", ""):
                rows.append(("From", obj.source))
        else:
            typ = type(obj).__name__
            items = []
        if items:
            rows.append(("Exercises", str(len(items))))
            names = []
            for o in items:
                i = _exercise_instrument(o)
                if i:
                    k = ins.key_of_played(i)
                    lab = ins.label(k) if k else i
                    if lab not in names:
                        names.append(lab)
            rows.append(("Instrument", ", ".join(names) or "any"))
            kinds, origins = [], []
            for o in items:
                if isinstance(o, Task):
                    k = kind_label(o.kind)
                    if k not in kinds:
                        kinds.append(k)
                if isinstance(o, Phrase):
                    org = o.origin or {}
                    if org.get("duet"):
                        src = "random"
                    elif org.get("library"):
                        src = "library"
                    elif org.get("midi"):
                        m = org["midi"]
                        src = f"MIDI {m.get('title', '')}".strip()
                    else:
                        src = o.source or "—"
                    if src not in origins:
                        origins.append(src)
            if kinds:
                rows.append(("Kind", ", ".join(kinds)))
            if origins:
                more = f" (+{len(origins) - 5} more)" if len(origins) > 5 else ""
                rows.append(("From", ", ".join(origins[:5]) + more))
            try:
                from ..difficulty import difficulty
                d = difficulty(obj) if isinstance(obj, (ExerciseSet, Routine)) else None
            except Exception:
                d = None
            if d and d.get("score") is not None:
                rows.append(("Difficulty", f"mean {d['score']:.1f}, max {d['max']:.1f}"))
            n_done = sum(1 for o in items if done_today(o, user))
            grades = [g for g in (shown_grade(o, user) for o in items) if g is not None]
            today = f"{n_done} of {len(items)}"
            if grades:
                today += f", mean grade {sum(grades) / len(grades):.1f}"
            rows.append(("Done today", today))
        out = [f"<h3>{html.escape(name)}</h3>", f"<p><i>{html.escape(typ)}</i></p>",
               "<table cellspacing='4'>"]
        for k, v in rows:
            out.append(f"<tr><td><b>{html.escape(k)}:</b></td><td>{html.escape(str(v))}</td>"
                       "</tr>")
        out.append("</table>")
        return "".join(out)

    def preview_object(self, name=None):
        """ONE CLICK = PREVIEW (owner, 2026-11-20): the object in the ONE tab "Preview"
        (it never becomes two; it disappears when another tab comes in front). A MIDI,
        score, recording or exercise ♩: its staff; a PDF: its pages; an exercise ◆: its
        summary; a group ▦ / ◆, a routine ↻, Play over MIDI ♬: a text about it."""
        from ..score import Score
        from ..midi import Midi
        from ..pdf import Pdf
        from ..phrase import Phrase
        from ..tasks import Task
        name = self._name(name)
        if name is None:
            return None
        try:
            obj = self.get_object(name)
            if not (self._preview_blank and getattr(self, "_preview_of", None) == name
                    and self.tabs.currentWidget() is self._preview):
                self._blank_preview(name)         # (already there after a click)
            if isinstance(obj, Phrase):
                return self._staff_preview(name, obj.to_score())
            if isinstance(obj, (Score, Midi)):
                return self._staff_preview(name, obj)
            if isinstance(obj, Pdf):
                from .viewers import pdf_view
                w = pdf_view(obj.path)
                return self._set_preview(name, w, bar=getattr(w, "bar", None))
            if isinstance(obj, Task):
                from .viewers import task_view
                w = task_view(self, obj, name)
                return self._set_preview(name, w, bar=getattr(w, "bar", None))
            return self._set_preview(name, self._info_widget(self._group_info(name, obj)))
        except Exception as e:
            self.log(f"preview {name}: {type(e).__name__}: {e}")
            return None

    def view_object(self, name=None):
        """Score/Midi/Notes: StaffView in a tab; exercise ♩: the Preview tab; group ▦: its
        information in the Preview tab; Pdf: its pages."""
        from PySide6.QtCore import Qt
        from ..score import Score
        from ..midi import Midi
        from ..pdf import Pdf
        from ..phrase import Phrase, ExerciseSet
        name = self._name(name)
        if name is None:
            return None
        obj = self.get_object(name)
        try:
            if isinstance(obj, ExerciseSet):
                it = self._find_item(name)
                if it is not None:
                    it.setExpanded(True)
                return self.preview_object(name)          # its information (2026-11-20)
            if isinstance(obj, Phrase):
                return self._show_preview(name, obj.to_score())
            from ..notes import Notes
            if isinstance(obj, Midi) and not isinstance(obj, Notes):
                from .midiview import MidiView           # staff + switch to the piano roll
                sv = MidiView(obj, name, app=self)
                sv.obj_name = name
                self._double_click_plays(sv, name)
                sv.win.bar = sv.make_bar()            # Stop, Zoom…, Piano roll (no Play)
                self.views[sv.win] = sv
                self.add_tab(sv.win, name)
                return sv
            if isinstance(obj, (Score, Midi)):
                from ..staffview import StaffView
                sv = StaffView(obj, title=name)
                sv.win.setWindowFlags(Qt.Widget)
                sv.hide_toolbar()
                sv.win.bar = sv.make_bar()            # Stop, Zoom… (no Play: Objects only)
                sv.obj_name = name
                self._double_click_plays(sv, name)
                self.views[sv.win] = sv
                self.add_tab(sv.win, name)
                return sv
            if isinstance(obj, Pdf):
                from .viewers import pdf_view
                return self.add_tab(pdf_view(obj.path), name)
            from ..tasks import Task, Routine
            if isinstance(obj, Task):
                from .viewers import task_view
                return self.add_tab(task_view(self, obj, name), f"View: {name}")
            if isinstance(obj, Routine):
                return self.practise(obj, name, key=f"open: {name}")
        except Exception as e:
            self.log(f"view {name}: {type(e).__name__}: {e}")
            return None
        self.log(f"{name}: no viewer for {type(obj).__name__}")
        return None

    def _as_midi(self, obj):
        from ..score import Score
        from ..pdf import Pdf
        from ..phrase import Phrase, ExerciseSet
        if isinstance(obj, ExerciseSet):
            raise TypeError("an exercise set: select one of its exercises")
        if isinstance(obj, Phrase):
            return obj.to_midi()
        if isinstance(obj, Score):
            return obj.to_midi()
        if isinstance(obj, Pdf):
            if getattr(obj, "_midi", None) is None:
                obj._midi = self._quiet(obj.to_midi)
            return obj._midi
        return obj

    def _view_for(self, name):
        """The open staff tab of an object, if any."""
        for w, sv in self.views.items():
            if getattr(sv, "obj_name", None) == name and self.tabs.indexOf(w) >= 0:
                return sv
        return None

    def play_object(self, name=None):
        """Listen to an object: its staff is shown in the central panel (the tab already
        open, or a new one; an exercise in the Preview tab; a PDF as the staff of
        its MIDI) and played with the red cursor following the sound: from the start, or
        from the bar clicked on that view after one count-in bar (2026-11-23).
        Returns the StaffView."""
        from PySide6.QtCore import Qt
        from ..midi import Midi
        from ..pdf import Pdf
        from ..phrase import Phrase, ExerciseSet
        name = self._name(name)
        if name is None:
            return None
        try:
            if Midi._default_sf2 is None:
                raise RuntimeError("no soundfont: choose one in Settings > Soundfont")
            obj = self.get_object(name)
            if isinstance(obj, ExerciseSet):
                raise TypeError("an exercise set: select one of its exercises")
            self._stop_players()
            sv = self._view_for(name)                 # the view already shown (also the
            if sv is not None:                        # Preview): its bar clicked is kept
                page = next((w for w, v in self.views.items() if v is sv), sv.win)
                self.tabs.setCurrentWidget(page)
            elif isinstance(obj, Phrase):
                sv = self._show_preview(name, obj.to_score())
            else:
                if sv is None:
                    if isinstance(obj, Pdf):
                        from ..staffview import StaffView
                        sv = StaffView(self._as_midi(obj), title=name)
                        sv.win.setWindowFlags(Qt.Widget)
                        sv.hide_toolbar()
                        sv.win.bar = sv.make_bar()
                        self._double_click_plays(sv, name)
                        self.views[sv.win] = sv
                        self.add_tab(sv.win, f"{name} (staff)")
                    else:
                        sv = self.view_object(name)
                    if sv is None:
                        return None
                    sv.obj_name = name
            if isinstance(obj, Phrase) and getattr(sv, "midi", None) is None:
                sv.midi = obj.to_midi()
            return self._listen(sv, name)
        except Exception as e:
            self.log(f"play {name}: {type(e).__name__}: {e}")
            return None

    def _listen(self, sv, name):
        """Play an object's view: from the bar clicked on it (from_q) after ONE COUNT-IN
        BAR (owner, 2026-11-23), else from the start with no count-in, as before."""
        start = getattr(sv, "from_q", None)
        self._playing = sv
        # LOOP (View > Loop playback): A once, B for about 10 minutes, C once, as one
        # sequence for the synth (StaffView / PianoRollView .loop); it ends after C — only
        # when it starts from the beginning
        sv.on_end = None
        sv.loop = self.play_loop()
        if start is None:
            sv.set_position(0)
            sv.listen(start=0, count_in=0)
        else:
            sv.listen(start=start, count_in=1)
        self.log(f"playing {name}" + (f" from beat {start:g}" if start is not None else "")
                 + (" (loop)" if self.play_loop() and not start else ""))
        return sv

    def _double_click_plays(self, sv, name):
        """DOUBLE CLICK ON A BAR (owner, 2026-11-23): the object of this view is played
        from that bar after one count-in bar, as Play in Objects (Stop / Esc / space bar)."""
        def play(q, sv=sv, name=name):
            from ..midi import Midi
            from ..phrase import Phrase
            try:
                if Midi._default_sf2 is None:
                    raise RuntimeError("no soundfont: choose one in Settings > Soundfont")
                self.stop_sound()
                obj = self.get_object(name)
                if isinstance(obj, Phrase) and getattr(sv, "midi", None) is None:
                    sv.midi = obj.to_midi()
                self._listen(sv, name)
                self._mark_playing()
            except Exception as e:
                self.log(f"play {name}: {type(e).__name__}: {e}")
        sv.on_double_click = play
        return sv

    # ------------------------------------------------------------ several objects at once
    def _save_names(self):
        """Selected objects to save (a group, not its phrases again)."""
        names = self.selected_names()
        return [n for n in names if not (" #" in n and n.rsplit(" #", 1)[0] in names)]

    def save_selected(self, quick=False):
        """Objects > Save / Save as… on the selection (owner, 2026-11-13: 20 PDFs with
        fingerings selected, Save saved only the last one). One object: as before. Several:
        Save as… = all of them in ONE folder chosen once (save_objects); Save = each one in
        its own file when it has one, the others in one folder chosen once."""
        names = self._save_names()
        if len(names) <= 1:
            return self.save_object_quick() if quick else self.save_object()
        if not quick:
            return self.save_objects(names)
        known, new = [], []
        for n in names:
            (known if self._own_file(self.get_object(n)) else new).append(n)
        out = [self.save_object_quick(n) for n in known]
        if new:
            out += self.save_objects(new) or []
        return out

    def _own_file(self, obj):
        """The file an object is saved to by Save (None: never saved / temporary)."""
        from ..midi import Midi
        from ..pdf import Pdf
        path = getattr(obj, "_saved_path", None)
        if path:
            return path
        if isinstance(obj, Pdf):
            return None if _is_temporary(obj.path) else obj.path
        src = getattr(obj, "source", None) if isinstance(obj, Midi) else None
        if src and isinstance(src, str) and os.path.isfile(src) \
                and src.lower().endswith((".mid", ".midi")):
            return src
        return None

    def save_objects(self, names):
        """Several objects in ONE folder (native folder dialog, opened once): each one with
        its name and the extension of its type (.pdf, .mid, .mke exercises, .mkr routines);
        files that exist already: one question for all of them (overwrite / skip / cancel).
        Returns the paths written."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from ..pdf import Pdf
        from ..phrase import ExerciseSet, Phrase
        from ..tasks import Task, Routine
        from ..playover import PlayOver
        first = self.get_object(names[0])
        start = folder(TYPE_FOLDER.get(_type_of(first)[0], "midi"))
        d = QFileDialog.getExistingDirectory(self.win, f"Save {len(names)} objects in…", start)
        if not d:
            return None
        plan = []
        for n in names:
            o = self.get_object(n)
            if isinstance(o, Pdf):
                ext = ".pdf"
            elif isinstance(o, (ExerciseSet, Phrase)):
                ext = ".mke"
            elif isinstance(o, Routine) and _type_of(o)[0] != "TaskGroup":
                ext = ".mkr"
            elif isinstance(o, (Task, Routine, PlayOver)):
                ext = ".mke"
            else:
                ext = ".mid"
            base = n.replace(os.sep, "_").replace(":", "_")
            plan.append((n, os.path.join(d, base + ext)))
        exist = [p for _, p in plan if os.path.exists(p)]
        if exist:
            box = QMessageBox(self.win)
            box.setWindowTitle("Files already there")
            box.setText(f"{len(exist)} of the {len(plan)} files exist already in {d}.")
            ow = box.addButton("Overwrite them", QMessageBox.AcceptRole)
            sk = box.addButton("Skip them", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Cancel)
            box.exec()
            if box.clickedButton() is sk:
                plan = [(n, p) for n, p in plan if p not in exist]
            elif box.clickedButton() is not ow:
                return None
        out = [p for p in (self.save_object(n, p) for n, p in plan) if p]
        self.log(f"saved {len(out)} of {len(names)} objects in {d}")
        return out

    def save_object(self, name=None, path=None):
        """Save an object: .mid (MIDI), .pdf (Pdf: copy; Midi/Score: engraved score),
        .wav (audio export), .json (exercise group, ONE exercise, exercise object ◆ with its
        results, routine). Exercises are saved only as exercises (.json, owner's rule: not
        MIDI / PDF / audio). Without path a file dialog opens in the default folder of the
        type (Settings > Folders…)."""
        import shutil
        from PySide6.QtWidgets import QFileDialog
        from ..pdf import Pdf
        from ..phrase import ExerciseSet, Phrase, save_exercises
        from ..tasks import Task, Routine, save as save_task
        name = self._name(name)
        if name is None:
            return None
        obj = self.get_object(name)
        from ..playover import PlayOver
        is_task = isinstance(obj, (Task, Routine, PlayOver))   # exercise objects, routines
        is_set = isinstance(obj, (ExerciseSet, Phrase))         # exercises: .mke / .json only
        if path is None:
            filt = ("PDF (*.pdf);;MIDI (*.mid)" if isinstance(obj, Pdf)
                    else "MusiKitE routine (*.mkr);;JSON (*.json)"
                    if isinstance(obj, Routine) and _type_of(obj)[0] != "TaskGroup"
                    else "MusiKitE exercise (*.mke);;JSON (*.json)" if is_set or is_task
                    else "MIDI (*.mid);;PDF score (*.pdf);;WAV audio (*.wav)")
            kind = TYPE_FOLDER.get(_type_of(obj)[0], "midi")
            base = self._prefixed(name) if kind in ("exercises", "results") else name.replace(os.sep, "_")
            path, chosen = QFileDialog.getSaveFileName(self.win, f"Save {name}",
                                                       os.path.join(folder(kind), base), filt)
            if not path:
                return None
            if not os.path.splitext(path)[1]:          # extension from the chosen filter
                for e in (".pdf", ".wav", ".csv", ".mke", ".mkr", ".json", ".mid"):
                    if e[1:] in chosen.lower():
                        path += e
                        break
        ext = os.path.splitext(path)[1].lower()
        try:
            if is_set:
                path = save_exercises(obj, path)
            elif is_task:
                path = save_task(obj, path)
            elif isinstance(obj, Pdf) and ext == ".pdf":
                shutil.copyfile(obj.path, path)
            elif ext == ".pdf":
                self._quiet(self._as_midi(obj).to_pdf, path, title=name)
            elif ext == ".wav":
                self._as_midi(obj).render(path)
            else:
                if ext not in (".mid", ".midi"):
                    path += ".mid"
                self._quiet(self._as_midi(obj).write, path)
            self.log(f"saved {name} -> {path}")
            try:
                obj._saved_path = path               # Save writes here next time
            except AttributeError:
                pass
        except Exception as e:
            self.log(f"save {name}: {type(e).__name__}: {e}")
            return None
        return path

    def open_file(self, path=None):
        """Open MIDI, PDF, MusicXML files or saved exercise groups (.json) as objects.
        path=None: the native dialog, SEVERAL files can be chosen at once (Cmd/Shift-click);
        path = a file or a list of files. Returns the name (one file) or the list of names.
        The dialog starts in the MIDI folder."""
        from PySide6.QtWidgets import QFileDialog
        if path is None:
            paths, _ = QFileDialog.getOpenFileNames(
                self.win, "Open", folder("midi"),
                "Music files (*.mid *.midi *.pdf *.musicxml *.xml *.mxl *.mke *.mkr *.json);;All files (*)")
            if not paths:
                return None
            path = paths if len(paths) > 1 else paths[0]
        if isinstance(path, (list, tuple)):
            names = []
            for p in path:
                n = self._open_one(p)
                if isinstance(n, list):
                    names += n
                elif n:
                    names.append(n)
            self.log(f"opened {len(names)} objects from {len(path)} files")
            return names
        return self._open_one(path)

    def _open_one(self, path):
        """Open one file as an object (see open_file); returns its name or None."""
        import json
        from ..midi import Midi
        from ..pdf import Pdf
        base, ext = os.path.splitext(os.path.basename(path))
        ext = ext.lower()
        try:
            if ext in (".mid", ".midi"):
                obj = Midi(path)
            elif ext == ".pdf":
                obj = Pdf(path)
            elif ext in (".musicxml", ".xml", ".mxl"):
                import music21
                from ..score import Score
                obj = Score(music21.converter.parse(path), base)
                obj.source = path
            elif ext in (".json", ".mke", ".mkr"):
                from ..phrase import read_exercise_file
                d = read_exercise_file(path)              # .mke = zip of the JSON
                if d.get("format") == "musikite-workspace":
                    names = self._load_workspace_file(path, replace=False)
                    return names
                if d.get("format") == "musikite-exercises" or "phrases" in d:
                    from ..phrase import exercises_from_dict
                    obj = exercises_from_dict(d)          # a group, or ONE exercise
                    base = obj.title or base
                    obj._saved_path = path
                elif d.get("format") in ("musikite-task", "musikite-routine") or (
                        "kind" in d and "items" in d):      # old result: converted
                    from ..tasks import from_file_dict
                    obj = from_file_dict(d)
                    base = obj.title
                    obj._saved_path = path if d.get("format") else None
                else:
                    self.log(f"{path}: unknown JSON content")
                    return None
            else:
                self.log(f"unknown file type: {path}")
                return None
        except Exception as e:
            self.log(f"open {path}: {type(e).__name__}: {e}")
            return None
        return self.add_object(obj, base)

    def run_tool(self, name, *inputs, **params):
        """Run a transform tool. Inputs: objects or names; none given = the objects
        selected in Objects that the tool accepts. The tool runs once per input
        (or once with all of them if it takes several, e.g. merge); missing options
        take their defaults. Results are added to Objects; returns the new name
        (a list if there are several)."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        t = registry.TOOLS[name]
        if t.inputs:
            types = tuple(t.inputs)
            if inputs:
                objs = [self.get_object(o) if isinstance(o, str) else o for o in inputs]
            else:
                objs = self.selected_objects(types)
                skipped = len(self.selected_objects()) - len(objs)
                if skipped:
                    self.log(f"{t.label}: {skipped} selected object(s) skipped (not "
                             f"{' / '.join(c.__name__ for c in types)})")
            if not objs:
                self.log(f"{t.label}: select one or more {' / '.join(c.__name__ for c in types)} "
                         "objects on the left")
                return None
            batches = [objs] if t.multi else [[o] for o in objs]
        else:
            batches = [[]]
        values = {p.name: p.value() for p in t.params}
        values.update(params)
        names = []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._hold_new_preview = True             # several results: the last one, at the end
        try:
            for objs in batches:
                try:
                    res = self._quiet(t.func, *objs, **values)
                except Exception as e:
                    self.log(f"{t.label}: {type(e).__name__}: {e}")
                    continue
                for r in (res if isinstance(res, list) else [res]):   # e.g. N exercises to do
                    oname = t.name_fn(r, values) if t.name_fn else t.label
                    names.append(self.add_object(r, oname))
                QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()
            self._hold_new_preview = False
        if self._new_preview is not None and not self._new_preview_pending:
            from PySide6.QtCore import QTimer
            self._new_preview_pending = True
            QTimer.singleShot(0, self._preview_new_now)
        if not names:
            return None
        if len(names) > 1:
            self.select(*names)                   # every object made, selected
        return names[0] if len(names) == 1 else names

    def _quiet(self, fn, *a, **kw):
        """Call fn and send what it prints to the Log."""
        import contextlib
        import io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                return fn(*a, **kw)
        finally:
            for line in buf.getvalue().splitlines():
                if line.strip():
                    self.log(line)

    def rename_object(self, old, new):
        """Rename an object (top level) from code; returns the name it got (unique)."""
        if old not in self.objects or new == old:
            return old
        base, k, name = new, 2, new
        while name in self.objects:
            name = f"{base} ({k})"
            k += 1
        obj = self.objects.pop(old)
        self.objects[name] = obj
        it = self._find_item(old)
        if it is not None and it.parent() is None:
            lst = it.treeWidget()
            idx = lst.indexOfTopLevelItem(it)
            lst.takeTopLevelItem(idx)
            lst.insertTopLevelItem(idx, self._make_item(name, obj))
        return name

    def rename_object_dialog(self):
        from PySide6.QtWidgets import QInputDialog
        from PySide6.QtCore import Qt
        it = self.obj_list.currentItem()
        if it is None or it.parent() is not None:
            self.log("rename: select an object (not an exercise inside a group)")
            return
        old = self._item_name(it)
        new, ok = QInputDialog.getText(self.win, "Rename", "Name:", text=old)
        if ok and new.strip() and new.strip() not in self.objects:
            self.rename_object(old, new.strip())

    def remove_selected_object(self):
        """Remove the selected objects (an exercise inside a group leaves the group)."""
        self._preview_quiet = True                # the next item becoming current: no preview
        try:
            self._remove_selected()
        finally:
            self._preview_quiet = False
        self._refresh_panel()

    def _remove_selected(self):
        if getattr(self, "_preview_of", None) in self.selected_names() and \
                self._preview is not None and self.tabs.indexOf(self._preview) >= 0:
            self.close_tab(self.tabs.indexOf(self._preview))     # it showed a removed object
        for n in list(self.selected_names()):
            it = self._find_item(n)
            if it is None:
                continue
            parent = it.parent()
            lst = it.treeWidget()
            if parent is None:
                self.objects.pop(n, None)
                lst.takeTopLevelItem(lst.indexOfTopLevelItem(it))
            else:
                base = self._item_name(parent)
                st = self.objects.get(base)
                ph = self.get_object(n)
                if st is not None:
                    st.phrases = [p for p in st.phrases if p is not ph]
                    idx = lst.indexOfTopLevelItem(parent)
                    lst.takeTopLevelItem(idx)
                    lst.insertTopLevelItem(idx, self._make_item(base, st))

    # ---------------------------------------------------------- audio
    def soundfont_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        from ..midi import Midi
        path, _ = QFileDialog.getOpenFileName(self.win, "Soundfont", folder("soundfonts"),
                                              "SoundFont (*.sf2 *.sf3)")
        if path:
            self.set_soundfont(path)
        return Midi._default_sf2

    def set_soundfont(self, path):
        from ..midi import Midi
        Midi().add_sf2(path)                    # sets the default for every object
        from ..progress import portable
        save_setting("sf2", portable(Midi._default_sf2))      # valid on the other computer
        self.log(f"soundfont: {Midi._default_sf2}")
        return self

    def settings(self, page=None):
        """The Settings window (tree of sections on the left); page: section to show."""
        from .settingsdialog import settings_dialog
        self._settings_dialog = settings_dialog(self, page)
        self._settings_dialog.show()
        return self._settings_dialog

    def folder_settings(self):
        return self.settings("Folders")

    def exercise_settings(self):
        return self.settings("Exercises")

    def audio_settings(self):
        """Settings window on the Audio page (returned: drivable from code)."""
        d = self.settings("Audio")
        d.test = d.pages["Audio"].test
        d.meter = d.pages["Audio"].meter
        d.values = d.pages["Audio"].values
        d.save = d.save_all
        return d

    def print_object(self, name=None):
        """Print a score (Midi, Score, exercise, Pdf): engraved to a temporary PDF,
        then the system print dialog."""
        import tempfile
        from PySide6.QtPrintSupport import QPrinter, QPrintDialog
        from PySide6.QtGui import QPainter, QImage
        from PySide6.QtCore import QRectF
        from ..pdf import Pdf
        name = self._name(name)
        if name is None:
            return None
        obj = self.get_object(name)
        try:
            if isinstance(obj, Pdf):
                path = obj.path
            else:
                path = os.path.join(tempfile.mkdtemp(prefix="musikite_"), "print.pdf")
                self._quiet(self._as_midi(obj).to_pdf, path, title=name)
        except Exception as e:
            self.log(f"print {name}: {type(e).__name__}: {e}")
            return None
        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(name)
        dlg = QPrintDialog(printer, self.win)
        if dlg.exec() != QPrintDialog.Accepted:
            return None
        import pymupdf
        doc = pymupdf.open(path)
        p = QPainter(printer)
        try:
            for k, page in enumerate(doc):
                if k:
                    printer.newPage()
                pix = page.get_pixmap(dpi=300, alpha=False)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                r = p.viewport()
                scale = min(r.width() / pix.width, r.height() / pix.height)
                p.drawImage(QRectF(0, 0, pix.width * scale, pix.height * scale), img)
        finally:
            p.end()
        self.log(f"printed {name} ({doc.page_count} pages)")
        return path

    def audio_test(self):
        from .. import realtime
        try:
            info = realtime.test()
            self.log(f"audio OK: driver {info['driver']}, device {info['device'] or 'default'}, "
                     f"latency {info['latency_ms']} ms" + (f" [{info['error']}]" if info["error"] else ""))
        except Exception as e:
            self.log(f"audio did not start: {e}")
            info = None
        return info

    def stop_sound(self):
        if getattr(self, "obj_buttons", None):
            self.obj_buttons["Play"].setText("Play")
            if self._play_timer is not None:
                self._play_timer.stop()
        sv = getattr(self, "_playing", None)
        if sv is not None:
            self._playing = None                       # first: no loop restart
            try:
                sv.on_end = None
                sv.stop()
            except Exception:
                pass
        self._stop_players()

    def _stop_players(self):
        from .. import realtime
        for p in list(realtime._players.values()):
            p.stop()

    # ---------------------------------------------------------- misc
    def log(self, text):
        """Write in the Log panel and in ~/.musikite/log.txt (kept for diagnosis)."""
        self.logbox.appendPlainText(str(text))
        try:
            import datetime as _dt
            from ..progress import APP_HOME
            os.makedirs(APP_HOME, exist_ok=True)
            path = os.path.join(APP_HOME, "log.txt")
            if os.path.isfile(path) and os.path.getsize(path) > 2_000_000:
                os.replace(path, path + ".old")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{_dt.datetime.now().isoformat(timespec='seconds')} "
                        f"[{self.user or '-'}] {text}\n")
        except Exception:
            pass

    def _install_excepthook(self):
        """Errors raised inside Qt callbacks (buttons, timers) go to the Log and to
        log.txt instead of being lost in the terminal."""
        import sys
        import traceback
        prev = sys.excepthook

        def hook(etype, value, tb):
            try:
                self.log("ERROR:\n" + "".join(traceback.format_exception(etype, value, tb)))
            except Exception:
                pass
            prev(etype, value, tb)
        sys.excepthook = hook

    def message(self, title, text):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self.win, title, text)

    def show(self):
        try:
            ip = get_ipython()                  # noqa: F821
            if ip.__class__.__name__ == "ZMQInteractiveShell":
                ip.enable_gui("qt")
        except NameError:
            pass
        self.win.show()
        return self

    def run(self):
        self.win.show()
        _app().exec()
        return self

    def __repr__(self):
        return (f"MusiKitE App(user={self.user!r}, tabs={self.tabs.count()}, "
                f"objects={list(self.objects)})")
