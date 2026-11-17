"""
Practice > Fingerings & note names (flash cards, owner 2026-11-08): one note on the staff
(Bb trumpet, written pitch), answer with its valves or its name. Logic in
reading.FlashcardQuiz (portable, no Qt); blocks of N questions, grade 0-10, exercise object
with its results at the end (exercise_ui), as the other quizzes.

From code:  w = app.open_tool('flashcards'); w.start(); w.answer('13'); w.stop_clicked()
"""
from ..reading import FlashcardQuiz, FLASH_EXERCISE, FLASH_MODES, flash_label
from . import registry
from .exercise_ui import exercise_base, CONTROL_FONT_PT, CONTROL_HEIGHT


def _widget_class():
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
                                   QPushButton, QLabel, QComboBox, QCheckBox)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from .interval_reading import svg_pixmap
    from .drills_ui import _note_combo

    class FlashcardWidget(exercise_base()):
        kind = FLASH_EXERCISE

        def __init__(self, app):
            super().__init__()
            self.app = app
            lay = QVBoxLayout(self)
            self._big = QFont()
            self._big.setPointSize(16)
            from ..phrase import instrument_range
            lo, hi = instrument_range("Bb (trumpet)")
            box = QGroupBox("Settings")
            row = QHBoxLayout(box)
            self.mode = QComboBox()
            self.mode.addItems(list(FLASH_MODES))
            self.acc = QCheckBox("Accidentals")
            self.acc.setChecked(True)
            self.lowest = _note_combo(54, 91, lo)
            self.highest = _note_combo(54, 91, hi)
            self.sound = QCheckBox("Play after answering")
            self.sound.setChecked(True)
            for wdg in (QLabel("Answer:"), self.mode, self.acc, QLabel("Lowest:"), self.lowest,
                        QLabel("Highest:"), self.highest, self.sound):
                row.addWidget(wdg)
            row.addStretch()
            from .bar import hscroll
            lay.addWidget(hscroll(box))
            self.build_controls()
            self.staff = QLabel()
            self.staff.setAlignment(Qt.AlignCenter)
            self.staff.setMinimumHeight(240)
            self.staff.setStyleSheet("background: white;")
            lay.addWidget(self.staff)
            self.grid_box = QWidget()
            self.grid = QGridLayout(self.grid_box)
            lay.addWidget(self.grid_box)
            self.buttons = {}
            row = QHBoxLayout()
            self.listen_btn = QPushButton("Listen")
            self.listen_btn.setToolTip("hear the note (costs points while answering)")
            self.listen_btn.clicked.connect(self.replay)
            ctl = QFont()
            ctl.setPointSize(CONTROL_FONT_PT)
            self.listen_btn.setFont(ctl)
            self.listen_btn.setMinimumHeight(CONTROL_HEIGHT)
            row.addWidget(self.listen_btn)
            lay.addLayout(row)
            self.feedback = QLabel("Choose the settings and press Start")
            f2 = QFont()
            f2.setPointSize(20)
            self.feedback.setFont(f2)
            self.feedback.setAlignment(Qt.AlignCenter)
            self.score_lbl = QLabel("")
            self.score_lbl.setFont(self._big)
            self.score_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.feedback)
            lay.addWidget(self.score_lbl)
            lay.addStretch()
            self.mode.currentTextChanged.connect(lambda *_: self._make_buttons())
            self._make_buttons()
            self.set_answers(False)

        def _make_buttons(self, keys=None):
            mode = self.mode.currentText()
            if keys is None:
                keys = FlashcardQuiz(answer=mode).answers()
            for b in self.buttons.values():
                b.setParent(None)
            self.buttons = {}
            cols = 7 if len(keys) == 7 else 6
            for i, k in enumerate(keys):
                b = QPushButton(flash_label(mode, k))
                b.setFont(self._big)
                b.setMinimumHeight(56)
                b.clicked.connect(lambda checked=False, k=k: self.answer(k))
                self.buttons[k] = b
                self.grid.addWidget(b, i // cols, i % cols)

        def apply_settings(self, st):
            if st.get("answer_mode"):
                self.mode.setCurrentText(st["answer_mode"])
            if "accidentals" in st:
                self.acc.setChecked(bool(st["accidentals"]))
            for k, c in (("lowest", self.lowest), ("highest", self.highest)):
                if st.get(k):
                    i = c.findData(int(st[k]))
                    if i >= 0:
                        c.setCurrentIndex(i)

        # ------------------------------------------------------ hooks for exercise_base
        def make_quiz(self):
            lo, hi = self.lowest.currentData(), self.highest.currentData()
            if hi < lo:
                self.feedback.setText("Lowest is above Highest")
                return None
            q = FlashcardQuiz(user=self.app.user, answer=self.mode.currentText(),
                              accidentals=self.acc.isChecked(), lowest=lo, highest=hi,
                              progress=self.app.progress)
            self._make_buttons(q.answers())
            return q

        def show_question(self, q, replay=True):
            self.staff.setPixmap(svg_pixmap(self.ex.quiz.svg(), 220))
            self.feedback.setStyleSheet("")
            self.feedback.setText("Valves?" if self.ex.quiz.answer_mode == "fingering"
                                  else "Which note is it?")

        def hide_question(self):
            self.staff.clear()

        def set_answers(self, enabled):
            for b in self.buttons.values():
                b.setEnabled(enabled)
            self.listen_btn.setEnabled(self.ex is not None and self.ex.state != "paused")

        def show_feedback(self, r):
            if r["correct"]:
                self.feedback.setStyleSheet("color: green")
                self.feedback.setText(f"Right! {r['name']}: {r['label']}   +{r['points']:.0f}  "
                                      f"({r['seconds']:.1f} s)")
            else:
                self.feedback.setStyleSheet("color: red")
                self.feedback.setText(f"No: {r['name']} is {r['label']}  (you said "
                                      f"{flash_label(self.ex.quiz.answer_mode, r['answered'])})")
            if self.sound.isChecked():
                self.free_listen()

        def free_listen(self):
            if self.ex is not None:
                try:
                    self.ex.quiz.play()
                except Exception as e:
                    self.app.log(f"sound: {e}")

    return FlashcardWidget


registry.register(registry.Tool(
    name="flashcards", label="Fingerings & note names", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="Flash cards: a note on the staff, answer with its valves or its name. Blocks of N "
         "questions, graded 0-10."))
