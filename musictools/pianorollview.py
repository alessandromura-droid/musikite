"""
PianoRollView: a MIDI shown and edited as a piano roll, Ableton style (Qt, PySide6).
The editing logic is in pianoroll.Roll (pure Python, for Android); this file only
draws and turns mouse/keys into Roll calls.

    v = PianoRollView(m).show()     # m: Midi object (edited IN PLACE) or a pianoroll.Roll
    v.set_position(8)               # red cursor at beat 8 (quarters)
    v.listen(); v.stop()            # play from the cursor, the cursor follows the sound
    v.quantize_dialog()             # Quantize… (grid, strength, note ends, which notes)

Window: time left to right (bar numbers on top), pitch bottom to top (keyboard on the
left, C4 = middle C), one colour per track; the notes of the other tracks are shown
faded, the track chosen in "Track" is the one edited.
Tools (row on top):
  Hand    click a note = select (Shift: add/remove), drag = move (time on the grid,
          pitch in semitones; Alt: free time), drag its right edge = length,
          drag on empty space = select a rectangle, double click: empty = new note,
          on a note = delete it
  Pencil  click on empty space = new note (one grid step long, drag right = longer);
          on a note it works as the hand
  Eraser  click / drag over notes = delete them
  Grid (editing), Velocity (new notes; changes the selected ones), Undo, Redo,
  Quantize…, Zoom.
Keys: Delete/Backspace, Ctrl+Z / Ctrl+Shift+Z (Cmd on the Mac), Ctrl+A, arrows (up/down
a semitone, Shift an octave; left/right a grid step), Ctrl+Q quantize.
Mouse wheel: scroll pitch; Shift+wheel: scroll time; Ctrl/Cmd+wheel: zoom time;
Alt+wheel: zoom pitch. Click on the bar numbers = cursor there.
"""
import time

from .pianoroll import Roll, GRIDS, EDIT_GRIDS, grid_steps, snap, snap_floor, MIN_DUR
from .staffview import _app, _enable_notebook_loop

KEY_W = 48                      # keyboard width (px)
RULER_H = 20                    # bar numbers height (px)
TRACK_COLORS = ("#2f7de1", "#e0712f", "#2fa84f", "#c23b8e", "#8a5ad6", "#c9a227",
                "#1aa3a3", "#d1453b")
PREVIEW_CH = 14                 # synth channel of the note preview (keyboard: 15)


class PianoRollView:
    last_quantize = dict(grid="1/16", strength=100, ends=False)   # remembered in the session

    def __init__(self, obj, title=None, on_change=None):
        """obj: Midi object (its notes are replaced at every edit) or a Roll.
        on_change(roll): called after every edit."""
        from .midi import Midi
        self.midi = obj if isinstance(obj, Midi) else None
        self.roll = obj if isinstance(obj, Roll) else Roll.from_midi(obj)
        self.title = title or self.roll.title or getattr(obj, "title", None) or "Piano roll"
        self.on_change = on_change
        self.position = 0.0
        self.track = 0
        self.selection = []                     # notes (lists) of the current track
        self.player = None
        self.bpm = None
        self.new_program = 0                    # GM program of a track drawn from nothing
        _app()
        self._build_window()

    # ---------------------------------------------------------- window
    def _build_window(self):
        from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                       QGridLayout, QScrollBar, QToolButton, QButtonGroup,
                                       QComboBox, QSpinBox, QLabel, QToolBar)
        from PySide6.QtGui import QAction, QFont
        from PySide6.QtCore import Qt, QTimer
        self.win = QMainWindow()
        self.win.setWindowTitle(self.title)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        row = QHBoxLayout()
        self.tool_buttons = {}
        grp = QButtonGroup(central)
        grp.setExclusive(True)
        for name, tip in (("Hand", "select, move, change length (drag the right edge)"),
                          ("Pencil", "draw notes (one grid step; drag right = longer)"),
                          ("Eraser", "delete the notes clicked / dragged over")):
            b = QToolButton()
            b.setText(name)
            b.setToolTip(tip)
            b.setCheckable(True)
            grp.addButton(b)
            row.addWidget(b)
            self.tool_buttons[name] = b
            b.toggled.connect(lambda on, n=name: on and self.set_tool(n))
        self.tool = "Hand"
        self.tool_buttons["Hand"].setChecked(True)
        row.addSpacing(12)
        row.addWidget(QLabel("Grid:"))
        self.grid = QComboBox()
        self.grid.addItems(EDIT_GRIDS)
        self.grid.setCurrentText("1/16")
        self.grid.setToolTip("grid of the editing (Alt while dragging: free)")
        self.grid.currentIndexChanged.connect(lambda *_: self.canvas.update())
        row.addWidget(self.grid)
        row.addWidget(QLabel("Track:"))
        self.track_box = QComboBox()
        self.track_box.setToolTip("the track edited (the others are shown faded)")
        self.track_box.currentIndexChanged.connect(self._track_changed)
        row.addWidget(self.track_box)
        row.addWidget(QLabel("Velocity:"))
        self.vel = QSpinBox()
        self.vel.setRange(1, 127)
        self.vel.setValue(90)
        self.vel.setToolTip("velocity of new notes; with notes selected it changes them")
        self.vel.editingFinished.connect(self._velocity_changed)
        row.addWidget(self.vel)
        row.addSpacing(12)
        for text, fn, tip in (("Undo", self.undo, "Ctrl+Z"), ("Redo", self.redo, "Ctrl+Shift+Z"),
                              ("Delete", self.delete_selection, "delete the selected notes"),
                              ("Quantize…", self.quantize_dialog,
                               "move the notes onto a grid (Ctrl+Q)"),
                              ("−", lambda: self.zoom(0.8), "zoom out (Ctrl+wheel)"),
                              ("+", lambda: self.zoom(1.25), "zoom in (Ctrl+wheel)")):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda checked=False, fn=fn: fn())
            row.addWidget(b)
            self.tool_buttons[text] = b
        row.addStretch(1)
        lay.addLayout(row)
        grid = QGridLayout()
        grid.setSpacing(0)
        self.canvas = _canvas_class()(self)
        self.hbar = QScrollBar(Qt.Horizontal)
        self.vbar = QScrollBar(Qt.Vertical)
        self.hbar.valueChanged.connect(lambda *_: self.canvas.update())
        self.vbar.valueChanged.connect(lambda *_: self.canvas.update())
        grid.addWidget(self.canvas, 0, 0)
        grid.addWidget(self.vbar, 0, 1)
        grid.addWidget(self.hbar, 1, 0)
        lay.addLayout(grid, 1)
        self.win.setCentralWidget(central)
        tb = self.toolbar = QToolBar()
        self.win.addToolBar(tb)
        for text, fn in self.bar_actions():
            a = QAction(text, self.win)
            a.triggered.connect(fn)
            tb.addAction(a)
        self._bar = None
        self.status = QLabel("")
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)
        self.status.setFont(mono)
        self.win.statusBar().addWidget(self.status, 1)
        self.timer = QTimer()
        self.timer.setInterval(25)
        self.timer.timeout.connect(self._tick)
        self.win.resize(1200, 600)
        self.px_q = 40.0                        # pixels per quarter
        self.row_h = 10.0                       # pixels per semitone
        self.refresh_tracks()
        self._fit_pitch()

    def bar_actions(self, play=True):
        """(text, function) of the toolbar; play=False in the main window (owner's rule:
        Play only in the Objects panel)."""
        acts = (("Play", self.listen),) if play else ()
        acts += (("Stop", self.stop),)
        if play:
            acts += (("Rewind", lambda: self.set_position(0)),)
        return acts + (("Zoom +", lambda: self.zoom(1.25)), ("Zoom -", lambda: self.zoom(0.8)))

    def hide_toolbar(self):
        self.toolbar.hide()
        self.win.statusBar().hide()
        return self

    def make_bar(self):
        from .gui.bar import action_bar
        if self._bar is None:
            self._bar, _ = action_bar([(t, fn) for t, fn in self.bar_actions(play=False)],
                                      right=self.status)
            self.win.statusBar().hide()
        return self._bar

    def show(self):
        _enable_notebook_loop()
        self.win.show()
        self.win.raise_()
        return self

    def run(self):
        self.win.show()
        _app().exec()
        return self

    def close(self):
        self.stop()
        self.win.close()

    def __repr__(self):
        return f"PianoRollView('{self.title}', {self.roll!r})"

    # ---------------------------------------------------------- state
    def set_roll(self, roll):
        """Show another Roll (e.g. the recording after a new take)."""
        self.roll = roll
        self.selection = []
        self.refresh_tracks()
        self._fit_pitch()
        return self

    def refresh_tracks(self):
        keep = self.track
        self.track_box.blockSignals(True)
        self.track_box.clear()
        for k, t in enumerate(self.roll.tracks):
            self.track_box.addItem(f"{k + 1} {t['name']}")
        if not self.roll.tracks:
            self.track_box.addItem("(new track)")
        self.track = max(0, min(keep, len(self.roll.tracks) - 1))
        self.track_box.setCurrentIndex(self.track)
        self.track_box.blockSignals(False)
        self._update_scroll()
        self.canvas.update()

    def set_track(self, k):
        self.track_box.setCurrentIndex(int(k))
        return self

    def _track_changed(self, k):
        self.track = max(0, k)
        self.selection = []
        self.canvas.update()

    def set_tool(self, name):
        self.tool = name
        if not self.tool_buttons[name].isChecked():
            self.tool_buttons[name].setChecked(True)
        if getattr(self, "canvas", None) is not None:
            self.canvas.update_cursor(None)
        return self

    def grid_step(self):
        s = grid_steps(self.grid.currentText())
        return s[0] if s else 0.0

    def _ensure_track(self):
        if not self.roll.tracks:
            self.roll.add_track(program=self.new_program)
            self.refresh_tracks()
        return self.track

    def changed(self, what=""):
        """After every edit: the Midi object gets the new notes, the owner is told."""
        self.roll.sort()
        if self.midi is not None:
            self.roll.apply_to(self.midi)
        self._update_scroll()
        self.canvas.update()
        n = self.roll.n_notes()
        self.status.setText(f"{what}  ({n} notes)  " if what else f"{n} notes  ")
        if self.on_change is not None:
            try:
                self.on_change(self.roll)
            except Exception:
                pass

    # ---------------------------------------------------------- geometry
    def content_w(self):
        return (self.roll.length_q() + 2 * self.roll.bar_q) * self.px_q

    def content_h(self):
        return 128 * self.row_h

    def x_of(self, q):
        return KEY_W + q * self.px_q - self.hbar.value()

    def y_of(self, p):
        return RULER_H + (127 - p) * self.row_h - self.vbar.value()

    def q_of(self, x):
        return (x - KEY_W + self.hbar.value()) / self.px_q

    def p_of(self, y):
        import math
        return 127 - int(math.floor((y - RULER_H + self.vbar.value()) / self.row_h))

    def _update_scroll(self):
        w = max(1, self.canvas.width() - KEY_W)
        h = max(1, self.canvas.height() - RULER_H)
        self.hbar.setRange(0, max(0, int(self.content_w() - w)))
        self.hbar.setPageStep(w)
        self.hbar.setSingleStep(int(self.px_q / 2) or 1)
        self.vbar.setRange(0, max(0, int(self.content_h() - h)))
        self.vbar.setPageStep(h)
        self.vbar.setSingleStep(int(self.row_h) or 1)

    def _fit_pitch(self):
        """Scroll so that the notes (or C4..C5) are in the middle."""
        lo, hi = self.roll.pitch_range()
        mid = (lo + hi) / 2.0
        h = max(1, self.canvas.height() - RULER_H)
        self._update_scroll()
        self.vbar.setValue(int((127 - mid) * self.row_h - h / 2))

    def zoom(self, f, anchor_x=None, vertical=False):
        if vertical:
            self.row_h = max(4.0, min(30.0, self.row_h * f))
            self._update_scroll()
        else:
            ax = anchor_x if anchor_x is not None else KEY_W
            q = self.q_of(ax)
            self.px_q = max(4.0, min(400.0, self.px_q * f))
            self._update_scroll()
            self.hbar.setValue(int(q * self.px_q - (ax - KEY_W)))
        self.canvas.update()
        return self

    # ---------------------------------------------------------- edit actions
    def undo(self):
        if self.roll.undo():
            self.selection = []
            self.refresh_tracks()
            self.changed("undo")
        return self

    def redo(self):
        if self.roll.redo():
            self.selection = []
            self.refresh_tracks()
            self.changed("redo")
        return self

    def delete_selection(self):
        if self.selection and self.roll.tracks:
            k = self.roll.remove(self.track, self.selection)
            self.selection = []
            self.changed(f"{k} deleted")
        return self

    def select_all(self):
        if self.roll.tracks:
            self.selection = list(self.roll.tracks[self.track]["notes"])
            self.canvas.update()
        return self

    def nudge(self, dq=0.0, dp=0):
        if self.selection:
            self.roll.move(self.track, self.selection, dq, dp)
            self.preview(self.selection[0][2])
            self.changed("moved")
        return self

    def _velocity_changed(self):
        if self.selection:
            self.roll.set_velocity(self.track, self.selection, self.vel.value())
            self.changed(f"velocity {self.vel.value()}")

    def quantize_dialog(self, track=None):
        """Quantize… dialog: the result is shown at once while the options change;
        OK keeps it (Undo takes it back), Cancel restores the notes."""
        return _quantize_dialog(self, track)

    # ---------------------------------------------------------- sound
    def preview(self, pitch):
        """Short note with the instrument of the track (when a note is drawn / moved)."""
        try:
            from .realtime import get_player
            from .midi import Midi
            if Midi._default_sf2 is None or not self.roll.tracks:
                return
            t = self.roll.tracks[self.track]
            p = get_player(Midi._default_sf2)
            ch = 9 if t["is_drum"] else PREVIEW_CH
            if not t["is_drum"] and p._programs.get(ch) != t["program"]:
                p.fs.program_select(ch, p.sfid, 0, int(t["program"]))
                p._programs[ch] = int(t["program"])
            p.fs.noteon(ch, int(pitch), 90)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(250, lambda: p.fs.noteoff(ch, int(pitch)))
        except Exception:
            pass

    # ---------------------------------------------------------- play (real time)
    def listen(self):
        """Play from the cursor (no count-in, no clicks); the cursor follows the sound."""
        return self.play()

    def play(self, start=None, sf2=None):
        from .midi import Midi
        from .realtime import get_player, midi_events
        self.stop()
        sf2 = sf2 or Midi._default_sf2
        if sf2 is None:
            raise RuntimeError("no soundfont: choose one in Settings > Soundfont")
        start = self.position if start is None else float(start)
        self._pm = pm = self.roll.to_pm()
        self._start_s = self.roll.q_to_s(start, pm)
        self._end_s = pm.get_end_time()
        self.bpm = self.roll.bpm
        self.player = get_player(sf2)
        self.player.play(midi_events(pm, start=self._start_s))
        self._t0 = time.perf_counter()
        self.timer.start()
        return self

    def stop(self):
        if getattr(self, "timer", None) is not None:
            self.timer.stop()
        if self.player is not None:
            self.player.stop()
        return self

    def _tick(self):
        t = self._start_s + max(0.0, self.player.elapsed())
        if t >= self._end_s:
            self.set_position(self.roll.s_to_q(self._end_s, self._pm))
            self.stop()
            return
        self.set_position(self.roll.s_to_q(t, self._pm), follow=True)

    def set_position(self, beat, follow=True):
        """Red cursor at a beat (quarters from the start); the view follows it."""
        self.position = max(0.0, float(beat))
        if follow:
            x = self.x_of(self.position)
            w = self.canvas.width()
            if x < KEY_W or x > w - 40:
                self.hbar.setValue(int(self.position * self.px_q - 0.15 * (w - KEY_W)))
        bq = self.roll.bar_q
        self.status.setText(f"beat {self.position:7.2f}   bar {int(self.position // bq) + 1:4d}")
        self.canvas.update()
        return self


# ---------------------------------------------------------------- canvas
def _canvas_class():
    from PySide6.QtWidgets import QWidget, QMenu
    from PySide6.QtGui import QPainter, QColor, QPen, QFont, QCursor
    from PySide6.QtCore import Qt, QRectF
    from .theory import note_name

    BLACK = {1, 3, 6, 8, 10}

    class Canvas(QWidget):
        def __init__(self, v):
            super().__init__()
            self.v = v
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.StrongFocus)
            self.setMinimumSize(200, 120)
            self.mode = None
            self.band = None

        # -------------------------------------------------- paint
        def resizeEvent(self, e):
            self.v._update_scroll()
            super().resizeEvent(e)

        def paintEvent(self, e):
            v, r = self.v, self.v.roll
            p = QPainter(self)
            W, H = self.width(), self.height()
            p.fillRect(0, 0, W, H, QColor("#f7f7f9"))
            p.setClipRect(KEY_W, RULER_H, W - KEY_W, H - RULER_H)
            # rows
            top = max(0, v.p_of(H))
            bot = min(127, v.p_of(RULER_H))
            for pitch in range(top, bot + 1):
                y = v.y_of(pitch)
                if pitch % 12 in BLACK:
                    p.fillRect(QRectF(KEY_W, y, W, v.row_h), QColor("#e6e6ec"))
                if pitch % 12 == 0:
                    p.setPen(QColor("#b8b8c4"))
                    p.drawLine(KEY_W, int(y + v.row_h), W, int(y + v.row_h))
            # vertical lines: grid, beats, bars
            q0, q1 = max(0.0, v.q_of(KEY_W)), v.q_of(W)
            step = v.grid_step()
            if step and step * v.px_q >= 5:
                p.setPen(QColor("#e2e2ea"))
                k = int(q0 / step)
                while k * step <= q1:
                    x = v.x_of(k * step)
                    p.drawLine(int(x), RULER_H, int(x), H)
                    k += 1
            bq, beat = r.bar_q, r.beat_q
            k = int(q0 / beat)
            while k * beat <= q1:
                q = k * beat
                on_bar = abs(q / bq - round(q / bq)) < 1e-6
                p.setPen(QPen(QColor("#6b6b78" if on_bar else "#c4c4ce"), 1.5 if on_bar else 1))
                x = v.x_of(q)
                p.drawLine(int(x), RULER_H, int(x), H)
                k += 1
            # notes: the other tracks faded, the current one on top
            order = [k for k in range(len(r.tracks)) if k != v.track]
            if v.track < len(r.tracks):
                order.append(v.track)
            sel = {id(n) for n in v.selection}
            font = QFont()
            font.setPointSizeF(max(6.0, min(9.0, v.row_h * 0.75)))
            p.setFont(font)
            for k in order:
                cur = k == v.track
                base = QColor(TRACK_COLORS[k % len(TRACK_COLORS)])
                for n in r.tracks[k]["notes"]:
                    s, d, pitch, vel = n
                    if s > q1 or s + d < q0 or pitch < top or pitch > bot:
                        continue
                    rect = QRectF(v.x_of(s), v.y_of(pitch) + 1, max(2.0, d * v.px_q - 1),
                                  v.row_h - 2)
                    c = QColor(base)
                    if not cur:
                        c.setAlpha(70)
                    else:
                        c.setAlpha(110 + int(145 * vel / 127))
                    if id(n) in sel:
                        c = QColor("#ff9f1a")
                    p.fillRect(rect, c)
                    p.setPen(QPen(QColor("#202020") if id(n) in sel else c.darker(150),
                                  1.6 if id(n) in sel else 1))
                    p.drawRect(rect)
                    if cur and rect.width() > 26 and v.row_h >= 9:
                        p.setPen(QColor("white"))
                        p.drawText(rect.adjusted(3, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft,
                                   note_name(pitch))
            # rubber band
            if self.band is not None:
                (xa, ya), (xb, yb) = self.band
                p.setPen(QPen(QColor("#333"), 1, Qt.DashLine))
                p.fillRect(QRectF(min(xa, xb), min(ya, yb), abs(xb - xa), abs(yb - ya)),
                           QColor(255, 159, 26, 40))
                p.drawRect(QRectF(min(xa, xb), min(ya, yb), abs(xb - xa), abs(yb - ya)))
            # cursor
            x = v.x_of(v.position)
            p.setPen(QPen(QColor(220, 0, 0), 2, Qt.DashLine))
            p.drawLine(int(x), RULER_H, int(x), H)
            p.setClipping(False)
            # ruler (bar numbers)
            p.fillRect(0, 0, W, RULER_H, QColor("#dcdce4"))
            p.setPen(QColor("#303038"))
            k = int(q0 / bq)
            while k * bq <= q1:
                x = v.x_of(k * bq)
                if x >= KEY_W:
                    p.drawLine(int(x), RULER_H - 6, int(x), RULER_H)
                    p.drawText(int(x) + 3, RULER_H - 6, str(k + 1))
                k += 1
            if KEY_W <= v.x_of(v.position) <= W:
                xp = v.x_of(v.position)
                p.setBrush(QColor(220, 0, 0))
                p.setPen(Qt.NoPen)
                from PySide6.QtGui import QPolygonF
                from PySide6.QtCore import QPointF
                p.drawPolygon(QPolygonF([QPointF(xp - 5, RULER_H - 8), QPointF(xp + 5, RULER_H - 8),
                                         QPointF(xp, RULER_H)]))
            # keyboard
            p.setClipRect(0, RULER_H, KEY_W, H - RULER_H)
            for pitch in range(top, bot + 1):
                y = v.y_of(pitch)
                black = pitch % 12 in BLACK
                p.fillRect(QRectF(0, y, KEY_W, v.row_h), QColor("#2a2a2e" if black else "white"))
                p.setPen(QColor("#9a9aa4"))
                p.drawLine(0, int(y + v.row_h), KEY_W, int(y + v.row_h))
                if pitch % 12 == 0 and v.row_h >= 7:
                    p.setPen(QColor("#303038"))
                    p.drawText(QRectF(2, y, KEY_W - 4, v.row_h), Qt.AlignVCenter | Qt.AlignRight,
                               f"C{pitch // 12 - 1}")
            p.setClipping(False)
            p.fillRect(0, 0, KEY_W, RULER_H, QColor("#c8c8d2"))
            p.setPen(QColor("#9a9aa4"))
            p.drawLine(KEY_W, 0, KEY_W, H)
            p.end()

        # -------------------------------------------------- mouse
        def _at(self, pos):
            return self.v.q_of(pos.x()), self.v.p_of(pos.y())

        def _hit(self, pos):
            v = self.v
            if not v.roll.tracks:
                return None
            q, pitch = self._at(pos)
            return v.roll.hit(v.track, q, pitch)

        def _near_end(self, n, pos):
            return n is not None and abs(self.v.x_of(n[0] + n[1]) - pos.x()) <= 6

        def update_cursor(self, pos):
            v = self.v
            if pos is None or pos.x() < KEY_W or pos.y() < RULER_H:
                self.setCursor(QCursor(Qt.ArrowCursor))
                return
            n = self._hit(pos)
            if v.tool == "Eraser":
                self.setCursor(QCursor(Qt.PointingHandCursor))
            elif self._near_end(n, pos):
                self.setCursor(QCursor(Qt.SizeHorCursor))
            elif n is not None:
                self.setCursor(QCursor(Qt.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CrossCursor if v.tool == "Pencil" else Qt.ArrowCursor))

        def _start_drag(self, mode, n, pos):
            v = self.v
            q, pitch = self._at(pos)
            self.mode = mode
            self.prim = n
            self.anchor = (q, pitch)
            self.orig = {id(m): (m[0], m[1], m[2]) for m in v.selection}
            self.moved = False
            self.last_p = n[2] if n is not None else None

        def mousePressEvent(self, e):
            v = self.v
            self.setFocus()
            pos = e.position() if hasattr(e, "position") else e.pos()
            if e.button() != Qt.LeftButton:
                return
            if pos.y() < RULER_H and pos.x() >= KEY_W:            # ruler: cursor here
                v.set_position(max(0.0, v.q_of(pos.x())), follow=False)
                return
            if pos.x() < KEY_W:                                   # keyboard: hear the note
                v.preview(v.p_of(pos.y()))
                return
            shift = bool(e.modifiers() & Qt.ShiftModifier)
            q, pitch = self._at(pos)
            n = self._hit(pos)
            if v.tool == "Eraser":
                v.roll.checkpoint()
                self.mode, self.moved = "erase", False
                self._erase(pos)
                return
            if n is not None:                                     # hand / pencil on a note
                if shift:
                    if any(m is n for m in v.selection):
                        v.selection = [m for m in v.selection if m is not n]
                        self.update()
                        return
                    v.selection.append(n)
                elif not any(m is n for m in v.selection):
                    v.selection = [n]
                v.roll.checkpoint()
                self._start_drag("resize" if self._near_end(n, pos) else "move", n, pos)
                v.preview(n[2])
                self.update()
                return
            if v.tool == "Pencil":
                tr = v._ensure_track()
                step = v.grid_step() or 0.25
                v.roll.checkpoint()
                n = v.roll.add(tr, snap_floor(max(0.0, q), step), step, pitch, v.vel.value(),
                               undo=False)
                v.selection = [n]
                self._start_drag("resize", n, pos)
                self.moved = True
                v.preview(pitch)
                self.update()
                return
            # hand on empty space: rectangle selection
            self.mode = "band"
            self.band = ((pos.x(), pos.y()), (pos.x(), pos.y()))
            self.band_keep = list(v.selection) if shift else []
            if not shift:
                v.selection = []
            self.update()

        def _erase(self, pos):
            n = self._hit(pos)
            if n is not None:
                self.v.roll.remove(self.v.track, [n], undo=False)
                self.v.selection = [m for m in self.v.selection if m is not n]
                self.moved = True
                self.update()

        def mouseMoveEvent(self, e):
            v = self.v
            pos = e.position() if hasattr(e, "position") else e.pos()
            if self.mode is None:
                self.update_cursor(pos)
                return
            q, pitch = self._at(pos)
            free = bool(e.modifiers() & Qt.AltModifier)
            step = 0.0 if free else v.grid_step()
            if self.mode == "erase":
                self._erase(pos)
            elif self.mode == "move":
                o = self.orig[id(self.prim)]
                new_s = max(0.0, o[0] + q - self.anchor[0])
                dq = (snap(new_s, step) if step else new_s) - o[0]
                dp = pitch - self.anchor[1]
                for m in v.selection:
                    m0, m1, m2 = self.orig[id(m)]
                    m[0] = round(max(0.0, m0 + dq), 6)
                    m[2] = max(0, min(127, m2 + dp))
                if self.prim[2] != self.last_p:
                    self.last_p = self.prim[2]
                    v.preview(self.prim[2])
                self.moved = True
                v.roll.version += 1
            elif self.mode == "resize":
                o = self.orig[id(self.prim)]
                end = snap(q, step) if step else q
                dur = max(step or MIN_DUR, end - o[0])
                delta = dur - o[1]
                for m in v.selection:
                    m[1] = round(max(step or MIN_DUR, self.orig[id(m)][1] + delta), 6)
                self.moved = True
                v.roll.version += 1
            elif self.mode == "band":
                self.band = (self.band[0], (pos.x(), pos.y()))
                if v.roll.tracks:
                    (xa, ya), (xb, yb) = self.band
                    inside = v.roll.notes_in(v.track, v.q_of(xa), v.q_of(xb), v.p_of(ya),
                                             v.p_of(yb))
                    ids = {id(m) for m in inside}
                    v.selection = inside + [m for m in self.band_keep if id(m) not in ids]
            self.update()

        def mouseReleaseEvent(self, e):
            v = self.v
            mode, self.mode = self.mode, None
            if mode == "band":
                self.band = None
                self.update()
                return
            if mode is None:
                return
            if self.moved:
                v.changed({"erase": "deleted", "move": "moved", "resize": "length"}.get(mode, ""))
            else:
                v.roll.drop_checkpoint()

        def mouseDoubleClickEvent(self, e):
            v = self.v
            pos = e.position() if hasattr(e, "position") else e.pos()
            if v.tool != "Hand" or pos.x() < KEY_W or pos.y() < RULER_H:
                return
            n = self._hit(pos)
            if n is not None:
                v.roll.remove(v.track, [n])
                v.selection = []
                v.changed("deleted")
            else:
                q, pitch = self._at(pos)
                tr = v._ensure_track()
                step = v.grid_step() or 0.25
                n = v.roll.add(tr, snap_floor(max(0.0, q), step), step, pitch, v.vel.value())
                v.selection = [n]
                v.preview(pitch)
                v.changed("note added")

        def contextMenuEvent(self, e):
            v = self.v
            m = QMenu(self)
            m.addAction("Delete", v.delete_selection).setEnabled(bool(v.selection))
            m.addAction("Quantize…", v.quantize_dialog)
            m.addAction("Select all", v.select_all)
            m.addSeparator()
            m.addAction("Undo", v.undo).setEnabled(v.roll.can_undo)
            m.addAction("Redo", v.redo).setEnabled(v.roll.can_redo)
            m.exec(e.globalPos())

        def wheelEvent(self, e):
            v = self.v
            mods = e.modifiers()
            d = e.angleDelta()
            dy, dx = d.y(), d.x()
            pos = e.position() if hasattr(e, "position") else e.pos()
            if mods & (Qt.ControlModifier | Qt.MetaModifier):
                v.zoom(1.15 if (dy or dx) > 0 else 1 / 1.15, anchor_x=pos.x())
            elif mods & Qt.AltModifier:
                v.zoom(1.15 if (dy or dx) > 0 else 1 / 1.15, vertical=True)
            elif mods & Qt.ShiftModifier:
                v.hbar.setValue(v.hbar.value() - (dy or dx))
            else:
                if dx:
                    v.hbar.setValue(v.hbar.value() - dx)
                if dy:
                    v.vbar.setValue(v.vbar.value() - dy)
            e.accept()

        def keyPressEvent(self, e):
            v = self.v
            k, mods = e.key(), e.modifiers()
            ctrl = bool(mods & (Qt.ControlModifier | Qt.MetaModifier))
            shift = bool(mods & Qt.ShiftModifier)
            if k in (Qt.Key_Delete, Qt.Key_Backspace):
                v.delete_selection()
            elif ctrl and k == Qt.Key_Z:
                v.redo() if shift else v.undo()
            elif ctrl and k == Qt.Key_Y:
                v.redo()
            elif ctrl and k == Qt.Key_A:
                v.select_all()
            elif ctrl and k == Qt.Key_Q:
                v.quantize_dialog()
            elif k == Qt.Key_Up:
                v.nudge(dp=12 if shift else 1)
            elif k == Qt.Key_Down:
                v.nudge(dp=-12 if shift else -1)
            elif k in (Qt.Key_Left, Qt.Key_Right):
                st = v.grid_step() or 0.25
                v.nudge(dq=st if k == Qt.Key_Right else -st)
            elif k == Qt.Key_Escape:
                v.selection = []
                self.update()
            else:
                super().keyPressEvent(e)

    return Canvas


# ---------------------------------------------------------------- Quantize…
def _quantize_dialog(v, track=None):
    from PySide6.QtWidgets import (QDialog, QFormLayout, QComboBox, QSpinBox, QCheckBox,
                                   QRadioButton, QDialogButtonBox, QVBoxLayout, QLabel)
    r = v.roll
    if not r.n_notes():
        v.status.setText("nothing to quantize  ")
        return None
    if track is not None:
        v.set_track(track)
    d = QDialog(v.win)
    d.setWindowTitle("Quantize")
    lay = QVBoxLayout(d)
    form = QFormLayout()
    grid = QComboBox()
    grid.addItems(GRIDS)
    grid.setCurrentText(PianoRollView.last_quantize["grid"])
    grid.setToolTip("T = triplets; 1/8+1/8T = every note to the nearest eighth OR eighth triplet")
    strength = QSpinBox()
    strength.setRange(0, 100)
    strength.setSuffix(" %")
    strength.setValue(PianoRollView.last_quantize["strength"])
    strength.setToolTip("100 % = exactly on the grid; less keeps part of the played timing")
    ends = QCheckBox("Note ends too (else the lengths are kept)")
    ends.setChecked(PianoRollView.last_quantize["ends"])
    form.addRow("Grid:", grid)
    form.addRow("Strength:", strength)
    form.addRow("", ends)
    lay.addLayout(form)
    lay.addWidget(QLabel("Notes:"))
    tname = r.tracks[v.track]["name"] if r.tracks else ""
    r_sel = QRadioButton(f"Selected notes ({len(v.selection)})")
    r_trk = QRadioButton(f"Track {v.track + 1} {tname}")
    r_all = QRadioButton("All tracks")
    r_sel.setEnabled(bool(v.selection))
    (r_sel if v.selection else r_trk if len(r.tracks) > 1 else r_all).setChecked(True)
    for b in (r_sel, r_trk, r_all):
        lay.addWidget(b)
    info = QLabel("")
    info.setStyleSheet("color: gray")
    lay.addWidget(info)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    lay.addWidget(bb)
    sel = list(v.selection)
    state = {"applied": False}

    def apply(*_):
        if state["applied"]:
            r.revert()                 # back to the notes before the preview
        notes = trk = None
        if r_sel.isChecked():
            # the selected notes after a revert are new lists: find them again
            trk = v.track
            keys = {(n[0], n[1], n[2], n[3]) for n in sel}
            notes = [n for n in r.tracks[trk]["notes"] if (n[0], n[1], n[2], n[3]) in keys]
        elif r_trk.isChecked():
            trk = v.track
        k = r.quantize(grid.currentText(), strength.value() / 100.0, ends.isChecked(),
                       track=trk, notes=notes)
        state["applied"] = True
        v.selection = []
        info.setText(f"{k} notes moved (shown now; OK keeps it, Undo takes it back)")
        v.canvas.update()

    for w in (grid,):
        w.currentIndexChanged.connect(apply)
    strength.valueChanged.connect(apply)
    ends.toggled.connect(apply)
    for b in (r_sel, r_trk, r_all):
        b.toggled.connect(lambda on: on and apply())
    apply()
    if d.exec() == QDialog.Accepted:
        PianoRollView.last_quantize = dict(grid=grid.currentText(), strength=strength.value(),
                                           ends=ends.isChecked())
        v.changed(f"quantized {grid.currentText()} {strength.value()} %")
        return True
    if state["applied"]:
        r.revert()
        v.selection = []
        v.canvas.update()
    return False
