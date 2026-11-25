"""
MELODIES AND ETUDES (owner, 2026-11-24; Generate > Melodies and etudes): NEW melodies as
Read & play reading material, in a key and a difficulty, for the instrument chosen beside
the user. NOT BASED ON THE LIBRARY (owner, 2026-11-24: the first version, a Markov model
of the library's melodies, gave "notes at random, no harmony"): the melodies are made by
the rule-based ENGINES of `melodygen.py` (form, harmony, rhythm, then the pitches:
'skeleton' Povel, 'probabilistic' Temperley, 'degrees' Markov on scale degrees) or are a
voice of a new duet ('duet voice', the duet engine). The ENGINE is an option (owner).

The difficulty is CONSTRUCTED (rhythmic cells, leaps, range, non-chord tones by level:
`melodygen.params`) and then checked with `difficulty.py` on the exercise for the
instrument: outside `DIFFICULTY_TOLERANCE` the melody is made again with the level moved
towards the one asked. Key: the one chosen (written) or Auto (from the difficulty, as the
library). Range: the user's range of the instrument (Settings > Instruments). No Qt.

    st = make_melodies(5, "Bb (trumpet)", key="Auto", difficulty=4, bars=16, seed=1,
                       engine="skeleton", time="4/4")
"""
import contextlib
import io
import math
import random

from . import melodygen
from .library import LEVEL_KEY_ACCIDENTALS, WRITTEN_TONICS, key_name, neutral_tonic

DIFFICULTY_TOLERANCE = 1.0
TRIES_PER_MELODY = 25
KEYS = ("Auto",) + WRITTEN_TONICS
DIFFICULTIES = ("Any",) + tuple(str(k) for k in range(11))
TIMES = melodygen.TIMES
MINOR_SHARE = .35                      # share of melodies in a minor key
ENGINES = melodygen.ENGINES + ("duet voice",)
ENGINE_LABELS = dict(melodygen.ENGINE_LABELS, **{"duet voice": "Voice of a new duet"})


def engine_key(engine):
    """'skeleton' … or its label -> the engine key."""
    if engine in ENGINES:
        return engine
    for k, v in ENGINE_LABELS.items():
        if v == engine:
            return k
    raise ValueError(f"engine must be one of {', '.join(ENGINES)}")


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


def _duet_voice(bars, tonic, mode, level, instrument, rng):
    """One voice of a NEW duet (duet engine) in the concert key, cut to `bars` bars."""
    from .midi import Midi
    from .progressions import key_name as kname, chords_to_key
    from .duet import DEFAULT_CHORDS
    from .phrase import exercises_from_midi
    concert = kname(tonic, mode == "aeolian")
    dl = 1 if level < 3.5 else (2 if level < 6.5 else 3)
    with contextlib.redirect_stdout(io.StringIO()):
        m = Midi().makeduet(chords=chords_to_key(DEFAULT_CHORDS, "C", concert), key=concert,
                            concert=True, level=dl, seed=rng.randrange(1000000),
                            rounds=max(1, math.ceil(int(bars) / 8)))
    st = exercises_from_midi(m, purpose="reading", bars=int(bars), parts=[rng.choice((0, 1))],
                             level=5, instrument=instrument, seed=rng.randrange(1000000),
                             whole_octaves=True, include_midi=False)
    return st.phrases[0] if st.phrases else None


def make_melodies(count, instrument, key="Auto", difficulty=None, bars=16, seed=None,
                  engine="skeleton", time="4/4", lib=None):
    """`count` new melodies for `instrument` (catalogue key) as an ExerciseSet (Read & play
    exercises). difficulty None / 'Any' = any (a level drawn for every melody). engine: a
    key of ENGINES or its label; time: '4/4', '3/4', '2/4', '6/8' (the duet voice is
    always 4/4). Fewer if not enough melodies of that difficulty were made (said in the
    title). `lib` is ignored (kept for old calls)."""
    from .phrase import ExerciseSet, Phrase, instrument_range
    from .translate import translate
    from .difficulty import score_of as diff_of
    from .instruments import CATALOGUE, label
    engine = engine_key(engine)
    ts = (4, 4) if engine == "duet voice" else melodygen.parse_ts(time)
    if isinstance(difficulty, str):
        difficulty = None if difficulty in ("", "Any") else float(difficulty)
    rng = random.Random(seed)
    T = int(CATALOGUE[instrument]["transposition"])
    wlo, whi = instrument_range(instrument)
    out, attempts, adj = [], 0, 0.0
    while len(out) < int(count) and attempts < int(count) * TRIES_PER_MELODY:
        attempts += 1
        wanted = difficulty if difficulty is not None else rng.uniform(1, 8)
        level = max(0.0, min(10.0, wanted + adj))
        mode = "aeolian" if rng.random() < MINOR_SHARE else "ionian"
        wt = _written_tonic(key, mode, wanted, rng)
        tonic = (wt - T) % 12
        if engine == "duet voice":
            ph = _duet_voice(bars, tonic, mode, level, instrument, rng)
            if ph is None:
                continue
        else:
            notes = melodygen.melody(int(bars), ts, tonic, mode, wlo - T, whi - T, level,
                                     engine, rng=rng)
            ph = Phrase(notes, int(bars), ts, tonic, mode, 90.0, 0, "Melody", "", "", "none",
                        "reading", 1, instrument="library", transposition=0)
        ex = translate(ph, instrument)
        d = diff_of(ex)
        if difficulty is not None:
            if d is None:
                continue
            if abs(d - difficulty) > DIFFICULTY_TOLERANCE:     # make it again, nearer
                adj = max(-4.0, min(4.0, adj + (.5 if d < difficulty else -.5)))
                continue
        n = len(out) + 1
        ex.transform = "none"
        ex.purpose = "reading"
        ex.title = f"Melody {n} – {key_name(wt, ex.mode)} – {label(instrument)}"
        ex.origin = dict(ex.origin or {}, melodies=dict(seed=seed, key=key,
                                                        difficulty=difficulty, bars=bars,
                                                        engine=engine,
                                                        time=f"{ts[0]}/{ts[1]}"))
        out.append(ex)
    title = f"Melodies and etudes – {len(out)} exercises ({ENGINE_LABELS[engine]})"
    if len(out) < int(count):
        title += f" (asked {count})"
    return ExerciseSet(out, title=title, source="melodies", purpose="reading")
