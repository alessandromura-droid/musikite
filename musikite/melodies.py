"""
MELODIES AND ETUDES (owner, 2026-11-24; Generate > Melodies and etudes, before "(to do)"):
NEW melodies as Read & play reading material, in a key and a difficulty, for the instrument
chosen beside the user. The melodies are made by the Markov model of `libgen.Markov`
(intervals order 2 with back-off, bar rhythms of the corpus per metre) trained on melodies
of the EXERCISE LIBRARY (the originals, else all; at most `CORPUS_MAX` drawn at random), so
they are new: a melody sharing more than `libgen.COPY_MAX` consecutive intervals with a
source is thrown away, and every one must pass the entropy filter (`MIN_ENTROPY` bits).
Then: moved to the written key chosen (or Auto from the difficulty, as the library) and
translated for the instrument (`translate.translate`); kept only if its difficulty for
the instrument (`difficulty.py`) is within `DIFFICULTY_TOLERANCE` of the one asked (Any =
all). No Qt.

    st = make_melodies(5, "Bb (trumpet)", key="Auto", difficulty=4, bars=16, seed=1)
"""
import random

from . import libgen
from .library import (LEVEL_KEY_ACCIDENTALS, WRITTEN_TONICS, key_name, neutral_tonic)

CORPUS_MAX = 300
MIN_ENTROPY = 3.5
DIFFICULTY_TOLERANCE = 1.0
TRIES_PER_MELODY = 40
KEYS = ("Auto",) + WRITTEN_TONICS
DIFFICULTIES = ("Any",) + tuple(str(k) for k in range(11))


def corpus(rng, lib=None):
    """Source melodies (Phrases) of the library: the originals, else every melody."""
    from .library import get
    lib = lib or get()
    entries = list(lib.entries())
    orig = [e for e in entries if e.get("kind") == "original"]
    entries = orig or entries
    if not entries:
        raise RuntimeError("the exercise library is empty: no melodies to learn from")
    if len(entries) > CORPUS_MAX:
        entries = rng.sample(entries, CORPUS_MAX)
    out = []
    for e in entries:
        try:
            out.append(lib.melody(e))
        except Exception:
            pass
    return out


def _written_tonic(key, mode, level, rng):
    """The written tonic: the one chosen, or Auto = a key signature with the accidentals
    allowed for the difficulty (library.LEVEL_KEY_ACCIDENTALS)."""
    from .theory import key_signature
    if key and key != "Auto":
        return WRITTEN_TONICS.index(key)
    lv = max(0, min(10, int(round(float(level if level is not None else 3)))))
    a, b = LEVEL_KEY_ACCIDENTALS[lv]
    cands = [t for t in range(12) if a <= abs(key_signature(t, mode)) <= b]
    return rng.choice(cands) if cands else neutral_tonic(mode)


def make_melodies(count, instrument, key="Auto", difficulty=None, bars=16, seed=None,
                  lib=None):
    """`count` new melodies for `instrument` (catalogue key) as an ExerciseSet (Read & play
    exercises). difficulty None / 'Any' = any. Fewer if not enough melodies of that
    difficulty were found (said in the title)."""
    from .phrase import ExerciseSet
    from .translate import translate
    from .difficulty import score_of as diff_of
    from .instruments import CATALOGUE, label
    if isinstance(difficulty, str):
        difficulty = None if difficulty in ("", "Any") else float(difficulty)
    rng = random.Random(seed)
    model = libgen.Markov(corpus(rng, lib))
    for ts in list(model.lengths):                   # the length asked, not the corpus'
        model.lengths[ts] = [int(bars)]
    T = int(CATALOGUE[instrument]["transposition"])
    out, attempts = [], 0
    while len(out) < int(count) and attempts < int(count) * TRIES_PER_MELODY:
        attempts += 1
        ph = model.generate(rng)
        if ph is None or not libgen.passes(ph, MIN_ENTROPY):
            continue
        wt = _written_tonic(key, ph.mode, difficulty, rng)
        k = ((wt - T) - ph.tonic) % 12
        if k > 6:
            k -= 12
        if k:
            ph = ph.transpose(k)
        ex = translate(ph, instrument)
        d = diff_of(ex)
        if difficulty is not None and (d is None or abs(d - difficulty) > DIFFICULTY_TOLERANCE):
            continue
        n = len(out) + 1
        ex.transform = "none"
        ex.purpose = "reading"
        ex.title = f"Melody {n} – {key_name(wt, ex.mode)} – {label(instrument)}"
        ex.origin = dict(ex.origin or {}, melodies=dict(seed=seed, key=key,
                                                        difficulty=difficulty, bars=bars))
        out.append(ex)
    title = f"Melodies and etudes – {len(out)} exercises"
    if len(out) < int(count):
        title += f" (asked {count})"
    return ExerciseSet(out, title=title, source="melodies", purpose="reading")
