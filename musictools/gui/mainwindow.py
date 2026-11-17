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

    app = musictools.gui()
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
# default soundfont in musictools/data (S. Christian Collins, free licence): used when the
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


def _key_filter(app):
    """COMPUTER KEYBOARD (owner, 2026-11-17): the keys a w s e d f t g y h u j k o l p ò
    (z x octave, c v velocity) go to midiin.ComputerKeyboard while a KeyboardSynth has it
    open (Free player, an exercise take, Test MIDI) and no text / number field has the
    focus; Cmd / Ctrl / Alt shortcuts stay as they are. Leaving the program releases the
    keys held (no hanging note)."""
    from PySide6.QtCore import QObject, QEvent, Qt
    from PySide6.QtWidgets import (QApplication, QLineEdit, QAbstractSpinBox, QTextEdit,
                                   QPlainTextEdit, QComboBox)

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


class App:
    def __init__(self):
        from PySide6.QtWidgets import (QMainWindow, QTabWidget, QDockWidget, QTreeWidget,
                                       QPlainTextEdit, QToolBar, QLabel, QComboBox,
                                       QPushButton, QAbstractItemView)
        from PySide6.QtCore import Qt
        from ..midi import Midi
        _app()
        from . import intervals, interval_reading, chords, flashcards, play_reading, freeplayer, tools_basic, drills_ui, diaryview  # noqa: F401  (register the tools)
        self.progress = Progress()
        self.objects = {}                      # name -> object
        self._attempt_listeners = []           # fn(obj) after an attempt (routine runner)
        self.tool_widgets = {}                 # tool name -> widget
        self.views = {}                        # tab widget -> StaffView (to stop it on close)
        start_user = last_user() if last_user() in _users() else None
        set_current_user(start_user)           # settings, results, workspace of this user
        self._apply_user_settings()

        w = self.win = QMainWindow()
        w.setWindowTitle(APP_NAME)
        self._key_filter = _key_filter(self)          # the computer keyboard as a keyboard
        from PySide6.QtWidgets import QApplication as _QApp
        _QApp.instance().installEventFilter(self._key_filter)
        self._close_filter = _CloseFilter(self.save_user_workspace)
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

        from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QSplitter, QLabel as _QL
        # Objects = TWO lists one above the other (owner, 2026-11-07): Material (MIDI, PDF,
        # scores, recordings) and Exercises (every exercise object, routines); own scrolling,
        # the divider can be moved (its position is saved)
        self.mat_list, self.ex_list = QTreeWidget(), QTreeWidget()
        self.split = QSplitter(Qt.Vertical)
        for title, lst in (("Material", self.mat_list), ("Exercises", self.ex_list)):
            lst.setHeaderHidden(True)
            lst.setSelectionMode(QAbstractItemView.ExtendedSelection)
            lst.itemDoubleClicked.connect(lambda it, col: self.open_object(self._item_name(it)))
            lst.currentItemChanged.connect(self._browse)
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
        self.ex_list.setDragEnabled(True)
        self.ex_list.setDragDropMode(QAbstractItemView.DragOnly)
        self.ex_list.setDefaultDropAction(Qt.CopyAction)
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
        self._fill_users(start_user)
        self._user_prev = self.user_box.currentText() or None

        self._build_menus()
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
        m.addSeparator()
        m.addAction(self.dock_objects.toggleViewAction())
        m.addAction(self.dock_tool.toggleViewAction())
        m.addAction(self.dock_log.toggleViewAction())

        for cat in registry.CATEGORIES:
            tools = registry.by_category(cat)
            m = mb.addMenu(cat)
            if not tools:
                a = m.addAction("(no tools yet)")
                a.setEnabled(False)
            subs = {}
            for t in tools:
                target = m
                if t.submenu:
                    if t.submenu not in subs:
                        subs[t.submenu] = m.addMenu(t.submenu)
                    target = subs[t.submenu]
                add(target, t.label + (" (to do)" if t.kind == "planned" else ""),
                    lambda checked=False, n=t.name: self.open_tool(n))

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
        set_current_user(name)
        self._user_prev = name
        self._apply_user_settings()
        self._update_title()
        self.log(f"user: {name}")
        self.load_user_workspace()

    def _apply_user_settings(self):
        """Settings that live outside the dialogs: soundfont, running synths."""
        from ..midi import Midi
        from .. import realtime
        sf2 = settings().get("sf2")
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
        self.win.setWindowTitle(f"{APP_NAME} – {self.user}" if self.user else APP_NAME)

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
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self.win, "New user", "Name:")
        if ok and name.strip():
            self.set_user(name.strip())

    # ---------------------------------------------------------- tools and tabs
    def open_tool(self, name):
        """Open a session tool in a tab (or bring it to front); returns its widget."""
        t = registry.TOOLS[name]
        if t.kind == "planned":                      # menu item of a tool still to write
            self.log(f"{t.label}: not there yet (planned: {t.help})")
            return None
        if t.kind == "transform":
            from .toolpanel import tool_panel
            self.tool_panel = tool_panel(self, t)
            self.dock_tool.setWidget(self.tool_panel)
            self.dock_tool.show()
            return self.tool_panel
        # THE TOOLS PANEL DISAPPEARS WHEN NO LONGER NEEDED (owner, 2026-11-13: the practice
        # diary opened with the "Transpose" panel still there): every tool that opens in a
        # tab (Practice, Analyse, …) closes it; it opens again with the next Generate /
        # Convert tool chosen
        self.dock_tool.hide()
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
        sv = self.views.pop(w, None)
        if sv is not None:
            sv.stop()
        self.tabs.removeTab(i)
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
    def add_object(self, obj, name=None, log=True):
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
        self._refresh_panel()
        return name

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
        else:
            g = shown_grade(obj, user)
            text = name + (f"   – {g:.1f}" if g is not None else
                           "   – n/a" if not getattr(obj, "graded", True) else "")
        it.setText(0, text)
        todo = to_do(obj, user)
        f = it.font(0)
        f.setBold(todo)
        it.setFont(0, f)
        it.setBackground(0, QBrush(QColor("#e6e6e6")) if todo else QBrush())
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
        for n in names:
            it = self._find_item(n)
            if it is not None:
                lst = it.treeWidget()
                lst.setCurrentItem(it, 0, QItemSelectionModel.NoUpdate)
                it.setSelected(True)
                self._active_list = lst
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
        b.setText("Stop")
        from PySide6.QtCore import QTimer
        if self._play_timer is None:
            self._play_timer = QTimer(self.win)
            self._play_timer.setInterval(300)
            self._play_timer.timeout.connect(self._play_watch)
        self._play_timer.start()
        return self

    def _play_watch(self):
        """Play button back to 'Play' when the listened object has finished."""
        sv = getattr(self, "_playing", None)
        if sv is None or not sv.timer.isActive():
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
            lst.clearSelection()
            lst.setCurrentItem(it, 0, QItemSelectionModel.NoUpdate)
            it.setSelected(True)
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
        menu.addSeparator()
        add("Rename…", self.rename_object_dialog, single and it.parent() is None)
        add("Remove", self.remove_selected_object)
        for cat in registry.CATEGORIES:                  # tools that accept the selection
            tools = [t for t in registry.by_category(cat)
                     if t.inputs and any(isinstance(o, tuple(t.inputs)) for o in objs)]
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

    def _browse(self, cur, prev):
        """With the exercise view (left View on an exercise) in front, moving with the
        arrow keys in Objects shows each exercise there (to look for one)."""
        from ..phrase import Phrase
        pv = getattr(self, "_preview", None)
        if cur is None or pv is None or self.tabs.currentWidget() is not pv:
            return
        name = self._item_name(cur)
        try:
            if isinstance(self.get_object(name), Phrase):
                self.view_object(name)
        except KeyError:
            pass

    def _show_preview(self, name, score):
        """One reusable tab 'View: exercise' (updated while browsing the exercises)."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        from ..staffview import StaffView
        pv = getattr(self, "_preview", None)
        if pv is None or self.tabs.indexOf(pv) < 0:
            pv = self._preview = QWidget()
            QVBoxLayout(pv).setContentsMargins(0, 0, 0, 0)
            self.add_tab(pv, "View: exercise")
        old = self.views.pop(pv, None)
        if old is not None:
            old.stop()
            old.win.setParent(None)
            old.win.deleteLater()
        sv = StaffView(score, title=name)
        sv.win.setWindowFlags(Qt.Widget)
        sv.hide_toolbar()
        pv.layout().addWidget(sv.win)
        self.views[pv] = sv
        self.tabs.set_bar(pv, sv.make_bar())
        self.tabs.setTabText(self.tabs.indexOf(pv), f"View: {name}"[:60].replace("&", "&&"))
        self.tabs.setCurrentWidget(pv)
        return sv

    def view_object(self, name=None):
        """Score/Midi/Notes: StaffView in a tab; exercise: the reusable 'View: exercise'
        tab (arrow keys in Objects then browse the exercises); Pdf: its pages."""
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
                self.log(f"{name}: {len(obj)} exercises (open one to view it)")
                return None
            if isinstance(obj, Phrase):
                return self._show_preview(name, obj.to_score())
            from ..notes import Notes
            if isinstance(obj, Midi) and not isinstance(obj, Notes):
                from .midiview import MidiView           # staff + switch to the piano roll
                sv = MidiView(obj, name, app=self)
                sv.obj_name = name
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
        open, or a new one; an exercise in the 'View: exercise' tab; a PDF as the staff of
        its MIDI) and played from the start with the red cursor following the sound.
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
            if isinstance(obj, Phrase):
                sv = self._show_preview(name, obj.to_score())
                sv.midi = obj.to_midi()
            else:
                sv = self._view_for(name)
                if sv is None:
                    if isinstance(obj, Pdf):
                        from ..staffview import StaffView
                        sv = StaffView(self._as_midi(obj), title=name)
                        sv.win.setWindowFlags(Qt.Widget)
                        sv.hide_toolbar()
                        sv.win.bar = sv.make_bar()
                        self.views[sv.win] = sv
                        self.add_tab(sv.win, f"{name} (staff)")
                    else:
                        sv = self.view_object(name)
                    if sv is None:
                        return None
                    sv.obj_name = name
                else:
                    self.tabs.setCurrentWidget(sv.win)
            sv.set_position(0)
            sv.listen()
            self._playing = sv
            self.log(f"playing {name}")
            return sv
        except Exception as e:
            self.log(f"play {name}: {type(e).__name__}: {e}")
            return None

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
        if not names:
            return None
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
        self._refresh_panel()

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
        save_setting("sf2", Midi._default_sf2)
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
            try:
                sv.stop()
            except Exception:
                pass
            self._playing = None
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
