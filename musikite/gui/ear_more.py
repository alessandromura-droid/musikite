"""
Practice > Scales and modes by ear, Scale degrees by ear, Cadences by ear (owner,
2026-11-19). Logic in eartraining (ScaleQuiz, DegreeQuiz, CadenceQuiz; no Qt); blocks of N
questions, grade 0-10, exercise object ◆ with its results at the end (exercise_ui), as the
intervals and the chord qualities. One widget class for the three: a SPEC says what is
asked, the settings shown and how the quiz is made.

From code:  w = app.open_tool('scale_ear'); w.start(); w.answer('dorian'); w.stop_clicked()
"""
from .. import eartraining as et
from . import registry
from .exercise_ui import exercise_base, CONTROL_FONT_PT, CONTROL_HEIGHT

# kind: (tab title, question text, answers {key: label}, check list of the answers asked
#        (settings key) or None, (label, choices) of the "mode" list, second list or None,
#        quiz class, help)
SPECS = {
    "scale_ear": dict(
        label="Scales and modes by ear", ask="Listen…  which scale is it?",
        answers=et.SCALE_LABELS, checks="scales", defaults=et.DEFAULT_SCALES,
        mode=("Direction:", et.SCALE_DIRECTIONS), second=None, quiz=et.ScaleQuiz,
        help="A scale or a mode is played from a random note (up, or up and down): name it. "
             "Blocks of N questions, graded 0-10."),
    "scale_degrees": dict(
        label="Scale degrees by ear", ask="Listen to the cadence…  which degree is the note?",
        answers={str(k): v for k, v in et.DEGREE_LABELS.items()}, checks=None, defaults=(),
        mode=("Key:", et.KEY_MODES), second=("degrees", "Degrees:", et.DEGREE_SETS),
        quiz=et.DegreeQuiz,
        help="A cadence (I IV V7 I) sets a random key, then one note is played: which degree "
             "of the key is it? Diatonic = the notes of the key, chromatic = all twelve. "
             "Blocks of N questions, graded 0-10."),
    "cadences": dict(
        label="Cadences by ear", ask="Listen…  which cadence ends it?",
        answers=et.CADENCE_LABELS, checks="cadences", defaults=et.DEFAULT_CADENCES,
        mode=("Key:", et.KEY_MODES), second=None, quiz=et.CadenceQuiz,
        help="Four chords in a random key: name the cadence at the end — perfect (V–I), "
             "plagal (IV–I), half (ending on V), deceptive (V–vi). Blocks of N questions, "
             "graded 0-10."),
}


def _widget_class(kind):
    from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
                                   QPushButton, QLabel, QComboBox, QCheckBox)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    spec = SPECS[kind]

    class EarWidget(exercise_base()):
        def __init__(self, app):
            super().__init__()
            self.kind = kind
            self.app = app
            lay = QVBoxLayout(self)
            box = QGroupBox("Settings")
            g = QGridLayout(box)
            self.checks = {}
            row0 = 0
            if spec["checks"]:
                for i, k in enumerate(spec["answers"]):
                    c = QCheckBox(spec["answers"][k])
                    c.setChecked(k in spec["defaults"])
                    self.checks[k] = c
                    g.addWidget(c, i // 5, i % 5)
                row0 = (len(spec["answers"]) + 4) // 5
            self.mode = QComboBox()
            self.mode.addItems(list(spec["mode"][1]))
            self.second = None
            row = QHBoxLayout()
            row.addWidget(QLabel(spec["mode"][0]))
            row.addWidget(self.mode)
            if spec["second"]:
                self.second = QComboBox()
                self.second.addItems(list(spec["second"][2]))
                row.addWidget(QLabel(spec["second"][1]))
                row.addWidget(self.second)
            self.instr = QComboBox()
            self.instr.addItems(list(et.INSTRUMENTS))
            row.addWidget(QLabel("Instrument:"))
            row.addWidget(self.instr)
            row.addStretch()
            g.addLayout(row, row0, 0, 1, 5)
            from .bar import hscroll
            lay.addWidget(hscroll(box))
            self.build_controls()
            big = QFont()
            big.setPointSize(16)
            grid = QGridLayout()
            self.buttons = {}
            per_row = 6 if kind == "scale_degrees" else 4
            for i, k in enumerate(spec["answers"]):
                b = QPushButton(spec["answers"][k])
                b.setFont(big)
                b.setMinimumHeight(64)
                b.clicked.connect(lambda checked=False, k=k: self.answer(k))
                self.buttons[k] = b
                grid.addWidget(b, i // per_row, i % per_row)
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
            self.feedback.setWordWrap(True)
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
            if spec["checks"] and st.get(spec["checks"]):
                for k, c in self.checks.items():
                    c.setChecked(k in st[spec["checks"]])
            if st.get("mode"):
                self.mode.setCurrentText(st["mode"])
            if self.second is not None and st.get(spec["second"][0]):
                self.second.setCurrentText(st[spec["second"][0]])
            if st.get("instrument"):
                self.instr.setCurrentText(st["instrument"])

        # ------------------------------------------------------ hooks for exercise_base
        def make_quiz(self):
            from ..midi import Midi
            if Midi._default_sf2 is None and not self.app.soundfont_dialog():
                self.feedback.setText("A soundfont is needed (Settings > Soundfont…)")
                return None
            kw = dict(user=self.app.user, mode=self.mode.currentText(),
                      instrument=self.instr.currentText(), progress=self.app.progress)
            if spec["checks"]:
                sel = [k for k, c in self.checks.items() if c.isChecked()]
                if not sel:
                    self.feedback.setText("Select at least one answer to ask")
                    return None
                kw[spec["checks"]] = sel
            if self.second is not None:
                kw[spec["second"][0]] = self.second.currentText()
            return spec["quiz"](**kw)

        def show_question(self, q, replay=True):
            self.feedback.setStyleSheet("")
            self.feedback.setText(spec["ask"])

        def hide_question(self):
            pass

        def set_answers(self, enabled):
            allowed = ({str(a) for a in self.ex.quiz.answers()} if self.ex is not None
                       else None)
            for k, b in self.buttons.items():
                b.setEnabled(enabled and (allowed is None or k in allowed))
            self.replay_btn.setEnabled(self.ex is not None and self.ex.state != "paused")

        def show_feedback(self, r):
            said = spec["answers"].get(str(r["answered"]), str(r["answered"]))
            if r["correct"]:
                self.feedback.setStyleSheet("color: green")
                self.feedback.setText(f"Right! {r['name']}   +{r['points']:.0f}  "
                                      f"({r['seconds']:.1f} s)")
            else:
                self.feedback.setStyleSheet("color: red")
                self.feedback.setText(f"No, it was {r['name']}  (you said {said})")

        def free_listen(self):
            if self.ex is not None:
                self.ex.quiz.replay()

    return EarWidget


for _kind, _spec in SPECS.items():
    registry.register(registry.Tool(
        name=_kind, label=_spec["label"], category="Practice", kind="session",
        factory=lambda app, k=_kind: _widget_class(k)(app), help=_spec["help"]))
