"""
Practice > Intervals: interval recognition by ear (session tool).

An exercise is a block of N questions (Settings > Exercises…): Play starts it
and then toggles Pause / Resume, Stop leaves it (questions not answered count 0).
Points depend on correctness, answer time, replays and harmonic/melodic; the
grade (0-10) and every answer are saved for the current user. Start makes a new
exercise: at its end it is an exercise object in Objects (Exercises) with this result;
Repeat = the same questions in another order (one more attempt on the same object).
Double click on that object opens it again (bind_task).

From code:  w = app.open_tool('intervals'); w.start(); w.answer(7); w.stop_clicked()
"""
from ..eartraining import IntervalQuiz, INTERVALS, DEFAULT_WEIGHTS, MODES, INSTRUMENTS, EXERCISE
from . import registry
from .exercise_ui import exercise_base, CONTROL_FONT_PT, CONTROL_HEIGHT

ABBR = {1: "m2", 2: "M2", 3: "m3", 4: "M3", 5: "P4", 6: "TT", 7: "P5", 8: "m6", 9: "M6",
        10: "m7", 11: "M7", 12: "P8"}


def _widget_class():
    from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
                                   QPushButton, QLabel, QComboBox, QCheckBox)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    class IntervalsWidget(exercise_base()):
        kind = EXERCISE

        def __init__(self, app):
            super().__init__()
            self.app = app
            lay = QVBoxLayout(self)

            box = QGroupBox("Settings")
            g = QGridLayout(box)
            self.checks = {}
            for i, k in enumerate(range(1, 13)):
                c = QCheckBox(INTERVALS[k])
                c.setChecked(DEFAULT_WEIGHTS[k] > 0)
                self.checks[k] = c
                g.addWidget(c, i // 6, i % 6)
            self.mode = QComboBox()
            self.mode.addItems(MODES)
            self.instr = QComboBox()
            self.instr.addItems(list(INSTRUMENTS))
            row = QHBoxLayout()
            for wdg in (QLabel("Mode:"), self.mode, QLabel("Instrument:"), self.instr):
                row.addWidget(wdg)
            row.addStretch()
            g.addLayout(row, 2, 0, 1, 6)
            from .bar import hscroll
            lay.addWidget(hscroll(box))

            self.build_controls()

            big = QFont()
            big.setPointSize(16)
            grid = QGridLayout()
            self.buttons = {}
            for i, k in enumerate(range(1, 13)):
                b = QPushButton(f"{INTERVALS[k]}\n({ABBR[k]})")
                b.setFont(big)
                b.setMinimumHeight(70)
                b.clicked.connect(lambda checked=False, k=k: self.answer(k))
                self.buttons[k] = b
                grid.addWidget(b, i // 4, i % 4)
            lay.addLayout(grid)

            row = QHBoxLayout()
            self.replay_btn = QPushButton("Replay")
            self.replay_btn.setToolTip("hear it again (costs points while answering)")
            self.replay_btn.clicked.connect(self.replay)
            self.hist_btn = QPushButton("History")
            self.hist_btn.clicked.connect(self.history)
            ctl = QFont()
            ctl.setPointSize(CONTROL_FONT_PT)
            for b in (self.replay_btn, self.hist_btn):
                b.setFont(ctl)
                b.setMinimumHeight(CONTROL_HEIGHT)
                row.addWidget(b)
            lay.addLayout(row)

            self.feedback = QLabel("Choose the settings and press Start")
            f2 = QFont()
            f2.setPointSize(22)
            self.feedback.setFont(f2)
            self.feedback.setAlignment(Qt.AlignCenter)
            self.score_lbl = QLabel("")
            self.score_lbl.setFont(big)
            self.score_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.feedback)
            lay.addWidget(self.score_lbl)
            lay.addStretch()
            self.set_answers(False)

        def apply_settings(self, st):
            """Settings of an exercise object (bind_task)."""
            w = {int(k): v for k, v in (st.get("weights") or {}).items()}
            if w:
                for k, c in self.checks.items():
                    c.setChecked(w.get(k, 0) > 0)
            if st.get("mode"):
                self.mode.setCurrentText(st["mode"])
            if st.get("instrument"):
                self.instr.setCurrentText(st["instrument"])

        # ------------------------------------------------------ hooks for exercise_base
        def make_quiz(self):
            from ..midi import Midi
            if Midi._default_sf2 is None and not self.app.soundfont_dialog():
                self.feedback.setText("A soundfont is needed (Settings > Soundfont…)")
                return None
            weights = {k: (DEFAULT_WEIGHTS[k] or 1) if c.isChecked() else 0
                       for k, c in self.checks.items()}
            if not any(weights.values()):
                self.feedback.setText("Select at least one interval")
                return None
            return IntervalQuiz(user=self.app.user, weights=weights, mode=self.mode.currentText(),
                                instrument=self.instr.currentText(), progress=self.app.progress)

        def show_question(self, q, replay=True):
            self.feedback.setStyleSheet("")
            self.feedback.setText("Listen…  which interval is it?")

        def hide_question(self):
            pass

        def set_answers(self, enabled):
            allowed = None
            if self.ex is not None:
                allowed = {k for k, w in self.ex.quiz.weights.items() if w > 0}
            for k, b in self.buttons.items():
                b.setEnabled(enabled and (allowed is None or k in allowed))
            self.replay_btn.setEnabled(self.ex is not None and self.ex.state != "paused")

        def show_feedback(self, r):
            who = self.app.user or ""
            if r["correct"]:
                self.feedback.setStyleSheet("color: green")
                self.feedback.setText(f"Right{', ' + who if who else ''}! {r['name']}   "
                                      f"+{r['points']:.0f}  ({r['seconds']:.1f} s)")
            else:
                self.feedback.setStyleSheet("color: red")
                self.feedback.setText(f"No, it was a {r['name']}  "
                                      f"(you said {INTERVALS[r['answered']]})")

        def free_listen(self):
            if self.ex is not None:
                self.ex.quiz.replay()

        def history(self):
            from .history import history_widget
            user = self.app.user
            if user is None:
                self.feedback.setText("Select a user to see the history")
                return None
            w = history_widget(self.app.progress, user, EXERCISE, "intervals",
                               lambda k: INTERVALS.get(int(k), str(k)))
            return self.app.add_tab(w, f"History – {user}")

    return IntervalsWidget


registry.register(registry.Tool(
    name="intervals", label="Intervals (ear training)", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="An interval is played; choose its name. Blocks of N questions, graded 0-10."))
