"""
Practice > Read & play (trumpet or MIDI keyboard): a block of N exercises (phrases) like the
other exercises (Start / Pause / Resume, Stop, Repeat, grade 0-10). Every phrase
is shown with a moving cursor: one count-in bar of metronome, then the player
plays while the microphone records; every note is checked (port of the MATLAB
mysmartmusic, logic in playcheck: PlayCheck, PlayQuiz; no Qt). Wrong notes turn
red; points = base × fraction of notes recognised.

Input: microphone (trumpet) or MIDI keyboard (Settings > Audio: MIDI input). With
the keyboard, Read & play expects the WRITTEN note (the one read), Listen & repeat
the note heard; the keys also sound with the soundfont if Settings > Audio
"Keyboard sound" is on. "First note: G4" (C4 = middle C, written pitch) is shown in
the bar when Settings > Exercises > <type> > Show first note is on.

QUICK EXERCISE (owner, 2026-11-07): Practice > Read & play / Listen & repeat opens a tab
whose Start makes ONE new RANDOM exercise (bars, simplify, instrument: settings in the tab;
made from a piece of a generated duet, phrase.exercise_from_duet — owner 2026-11-09: the user
is never told about duets, "misleading") — added to Objects (Exercises) and played at once; Again =
another take, Repeat = the same exercise again; every take is an attempt on that exercise.
Existing exercises (♩ / ▦, from Generate) are done with a double click on the object: the
tab is then bound to them (bind). A MIDI/Score is never practised directly.
The clicks must reach the microphone (loudspeakers, no headphones).

From code:  w = app.open_tool('play_reading'); w.start()          # quick
            w = app.open_object('<exercise name>'); w.start()     # an existing exercise
"""
from . import registry
from .exercise_ui import exercise_base, CONTROL_FONT_PT, CONTROL_HEIGHT
from ..playcheck import PlayQuiz, EXERCISE

START_TAKE_MS = 900          # time to look at the phrase before the count-in


class _StreamClock:
    """Stands for the StaffView player: the cursor follows the time heard from
    the Read & play stream (playcheck.PlayCheck.heard_time)."""

    def __init__(self, pc):
        self.pc = pc
        self.t0 = None
        self.latency = 0.0

    def elapsed(self):
        return self.pc.heard_time()

    def stop(self):
        pass


def _is_random(ph):
    """A random exercise (a piece of a generated duet): it has no Make a variant panel."""
    return bool((getattr(ph, "origin", None) or {}).get("duet"))


def _widget_class():
    from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel,
                                   QSpinBox)
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont

    class PlayReadingWidget(exercise_base()):
        kind = EXERCISE
        mode = "reading"             # 'repeat' in ListenRepeatWidget
        LOG = "read & play"
        result_object = False        # no new object: the grade goes on each exercise (phrase)

        def __init__(self, app):
            super().__init__()
            self.app = app
            self.sv = None
            self._zoom = 1.0                 # zoom of the staff, kept for every exercise / report
            self._repeat_questions = None
            self._bound = None              # phrases of this tab (opened from an exercise)
            self._quick = None              # quick exercise made by the last Start
            lay = QVBoxLayout(self)
            big = QFont()
            big.setPointSize(15)

            from ..exercise import exercise_settings
            cfg = exercise_settings(self.kind)
            box = QGroupBox("Settings")
            row = QHBoxLayout(box)
            self.bpm = QSpinBox()
            self.bpm.setRange(30, 240)
            self.bpm.setValue(int(cfg.get("bpm", 90)))       # default: Settings > Exercises
            self.source = QLabel("")
            from PySide6.QtWidgets import QComboBox
            self.input_box = QComboBox()
            self.input_box.addItems(["Microphone", "MIDI keyboard"])
            self.input_box.setCurrentText(str(cfg.get("input", "Microphone")))
            self.input_box.setToolTip("trumpet (microphone) or MIDI keyboard (Settings > Audio: "
                                      "MIDI input)" + ("; with the keyboard play the WRITTEN note"
                                                       if self.mode == "reading" else ""))
            from PySide6.QtWidgets import QCheckBox
            self.click_box = QCheckBox("Click")
            self.click_box.setChecked(bool(cfg.get("click", True)))
            self.click_box.setToolTip("metronome clicks during the exercise (count-in and "
                                      "beats); untick to practise without them")
            extra = (QLabel("Input:"), self.input_box, self.click_box)
            self.pos_box = None
            if self.mode == "reading":               # SHOW POSITIONS (owner, 2026-11-09)
                from ..progress import settings as _st
                self.pos_box = QCheckBox("Show positions")
                self.pos_box.setChecked(bool(_st().get("show_positions", False)))
                self.pos_box.setToolTip("the valves (trumpet) or the slide positions (trombone) "
                                        "under the notes you read")
                self.pos_box.toggled.connect(self._positions_toggled)
                extra = extra + (self.pos_box,)
            self.show_first = bool(cfg.get("show_first_note", self.mode == "repeat"))
            for wdg in (QLabel("bpm:"), self.bpm) + extra + (self.source,):
                row.addWidget(wdg)
            row.addStretch()
            from .bar import hscroll
            lay.addWidget(hscroll(box))
            self.quick_box = self._quick_settings(cfg)
            lay.addWidget(hscroll(self.quick_box))
            self.edit_box = self._edit_controls()
            lay.addWidget(hscroll(self.edit_box))
            self.edit_box.hide()                 # quick tab: random exercises, no variants

            self.build_controls(extra=[("Again", lambda: self.again(),
                                        "play this exercise again from the count-in"),
                                       None,
                                       ("Zoom +", lambda: self.zoom(1.25), "larger staff"),
                                       ("Zoom -", lambda: self.zoom(0.8), "smaller staff")])
            self.again_btn = self.bar_buttons["Again"]
            self.first_lbl = QLabel("")                   # "First note: G4" (in the bar)
            fb = QFont()
            fb.setPointSize(14)
            fb.setBold(True)
            self.first_lbl.setFont(fb)
            self.first_lbl.setToolTip("first note of the exercise (written; C4 = middle C)")
            bl = self.bar.layout()
            bl.insertWidget(max(0, bl.count() - 2), self.first_lbl)   # before stretch + clock

            self.staff_box = QVBoxLayout()
            lay.addLayout(self.staff_box, 1)

            self.feedback = QLabel("Start = a new random exercise")
            f2 = QFont()
            f2.setPointSize(20)
            self.feedback.setFont(f2)
            self.feedback.setAlignment(Qt.AlignCenter)
            self.feedback.setWordWrap(True)            # long titles wrap, never widen the tab
            self.score_lbl = QLabel("")
            self.score_lbl.setFont(big)
            self.score_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.feedback)
            lay.addWidget(self.score_lbl)

            self.take_timer = QTimer(self)                 # count-in delay, then end of take
            self.take_timer.setSingleShot(True)
            self.take_timer.timeout.connect(self._take_step)
            self._take_state = None                        # None, 'waiting', 'recording'
            self.set_answers(False)
            self.selection_changed()

        # ------------------------------------------------------ quick exercise
        def _quick_settings(self, cfg):
            """Quick exercise (no exercise bound): bars, simplify, instrument of the random
            exercise made at every Start (saved per user). The part of the duet it is cut
            from is always random and not shown (owner, 2026-11-09)."""
            from PySide6.QtWidgets import QComboBox
            from ..phrase import LEVEL_LABELS, EXERCISE_INSTRUMENTS, INSTRUMENTS, DUET_PARTS
            from ..progress import settings
            q = dict(settings().get("quick_exercises", {}).get(self.kind, {}))
            box = QGroupBox("New random exercise (every Start)")
            row = QHBoxLayout(box)
            self.q_part = QComboBox()
            self.q_part.addItems(list(DUET_PARTS))
            self.q_part.setCurrentText(str(q.get("part", "random")))
            self.q_bars = QSpinBox()
            self.q_bars.setRange(1, 16)
            self.q_bars.setValue(int(q.get("bars") or cfg.get("bars") or 4))
            self.q_level = QComboBox()
            for k, t in LEVEL_LABELS.items():
                self.q_level.addItem(t, k)
            self.q_level.setCurrentIndex(max(0, self.q_level.findData(int(q.get("level", 3)))))
            self.q_instr = QComboBox()
            self.q_instr.addItems(list(EXERCISE_INSTRUMENTS if self.mode == "reading"
                                       else INSTRUMENTS))
            self.q_instr.setCurrentText(str(q.get("instrument", "Bb (trumpet)")))
            for c in (self.q_part, self.q_level, self.q_instr):
                c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                c.setMinimumContentsLength(10)
            self.q_part.setCurrentText("random")
            self.q_part.hide()
            self.q_instr.setToolTip("the instrument you play to study")
            for wdg in (QLabel("Bars:"), self.q_bars,
                        QLabel("Simplify:"), self.q_level, QLabel("Instrument:"), self.q_instr):
                row.addWidget(wdg)
            row.addStretch()
            return box

        def quick_settings(self):
            return dict(part=self.q_part.currentText(), bars=self.q_bars.value(),
                        level=self.q_level.currentData(), instrument=self.q_instr.currentText())

        def _new_quick(self):
            """A new random exercise (a piece of a new duet), added to Objects (Exercises)."""
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt as _Qt
            from ..phrase import exercise_from_duet
            from ..progress import settings, save_setting
            q = self.quick_settings()
            try:
                allq = dict(settings().get("quick_exercises", {}))
                allq[self.kind] = q
                save_setting("quick_exercises", allq)
            except Exception:
                pass
            self.feedback.setText("A new exercise…")
            QApplication.setOverrideCursor(_Qt.WaitCursor)
            try:
                ph = exercise_from_duet(purpose=self.mode, **q)
            except Exception as e:
                self._say(f"no exercise: {type(e).__name__}: {e}")
                return None
            finally:
                QApplication.restoreOverrideCursor()
            ph.practice_bpm = float(self.bpm.value())
            name = self.app.add_object(ph, ph.title)
            self.app.log(f"{self.LOG}: new exercise {name}")
            self._quick = [ph]
            self._load_edit()
            return [ph]

        # ------------------------------------------------------ change the exercise
        def _edit_controls(self):
            """Change the exercise (owner, 2026-11-08): bars, part, difficulty, instrument
            (also a transposition), transformation, tempo (the bpm field above). A changed
            exercise is ANOTHER exercise: 'Save as new' adds it without results; doing it
            (Start, or 'Start changed') adds it with that result. The old one stays."""
            from PySide6.QtWidgets import QComboBox, QPushButton
            from ..phrase import (LEVEL_LABELS, EXERCISE_INSTRUMENTS, INSTRUMENTS,
                                  transform_tags)
            box = QGroupBox("Make a variant (a new exercise; this one stays as it is)")
            outer = QVBoxLayout(box)                   # two rows: never wider than needed
            row, row2 = QHBoxLayout(), QHBoxLayout()
            outer.addLayout(row)
            outer.addLayout(row2)
            self.e_first, self.e_last = QSpinBox(), QSpinBox()
            for sp in (self.e_first, self.e_last):
                sp.setRange(0, 9999)
            self.e_part = QComboBox()
            self.e_level = QComboBox()
            for k, t in LEVEL_LABELS.items():
                self.e_level.addItem(t, k)
            self.e_instr = QComboBox()
            self.e_instr.addItems(list(EXERCISE_INSTRUMENTS if self.mode == "reading"
                                       else INSTRUMENTS))
            self.e_trans = QComboBox()
            self.e_trans.addItems(list(transform_tags()))
            self.e_save = QPushButton("Save as new")
            self.e_save.setToolTip("a new exercise with these changes, without results")
            self.e_save.clicked.connect(lambda: self.save_changed())
            self.e_go = QPushButton("Start changed")
            self.e_go.setToolTip("do the changed exercise now: it becomes a new exercise with "
                                 "this result")
            self.e_go.clicked.connect(lambda: self.start_changed())
            self.e_reset = QPushButton("Reset")
            self.e_reset.clicked.connect(lambda: self._load_edit())
            self.e_info = QLabel("")
            self.e_info.setWordWrap(True)
            for c in (self.e_part, self.e_level, self.e_instr, self.e_trans):
                c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                c.setMinimumContentsLength(12)          # the list still shows the whole text
            for wdg in (QLabel("Bars"), self.e_first, QLabel("to"), self.e_last, QLabel("Part:"),
                        self.e_part, QLabel("Simplify:"), self.e_level):
                row.addWidget(wdg)
            row.addStretch()
            for wdg in (QLabel("Instrument:"), self.e_instr, QLabel("Change:"), self.e_trans,
                        self.e_save, self.e_go, self.e_reset):
                row2.addWidget(wdg)
            row2.addWidget(self.e_info, 1)
            box.setEnabled(False)
            return box

        def _edit_target(self):
            """The exercise the panel changes: one phrase bound to the tab, or the last
            quick one (a group: none)."""
            ph = self._phrases()
            return ph[0] if len(ph) == 1 else None

        def _default_bpm(self):
            from ..exercise import exercise_settings
            return int(exercise_settings(self.kind).get("bpm", 90))

        def _load_edit(self):
            """The values of the exercise in the panel (and its tempo in the bpm field)."""
            from ..phrase import settings_of
            ph = self._edit_target()
            # RANDOM EXERCISES HAVE NO "Make a variant" (owner, 2026-11-09: bars and part refer
            # to a hidden duet; a new Start makes another one): the panel is hidden in the
            # quick tab and for random exercises; only those cut from a MIDI / score have it
            random = (not self._bound) or all(_is_random(p) for p in self._phrases())
            self.edit_box.setVisible(not random)
            if random:
                self.edit_box.setEnabled(False)
                if ph is not None:
                    self.bpm.setValue(int(round(ph.practice_bpm or self._default_bpm())))
                return
            if ph is None:
                self.edit_box.setEnabled(False)
                self.e_info.setText("open ONE exercise to change it" if self._bound else "")
                return
            st = settings_of(ph)
            self.edit_box.setEnabled(True)
            full = st["can_remake"]
            lo, hi = st["bars"] or (st["first"], st["last"])
            for sp, v in ((self.e_first, st["first"]), (self.e_last, st["last"])):
                sp.setRange(int(lo), int(hi))
                sp.setValue(int(v))
            self.e_part.clear()
            if st["part"] is None or not st["parts"]:
                self.e_part.addItem(ph.part or "all parts", None)
            else:
                for i, n in enumerate(st["parts"]):
                    self.e_part.addItem(n, i)
                self.e_part.setCurrentIndex(int(st["part"]))
            self.e_level.setCurrentIndex(max(0, self.e_level.findData(int(st["level"]))))
            self.e_instr.setCurrentText(st["instrument"])
            if self.e_instr.currentText() != st["instrument"]:      # an old transposition
                self.e_instr.insertItem(0, st["instrument"])           # exercise (hidden now)
                self.e_instr.setCurrentIndex(0)
            self.e_trans.setCurrentText(st["transform"])
            if self.e_trans.currentText() != st["transform"]:
                self.e_trans.insertItem(0, st["transform"])
                self.e_trans.setCurrentIndex(0)
            for w in (self.e_first, self.e_last, self.e_part, self.e_level, self.e_instr):
                w.setEnabled(full)
            self.e_info.setText("" if full else "made before 2026-11-08: only tempo and "
                                                "transposition can change")
            self.bpm.setValue(int(round(ph.practice_bpm or self._default_bpm())))

        def changes(self):
            """What differs from the exercise in the panel ({} = nothing)."""
            from ..phrase import settings_of
            ph = self._edit_target()
            if ph is None or not self.edit_box.isEnabled():
                return {}
            st = settings_of(ph)
            new = dict(first=self.e_first.value(), last=self.e_last.value(),
                       part=self.e_part.currentData(), level=self.e_level.currentData(),
                       instrument=self.e_instr.currentText(),
                       transform=self.e_trans.currentText())
            out = {k: v for k, v in new.items() if st["can_remake"] or k == "transform"
                   if v != st[k] and not (k == "part" and v is None)}
            bpm = float(self.bpm.value())
            if abs(bpm - float(ph.practice_bpm or self._default_bpm())) > 1e-6:
                out["bpm"] = bpm
            return out

        def _changed_exercise(self):
            """The changed exercise as a NEW object in Objects (no results); the tab now
            works on it. None if nothing changed or it cannot be made."""
            from ..phrase import remake
            ch = self.changes()
            ph = self._edit_target()
            if not ch or ph is None:
                return None
            try:
                new = remake(ph, bpm=ch.pop("bpm", ph.practice_bpm or self._default_bpm()), **ch)
            except Exception as e:
                self._say(f"cannot change it: {type(e).__name__}: {e}")
                return None
            name = self.app.add_object(new, new.title)
            self.app.log(f"{self.LOG}: changed exercise saved as {name}")
            if self._bound:
                self._bound = [new]
            else:
                self._quick = [new]
            self._load_edit()
            self.selection_changed()
            return new

        def save_changed(self):
            """'Save as new': the changed exercise, without results."""
            new = self._changed_exercise()
            if new is None and not self.changes():
                self._say("nothing changed", error=False)
            return new

        def start_changed(self):
            """'Start changed': the changed exercise is made and done now."""
            if self._changed_exercise() is None and self.changes():
                return None
            self._repeat_questions = self._phrases()
            return self.start()

        # ------------------------------------------------------ exercises
        def bind(self, phrases):
            """This tab works on these exercises (double click on an exercise / group,
            routine); the staff is shown at once; no quick exercise here."""
            self._bound = list(phrases)
            self.quick_box.hide()
            self.selection_changed()
            self._load_edit()
            return self

        def _phrases(self):
            """Exercises of this tab: the bound ones, else the last quick exercise."""
            if self._bound:
                return list(self._bound)
            return list(self._quick or [])

        def selection_changed(self):
            """Bound tab: count of exercises and, while no exercise is running, the
            staff of the first one at once (the selection in Objects is not used)."""
            try:
                ph = self._phrases()
                if self._bound:
                    self.source.setText(f"   {len(ph)} exercises")
                elif not ph:
                    self.source.setText("")
                    self.feedback.setText("Start = a new random exercise")
                running = self.ex is not None and self.ex.state not in ("finished", "stopped")
                if self._bound and ph and not running:
                    self._first_note(ph[0])
                    self.feedback.setStyleSheet("")
                    if self.mode == "repeat":             # the staff stays hidden: listen first
                        self._hide_staff()
                        self.feedback.setText(f"{len(ph)} exercises — press Start, listen, "
                                              "then repeat after the count-in")
                    else:
                        self._show_staff(ph[0].to_score(positions=self._positions()))
                        self.feedback.setText(ph[0].title + "  —  press Start")
            except Exception as e:
                self.app.log(f"{self.LOG}: preview: {type(e).__name__}: {e}")

        # ------------------------------------------------------ hooks for exercise_base
        def make_quiz(self):
            try:
                import sounddevice  # noqa: F401
                import scipy        # noqa: F401
            except ImportError as e:
                self._say(f"missing package: {e.name} (pip install {e.name})")
                return None
            if self._repeat_questions is not None:
                phrases, self._repeat_questions = self._repeat_questions, None
            elif self._bound:
                if self.changes():                     # changed and done: a new exercise
                    if self._changed_exercise() is None:
                        return None
                phrases = list(self._bound)
            else:
                phrases = self._new_quick()                # quick: a new exercise
                if phrases:
                    self._first_note(phrases[0])
            if not phrases:
                if self._bound is not None:
                    self._say("no exercises in this tab")
                return None
            source = "microphone"
            if self.input_box.currentText() == "MIDI keyboard":
                source = "midi"
                port = self._midi_port_name()
                if port is None:
                    return None
            from ..midi import Midi
            if self.mode == "repeat" and not Midi._default_sf2:
                self._say("a soundfont is needed to play the phrase (Settings > Soundfont…)")
                return None
            self.app.log(f"{self.LOG}: {len(phrases)} exercises available, bpm {self.bpm.value()}, "
                         f"input {source}")
            return PlayQuiz(phrases, user=self.app.user, bpm=self.bpm.value(),
                            progress=self.app.progress, mode=self.mode, source=source,
                            click=self.click_box.isChecked(), positions=self._positions())

        def _positions(self):
            return self.pos_box is not None and self.pos_box.isChecked()

        def _positions_toggled(self, on):
            """Saved per user; the staff of a bound tab is shown again at once."""
            try:
                from ..progress import save_setting
                save_setting("show_positions", bool(on))
            except Exception:
                pass
            self.selection_changed()

        def _midi_port_name(self):
            """MIDI input port of the settings (or the first one), None + message if none."""
            from ..midiin import port_name
            try:
                name = port_name()
            except RuntimeError as e:
                self._say(str(e))
                return None
            if name is None:
                self._say("no MIDI keyboard connected (Settings > Audio: Test MIDI)")
            return name

        def _first_note(self, q):
            """'First note: G4' in the bar (written pitch), if the setting is on."""
            if not self.show_first:
                self.first_lbl.setText("")
                return
            try:
                from ..phrase import Phrase
                ph = q if isinstance(q, Phrase) else Phrase.from_dict(q)
                n = ph.first_note()
                self.first_lbl.setText(f"First note: {n}" if n else "")
            except Exception as e:
                self.first_lbl.setText("")
                self.app.log(f"{self.LOG}: first note: {type(e).__name__}: {e}")

        def _say(self, text, error=True):
            """Message under the staff AND in the Log (never only on screen)."""
            self.feedback.setStyleSheet("color: red" if error else "")
            self.feedback.setText(text)
            self.app.log(f"{self.LOG}: {text}")

        def show_question(self, q, replay=True):
            self.app.log(f"{self.LOG}: exercise {len(self.ex.items) + 1}/{self.ex.n}: "
                         f"{q.get('title', '')}")
            self._show_staff(self.ex.quiz.check.score)
            self._first_note(q)
            self.feedback.setStyleSheet("")
            if self.mode == "repeat":
                self._hide_staff()
                self.feedback.setText("Listen…")
            else:
                self.feedback.setText(q.get("title", ""))
            self._start_take(delay=START_TAKE_MS)

        def hide_question(self):
            self._stop_take()

        def set_answers(self, enabled):
            self.again_btn.setEnabled(bool(enabled))

        def show_feedback(self, r):
            rep = r.get("report")
            if rep is not None:                  # expected (green / red) + what was played
                try:
                    self._show_report(rep)
                except Exception as e:
                    self.app.log(f"{self.LOG}: report: {type(e).__name__}: {e}")
            elif self.sv is not None:
                self.sv.mark_errors(r.get("errors") or [])
                self.sv.set_position(0)
            self.feedback.setStyleSheet("color: green" if r["correct"] else "color: red")
            self.feedback.setText(f"Recognised {r['answered']}: {r['rating']}   "
                                  f"+{r['points']:.0f}")
            q = self.ex.items[-1]["question"] if self.ex.items else {}
            if q.get("uid"):
                # one attempt on the exercise object; its name shows the best of today
                self.app.phrase_attempt(q["uid"], round(10.0 * r["fraction"], 1),
                                        rating=r.get("rating"))
            d = r.get("detail") or {}
            if d.get("delay") is not None:
                self.app.log(f"{self.LOG}: delay {d['delay'] * 1000:.0f} ms ({d['delay_source']})")

        def free_listen(self):
            return None

        def repeat(self, result=None):
            """Same exercises, same order, same bpm/T (default: the last result)."""
            result = result or self.last_result
            if result is None:
                return None
            q = result.data.get("quiz", {})
            if "bpm" in q:
                self.bpm.setValue(int(round(q["bpm"])))
            self._repeat_questions = list(result.data["questions"])
            return self.start(questions_from=result)

        # ------------------------------------------------------ one take
        def _show_staff(self, score):
            from ..staffview import StaffView
            if self.sv is not None:
                self.sv.stop()
                self.sv.win.setParent(None)
                self.sv.win.deleteLater()
            self.sv = StaffView(score, title=score.title)
            self.sv.win.setWindowFlags(Qt.Widget)
            self.sv.hide_toolbar()                       # the exercise has its own bar (Start…)
            self.staff_box.addWidget(self.sv.win)
            if abs(self._zoom - 1.0) > 1e-6:
                self.sv.zoom(self._zoom)                  # same zoom as the previous staff

        def zoom(self, f):
            """Zoom + / Zoom - of the staff (exercise and report); kept for the next ones."""
            self._zoom = max(0.2, min(5.0, self._zoom * f))
            if self.sv is not None:
                self.sv.zoom(f)
            return self

        def _hide_staff(self):
            if self.sv is not None:
                self.sv.win.hide()

        def _show_report(self, rep):
            """ScoreReport: the exercise with right / wrong notes and, below, what was played."""
            score, colors = rep.to_score()
            self._show_staff(score)
            self.sv.mark(colors)
            self.sv.win.show()

        def _start_take(self, delay=0):
            self._stop_take()
            self._take_state = "waiting"
            self.take_timer.start(int(delay))

        def _take_step(self):
            """Timer steps of one take: 'waiting' -> start stream, 'recording' -> evaluate.
            Any error is written in the Log with its traceback (never silent)."""
            import traceback
            try:
                self._take_step_inner()
            except Exception as e:
                self._take_state = None
                self.feedback.setStyleSheet("color: red")
                self.feedback.setText(f"Error: {type(e).__name__}: {e} (see Log)")
                self.app.log(f"{self.LOG} error:\n" + traceback.format_exc())

        def _take_step_inner(self):
            if self.ex is None or self.ex.state != "asking":
                self.app.log(f"{self.LOG}: take step ignored (state "
                             f"{None if self.ex is None else self.ex.state})")
                self._take_state = None
                return
            pc = self.ex.quiz.check
            if self._take_state == "waiting":
                self._take_state = "recording"
                self.take_timer.start(int(pc.duration * 1000) + 300)   # end of the take
                try:
                    pc.start(**self._devices())
                except Exception as e:
                    self.take_timer.stop()
                    self._take_state = None
                    self.feedback.setStyleSheet("color: red")
                    self.feedback.setText(f"audio: {e}")
                    self.app.log(f"{self.LOG}: {type(e).__name__}: {e}")
                    return
                self.app.log(f"{self.LOG}: recording {pc.duration:.1f} s, stream latency "
                             f"{1000 * (pc._stream_latency or 0):.0f} ms")
                self.feedback.setStyleSheet("")
                if self.ex.quiz.source == "midi":
                    self._open_midi(pc)
                if self.mode == "repeat":
                    self.feedback.setText("Listen… then repeat after the count-in")
                else:
                    self.feedback.setText("Count-in… then play")
                self.sv.clear_marks()
                self.sv.play(bpm=pc.bpm, start=0, count_in=1, click=False, sound=False)
                self.sv.player = _StreamClock(pc)             # cursor on the audio stream clock
            elif self._take_state == "recording":
                self._take_state = None
                self._close_midi()
                self.sv.stop()
                self.feedback.setText("Checking…")
                self.feedback.repaint()
                rec = None
                try:
                    pc.wait(timeout=1.0)        # the take is over: never block the window
                    rec = pc.recording
                except Exception as e:
                    self.app.log(f"{self.LOG}: {type(e).__name__}: {e}")
                if rec is not None:
                    import numpy as np
                    peak = float(np.max(np.abs(rec))) if len(rec) else 0.0
                    self.app.log(f"{self.LOG}: {len(rec)} samples recorded, peak "
                                 f"{20 * np.log10(peak) if peak > 0 else -999:.0f} dBFS"
                                 + ("  — SILENCE: microphone permission or input device? "
                                    "(Settings > Audio…: input level)" if peak < 1e-4 else ""))
                self.answer(rec)

        def _devices(self):
            """Input / output devices of the audio settings (None = system default)."""
            from ..realtime import audio_config
            cfg = audio_config()
            return dict(input_device=cfg.get("input_device") or None,
                        output_device=cfg.get("device") or None)

        def _open_midi(self, pc):
            """Keyboard notes timed on the stream clock; they also sound with the
            soundfont (instrument of the exercise) if Settings > Audio: Keyboard sound."""
            from ..midiin import KeyboardSynth
            from ..realtime import audio_config
            name = self._midi_port_name()
            if name is None:
                return

            def listen(msg, t):
                if msg.type == "note_on" and msg.velocity > 0:
                    pc.midi_message(True, msg.note)
                elif msg.type in ("note_off", "note_on"):
                    pc.midi_message(False, msg.note)
            q = self.ex.quiz.current or {}
            thru = bool(audio_config().get("midi_thru", True))
            try:
                self._midi_in = KeyboardSynth(program=int(q.get("program", 0)), sound=thru,
                                              listener=listen).open(name)
            except Exception as e:                  # no sound: still record the notes
                self.app.log(f"{self.LOG}: keyboard sound off: {type(e).__name__}: {e}")
                self._midi_in = KeyboardSynth(sound=False, listener=listen).open(name)
            self.app.log(f"{self.LOG}: MIDI input '{name}'" + (" (sound on)" if thru else ""))

        def _close_midi(self):
            port = getattr(self, "_midi_in", None)
            if port is not None:
                try:
                    port.close()
                except Exception:
                    pass
                self._midi_in = None

        def _stop_take(self):
            self._close_midi()
            self.take_timer.stop()
            if self._take_state == "recording" and self.ex is not None:
                try:
                    self.ex.quiz.check.stop()
                except Exception:
                    pass
            self._take_state = None
            if self.sv is not None:
                self.sv.stop()

        def again(self):
            """Play the current exercise again (counted as a replay)."""
            if self.ex is None or self.ex.state != "asking":
                return None
            self.ex.replay()
            self._start_take(delay=300)
            return self

        def stop_clicked(self):
            self._stop_take()
            return super().stop_clicked()

        def closing(self):
            self._stop_take()
            super().closing()

    return PlayReadingWidget


def _repeat_class():
    from ..playcheck import EXERCISE_REPEAT

    class ListenRepeatWidget(_widget_class()):
        """Practice > Listen & repeat: the phrase is played (soundfont), then one
        count-in bar, then the player repeats it (trumpet into the microphone, or a
        MIDI keyboard). The staff stays hidden until the end; then the report shows
        the exercise (right / wrong notes) and what was played."""
        kind = EXERCISE_REPEAT
        mode = "repeat"
        LOG = "listen & repeat"

    return ListenRepeatWidget


registry.register(registry.Tool(
    name="play_reading", label="Read & play", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="Quick exercise: every Start = a new random exercise, played on your instrument "
         "(the microphone listens; use loudspeakers, not headphones) or on a MIDI keyboard "
         "(play the written note); every note is checked after one count-in bar. Show "
         "positions: valves / slide positions under the notes."))

registry.register(registry.Tool(
    name="listen_repeat", label="Listen & repeat", category="Practice", kind="session",
    factory=lambda app: _repeat_class()(app),
    help="Quick exercise: every Start = a new random exercise is played: repeat it (your "
         "instrument or a MIDI keyboard). The staff is shown at the end with your notes and "
         "the right ones."))
