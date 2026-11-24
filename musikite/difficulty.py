"""
Difficulty of an exercise, 0-10: a SIMPLE estimate (owner, 2026-11-08) used to organise
the exercises (folders, ordering) from scripts; not in the GUI for now. No Qt.

    score = density + variability + length + key + accidentals + instrument, at most 10
    density     = notes per second × DENSITY_PER_NOTE_S (2.5: 2 notes/s -> 5, 4 notes/s -> 10)
    variability = coefficient of variation of the time between one note and the next
                  (standard deviation / mean) × VARIABILITY_PER_CV (2: 100 % -> 2), at most
                  VARIABILITY_MAX (3); a constant rhythm = 0
    length      = +LONG_POINT (1) if the exercise lasts more than LONG_S (60 s)
    key         = KEY_PER_ACCIDENTAL (0.25) for every sharp / flat of the WRITTEN key
                  signature (Bb trumpet: the transposed key; 4 -> +1, 7 -> +1.75)
    accidentals = fraction of the notes outside the key (alterations not in the key
                  signature) × ACCIDENTALS_PER_FRACTION (4), at most ACCIDENTALS_MAX (2)
                  (owner, 2026-11-08: 25 % altered notes -> +1)
    instrument  = rules of the instrument the exercise is played on (INSTRUMENT_RULES;
                  the exercise knows it: Phrase.instrument). Trumpet: the highest note
                  (written for the Bb trumpet): up to F5 (top line) 0, F#5-G#5 (G above the
                  staff) +0.5, A5 and above +1 (owner, 2026-11-08). Other instruments: none
                  yet (trombone, tuba, sax… will have their own rules).

Notes starting together (a chord) count as one note. The time is that of the exercise at
its tempo: `bpm` given, else the exercise's own (`practice_bpm`), else DEFAULT_BPM.
Examples (owner): 2 notes/s steady -> 5; 2 notes/s with a 100 % spread -> 5 + 2 = 7.

    from musikite.difficulty import difficulty, rank
    difficulty(phrase)            # dict(score, density, variability, length, notes_per_s, cv, seconds)
    difficulty(group)             # dict(score = mean, max, items)
    rank(objects)                 # [(score, object)], easiest first
"""
import math

DENSITY_PER_NOTE_S = 2.5
VARIABILITY_PER_CV = 2.0
VARIABILITY_MAX = 3.0
LONG_S = 60.0
LONG_POINT = 1.0
KEY_PER_ACCIDENTAL = 0.25
ACCIDENTALS_PER_FRACTION = 4.0
ACCIDENTALS_MAX = 2.0


def _trumpet_high(ph):
    """Bb trumpet: the highest WRITTEN note for the Bb trumpet (also when the exercise is
    read as a trumpet in C, D…: it is played on the Bb trumpet)."""
    if not ph.notes:
        return 0.0
    top = max(p for _, _, p in ph.notes) + 2            # concert -> written for Bb trumpet
    return 0.0 if top <= 77 else (0.5 if top < 81 else 1.0)    # F5 / G5 / A5


# instrument -> [(name, function(phrase) -> points)]
INSTRUMENT_RULES = {"trumpet": [("high register", _trumpet_high)]}
DEFAULT_BPM = 90.0
LEVELS = ((3.0, "easy"), (6.0, "medium"), (8.0, "hard"), (10.01, "very hard"))


def phrase_difficulty(ph, bpm=None):
    """Difficulty of a Phrase (Read & play / Listen & repeat, also the phrase of a drill)."""
    bpm = float(bpm or getattr(ph, "practice_bpm", None) or DEFAULT_BPM)
    spq = 60.0 / bpm
    onsets = sorted({round(float(s), 6) for s, _, _ in ph.notes})
    seconds = max(float(ph.length_q), max((s + d for s, d, _ in ph.notes), default=0.0)) * spq
    n = len(onsets)
    if n == 0 or seconds <= 0:
        return dict(score=0.0, density=0.0, variability=0.0, length=0.0, key=0.0,
                    accidentals=0.0, instrument=0.0, instrument_rules={}, notes_per_s=0.0,
                    cv=0.0, key_accidentals=0, out_of_key=0.0, seconds=round(seconds, 1),
                    bpm=bpm)
    rate = n / seconds
    iois = [(b - a) * spq for a, b in zip(onsets, onsets[1:])]
    if len(iois) > 1:
        m = sum(iois) / len(iois)
        cv = math.sqrt(sum((x - m) ** 2 for x in iois) / len(iois)) / m if m > 0 else 0.0
    else:
        cv = 0.0
    density = rate * DENSITY_PER_NOTE_S
    variability = min(VARIABILITY_MAX, cv * VARIABILITY_PER_CV)
    length = LONG_POINT if seconds > LONG_S else 0.0
    n_key, out = key_accidentals(ph), out_of_key(ph)
    key = KEY_PER_ACCIDENTAL * n_key
    accidentals = min(ACCIDENTALS_MAX, out * ACCIDENTALS_PER_FRACTION)
    rules = {name: f(ph) for name, f in
             INSTRUMENT_RULES.get(getattr(ph, "instrument", None), [])}
    inst = sum(rules.values())
    score = min(10.0, density + variability + length + key + accidentals + inst)
    return dict(score=round(score, 1), density=round(density, 2),
                variability=round(variability, 2), length=length, key=round(key, 2),
                accidentals=round(accidentals, 2), instrument=round(inst, 2),
                instrument_rules=rules, notes_per_s=round(rate, 2), cv=round(cv, 2),
                key_accidentals=n_key, out_of_key=round(out, 3), seconds=round(seconds, 1),
                bpm=bpm)


def key_accidentals(ph):
    """Number of sharps / flats of the WRITTEN key signature of a phrase."""
    import pretty_midi
    try:
        kn = (ph.key_number() + int(ph.transposition)) % 12
        return abs(pretty_midi.key_number_to_mode_accidentals(kn)[1])
    except Exception:
        return 0


def out_of_key(ph):
    """Fraction of the notes outside the scale of the phrase's key (alterations)."""
    try:
        scale = ph._scale()
    except Exception:
        return 0.0
    notes = [p for _, _, p in ph.notes]
    if not notes:
        return 0.0
    return sum(1 for p in notes if p % 12 not in scale) / len(notes)


def difficulty(obj, bpm=None):
    """Phrase -> phrase_difficulty; ExerciseSet / Routine -> dict(score = mean, max, items);
    a drill (tasks.Task) -> the difficulty of its phrase; blocks of questions (intervals,
    chords, flash cards…) -> None (not a melody)."""
    from .phrase import Phrase, ExerciseSet
    from .tasks import Task, Routine
    if isinstance(obj, Phrase):
        return phrase_difficulty(obj, bpm)
    if isinstance(obj, Task):
        if not obj.drill:
            return None
        d = obj.drill_obj()
        return phrase_difficulty(d.phrase, bpm or (obj.settings or {}).get("bpm") or d.phrase.bpm)
    if isinstance(obj, (ExerciseSet, Routine)):
        parts = obj.phrases if isinstance(obj, ExerciseSet) else [it["obj"] for it in obj.items]
        items = [difficulty(p, bpm) for p in parts]
        sc = [x["score"] for x in items if x and "score" in x]
        return dict(score=round(sum(sc) / len(sc), 1) if sc else None,
                    max=max(sc) if sc else None, items=items)
    return None


def score_of(obj, bpm=None):
    d = difficulty(obj, bpm)
    return None if d is None else d.get("score")


def level_name(score):
    """'easy' (< 3), 'medium' (< 6), 'hard' (< 8), 'very hard' — e.g. for folder names."""
    if score is None:
        return "not rated"
    for lim, name in LEVELS:
        if score < lim:
            return name
    return LEVELS[-1][1]


def rank(objects, bpm=None):
    """[(score, object)] easiest first; objects without a score (None) at the end."""
    out = [(score_of(o, bpm), o) for o in objects]
    return sorted(out, key=lambda x: (x[0] is None, x[0] if x[0] is not None else 0.0))
