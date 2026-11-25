"""Routine runner (double click on a routine ↻): the list of its exercises with a tick for
the ones done today and their grade; Start does the first one not done today (or the one
selected), every exercise in its own tab, started at once; with Auto-advance the next one
opens after an attempt (Settings > Exercises "Routine: next exercise after", default 10 s);
◀ / ▶ in the bar of the EXERCISE's tab (owner, 2026-11-14: not in the list) move by hand to
the item before / after it, only while the exercise is stopped (disabled during it). When
the routine opens, its first exercise is selected: Start begins from the start. Add… inserts exercises after the selected one
(the exercises selected in Objects, exercise files .mke, or a NEW exercise made with your
last settings, 'new each time'); Up / Down / Remove change the order;
"New each time" (per item) makes drills, interval blocks and pieces of duets new every
day. DRAG AND DROP (owner, 2026-11-08, also for Android): exercises dragged from Objects
(Exercises) or exercise files (.mke / .mkr / .json) dragged from the Finder are inserted where
they are dropped; the items of the list are reordered by dragging them. Holding a drag over
the routine's tab brings it to the front. Logic in tasks.Routine (no Qt)."""

AUTO_S = 10                 # pause after an attempt before the next exercise opens (owner,
                            # 2026-11-13: 10 s, a general option in Settings > Exercises;
                            # it was 7.5 s, 2.5 s before 2026-11-09)


def auto_seconds():
    """Seconds of the routine's auto-advance (settings key 'routine_auto_s')."""
    try:
        from ..progress import settings
        v = float(settings().get("routine_auto_s", AUTO_S))
    except Exception:
        v = AUTO_S
    return max(1.0, v)


def item_tab_title(routine, k, n, width=40):
    """Title of the tab of an exercise done in a routine (owner, 2026-11-19): the ROUTINE's
    name and the position, never the exercise's ("↻ Routine trumpet – 3/7"; a group of
    exercises ▦ its group name), so the tab says that it belongs to a routine. A long
    name is shortened in the middle: the position stays visible."""
    sym = "▦" if type(routine).__name__ == "TaskGroup" else "↻"
    tail = f" – {k + 1}/{n}"
    name = str(routine.title or "Routine")
    room = max(8, width - len(tail) - 2)
    if len(name) > room:
        half = (room - 1) // 2
        name = name[:room - 1 - half] + "…" + name[-half:]
    return f"{sym} {name}{tail}"


def routine_widget(app, routine):
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
                                   QCheckBox, QAbstractItemView)
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    from .bar import action_bar
    from ..tasks import done_today, shown_grade, regenerable, Task

    class RoutineWidget(QWidget):
        def __init__(self):
            super().__init__()
            self.routine = routine
            self.app = app
            self.current = None               # index of the item being done
            self.item_tab = None              # its tab
            self.auto = QCheckBox("Auto-advance")
            self.auto.setChecked(True)
            self.auto.setToolTip("after an attempt the next exercise not done today opens")
            self.bar, self.buttons = action_bar(
                [("Start", self.start, "the first exercise not done today (or the one "
                                       "selected)"),
                 None,
                 ("Add…", self.add_menu, "add exercises after the selected one"),
                 ("Up", lambda: self.move(-1), "move the selected exercise up"),
                 ("Down", lambda: self.move(1), "move the selected exercise down"),
                 ("Remove", self.remove, "remove the selected exercise from the routine")],
                right=self.auto)
            lay = QVBoxLayout(self)
            self.head = QLabel("")
            f = QFont()
            f.setPointSize(15)
            self.head.setFont(f)
            lay.addWidget(self.head)
            self.list = _drop_list_class()(self)
            self.list.setHeaderLabels(["Today", "Grade", "Exercise", "New each time"])
            self.list.setRootIsDecorated(False)
            self.list.setSelectionMode(QAbstractItemView.SingleSelection)
            self.list.itemDoubleClicked.connect(lambda it, c: self.run(self._row(it)))
            self.list.itemChanged.connect(self._flag_changed)
            lay.addWidget(self.list, 1)
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.auto_next)
            self.watch = QTimer(self)                 # ◀ ▶ only while the exercise is stopped
            self.watch.setInterval(300)
            self.watch.timeout.connect(self._update_moves)
            self.watch.start()
            app._attempt_listeners.append(self.on_attempt)
            self._moves = None                        # ◀ ▶ in the bar of the item's tab
            self.refresh_routine()
            if self.list.topLevelItemCount():         # owner, 2026-11-14: Start = from the
                self.list.setCurrentItem(self.list.topLevelItem(0))   # first exercise

        # ------------------------------------------------------ list
        def _row(self, it):
            return self.list.indexOfTopLevelItem(it)

        def refresh_routine(self):
            user = app.user
            sel = self.list.currentIndex().row() if self.list.currentItem() else None
            self.list.blockSignals(True)
            self.list.clear()
            for k, it in enumerate(self.routine.items):
                o = it["obj"]
                g = shown_grade(o, user)
                kind = o.label if hasattr(o, "label") and not hasattr(o, "purpose") else (
                    "Read & play" if o.purpose == "reading" else "Listen & repeat")
                row = QTreeWidgetItem(["✓" if done_today(o, user) else "",
                                       "n/a" if not getattr(o, "graded", True) else
                                       "" if g is None else f"{g:.1f}",
                                       f"{k + 1}. " + (o.title if o.title.startswith(kind)
                                                       else f"{kind}: {o.title}"), ""])
                if regenerable(o):
                    row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
                    row.setCheckState(3, Qt.Checked if it.get("fresh") else Qt.Unchecked)
                if k == self.current:
                    fb = row.font(2)
                    fb.setBold(True)
                    row.setFont(2, fb)
                self.list.addTopLevelItem(row)
            for c in range(3):
                self.list.resizeColumnToContents(c)
            self.list.blockSignals(False)
            if sel is not None and 0 <= sel < self.list.topLevelItemCount():
                self.list.setCurrentItem(self.list.topLevelItem(sel))
            self.head.setText(f"<b>{self.routine.title}</b> – {user or 'no user'}: "
                              + self.routine.summary(user))

        def _flag_changed(self, row, col):
            if col == 3:
                k = self._row(row)
                self.routine.set_fresh(k, row.checkState(3) == Qt.Checked)

        def _selected(self):
            it = self.list.currentItem()
            return self._row(it) if it is not None and it.isSelected() else None

        def move(self, d):
            k = self._selected()
            if k is None or not 0 <= k + d < len(self.routine.items):
                return
            self.routine.move(k, k + d)
            if self.current in (k, k + d):
                self.current = k + d if self.current == k else k
            self.refresh_routine()
            self.list.setCurrentItem(self.list.topLevelItem(k + d))

        # ------------------------------------------------------ add
        def add_menu(self):
            """Add…: the exercises selected in Objects, exercise files, or a new exercise."""
            from PySide6.QtWidgets import QMenu
            from PySide6.QtGui import QCursor
            from ..tasks import NEW_KINDS
            m = QMenu(self)
            sel = self._selected_exercises()
            a = m.addAction(f"Exercises selected in Objects ({len(sel)})")
            a.setEnabled(bool(sel))
            a.triggered.connect(lambda: self.add_objects(sel))
            m.addAction("Exercise files (.mke)…").triggered.connect(self.add_files)
            m.addSeparator()
            sub = m.addMenu("New exercise (new each time)")
            for kind, label in NEW_KINDS:
                sub.addAction(label).triggered.connect(lambda checked=False, k=kind: self.add_new(k))
            b = self.buttons.get("Add…")
            m.exec(b.mapToGlobal(b.rect().bottomLeft()) if b is not None else QCursor.pos())
            return m

        def _at(self):
            k = self._selected()
            return None if k is None else k + 1

        def _selected_exercises(self):
            from ..phrase import Phrase, ExerciseSet
            from ..tasks import Task, Routine
            from ..playover import PlayOver
            return [o for o in app.selected_objects((Phrase, ExerciseSet, Task, Routine,
                                                     PlayOver))
                    if o is not self.routine]

        def _added(self, n, what):
            app.log(f"routine {self.routine.title}: {n} exercise{'s' if n != 1 else ''} "
                    f"added ({what})")
            app.refresh_exercises()

        def add_objects(self, objs, at=-1):
            at, n = (self._at() if at == -1 else at), 0
            for o in objs:
                n += self.routine.add(o, False, None if at is None else at + n)
            self._added(n, "from Objects")
            return n

        def add_files(self, paths=None, at=-1):
            from PySide6.QtWidgets import QFileDialog
            from ..progress import folder
            from ..phrase import read_exercise_file, exercises_from_dict
            from ..tasks import from_file_dict
            if paths is None:
                paths, _ = QFileDialog.getOpenFileNames(
                    app.win, "Add exercises", folder("exercises"),
                    "MusiKitE exercises (*.mke *.mkr *.json)")
            at, n = (self._at() if at == -1 else at), 0
            for p in paths or []:
                try:
                    d = read_exercise_file(p)
                    o = exercises_from_dict(d) if (d.get("format") == "musikite-exercises"
                                                   or "phrases" in d) else from_file_dict(d)
                    n += self.routine.add(o, False, None if at is None else at + n)
                except Exception as e:
                    app.log(f"add {p}: {type(e).__name__}: {e}")
            self._added(n, "from files")
            return n

        def add_new(self, kind):
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt as _Qt
            QApplication.setOverrideCursor(_Qt.WaitCursor)
            try:
                n = self.routine.add_new(kind, self._at())
            except Exception as e:
                app.log(f"routine: new {kind}: {type(e).__name__}: {e}")
                return 0
            finally:
                QApplication.restoreOverrideCursor()
            self._added(n, f"new {kind}")
            return n

        # ------------------------------------------------------ drag and drop
        def drop_row(self, pos):
            """Row where a drop at `pos` (list viewport) inserts: before the item under the
            pointer (after it in its lower half); None = at the end."""
            it = self.list.itemAt(pos)
            if it is None:
                return None
            k = self._row(it)
            r = self.list.visualItemRect(it)
            return k + 1 if pos.y() > r.center().y() else k

        def dropped(self, event):
            """A drop on the list: own items = move; Objects (Exercises) = add the selected
            exercises; files = add them. Returns the number of items added / moved."""
            from PySide6.QtCore import Qt as _Qt
            at = self.drop_row(event.position().toPoint())
            src = event.source()
            if src is self.list:
                k = self._selected()
                if k is None:
                    return 0
                j = len(self.routine.items) - 1 if at is None else (at - 1 if at > k else at)
                if j == k:
                    return 0
                self.routine.move(k, j)
                if self.current is not None:
                    order = list(range(len(self.routine.items)))
                    order.insert(j, order.pop(k))
                    self.current = order.index(self.current)
                self.refresh_routine()
                self.list.setCurrentItem(self.list.topLevelItem(j))
                app.refresh_exercises()
                return 1
            if src is getattr(app, "ex_list", None):
                return self.add_objects(self._selected_exercises(), at)
            md = event.mimeData()
            if md.hasUrls():
                paths = [u.toLocalFile() for u in md.urls()
                         if u.toLocalFile().lower().endswith((".mke", ".mkr", ".json"))]
                return self.add_files(paths, at) if paths else 0
            return 0

        def remove(self):
            k = self._selected()
            if k is None:
                return
            if k == self.current:
                self._close_item_tab()
                self.current = None
            elif self.current is not None and k < self.current:
                self.current -= 1
            self.routine.remove(k)
            app.refresh_exercises()

        # ------------------------------------------------------ doing it
        def start(self):
            k = self._selected()
            if k is None:
                k = self.routine.next_to_do(app.user)
            if k is None:
                return self._all_done()
            return self.run(k)

        def auto_next(self):
            """Auto-advance: the next exercise not done today (not while one is going on,
            e.g. Again pressed meanwhile)."""
            self.timer.stop()
            if self._busy():
                return None
            k = self.routine.next_to_do(app.user, after=-1 if self.current is None
                                        else self.current)
            if k is None:
                return self._all_done()
            return self.run(k)

        def next(self):
            """Next ▶: the item after the current one (none open: Start)."""
            self.timer.stop()
            if self._busy():
                return None
            if self.current is None:
                return self.start()
            if self.current + 1 >= len(self.routine.items):
                app.log(f"routine {self.routine.title}: this is the last exercise")
                return None
            return self.run(self.current + 1)

        def previous(self):
            """◀ Previous: the item before the current one."""
            self.timer.stop()
            if self._busy() or self.current is None:
                return None
            if self.current <= 0:
                app.log(f"routine {self.routine.title}: this is the first exercise")
                return None
            return self.run(self.current - 1)

        def _busy(self):
            w = self.item_tab
            try:
                return bool(w is not None and hasattr(w, "busy") and w.busy())
            except RuntimeError:                      # its tab was closed meanwhile
                return False

        def _add_moves(self, w):
            """◀ ▶ at the start of the bar of the exercise's tab (owner, 2026-11-14): the
            exercise before / after in the routine; deferred, the tab is closed by them."""
            from PySide6.QtWidgets import QPushButton
            self._moves = None
            bar = getattr(w, "bar", None) if w is not None else None
            lay = bar.layout() if bar is not None else None
            if lay is None:
                return
            prev_b, next_b = QPushButton("◀"), QPushButton("▶")
            prev_b.setToolTip(f"routine {self.routine.title}: the exercise before (when "
                              "the exercise is stopped)")
            next_b.setToolTip(f"routine {self.routine.title}: the exercise after (when "
                              "the exercise is stopped)")
            prev_b.clicked.connect(lambda *a: QTimer.singleShot(0, self.previous))
            next_b.clicked.connect(lambda *a: QTimer.singleShot(0, self.next))
            lay.insertWidget(0, prev_b)
            lay.insertWidget(1, next_b)
            self._moves = (prev_b, next_b)
            self._update_moves()

        def _update_moves(self):
            if self._moves is None:
                return
            free = not self._busy()
            try:
                prev_b, next_b = self._moves
                prev_b.setEnabled(free and self.current is not None and self.current > 0)
                next_b.setEnabled(free and self.current is not None
                                  and self.current + 1 < len(self.routine.items))
            except RuntimeError:                      # the tab was closed meanwhile
                self._moves = None

        def run(self, k):
            """Item k in its own tab, started at once ('new each time': made new first,
            once a day)."""
            self.timer.stop()
            self._close_item_tab()
            try:
                obj = self.routine.prepare(k, app.user)
            except Exception as e:
                app.log(f"routine {self.routine.title}: item {k + 1}: {type(e).__name__}: {e}")
                return None
            self.current = k
            n = len(self.routine.items)
            w = app.practise(obj, item_tab_title(self.routine, k, n),
                             key=f"routine {self.routine.uid} item")
            self.item_tab = w
            self._add_moves(w)
            self.refresh_routine()
            app.log(f"routine {self.routine.title}: {k + 1}/{n} {obj.title}")
            if w is not None and hasattr(w, "start"):
                QTimer.singleShot(400, w.start)
            return w

        def on_attempt(self, obj):
            """An attempt on an exercise: the list is redrawn; the current item done ->
            the next one after a pause (Auto-advance)."""
            self.refresh_routine()
            if self.current is None or self.current >= len(self.routine.items):
                return
            if getattr(self, "_closing", False):     # a stopped exercise while leaving it
                return
            if self.routine.items[self.current]["obj"] is obj and self.auto.isChecked():
                self.timer.start(int(auto_seconds() * 1000))

        def _close_item_tab(self):
            w = self.item_tab
            self.item_tab = None
            self._moves = None
            if w is not None:
                i = app.tabs.indexOf(w)
                if i >= 0:
                    self._closing = True
                    try:
                        app.close_tab(i)
                    finally:
                        self._closing = False

        def _all_done(self):
            self._close_item_tab()
            self.current = None
            self.refresh_routine()
            app.tabs.setCurrentWidget(self)
            msg = f"{self.routine.title}: everything done today – " + \
                self.routine.summary(app.user)
            app.log(msg)
            self.head.setText(f"<b>{msg}</b>")
            return None

        def user_changed(self, name):
            self.timer.stop()
            self.current = None

        def closing(self):
            self.timer.stop()
            self.watch.stop()
            try:
                app._attempt_listeners.remove(self.on_attempt)
            except ValueError:
                pass

    return RoutineWidget()


def _drop_list_class():
    """The runner's list: accepts exercises from Objects, files, and its own items."""
    from PySide6.QtWidgets import QTreeWidget, QAbstractItemView

    class DropList(QTreeWidget):
        def __init__(self, owner):
            super().__init__()
            self.owner = owner
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.viewport().setAcceptDrops(True)
            self.setDropIndicatorShown(True)
            self.setDragDropMode(QAbstractItemView.DragDrop)

        def _ok(self, e):
            src = e.source()
            if src is self or src is getattr(self.owner_app(), "ex_list", None):
                return True
            md = e.mimeData()
            return md.hasUrls() and any(u.toLocalFile().lower().endswith(
                (".mke", ".mkr", ".json")) for u in md.urls())

        def owner_app(self):
            return getattr(self.owner, "app", None)

        def dragEnterEvent(self, e):
            if self._ok(e):
                e.acceptProposedAction()
            else:
                e.ignore()

        def dragMoveEvent(self, e):
            if self._ok(e):
                super().dragMoveEvent(e)          # draws the drop indicator
                e.acceptProposedAction()
            else:
                e.ignore()

        def dropEvent(self, e):
            if not self._ok(e):
                return e.ignore()
            self.owner.dropped(e)                 # the routine changes, then the list is redrawn
            e.setDropAction(e.proposedAction() if e.source() is not self else
                            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.IgnoreAction)
            e.accept()

    return DropList
