"""
Practice > Long tones, Scales & arpeggios, Lip slurs, Rhythm reading, Chord arpeggios
(logic in drills.py, no Qt there). Owner's rules (2026-11-06): the settings are in the tab; every Start makes
ONE new exercise and plays it (count-in, clicks, recording), Again repeats the same one
(the grade of the day is the best attempt), as many as you like; every take goes to the
practice diary. No result object (owner, 2026-11-07): every exercise made with Start becomes
an exercise object in Objects (Exercises) with its result; Again adds an attempt to the same
object (the name shows the best grade of today); double click on the object opens a tab
bound to it (bind_task: Start = that exercise again, its settings shown).

Inputs: microphone (trumpet); Scales & arpeggios also a MIDI keyboard (the note READ);
Rhythm reading: claps (microphone), the space bar, or any key of a MIDI keyboard.
Rhythm metronome: high click (a pure tone removed by a notch filter before the claps are
found), normal click, count-in only, none; volume of the clicks.
Chord arpeggios: the name of the chord sounding is shown big during the take (with the next
one; easy version: its chord tones and tensions); without "Show the notes" the staff is
hidden until the end of the take.
"""
from . import registry
from .. import drills as dr

START_MS = 900                 # time to look at the exercise before the count-in
LOOP_PAUSE_MS = 300            # chord arpeggios: pause between two takes of the loop


def _note_combo(lo=48, hi=88, value=None):
    from PySide6.QtWidgets import QComboBox
    from ..theory import note_name
    c = QComboBox()
    for p in range(lo, hi + 1):
        c.addItem(note_name(p), p)
    if value is not None:
        i = c.findData(int(value))
        if i >= 0:
            c.setCurrentIndex(i)
    return c


def _checks_button(label, items, selected):
    """A button with a menu of check boxes (keys, scale types, valve positions)."""
    from PySide6.QtWidgets import QToolButton, QMenu
    b = QToolButton()
    b.setPopupMode(QToolButton.InstantPopup)
    m = QMenu(b)
    acts = []
    for it in items:
        a = m.addAction(it)
        a.setCheckable(True)
        a.setChecked(it in selected)
        acts.append(a)
    b.setMenu(m)

    def text():
        sel = [a.text() for a in acts if a.isChecked()]
        b.setText(f"{label}: {', '.join(sel) if sel else 'none'}")
    for a in acts:
        a.toggled.connect(lambda *_: text())
    text()
    b.values = lambda: [a.text() for a in acts if a.isChecked()]

    def set_values(vals):
        for a in acts:
            a.setChecked(a.text() in vals)
    b.set_values = set_values
    return b


def _cents_chart_class():
    from PySide6.QtWidgets import QWidget
    from PySide6.QtGui import QPainter, QColor, QPen
    from PySide6.QtCore import Qt, QPointF, QRectF

    class CentsChart(QWidget):
        """Long tones: the pitch of every note in cents (0 = in tune), time left-right.
        Scale ±RANGE cents (owner, 2026-11-09: at least ±150, so a missed note shows why;
        it was ±50 and the points outside were dropped); dashed lines at ±50 = the limit
        of "held" (the grade); points beyond ±50 drawn in red."""
        RANGE = 150

        def __init__(self):
            super().__init__()
            self.notes = []
            self.setMinimumHeight(170)

        def set_notes(self, notes):
            self.notes = notes or []
            self.update()

        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.fillRect(self.rect(), QColor("white"))
            W, H = self.width(), self.height()
            L, T, B = 40, 10, 20
            ph = H - T - B

            R = self.RANGE

            def yv(c):
                return T + ph * (1 - (max(-R, min(R, c)) + R) / (2.0 * R))
            p.fillRect(QRectF(L, yv(10), W - L - 6, yv(-10) - yv(10)), QColor(46, 125, 50, 30))
            for c in (-150, -100, -50, 0, 50, 100, 150):
                pen = QPen(QColor("#999" if c else "#2e7d32"), 1 if c else 1.5)
                if abs(c) == 50:
                    pen.setStyle(Qt.DashLine)               # the limit of "held"
                p.setPen(pen)
                p.drawLine(QPointF(L, yv(c)), QPointF(W - 6, yv(c)))
                p.setPen(QColor("#555"))
                p.drawText(QRectF(0, yv(c) - 8, L - 4, 16), Qt.AlignRight | Qt.AlignVCenter,
                           f"{c:+d}" if c else "0")
            if not self.notes:
                p.drawText(self.rect(), Qt.AlignCenter, "cents of every note after the take")
                return
            n = len(self.notes)
            slot = (W - L - 6) / n
            for k, nt in enumerate(self.notes):
                x0 = L + k * slot + 4
                curve = nt.get("curve") or []
                tmax = max((t for t, _ in curve), default=1.0) or 1.0
                p.setPen(QColor("#333"))
                p.drawText(QPointF(x0, H - 5), f"{nt['name']}  {100 * nt['held']:.0f}%")
                prev = None
                for t, c in curve:
                    if c is None or abs(c) > R:
                        prev = None
                        continue
                    pt = QPointF(x0 + (slot - 8) * t / tmax, yv(c))
                    p.setPen(QPen(QColor("#c62828" if abs(c) > 50 else "#1565c0"), 1.6))
                    if prev is not None:
                        p.drawLine(prev, pt)
                    else:
                        p.drawPoint(pt)
                    prev = pt
            p.end()

    return CentsChart


def _widget_class(kind):
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                                   QSpinBox, QComboBox, QCheckBox)
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont, QKeySequence, QShortcut
    from .bar import action_bar
    from .play_reading import _StreamClock

    class DrillWidget(QWidget):
        KIND = kind

        def __init__(self, app):
            super().__init__()
            self.app = app
            self.drill = None
            self.task = None                    # exercise object of the attempts (tasks.Task)
            self.bound_task = None              # tab opened on an exercise object
            self.pc = None
            self.sv = None
            self._zoom = 1.0
            self._midi_in = None
            self._state = None
            from ..progress import settings
            self.cfg = dr.settings_of(kind, settings().get("drills", {}).get(kind))
            self.status = QLabel("")
            self.bar, self.buttons = action_bar(
                [("Start", self.start, "a NEW exercise with these settings, then the take"),
                 ("Again", self.again, "the same exercise again (the best grade of today "
                                       "counts)"),
                 ("Stop", self.stop, "stop the take"),
                 ("Keep", self.keep, "put this exercise in Objects now (it goes there "
                                     "anyway after its first take); its takes go into it"),
                 None,
                 ("Zoom +", lambda: self.zoom(1.25), "larger staff"),
                 ("Zoom -", lambda: self.zoom(0.8), "smaller staff")], right=self.status)
            self.buttons["Again"].setEnabled(False)
            lay = QVBoxLayout(self)
            box = QGroupBox("Settings")
            v = QVBoxLayout(box)
            self.form, self.form2 = QHBoxLayout(), QHBoxLayout()
            v.addLayout(self.form)
            v.addLayout(self.form2)
            self._build_settings()
            self.form.addStretch(1)
            self.form2.addStretch(1)
            from .bar import hscroll
            lay.addWidget(hscroll(box))
            self.staff_box = QVBoxLayout()
            lay.addLayout(self.staff_box, 1)
            self.chart = None
            if kind == "long_tones":
                self.chart = _cents_chart_class()()
                lay.addWidget(self.chart)
            big = QFont()
            big.setPointSize(18)
            self.feedback = QLabel(f"{dr.LABELS[kind]}: choose the settings and press Start")
            self.feedback.setFont(big)
            self.feedback.setAlignment(Qt.AlignCenter)
            self.detail = QLabel("")
            self.detail.setWordWrap(True)
            self.detail.setAlignment(Qt.AlignCenter)
            self.chord_label = None
            if kind == "chord_arpeggios":            # the chord sounding, big
                self.chord_label = QLabel("")
                self.chord_label.setTextFormat(Qt.RichText)
                self.chord_label.setAlignment(Qt.AlignCenter)
                self.chord_label.setWordWrap(True)
                lay.addWidget(self.chord_label)
                self.tick = QTimer(self)
                self.tick.setInterval(50)
                self.tick.timeout.connect(self._show_chord)
            lay.addWidget(self.feedback)
            lay.addWidget(self.detail)
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._step)
            self.tap_key = QShortcut(QKeySequence(Qt.Key_Space), self)
            self.tap_key.setContext(Qt.WidgetWithChildrenShortcut)
            self.tap_key.activated.connect(self.tap)

        # ------------------------------------------------------ settings
        def _add(self, label, w, second=False):
            f = self.form2 if second else self.form
            if label:
                f.addWidget(QLabel(label))
            f.addWidget(w)
            return w

        def _spin(self, lo, hi, val):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(int(val))
            return s

        def _combo(self, items, val):
            c = QComboBox()
            c.addItems(list(items))
            if val in items:
                c.setCurrentText(val)
            return c

        def _build_settings(self):
            c = self.cfg
            w = self.w = {}
            if kind in ("long_tones", "scales"):
                from ..phrase import instrument_range
                lo, hi = instrument_range("Bb (trumpet)")
                w["lowest"] = self._add("Lowest:", _note_combo(value=c.get("lowest") or lo))
                w["highest"] = self._add("Highest:", _note_combo(value=c.get("highest") or hi))
            if kind == "long_tones":
                w["notes"] = self._add("Notes:", self._spin(1, 12, c["notes"]))
                w["beats"] = self._add("Beats each:", self._spin(2, 16, c["beats"]))
                w["rest"] = self._add("Rest beats:", self._spin(1, 8, c["rest"]))
            if kind == "scales":
                w["keys"] = self._add("", _checks_button("Keys", dr.KEYS, c["keys"]), True)
                w["types"] = self._add("", _checks_button("Types", list(dr.SCALE_TYPES),
                                                          c["types"]), True)
                w["octaves"] = self._add("Octaves:", self._spin(1, 2, c["octaves"]), True)
                w["pattern"] = self._add("Pattern:", self._combo(dr.SCALE_PATTERNS,
                                                                 c.get("pattern", "varied")), True)
                w["note"] = self._add("Rhythm:", self._combo(dr.SCALE_NOTES,
                                                                 c["note"]), True)
                w["instrument"] = self._add("Instrument:", self._combo(
                    ("Bb (trumpet)", "C (piano)"), c["instrument"]), True)
            if kind == "lip_slurs":
                w["positions"] = self._add("", _checks_button("Valves", list(dr.VALVES),
                                                              c["positions"]))
                lv = QComboBox()
                for k, t in dr.SLUR_LABELS.items():
                    lv.addItem(t, k)
                lv.setCurrentIndex(max(0, lv.findData(int(c["level"]))))
                w["level"] = self._add("Level:", lv)
                w["note"] = self._add("Note value:", self._combo(("whole", "half", "quarter"),
                                                                 c["note"]))
                from ..phrase import instrument_range
                w["highest"] = self._add("Highest:", _note_combo(
                    value=c.get("highest") or instrument_range("Bb (trumpet)")[1]))
            if kind == "rhythm":
                lv = QComboBox()
                for k, t in dr.RHYTHM_LEVELS.items():
                    lv.addItem(t, k)
                lv.setCurrentIndex(max(0, lv.findData(int(c["level"]))))
                w["level"] = self._add("Difficulty:", lv)
                w["bars"] = self._add("Bars:", self._spin(1, 8, c["bars"]))
                w["time"] = self._add("Time:", self._combo(("4/4", "3/4", "2/4", "6/8"), c["time"]))
                w["metronome"] = self._add("Metronome:", self._combo(list(dr.METRONOMES),
                                                                     c["metronome"]), True)
                w["volume"] = self._add("Volume:", self._spin(0, 100, c["volume"]), True)
                w["volume"].setSuffix(" %")
                w["input"] = self._add("Input:", self._combo(
                    ("Clap (microphone)", "Key (space bar)", "MIDI keyboard"), c["input"]), True)
            if kind == "chord_arpeggios":
                from ..progressions import CATALOGUE
                w["progression"] = self._add("Progression:", self._combo(list(CATALOGUE),
                                                                         c["progression"]))
                w["key"] = self._add("Key (written):", self._combo(dr.KEYS, c["key"]))
                w["instrument"] = self._add("Instrument:", self._combo(dr.CHORD_INSTRUMENTS,
                                                                       c["instrument"]))
                ck = QComboBox()
                for n in dr.CHORD_CLICKS:
                    ck.addItem(str(n), n)
                ck.setCurrentIndex(max(0, ck.findData(int(c["clicks"]))))
                w["clicks"] = self._add("Clicks a chord:", ck, True)
                w["times"] = self._add("Times:", self._spin(1, 4, c["times"]), True)
                hb = QCheckBox("Show the notes")
                hb.setToolTip("easy version: the chord tones and the tensions of every chord "
                              "are shown (and the staff)")
                hb.setChecked(bool(c.get("help", True)))
                w["help"] = self._add("", hb, True)
                rb = QCheckBox("Random")
                rb.setToolTip("change every time: progression, key and clicks a chord drawn at "
                              "random for every new exercise")
                rb.setChecked(bool(c.get("random", False)))
                w["random"] = self._add("", rb, True)

                def _rand(on):
                    for k in ("progression", "key", "clicks"):
                        w[k].setEnabled(not on)
                rb.toggled.connect(_rand)
                _rand(rb.isChecked())
            w["bpm"] = self._add("bpm:", self._spin(30, 220, c["bpm"]),
                                 kind in ("scales", "rhythm", "chord_arpeggios"))
            if kind != "rhythm":
                cb = QCheckBox("Click")
                cb.setChecked(bool(c.get("click", True)))
                w["click"] = self._add("", cb, kind in ("scales", "chord_arpeggios"))
            if kind in ("scales", "chord_arpeggios"):
                w["input"] = self._add("Input:", self._combo(("Microphone", "MIDI keyboard"),
                                                             c["input"]), True)

        def settings(self):
            """Values of the tab (saved for the next time)."""
            s = {}
            for k, wd in self.w.items():
                if hasattr(wd, "values"):
                    s[k] = wd.values()
                elif isinstance(wd, QCheckBox):
                    s[k] = wd.isChecked()
                elif isinstance(wd, QSpinBox):
                    s[k] = wd.value()
                elif isinstance(wd, QComboBox):
                    s[k] = wd.currentData() if wd.currentData() is not None else wd.currentText()
            return s

        def apply_settings(self, s):
            """Settings of an exercise object in the controls (bind_task)."""
            for k, v in (s or {}).items():
                wd = self.w.get(k)
                if wd is None or v is None:
                    continue
                if hasattr(wd, "set_values"):
                    wd.set_values(list(v))
                elif isinstance(wd, QCheckBox):
                    wd.setChecked(bool(v))
                elif isinstance(wd, QSpinBox):
                    wd.setValue(int(v))
                elif isinstance(wd, QComboBox):
                    i = wd.findData(v)
                    if i < 0:
                        i = wd.findText(str(v))
                    if i >= 0:
                        wd.setCurrentIndex(i)

        def _save(self, s):
            try:
                from ..progress import settings, save_setting
                allv = dict(settings().get("drills", {}))
                allv[kind] = s
                save_setting("drills", allv)
            except Exception as e:
                self.app.log(f"{dr.LABELS[kind]}: settings not saved: {e}")

        # ------------------------------------------------------ flow
        def _say(self, text, error=False):
            self.feedback.setStyleSheet("color: red" if error else "")
            self.feedback.setText(text)
            self.app.log(f"{dr.LABELS[kind]}: {text}")

        def start(self):
            """A new exercise, then its take (a tab bound to an exercise object: that
            exercise again)."""
            if self.bound_task is not None:
                return self.again()
            self.stop()
            s = self.settings()
            self._save(s)
            try:
                self.drill = dr.make(kind, s)
            except ValueError as e:
                self._say(str(e), error=True)
                return None
            self.task = None                           # a new exercise = a new object
            self.buttons["Again"].setEnabled(True)
            self._looping = kind == "chord_arpeggios"
            return self._prepare()

        def again(self):
            if self.drill is None:
                return self.start()
            self.stop()
            self._looping = kind == "chord_arpeggios"
            return self._prepare()

        def _loop_next(self):
            """CHORD ARPEGGIOS LOOP (owner, 2026-11-13: "it must always loop, it must not
            stop"): after every take the next one starts at once (Random ticked and not
            bound to an exercise: a new random exercise, else the same one again), until
            Stop; the grade of the take just done stays shown during the next one."""
            if not getattr(self, "_looping", False) or self._state is not None:
                return
            last = (self.feedback.text(), self.detail.text())
            if self.bound_task is None and self.settings().get("random"):
                self.start()
            else:
                self.again()
            if self._looping:
                self.detail.setText(f"previous take: {last[0]}\n{last[1]}")

        def bind_task(self, task):
            """This tab does this exercise object (double click / routine): its settings
            in the controls; Start and Again = its take; the attempts go into it."""
            self.stop()
            self.bound_task = self.task = task
            self.drill = task.drill_obj()
            self.apply_settings(task.settings)
            self.buttons["Again"].setEnabled(True)
            self.feedback.setStyleSheet("")
            self.feedback.setText(f"{task.title}  —  press Start")
            return self

        def _source(self):
            t = self.settings().get("input", "Microphone")
            return {"MIDI keyboard": "midi", "Key (space bar)": "key"}.get(t, "microphone")

        def _prepare(self):
            from ..midi import Midi
            s = self.settings()
            mode = dr.METRONOMES.get(s.get("metronome"), "normal" if s.get("click", True) else "none")
            gain = float(s.get("volume", 100)) / 100.0
            try:
                self.pc = self.drill.check(bpm=s["bpm"], click_mode=mode, click_gain=gain,
                                           user=self.app.user)
            except Exception as e:
                self._say(f"{type(e).__name__}: {e}", error=True)
                return None
            if mode == "normal" and not Midi._default_sf2:
                self.app.log(f"{dr.LABELS[kind]}: no soundfont: synthetic clicks")
            self._show_staff()
            if kind == "chord_arpeggios":
                self._chord_list()
                if not self.drill.info.get("help"):
                    self.sv.win.hide()                 # nothing to read: only the names
                self._show_chord(waiting=True)
            if self.chart is not None:
                self.chart.set_notes([])
            self.detail.setText("")
            self._say(self.drill.title)
            self._state = "waiting"
            self.timer.start(START_MS)
            return self.drill

        def _show_staff(self):
            from ..staffview import StaffView
            if self.sv is not None:
                self.sv.stop()
                self.sv.win.setParent(None)
                self.sv.win.deleteLater()
            self.sv = StaffView(self.pc.score, title=self.drill.title)
            self.sv.win.setWindowFlags(Qt.Widget)
            self.sv.hide_toolbar()
            self.sv.win.statusBar().hide()
            self.staff_box.addWidget(self.sv.win)
            if abs(self._zoom - 1.0) > 1e-6:
                self.sv.zoom(self._zoom)

        def zoom(self, f):
            self._zoom = max(0.2, min(5.0, self._zoom * f))
            if self.sv is not None:
                self.sv.zoom(f)
            return self

        def _devices(self):
            from ..realtime import audio_config
            cfg = audio_config()
            return dict(input_device=cfg.get("input_device") or None,
                        output_device=cfg.get("device") or None)

        def _step(self):
            import traceback
            try:
                if self._state == "waiting":
                    self._begin_take()
                elif self._state == "recording":
                    self._end_take()
            except Exception as e:
                self._state = None
                self._say(f"Error: {type(e).__name__}: {e} (see Log)", error=True)
                self.app.log(traceback.format_exc())

        def _begin_take(self):
            pc = self.pc
            src = self._source()
            pc.start(**self._devices())
            self._state = "recording"
            self.timer.start(int(pc.duration * 1000) + 300)
            if src == "midi":
                self._open_midi(pc)
            if src == "key":
                self.setFocus()
            self.sv.clear_marks()
            self.sv.play(bpm=pc.bpm, start=0, count_in=1, click=False, sound=False)
            self.sv.player = _StreamClock(pc)
            if self.chord_label is not None:
                self.tick.start()
            what = {"key": "tap the SPACE BAR", "midi": "play the keyboard"}.get(
                src, "clap" if kind == "rhythm" else "play")
            self.status.setText("● take ")
            self._say(f"Count-in… then {what}")

        def tap(self):
            """Space bar (rhythm reading, input Key)."""
            if self._state == "recording" and self.pc is not None and kind == "rhythm":
                self.pc.tap()

        # ------------------------------------------------------ chord arpeggios
        def _chord_list(self):
            """[(start_q, end_q, name, notes text)] of the chords of the drill."""
            from .. import theory as th
            info = self.drill.info
            ch = info["chords"]
            ctx = dr.chord_context([c for c, _, _ in ch], info["key"], info.get("minor", False))
            flat = info["key"] in ("F", "Bb", "Eb", "Ab", "Db", "Gb")

            def names(pcs, sym):
                acc = sym[1:2]
                tab = th.FLAT_NAMES if acc == "b" or (acc != "#" and flat) else th.SHARP_NAMES
                return " ".join(tab[pc] for pc in pcs)
            out = []
            for (c, st, du), (chord, cx) in zip(ch, ctx):
                tones, tens = dr.chord_notes(chord, cx)
                txt = names(tones, c) + (f"   ·   tensions {names(tens, c)}" if tens else "")
                out.append((st, st + du, c, txt))
            self._chords = out

        def _show_chord(self, waiting=False):
            """The chord sounding (stream clock), the next one; notes if easy version."""
            if self.chord_label is None or not getattr(self, "_chords", None):
                return
            pc = self.pc
            q = -1.0
            if not waiting and pc is not None:
                q = pc.heard_time() * pc.bpm / 60.0 - pc.lead_q
            k = 0
            for i, (st, en, _, _) in enumerate(self._chords):
                if st <= q:
                    k = i
            st, en, name, notes = self._chords[k]
            nxt = self._chords[k + 1][2] if k + 1 < len(self._chords) else ""
            help_ = self.drill.info.get("help")
            pre = "count-in… " if q < 0 else ""
            html = (f"<div style='font-size:12pt;color:#666'>{pre}chord {k + 1}/"
                    f"{len(self._chords)}</div><div style='font-size:44pt;font-weight:bold'>"
                    f"{name}</div>")
            if help_:
                html += f"<div style='font-size:16pt;color:#1565c0'>{notes}</div>"
            if nxt:
                html += f"<div style='font-size:13pt;color:#666'>next: {nxt}</div>"
            self.chord_label.setText(html)

        def _end_take(self):
            self._state = None
            self._close_midi()
            if self.chord_label is not None:
                self.tick.stop()
                self.chord_label.setText("")
                self.sv.win.show()                     # the staff, coloured, at the end
            pc = self.pc
            self.sv.stop()
            self.status.setText("")
            self.feedback.setText("Checking…")
            self.feedback.repaint()
            pc.wait(timeout=1.0)
            src = self._source()
            r = self.drill.evaluate(pc, source=src)
            self.sv.mark(r["colors"])
            self.sv.set_position(0)
            best = None
            try:
                self.drill.record(r, pc, self.app.user)
                from ..diary import get
                best = get(self.app.user).best_today(self.drill.key)
            except Exception as e:
                self.app.log(f"{dr.LABELS[kind]}: diary: {type(e).__name__}: {e}")
            self._to_object(r, pc)
            ok = r["fraction"] > 0.6
            self.feedback.setStyleSheet("color: green" if ok else "color: red")
            self.feedback.setText(f"{r['rating']}   {r['grade']:.1f}/10"
                                  + (f"   (best today {best:.1f})" if best is not None
                                     and best > r["grade"] else ""))
            extra = r.get("detail", {}).get("played_names")
            per = r.get("detail", {}).get("chords")
            if per:                                    # chord arpeggios: chord by chord
                extra = "   ".join(f"{x['chord']} {10 * x['score']:.0f}" for x in per)
            self.detail.setText(r["text"] + (f"\nplayed: {extra}" if extra and not per
                                              else f"\n{extra}" if extra else ""))
            if self.chart is not None:
                self.chart.set_notes(r["detail"].get("notes"))
            self.app.log(f"{dr.LABELS[kind]}: {self.drill.title}: {r['grade']:.1f} ({r['text']})")
            if getattr(self, "_looping", False):       # chord arpeggios: the next take at once
                QTimer.singleShot(LOOP_PAUSE_MS, self._loop_next)

        def keep(self):
            """KEEP (owner, 2026-11-13): the exercise of this tab into Objects at once, also
            before (or without) a take; the takes then go into it. Not on disk."""
            from ..tasks import Task
            if self.task is not None:
                self.app.log(f"{self.task.title}: already in Objects")
                return self.task
            if self.drill is None:
                self.app.log(f"{dr.LABELS[kind]}: press Start first (the exercise is made "
                             "at Start)")
                return None
            try:
                self.task = Task.from_drill(self.drill, self.settings())
                name = self.app.add_object(self.task, self.task.title)
                self.app.log(f"exercise kept in Objects: {name}")
            except Exception as e:
                self.app.log(f"{dr.LABELS[kind]}: keep: {type(e).__name__}: {e}")
            return self.task

        def busy(self):
            """A take is going on (or the chord arpeggios loop): the routine's ◀ ▶ wait."""
            return self._state is not None or bool(getattr(self, "_looping", False))

        def _to_object(self, r, pc):
            """The exercise object in Objects: created at the first take of a new exercise
            (with this result), one more attempt at every Again."""
            from ..tasks import Task
            try:
                if self.task is None:
                    self.task = Task.from_drill(self.drill, self.settings())
                    self.task.add_take(r, pc, self.app.user)
                    self.app.add_object(self.task, self.task.title)
                else:
                    self.task.add_take(r, pc, self.app.user)
                self.app.attempt_added(self.task)
            except Exception as e:
                self.app.log(f"{dr.LABELS[kind]}: exercise object: {type(e).__name__}: {e}")

        def _open_midi(self, pc):
            from ..midiin import KeyboardSynth, port_name
            from ..realtime import audio_config
            try:
                name = port_name()
            except RuntimeError as e:
                self.app.log(str(e))
                return
            if name is None:
                self._say("no MIDI keyboard connected (Settings > Audio: Test MIDI)", error=True)
                return

            def listen(msg, t):
                on = msg.type == "note_on" and msg.velocity > 0
                if kind == "rhythm":
                    if on:
                        pc.tap()
                elif on:
                    pc.midi_message(True, msg.note)
                elif msg.type in ("note_off", "note_on"):
                    pc.midi_message(False, msg.note)
            thru = bool(audio_config().get("midi_thru", True)) and kind != "rhythm"
            try:
                self._midi_in = KeyboardSynth(program=self.drill.phrase.program, sound=thru,
                                              listener=listen).open(name)
            except Exception:
                self._midi_in = KeyboardSynth(sound=False, listener=listen).open(name)

        def _close_midi(self):
            if self._midi_in is not None:
                try:
                    self._midi_in.close()
                except Exception:
                    pass
                self._midi_in = None

        def stop(self):
            self._looping = False                     # Stop ends the chord arpeggios loop
            self.timer.stop()
            self._close_midi()
            if self._state == "recording" and self.pc is not None:
                try:
                    self.pc.stop()
                except Exception:
                    pass
            self._state = None
            if self.chord_label is not None:
                self.tick.stop()
            if self.sv is not None:
                self.sv.stop()
            self.status.setText("")
            return self

        def closing(self):
            self.stop()

    return DrillWidget


for _k, _help in (
        ("long_tones", "A long note (or a few) in your range: held time, stability and "
                       "intonation in cents; Start = a new exercise, Again = the same."),
        ("scales", "Scales and arpeggios in the keys and types chosen, one or two octaves "
                   "up and down; only the order of the notes counts (very loose timing)."),
        ("lip_slurs", "Lip slurs on the harmonics of the valve positions chosen, level 1-6; "
                      "only the order of the notes counts."),
        ("rhythm", "Rhythm reading: clap (microphone), tap the space bar or a MIDI key; only "
                   "the timing counts. Metronome: high click (filtered out), normal, count-in "
                   "only, none."),
        ("chord_arpeggios", "The chords of a progression in a key: every chord sounds once "
                            "at its first click (sustained piano) and its name is shown; "
                            "arpeggiate on it for 4, 8 or 12 clicks. More right notes = "
                            "better (chord tones and tensions); wrong notes and silence "
                            "lower the grade. Show the notes = easy version.")):
    registry.register(registry.Tool(
        name=f"drill_{_k}", label=dr.LABELS[_k], category="Practice", kind="session",
        factory=(lambda app, k=_k: _widget_class(k)(app)), help=_help))
