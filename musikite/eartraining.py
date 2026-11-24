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


# ================================================================ more ear training (2026-11-19)
# Scales and modes, scale degrees, cadences by ear (owner, 2026-11-19, from todo.md). Same
# container as the intervals and chord qualities (Exercise: blocks of N questions, points,
# grade 0-10, exercise objects ◆, Repeat = the same questions in another order); musical
# knowledge from the theory engine (theory.SCALES); no Qt, no music21.

def _close_voicing(pcs, prev, lo, hi):
    """Upper voices of a chord: the close position (every inversion, every octave inside
    lo..hi) nearest to the previous one (smallest sum of moves), the first one in the
    middle of the range."""
    pcs = list(pcs)
    best, best_cost = None, None
    for inv in range(len(pcs)):
        order = pcs[inv:] + pcs[:inv]
        for base in range(lo, hi + 1):
            if base % 12 != order[0] % 12:
                continue
            notes, p = [base], base
            for pc in order[1:]:
                p += (pc - p) % 12 or 12
                notes.append(p)
            if notes[-1] > hi:
                continue
            if prev:
                cost = sum(abs(a - b) for a, b in zip(sorted(notes), sorted(prev)))
            else:
                cost = abs(sum(notes) / len(notes) - (lo + hi) / 2)
            if best is None or cost < best_cost:
                best, best_cost = notes, cost
    return best or [lo + (pc - lo) % 12 for pc in pcs]


KEY_MODES = ("major", "minor", "mixed")
# chords of a key by Roman numeral: (root in semitones above the tonic, intervals)
_TRIADS = {"I": (0, (0, 4, 7)), "i": (0, (0, 3, 7)), "ii": (2, (0, 3, 7)),
           "iv": (5, (0, 3, 7)), "IV": (5, (0, 4, 7)), "V": (7, (0, 4, 7)),
           "V7": (7, (0, 4, 7, 10)), "vi": (9, (0, 3, 7)), "VI": (8, (0, 4, 7))}


def chord_sequence(tonic, numerals, chord_s=0.9, last_s=1.6, t=0.0, prog=0, velocity=80):
    """Events (t, on, channel, key, velocity, program) of a sequence of chords in the key of
    `tonic` (MIDI number of the tonic, around G3-F#4): bass = the root under the tonic, upper
    voices in close position near each other. Returns (events, end time)."""
    ev, prev = [], None
    for k, num in enumerate(numerals):
        root, ivs = _TRIADS[num]
        bass = tonic - 12 + root
        if bass >= tonic - 4:
            bass -= 12
        upper = _close_voicing([(tonic + root + i) % 12 for i in ivs], prev,
                               tonic - 3, tonic + 12)
        prev = upper
        dur = last_s if k == len(numerals) - 1 else chord_s
        for p in [bass] + upper:
            ev.append((t, True, 0, p, velocity, prog))
            ev.append((t + dur * 0.97, False, 0, p, 0, prog))
        t += dur
    return ev, t


class _EarQuiz(IntervalQuiz):
    """Common part: one question = a dict; `_sound(q, t)` -> (events, end); a wrong answer
    plays the right one again (`feedback_s` = its length, the exercise waits for it)."""
    kind = None
    labels = {}

    def __init__(self, user=None, sf2=None, mode="", instrument="piano", progress=None,
                 seed=None, repeats=1):
        super().__init__(user=user, sf2=sf2, mode=mode, instrument=instrument,
                         repeats=repeats, progress=progress, seed=seed)
        self.feedback_s = 0.0

    def _prog(self):
        return INSTRUMENTS.get(self.instrument, 0)

    def _sound(self, q, t):
        raise NotImplementedError

    def _play(self, sequence, q=None):
        c = q or self.current
        ev, t = [], 0.0
        for _ in sequence:
            e, end = self._sound(c, t)
            ev += e
            t = end + 0.8
        self._player().play(ev)
        return t

    def replay(self):
        q = self.current or self.last
        if q is None:
            return 0.0
        return self._play([None] * self.repeats, q)

    def response_delay(self, q=None):
        q = q or self.current or self.last
        return self._sound(q, 0.0)[1] if q else 0.0

    def asked(self, q):
        raise NotImplementedError

    def answer(self, value):
        if self.current is None:
            raise RuntimeError("no question: call new() first")
        c = self.current
        right = self.asked(c)
        ok = str(value) == str(right)
        self.total += 1
        self.correct += ok
        if self.user:
            self.progress.record(self.user, self.kind, self.session, right, value,
                                 instrument=self.instrument,
                                 **{k: v for k, v in c.items() if k not in ("answer",)})
        res = dict(correct=ok, asked=right, answered=value,
                   name=self.labels.get(right, str(right)), score=self.score())
        self.feedback_s = self._play([None], c) if not ok else 0.0
        self.last = c
        self.current = None
        return res


# ---------------------------------------------------------------- scales and modes by ear
SCALE_EXERCISE = "scale_ear"
SCALE_LABELS = {"ionian": "Major", "aeolian": "Natural minor", "harmonic_minor": "Harmonic minor",
                "melodic_minor": "Melodic minor", "dorian": "Dorian", "phrygian": "Phrygian",
                "lydian": "Lydian", "mixolydian": "Mixolydian", "locrian": "Locrian",
                "major_pentatonic": "Major pentatonic", "minor_pentatonic": "Minor pentatonic",
                "blues": "Blues", "whole_tone": "Whole tone",
                "diminished_wh": "Diminished (whole-half)"}
DEFAULT_SCALES = ("ionian", "aeolian", "harmonic_minor", "melodic_minor")
SCALE_DIRECTIONS = ("up", "up and down", "mixed")


class ScaleQuiz(_EarQuiz):
    """A scale or mode is played from a random tonic (up, or up and down): name it.

        q = ScaleQuiz(scales=('ionian', 'dorian', 'mixolydian'), mode='up')
        q.new(); q.answer('dorian')
    """
    kind = SCALE_EXERCISE
    labels = SCALE_LABELS
    STEP_S = 0.32                       # one note
    LAST_S = 1.0                        # the last one held

    def __init__(self, user=None, sf2=None, scales=DEFAULT_SCALES, mode="up",
                 instrument="piano", low=55, high=67, progress=None, seed=None):
        super().__init__(user=user, sf2=sf2, mode=mode, instrument=instrument,
                         progress=progress, seed=seed)
        self.scales = tuple(s for s in scales if s in SCALE_LABELS) or DEFAULT_SCALES
        self.low, self.high = low, high

    def settings(self):
        return dict(scales=list(self.scales), mode=self.mode, instrument=self.instrument)

    def answers(self):
        return self.scales

    def pitches(self, q):
        from .theory import SCALES
        ivs = list(SCALES[q["scale"]]) + [12]
        up = [q["tonic"] + i for i in ivs]
        return up + up[-2::-1] if q["direction"] == "up and down" else up

    def new(self, play=True):
        sc = self.r.choice(self.scales)
        d = self.mode if self.mode != "mixed" else self.r.choice(SCALE_DIRECTIONS[:2])
        self.current = dict(tonic=self.r.randint(self.low, self.high), scale=sc, direction=d)
        if play:
            self.replay()
        return self.current

    def asked(self, q):
        return q["scale"]

    def _sound(self, q, t):
        prog, ev = self._prog(), []
        ps = self.pitches(q)
        for i, p in enumerate(ps):
            dur = self.LAST_S if i == len(ps) - 1 else self.STEP_S * 0.95
            ev.append((t, True, 0, p, 85, prog))
            ev.append((t + dur, False, 0, p, 0, prog))
            t += self.STEP_S
        return ev, t - self.STEP_S + self.LAST_S


# ---------------------------------------------------------------- scale degrees by ear
DEGREE_EXERCISE = "scale_degrees"
DEGREE_LABELS = {0: "1", 1: "b2", 2: "2", 3: "b3", 4: "3", 5: "4", 6: "#4 / b5", 7: "5",
                 8: "b6", 9: "6", 10: "b7", 11: "7"}
DEGREE_SETS = ("diatonic", "chromatic")
_DIATONIC = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}
_CADENCE_OF = {"major": ("I", "IV", "V7", "I"), "minor": ("i", "iv", "V7", "i")}


class DegreeQuiz(_EarQuiz):
    """A cadence sets the key (I IV V7 I, minor i iv V7 i), then ONE note is played: which
    degree of the key is it (1, b2, 2 … 7)? degrees 'diatonic' = the notes of the key
    (major / natural minor), 'chromatic' = all twelve.

        q = DegreeQuiz(mode='major', degrees='diatonic')
        q.new(); q.answer(7)          # semitones above the tonic
    """
    kind = DEGREE_EXERCISE
    labels = DEGREE_LABELS

    def __init__(self, user=None, sf2=None, mode="major", degrees="diatonic",
                 instrument="piano", low=55, high=66, progress=None, seed=None):
        super().__init__(user=user, sf2=sf2, mode=mode, instrument=instrument,
                         progress=progress, seed=seed)
        self.degrees = degrees if degrees in DEGREE_SETS else "diatonic"
        self.low, self.high = low, high

    def settings(self):
        return dict(mode=self.mode, degrees=self.degrees, instrument=self.instrument)

    def _pool(self, key_mode):
        return tuple(range(12)) if self.degrees == "chromatic" else _DIATONIC[key_mode]

    def answers(self):
        modes = ("major", "minor") if self.mode == "mixed" else (self.mode,)
        return tuple(sorted({d for m in modes for d in self._pool(m)}))

    def new(self, play=True):
        km = self.mode if self.mode != "mixed" else self.r.choice(KEY_MODES[:2])
        deg = self.r.choice(self._pool(km))
        self.current = dict(tonic=self.r.randint(self.low, self.high), key_mode=km,
                            degree=deg, octave=self.r.choice((0, 0, 1)) if deg < 5 else 0)
        if play:
            self.replay()
        return self.current

    def asked(self, q):
        return q["degree"]

    def answer(self, value):
        return super().answer(int(value))

    def _sound(self, q, t):
        prog = self._prog()
        ev, t = chord_sequence(q["tonic"], _CADENCE_OF[q["key_mode"]], t=t, prog=prog)
        t += 0.7
        p = q["tonic"] + q["degree"] + 12 * int(q.get("octave", 0))
        ev += [(t, True, 0, p, 95, prog), (t + 1.5, False, 0, p, 0, prog)]
        return ev, t + 1.5

    def response_delay(self, q=None):
        q = q or self.current or self.last
        return (self._sound(q, 0.0)[1] - 1.5) if q else 0.0     # from the note


# ---------------------------------------------------------------- cadences by ear
CADENCE_EXERCISE = "cadences"
CADENCE_LABELS = {"perfect": "Perfect (V–I)", "plagal": "Plagal (IV–I)",
                  "half": "Half (… –V)", "deceptive": "Deceptive (V–vi)"}
DEFAULT_CADENCES = tuple(CADENCE_LABELS)
CADENCE_CHORDS = {"major": {"perfect": ("I", "IV", "V", "I"), "plagal": ("I", "vi", "IV", "I"),
                            "half": ("I", "IV", "I", "V"), "deceptive": ("I", "IV", "V", "vi")},
                  "minor": {"perfect": ("i", "iv", "V", "i"), "plagal": ("i", "VI", "iv", "i"),
                            "half": ("i", "iv", "i", "V"), "deceptive": ("i", "iv", "V", "VI")}}


class CadenceQuiz(_EarQuiz):
    """Four chords in a random key, the last two a cadence: perfect (V–I), plagal (IV–I),
    half (ending on V), deceptive (V–vi; minor V–VI). Name it.

        q = CadenceQuiz(cadences=('perfect', 'half'), mode='major')
        q.new(); q.answer('half')
    """
    kind = CADENCE_EXERCISE
    labels = CADENCE_LABELS

    def __init__(self, user=None, sf2=None, cadences=DEFAULT_CADENCES, mode="major",
                 instrument="piano", low=55, high=66, progress=None, seed=None):
        super().__init__(user=user, sf2=sf2, mode=mode, instrument=instrument,
                         progress=progress, seed=seed)
        self.cadences = tuple(c for c in cadences if c in CADENCE_LABELS) or DEFAULT_CADENCES
        self.low, self.high = low, high

    def settings(self):
        return dict(cadences=list(self.cadences), mode=self.mode, instrument=self.instrument)

    def answers(self):
        return self.cadences

    def new(self, play=True):
        km = self.mode if self.mode != "mixed" else self.r.choice(KEY_MODES[:2])
        self.current = dict(tonic=self.r.randint(self.low, self.high), key_mode=km,
                            cadence=self.r.choice(self.cadences))
        if play:
            self.replay()
        return self.current

    def asked(self, q):
        return q["cadence"]

    def _sound(self, q, t):
        return chord_sequence(q["tonic"], CADENCE_CHORDS[q["key_mode"]][q["cadence"]], t=t,
                              prog=self._prog())

    def response_delay(self, q=None):
        q = q or self.current or self.last
        return (self._sound(q, 0.0)[1] - 1.6) if q else 0.0     # from the last chord
