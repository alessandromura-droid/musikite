"""
Exercise: a block of N questions of a quiz (interval ear training, interval
reading, …) with timing, points, grade, pause/resume/stop and repeat.
Portable core: no Qt (the GUI only displays and forwards clicks).

Container of every exercise type: the type ("quiz") gives the questions and
judges the answers; Exercise handles the block of N questions, time, pause,
points, grade, stop, repeat and the result. A quiz implements
    new(play=False) -> question dict (JSON-able)   ask(question)   answer(value) -> dict
    (asked, answered, correct, ...); optional: response_delay(q), replay(),
    points(cfg, r, seconds, replays, question), max_points(cfg), pool_size,
    settings() (stored in the result).
The answer can be a button key (intervals) or anything else the quiz knows how
to judge (Read & play: the microphone recording).

Scoring (settings of the current user, settings.json key 'exercise', and per
exercise type under 'exercise_kinds' -> kind, which override the general ones):
    points = base * mode_factor * time_factor * replay_factor   (wrong answer: 0)
    mode_factor   harmonic_factor if the interval is harmonic, else melodic_factor
    time_factor   1 up to fast_s seconds, then linear down to slow_factor at slow_s,
                  slow_factor after
    replay_factor replay_factor ** (number of replays)
    grade = 10 * points / (n_questions * max points)   (questions not answered: 0)

    ex = Exercise(quiz, kind='intervals')      # quiz: IntervalQuiz / IntervalReadingQuiz
    ex.start()                                 # first question
    ex.answer(7) ... ex.next()
    ex.pause(); ex.resume(); ex.stop()         # stop = interrupted
    ex.result                                  # ExerciseResult once finished/stopped
    ex2 = ex.result.repeat(quiz)               # same questions, new attempt

ExerciseResult is the DATA of a finished block (progress archive, practice diary); it is no
longer an object in Objects (owner, 2026-11-07: there is no result object): the GUI puts
it into the exercise object (tasks.Task.from_block / add_block).
"""
import copy
import datetime as _dt
import time

DEFAULTS = dict(n_questions=10, base=100.0, harmonic_factor=1.2, melodic_factor=1.0,
                fast_s=3.0, slow_s=15.0, slow_factor=0.5, replay_factor=0.8)
KINDS = ("intervals", "interval_reading", "chords", "flashcards", "play_reading",
         "listen_repeat")
KIND_LABELS = {"intervals": "Intervals (ear training)", "interval_reading": "Interval reading",
               "chords": "Chord qualities (ear training)",
               "flashcards": "Fingerings & note names",
               "play_reading": "Read & play", "listen_repeat": "Listen & repeat"}
# settings that exist only for some exercise types (besides DEFAULTS)
KIND_DEFAULTS = {
    "play_reading": dict(bars=8, bpm=90, input="Microphone", show_first_note=False,
                         click=True),
    "listen_repeat": dict(bars=2, bpm=90, input="Microphone", show_first_note=True,
                          click=True),
}
RESULT_VERSION = 2          # data format of ExerciseResult (1 = before the per-kind settings)


def kind_keys(kind):
    return list(DEFAULTS) + list(KIND_DEFAULTS.get(kind, {}))


def exercise_settings(kind=None):
    """Settings of an exercise type: every type has its own complete set
    (defaults: DEFAULTS + KIND_DEFAULTS[kind]); kind=None: the general defaults."""
    from .progress import settings
    s = dict(DEFAULTS)
    st = settings()
    s.update({k: v for k, v in st.get("exercise", {}).items() if k in DEFAULTS})  # old files
    if kind:
        s.update(KIND_DEFAULTS.get(kind, {}))
        s.update({k: v for k, v in st.get("exercise_kinds", {}).get(kind, {}).items()
                  if k in kind_keys(kind)})
    return s


def set_exercise_settings(kind=None, **changes):
    """Change the settings of one exercise type (kind=None: of all of them)."""
    from .progress import save_setting, settings
    kinds = [kind] if kind else list(KINDS)
    allk = dict(settings().get("exercise_kinds", {}))
    for k in kinds:
        bad = set(changes) - set(kind_keys(k))
        if bad and kind:
            raise ValueError(f"unknown setting(s) for {k}: {', '.join(sorted(bad))}; "
                             f"known: {', '.join(kind_keys(k))}")
        cur = exercise_settings(k)
        cur.update({x: v for x, v in changes.items() if x in kind_keys(k)})
        allk[k] = cur
    save_setting("exercise_kinds", allk)
    return exercise_settings(kind) if kind else allk


def clear_exercise_settings(kind):
    """Back to the defaults for one exercise type."""
    from .progress import save_setting, settings
    allk = dict(settings().get("exercise_kinds", {}))
    allk.pop(kind, None)
    save_setting("exercise_kinds", allk)


def is_harmonic(q):
    return bool(q.get("harmonic")) or q.get("mode") == "harmonic"


def question_points(cfg, correct, seconds, replays, harmonic):
    if not correct:
        return 0.0
    mode = cfg["harmonic_factor"] if harmonic else cfg["melodic_factor"]
    fast, slow, low = cfg["fast_s"], cfg["slow_s"], cfg["slow_factor"]
    if seconds <= fast:
        tf = 1.0
    elif seconds >= slow:
        tf = low
    else:
        tf = 1.0 - (1.0 - low) * (seconds - fast) / (slow - fast)
    return round(cfg["base"] * mode * tf * cfg["replay_factor"] ** replays, 1)


def max_points(cfg):
    return cfg["base"] * max(cfg["harmonic_factor"], cfg["melodic_factor"])


class Exercise:
    def __init__(self, quiz, kind, settings=None, questions=None, user=None):
        """questions: list of question dicts to ask again (repeat); None = new random ones."""
        self.quiz = quiz
        self.kind = kind
        self.cfg = dict(settings or exercise_settings(kind))
        self.user = user if user is not None else getattr(quiz, "user", None)
        self.fixed = [copy.deepcopy(q) for q in questions] if questions else None
        self.n = len(self.fixed) if self.fixed else int(self.cfg["n_questions"])
        if not self.fixed and getattr(quiz, "pool_size", None):
            self.n = min(self.n, int(quiz.pool_size))     # fewer exercises than N: all of them
        self.items = []                   # one dict per answered question
        self.state = "ready"              # ready, asking, feedback, paused, finished, stopped
        self.started = None
        self._t0 = None                   # perf_counter start of the running time
        self._run = 0.0                   # running seconds accumulated before the last pause
        self._q0 = None                   # perf_counter when the current answer time starts
        self._qacc = 0.0                  # answer seconds accumulated before a pause
        self._replays = 0
        self._paused_from = None
        self.result = None

    # ---------------------------------------------------------- time
    def elapsed(self):
        """Exercise time (pauses excluded)."""
        if self._t0 is None:
            return self._run
        return self._run + (time.perf_counter() - self._t0)

    def question_elapsed(self):
        if self._q0 is None:
            return self._qacc
        return self._qacc + max(0.0, time.perf_counter() - self._q0)

    # ---------------------------------------------------------- flow
    def start(self):
        """Draw all the questions (unless repeating) and ask the first one."""
        if not self.fixed:
            self.fixed = []
            for _ in range(self.n):
                try:
                    q = self.quiz.new(play=False)
                except TypeError:
                    q = self.quiz.new()
                self.fixed.append(copy.deepcopy(q))
            self.quiz.current = None
        self.started = _dt.datetime.now().isoformat(timespec="seconds")
        self._t0 = time.perf_counter()
        return self.next()

    def next(self):
        """Ask the next question (or finish the exercise)."""
        if self.state in ("finished", "stopped", "paused"):
            return None
        if len(self.items) >= self.n:
            return self._finish("finished")
        q = self.quiz.ask(self.fixed[len(self.items)])
        delay = self.quiz.response_delay(q) if hasattr(self.quiz, "response_delay") else 0.0
        self._q0 = time.perf_counter() + delay
        self._qacc = 0.0
        self._replays = 0
        self.state = "asking"
        return q

    def replay(self):
        if self.state != "asking":
            return None
        self._replays += 1
        if hasattr(self.quiz, "replay"):
            return self.quiz.replay()
        return self.quiz.play()

    def answer(self, key):
        if self.state != "asking":
            return None
        secs = self.question_elapsed()
        q = copy.deepcopy(self.quiz.current)
        r = self.quiz.answer(key)
        if hasattr(self.quiz, "points"):
            pts = round(float(self.quiz.points(self.cfg, r, secs, self._replays, q)), 1)
        else:
            pts = question_points(self.cfg, r["correct"], secs, self._replays, is_harmonic(q))
        item = dict(question=q, asked=r["asked"], answered=r["answered"], correct=r["correct"],
                    seconds=round(secs, 2), replays=self._replays, points=pts)
        if r.get("detail") is not None:
            item["detail"] = r["detail"]
        self.items.append(item)
        self._q0 = None
        self.state = "feedback"
        r = dict(r, points=pts, seconds=item["seconds"], replays=self._replays,
                 number=len(self.items), of=self.n, last=len(self.items) >= self.n)
        return r

    def pause(self):
        if self.state not in ("asking", "feedback"):
            return self
        self._paused_from = self.state
        self._run = self.elapsed()
        self._t0 = None
        if self._q0 is not None:
            self._qacc = self.question_elapsed()
            self._q0 = None
        self.state = "paused"
        return self

    def resume(self):
        if self.state != "paused":
            return self
        self._t0 = time.perf_counter()
        self.state = self._paused_from
        if self.state == "asking":
            self._q0 = time.perf_counter()
        return self

    def stop(self):
        """Interrupt: the questions not answered count 0."""
        if self.state in ("finished", "stopped"):
            return self.result
        return self._finish("stopped")

    def _finish(self, how):
        self._run = self.elapsed()
        self._t0 = self._q0 = None
        self.state = how
        self.result = ExerciseResult.from_exercise(self, complete=(how == "finished"))
        progress = getattr(self.quiz, "progress", None)
        if progress is not None and self.user:
            progress.add_exercise(self.result.data)
        try:                                   # practice diary (intervals: one attempt per block)
            from .diary import record_block
            record_block(self.result.data)
        except Exception:
            pass
        return self.result

    # ---------------------------------------------------------- score
    def points(self):
        return round(sum(i["points"] for i in self.items), 1)

    def max_points(self):
        if hasattr(self.quiz, "max_points"):
            return float(self.quiz.max_points(self.cfg))
        return max_points(self.cfg)

    def grade(self):
        return round(10.0 * self.points() / (self.n * self.max_points()), 1)

    def correct(self):
        return sum(i["correct"] for i in self.items)


class ExerciseResult:
    """Data of a finished (or interrupted) block; goes into its exercise object
    (tasks.Task), can be repeated."""

    def __init__(self, data):
        self.data = data
        data.setdefault("version", 1)

    @classmethod
    def from_exercise(cls, ex, complete):
        q = ex.quiz
        settings = {k: getattr(q, k) for k in ("mode", "instrument", "weights", "answer_mode",
                                               "accidentals", "clef", "display", "numbers")
                    if hasattr(q, k)}
        if hasattr(q, "settings"):
            settings.update(q.settings())
        return cls(dict(version=RESULT_VERSION, kind=ex.kind, user=ex.user, start=ex.started,
                        session=getattr(q, "session", None), complete=complete,
                        n_questions=ex.n, answered=len(ex.items), correct=ex.correct(),
                        seconds=round(ex.elapsed(), 1), points=ex.points(), grade=ex.grade(),
                        scoring=dict(ex.cfg), quiz=settings,
                        questions=copy.deepcopy(ex.fixed or []),
                        items=copy.deepcopy(ex.items)))

    # ---------------------------------------------------------- info
    @property
    def grade(self):
        return self.data["grade"]

    @property
    def label(self):
        """Name of the exercise type (e.g. 'Rhythm reading')."""
        try:
            from .diary import KIND_LABELS
            return KIND_LABELS.get(self.data["kind"], self.data["kind"])
        except Exception:
            return self.data["kind"]

    @property
    def title(self):
        d = self.data
        when = (d["start"] or "")[5:16].replace("T", " ")
        tag = "" if d["complete"] else " (stopped)"
        return f"{self.label} – {d['user'] or 'no user'} – {when} – {d['grade']:.1f}{tag}"

    def summary(self):
        d = self.data
        m, s = divmod(int(d["seconds"]), 60)
        if d.get("drill"):                      # drills: best of the attempts
            last = d["items"][-1]["result"] if d["items"] else ""
            return (f"{d['drill']['title']}\nGrade {d['grade']:.1f}/10 ({d['rating']}), best of "
                    f"{len(d['items'])} attempt{'s' if len(d['items']) != 1 else ''}   "
                    f"time {m}:{s:02d}\nlast: {last}")
        if d.get("rating"):                     # read & play: notes recognised
            return (f"Grade {d['grade']:.1f}/10   recognised {d['correct']}/{d['n_questions']}: "
                    f"{d['rating']}   time {m}:{s:02d}")
        return (f"Grade {d['grade']:.1f}/10   correct {d['correct']}/{d['n_questions']}   "
                f"points {d['points']:.0f}   time {m}:{s:02d}"
                + ("" if d["complete"] else f"   (stopped after {d['answered']})"))

    def table(self):
        import pandas as pd
        items = self.data["items"]
        if items and "asked" not in items[0]:   # other exercises (read & play): items as they are
            return pd.DataFrame(items)
        rows = [dict(n=i + 1, asked=it["asked"], answered=it["answered"], correct=it["correct"],
                     seconds=it["seconds"], replays=it["replays"], points=it["points"])
                for i, it in enumerate(self.data["items"])]
        return pd.DataFrame(rows)

    def repeat(self, quiz, shuffle=None):
        """New Exercise with the same questions (all of them, also the ones not
        reached if it was stopped) and the same scoring. Intervals and interval
        reading (owner's rule): the same questions in ANOTHER ORDER (shuffle=None:
        shuffled for those kinds, as they are for the others)."""
        import random
        qs = copy.deepcopy(self.data["questions"])
        if shuffle is None:
            shuffle = self.data["kind"] in ("intervals", "interval_reading", "chords",
                                            "flashcards")
        if shuffle and len(qs) > 1:
            old = list(qs)
            for _ in range(5):                    # another order, if there is one
                random.shuffle(qs)
                if qs != old:
                    break
        return Exercise(quiz, self.data["kind"], self.data["scoring"], questions=qs)

    def __repr__(self):
        return f"ExerciseResult({self.title})"
