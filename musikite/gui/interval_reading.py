"""
Practice > Interval reading: two notes on the staff, name the interval
(the visual version of Practice > Intervals). Logic in reading.IntervalReadingQuiz
(portable, no Qt); this widget only shows the SVG and the buttons.

Blocks of N questions with Start / Pause / Resume and Stop, grade 0-10 (see exercise.py).

From code:  w = app.open_tool('interval_reading'); w.start(); w.answer('M3'); w.stop_clicked()
"""
from ..reading import (IntervalReadingQuiz, QUALITY_ANSWERS, NUMBER_ANSWERS, DISPLAYS, CLEFS,
                       EXERCISE, answer_label)
from . import registry
from .exercise_ui import exercise_base, CONTROL_FONT_PT, CONTROL_HEIGHT


def svg_pixmap(svg, height):
    """SVG string (Verovio) -> QPixmap of the given height, aspect kept."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QPixmap, QPainter, QColor
    from PySide6.QtCore import QByteArray, Qt
    from ..engrave import _unwrap, _flatten_texts
    r = QSvgRenderer(QByteArray(_flatten_texts(_unwrap(svg)).encode()))
    size = r.defaultSize()
    w = max(1, int(size.width() * height / max(1, size.height())))
    pm = QPixmap(w, height)
    pm.fill(QColor("white"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    return pm


def _widget_class():
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
                                   QPushButton, QLabel, QComboBox, QCheckBox)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    class IntervalReadingWidget(exercise_base()):
        kind = EXERCISE

        def __init__(self, app):
            super().__init__()
            self.app = app
            lay = QVBoxLayout(self)
            big = QFont()
            big.setPointSize(15)
            self._big = big

            box = QGroupBox("Settings")
            row = QHBoxLayout(box)
            self.mode = QComboBox()
            self.mode.addItems(["number + quality", "number only"])
            self.acc = QCheckBox("Accidentals")
            self.clef = QComboBox()
            self.clef.addItems(list(CLEFS))
            self.display = QComboBox()
            self.display.addItems(list(DISPLAYS))
            self.sound = QCheckBox("Play after answering")
            self.sound.setChecked(True)
            for wdg in (QLabel("Answer:"), self.mode, self.acc, QLabel("Clef:"), self.clef,
                        QLabel("Notes:"), self.display, self.sound):
                row.addWidget(wdg)
            row.addStretch()
            from .bar import hscroll
            lay.addWidget(hscroll(box))

            self.build_controls()

            self.staff = QLabel()
            self.staff.setAlignment(Qt.AlignCenter)
            self.staff.setMinimumHeight(260)
            self.staff.setStyleSheet("background: white;")
            lay.addWidget(self.staff)

            self.grid_box = QWidget()
            self.grid = QGridLayout(self.grid_box)
            lay.addWidget(hscroll(self.grid_box))
            self.buttons = {}

            row = QHBoxLayout()
            self.listen_btn = QPushButton("Listen")
            self.listen_btn.setToolTip("hear it (costs points while answering)")
            self.listen_btn.clicked.connect(self.replay)
            self.hist_btn = QPushButton("History")
            self.hist_btn.clicked.connect(self.history)
            ctl = QFont()
            ctl.setPointSize(CONTROL_FONT_PT)
            for b in (self.listen_btn, self.hist_btn):
                b.setFont(ctl)
                b.setMinimumHeight(CONTROL_HEIGHT)
                row.addWidget(b)
            lay.addLayout(row)
            self.feedback = QLabel("Choose the settings and press Start")
            f2 = QFont()
            f2.setPointSize(20)
            self.feedback.setFont(f2)
            self.feedback.setAlignment(Qt.AlignCenter)
            self.feedback.setWordWrap(True)            # never widens the tab
            self.score_lbl = QLabel("")
            self.score_lbl.setFont(big)
            self.score_lbl.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.feedback)
            lay.addWidget(self.score_lbl)
            lay.addStretch()
            self._make_buttons(QUALITY_ANSWERS)
            self.set_answers(False)

        def _make_buttons(self, keys):
            for b in self.buttons.values():
                b.setParent(None)
            self.buttons = {}
            cols = 7 if len(keys) == 7 else 5
            for i, k in enumerate(keys):
                b = QPushButton(answer_label(k) + ("" if k.isdigit() else f"\n({k})"))
                b.setFont(self._big)
                b.setMinimumHeight(56)
                b.clicked.connect(lambda checked=False, k=k: self.answer(k))
                self.buttons[k] = b
                self.grid.addWidget(b, i // cols, i % cols)

        def apply_settings(self, st):
            """Settings of an exercise object (bind_task)."""
            if st.get("answer_mode"):
                self.mode.setCurrentText("number only" if st["answer_mode"] == "number"
                                         else "number + quality")
            if "accidentals" in st:
                self.acc.setChecked(bool(st["accidentals"]))
            if st.get("clef"):
                self.clef.setCurrentText(st["clef"])
            if st.get("display"):
                self.display.setCurrentText(st["display"])

        # ------------------------------------------------------ hooks for exercise_base
        def make_quiz(self):
            mode = "number" if self.mode.currentText() == "number only" else "quality"
            q = IntervalReadingQuiz(user=self.app.user, answer=mode,
                                    accidentals=self.acc.isChecked(),
                                    clef=self.clef.currentText(),
                                    display=self.display.currentText(),
                                    progress=self.app.progress)
            self._make_buttons(q.answers())
            return q

        def show_question(self, q, replay=True):
            self.staff.setPixmap(svg_pixmap(self.ex.quiz.svg(), 240))
            self.feedback.setStyleSheet("")
            self.feedback.setText("Which interval is it?")

        def hide_question(self):
            self.staff.clear()

        def set_answers(self, enabled):
            for b in self.buttons.values():
                b.setEnabled(enabled)
            self.listen_btn.setEnabled(self.ex is not None and self.ex.state != "paused")

        def show_feedback(self, r):
            if r["correct"]:
                self.feedback.setStyleSheet("color: green")
                self.feedback.setText(f"Right! {r['full']}   +{r['points']:.0f}  ({r['seconds']:.1f} s)")
            else:
                self.feedback.setStyleSheet("color: red")
                self.feedback.setText(f"No, it is a {r['full']}  (you said {answer_label(r['answered'])})")
            if self.sound.isChecked():
                self.free_listen()

        def free_listen(self):
            if self.ex is not None:
                try:
                    self.ex.quiz.play()
                except Exception as e:
                    self.app.log(f"sound: {e}")

        def history(self):
            from .history import history_widget
            user = self.app.user
            if user is None:
                self.feedback.setText("Select a user to see the history")
                return None
            w = history_widget(self.app.progress, user, EXERCISE, "interval reading", answer_label)
            return self.app.add_tab(w, f"History – {user} (reading)")

    return IntervalReadingWidget


registry.register(registry.Tool(
    name="interval_reading", label="Interval reading (staff)", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="Two notes on the staff: name the interval. Results saved per user."))
