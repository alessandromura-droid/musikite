"""
Exercise material: short phrases cut from a MIDI (counterpart of the MATLAB
mysmartmusic_obj `exercise` object and `exercisegen`), shared by the exercises
that need a melody: Read & play (reading, default 8 bars) and the melodic
Listen & repeat (the phrase is played, the player repeats it with the trumpet
or a MIDI keyboard; default 2 bars).

    s = exercises_from_midi(midi, purpose='reading', transform='random')
    s                      ExerciseSet: s.phrases, len(s)
    p = s.phrases[0]       Phrase: notes [start, dur, pitch] (quarters, CONCERT pitch)
    p.to_score(); p.to_midi(); p.reverse_melody(); p.transpose(3); p.to_dict()

Transformations (MATLAB exercise.m): transpose, reverse_melody (pitches
reversed, rhythm kept), reverse_rhythm (rhythm reversed, pitch order kept;
MATLAB reverse_tempo), inversion (mirror around the tonic, back into the scale;
MATLAB canon), mode (church mode on the same tonic; MATLAB modal),
remove_accidentals (MATLAB removealterations), even_eighths (all notes eighths;
MATLAB remove_tempo). 'random' gives every phrase one of them, or none.
Portable: no Qt (music21 only through Score, for engraving).
"""
import copy
import random

PURPOSES = {"reading": 8, "repeat": 2}              # default bars per phrase
LEGACY_PURPOSE = {"dictation": "repeat"}
TRANSFORMS = ("none", "transpose", "reverse_melody", "reverse_rhythm", "inversion", "mode",
              "remove_accidentals", "even_eighths")
TRANSFORM_CHOICES = TRANSFORMS + ("random",)
MIN_NOTES = 4                                        # as exercisegen (auto): at least 4 notes
# SIMPLIFY level (called "difficulty" before 2026-11-08; not the 0-10 rating of difficulty.py):
# shortest note value kept (quarters); 5 = all notes
LEVELS = {1: 2.0, 2: 1.0, 3: 0.5, 4: 0.25, 5: None}
LEVEL_LABELS = {1: "1 – whole and half notes", 2: "2 – + quarter notes", 3: "3 – + eighth notes",
                4: "4 – + sixteenth notes", 5: "5 – all notes"}
# INSTRUMENT of the exercise = the instrument PHYSICALLY played to study (owner, 2026-11-09):
# written = concert + transposition; GM program. Trombone: tenor trombone, reads in C.
# (owner, 2026-11-18): every instrument of the catalogue `instruments.py` (cornet, flugelhorn,
# saxophones, clarinet, flute added); key -> (transposition, GM program)
from . import instruments as _ins                     # noqa: E402
INSTRUMENTS = {k: (r["transposition"], r["program"]) for k, r in _ins.CATALOGUE.items()}
# TRANSPOSITION exercises (owner, 2026-11-06): a part written for another trumpet, read and
# played on the Bb trumpet. written = concert + T: trumpet in C 0, D -2, Eb -3, E -4, F -5
# (the orchestral parts sound above the written note), A +3 (sounds a minor third below).
READ_AS = {"Trumpet in C (transposition)": ("C", 0), "Trumpet in D (transposition)": ("D", -2),
           "Trumpet in Eb (transposition)": ("Eb", -3), "Trumpet in E (transposition)": ("E", -4),
           "Trumpet in F (transposition)": ("F", -5), "Trumpet in A (transposition)": ("A", 3)}
READ_AS_NAMES = {t: n for n, t in READ_AS.values()}
# READ_AS HIDDEN (owner, 2026-11-09: "read C and play D" is an advanced exercise, not used
# now): no selector offers it any more; the code stays and the exercises already made with
# it open and play as before. The transformation 'transpose' (the whole piece in another
# key: you see D, you play D) is a different thing and stays.
EXERCISE_INSTRUMENTS = tuple(INSTRUMENTS)
from . import theory as _th                           # scales and modes: theory engine
MAJOR = _th.SCALES["ionian"]
MODES = {m: i for i, m in enumerate(_th.MODES)}      # degree of the major scale it starts on
TRUMPET_CONCERT = (52, 82)                           # Bb trumpet range, concert pitch
# range of the exercises, WRITTEN pitch (MIDI numbers), per instrument: default from the
# G below the staff (G3) to the F on the top line (F5); Settings > Instruments
# (trombone E2-Bb4, owner 2026-11-09; the other instruments: instruments.CATALOGUE)
RANGE_DEFAULT = {k: tuple(r["range"]) for k, r in _ins.CATALOGUE.items()}
TRUMPET_PROGRAMS = (56, 59)                          # GM trumpet, muted trumpet
TROMBONE_PROGRAMS = (57,)                            # GM trombone
# instruments that play ONE voice: every wind instrument
ONE_VOICE = tuple(r["played"] for r in _ins.CATALOGUE.values() if r["family"] != "keyboard")
# the clef of an instrument (forced): trumpet treble, trombone bass…
CLEFS = {r["played"]: r["clef"] for r in _ins.CATALOGUE.values() if r["clef"]}
# concert range (MIDI) where the notes of an instrument are searched in a recording
# (trombone D2-D5; the trumpet, cornet, flugelhorn: transcribe.RANGE)
DETECT_RANGE = {r["played"]: tuple(r["detect"]) for r in _ins.CATALOGUE.values()
                if r["detect"] and r["family"] != "keyboard"}
# THE INSTRUMENT OF AN EXERCISE (owner, 2026-11-08): every exercise knows the instrument it
# is played on ('trumpet', 'piano'; later trombone, tuba, sax…), because the rules change
# with it (range, difficulty…). Exercise instrument choice -> instrument played.
PLAYED_ON = {k: r["played"] for k, r in _ins.CATALOGUE.items()}
# name of the part of a random exercise (owner, 2026-11-09: nothing says "duet" to the user)
PART_NAMES = {k: r["part"] for k, r in _ins.CATALOGUE.items()}
PLAYED_ON.update({k: "trumpet" for k in READ_AS})       # transpositions: read, played on Bb


def instrument_of_program(program):
    p = int(program)
    if p in _ins.PROGRAM_PLAYED:
        return _ins.PROGRAM_PLAYED[p]
    return "piano" if p < 8 else "other"


def _treble(score):
    """TRUMPET = TREBLE CLEF (owner, 2026-11-08: a lip slur on 123 came out in the bass
    clef): music21 picks the clef from the mean height of the notes; an exercise played on
    the trumpet always gets the treble clef (low notes on ledger lines)."""
    return _clef(score, "treble")


def _clef(score, which):
    """The clef of the instrument on every part ('treble', 'bass'; CLEFS): the trumpet
    treble, the trombone bass (owner, 2026-11-09)."""
    from music21 import clef
    make = {"treble": clef.TrebleClef, "bass": clef.BassClef}[which]
    for part in score.m21.parts:
        for c in list(part.recurse().getElementsByClass("Clef")):
            c.activeSite.remove(c)
        ms = part.getElementsByClass("Measure")
        if len(ms):
            ms[0].insert(0, make())
        else:
            part.insert(0, make())
    return score


def _positions(score, instrument, transposition):
    """SHOW POSITIONS (owner, 2026-11-09): the valves (trumpet) / slide position (trombone)
    of every note written under it (a lyric), from fingerings.py; the note played =
    concert = written - transposition on the instrument played (`instrument`); a tied
    continuation gets none; instruments without fingerings: nothing."""
    from .fingerings import fingering_concert, has_fingerings
    if not has_fingerings(instrument):
        return score
    for n in score.m21.recurse().notes:
        if n.isChord:
            continue
        if n.tie is not None and n.tie.type in ("stop", "continue"):
            continue
        f = fingering_concert(instrument, n.pitch.midi - transposition)
        if f:
            n.addLyric(f)
    return score


def instrument_range(instrument):
    """(lowest, highest) written pitch of the exercises for an instrument
    (settings of the current user, key 'ranges'; default RANGE_DEFAULT)."""
    lo, hi = RANGE_DEFAULT[instrument]
    try:
        from .progress import settings
        v = settings().get("ranges", {}).get(instrument)
        if v:
            lo, hi = int(v[0]), int(v[1])
    except Exception:
        pass
    return lo, hi


def set_instrument_range(instrument, lowest=None, highest=None):
    """Save the written range of an instrument (None = default). At least an
    octave (11 semitones apart), so that every note can be moved into it."""
    from .progress import save_setting, settings
    if instrument not in INSTRUMENTS:
        raise ValueError(f"instrument must be one of {', '.join(INSTRUMENTS)}")
    d0 = RANGE_DEFAULT[instrument]
    lo = int(d0[0] if lowest is None else lowest)
    hi = int(d0[1] if highest is None else highest)
    if hi - lo < 11:
        raise ValueError(f"range {lo}-{hi} too small: at least an octave is needed")
    allr = dict(settings().get("ranges", {}))
    allr[instrument] = [lo, hi]
    save_setting("ranges", allr)
    return lo, hi


def fit_range(notes, transposition, lowest, highest):
    """Every note outside the WRITTEN range [lowest, highest] is moved by octaves
    into it (one note at a time; the others stay). notes: [start, dur, concert]."""
    out, seen = [], set()
    for s, d, p in notes:
        w = p + transposition
        while w < lowest:
            w += 12
        while w > highest:
            w -= 12
        if w < lowest:                   # range smaller than an octave: nearest edge
            w += 12 if (w + 12 - highest) < (lowest - w) else 0
        key = (round(s, 6), w)
        if key in seen:                  # two notes of a chord folded on the same pitch
            continue
        seen.add(key)
        out.append([s, d, w - transposition])
    return out


def octave_fit(notes, transposition, lowest, highest):
    """The WHOLE exercise moved by octaves into the written range [lowest, highest]: the
    shift with the fewest notes outside (a tie: the one closest to 0). Used for the random
    exercises (pieces of duets for trumpets played on the trombone: an octave lower,
    owner 2026-11-09); the notes still outside are then moved one by one (fit_range)."""
    if not notes:
        return notes
    best = None
    for k in range(-4, 5):
        out = sum(1 for _, _, p in notes
                  if not lowest <= p + transposition + 12 * k <= highest)
        key = (out, abs(k))
        if best is None or key < best[0]:
            best = (key, k)
    k = best[1]
    return [[s, d, p + 12 * k] for s, d, p in notes]


def mode_scale(mode):
    return _th.scale(mode)


class Phrase:
    """A short melody to practise: notes [start, dur, pitch] in quarters from
    the start of the phrase, concert pitch (like Midi objects)."""

    def __init__(self, notes, bars, ts=(4, 4), tonic=0, mode="ionian", bpm=90.0, program=56,
                 part="", title="", source="", transform="none", purpose="reading", start_bar=1,
                 uid=None, grades=None, transposition=None, level=5, results=None, origin=None,
                 practice_bpm=None, source_midi=None, instrument=None, ts_changes=None):
        self.notes = [[float(s), float(d), int(p)] for s, d, p in sorted(notes)]
        self.bars = int(bars)
        self.ts = (int(ts[0]), int(ts[1]))
        self.tonic = int(tonic) % 12
        self.mode = mode
        self.bpm = float(bpm)
        self.program = int(program)
        self.part = part
        self.title = title
        self.source = source
        self.transform = transform
        self.purpose = LEGACY_PURPOSE.get(purpose, purpose)
        self.start_bar = int(start_bar)
        self.uid = uid or __import__("uuid").uuid4().hex[:12]   # identity of the exercise
        self.grades = dict(grades or {})       # user -> last grade (before 2026-11-07, shown only)
        self.results = dict(results or {})     # user -> [attempts] (tasks.add_result)
        self.origin = origin                   # how it was made: {'midi': {...}, 'duet': {...}}
        self.practice_bpm = practice_bpm       # tempo of the exercise (None: from Settings)
        self.source_midi = source_midi         # the MIDI it was cut from (base64), see remake()
        # written = concert + transposition ("transposed of"): Bb instruments 2, C 0
        self.transposition = int(transposition if transposition is not None
                                 else (2 if self.program in TRUMPET_PROGRAMS else 0))
        self.level = int(level)
        # the instrument it is played on ('trumpet', 'piano'…); old exercises: from the program
        self.instrument = instrument or instrument_of_program(self.program)
        self.ts_changes = ([(int(b), (int(t[0]), int(t[1]))) for b, t in ts_changes]
                           if ts_changes else None)

    # ---------------------------------------------------------- info
    @property
    def bar_q(self):
        return self.ts[0] * 4.0 / self.ts[1]

    @property
    def length_q(self):
        if not self.ts_changes:
            return self.bars * self.bar_q
        changes = dict(self.ts_changes)
        cur = self.ts
        total = 0.0
        for b in range(self.bars):
            if b in changes:
                cur = changes[b]
            total += cur[0] * 4.0 / cur[1]
        return total

    def __len__(self):
        return len(self.notes)

    @property
    def polyphonic(self):
        return len({s for s, _, _ in self.notes}) < len(self.notes)

    def events(self):
        """Notes grouped by onset: [(start, dur, [pitches])] (chords = one event)."""
        ev = {}
        for s, d, p in self.notes:
            e = ev.setdefault(s, [s, d, []])
            e[1] = max(e[1], d)
            e[2].append(p)
        return [ev[k] for k in sorted(ev)]

    def first_note(self, written=True):
        """Name of the first note (written pitch by default, e.g. 'G4'; C4 = middle C);
        in a chord the highest. None if the phrase has no notes."""
        if not self.notes:
            return None
        from .notes import note_name
        s0 = min(s for s, _, _ in self.notes)
        p = max(p for s, _, p in self.notes if abs(s - s0) < 1e-6)
        return note_name(p + (self.transposition if written else 0))

    def grade(self, user):
        """Grade shown: the best of today, else the last one (tasks.shown_grade)."""
        from .tasks import shown_grade
        return shown_grade(self, user)

    def __repr__(self):
        return f"Phrase('{self.title}', {len(self.notes)} notes, {self.bars} bars, {self.transform})"

    def to_dict(self, embed=True):
        """embed=False: the source MIDI is left out (a group stores it once, by key)."""
        d = dict(notes=self.notes, bars=self.bars, ts=list(self.ts), tonic=self.tonic,
                 mode=self.mode, bpm=self.bpm, program=self.program, part=self.part,
                 title=self.title, source=self.source, transform=self.transform,
                 purpose=self.purpose, start_bar=self.start_bar, uid=self.uid,
                 grades=self.grades, transposition=self.transposition, level=self.level,
                 results=self.results, origin=self.origin, practice_bpm=self.practice_bpm,
                 instrument=self.instrument)
        if embed and self.source_midi:
            d["source_midi"] = self.source_midi
        if self.ts_changes:
            d["ts_changes"] = [[b, list(t)] for b, t in self.ts_changes]
        return d

    @classmethod
    def from_dict(cls, d, sources=None):
        d = dict(d)
        ref = d.pop("source_ref", None)
        if ref and sources and not d.get("source_midi"):
            d["source_midi"] = sources.get(ref)
        known = cls.__init__.__code__.co_varnames
        return cls(**{k: v for k, v in d.items() if k in known})

    def can_remake(self):
        """Can it be cut again from its MIDI (other bars, part, difficulty…)?"""
        return bool(self.source_midi and (self.origin or {}).get("midi"))

    def copy(self, **changes):
        """Copy (a new exercise: new uid, no grades, no results)."""
        d = copy.deepcopy(self.to_dict())
        d["uid"], d["grades"], d["results"] = None, None, None
        p = Phrase.from_dict(d)
        for k, v in changes.items():
            setattr(p, k, v)
        return p

    # ---------------------------------------------------------- output
    def key_number(self):
        """pretty_midi key number of the key signature (major key with the same
        signature as tonic + mode)."""
        rel = (self.tonic - MAJOR[MODES[self.mode]]) % 12
        return rel

    def to_midi(self):
        """Midi object (concert pitch)."""
        import pretty_midi
        from .midi import Midi
        spq = 60.0 / self.bpm
        pm = pretty_midi.PrettyMIDI(initial_tempo=self.bpm)
        if self.ts_changes:
            changes = dict(self.ts_changes)
            cur = self.ts
            q = 0.0
            for b in range(self.bars):
                if b in changes:
                    cur = changes[b]
                if b == 0 or b in changes:
                    pm.time_signature_changes.append(
                        pretty_midi.TimeSignature(cur[0], cur[1], q * spq))
                q += cur[0] * 4.0 / cur[1]
        else:
            pm.time_signature_changes.append(pretty_midi.TimeSignature(self.ts[0], self.ts[1], 0.0))
        pm.key_signature_changes.append(pretty_midi.KeySignature(self.key_number(), 0.0))
        ins = pretty_midi.Instrument(program=self.program, name=self.part or "Melody")
        for s, d, p in self.notes:
            ins.notes.append(pretty_midi.Note(80, p, s * spq, (s + d) * spq))
        pm.instruments.append(ins)
        m = Midi()
        m.pm = pm
        m.source = None
        m.title = self.title
        return m

    @property
    def read_as(self):
        """'C', 'D', 'Eb', 'E', 'F', 'A' for a transposition exercise (a trumpet part
        written for another trumpet), else None."""
        if self.program in TRUMPET_PROGRAMS and self.transposition != 2:
            return READ_AS_NAMES.get(self.transposition)
        return None

    def to_score(self, positions=False):
        """Score (written pitch for transposing instruments), padded to its bars.
        Transposition exercises: written for the trumpet read (self.transposition).
        positions=True: the valves / slide positions under the notes (instruments of
        fingerings.py)."""
        from .score import Score
        if self.read_as is not None:                   # music21 knows only the Bb trumpet
            m = self.copy(program=0)
            m.notes = [[st, d, p + self.transposition] for st, d, p in self.notes]
            m.tonic = (self.tonic + self.transposition) % 12
            m.part = self.part or f"Trumpet in {self.read_as}"
            s = Score.from_midi(m.to_midi(), title=self.title, written=False)
        else:
            s = Score.from_midi(self.to_midi(), title=self.title)
        missing = int(round(self.length_q - float(s.m21.highestTime)))
        if missing > 0:                                # trailing rests up to the last bar
            from music21 import note
            for p in s.m21.parts:
                ms = p.getElementsByClass("Measure")
                last = ms[-1] if len(ms) else None
                if last is not None and last.barDuration.quarterLength > last.duration.quarterLength:
                    last.append(note.Rest(quarterLength=last.barDuration.quarterLength
                                          - last.duration.quarterLength))
        if self.instrument in CLEFS:
            _clef(s, CLEFS[self.instrument])
        if positions:
            _positions(s, self.instrument, self.transposition)
        return s

    # ---------------------------------------------------------- transformations
    def _scale(self):
        return {(self.tonic + i) % 12 for i in mode_scale(self.mode)}

    def _sharp_side(self):
        """+1 for sharp key signatures, -1 for flat ones (MATLAB removealterations)."""
        import pretty_midi
        acc = pretty_midi.key_number_to_mode_accidentals(self.key_number())[1]
        return 1 if acc >= 0 else -1

    def _named(self, what, **changes):
        tag = what if self.transform == "none" else f"{self.transform}+{what}"
        p = self.copy(**changes)
        p.transform = tag
        p.title = _title(p)
        return p

    def transpose(self, k):
        """k semitones up (down if negative); the key follows."""
        p = self._named(f"transpose {k:+d}")
        p.notes = [[s, d, n + k] for s, d, n in self.notes]
        p.tonic = (self.tonic + k) % 12
        return p

    def reverse_melody(self):
        """Pitches in reverse order, rhythm unchanged."""
        p = self._named("reverse_melody")
        ev = self.events()
        chords = [c for _, _, c in ev][::-1]
        p.notes = [[s, d, n] for (s, d, _), c in zip(ev, chords) for n in c]
        return p

    def reverse_rhythm(self):
        """Rhythm (durations and rests) reversed, pitches kept in order."""
        p = self._named("reverse_rhythm")
        L = self.length_q
        ev = self.events()
        slots = sorted([L - s - d, d] for s, d, _ in ev)
        p.notes = [[s, d, n] for (s, d), (_, _, c) in zip(slots, ev) for n in c]
        return p

    def inversion(self):
        """Diatonic mirror around the tonic (a third up becomes a third down);
        notes outside the scale are mirrored chromatically and moved back into it
        (MATLAB canon); moved by octaves to keep the register."""
        p = self._named("inversion")
        sc = mode_scale(self.mode)
        scale, d = self._scale(), self._sharp_side()
        mean = sum(n for _, _, n in self.notes) / len(self.notes)
        t = self.tonic + 12 * round((mean - self.tonic) / 12)
        out = []
        for s_, du, n in self.notes:
            rel = n - t
            o, r = divmod(rel, 12)
            if r in sc:
                deg = -(o * 7 + sc.index(r))            # mirrored degree
                o2, i2 = divmod(deg, 7)
                m = t + 12 * o2 + sc[i2]
            else:
                m = t - rel
                if m % 12 not in scale:
                    m += d
            out.append([s_, du, m])
        shift = 12 * round((mean - sum(n for _, _, n in out) / len(out)) / 12)
        p.notes = [[s_, du, n + shift] for s_, du, n in out]
        return p

    def to_mode(self, mode):
        """Same tonic, another church mode: the scale degrees move."""
        cur, new = mode_scale(self.mode), mode_scale(mode)
        p = self._named(f"mode {mode}", mode=mode)
        out = []
        for s, d, n in self.notes:
            rel = (n - self.tonic) % 12
            if rel in cur:
                n += new[cur.index(rel)] - rel
            out.append([s, d, n])
        p.notes = out
        return p

    def remove_accidentals(self):
        """Notes outside the scale moved one semitone into it."""
        p = self._named("remove_accidentals")
        scale, d = self._scale(), self._sharp_side()
        p.notes = [[s, du, n if n % 12 in scale else n + d] for s, du, n in self.notes]
        return p

    def even_eighths(self):
        """Every note an eighth, one after the other (MATLAB remove_tempo)."""
        p = self._named("even_eighths")
        ev = self.events()
        p.notes = [[0.5 * i, 0.5, n] for i, (_, _, c) in enumerate(ev) for n in c]
        p.bars = max(1, -(-len(ev) * 0.5 // self.bar_q))
        p.bars = int(p.bars)
        return p

    def transformed(self, name, rng=None, note_range=None):
        """Apply a transformation by name ('random': one of them or none).
        note_range: (lowest, highest) WRITTEN pitch allowed for 'transpose'."""
        rng = rng or random.Random()
        if name == "random":
            name = rng.choice(TRANSFORMS)
        if name == "none":
            return self
        if name.startswith("transpose "):                # exact tag, e.g. 'transpose +3'
            return self.transpose(int(name.split()[1]))
        if name.startswith("mode "):                     # exact tag, e.g. 'mode dorian'
            return self.to_mode(name.split(" ", 1)[1])
        if name == "transpose":
            ks = [k for k in range(-5, 7) if k and self._fits(k, note_range)]
            return self.transpose(rng.choice(ks)) if ks else self
        if name == "mode":
            return self.to_mode(rng.choice([m for m in MODES if m != self.mode]))
        return getattr(self, name)()

    def _fits(self, k, note_range=None):
        if note_range is not None:                       # written range of the instrument
            lo, hi = note_range[0] - self.transposition, note_range[1] - self.transposition
        else:
            lo, hi = TRUMPET_CONCERT if self.program in TRUMPET_PROGRAMS else (21, 108)
        return all(lo <= n + k <= hi for _, _, n in self.notes)


def _title(p):
    t = f"{p.source} – {p.part} – bars {p.start_bar}-{p.start_bar + p.bars - 1}" if p.part \
        else f"{p.source} – bars {p.start_bar}-{p.start_bar + p.bars - 1}"
    return t if p.transform == "none" else f"{t} ({p.transform})"


def simplify(notes, level, length_q):
    """Brutal simplification for a difficulty level: only notes starting on the grid of
    the shortest value allowed are kept; each lasts until the next kept note (or its
    own end, rounded to the grid), never less than that value."""
    q = LEVELS.get(int(level))
    if not q:
        return [list(n) for n in notes]
    kept = {}
    for s, d, p in sorted(notes):
        if abs(s / q - round(s / q)) < 1e-6:
            if s not in kept or p > kept[s][2]:
                kept[s] = [s, d, p]
    starts = sorted(kept)
    out = []
    for i, s in enumerate(starts):
        _, d, p = kept[s]
        nxt = starts[i + 1] if i + 1 < len(starts) else length_q
        end = s + max(q, -(-d // q) * q)                 # own end, rounded up to the grid
        d = max(q, min(end, nxt) - s)
        out.append([s, min(d, length_q - s), p])
    return [n for n in out if n[1] > 0]


def _drop_empty_bars(numbers, offs, end, notes):
    """Remove the bars where no note sounds; later bars and notes move back."""
    spans = []
    for i, m in enumerate(numbers):
        a = offs[m]
        b = offs[numbers[i + 1]] if i + 1 < len(numbers) else end
        spans.append((m, a, b))
    empty = [(a, b) for m, a, b in spans
             if not any(s < b - 1e-6 and s + d > a + 1e-6 for s, d, _ in notes)]
    if not empty:
        return numbers, offs, end, notes

    def removed_before(t):
        return sum(b - a for a, b in empty if b <= t + 1e-6)
    kept = [m for m, a, b in spans if (a, b) not in empty]
    new_offs = {m: offs[m] - removed_before(offs[m]) for m in kept}
    new_notes = [[s - removed_before(s), d, p] for s, d, p in notes]
    return kept, new_offs, end - removed_before(end), new_notes


class ExerciseSet:
    """A group of phrases (shown as one expandable item in the GUI)."""

    def __init__(self, phrases, title="", source="", purpose="reading", transform="none"):
        self.phrases = list(phrases)
        self.title = title
        self.source = source
        self.purpose = LEGACY_PURPOSE.get(purpose, purpose)
        self.transform = transform

    def __len__(self):
        return len(self.phrases)

    def __iter__(self):
        return iter(self.phrases)

    def __getitem__(self, k):
        return self.phrases[k]

    def __repr__(self):
        return f"ExerciseSet('{self.title}', {len(self.phrases)} phrases, {self.purpose})"

    def to_dict(self):
        """The source MIDIs of the phrases are stored once (`sources`, by key)."""
        sources, phrases = {}, []
        for p in self.phrases:
            d = p.to_dict(embed=False)
            if p.source_midi:
                key = _b64_key(p.source_midi)
                sources[key] = p.source_midi
                d["source_ref"] = key
            phrases.append(d)
        out = dict(title=self.title, source=self.source, purpose=self.purpose,
                   transform=self.transform, phrases=phrases)
        if sources:
            out["sources"] = sources
        return out

    @classmethod
    def from_dict(cls, d):
        src = d.get("sources") or {}
        return cls([Phrase.from_dict(p, src) for p in d["phrases"]], d.get("title", ""),
                   d.get("source", ""), d.get("purpose", "reading"), d.get("transform", "none"))


# ---------------------------------------------------------------- files
EXERCISES_FORMAT = "musikite-exercises"


def exercises_to_dict(obj):
    """File content of an exercise group or of ONE exercise (owner's rule: exercises are
    saved only as exercises, never as MIDI / PDF / audio). One exercise = a group of one
    with single=True, read back as an exercise (Phrase), not as a group."""
    if isinstance(obj, Phrase):
        d = ExerciseSet([obj], title=obj.title, source=obj.source, purpose=obj.purpose,
                        transform=obj.transform).to_dict()
        return dict(format=EXERCISES_FORMAT, single=True, **d)
    if isinstance(obj, ExerciseSet):
        return dict(format=EXERCISES_FORMAT, **obj.to_dict())
    raise TypeError(f"not an exercise: {type(obj).__name__}")


def exercises_from_dict(d):
    """ExerciseSet, or the Phrase of a file written for one exercise."""
    s = ExerciseSet.from_dict(d)
    return s.phrases[0] if d.get("single") and len(s.phrases) == 1 else s


EXERCISE_EXT = ".mke"            # MusiKitE exercise: ONE zip with the compact JSON inside
ROUTINE_EXT = ".mkr"             # MusiKitE routine: the same, zipped too (owner, 2026-11-08)
ZIP_EXTS = {EXERCISE_EXT: "exercise.json", ROUTINE_EXT: "routine.json"}
MKE_MEMBER = "exercise.json"


def write_exercise_file(d, path, default_ext=EXERCISE_EXT):
    """Exercise files (owner, 2026-11-08): COMPACT JSON (no indentation); '.mke' = a zip
    archive (deflate) with that JSON as 'exercise.json' (any zip tool opens it, also Android:
    java.util.zip); '.mkr' = a routine, zipped the same way ('routine.json'); '.json' = the
    plain compact JSON. Other extension: default_ext is added."""
    import json
    import os
    ext = os.path.splitext(path)[1].lower()
    if ext not in tuple(ZIP_EXTS) + (".json",):
        path += default_ext
        ext = default_ext
    text = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    if ext in ZIP_EXTS:
        import zipfile
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.writestr(ZIP_EXTS[ext], text)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return path


def read_exercise_file(path):
    """The dict of an exercise file: .mke (zip) or .json (indented or compact)."""
    import json
    import zipfile
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            name = next((n for n in ZIP_EXTS.values() if n in names), names[0])
            return json.loads(z.read(name).decode("utf-8"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_exercises(obj, path):
    """Write an exercise group / one exercise: .mke (zip, default) or .json (compact)."""
    return write_exercise_file(exercises_to_dict(obj), path)


def load_exercises(path):
    return exercises_from_dict(read_exercise_file(path))


def _key_of(midi, score):
    """(tonic pitch class, mode) of the source: MIDI key signature, else estimated by the
    theory engine (port of the owner's tonalita.m + minor if it starts / ends on the tonic
    of the relative minor; no music21)."""
    ks = midi.pm.key_signature_changes
    if ks:
        k = ks[0].key_number
        return (k % 12, "aeolian" if k >= 12 else "ionian")
    notes = [[n.start, n.end - n.start, n.pitch] for i in midi.pm.instruments
             if not i.is_drum for n in i.notes]
    return _th.key_of_notes(notes)


def exercises_from_midi(obj, purpose="reading", bars=None, transform="none", parts=None,
                        seed=None, title=None, min_notes=None, polyphony=False, level=5,
                        instrument="Bb (trumpet)", remove_empty=True, note_range=None,
                        bar_range=None, practice_bpm=None, transpose=0, include_midi=True,
                        whole_octaves=False):
    """ExerciseSet of phrases of `bars` bars (default 8 for reading, 2 for repeat)
    cut from a Midi or Score (parts: list of part indices, None = all), each with
    `transform` applied ('random': a different one, or none, per phrase).
    polyphony=False (default): one exercise per part, one voice only (in a chord
    the highest note is kept); True: all the selected parts together in one
    exercise (e.g. the whole duet).
    level 1..5: difficulty (1 whole and half notes, 2 + quarters, 3 + eighths,
    4 + sixteenths, 5 everything); the extra notes are removed (simplify).
    instrument: 'Bb (trumpet)' (written a tone above, trumpet sound), 'C (piano)' or
    'C (trombone)' (bass clef, one voice). whole_octaves=True: the whole piece is first
    moved by octaves into the range (octave_fit; random exercises from duets).
    remove_empty: bars with rests only are removed before cutting the phrases.
    note_range: (lowest, highest) WRITTEN pitch; default: Settings > Instruments
    (instrument_range). Notes outside it are moved by octaves into it, one by one,
    after the transformation.
    Phrases with fewer than min_notes notes are skipped (as exercisegen; default 4,
    fewer at the easy levels).
    bar_range=(first, last): ONE phrase with the bars first..last (numbers of the MIDI;
    empty bars removed if remove_empty) — used by remake(). transform may also be an exact
    tag ('transpose +3', 'mode dorian', 'inversion'…).
    practice_bpm: tempo of the exercises (None: Settings > Exercises when practised).
    include_midi=False ("do not include MIDI", owner 2026-11-08): no trace of the source
    MIDI in the exercises (no `source_midi`, no `origin['midi']`): they cannot be cut again,
    only their tempo and a transposition can change.
    transpose: semitones applied after the transformation (remembered in origin, so a
    transformed AND transposed exercise can be cut again: scripts/makeexercises.py).
    Every phrase remembers its MIDI (`source_midi`, base64) and how it was cut
    (`origin['midi']`: part, bars, difficulty, instrument, transformation…)."""
    instrument_asked = instrument
    if PLAYED_ON.get(instrument) in ONE_VOICE:
        polyphony = False                # owner, 2026-11-08: a trumpet (trombone) plays ONE voice
    read_as = READ_AS.get(instrument)
    if read_as is not None:              # transposition: generated for the Bb trumpet (its
        instrument = "Bb (trumpet)"      # range), then written for the trumpet read
    if instrument not in INSTRUMENTS:
        raise ValueError(f"instrument must be one of {', '.join(EXERCISE_INSTRUMENTS)}")
    transposition, inst_program = INSTRUMENTS[instrument]
    note_range = tuple(note_range) if note_range else instrument_range(instrument)
    if min_notes is None:
        min_notes = {1: 2, 2: 3}.get(int(level), MIN_NOTES)
    from .midi import Midi
    from .score import Score
    from music21 import stream
    if purpose not in PURPOSES:
        raise ValueError(f"purpose must be one of {', '.join(PURPOSES)}")
    if transform not in TRANSFORM_CHOICES and transform not in transform_tags():
        raise ValueError(f"transform must be one of {', '.join(TRANSFORM_CHOICES)}")
    bars = int(bars or PURPOSES[purpose])
    rng = random.Random(seed)
    midi = obj.to_midi() if isinstance(obj, Score) else obj
    if not isinstance(midi, Midi):
        raise TypeError("exercises_from_midi needs a Midi or Score object")
    src = title or getattr(obj, "title", None) or (
        __import__("os").path.splitext(__import__("os").path.basename(midi.source))[0]
        if getattr(midi, "source", None) else "MIDI")
    score = Score.from_midi(midi, written=False)                 # concert pitch
    midi_b64 = _midi_b64(midi)
    tonic, mode = _key_of(midi, score)
    bpm = score.tempo() or (midi.tempo() if hasattr(midi, "tempo") else None) or 90.0
    tracks = [i for i in midi.pm.instruments if i.notes]
    names = score.parts()
    many = len(names) > 1
    phrases = []
    per_part = []                    # (ip, program, notes, measures, offsets, tsig, end)
    for ip, part in enumerate(score.m21.parts):
        if parts is not None and ip not in parts:
            continue
        program = tracks[ip].program if ip < len(tracks) else 56
        measures = list(part.getElementsByClass(stream.Measure))
        if not measures:
            continue
        offs = {m.number: float(m.offset) for m in measures}
        ts = part.recurse().getElementsByClass("TimeSignature").first()
        tsig = (ts.numerator, ts.denominator) if ts is not None else (4, 4)
        notes = []
        for r in score.table(part=ip).itertuples():
            if r.pitch is None or str(r.pitch) == "<NA>":
                continue
            s, d, p = float(r.start), float(r.dur), int(r.pitch)
            if r.tie in ("stop", "continue") and notes:
                prev = [n for n in notes if n[2] == p and abs(n[0] + n[1] - s) < 1e-6]
                if prev:
                    prev[-1][1] += d
                    continue
            notes.append([s, d, p])
        if not polyphony:            # one voice: highest note of every chord
            top = {}
            for n in notes:
                if n[0] not in top or n[2] > top[n[0]][2]:
                    top[n[0]] = n
            notes = [top[k] for k in sorted(top)]
        per_part.append((ip, program, notes, [m.number for m in measures], offs, tsig,
                         float(part.highestTime)))
    groups = [[x] for x in per_part] if not polyphony else ([per_part] if per_part else [])
    for grp in groups:
        ip, program, _, numbers, offs, tsig, end = grp[0]
        notes = sorted(n for g in grp for n in g[2])
        if remove_empty:
            numbers, offs, end, notes = _drop_empty_bars(numbers, offs, end, notes)
        pname = names[ip] if (many and not polyphony) else ("all parts" if many else "")
        if bar_range is not None:
            first, last = int(bar_range[0]), int(bar_range[1])
            idx = [i for i, m in enumerate(numbers) if first <= m <= last]
            if not idx:
                raise ValueError(f"no bars {first}-{last} in {src}")
            chunks = [(idx[0], idx[-1] + 1)]
        else:
            chunks = [(k, min(k + bars, len(numbers))) for k in range(0, len(numbers), bars)]
        for a, e in chunks:
            group = numbers[a:e]
            t0 = offs[group[0]]
            t1 = offs[numbers[e]] if e < len(numbers) else end
            sel = [[s - t0, min(d, t1 - s), p] for s, d, p in notes if t0 - 1e-6 <= s < t1 - 1e-6]
            sel = simplify(sel, level, t1 - t0)
            if len({s for s, _, _ in sel}) < (1 if bar_range is not None else min_notes):
                if bar_range is not None:
                    raise ValueError(f"no notes in bars {group[0]}-{group[-1]}")
                continue
            ph = Phrase(sel, len(group), tsig, tonic, mode, bpm, inst_program, pname, "", src,
                        "none", purpose, group[0], transposition=transposition, level=level)
            ph.title = _title(ph)
            if whole_octaves:                # the whole piece by octaves first (melody kept)
                ph.notes = octave_fit(ph.notes, transposition, *note_range)
            ph = ph.transformed(transform, rng, note_range)
            applied = ph.transform
            if int(transpose):
                ph = ph.transpose(int(transpose))
            ph.notes = sorted(fit_range(ph.notes, transposition, *note_range))
            ph.practice_bpm = practice_bpm
            ph.instrument = PLAYED_ON.get(instrument_asked, ph.instrument)
            ph.source_midi = midi_b64
            ph.origin = dict(midi=dict(
                title=src, part=None if polyphony else ip, parts=list(names),
                first=group[0], last=group[-1], bars=[numbers[0], numbers[-1]],
                level=int(level), instrument=instrument_asked, transform=applied,
                transpose=int(transpose),
                remove_empty=bool(remove_empty), polyphony=bool(polyphony), purpose=purpose))
            if not include_midi:             # no trace of the source MIDI
                ph.source_midi = None
                ph.origin = {k: v for k, v in ph.origin.items() if k != "midi"} or None
            phrases.append(ph)
    tag = ("" if transform == "none" else f", {transform}") + (", polyphony" if polyphony else "")
    tag += f", level {level}, {instrument.split(' ')[0]}"
    if read_as is not None:
        name, t = read_as
        for ph in phrases:
            ph.transposition = t
            ph.part = f"Trumpet in {name}"
            ph.title = f"{ph.title} – read as trumpet in {name}"
        tag += f", read as trumpet in {name}"
    label = {"reading": "reading", "repeat": "listen & repeat"}.get(purpose, purpose)
    return ExerciseSet(phrases, f"{src} – {len(phrases)} exercises ({label}{tag})", src,
                       purpose, transform)


# ---------------------------------------------------------------- one exercise from a duet
DUET_LEVEL = {1: 1, 2: 1, 3: 2, 4: 3, 5: 3}     # difficulty of the exercise -> duet level
DUET_PARTS = ("random", "1", "2")


# KEY OF THE RANDOM EXERCISES (owner, 2026-11-17: with the piano every random exercise was in
# Bb — the duets are written in C for the Bb trumpet —; "the key must be random, no sharps or
# flats for the easy levels, then more and more"): the WRITTEN key of the instrument played is
# drawn among the keys with at most N sharps / flats (major or minor); "auto" = N from the
# Simplify level. The trumpet reads in C at the easy levels as before.
LEVEL_ACCIDENTALS = {1: 0, 2: 0, 3: 1, 4: 3, 5: 5}
KEY_SIG_LABELS = {"auto": "auto (from Simplify)", 0: "none (C / Am)", 1: "up to 1 sharp / flat",
                  2: "up to 2", 3: "up to 3", 4: "up to 4", 5: "up to 5", 6: "up to 6"}


def key_sig_value(v):
    """'auto' / 0..6 from a value or a label of KEY_SIG_LABELS."""
    if v is None or v == "auto":
        return "auto"
    for k, t in KEY_SIG_LABELS.items():
        if v == t:
            return k
    try:
        return max(0, min(6, int(v)))
    except (TypeError, ValueError):
        return "auto"


def random_written_key(max_accidentals, rng=None):
    """A key name of progressions.KEYS (major or minor) with at most `max_accidentals`
    sharps / flats in its key signature."""
    from .progressions import KEYS, key_parts
    from .theory import key_signature
    rng = rng or random.Random()
    cands = []
    for k in KEYS:
        tonic, minor = key_parts(k)
        if abs(key_signature(tonic, "aeolian" if minor else "ionian")) <= int(max_accidentals):
            cands.append(k)
    return rng.choice(cands or ["C"])


def exercise_from_duet(purpose="reading", bars=None, level=3, instrument="Bb (trumpet)",
                       part="random", seed=None, key_sig="auto"):
    """ONE exercise (Phrase) cut from a NEW duet for two trumpets (owner: Practice > Read &
    play is done on a random melody: a piece of a generated duet). part: '1', '2' or
    'random'; bars None = 8 (reading) / 2 (repeat); level = difficulty 1-5 (the duet level
    follows it, DUET_LEVEL); instrument as exercises_from_midi (the whole piece is first moved by
    octaves into its range: a trombone plays it an octave lower).
    key_sig: at most this many sharps / flats in the WRITTEN key (0-6) or 'auto' (from the
    level, LEVEL_ACCIDENTALS); the key is drawn at random for every exercise.
    The phrase keeps how it was made (`origin`), so a routine can make a new one each day."""
    import contextlib
    import io
    from .midi import Midi
    from .progressions import key_parts, key_name, chords_to_key
    from .duet import DEFAULT_CHORDS
    rng = random.Random(seed)
    level = int(level)
    key_sig = key_sig_value(key_sig)
    max_acc = LEVEL_ACCIDENTALS.get(level, 1) if key_sig == "auto" else int(key_sig)
    trasp = INSTRUMENTS.get(instrument, (None,))[0]     # None: a hidden transposition
    for _ in range(8):
        dseed = rng.randrange(1000000)
        duet_kw = {}
        if trasp is not None:                    # the written key -> the concert key
            tonic, minor = key_parts(random_written_key(max_acc, rng))
            concert = key_name(tonic - trasp, minor)
            duet_kw = dict(chords=chords_to_key(DEFAULT_CHORDS, "C", concert), key=concert,
                           concert=True)
        with contextlib.redirect_stdout(io.StringIO()):
            m = Midi().makeduet(level=DUET_LEVEL.get(level, 2), seed=dseed, rounds=2,
                                **duet_kw)
        p = int(part) if str(part) in ("1", "2") else rng.choice((1, 2))
        st = exercises_from_midi(m, purpose=purpose, bars=bars, parts=[p - 1], level=level,
                                 instrument=instrument, seed=rng.randrange(1000000),
                                 title=f"Random {dseed}", whole_octaves=True)
        if st.phrases:
            ph = rng.choice(st.phrases)
            ph.part = PART_NAMES.get(instrument, ph.part)   # the instrument played, not
            ph.title = _title(ph)                           # "Trumpet in Bb 2" of the duet
            ph.origin = dict(ph.origin or {}, duet=dict(purpose=purpose, bars=bars, level=level,
                                                        instrument=instrument, part=str(part),
                                                        key_sig=key_sig))
            return ph
    raise RuntimeError("no exercise could be cut from the duets (too few notes?)")


def exercises_from_duets(count=5, purpose="reading", bars=None, level=3,
                         instrument="Bb (trumpet)", part="random", seed=None, key_sig="auto"):
    """Generate > Read & play from duets: a group of `count` exercises, each from a new duet
    (each in its own random key, see exercise_from_duet)."""
    rng = random.Random(seed)
    phrases = [exercise_from_duet(purpose, bars, level, instrument, part,
                                  seed=rng.randrange(1 << 30), key_sig=key_sig)
               for _ in range(int(count))]
    label = {"reading": "Read & play", "repeat": "Listen & repeat"}.get(purpose, purpose)
    return ExerciseSet(phrases, f"{label} random – {len(phrases)} exercises (level {level}, "
                       f"{instrument.split(' (')[0]})", "duets", purpose)


# ---------------------------------------------------------------- source MIDI, remake
def _midi_b64(midi):
    import base64
    import io
    buf = io.BytesIO()
    midi.pm.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _b64_key(b64):
    import hashlib
    return hashlib.sha1(b64.encode("ascii")).hexdigest()[:12]


def source_of(ph):
    """The Midi object an exercise was cut from (None if it does not know it)."""
    if not ph.source_midi:
        return None
    import base64
    import io
    import pretty_midi
    from .midi import Midi
    m = Midi()
    m.pm = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(ph.source_midi)))
    m.title = ((ph.origin or {}).get("midi") or {}).get("title") or ph.source
    return m


def transform_tags():
    """Exact transformations of an exercise (edit panel): none, transpose -5..+6, the
    others, mode <church mode>."""
    tags = ["none"] + [f"transpose {k:+d}" for k in range(-5, 7) if k]
    tags += [t for t in TRANSFORMS if t not in ("none", "transpose", "mode")]
    tags += [f"mode {m}" for m in MODES]
    return tuple(tags)


def settings_of(ph):
    """What can be changed in an exercise (edit panel): first, last, part, level,
    instrument, transform, bpm (practice_bpm) + the ranges (bars, parts)."""
    o = (ph.origin or {}).get("midi") or {}
    inst = o.get("instrument") or next((k for k, v in READ_AS.items()
                                        if v[1] == ph.transposition and ph.read_as), None) \
        or next((k for k, v in PLAYED_ON.items() if v == ph.instrument and k in INSTRUMENTS),
                None) \
        or ("Bb (trumpet)" if ph.transposition == 2 else "C (piano)")
    return dict(first=o.get("first", ph.start_bar), last=o.get("last", ph.start_bar + ph.bars - 1),
                part=o.get("part"), parts=o.get("parts") or [], bars=o.get("bars"),
                level=o.get("level", ph.level), instrument=inst,
                transform=o.get("transform", ph.transform), bpm=ph.practice_bpm,
                transpose=int(o.get("transpose", 0)), can_remake=ph.can_remake())


def remake(ph, first=None, last=None, part=None, level=None, instrument=None, transform=None,
           bpm=None, title=None):
    """A NEW exercise from the same MIDI with other bars / part / difficulty / instrument
    (also a transposition) / transformation / tempo (owner, 2026-11-08: a changed exercise
    is another exercise, without results). Without a source MIDI only the tempo and a
    transposition ('transpose +k' on the notes as they are) can change."""
    cur = settings_of(ph)
    first = cur["first"] if first is None else int(first)
    last = cur["last"] if last is None else int(last)
    part = cur["part"] if part is None else part
    level = cur["level"] if level is None else int(level)
    instrument = instrument or cur["instrument"]
    transform = transform or cur["transform"]
    if bpm is None:
        bpm = ph.practice_bpm
    if ph.can_remake():
        o = ph.origin["midi"]
        st = exercises_from_midi(
            source_of(ph), purpose=ph.purpose, transform=transform,
            parts=None if o.get("polyphony") else [int(part)], title=o.get("title"),
            polyphony=o.get("polyphony", False), level=level, instrument=instrument,
            remove_empty=o.get("remove_empty", True), bar_range=(first, last),
            practice_bpm=bpm, transpose=cur["transpose"])
        if not st.phrases:
            raise ValueError("no exercise in those bars")
        new = st.phrases[0]
        if (ph.origin or {}).get("duet"):
            new.origin["duet"] = dict(ph.origin["duet"])
    else:
        new = ph.copy()
        if transform != cur["transform"] and transform.startswith("transpose "):
            new = new.transpose(int(transform.split()[1]))
        elif transform != cur["transform"]:
            raise ValueError("this exercise does not know its MIDI: only tempo and "
                             "transposition can change")
        new.practice_bpm = bpm
    # a TRANSLATED exercise (library, owner 2026-11-19): cut from the MIDI for its original
    # instrument, then translated again for the same target
    tr = (ph.origin or {}).get("translation")
    if tr and tr.get("target") and new.instrument != ph.instrument:
        from .translate import translate
        new = translate(new, tr["target"], source_id=new.uid)
    new.uid = __import__("uuid").uuid4().hex[:12]
    new.results, new.grades = {}, {}
    if title:
        new.title = title
    elif bpm and bpm != ph.practice_bpm:
        new.title = f"{new.title} – {int(round(bpm))} bpm"
    return new
