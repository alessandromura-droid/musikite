"""
Ear training: interval recognition (port of MATLAB myintervalli.m /
mysmartmusic_obj/myintervals.m).

As in MATLAB: a random lower note, a random interval drawn with the same
weights (thirds, fourths, fifths, sixths and the octave more frequent, no
minor second by default), played harmonically twice; after a wrong answer
the interval is played again harmonically and then melodically, and the
right name is shown. Here every answer is also stored per user (Progress).

Usable without the GUI (Jupyter / command line):

    q = IntervalQuiz(user='Teresa', sf2='/path/font.sf2')
    q.new()            # draws and plays an interval
    q.replay()
    q.answer(7)        # semitones -> dict(correct=..., asked=..., name=...)
    q.score()          # (correct, total)
"""
import random
import time

from .progress import Progress

from .theory import interval_name

INTERVALS = {k: interval_name(k) for k in range(1, 13)}    # names from the theory engine
# MATLAB: Nb = [2 3 3 3 4 4 4 5 5 5 5 6 7 7 7 8 9 9 9 10 11 12 12]
DEFAULT_WEIGHTS = {1: 0, 2: 1, 3: 3, 4: 3, 5: 4, 6: 1, 7: 3, 8: 1, 9: 3, 10: 1, 11: 1, 12: 2}
MODES = ("harmonic", "melodic up", "melodic down", "mixed")
INSTRUMENTS = {"piano": 0, "trumpet": 56, "organ": 19, "flute": 73}
EXERCISE = "intervals"


class IntervalQuiz:
    def __init__(self, user=None, sf2=None, weights=None, mode="harmonic",
                 instrument="piano", low=55, high=79, repeats=2, progress=None, seed=None):
        """weights: {semitones: weight} (0 = not asked); low/high: MIDI range of
        the two notes; repeats: times the interval is played at each question."""
        from .midi import Midi
        self.user = user
        self.sf2 = sf2 or Midi._default_sf2
        self.weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
        self.mode = mode
        self.instrument = instrument
        self.low, self.high = low, high
        self.repeats = repeats
        self.progress = progress if progress is not None else Progress()
        self.r = random.Random(seed)
        self.session = Progress.new_session()
        self.correct = 0
        self.total = 0
        self.current = None                  # dict(low, semitones, mode) still to answer
        self.last = None                     # last answered question

    # ---------------------------------------------------------- audio
    def _player(self):
        from .realtime import get_player
        if self.sf2 is None:
            raise RuntimeError("no soundfont: give sf2= or use Midi.add_sf2(path) first")
        return get_player(self.sf2)

    def _events(self, low, semis, mode, t=0.0, dur=1.4, gap=0.75):
        prog = INSTRUMENTS.get(self.instrument, 0)
        hi = low + semis
        if mode == "harmonic":
            notes = [(t, low), (t, hi)]
            end = t + dur
        elif mode == "melodic down":
            notes = [(t, hi), (t + gap, low)]
            end = t + gap + dur
        else:                                          # melodic up
            notes = [(t, low), (t + gap, hi)]
            end = t + gap + dur
        ev = []
        for t0, k in notes:
            ev.append((t0, True, 0, k, 90, prog))
            ev.append((t0 + dur, False, 0, k, 0, prog))
        return ev, end

    def _play(self, sequence, q=None):
        """sequence: list of modes played one after the other with a pause."""
        c = q or self.current
        ev, t = [], 0.0
        for m in sequence:
            e, end = self._events(c["low"], c["semitones"], m, t)
            ev += e
            t = end + 0.6
        self._player().play(ev)
        return t

    # ---------------------------------------------------------- quiz
    def asked_intervals(self):
        return [k for k, w in self.weights.items() if w > 0]

    def new(self, play=True):
        """Draw a new interval and play it (`repeats` times)."""
        pool = self.asked_intervals()
        if not pool:
            raise ValueError("no interval selected")
        semis = self.r.choices(pool, weights=[self.weights[k] for k in pool])[0]
        low = self.r.randint(self.low, self.high - semis)
        mode = self.mode if self.mode != "mixed" else self.r.choice(MODES[:3])
        self.current = dict(low=low, semitones=semis, mode=mode)
        if play:
            self.replay()
        return self.current

    def ask(self, question, play=True):
        """Ask a given question again (used to repeat an exercise)."""
        self.current = dict(question)
        if play:
            self.replay()
        return self.current

    def response_delay(self, q=None):
        """Seconds after the start of the sound when the interval has been heard
        once (the answer time is counted from there)."""
        q = q or self.current or self.last
        return 0.5 if q and q["mode"] == "harmonic" else 1.25

    def replay(self):
        """Play the current question again (or the last one, once answered)."""
        q = self.current or self.last
        if q is None:
            return 0.0
        keep, self.current = self.current, q
        try:
            return self._play([q["mode"]] * self.repeats)
        finally:
            self.current = keep

    def answer(self, semitones):
        """Check an answer (semitones). Wrong: replays harmonic + melodic (as in MATLAB)."""
        if self.current is None:
            raise RuntimeError("no question: call new() first")
        c = self.current
        ok = int(semitones) == c["semitones"]
        self.total += 1
        self.correct += ok
        if self.user:
            self.progress.record(self.user, EXERCISE, self.session, c["semitones"], int(semitones),
                                 mode=c["mode"], low=c["low"], instrument=self.instrument)
        res = dict(correct=ok, asked=c["semitones"], answered=int(semitones),
                   name=INTERVALS[c["semitones"]], score=self.score())
        if not ok:
            self._play(["harmonic", "melodic down" if c["mode"] == "melodic down" else "melodic up"], c)
        self.last = c
        self.current = None                  # one answer per question
        return res

    def score(self):
        return self.correct, self.total

    def restart(self):
        """New session for the same user (results so far are already saved)."""
        self.session = Progress.new_session()
        self.correct = self.total = 0
        self.current = self.last = None
        return self

    def stop(self):
        if self.sf2 is not None:
            self._player().stop()


# ---------------------------------------------------------------- chord qualities
CHORD_EXERCISE = "chords"
CHORD_LABELS = {"": "Major", "m": "Minor", "dim": "Diminished", "aug": "Augmented",
                "sus4": "Suspended 4th", "7": "Dominant 7th", "maj7": "Major 7th",
                "m7": "Minor 7th", "m7b5": "Half-diminished", "dim7": "Diminished 7th",
                "6": "Major 6th", "m6": "Minor 6th", "m(maj7)": "Minor-major 7th"}
DEFAULT_CHORDS = ("", "m", "dim", "aug", "7", "maj7", "m7")
CHORD_MODES = ("harmonic", "arpeggio up", "mixed")


class ChordQuiz(IntervalQuiz):
    """Ear training: a chord is played, name its QUALITY (major, minor, dominant 7th…).
    Same container as the intervals (Exercise: blocks, points, grade); qualities and
    intervals from the theory engine (theory.CHORD_TYPES). After a wrong answer the chord
    is played again, then as an arpeggio.

        q = ChordQuiz(qualities=('', 'm', '7'), mode='harmonic', inversions=False)
        q.new(); q.answer('m7')
    """

    def __init__(self, user=None, sf2=None, qualities=DEFAULT_CHORDS, mode="harmonic",
                 instrument="piano", inversions=False, low=48, high=72, repeats=2,
                 progress=None, seed=None):
        super().__init__(user=user, sf2=sf2, mode=mode, instrument=instrument, low=low,
                         high=high, repeats=repeats, progress=progress, seed=seed)
        self.qualities = tuple(q for q in qualities if q in CHORD_LABELS) or DEFAULT_CHORDS
        self.inversions = bool(inversions)

    def settings(self):
        return dict(qualities=list(self.qualities), mode=self.mode, instrument=self.instrument,
                    inversions=self.inversions)

    def answers(self):
        return self.qualities

    def pitches(self, q=None):
        from .theory import CHORD_TYPES
        q = q or self.current
        ivs = list(CHORD_TYPES[q["quality"]])
        for _ in range(int(q.get("inversion", 0))):           # lowest note up an octave
            ivs = ivs[1:] + [ivs[0] + 12]
        return [q["root"] + i for i in ivs]

    def new(self, play=True):
        from .theory import CHORD_TYPES
        qual = self.r.choice(self.qualities)
        top = max(CHORD_TYPES[qual])
        root = self.r.randint(self.low, max(self.low, self.high - top))
        inv = self.r.randrange(len(CHORD_TYPES[qual])) if self.inversions else 0
        mode = self.mode if self.mode != "mixed" else self.r.choice(CHORD_MODES[:2])
        self.current = dict(root=root, quality=qual, inversion=inv, mode=mode)
        if play:
            self.replay()
        return self.current

    def response_delay(self, q=None):
        q = q or self.current or self.last
        return 0.5 if q and q["mode"] == "harmonic" else 0.4 * len(self.pitches(q))

    def _play(self, sequence, q=None):
        c = q or self.current
        prog = INSTRUMENTS.get(self.instrument, 0)
        ev, t = [], 0.0
        for m in sequence:
            ps = self.pitches(c)
            starts = [t] * len(ps) if m == "harmonic" else [t + 0.4 * i for i in range(len(ps))]
            for t0, k in zip(starts, ps):
                ev.append((t0, True, 0, k, 85, prog))
                ev.append((max(starts) + 1.6, False, 0, k, 0, prog))
            t = max(starts) + 1.6 + 0.6
        self._player().play(ev)
        return t

    def answer(self, quality):
        if self.current is None:
            raise RuntimeError("no question: call new() first")
        c = self.current
        ok = str(quality) == c["quality"]
        self.total += 1
        self.correct += ok
        if self.user:
            self.progress.record(self.user, CHORD_EXERCISE, self.session, c["quality"],
                                 str(quality), mode=c["mode"], root=c["root"],
                                 inversion=c["inversion"], instrument=self.instrument)
        res = dict(correct=ok, asked=c["quality"], answered=str(quality),
                   name=CHORD_LABELS[c["quality"]], score=self.score())
        # length of the replay after a wrong answer (block, then arpeggio): the exercise
        # waits for it + 1 s before the next question (owner, 2026-11-14: a 4-note
        # arpeggio was cut after 3 notes by the next chord)
        self.feedback_s = self._play(["harmonic", "arpeggio up"], c) if not ok else 0.0
        self.last = c
        self.current = None
        return res
