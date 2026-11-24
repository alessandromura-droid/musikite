"""
TRANSLATION OF AN EXERCISE TO ANOTHER INSTRUMENT (owner, 2026-11-19). Pure Python, no Qt,
no music21 (Android).

An exercise is written for one instrument (Phrase.instrument, e.g. the library's trumpet
exercises) and TRANSLATED, deterministically, for the instrument chosen beside the user.
Owner's rules: nothing is ever rejected — a note too high goes an octave down (too low: up),
notes too fast for the instrument are QUANTIZED to longer values at the same tempo (a band
instrument keeps the band's tempo; its part simply has no short notes).

The rules are one PROFILE per target instrument (instruments.CATALOGUE: transposition,
written range, clef, program, part, min_note_s), not one rule per pair of instruments, and
the same chain of steps for all:

1. concert pitch (Phrase notes are already concert);
2. the WHOLE exercise moved by octaves into the target's range (`phrase.octave_fit`: the
   shift with the fewest notes outside, a tie the smallest shift);
3. the notes still outside folded ONE BY ONE by octaves into the range, each to the octave
   nearest to the previous note (no seventh / ninth where there was a step);
4. one voice for the wind instruments (a chord keeps its highest note);
5. SHORTEST NOTE: every note must last at least `min_note_s(target, concert pitch)` seconds
   at the exercise's tempo — the detection of low notes needs time (about 10 periods of the
   fundamental: E1 0.24 s, E2 0.12 s, C3 0.08 s) and some instruments are slow by nature
   (sousaphone: catalogue `min_note_s`); if a note is shorter, the exercise is simplified
   (`phrase.simplify`) with the finest grid that is long enough (sixteenths, eighths,
   quarters, halves);
6. written for the target: transposition, program, part name, instrument played (its clef
   comes from phrase.CLEFS).

TWINS (`twins`: same transposition, clef, family and default range — trumpet, cornet,
flugelhorn) and the exercise's own instrument: the notes are NOT touched (steps 2-5
skipped; e.g. a library exercise up to C6 stays so for the trumpet even if the user's range
stops at F5), only the instrument and the identity change.

IDENTITY: a translated exercise has its own uid = hash(source id, target, VERSION), so the
results of the trumpet and of the euphonium never mix; raise VERSION when a rule changes a
result (a new version = new exercises, the old results stay with the old ones).

    from musikite.translate import translate
    ph2 = translate(ph, "C (euphonium)")
"""
import copy
import hashlib

VERSION = 1
DETECT_PERIODS = 10.0          # periods of the fundamental needed to recognise a note


def _profile(target):
    from .instruments import CATALOGUE
    if target not in CATALOGUE:
        raise ValueError(f"unknown instrument {target}")
    return CATALOGUE[target]


def min_note_s(target, concert):
    """Shortest note (seconds) an instrument keeps at a concert pitch: detection
    (DETECT_PERIODS periods of the fundamental) or the instrument's own limit."""
    f = 440.0 * 2.0 ** ((int(concert) - 69) / 12.0)
    return max(DETECT_PERIODS / f, float(_profile(target).get("min_note_s") or 0.0))


def translated_uid(source_id, target):
    return hashlib.sha1(f"{source_id}|{target}|{VERSION}".encode()).hexdigest()[:12]


def _fold(notes, transposition, lo, hi):
    """Notes outside the WRITTEN range [lo, hi] moved by octaves into it, each to the
    octave nearest to the previous note (the first: nearest to itself)."""
    out, prev = [], None
    for s, d, p in sorted(notes):
        w = p + transposition
        if lo <= w <= hi:
            out.append([s, d, p])
            prev = w
            continue
        cands = [w + 12 * k for k in range(-8, 9) if lo <= w + 12 * k <= hi]
        if not cands:                                   # range under an octave: nearest edge
            cands = [min(max(w, lo), hi)]
        ref = prev if prev is not None else w
        w2 = min(cands, key=lambda c: (abs(c - ref), abs(c - w)))
        out.append([s, d, w2 - transposition])
        prev = w2
    return out


def _one_voice(notes):
    top = {}
    for s, d, p in notes:
        k = round(s, 6)
        if k not in top or p > top[k][2]:
            top[k] = [s, d, p]
    return [top[k] for k in sorted(top)]


def _quantize_for(notes, target, bpm, length_q):
    """Step 5: simplified only if a note is shorter than the instrument allows."""
    from .phrase import simplify, LEVELS
    spq = 60.0 / bpm
    if all(d * spq + 1e-9 >= min_note_s(target, p) for _, d, p in notes):
        return notes, 5
    need_q = max(min_note_s(target, p) for _, _, p in notes) / spq
    for level in (4, 3, 2, 1):                         # finest grid that is long enough
        if LEVELS[level] + 1e-9 >= need_q:
            return simplify(notes, level, length_q), level
    return simplify(notes, 1, length_q), 1


def twins(a, b):
    """Two catalogue keys read the same part the same way (same transposition, clef,
    family and default range): trumpet, cornet, flugelhorn."""
    from .instruments import CATALOGUE
    if a == b:
        return True
    ra, rb = CATALOGUE.get(a), CATALOGUE.get(b)
    if not ra or not rb:
        return False
    return all(ra[k] == rb[k] for k in ("transposition", "clef", "family", "range"))


def translate(ph, target, source_id=None, range_override=None):
    """A NEW Phrase: `ph` for the instrument `target` (catalogue key, e.g. 'C (euphonium)').
    source_id: identity of the original (library id; default its uid). The original is not
    changed. range_override: (lo, hi) written (default: the user's range of the target,
    Settings > Instruments)."""
    from .phrase import Phrase, octave_fit, instrument_range, ONE_VOICE
    prof = _profile(target)
    T = int(prof["transposition"])
    from .instruments import key_of_played
    notes = [list(n) for n in ph.notes]
    src = key_of_played(ph.instrument)
    if src is not None and twins(src, target):
        level = 5                       # its own instrument or a twin: the notes as they are
    else:
        lo, hi = range_override or instrument_range(target)
        notes = octave_fit(notes, T, lo, hi)
        notes = _fold(notes, T, lo, hi)
        if prof["played"] in ONE_VOICE:
            notes = _one_voice(notes)
        bpm = float(ph.practice_bpm or ph.bpm or 90.0)
        notes, level = _quantize_for(notes, target, bpm, ph.length_q)
    d = copy.deepcopy(ph.to_dict())
    d.update(notes=notes, transposition=T, program=int(prof["program"]),
             part=prof["part"], instrument=prof["played"], results=None, grades=None,
             uid=translated_uid(source_id or ph.uid, target))
    if ph.instrument != prof["played"]:
        d["title"] = f"{ph.title} – {prof['label']}"
    origin = dict(d.get("origin") or {})
    origin["translation"] = dict(source=source_id or ph.uid, source_instrument=ph.instrument,
                                 target=target, version=VERSION,
                                 simplified=None if level == 5 else level)
    d["origin"] = origin
    if level != 5:
        d["level"] = min(int(d.get("level", 5)), level)
    return Phrase.from_dict(d)
