"""
Shared controls of exercise widgets: Start (then Pause / Resume) and Stop
(always on: leaves the exercise), timer, question counter, automatic advance,
result object at the end. The logic is in exercise.Exercise (no Qt).

A tool widget subclasses the class returned by exercise_base() and implements:
    make_quiz()            quiz object with the current settings
    show_question(q)       display / play the question
    hide_question()        while paused or idle
    set_answers(enabled)   enable the answer buttons
    show_feedback(r)       after an answer (r from Exercise.answer)
    kind                   'intervals', 'interval_reading', …
    apply_settings(s)      (optional) put the settings of an exercise object in the controls

No result object (owner, 2026-11-07): Start in the tab of Practice makes a NEW exercise; at
its end it becomes an exercise object (tasks.Task) with this result; Repeat adds an attempt
to the same object (same questions, another order). A tab opened on an exercise object
(double click, routine: bind_task) does that exercise: Start = its questions again.
"""
CONTROL_FONT_PT = 13          # Replay / Listen / History: normal buttons, as the Objects panel
CONTROL_HEIGHT = 0
# Read & play / Listen & repeat show the GRADE of the take: 5 s more to read it before the
# next exercise (owner, 2026-11-09: "after seeing the grade wait at least 5 s more"; it was
# 3 s / 6 s for Read & play, 1.3 s / 3.5 s for Listen & repeat)
GRADE_EXTRA_MS = 5000
CORRECT_DELAY_MS = {"play_reading": 3000 + GRADE_EXTRA_MS, "listen_repeat": 3000 + GRADE_EXTRA_MS,
                    "default": 1300}
WRONG_DELAY_MS = {"intervals": 6000, "play_reading": 6000 + GRADE_EXTRA_MS,
                  "listen_repeat": 6000 + GRADE_EXTRA_MS, "default": 3500}

# a quiz that plays something after the answer (Chord qualities: block + arpeggio after a
# wrong answer, `quiz.feedback_s`): the next question waits for its end + this (owner,
# 2026-11-14)
FEEDBACK_PAD_S = 1.0

def _fmt(t):
    m, s = divmod(int(max(0.0, t)), 60)
    return f"{m:2d}:{s:02d}"


def exercise_base():
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QFont

    class ExerciseBase(QWidget):
        kind = "exercise"

        def build_controls(self, layout=None, extra=()):
            """Start (then Pause / Resume), Stop, Repeat (+ extra buttons) and the clock:
            they go in the action bar of the main window (self.bar), at the top."""
            from .bar import action_bar
            self.clock = QLabel("")
            mono = QFont("Menlo")
            mono.setStyleHint(QFont.Monospace)
            mono.setFixedPitch(True)
            mono.setPointSize(18)
            self.clock.setFont(mono)
            self.clock.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            items = [("Start", self.play_clicked, "start the exercise (then Pause / Resume)"),
                     ("Stop", self.stop_clicked, "leave the exercise"),
                     ("Repeat", lambda: self.repeat(), "same questions again (intervals: in another order); a better grade replaces the one of today")] + list(extra)
            if getattr(self, "result_object", True):
                items.append(("Keep", self.keep, "put this exercise in Objects now (it goes "
                                                 "there anyway at its end); its attempts go "
                                                 "into it"))
            self.bar, btn = action_bar(items, right=self.clock)
            self.play_btn, self.stop_btn, self.repeat_btn = btn["Start"], btn["Stop"], btn["Repeat"]
            self.bar_buttons = btn
            self.ex = None
            self.last_result = None
            self.task = None                  # exercise object of the attempts (tasks.Task)
            self.bound_task = None            # tab opened on this exercise object
            self.advance = QTimer(self)
            self.advance.setSingleShot(True)
            self.advance.timeout.connect(self._advance)
            self._advance_left = None
            self.ticker = QTimer(self)
            self.ticker.setInterval(250)
            self.ticker.timeout.connect(self._tick)
            self.repeat_btn.setEnabled(False)

        # ------------------------------------------------------ buttons
        def play_clicked(self):
            ex = self.ex
            if ex is None or ex.state in ("finished", "stopped"):
                return self.start()
            if ex.state == "paused":
                return self.resume()
            return self.pause()

        def stop_clicked(self):
            if self.ex is not None and self.ex.state not in ("finished", "stopped"):
                self.advance.stop()
                self._finish(self.ex.stop())
            else:
                self.hide_question()
                self.set_answers(False)
            return self

        # ------------------------------------------------------ flow
        def start(self, questions_from=None):
            from ..exercise import Exercise
            from ..tasks import Task
            if questions_from is None and self.bound_task is not None:
                questions_from = self.bound_task
            quiz = self.make_quiz()
            if quiz is None:
                return None
            if isinstance(questions_from, Task):        # the same exercise object again
                self.task = questions_from
                self.ex = questions_from.exercise(quiz)
            elif questions_from is not None:
                self.ex = questions_from.repeat(quiz)
            else:
                self.task = None                         # a new exercise = a new object
                self.ex = Exercise(quiz, self.kind)
            if self.app.user is None:
                self.app.log("no user selected: results are not saved")
            self.score_lbl.setText("")
            q = self.ex.start()
            self.play_btn.setText("Pause")
            self.repeat_btn.setEnabled(False)
            self.ticker.start()
            self.show_question(q)
            self.set_answers(True)
            return self

        def repeat(self, result=None):
            """The same exercise again (default: the exercise object of the last block;
            intervals: the same questions in another order); one more attempt on it."""
            result = result or self.task or self.last_result
            if result is None:
                return None
            return self.start(questions_from=result)

        def bind_task(self, task):
            """This tab does this exercise object (double click / routine): its settings
            are shown, Start = its questions again (new ones if it has none yet)."""
            self.bound_task = self.task = task
            if hasattr(self, "apply_settings"):
                try:
                    self.apply_settings(task.settings)
                except Exception as e:
                    self.app.log(f"{task.title}: settings: {type(e).__name__}: {e}")
            self.feedback.setStyleSheet("")
            self.feedback.setText(f"{task.title}\npress Start")
            return self

        def keep(self):
            """KEEP (owner, 2026-11-13): the exercise of this tab into Objects at once, also
            before its end (it is put there anyway when it ends); the attempts then go
            into it. Not on disk: Save does that."""
            from ..tasks import Task
            from ..exercise import ExerciseResult
            if self.task is not None:
                self.app.log(f"{self.task.title}: already in Objects")
                return self.task
            if self.ex is None:
                self.app.log(f"{self.kind}: press Start first (the questions are drawn at Start)")
                return None
            try:
                d = ExerciseResult.from_exercise(self.ex, complete=False).data
                self.task = Task(d["kind"], settings=d.get("quiz"), questions=d.get("questions"),
                                 scoring=d.get("scoring"))
                name = self.app.add_object(self.task, self.task.title)
                self.app.log(f"exercise kept in Objects: {name}")
            except Exception as e:
                self.app.log(f"{self.kind}: keep: {type(e).__name__}: {e}")
            return self.task

        def busy(self):
            """An exercise is going on (not stopped / finished): the routine's ◀ ▶ wait."""
            return self.ex is not None and self.ex.state in ("ready", "asking", "feedback",
                                                             "paused")

        def pause(self):
            if self.ex is None:
                return self
            if self.advance.isActive():
                self._advance_left = self.advance.remainingTime()
                self.advance.stop()
            self.ex.pause()
            self.play_btn.setText("Resume")
            self.hide_question()
            self.set_answers(False)
            self.feedback.setStyleSheet("")
            self.feedback.setText("Paused")
            return self

        def resume(self):
            if self.ex is None:
                return self
            self.ex.resume()
            self.play_btn.setText("Pause")
            if self.ex.state == "asking":
                self.show_question(self.ex.quiz.current, replay=False)
                self.set_answers(True)
                self.feedback.setText("Go on…")
            elif self._advance_left is not None:
                self.advance.start(max(0, self._advance_left))
            self._advance_left = None
            return self

        def answer(self, key):
            if self.ex is None or self.ex.state != "asking":
                return None
            r = self.ex.answer(key)
            self.set_answers(False)
            self.show_feedback(r)
            ok = self.ex.correct()
            self.score_lbl.setText(f"{ok} of {len(self.ex.items)} right   "
                                   f"points {self.ex.points():.0f}")
            table = CORRECT_DELAY_MS if r["correct"] else WRONG_DELAY_MS
            delay = table.get(self.kind, table["default"])
            heard = float(getattr(self.ex.quiz, "feedback_s", 0.0) or 0.0)
            if heard > 0:                    # a replay after the answer: wait for it + 1 s
                delay = max(delay, int((heard + FEEDBACK_PAD_S) * 1000))
            self.advance.start(delay)
            return r

        def replay(self):
            """Hear the question again: during the question it costs points."""
            if self.ex is not None and self.ex.state == "asking":
                return self.ex.replay()
            return self.free_listen()

        def free_listen(self):
            return None

        def _advance(self):
            if self.ex is None or self.ex.state != "feedback":
                return
            q = self.ex.next()
            if self.ex.state == "finished":
                return self._finish(self.ex.result)
            self.show_question(q)
            self.set_answers(True)

        def _finish(self, result):
            self.ticker.stop()
            self._tick()
            self.play_btn.setText("Start")
            self.set_answers(False)
            self.last_result = result
            self.repeat_btn.setEnabled(True)
            self.feedback.setStyleSheet("color: navy")
            self.feedback.setText(result.summary())
            if getattr(self, "result_object", True):
                self._store(result)
            else:                       # e.g. Read & play: the grades go on the exercise objects
                self.app.log(f"{self.kind}: {result.summary()}")
            return result

        def _store(self, result):
            """The block into its exercise object: a new object (Start in Practice) or one
            more attempt on the object of this tab."""
            from ..tasks import Task
            try:
                if self.task is None:
                    self.task = Task.from_block(result.data)
                    name = self.app.add_object(self.task, self.task.title)
                    self.app.log(f"exercise saved: {name} ({result.grade:.1f})")
                else:
                    self.task.add_block(result.data)
                    self.app.log(f"{self.task.title}: attempt {result.grade:.1f}")
                self.app.attempt_added(self.task)
            except Exception as e:
                self.app.log(f"{self.kind}: exercise object: {type(e).__name__}: {e}")

        def _tick(self):
            ex = self.ex
            if ex is None:
                return
            k = min(len(ex.items) + (1 if ex.state in ("asking", "paused") else 0), ex.n)
            self.clock.setText(f"question {k:2d}/{ex.n}  {_fmt(ex.question_elapsed())}  "
                               f"total {_fmt(ex.elapsed())}")

        def user_changed(self, name):
            if self.ex is not None and self.ex.state not in ("finished", "stopped"):
                self.stop_clicked()
            self.feedback.setText(f"User: {name}. Press Start")

        def closing(self):
            self.advance.stop()
            self.ticker.stop()
            if self.ex is not None and self.ex.state not in ("finished", "stopped"):
                self._finish(self.ex.stop())

    return ExerciseBase
