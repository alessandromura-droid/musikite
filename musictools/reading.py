"""
Reading exercises: interval reading (two notes on the staff, name the interval).
Same idea as the ear-training interval quiz, but visual.

Portable core (thinking of an Android port): pure Python, no Qt, no music21.
The question is built as a small MusicXML string; svg() engraves it with
Verovio (Python here; Verovio also exists for JavaScript/WebView), so the GUI
only has to show an SVG.

    q = IntervalReadingQuiz(user='Teresa', answer='quality', accidentals=True)
    q.new();  svg = q.svg()          # show it
    q.answer('M3')                   # -> dict(correct=..., asked='M3', ...)
    q.play()                         # hear it (real time, optional)

Answer modes:
  'number'   generic interval: '2' … '8' (2nd … octave), accidentals ignored
  'quality'  number + quality: m2 M2 m3 M3 P4 A4 d5 P5 m6 M6 m7 M7 P8
"""
import random

from .progress import Progress
from . import theory as _th

EXERCISE = "interval_reading"
STEPS = _th.STEP_LETTERS                      # interval theory: theory engine
STEP_SEMI = _th.STEP_SEMI
PERFECT = _th.PERFECT_NUMBERS                 # number -> semitones of the perfect interval
MAJOR = _th.MAJOR_NUMBERS                     # number -> semitones of the major interval
QUALITY_ANSWERS = ("m2", "M2", "m3", "M3", "P4", "A4", "d5", "P5", "m6", "M6", "m7", "M7", "P8")
NUMBER_ANSWERS = ("2", "3", "4", "5", "6", "7", "8")
NUMBER_NAMES = {k: v for k, v in _th.NUMBER_NAMES.items() if k >= 2}
QUALITY_NAMES = _th.QUALITY_NAMES
DISPLAYS = ("melodic", "harmonic", "mixed")
# clef: (sign, line, lowest and highest diatonic index allowed; index = octave*7 + step)
CLEFS = {"treble": ("G", 2, 4 * 7 + 0, 5 * 7 + 5),       # C4 .. A5
         "bass": ("F", 4, 2 * 7 + 2, 4 * 7 + 0)}         # E2 .. C4


def engrave_question(xml, scale=100):
    """One-bar MusicXML question -> SVG string (Verovio)."""
    import verovio
    tk = verovio.toolkit()
    tk.setOptions({"scale": scale, "adjustPageWidth": True, "adjustPageHeight": True,
                   "header": "none", "footer": "none", "breaks": "none",
                   "pageMarginLeft": 40, "pageMarginRight": 40,
                   "pageMarginTop": 20, "pageMarginBottom": 20})
    if not tk.loadData(xml):
        raise RuntimeError("Verovio could not read the question")
    return tk.renderToSVG(1)


def _xml_note(d, a, dur, typ, chord=False):
    alter = f"<alter>{a}</alter>" if a else ""
    acc = {1: "sharp", -1: "flat"}.get(a)
    acc = f"<accidental>{acc}</accidental>" if acc else ""
    return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{STEPS[d % 7]}</step>{alter}"
            f"<octave>{d // 7}</octave></pitch><duration>{dur}</duration>"
            f"<type>{typ}</type>{acc}</note>")


def _xml_bar(sign, line, body):
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<score-partwise version="3.1"><part-list><score-part id="P1"><part-name print-object="no">'
            '</part-name></score-part></part-list><part id="P1"><measure number="1">'
            '<attributes><divisions>1</divisions><key><fifths>0</fifths></key>'
            '<time print-object="no"><beats>4</beats><beat-type>4</beat-type></time>'
            f'<clef><sign>{sign}</sign><line>{line}</line></clef></attributes>{body}'
            '<barline location="right"><bar-style>none</bar-style></barline>'
            '</measure></part></score-partwise>')


def answer_label(key):
    """'M3' -> 'Major 3rd', '5' -> '5th', 'P8' -> 'Perfect Octave'."""
    return _th.interval_label(key)


def midi_of(d, alter):
    """Diatonic index (octave*7 + step) and alteration -> MIDI number."""
    return 12 * (d // 7 + 1) + STEP_SEMI[d % 7] + alter


def interval_name(d1, a1, d2, a2):
    """Name of the interval between two spelled notes ('M3', 'A4', …) or None
    if it is not a simple interval with a usual quality."""
    if d2 < d1:
        d1, a1, d2, a2 = d2, a2, d1, a1
    return _th.spelled_interval(d2 - d1 + 1, midi_of(d2, a2) - midi_of(d1, a1))


class IntervalReadingQuiz:
    def __init__(self, user=None, answer="quality", accidentals=False, clef="treble",
                 display="melodic", numbers=(2, 3, 4, 5, 6, 7, 8), progress=None, seed=None,
                 sf2=None, instrument_program=0):
        self.user = user
        self.answer_mode = answer
        self.accidentals = accidentals
        self.clef = clef
        self.display = display
        self.numbers = tuple(numbers)
        self.progress = progress if progress is not None else Progress()
        self.r = random.Random(seed)
        self.session = Progress.new_session()
        self.correct = self.total = 0
        self.current = self.last = None
        self.sf2 = sf2
        self.program = instrument_program

    def answers(self):
        if self.answer_mode == "number":
            return tuple(a for a in NUMBER_ANSWERS if int(a) in self.numbers)
        return tuple(a for a in QUALITY_ANSWERS if int(a[1:]) in self.numbers)

    # ---------------------------------------------------------- questions
    def new(self):
        sign, line, lo, hi = CLEFS[self.clef]
        allowed = set(self.answers())
        for _ in range(1000):
            n = self.r.choice(self.numbers)
            d1 = self.r.randint(lo, hi - (n - 1))
            d2 = d1 + n - 1
            if self.accidentals:
                a1 = self.r.choice((0, 0, 0, 1, -1))
                a2 = self.r.choice((0, 0, 0, 1, -1))
            else:
                a1 = a2 = 0
            name = interval_name(d1, a1, d2, a2)
            key = str(n) if self.answer_mode == "number" else name
            if name is not None and key in allowed:
                break
        else:
            raise RuntimeError("no interval fits the settings")
        harmonic = self.display == "harmonic" or (self.display == "mixed" and self.r.random() < 0.5)
        notes = [(d1, a1), (d2, a2)]
        if not harmonic and self.r.random() < 0.5:
            notes.reverse()                                  # descending
        self.current = dict(notes=notes, harmonic=harmonic, name=name, number=n, key=key)
        return self.current

    def ask(self, question):
        """Ask a given question again (used to repeat an exercise)."""
        self.current = dict(question, notes=[tuple(n) for n in question["notes"]])
        return self.current

    def response_delay(self, q=None):
        return 0.0

    def musicxml(self, q=None):
        """The question as a one-bar MusicXML score (no time signature shown)."""
        q = q or self.current
        sign, line = CLEFS[self.clef][:2]

        def note(d, a, dur, typ, chord=False):
            alter = f"<alter>{a}</alter>" if a else ""
            acc = {1: "sharp", -1: "flat"}.get(a)
            acc = f"<accidental>{acc}</accidental>" if acc else ""
            return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{STEPS[d % 7]}</step>{alter}"
                    f"<octave>{d // 7}</octave></pitch><duration>{dur}</duration>"
                    f"<type>{typ}</type>{acc}</note>")

        (d1, a1), (d2, a2) = q["notes"]
        if q["harmonic"]:
            body = note(d1, a1, 4, "whole") + note(d2, a2, 4, "whole", chord=True)
        else:
            body = note(d1, a1, 2, "half") + note(d2, a2, 2, "half")
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<score-partwise version="3.1"><part-list><score-part id="P1"><part-name print-object="no">'
                '</part-name></score-part></part-list><part id="P1"><measure number="1">'
                '<attributes><divisions>1</divisions><key><fifths>0</fifths></key>'
                '<time print-object="no"><beats>4</beats><beat-type>4</beat-type></time>'
                f'<clef><sign>{sign}</sign><line>{line}</line></clef></attributes>{body}'
                '<barline location="right"><bar-style>none</bar-style></barline>'
                '</measure></part></score-partwise>')

    def svg(self, scale=100):
        """Engraved question (SVG string), via Verovio."""
        return engrave_question(self.musicxml(), scale)

    # ---------------------------------------------------------- answers
    def answer(self, key):
        if self.current is None:
            raise RuntimeError("no question: call new() first")
        c = self.current
        ok = str(key) == c["key"]
        self.total += 1
        self.correct += ok
        if self.user:
            self.progress.record(self.user, EXERCISE, self.session, c["key"], str(key),
                                 mode=self.answer_mode, name=c["name"], clef=self.clef,
                                 harmonic=c["harmonic"], accidentals=self.accidentals)
        res = dict(correct=ok, asked=c["key"], answered=str(key), name=c["name"],
                   label=answer_label(c["key"]), full=answer_label(c["name"]), score=self.score())
        self.last, self.current = c, None
        return res

    def score(self):
        return self.correct, self.total

    def play(self, q=None):
        """Hear the interval shown (real time): together if harmonic, else one after the other."""
        from .realtime import get_player
        from .midi import Midi
        q = q or self.current or self.last
        sf2 = self.sf2 or Midi._default_sf2
        if q is None or sf2 is None:
            return None
        k1, k2 = (midi_of(d, a) for d, a in q["notes"])
        t2 = 0.0 if q["harmonic"] else 0.8
        ev = [(0.0, True, 0, k1, 90, self.program), (1.4, False, 0, k1, 0, self.program),
              (t2, True, 0, k2, 90, self.program), (t2 + 1.4, False, 0, k2, 0, self.program)]
        get_player(sf2).play(ev)
        return self


# ---------------------------------------------------------------- flash cards
FLASH_EXERCISE = "flashcards"
FLASH_MODES = ("fingering", "note name")
NAME_ANSWERS = tuple(str(k) for k in range(12))          # pitch class (enharmonics are equal)
NAME_LABELS = {0: "C", 1: "C# / Db", 2: "D", 3: "D# / Eb", 4: "E", 5: "F", 6: "F# / Gb",
               7: "G", 8: "G# / Ab", 9: "A", 10: "A# / Bb", 11: "B"}


def flash_label(mode, key):
    if mode == "fingering":
        return "open (0)" if key == "0" else "–".join(key)
    return NAME_LABELS[int(key)]


class FlashcardQuiz:
    """Flash cards (owner, 2026-11-08): ONE note on the staff (treble clef, Bb trumpet,
    WRITTEN pitch) -> its valves ('fingering': 0 2 1 12 23 13 123, standard fingering of
    fingerings.VALVE_TABLE) or its name ('note name': 12 answers, enharmonics equal).
    lowest / highest: written range (default: Settings > Instruments, trumpet).

        q = FlashcardQuiz(answer='fingering', accidentals=True)
        q.new(); svg = q.svg(); q.answer('13')
    """

    def __init__(self, user=None, answer="fingering", accidentals=True, lowest=None,
                 highest=None, progress=None, seed=None, sf2=None, instrument_program=56):
        from .fingerings import VALVE_TABLE as TRUMPET_FINGERING
        self.user = user
        self.answer_mode = answer if answer in FLASH_MODES else "fingering"
        self.accidentals = bool(accidentals)
        if lowest is None or highest is None:
            try:
                from .phrase import instrument_range
                lo, hi = instrument_range("Bb (trumpet)")
            except Exception:
                lo, hi = 55, 77
            lowest = lo if lowest is None else lowest
            highest = hi if highest is None else highest
        lo, hi = min(TRUMPET_FINGERING), max(TRUMPET_FINGERING)
        self.lowest, self.highest = max(lo, int(lowest)), min(hi, int(highest))
        self.progress = progress if progress is not None else Progress()
        self.r = random.Random(seed)
        self.session = Progress.new_session()
        self.correct = self.total = 0
        self.current = self.last = None
        self.sf2 = sf2
        self.program = instrument_program

    def settings(self):
        return dict(answer_mode=self.answer_mode, accidentals=self.accidentals,
                    lowest=self.lowest, highest=self.highest)

    def answers(self):
        from .fingerings import VALVE_COMBINATIONS
        return VALVE_COMBINATIONS if self.answer_mode == "fingering" else NAME_ANSWERS

    def new(self, play=False):
        from .fingerings import VALVE_TABLE as TRUMPET_FINGERING
        pool = [p for p in range(self.lowest, self.highest + 1)
                if self.accidentals or (p % 12) in STEP_SEMI]
        if not pool:
            raise RuntimeError("no note in the range")
        p = self.r.choice(pool)
        step = {v: k for k, v in enumerate(STEP_SEMI)}
        pc, octave = p % 12, p // 12 - 1
        if pc in step:
            d, a = octave * 7 + step[pc], 0
        elif self.r.random() < 0.5:                       # sharp spelling
            d, a = octave * 7 + step[pc - 1], 1
        else:                                             # flat spelling
            d, a = octave * 7 + step[(pc + 1) % 12] + (7 if pc == 11 else 0), -1
        key = TRUMPET_FINGERING[p] if self.answer_mode == "fingering" else str(pc)
        self.current = dict(note=(d, a), midi=p, key=key, harmonic=False,
                            name=f"{STEPS[d % 7]}{ {1: '#', -1: 'b'}.get(a, '') }{d // 7}")
        return self.current

    def ask(self, question):
        self.current = dict(question, note=tuple(question["note"]))
        return self.current

    def response_delay(self, q=None):
        return 0.0

    def musicxml(self, q=None):
        q = q or self.current
        d, a = q["note"]
        return _xml_bar("G", 2, _xml_note(d, a, 4, "whole"))

    def svg(self, scale=100):
        return engrave_question(self.musicxml(), scale)

    def answer(self, key):
        if self.current is None:
            raise RuntimeError("no question: call new() first")
        c = self.current
        if self.answer_mode == "fingering":
            ok = str(key) == c["key"]
        else:
            ok = int(key) % 12 == int(c["key"])
        self.total += 1
        self.correct += ok
        if self.user:
            self.progress.record(self.user, FLASH_EXERCISE, self.session, c["key"], str(key),
                                 mode=self.answer_mode, note=c["midi"])
        res = dict(correct=ok, asked=c["key"], answered=str(key), name=c["name"],
                   label=flash_label(self.answer_mode, c["key"]), score=self.score())
        self.last, self.current = c, None
        return res

    def score(self):
        return self.correct, self.total

    def play(self, q=None):
        """The note as it sounds on the Bb trumpet (a tone below the written one)."""
        from .realtime import get_player
        from .midi import Midi
        q = q or self.current or self.last
        sf2 = self.sf2 or Midi._default_sf2
        if q is None or sf2 is None:
            return None
        k = q["midi"] - 2
        get_player(sf2).play([(0.0, True, 0, k, 90, self.program),
                              (1.2, False, 0, k, 0, self.program)])
        return self
