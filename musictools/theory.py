"""
Music theory engine of MusiKitE (pure Python: no music21, no Qt, no native
library, so it runs unchanged on Android). Every part of the app that needs
theory asks it here: duets, exercises (modes, transformations), intervals,
chord progressions, backing tracks, evaluation of improvisation.

    from musictools import theory as th
    th.note_name(70)                  'Bb4'      (styles: brass, sharp, flat, it)
    th.parse_note('G3')               55
    th.interval_name(7)               'Perfect 5th'
    th.spelled_interval(3, 4)         'M3'       (number of steps, semitones)
    th.scale_pitches(2, 'dorian', 60, 72)
    c = th.parse_chord('Dm7')         Chord: root 2, quality 'm7', pcs {2, 5, 9, 0}
    c.name('it')                      'Re minore settima'
    th.parse_progression('Dm7 G7 Cmaj7:A7')   bars of (Chord, beats)
    k = th.Key(0, 'major');  k.roman(c)       'ii7'
    th.RULES.scales_for(c, key=k)     [('dorian', 1.0), ...]  chord -> scale (rules)
    th.RULES.classify(65, c, key=k)   'chord_tone' | 'tension' | 'avoid' | 'scale' | 'chromatic'

DESIGN: MADE TO GROW. The theory is DATA and RULES, not code scattered in the
modules:
  * tables (SCALES, CHORD_TYPES, CHORD_ALIASES, INTERVALS, PROGRESSIONS): to know
    more scales / chords / progressions, add entries; never change the meaning of
    an existing name (saved exercises and duets use them);
  * RULES (RuleBook): chord -> scale choices with weights, decided by Rule objects
    that see the chord and its context (key, previous and next chord). New
    knowledge (from theory books, styles, levels) = new Rule with its `source`;
    higher priority wins, weights order the alternatives. The user's choices
    (settings key 'chord_scales', {quality: scale}) come first;
  * VERSION goes up when a rule changes a result, so results can be compared.
Pitch classes: 0 = C … 11 = B; MIDI numbers: 60 = C4 (middle C).
"""
import re

VERSION = 1

# ======================================================================== pitches
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
BRASS_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
IT_NAMES = ("Do", "Do diesis", "Re", "Mi bemolle", "Mi", "Fa", "Fa diesis", "Sol",
            "La bemolle", "La", "Si bemolle", "Si")
NAME_STYLES = {"sharp": SHARP_NAMES, "flat": FLAT_NAMES, "brass": BRASS_NAMES, "it": IT_NAMES}
LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
IT_PC = {"Do": 0, "Re": 2, "Mi": 4, "Fa": 5, "Sol": 7, "La": 9, "Si": 11}
STEP_LETTERS = "CDEFGAB"
STEP_SEMI = (0, 2, 4, 5, 7, 9, 11)
_ACC = {"": 0, "#": 1, "b": -1, "##": 2, "bb": -2, "x": 2, "♯": 1, "♭": -1,
        " diesis": 1, " bemolle": -1, "diesis": 1, "bemolle": -1}
_NOTE_RE = re.compile(r"^(Do|Re|Mi|Fa|Sol|La|Si|[A-G])"
                      r"(##|bb|#|b|x|♯|♭| ?diesis| ?bemolle)?(-?\d+)?$")


def pc_of(name):
    """Pitch class of a note name: 'C', 'F#', 'Bb', 'Do', 'Sib', 'Fa diesis', 'Si bemolle'."""
    m = _NOTE_RE.match(name.strip())
    if not m or m.group(3) is not None:
        raise ValueError(f"not a note name: '{name}'")
    base = IT_PC.get(m.group(1), LETTER_PC.get(m.group(1)))
    return (base + _ACC[m.group(2) or ""]) % 12


def parse_note(name):
    """MIDI number of a note with octave: 'G3' -> 55, 'Bb4' -> 70, 'Sol3' -> 55 (C4 = 60)."""
    m = _NOTE_RE.match(name.strip())
    if not m or m.group(3) is None:
        raise ValueError(f"not a note with octave: '{name}' (e.g. G3, Bb4)")
    base = IT_PC.get(m.group(1), LETTER_PC.get(m.group(1)))
    return 12 * (int(m.group(3)) + 1) + base + _ACC[m.group(2) or ""]


def note_name(p, style="brass", octave=True):
    """MIDI number -> name: 70 -> 'Bb4' (brass: Bb Eb Ab C# F#), 'A#4' (sharp),
    'Si bemolle 4' (it). octave=False: pitch class only."""
    names = NAME_STYLES[style]
    n = names[int(p) % 12]
    if not octave:
        return n
    return f"{n} {int(p) // 12 - 1}" if style == "it" else f"{n}{int(p) // 12 - 1}"


# ======================================================================== intervals
# semitones -> (short, long name); the tritone is A4 or d5 depending on the spelling
INTERVALS = {
    0: ("P1", "Unison"), 1: ("m2", "Minor 2nd"), 2: ("M2", "Major 2nd"), 3: ("m3", "Minor 3rd"),
    4: ("M3", "Major 3rd"), 5: ("P4", "Perfect 4th"), 6: ("TT", "Tritone"),
    7: ("P5", "Perfect 5th"), 8: ("m6", "Minor 6th"), 9: ("M6", "Major 6th"),
    10: ("m7", "Minor 7th"), 11: ("M7", "Major 7th"), 12: ("P8", "Octave"),
}
PERFECT_NUMBERS = {1: 0, 4: 5, 5: 7, 8: 12}     # number -> semitones of the perfect interval
MAJOR_NUMBERS = {2: 2, 3: 4, 6: 9, 7: 11}       # number -> semitones of the major interval
NUMBER_NAMES = {1: "Unison", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th",
                8: "Octave"}
QUALITY_NAMES = {"m": "Minor", "M": "Major", "P": "Perfect", "A": "Augmented", "d": "Diminished"}


def interval_name(semitones, short=False):
    """12 -> 'Octave'; short=True -> 'P8'. Compound intervals: reduced to the octave."""
    s = int(semitones)
    if s > 12:
        s = s % 12 or 12
    return INTERVALS[s][0 if short else 1]


def spelled_interval(number, semitones):
    """Interval of two SPELLED notes: number = diatonic steps + 1 (3 = a third),
    semitones -> 'M3', 'A4', 'd5', … or None if not a usual quality."""
    n = int(number)
    if n in PERFECT_NUMBERS:
        q = {0: "P", 1: "A", -1: "d"}.get(semitones - PERFECT_NUMBERS[n])
    elif n in MAJOR_NUMBERS:
        q = {0: "M", -1: "m", 1: "A", -2: "d"}.get(semitones - MAJOR_NUMBERS[n])
    else:
        return None
    return f"{q}{n}" if q else None


def interval_label(key):
    """'M3' -> 'Major 3rd', '5' -> '5th', 'P8' -> 'Perfect Octave'."""
    if key.isdigit():
        return NUMBER_NAMES[int(key)]
    return f"{QUALITY_NAMES[key[0]]} {NUMBER_NAMES[int(key[1:])]}"


# ======================================================================== scales
# name -> intervals from the tonic. Church modes in the order of the degrees of the
# major scale (MODES). Add new scales at the end; never change an existing one.
SCALES = {
    "ionian": (0, 2, 4, 5, 7, 9, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "aeolian": (0, 2, 3, 5, 7, 8, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
    "harmonic_minor": (0, 2, 3, 5, 7, 8, 11),
    "melodic_minor": (0, 2, 3, 5, 7, 9, 11),           # ascending (jazz minor)
    "phrygian_dominant": (0, 1, 4, 5, 7, 8, 10),       # 5th mode of harmonic minor
    "lydian_dominant": (0, 2, 4, 6, 7, 9, 10),         # 4th mode of melodic minor
    "locrian_nat2": (0, 2, 3, 5, 6, 8, 10),            # 6th mode of melodic minor
    "altered": (0, 1, 3, 4, 6, 8, 10),                 # 7th mode of melodic minor
    "lydian_augmented": (0, 2, 4, 6, 8, 9, 11),        # 3rd mode of melodic minor
    "whole_tone": (0, 2, 4, 6, 8, 10),
    "diminished_hw": (0, 1, 3, 4, 6, 7, 9, 10),        # half-whole (dominant 7b9)
    "diminished_wh": (0, 2, 3, 5, 6, 8, 9, 11),        # whole-half (dim7)
    "major_pentatonic": (0, 2, 4, 7, 9),
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "blues": (0, 3, 5, 6, 7, 10),
    "major_blues": (0, 2, 3, 4, 7, 9),
    "bebop_dominant": (0, 2, 4, 5, 7, 9, 10, 11),
    "bebop_major": (0, 2, 4, 5, 7, 8, 9, 11),
    "chromatic": tuple(range(12)),
}
SCALE_ALIASES = {"major": "ionian", "minor": "aeolian", "natural_minor": "aeolian",
                 "jazz_minor": "melodic_minor", "super_locrian": "altered",
                 "half_whole": "diminished_hw", "whole_half": "diminished_wh"}
MODES = ("ionian", "dorian", "phrygian", "lydian", "mixolydian", "aeolian", "locrian")


def scale(name):
    """Intervals of a scale (names and aliases of SCALES)."""
    n = SCALE_ALIASES.get(name, name)
    if n not in SCALES:
        raise ValueError(f"unknown scale '{name}'; known: {', '.join(SCALES)}")
    return SCALES[n]


def scale_pcs(tonic, name):
    """Pitch classes of a scale on a tonic (pitch class or note name)."""
    t = pc_of(tonic) if isinstance(tonic, str) else int(tonic) % 12
    return frozenset((t + i) % 12 for i in scale(name))


def scale_pitches(tonic, name, lo, hi):
    """MIDI numbers of the scale between lo and hi (included)."""
    pcs = scale_pcs(tonic, name)
    return [p for p in range(int(lo), int(hi) + 1) if p % 12 in pcs]


def mode_degree(mode):
    """Degree (0-6) of the major scale a church mode starts on (dorian = 1)."""
    return MODES.index(SCALE_ALIASES.get(mode, mode))


# ======================================================================== chords
# canonical quality -> intervals from the root (extensions above the octave allowed).
# Add new qualities at the end; aliases in CHORD_ALIASES.
CHORD_TYPES = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "m7": (0, 3, 7, 10),
    "maj7": (0, 4, 7, 11),
    "6": (0, 4, 7, 9),
    "m6": (0, 3, 7, 9),
    "dim": (0, 3, 6),
    "dim7": (0, 3, 6, 9),
    "m7b5": (0, 3, 6, 10),
    "aug": (0, 4, 8),
    "sus4": (0, 5, 7),
    "sus2": (0, 2, 7),
    "7sus4": (0, 5, 7, 10),
    "aug7": (0, 4, 8, 10),
    "m(maj7)": (0, 3, 7, 11),
    "maj7#5": (0, 4, 8, 11),
    "maj7#11": (0, 4, 7, 11, 18),
    "add9": (0, 4, 7, 14),
    "madd9": (0, 3, 7, 14),
    "6/9": (0, 4, 7, 9, 14),
    "9": (0, 4, 7, 10, 14),
    "m9": (0, 3, 7, 10, 14),
    "maj9": (0, 4, 7, 11, 14),
    "7b9": (0, 4, 7, 10, 13),
    "7#9": (0, 4, 7, 10, 15),
    "7#11": (0, 4, 7, 10, 18),
    "7b13": (0, 4, 7, 10, 20),
    "7alt": (0, 4, 10, 13, 15, 18, 20),
    "11": (0, 4, 7, 10, 14, 17),
    "m11": (0, 3, 7, 10, 14, 17),
    "13": (0, 4, 7, 10, 14, 21),
    "m13": (0, 3, 7, 10, 14, 21),
    "5": (0, 7),
}
CHORD_ALIASES = {
    "maj": "", "M": "", "major": "",
    "min": "m", "-": "m", "minor": "m",
    "dom7": "7",
    "-7": "m7", "min7": "m7",
    "M7": "maj7", "Maj7": "maj7", "ma7": "maj7", "Δ": "maj7", "Δ7": "maj7",
    "7+": "maj7", "7m": "maj7",          # Italian usage (MATLAB chord.m, get_chord_name_it)
    "min6": "m6", "-6": "m6",
    "o": "dim", "°": "dim",
    "o7": "dim7", "°7": "dim7",
    "ø": "m7b5", "ø7": "m7b5", "-7b5": "m7b5", "min7b5": "m7b5",
    "+": "aug", "#5": "aug",
    "sus": "sus4",
    "7sus": "7sus4",
    "+7": "aug7", "7#5": "aug7",
    "mM7": "m(maj7)", "m(M7)": "m(maj7)", "-maj7": "m(maj7)", "mmaj7": "m(maj7)",
    "69": "6/9", "6add9": "6/9",
    "-9": "m9", "min9": "m9", "M9": "maj9", "Δ9": "maj9",
    "alt": "7alt",
    "-11": "m11", "-13": "m13",
}
# words for the spoken / written Italian name (MATLAB get_chord_name_it)
QUALITY_IT = {
    "": "", "m": "minore", "7": "settima", "m7": "minore settima", "maj7": "settima maggiore",
    "6": "sesta", "m6": "minore sesta", "dim": "diminuito", "dim7": "diminuito settima",
    "m7b5": "semidiminuito", "aug": "aumentato", "sus4": "sospeso quarta",
    "sus2": "sospeso seconda", "7sus4": "settima sospeso quarta", "aug7": "settima aumentato",
    "m(maj7)": "minore settima maggiore", "9": "nona", "m9": "minore nona",
    "maj9": "nona maggiore", "7b9": "settima nona bemolle", "7#9": "settima nona diesis",
    "13": "tredicesima", "7alt": "settima alterato", "6/9": "sesta nona",
}
DEGREE_NAMES = {0: "1", 1: "b9", 2: "9", 3: "b3", 4: "3", 5: "11", 6: "#11", 7: "5",
                8: "b13", 9: "13", 10: "b7", 11: "7"}
_ROOT_RE = re.compile(r"^(Do|Re|Mi|Fa|Sol|La|Si|[A-G])(#|b| diesis| bemolle)?(.*)$")


def chord_quality(q):
    """Canonical quality of a chord suffix ('-7' -> 'm7'); ValueError if unknown."""
    q = q.strip()
    if q in CHORD_TYPES:
        return q
    if q in CHORD_ALIASES:
        return CHORD_ALIASES[q]
    raise ValueError(f"unknown chord quality '{q}'; known: "
                     + ", ".join(repr(k) for k in CHORD_TYPES) + " (and the aliases of CHORD_ALIASES)")


class Chord:
    """A chord: root pitch class, canonical quality, optional bass (slash chord)."""

    def __init__(self, root, quality="", bass=None, symbol=None):
        self.root = int(root) % 12
        self.quality = chord_quality(quality)
        self.bass = None if bass is None else int(bass) % 12
        self.symbol = symbol or self.name()

    def __repr__(self):
        return f"Chord('{self.name()}')"

    def __eq__(self, other):
        return isinstance(other, Chord) and (self.root, self.quality, self.bass) == \
            (other.root, other.quality, other.bass)

    def __hash__(self):
        return hash((self.root, self.quality, self.bass))

    @property
    def intervals(self):
        return CHORD_TYPES[self.quality]

    @property
    def pcs(self):
        """Pitch classes of the chord (the bass of a slash chord included)."""
        s = {(self.root + i) % 12 for i in self.intervals}
        if self.bass is not None:
            s.add(self.bass)
        return frozenset(s)

    @property
    def third(self):
        """3 (minor), 4 (major) or None (sus, power chord)."""
        iv = {i % 12 for i in self.intervals}
        return 4 if 4 in iv else 3 if 3 in iv else None

    @property
    def seventh(self):
        """10 (minor 7th), 11 (major 7th), 9 (dim7) or None."""
        iv = {i % 12 for i in self.intervals if i < 12}
        if self.quality in ("dim7",):
            return 9
        return 10 if 10 in iv else 11 if 11 in iv else None

    @property
    def is_minor(self):
        return self.third == 3

    @property
    def is_dominant(self):
        """Major third and minor seventh (or sus with minor 7th)."""
        return self.seventh == 10 and self.third in (4, None)

    def degree(self, pc):
        """Name of a pitch class relative to the root: '1', 'b3', '3', '5', 'b7', '9'…"""
        return DEGREE_NAMES[(int(pc) - self.root) % 12]

    def tones(self, lo, hi):
        """MIDI numbers of the chord tones between lo and hi."""
        return [p for p in range(int(lo), int(hi) + 1) if p % 12 in self.pcs]

    def voicing(self, lo=48, inversion=0):
        """Close position from the first root (or chosen inversion) at or above lo."""
        base = lo + (self.root - lo) % 12
        notes = sorted({base + i for i in self.intervals})
        for _ in range(int(inversion) % len(notes)):
            notes = notes[1:] + [notes[0] + 12]
        if self.bass is not None:
            b = notes[0] - ((notes[0] - self.bass) % 12 or 12)
            notes = [b] + notes
        return notes

    def transpose(self, k):
        return Chord(self.root + k, self.quality,
                     None if self.bass is None else self.bass + k)

    def name(self, style="brass"):
        """'Dm7', or in Italian 'Re minore settima' (style 'it')."""
        if style == "it":
            q = QUALITY_IT.get(self.quality, self.quality)
            s = IT_NAMES[self.root] + (f" {q}" if q else "")
            return s + (f" con basso {IT_NAMES[self.bass]}" if self.bass is not None else "")
        r = NAME_STYLES[style][self.root]
        return r + self.quality + (f"/{NAME_STYLES[style][self.bass]}" if self.bass is not None else "")


def parse_chord(symbol):
    """Chord from a symbol: 'C', 'Cm7', 'F#7b9', 'Bbmaj7', 'Dm7b5', 'C/E', 'C6/9',
    Italian roots 'Do', 'Solm7', 'Sib7' (aliases: CHORD_ALIASES)."""
    sym = symbol.strip()
    m = _ROOT_RE.match(sym)
    if not m:
        raise ValueError(f"cannot parse chord '{symbol}'")
    name, acc, rest = m.groups()
    root = (IT_PC.get(name, LETTER_PC.get(name)) + _ACC[acc or ""]) % 12
    bass = None
    try:
        q = chord_quality(rest)
    except ValueError:
        if "/" not in rest:
            raise ValueError(f"cannot parse chord '{symbol}': " + str(_quality_error(rest))) from None
        q_txt, b_txt = rest.rsplit("/", 1)
        try:
            q, bass = chord_quality(q_txt), pc_of(b_txt)
        except ValueError:
            raise ValueError(f"cannot parse chord '{symbol}'") from None
    return Chord(root, q, bass, symbol=sym)


def _quality_error(q):
    try:
        chord_quality(q)
    except ValueError as e:
        return e
    return None


# ======================================================================== progressions
def parse_progression(text, beats_per_bar=4, transpose=0):
    """Bars of a progression: 'C F G7 C' (one chord per bar), 'F:G' (two chords in a
    bar), 'C:Am:F:G' (four); separators: spaces, commas, '|'. Returns a list of bars,
    each a list of (Chord, beats)."""
    bars = []
    for tok in re.split(r"[\s,|]+", text.strip()):
        if not tok:
            continue
        parts = tok.split(":")
        if len(parts) not in (1, 2, 4):
            raise ValueError(f"'{tok}': a bar can hold 1, 2 or 4 chords")
        bars.append([(parse_chord(p).transpose(transpose) if transpose else parse_chord(p),
                      beats_per_bar / len(parts)) for p in parts])
    if not bars:
        raise ValueError("empty chord progression")
    return bars


def timeline(bars, beats_per_bar=4):
    """[(start_beat, beats, Chord)] of a parsed progression."""
    out = []
    for b, bar in enumerate(bars):
        t = b * beats_per_bar
        for c, beats in bar:
            out.append((t, beats, c))
            t += beats
    return out


# common progressions (in C, one token per bar); add new ones at the end
# The progressions live in progressions.py (owner, 2026-11-08: Roman numerals, any key, a
# catalogue that grows); the old table (C, chord names) stays the same under this name.
from .progressions import LEGACY as PROGRESSIONS  # noqa: E402


# ======================================================================== keys
class Key:
    """A key: tonic pitch class and mode ('major', 'minor' or a church mode)."""

    def __init__(self, tonic, mode="major"):
        self.tonic = pc_of(tonic) if isinstance(tonic, str) else int(tonic) % 12
        self.mode = SCALE_ALIASES.get(mode, mode)
        self.pcs = scale_pcs(self.tonic, self.mode)

    def __repr__(self):
        return f"Key({BRASS_NAMES[self.tonic]} {self.mode})"

    @property
    def is_minor(self):
        return self.mode in ("aeolian", "dorian", "phrygian", "harmonic_minor", "melodic_minor")

    def degree_of(self, pc):
        """Scale degree 0-6 of a pitch class, or None if not in the key."""
        iv = scale(self.mode)
        d = (int(pc) - self.tonic) % 12
        return iv.index(d) if d in iv else None

    def diatonic_chords(self, sevenths=True):
        """The chord on every degree, built by thirds inside the scale."""
        iv = scale(self.mode)
        n = len(iv)
        out = []
        for d in range(n):
            notes = [iv[(d + 2 * k) % n] + 12 * ((d + 2 * k) // n) for k in range(4 if sevenths else 3)]
            rel = tuple(x - notes[0] for x in notes)
            q = next((k for k, v in CHORD_TYPES.items() if tuple(v) == rel), None)
            out.append(Chord(self.tonic + iv[d], q if q is not None else ""))
        return out

    def roman(self, chord):
        """Roman numeral of a chord in the key ('ii7', 'V7', 'bVII', …)."""
        romans = ("I", "II", "III", "IV", "V", "VI", "VII")
        major_iv = SCALES["ionian"]
        d = (chord.root - self.tonic) % 12
        if d in major_iv:
            num, acc = romans[major_iv.index(d)], ""
        else:
            num, acc = romans[major_iv.index((d + 1) % 12)], "b"
        num = num.lower() if chord.is_minor or chord.quality in ("dim", "dim7", "m7b5") else num
        suffix = {"m": "", "": "", "maj7": "maj7", "m7": "7", "7": "7", "m7b5": "ø7",
                  "dim": "°", "dim7": "°7", "6": "6", "m6": "6"}.get(chord.quality, chord.quality)
        return acc + num + suffix


# ======================================================================== rules
class Rule:
    """One piece of knowledge: for a chord in its context, the scales to use.

    qualities : canonical qualities it applies to (None = any)
    when      : optional test f(chord, ctx) -> bool; ctx = dict(key, prev, next)
    scales    : [(scale name, weight)], weight 0..1 (1 = first choice)
    priority  : higher wins when several rules apply (equal: alternatives merged)
    source    : where it comes from (book, teacher, style), for the record."""

    def __init__(self, name, qualities, scales, when=None, priority=0, source=""):
        self.name = name
        self.qualities = None if qualities is None else frozenset(qualities)
        self.scales = [(SCALE_ALIASES.get(s, s), float(w)) for s, w in scales]
        for s, _ in self.scales:
            scale(s)                                   # unknown scale: error at once
        self.when = when
        self.priority = priority
        self.source = source

    def applies(self, chord, ctx):
        if self.qualities is not None and chord.quality not in self.qualities:
            return False
        return True if self.when is None else bool(self.when(chord, ctx))

    def __repr__(self):
        return f"Rule({self.name}, priority {self.priority})"


def _resolves_down_fifth(chord, ctx):
    n = ctx.get("next")
    return n is not None and (n.root - chord.root) % 12 == 5


def _to_minor(chord, ctx):
    n = ctx.get("next")
    return _resolves_down_fifth(chord, ctx) and n.is_minor


def _diatonic_degree(deg):
    def test(chord, ctx):
        k = ctx.get("key")
        return k is not None and not k.is_minor and k.degree_of(chord.root) == deg \
            and chord.pcs <= k.pcs | {chord.root}
    return test


CHORD_SCALE_SOURCE = "chord-scale theory (M. Levine, The Jazz Theory Book, 1995, ch. 3-5)"
DEFAULT_RULES = [
    # --- defaults per quality (priority 0)
    Rule("major triad", ["", "6", "add9", "6/9", "5"], [("ionian", 1), ("major_pentatonic", .8),
                                                       ("lydian", .5)], source=CHORD_SCALE_SOURCE),
    Rule("maj7", ["maj7", "maj9"], [("ionian", 1), ("lydian", .8)], source=CHORD_SCALE_SOURCE),
    Rule("maj7#11", ["maj7#11"], [("lydian", 1)], source=CHORD_SCALE_SOURCE),
    Rule("maj7#5", ["maj7#5"], [("lydian_augmented", 1)], source=CHORD_SCALE_SOURCE),
    Rule("minor", ["m", "m7", "m9", "m11", "m13", "madd9"],
         [("dorian", 1), ("aeolian", .7), ("minor_pentatonic", .7)], source=CHORD_SCALE_SOURCE),
    Rule("minor 6 / minor-major", ["m6", "m(maj7)"], [("melodic_minor", 1), ("dorian", .6)],
         source=CHORD_SCALE_SOURCE),
    Rule("dominant", ["7", "9", "13", "11"], [("mixolydian", 1), ("bebop_dominant", .7),
                                             ("blues", .5)], source=CHORD_SCALE_SOURCE),
    Rule("7sus4", ["7sus4", "sus4", "sus2"], [("mixolydian", 1)], source=CHORD_SCALE_SOURCE),
    Rule("7b9", ["7b9"], [("diminished_hw", 1), ("phrygian_dominant", .8)], source=CHORD_SCALE_SOURCE),
    Rule("7#9 / alt", ["7#9", "7alt"], [("altered", 1), ("diminished_hw", .6)],
         source=CHORD_SCALE_SOURCE),
    Rule("7#11", ["7#11"], [("lydian_dominant", 1)], source=CHORD_SCALE_SOURCE),
    Rule("7b13", ["7b13"], [("altered", .8), ("phrygian_dominant", 1)], source=CHORD_SCALE_SOURCE),
    Rule("aug", ["aug", "aug7"], [("whole_tone", 1)], source=CHORD_SCALE_SOURCE),
    Rule("half-diminished", ["m7b5"], [("locrian", 1), ("locrian_nat2", .8)],
         source=CHORD_SCALE_SOURCE),
    Rule("dim", ["dim", "dim7"], [("diminished_wh", 1)], source=CHORD_SCALE_SOURCE),
    # --- context (priority 10): function in the key, resolution
    Rule("V7 to minor", ["7", "7b9"], [("phrygian_dominant", 1), ("altered", .7),
                                      ("diminished_hw", .6)], when=_to_minor, priority=10,
         source=CHORD_SCALE_SOURCE),
    Rule("iii in major", ["m", "m7"], [("phrygian", 1), ("aeolian", .5)],
         when=_diatonic_degree(2), priority=10, source=CHORD_SCALE_SOURCE),
    Rule("vi in major", ["m", "m7"], [("aeolian", 1), ("dorian", .6)],
         when=_diatonic_degree(5), priority=10, source=CHORD_SCALE_SOURCE),
    Rule("IV in major", ["", "maj7"], [("lydian", 1), ("ionian", .6)],
         when=_diatonic_degree(3), priority=10, source=CHORD_SCALE_SOURCE),
]


class RuleBook:
    """The rules of the engine (see the module doc). One shared instance: RULES."""

    def __init__(self, rules=()):
        self.rules = list(rules)

    def add(self, rule):
        """New knowledge: a Rule (replaces a rule with the same name)."""
        self.rules = [r for r in self.rules if r.name != rule.name] + [rule]
        return rule

    def remove(self, name):
        self.rules = [r for r in self.rules if r.name != name]

    def overrides(self):
        """The user's choices {quality: scale} (settings key 'chord_scales'), if any."""
        try:
            from .progress import settings
            d = settings().get("chord_scales", {})
            return {chord_quality(q): SCALE_ALIASES.get(s, s) for q, s in d.items() if s in SCALES
                    or s in SCALE_ALIASES}
        except Exception:
            return {}

    def scales_for(self, chord, key=None, prev=None, next=None, explain=False):
        """[(scale, weight)] best first for a chord in its context. explain=True:
        [(scale, weight, rule name, source)]."""
        if isinstance(chord, str):
            chord = parse_chord(chord)
        ctx = dict(key=key, prev=prev, next=next)
        user = self.overrides().get(chord.quality)
        if user:
            return [(user, 1.0, "user setting", "settings 'chord_scales'")] if explain \
                else [(user, 1.0)]
        hits = [r for r in self.rules if r.applies(chord, ctx)]
        if not hits:
            out = [("chromatic", 0.1, "no rule", "")]
        else:
            top = max(r.priority for r in hits)
            best = {}
            for r in hits:
                if r.priority != top:
                    continue
                for s, w in r.scales:
                    if s not in best or w > best[s][0]:
                        best[s] = (w, r.name, r.source)
            out = sorted(((s, w, n, src) for s, (w, n, src) in best.items()), key=lambda x: -x[1])
        return out if explain else [(s, w) for s, w, _, _ in out]

    def scale_for(self, chord, **ctx):
        """Pitch classes of the first-choice scale of a chord (on its root)."""
        if isinstance(chord, str):
            chord = parse_chord(chord)
        return scale_pcs(chord.root, self.scales_for(chord, **ctx)[0][0])

    def classify(self, pitch, chord, **ctx):
        """Role of a note over a chord: 'chord_tone', 'tension' (scale tone that is
        not an avoid note), 'avoid' (scale tone a half step above a chord tone of
        the basic chord), 'scale' (in the scale of another choice), 'chromatic'."""
        if isinstance(chord, str):
            chord = parse_chord(chord)
        pc = int(pitch) % 12
        if pc in chord.pcs:
            return "chord_tone"
        choices = self.scales_for(chord, **ctx)
        first = scale_pcs(chord.root, choices[0][0])
        if pc in first:
            basic = {(chord.root + i) % 12 for i in chord.intervals if i < 12}
            return "avoid" if (pc - 1) % 12 in basic else "tension"
        if any(pc in scale_pcs(chord.root, s) for s, _ in choices[1:]):
            return "scale"
        return "chromatic"


RULES = RuleBook(DEFAULT_RULES)


# ---------------------------------------------------------------- instruments
# FINGERINGS now live in fingerings.py (owner, 2026-11-09: valves, slide positions, one row
# per instrument); these names stay as aliases (Bb trumpet, WRITTEN pitch -> valves).
from .fingerings import VALVE_TABLE as TRUMPET_FINGERING, VALVE_COMBINATIONS  # noqa: E402


# ---------------------------------------------------------------- key estimation
# Port of the owner's MATLAB mysmartmusic/tonalita.m and mysmartmusic_obj/key_signature.m
# (2026-11-08: used instead of music21's analyze('key'), which does not exist on Android).
# Major key by tonic pitch class (C = 0 … B = 11) -> number of accidentals (tonalita.m F) and
# their kind (+1 sharps, -1 flats; key_signature.m altr): F# major = 6 sharps.
KEY_ACCIDENTALS = (0, 5, 2, 3, 4, 1, 6, 1, 4, 3, 2, 5)
KEY_SIGN = (1, -1, 1, -1, 1, -1, 1, 1, -1, 1, -1, 1)
MAJOR_SCALE_PCS = (0, 2, 4, 5, 7, 9, 11)


def estimate_major_key(pitches):
    """tonalita.m: the major key whose scale contains most of the notes (every note counted
    once, no duration weight); a tie goes to the key signature with fewer accidentals
    (0.1 per accidental). Returns the tonic pitch class (0 = C)."""
    pcs = [int(p) % 12 for p in pitches]
    best, best_s = 0, None
    for t in range(12):
        scale = {(t + i) % 12 for i in MAJOR_SCALE_PCS}
        s = sum(1 for pc in pcs if pc in scale) - 0.1 * KEY_ACCIDENTALS[t]
        if best_s is None or s > best_s:
            best, best_s = t, s
    return best


def estimate_key(pitches, first=(), last=()):
    """Key of a melody: (tonic pitch class, 'ionian' | 'aeolian').
    The major key of tonalita.m; MINOR (the relative minor, same key signature) if the
    music starts OR ends on the tonic of the relative minor (owner's simple rule,
    2026-11-08). pitches: all the notes (MIDI numbers, in any order); first / last: the
    pitches sounding at the first / last onset (a chord: all its notes)."""
    if not len(pitches):
        return 0, "ionian"
    major = estimate_major_key(pitches)
    rel = (major + 9) % 12
    if any(int(p) % 12 == rel for p in list(first) + list(last)):
        return rel, "aeolian"
    return major, "ionian"


def key_signature(tonic, mode="ionian"):
    """Signed number of accidentals of a key (+ sharps, - flats; key_signature.m): the
    minor modes use their relative major (aeolian / dorian… are measured from the major
    scale they belong to)."""
    from_major = {"ionian": 0, "dorian": 2, "phrygian": 4, "lydian": 5, "mixolydian": 7,
                  "aeolian": 9, "locrian": 11, "major": 0, "minor": 9}
    major = (int(tonic) - from_major.get(mode, 0)) % 12
    return KEY_SIGN[major] * KEY_ACCIDENTALS[major]


def key_of_notes(notes):
    """estimate_key from notes [start, dur, pitch] (first / last onset found here)."""
    if not notes:
        return 0, "ionian"
    starts = [float(n[0]) for n in notes]
    s0, s1 = min(starts), max(starts)
    first = [n[2] for n in notes if abs(float(n[0]) - s0) < 1e-6]
    last = [n[2] for n in notes if abs(float(n[0]) - s1) < 1e-6]
    return estimate_key([n[2] for n in notes], first, last)


# ---------------------------------------------------------------- instruments: how they are WRITTEN
# (owner, 2026-11-08, Play over MIDI: "in view of using the program for other instruments")
# General MIDI program -> (written name, transposition = written - concert in semitones,
# clef 'treble' / 'bass' / 'alto' / None = chosen from the notes). Ranges of programs share a
# row. Pure data: Android-ready, no music21.
_WRITTEN_RANGES = [
    (range(0, 8), ("Piano", 0, None)),
    (range(8, 16), ("Chromatic percussion", 0, None)),
    (range(16, 24), ("Organ", 0, None)),
    (range(24, 32), ("Guitar", 12, "treble")),           # sounds an octave lower
    (range(32, 40), ("Bass", 12, "bass")),               # sounds an octave lower
    (range(44, 56), ("Strings", 0, None)),
    (range(61, 64), ("Brass", 0, None)),
    (range(75, 80), ("Flute", 0, "treble")),
    (range(80, 128), ("Synth", 0, None)),
]
WRITTEN_FOR_GM = {
    40: ("Violin", 0, "treble"), 41: ("Viola", 0, "alto"), 42: ("Cello", 0, "bass"),
    43: ("Contrabass", 12, "bass"),
    56: ("Trumpet in Bb", 2, "treble"), 57: ("Trombone", 0, "bass"), 58: ("Tuba", 0, "bass"),
    59: ("Trumpet in Bb", 2, "treble"), 60: ("Horn in F", 7, "treble"),
    64: ("Soprano Saxophone in Bb", 2, "treble"), 65: ("Alto Saxophone in Eb", 9, "treble"),
    66: ("Tenor Saxophone in Bb", 14, "treble"), 67: ("Baritone Saxophone in Eb", 21, "treble"),
    68: ("Oboe", 0, "treble"), 69: ("English Horn in F", 7, "treble"), 70: ("Bassoon", 0, "bass"),
    71: ("Clarinet in Bb", 2, "treble"), 72: ("Piccolo", -12, "treble"),
    73: ("Flute", 0, "treble"), 74: ("Recorder", 0, "treble"),
}


# track NAME -> General MIDI program, when the name says the instrument (a "Tromba" track
# saved with a piano program is still a trumpet): first match wins, Italian names too
NAME_PROGRAMS = (
    (("english horn", "corno inglese"), 69), (("trombone",), 57),
    (("trumpet", "tromba", "flugelhorn", "flicorno", "cornet", "cornetta"), 56),
    (("tuba",), 58), (("horn", "corno"), 60),
    (("soprano sax",), 64), (("alto sax", "sax alto", "sax contralto"), 65),
    (("tenor sax", "sax tenore"), 66), (("baritone sax", "sax baritono"), 67),
    (("clarinet", "clarinetto"), 71), (("piccolo", "ottavino"), 72), (("flute", "flauto"), 73),
)


def program_of_name(name):
    """General MIDI program named by a track name (None: the name says nothing)."""
    n = (name or "").lower()
    for words, prog in NAME_PROGRAMS:
        if any(w in n for w in words):
            return prog
    return None


def written_part(program, is_drum=False, name=None):
    """How a General MIDI instrument is written: dict(name, transposition, clef); a track
    name that says the instrument ("Tromba 1", "Alto Sax") wins over the program."""
    if is_drum:
        return dict(name="Drums", transposition=0, clef=None)
    by_name = program_of_name(name)
    p = int(program if by_name is None else by_name)
    row = WRITTEN_FOR_GM.get(p)
    if row is None:
        row = next((r for rng, r in _WRITTEN_RANGES if p in rng), ("Instrument", 0, None))
    return dict(name=row[0], transposition=row[1], clef=row[2])
