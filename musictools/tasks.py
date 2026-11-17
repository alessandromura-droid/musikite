"""
Exercise objects with their results, and routines (owner's rules, 2026-11-07). No Qt.

THERE IS NO RESULT OBJECT: an exercise that has been done is an exercise with results.
Every exercise object keeps its attempts per user (`results` = {user: [attempt, ...]},
attempt = dict(time, grade, ...)); doing it again (Again / Repeat / double click) adds
an attempt to the same object; the name in Objects shows the grade.

- Phrase / ExerciseSet (phrase.py): Read & play, Listen & repeat (attempt = one take).
- Task (here): intervals and interval reading (a block of questions + its settings and
  scoring; doing it again = the same questions in another order) and the drills (long
  tones, scales & arpeggios, lip slurs, rhythm reading: the exercise + its settings).
- Routine (here): a sequence of exercises done one after the other, every day; the items
  are COPIES of the exercises, each with a flag "new each time" (a new exercise of the same
  kind every day: drills, interval blocks, Read & play phrases made from duets).

TO DO (TODO_RULE, owner: "never done today", may change later): an exercise is to do when
the current user has no attempt today (the day starts at 04:00, diary.day_of).
The grade shown is the best of today only (none if not done today).
"""
import copy
import datetime as _dt
import json
import random
import uuid

QUIZ_KINDS = ("intervals", "interval_reading", "chords", "flashcards")
DRILL_KINDS = ("long_tones", "scales", "lip_slurs", "rhythm", "chord_arpeggios")
TODO_RULES = ("never done today",)
TODO_RULE = TODO_RULES[0]
TASK_FORMAT = "musikite-task"
ROUTINE_FORMAT = "musikite-routine"
GROUP_FORMAT = "musikite-group"


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def _day(when=None):
    from .diary import day_of
    return day_of(when)


# ---------------------------------------------------------------- results of any exercise
def attempts(obj, user):
    return list((getattr(obj, "results", None) or {}).get(user or "", []))


def add_result(obj, user, grade, **extra):
    """One attempt of `user` on an exercise object (Phrase, Task)."""
    if getattr(obj, "results", None) is None:
        obj.results = {}
    a = dict(time=extra.pop("time", None) or _now(), grade=None if grade is None
             else round(float(grade), 1), **extra)
    obj.results.setdefault(user or "", []).append(a)
    return a


def graded(obj):
    """Has this exercise a grade? (Play over MIDI: no, "n/a")."""
    return getattr(obj, "graded", True)


# Exercises without results (Play over MIDI) done in this session: {(uid, user)} (owner,
# 2026-11-08: "it keeps track of nothing"; in a routine, played to the end = done until the
# app is closed)
SESSION_DONE = set()


def mark_done(obj, user):
    SESSION_DONE.add((obj.uid, user or ""))


def best_today(obj, user):
    """Best grade of today (None: not done today). A group / routine: mean of its graded
    items when all are done today (an item without grade only has to be done)."""
    items = _parts(obj)
    if items is not None:
        if not items or not all(done_today(o, user) for o in items):
            return None
        g = [best_today(o, user) for o in items if graded(o)]
        return None if not g or None in g else round(sum(g) / len(g), 1)
    today = _day()
    g = [a["grade"] for a in attempts(obj, user)
         if a.get("grade") is not None and _day(a["time"]) == today]
    return max(g) if g else None


def last_grade(obj, user):
    items = _parts(obj)
    if items is not None:
        g = [last_grade(o, user) for o in items]
        g = [x for x in g if x is not None]
        return round(sum(g) / len(g), 1) if g else None
    a = [x for x in attempts(obj, user) if x.get("grade") is not None]
    if a:
        return a[-1]["grade"]
    old = getattr(obj, "grades", None) or {}            # phrases before 2026-11-07
    return old.get(user or "")


def done_today(obj, user):
    items = _parts(obj)
    if items is not None:
        return bool(items) and all(done_today(o, user) for o in items)
    if not graded(obj):
        return (obj.uid, user or "") in SESSION_DONE
    today = _day()
    return any(_day(a["time"]) == today for a in attempts(obj, user))


def todo_rule():
    """The rule chosen in Settings > Exercises (settings key 'todo_rule')."""
    try:
        from .progress import settings
        r = settings().get("todo_rule")
    except Exception:
        r = None
    return r if r in TODO_RULES else TODO_RULE


def to_do(obj, user):
    """Is this exercise to do for this user? (todo_rule(); for now: never done today)."""
    return not done_today(obj, user)


def shown_grade(obj, user):
    """Grade shown with the object (Objects, routine runner): ONLY the best of today, None
    if not done today (owner, 2026-11-13: a grade of yesterday next to today's ones is
    misleading; it was the best of today, else the last one)."""
    return best_today(obj, user)


def is_exercise(obj):
    from .phrase import Phrase, ExerciseSet
    from .playover import PlayOver
    return isinstance(obj, (Phrase, ExerciseSet, Task, Routine, PlayOver))


def _parts(obj):
    from .phrase import ExerciseSet
    if isinstance(obj, ExerciseSet):
        return list(obj.phrases)
    if isinstance(obj, Routine):
        return [it["obj"] for it in obj.items]
    return None


# ---------------------------------------------------------------- Task
def kind_label(kind):
    from .diary import KIND_LABELS
    return KIND_LABELS.get(kind, kind)


class Task:
    """An exercise of a kind that is not a phrase: intervals / interval reading (questions,
    quiz settings, scoring) or a drill (drill dict + settings of the tab)."""

    def __init__(self, kind, title="", settings=None, questions=None, scoring=None, drill=None,
                 uid=None, results=None, created=None):
        if kind not in QUIZ_KINDS + DRILL_KINDS:
            raise ValueError(f"unknown exercise kind {kind}")
        self.kind = kind
        self.settings = dict(settings or {})
        self.questions = copy.deepcopy(list(questions or []))
        self.scoring = dict(scoring or {})
        self.drill = copy.deepcopy(drill)
        self.uid = uid or uuid.uuid4().hex[:12]
        self.results = copy.deepcopy(results or {})
        self.created = created or _now()
        self.title = title or self.default_title()

    @property
    def instrument(self):
        """The instrument the exercise is played on (owner, 2026-11-08): drills -> their
        phrase ('trumpet', 'piano'); flash cards -> 'trumpet' (Bb trumpet fingerings);
        ear training / interval reading / rhythm -> None (any instrument)."""
        if self.drill:
            if self.kind == "rhythm":
                return None
            return (self.drill.get("phrase") or {}).get("instrument") or \
                self.drill_obj().phrase.instrument
        return "trumpet" if self.kind == "flashcards" else None

    @property
    def is_quiz(self):
        return self.kind in QUIZ_KINDS

    @property
    def label(self):
        return kind_label(self.kind)

    def default_title(self):
        s = self.settings
        if self.drill:
            return self.drill.get("title") or self.label
        if self.kind == "intervals":
            from .eartraining import INTERVALS
            w = {int(k): v for k, v in (s.get("weights") or {}).items()}
            names = [INTERVALS.get(k, str(k)) for k in sorted(w) if w[k]]
            what = ", ".join(names) if 0 < len(names) <= 4 else f"{len(names)} intervals"
            return f"Intervals – {s.get('mode', '')} – {what}"
        if self.kind == "interval_reading":
            return (f"Interval reading – {s.get('clef', 'treble')} clef – "
                    f"{s.get('display', '')}".rstrip(" –"))
        if self.kind == "chords":
            from .eartraining import CHORD_LABELS
            q = [CHORD_LABELS.get(x, x) for x in s.get("qualities") or []]
            what = ", ".join(q) if 0 < len(q) <= 3 else f"{len(q)} qualities"
            return f"Chord qualities – {s.get('mode', '')} – {what}"
        if self.kind == "flashcards":
            from .theory import note_name
            rng = (f" {note_name(s['lowest'])}-{note_name(s['highest'])}"
                   if s.get("lowest") and s.get("highest") else "")
            return (f"Flash cards – {s.get('answer_mode', 'fingering')}{rng}"
                    + (" – accidentals" if s.get("accidentals") else ""))
        return self.label

    def __repr__(self):
        return f"Task({self.kind}, '{self.title}')"

    # ---------------------------------------------------------- doing it
    def exercise(self, quiz, shuffle=True):
        """Intervals / interval reading: an Exercise with THE SAME QUESTIONS in another
        order (owner's rule); no questions yet (new each time) = new ones are drawn."""
        from .exercise import Exercise
        qs = copy.deepcopy(self.questions)
        if shuffle and len(qs) > 1:
            old = list(qs)
            for _ in range(5):
                random.shuffle(qs)
                if qs != old:
                    break
        return Exercise(quiz, self.kind, self.scoring or None, questions=qs or None)

    def drill_obj(self):
        from .drills import Drill
        return Drill.from_dict(self.drill)

    def regenerate(self, seed=None):
        """A new exercise of the same kind and settings (routine items 'new each time');
        the results stay (they are the item's)."""
        if self.drill:
            from .drills import make
            self.drill = make(self.kind, self.settings, seed=seed).to_dict()
            self.title = self.default_title()
        else:
            self.questions = []                   # new questions drawn at Start
        return self

    def add_block(self, data, user=None):
        """Intervals / interval reading: a finished (or stopped) block (ExerciseResult.data);
        the questions are kept when the exercise had none yet."""
        if not self.questions:
            self.questions = copy.deepcopy(data.get("questions") or [])
        if not self.scoring:
            self.scoring = dict(data.get("scoring") or {})
        return add_result(self, user if user is not None else data.get("user"), data["grade"],
                          time=data.get("start"), complete=data.get("complete", True),
                          correct=data.get("correct"), n_questions=data.get("n_questions"),
                          answered=data.get("answered"), seconds=data.get("seconds"),
                          points=data.get("points"), items=copy.deepcopy(data.get("items")))

    def add_take(self, r, pc=None, user=None):
        """Drills: one take (r = Drill.evaluate); long-tone curves kept small."""
        notes = []
        for n in (r.get("detail") or {}).get("notes") or []:
            c = [(round(t, 2), None if v is None else round(v, 1))
                 for t, v in n.get("curve", [])[::2]]
            notes.append(dict(n, curve=c))
        extra = dict(rating=r.get("rating"), result=r.get("text"),
                     colors={str(k): v for k, v in (r.get("colors") or {}).items()},
                     seconds=round(float(getattr(pc, "duration", 0.0) or 0.0), 1))
        if notes:
            extra["notes"] = notes
        if pc is not None:
            self._pc = pc                         # last take kept in memory (audio)
        return add_result(self, user, r["grade"], **extra)

    def summary(self, user):
        a = attempts(self, user)
        if not a:
            return f"{self.label}: not done yet"
        bt, last = best_today(self, user), a[-1]
        txt = (f"{self.label}: {len(a)} attempt{'s' if len(a) != 1 else ''}, last "
               f"{last['grade']:.1f}" + (f", best today {bt:.1f}" if bt is not None else ", "
                                         "not done today"))
        if last.get("result"):
            txt += f"\nlast: {last['result']}"
        elif last.get("n_questions"):
            txt += (f"\nlast: correct {last.get('correct')}/{last.get('n_questions')}"
                    + ("" if last.get("complete", True) else " (stopped)"))
        return txt

    # ---------------------------------------------------------- data
    def to_dict(self):
        return dict(kind=self.kind, title=self.title, settings=self.settings,
                    questions=self.questions, scoring=self.scoring, drill=self.drill,
                    uid=self.uid, results=self.results, created=self.created)

    @classmethod
    def from_dict(cls, d):
        return cls(d["kind"], d.get("title", ""), d.get("settings"), d.get("questions"),
                   d.get("scoring"), d.get("drill"), d.get("uid"), d.get("results"),
                   d.get("created"))

    def copy(self):
        """Same exercise, no results, new identity (routine items)."""
        d = copy.deepcopy(self.to_dict())
        d["uid"], d["results"], d["created"] = None, None, None
        return Task.from_dict(d)

    @classmethod
    def from_block(cls, data):
        """New exercise from a finished interval block (Practice: Start = a new exercise)."""
        t = cls(data["kind"], settings=data.get("quiz"), questions=data.get("questions"),
                scoring=data.get("scoring"))
        t.add_block(data)
        return t

    @classmethod
    def from_drill(cls, drill, settings=None):
        return cls(drill.kind, drill.title, settings, drill=drill.to_dict())


# ---------------------------------------------------------------- old result objects
def from_result(d):
    """An old ExerciseResult (workspace or .json, before 2026-11-07) as an exercise with
    its result: drills and interval blocks -> Task; Read & play / Listen & repeat blocks
    -> a group of their phrases (when the phrases are in it). ValueError otherwise."""
    kind = d.get("kind")
    user = d.get("user") or ""
    if d.get("drill"):
        t = Task(kind, d["drill"].get("title", ""), d.get("settings"), drill=d["drill"])
        for it in d.get("items") or []:
            add_result(t, user, it.get("grade"), time=it.get("time"), rating=it.get("rating"),
                       result=it.get("result"), colors=it.get("colors") or {},
                       **({"notes": it["notes"]} if it.get("notes") else {}))
        return t
    if kind in QUIZ_KINDS:
        t = Task(kind, settings=d.get("quiz"), questions=d.get("questions"),
                 scoring=d.get("scoring"))
        t.add_block(d, user)
        return t
    qs = [q for q in d.get("questions") or [] if isinstance(q, dict) and "notes" in q]
    if kind in ("play_reading", "listen_repeat") and qs:
        from .phrase import Phrase, ExerciseSet
        phrases = [Phrase.from_dict({k: v for k, v in q.items()
                                     if k in Phrase.__init__.__code__.co_varnames})
                   for q in qs]
        return ExerciseSet(phrases, title=f"{kind_label(kind)} – {d.get('start', '')[:10]}",
                           purpose="reading" if kind == "play_reading" else "repeat")
    raise ValueError(f"old result of kind {kind} without its exercise")


# ---------------------------------------------------------------- Routine
def regenerable(obj):
    """Can this exercise be made new every day? drills, interval blocks, phrases from duets."""
    from .phrase import Phrase
    if isinstance(obj, Task):
        return True
    return isinstance(obj, Phrase) and bool((getattr(obj, "origin", None) or {}).get("duet"))


class Routine:
    """A sequence of exercises done one after the other (every day the same routine).
    items: [dict(obj=Task|Phrase, fresh=bool, made=day of the last regeneration)]."""

    def __init__(self, title="Routine", items=None, uid=None, created=None):
        self.title = title
        self.items = []
        self.uid = uid or uuid.uuid4().hex[:12]
        self.created = created or _now()
        for it in items or []:
            self.items.append(dict(it))

    def __len__(self):
        return len(self.items)

    def __repr__(self):
        return f"Routine('{self.title}', {len(self.items)} exercises)"

    @classmethod
    def from_objects(cls, objs, title="Routine", fresh=False):
        """Copies of the exercises (groups: their phrases), in this order."""
        from .phrase import ExerciseSet
        r = cls(title)
        for o in objs:
            for x in (o.phrases if isinstance(o, ExerciseSet) else [o]):
                r.add(x, fresh)
        return r

    def add_new(self, kind, at=None, fresh=True):
        """A NEW exercise of a kind made with the user's last settings (routine editor >
        Add > New): drills, blocks of questions, 'duet' (a piece of a new duet); 'new each
        time' by default, so a daily routine is different every day."""
        return self.add(new_exercise(kind), fresh, at)

    def add(self, obj, fresh=False, at=None):
        """A COPY of an exercise (a group: its phrases; a routine: its items) at the end or
        at position `at`; returns the number of items added."""
        from .phrase import Phrase, ExerciseSet
        if isinstance(obj, (Routine, ExerciseSet)):
            parts = ([(it["obj"], it.get("fresh", False)) for it in obj.items]
                     if isinstance(obj, Routine) else [(p, fresh) for p in obj.phrases])
            n = 0
            for o, f in parts:
                n += self.add(o, f, None if at is None else at + n)
            return n
        from .playover import PlayOver
        if not isinstance(obj, (Task, Phrase, PlayOver)):
            raise TypeError(f"not an exercise: {type(obj).__name__}")
        c = obj.copy()
        if isinstance(obj, Phrase):
            c.origin = copy.deepcopy(getattr(obj, "origin", None))
        item = dict(obj=c, fresh=bool(fresh) and regenerable(c), made=None)
        if at is None:
            self.items.append(item)
        else:
            self.items.insert(max(0, min(int(at), len(self.items))), item)
        return 1

    def move(self, i, j):
        if 0 <= i < len(self.items) and 0 <= j < len(self.items):
            self.items.insert(j, self.items.pop(i))
        return self

    def remove(self, i):
        self.items.pop(i)
        return self

    def set_fresh(self, i, fresh):
        self.items[i]["fresh"] = bool(fresh) and regenerable(self.items[i]["obj"])
        return self.items[i]["fresh"]

    def next_to_do(self, user, after=-1):
        """Index of the next item not done today (after `after`), None if all done."""
        n = len(self.items)
        for k in list(range(after + 1, n)) + list(range(0, after + 1)):
            if to_do(self.items[k]["obj"], user):
                return k
        return None

    def prepare(self, i, user=None, seed=None):
        """Before doing item i: a 'new each time' item not yet made today is made new
        (the same day it stays the same, so it can be improved)."""
        it = self.items[i]
        today = _day()
        if not it.get("fresh") or it.get("made") == today or done_today(it["obj"], user):
            return it["obj"]
        o = it["obj"]
        if isinstance(o, Task):
            o.regenerate(seed)
        else:
            from .phrase import exercise_from_duet
            new = exercise_from_duet(seed=seed, **o.origin["duet"])
            new.results = o.results               # the results are the item's
            new.practice_bpm = o.practice_bpm
            it["obj"] = new
        it["made"] = today
        return it["obj"]

    def summary(self, user):
        done = sum(done_today(it["obj"], user) for it in self.items)
        g = best_today(self, user)
        return (f"{done} of {len(self.items)} done today"
                + (f", grade of the routine {g:.1f}" if g is not None else ""))

    def to_dict(self):
        from .phrase import Phrase
        from .playover import PlayOver
        items = []
        for it in self.items:
            o = it["obj"]
            items.append(dict(type="Phrase" if isinstance(o, Phrase) else
                              "PlayOver" if isinstance(o, PlayOver) else "Task",
                              data=o.to_dict(), fresh=it.get("fresh", False),
                              made=it.get("made")))
        return dict(title=self.title, uid=self.uid, created=self.created, items=items)

    @classmethod
    def from_dict(cls, d):
        from .phrase import Phrase
        items = []
        from .playover import PlayOver
        for it in d.get("items") or []:
            o = Phrase.from_dict(it["data"]) if it["type"] == "Phrase" else \
                PlayOver.from_dict(it["data"]) if it["type"] == "PlayOver" else \
                Task.from_dict(it["data"])
            items.append(dict(obj=o, fresh=it.get("fresh", False), made=it.get("made")))
        return cls(d.get("title", "Routine"), items, d.get("uid"), d.get("created"))


class TaskGroup(Routine):
    """A GROUP of exercises ◆ made together (owner, 2026-11-08: "5 lip slurs must be grouped",
    as the Read & play groups ▦): the exercises THEMSELVES (not copies), shown expandable in
    Objects; double click = the runner (one after the other); results stay on each exercise.
    `phrases` = the exercises (same interface as ExerciseSet for the Objects tree)."""

    def __init__(self, title="Group", tasks=(), uid=None, created=None, items=None):
        super().__init__(title, items or [dict(obj=t, fresh=False, made=None) for t in tasks],
                         uid, created)
        self.source = ""

    @property
    def phrases(self):
        return [it["obj"] for it in self.items]

    @phrases.setter
    def phrases(self, objs):
        keep = {id(it["obj"]): it for it in self.items}
        self.items = [keep.get(id(o)) or dict(obj=o, fresh=False, made=None) for o in objs]

    def __repr__(self):
        return f"TaskGroup('{self.title}', {len(self.items)} exercises)"

    def to_dict(self):
        return dict(super().to_dict(), group=True)

    @classmethod
    def from_dict(cls, d):
        r = Routine.from_dict(d)
        return cls(r.title, uid=r.uid, created=r.created, items=r.items)


def group_or_single(tasks, title):
    """Generate with "How many" (owner): one exercise -> itself; more -> ONE group."""
    tasks = list(tasks)
    if len(tasks) == 1:
        return tasks[0]
    return TaskGroup(f"{title} – {len(tasks)} exercises", tasks)


# ---------------------------------------------------------------- files
def to_file_dict(obj):
    from .playover import PlayOver, FORMAT as PLAYOVER_FORMAT
    if isinstance(obj, PlayOver):
        return dict(format=PLAYOVER_FORMAT, **obj.to_dict())
    if isinstance(obj, TaskGroup):
        return dict(format=GROUP_FORMAT, **obj.to_dict())
    if isinstance(obj, Task):
        return dict(format=TASK_FORMAT, **obj.to_dict())
    if isinstance(obj, Routine):
        return dict(format=ROUTINE_FORMAT, **obj.to_dict())
    raise TypeError(f"not a task / routine: {type(obj).__name__}")


def from_file_dict(d):
    """Task / Routine of a .json (also an old result: converted)."""
    if d.get("format") == TASK_FORMAT:
        return Task.from_dict(d)
    if d.get("format") == ROUTINE_FORMAT:
        return Routine.from_dict(d)
    if d.get("format") == GROUP_FORMAT:
        return TaskGroup.from_dict(d)
    from .playover import PlayOver, FORMAT as PLAYOVER_FORMAT
    if d.get("format") == PLAYOVER_FORMAT:
        return PlayOver.from_dict(d)
    if "kind" in d and "items" in d:
        return from_result(d)
    raise ValueError("not an exercise file")


def save(obj, path):
    """Task: .mke; Routine: .mkr (owner, 2026-11-08); both a zip of the compact JSON
    (default) — or .json (compact) if asked."""
    from .phrase import write_exercise_file, EXERCISE_EXT, ROUTINE_EXT
    is_routine = isinstance(obj, Routine) and not isinstance(obj, TaskGroup)
    return write_exercise_file(to_file_dict(obj), path,
                               ROUTINE_EXT if is_routine else EXERCISE_EXT)


def load(path):
    from .phrase import read_exercise_file
    return from_file_dict(read_exercise_file(path))


# ---------------------------------------------------------------- generation (Generate)
def new_quiz_tasks(kind, count=1, n_questions=10, seed=None, **quiz_settings):
    """Blocks of questions to do (intervals, interval reading, chord qualities, flash cards): `count` exercises of n_questions each (drawn now)."""
    from .exercise import exercise_settings
    rng = random.Random(seed)
    out = []
    for _ in range(int(count)):
        if kind == "intervals":
            from .eartraining import IntervalQuiz
            q = IntervalQuiz(seed=rng.randrange(1 << 30), **quiz_settings)
            settings = dict(mode=q.mode, instrument=q.instrument, weights=q.weights)
            qs = [q.new(play=False) for _ in range(int(n_questions))]
        elif kind == "chords":
            from .eartraining import ChordQuiz
            q = ChordQuiz(seed=rng.randrange(1 << 30), **quiz_settings)
            settings = q.settings()
            qs = [q.new(play=False) for _ in range(int(n_questions))]
        elif kind == "flashcards":
            from .reading import FlashcardQuiz
            q = FlashcardQuiz(seed=rng.randrange(1 << 30), **quiz_settings)
            settings = q.settings()
            qs = [q.new() for _ in range(int(n_questions))]
        else:
            from .reading import IntervalReadingQuiz
            q = IntervalReadingQuiz(seed=rng.randrange(1 << 30), **quiz_settings)
            settings = dict(answer_mode=q.answer_mode, accidentals=q.accidentals, clef=q.clef,
                            display=q.display, numbers=list(q.numbers))
            qs = [q.new() for _ in range(int(n_questions))]
        out.append(Task(kind, settings=settings, questions=copy.deepcopy(qs),
                        scoring=dict(exercise_settings(kind), n_questions=int(n_questions))))
    return out


def new_drill_tasks(kind, count=1, seed=None, **settings):
    """Drills to do: `count` new exercises with these settings."""
    from .drills import make
    rng = random.Random(seed)
    return [Task.from_drill(make(kind, settings, seed=rng.randrange(1 << 30)), settings)
            for _ in range(int(count))]


def new_exercise(kind):
    """One new exercise of a kind with the current user's last settings (drills: the
    Practice tab's; blocks of questions: Settings > Exercises questions + default quiz
    settings; 'duet' / 'duet_repeat': Read & play / Listen & repeat (random) = a piece of a NEW
    duet generated from the theory engine, with the quick tab's settings)."""
    from .progress import settings
    st = settings()
    if kind in DRILL_KINDS:
        return new_drill_tasks(kind, 1, **(st.get("drills", {}).get(kind) or {}))[0]
    if kind in QUIZ_KINDS:
        from .exercise import exercise_settings
        n = int(exercise_settings(kind)["n_questions"])
        return new_quiz_tasks(kind, 1, n)[0]
    if kind in ("duet", "duet_repeat"):        # Read & play / Listen & repeat (random)
        from .phrase import exercise_from_duet, INSTRUMENTS
        from .exercise import exercise_settings
        ex_kind, purpose = (("play_reading", "reading") if kind == "duet"
                            else ("listen_repeat", "repeat"))
        q = dict(st.get("quick_exercises", {}).get(ex_kind) or {})
        q = {k: v for k, v in q.items() if k in ("bars", "level", "instrument", "part")}
        if q.get("instrument") not in (None, *INSTRUMENTS):
            q["instrument"] = "Bb (trumpet)"   # transpositions hidden (owner, 2026-11-09)
        ph = exercise_from_duet(purpose, **q)
        ph.practice_bpm = float(exercise_settings(ex_kind).get("bpm", 90))
        return ph
    raise ValueError(f"unknown exercise kind {kind}")


NEW_KINDS = (("long_tones", "Long tones"), ("scales", "Scales & arpeggios"),
             ("lip_slurs", "Lip slurs"), ("rhythm", "Rhythm reading"),
             ("chord_arpeggios", "Chord arpeggios"),
             ("intervals", "Intervals (ear training)"), ("interval_reading", "Interval reading"),
             ("chords", "Chord qualities"), ("flashcards", "Fingerings & note names"),
             ("duet", "Read & play (random)"), ("duet_repeat", "Listen & repeat (random)"))
