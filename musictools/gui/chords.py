"""
Practice > Chord qualities (ear training, owner 2026-11-08): a chord is played, name its
quality. Logic in eartraining.ChordQuiz (no Qt); blocks of N questions, grade 0-10, exercise
object with its results at the end (exercise_ui), as the intervals.

From code:  w = app.open_tool('chords'); w.start(); w.answer('m7'); w.stop_clicked()
"""
from ..eartraining import (ChordQuiz, CHORD_EXERCISE, CHORD_LABELS, DEFAULT_CHORDS, CHORD_MODES,
                           INSTRUMENTS)
from . import registry
from .exercise_ui import exercise_base, CONTROL_FONT_PT, CONTROL_HEIGHT


def _widget_class():
    from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
                                   QPushButton, QLabel, QComboBox, QCheckBox)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    class ChordsWidget(exercise_base()):
        kind = CHORD_EXERCISE

        def __init__(self, app):
            super().__init__()
            self.app = app
            lay = QVBoxLayout(self)
            box = QGroupBox("Settings")
            g = QGridLayout(box)
            self.checks = {}
            for i, k in enumerate(CHORD_LABELS):
                c = QCheckBox(CHORD_LABELS[k])
                c.setChecked(k in DEFAULT_CHORDS)
                self.checks[k] = c
                g.addWidget(c, i // 5, i % 5)
            self.mode = QComboBox()
            self.mode.addItems(list(CHORD_MODES))
            self.inv = QCheckBox("Inversions")
            self.instr = QComboBox()
            self.instr.addItems(list(INSTRUMENTS))
            row = QHBoxLayout()
            for wdg in (QLabel("Mode:"), self.mode, self.inv, QLabel("Instrument:"), self.instr):
                row.addWidget(wdg)
            row.addStretch()
            g.addLayout(row, 3, 0, 1, 5)
            from .bar import hscroll
            lay.addWidget(hscroll(box))
            self.build_controls()
            big = QFont()
            big.setPointSize(16)
            grid = QGridLayout()
            self.buttons = {}
            for i, k in enumerate(CHORD_LABELS):
                b = QPushButton(CHORD_LABELS[k])
                b.setFont(big)
                b.setMinimumHeight(64)
                b.clicked.connect(lambda checked=False, k=k: self.answer(k))
                self.buttons[k] = b
                grid.addWidget(b, i // 4, i % 4)
            lay.addLayout(grid)
            row = QHBoxLayout()
            self.replay_btn = QPushButton("Replay")
            self.replay_btn.setToolTip("hear it again (costs points while answering)")
            self.replay_btn.clicked.connect(self.replay)
            ctl = QFont()
            ctl.setPointSize(CONTROL_FONT_PT)
            self.replay_btn.setFont(ctl)
            self.replay_btn.setMinimumHeight(CONTROL_HEIGHT)
            row.addWidget(self.replay_btn)
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
            if st.get("qualities"):
                for k, c in self.checks.items():
                    c.setChecked(k in st["qualities"])
            if st.get("mode"):
                self.mode.setCurrentText(st["mode"])
            if "inversions" in st:
                self.inv.setChecked(bool(st["inversions"]))
            if st.get("instrument"):
                self.instr.setCurrentText(st["instrument"])

        # ------------------------------------------------------ hooks for exercise_base
        def make_quiz(self):
            from ..midi import Midi
            if Midi._default_sf2 is None and not self.app.soundfont_dialog():
                self.feedback.setText("A soundfont is needed (Settings > Soundfont…)")
                return None
            qual = [k for k, c in self.checks.items() if c.isChecked()]
            if not qual:
                self.feedback.setText("Select at least one chord quality")
                return None
            return ChordQuiz(user=self.app.user, qualities=qual, mode=self.mode.currentText(),
                             instrument=self.instr.currentText(),
                             inversions=self.inv.isChecked(), progress=self.app.progress)

        def show_question(self, q, replay=True):
            self.feedback.setStyleSheet("")
            self.feedback.setText("Listen…  which chord is it?")

        def hide_question(self):
            pass

        def set_answers(self, enabled):
            allowed = set(self.ex.quiz.qualities) if self.ex is not None else None
            for k, b in self.buttons.items():
                b.setEnabled(enabled and (allowed is None or k in allowed))
            self.replay_btn.setEnabled(self.ex is not None and self.ex.state != "paused")

        def show_feedback(self, r):
            if r["correct"]:
                self.feedback.setStyleSheet("color: green")
                self.feedback.setText(f"Right! {r['name']}   +{r['points']:.0f}  "
                                      f"({r['seconds']:.1f} s)")
            else:
                self.feedback.setStyleSheet("color: red")
                self.feedback.setText(f"No, it was {r['name']}  (you said "
                                      f"{CHORD_LABELS.get(r['answered'], r['answered'])})")

        def free_listen(self):
            if self.ex is not None:
                self.ex.quiz.replay()

    return ChordsWidget


registry.register(registry.Tool(
    name="chords", label="Chord qualities (ear training)", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="A chord is played (block or arpeggio, optionally inverted): name its quality. Blocks "
         "of N questions, graded 0-10."))
