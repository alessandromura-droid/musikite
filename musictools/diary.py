"""
Practice diary: what was practised day by day, the grade of the day of every
exercise and the study time (pure Python, no Qt: goes to Android as it is; the
charts are drawn by gui/diaryview.py).

Owner's rules (2026-11-06):
- THE DAY runs from 04:00 to 04:00 (DAY_START_HOUR), so a session across midnight
  stays one day.
- Within the day an exercise can be repeated to improve its grade: Read & play and
  Listen & repeat exactly the same exercise; intervals and interval reading the same
  questions in another order. The grade of the day of an exercise is the BEST attempt
  (a better repetition cancels the previous grade, a worse one does not count);
  every attempt is kept (for the candles chart) and its time always counts.
- At the end of the day the day is FROZEN: number of exercises, their grades, mean
  per exercise type, time studied; frozen days are never computed again (a later
  change of the grading rules does not rewrite the past).
- STUDY TIME = only exercises: twice the sound time of a take (Read & play,
  Listen & repeat: the whole take, incl. the phrase heard in Listen & repeat); for
  intervals / interval reading the answer time, at most ANSWER_CAP_S per question;
  Free player: twice the time the keyboard was really played (`Activity`). An app
  left open, listening to MIDI files with Play: nothing.

Identity of an exercise (`key`): "<kind>:<phrase uid>" for Read & play / Listen &
repeat; "<kind>:<fingerprint of the question set>" for intervals (same questions in
another order = same exercise).

    d = Diary('Teresa')                       # users/Teresa/diary.json
    d.record('play_reading', 'play_reading:ab12', grade=7.5, study_s=40, title='…')
    d.add_time('free_player', 120)
    d.day('2026-11-06')                       # summary (frozen or of today)
    d.calendar('time') / d.calendar('grade', kind='intervals')
    d.candles('play_reading'); d.trend(); d.weekly()
"""
import datetime as _dt
import hashlib
import json
import os
import threading

DAY_START_HOUR = 4
ANSWER_CAP_S = 15.0                 # intervals: answer time counted at most per question
SOUND_FACTOR = 2.0                  # study time = SOUND_FACTOR × sound time
KINDS = ("intervals", "interval_reading", "chords", "flashcards", "play_reading",
         "listen_repeat", "long_tones", "scales", "lip_slurs", "rhythm", "chord_arpeggios",
         "free_player")
BLOCK_KINDS = ("intervals", "interval_reading", "chords", "flashcards")   # blocks of questions
KIND_LABELS = {"intervals": "Intervals", "interval_reading": "Interval reading",
               "play_reading": "Read & play", "listen_repeat": "Listen & repeat",
               "long_tones": "Long tones", "scales": "Scales & arpeggios",
               "lip_slurs": "Lip slurs", "rhythm": "Rhythm reading", "free_player": "Free player",
               "chords": "Chord qualities", "flashcards": "Fingerings & note names",
               "chord_arpeggios": "Chord arpeggios"}
GRADED = ("intervals", "interval_reading", "chords", "flashcards", "play_reading",
          "listen_repeat", "long_tones", "scales", "lip_slurs", "rhythm", "chord_arpeggios")
VERSION = 1


def day_of(when=None):
    """Day (YYYY-MM-DD) of an instant: the day starts at DAY_START_HOUR."""
    if when is None:
        when = _dt.datetime.now()
    elif isinstance(when, str):
        when = _dt.datetime.fromisoformat(when)
    return (when - _dt.timedelta(hours=DAY_START_HOUR)).date().isoformat()


def questions_key(kind, questions):
    """Identity of an interval exercise: its questions, whatever their order."""
    items = sorted(json.dumps(q, sort_keys=True, default=str) for q in questions or [])
    h = hashlib.sha1("\n".join(items).encode()).hexdigest()[:12]
    return f"{kind}:{h}"


def interval_study_s(items):
    """Study time of an interval block: answer times, at most ANSWER_CAP_S each."""
    return round(sum(min(float(i.get("seconds", 0.0)), ANSWER_CAP_S) for i in items), 1)


class Activity:
    """Time an instrument was really played (Free player): every note (on or off)
    keeps the player 'active' for `hold` seconds; the union of these intervals is
    the playing time (a coffee with the app open counts nothing)."""

    def __init__(self, hold=1.0):
        self.hold = float(hold)
        self.end = None
        self.total = 0.0

    def hit(self, t):
        e = t + self.hold
        if self.end is None or t >= self.end:
            self.total += self.hold
        else:
            self.total += max(0.0, e - self.end)
        self.end = e if self.end is None else max(self.end, e)

    def take(self):
        """Seconds accumulated since the last take() (and reset)."""
        s, self.total = self.total, 0.0
        return s


# ---------------------------------------------------------------- the diary
class Diary:
    def __init__(self, user=None, path=None):
        from .progress import user_dir, current_user
        self.user = current_user() if user is None else user
        self.path = path or os.path.join(user_dir(self.user), "diary.json")
        self._lock = threading.RLock()
        self.data = self._load()
        self.freeze()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        d.setdefault("version", VERSION)
        d.setdefault("attempts", [])
        d.setdefault("days", {})            # frozen days: day -> summary
        return d

    def save(self):
        from .progress import _save
        with self._lock:
            _save(self.path, self.data)

    # ---------------------------------------------------------- writing
    def record(self, kind, key, grade=None, study_s=0.0, title="", when=None, save=True,
               freeze=True, **extra):
        """One attempt of an exercise (grade 0-10, None = time only)."""
        when = when or _dt.datetime.now().isoformat(timespec="seconds")
        a = dict(time=when, day=day_of(when), kind=kind, key=key,
                 grade=None if grade is None else round(float(grade), 2),
                 study_s=round(float(study_s), 1), title=title, **extra)
        with self._lock:
            if freeze:
                self.freeze()
            if a["day"] in self.data["days"]:          # an attempt of a frozen day: kept
                a["late"] = True                       # but the frozen summary stays
            self.data["attempts"].append(a)
            if save:
                self.save()
        return a

    def add_time(self, kind, seconds, when=None):
        """Study time without a grade (Free player)."""
        if seconds <= 0:
            return None
        return self.record(kind, None, None, seconds, KIND_LABELS.get(kind, kind), when)

    # ---------------------------------------------------------- days
    def attempts(self, day=None, kind=None):
        return [a for a in self.data["attempts"]
                if (day is None or a["day"] == day) and (kind is None or a["kind"] == kind)]

    def freeze(self, today=None):
        """Freeze every day before today that has attempts and is not frozen yet."""
        today = today or day_of()
        with self._lock:
            days = sorted({a["day"] for a in self.data["attempts"]})
            new = False
            for d in days:
                if d < today and d not in self.data["days"]:
                    self.data["days"][d] = dict(summarize(self.attempts(d)), day=d,
                                                frozen=True)
                    new = True
            if new:
                self.save()
        return self

    def day(self, day=None):
        """Summary of a day: frozen, or computed now (today)."""
        day = day or day_of()
        if day in self.data["days"]:
            return self.data["days"][day]
        return dict(summarize(self.attempts(day)), day=day, frozen=False)

    def days(self):
        """Every day with something done, oldest first."""
        return sorted(set(self.data["days"]) | {a["day"] for a in self.data["attempts"]})

    def best_today(self, key):
        g = [a["grade"] for a in self.attempts(day_of()) if a["key"] == key
             and a["grade"] is not None]
        return max(g) if g else None

    # ---------------------------------------------------------- chart data
    def calendar(self, metric="time", kind=None):
        """{day: value}: metric 'time' (minutes studied, of one kind or all) or
        'grade' (mean grade of the day, of one kind or all)."""
        out = {}
        for d in self.days():
            s = self.day(d)
            if metric == "time":
                v = (s["by_kind"].get(kind, {}).get("minutes", 0.0) if kind else s["minutes"])
                if v > 0:
                    out[d] = v
            else:
                v = s["by_kind"].get(kind, {}).get("mean") if kind else s["mean"]
                if v is not None:
                    out[d] = v
        return out

    def candles(self, kind=None):
        """[(day, open, high, low, close, mean)]: grades of the attempts of a day (of one
        kind or all): first, best, worst, last, mean of the grades of the day."""
        out = []
        for d in self.days():
            s = self.day(d)
            c = s["by_kind"].get(kind) if kind else s.get("all")
            if c and c.get("open") is not None:
                out.append((d, c["open"], c["high"], c["low"], c["close"], c["mean"]))
        return out

    def trend(self, kind=None, window=7):
        """[(day, mean of the day, low, high, moving mean over `window` days)]."""
        rows = [(d, m, lo, hi) for d, o, hi, lo, c, m in self.candles(kind)]
        out = []
        for i, (d, m, lo, hi) in enumerate(rows):
            d0 = (_dt.date.fromisoformat(d) - _dt.timedelta(days=window - 1)).isoformat()
            ms = [r[1] for r in rows[:i + 1] if r[0] >= d0]
            out.append((d, m, lo, hi, round(sum(ms) / len(ms), 2)))
        return out

    def weekly(self):
        """{week start (Monday, YYYY-MM-DD): {kind: minutes}}."""
        out = {}
        for d in self.days():
            date = _dt.date.fromisoformat(d)
            wk = (date - _dt.timedelta(days=date.weekday())).isoformat()
            w = out.setdefault(wk, {})
            for k, v in self.day(d)["by_kind"].items():
                if v.get("minutes"):
                    w[k] = round(w.get(k, 0.0) + v["minutes"], 1)
        return dict(sorted(out.items()))

    def streak(self, today=None):
        """(current streak, longest streak) of consecutive days with study time."""
        days = sorted(d for d in self.days() if self.day(d)["minutes"] > 0)
        if not days:
            return 0, 0
        best = run = 1
        for a, b in zip(days, days[1:]):
            run = run + 1 if (_dt.date.fromisoformat(b) - _dt.date.fromisoformat(a)).days == 1 else 1
            best = max(best, run)
        today = _dt.date.fromisoformat(today or day_of())
        last = _dt.date.fromisoformat(days[-1])
        cur = run if (today - last).days <= 1 else 0
        return cur, best

    # ---------------------------------------------------------- old results
    def import_progress(self, exercises):
        """Build the attempts once from the exercise blocks already stored in
        progress.json (before the diary existed). Read & play / Listen & repeat:
        one attempt per phrase, study time estimated from bars and bpm."""
        if self.data.get("imported"):
            return 0
        n = 0
        with self._lock:
            for e in exercises or []:
                kind, start = e.get("kind"), e.get("start")
                if not start or kind not in GRADED:
                    continue
                items = e.get("items") or []
                if kind in BLOCK_KINDS:
                    self.record(kind, questions_key(kind, e.get("questions")), e.get("grade"),
                                interval_study_s(items),
                                f"{KIND_LABELS[kind]} ({e.get('n_questions')} questions)",
                                when=start, save=False, freeze=False, imported=True)
                    n += 1
                    continue
                bpm = float((e.get("quiz") or {}).get("bpm") or 90)
                base = float((e.get("scoring") or {}).get("base") or 100)
                for it in items:
                    q = it.get("question") or {}
                    frac = (it.get("detail") or {}).get("fraction")
                    if frac is None:
                        frac = float(it.get("points", 0.0)) / base
                    ts = q.get("ts") or (4, 4)
                    beats = (int(q.get("bars", 2)) + 1) * ts[0] * 4.0 / ts[1]
                    sound = beats * 60.0 / bpm * (2 if kind == "listen_repeat" else 1) + 2.0
                    self.record(kind, f"{kind}:{q.get('uid')}", 10.0 * float(frac),
                                SOUND_FACTOR * sound, q.get("title", ""), when=start,
                                save=False, freeze=False, imported=True)
                    n += 1
            self.data["imported"] = True
            self.data["attempts"].sort(key=lambda a: a["time"])
            self.save()
            self.freeze()
        return n


def summarize(attempts):
    """Summary of the attempts of one day: exercises (best of the day), means and
    candles per kind and overall, minutes."""
    ex = {}
    for a in sorted(attempts, key=lambda a: a["time"]):
        if a["grade"] is None or a["key"] is None:
            continue
        e = ex.setdefault(a["key"], dict(key=a["key"], kind=a["kind"], title=a.get("title", ""),
                                         grades=[]))
        e["grades"].append(a["grade"])
    exercises = []
    for e in ex.values():
        g = e.pop("grades")
        exercises.append(dict(e, best=max(g), attempts=len(g), first=g[0], last=g[-1]))

    def block(ats, exs):
        gs = [a["grade"] for a in sorted(ats, key=lambda a: a["time"]) if a["grade"] is not None]
        bests = [x["best"] for x in exs]
        return dict(n=len(exs), attempts=len(gs),
                    mean=round(sum(bests) / len(bests), 2) if bests else None,
                    minutes=round(sum(a["study_s"] for a in ats) / 60.0, 1),
                    open=gs[0] if gs else None, close=gs[-1] if gs else None,
                    high=max(gs) if gs else None, low=min(gs) if gs else None)

    by_kind = {}
    for k in sorted({a["kind"] for a in attempts}):
        by_kind[k] = block([a for a in attempts if a["kind"] == k],
                           [x for x in exercises if x["kind"] == k])
    allb = block(attempts, exercises)
    return dict(exercises=sorted(exercises, key=lambda x: (x["kind"], x["title"])),
                by_kind=by_kind, all=allb, n=allb["n"], mean=allb["mean"],
                minutes=allb["minutes"])


# ---------------------------------------------------------------- shared instances
_diaries = {}


def get(user=None):
    """The Diary of a user (one per user in the process)."""
    from .progress import current_user
    user = current_user() if user is None else user
    d = _diaries.get(user or "")
    if d is None:
        d = _diaries[user or ""] = Diary(user)
    return d


def record_take(kind, uid, grade, sound_s, title="", user=None):
    """Read & play / Listen & repeat: one take of a phrase."""
    return get(user).record(kind, f"{kind}:{uid}", grade, SOUND_FACTOR * float(sound_s), title)


def record_block(data):
    """Intervals / interval reading: a finished (or stopped) block (ExerciseResult.data)."""
    kind = data.get("kind")
    if kind not in BLOCK_KINDS:
        return None
    return get(data.get("user")).record(
        kind, questions_key(kind, data.get("questions")), data.get("grade"),
        interval_study_s(data.get("items") or []),
        f"{KIND_LABELS[kind]} ({data.get('n_questions')} questions)")
