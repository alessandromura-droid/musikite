"""
FINGERINGS of the brass instruments (owner, 2026-11-09): the valves / slide positions to
show under the notes. Part of the theory engine (as `progressions.py`); pure Python, no
music21, no Qt (Android). Saxophones, clarinets and flutes will have NO written fingerings
(owner).

    from musikite.fingerings import fingering, has_fingerings, instrument_of
    fingering("Trumpet in Bb", 62)          # '13'   (WRITTEN D4)
    fingering("Tenor trombone", 53)         # '1'    (F3, concert: the trombone reads in C)
    fingering(instrument_of("trumpet"), 60) # '0'
    has_fingerings("Alto saxophone in Eb")  # False

THE NOTE IS THE WRITTEN ONE (the note read): every instrument has its transposition (written
- concert, as `theory.written_part`). An instrument that has no fingering for a note (out of
its range) gives None.

INSTRUMENTS:
- VALVES (kind 'valves', fingering = the valves pressed, '0' = open, '13' = 1st and 3rd):
  one table on the WRITTEN note for the Bb / C trumpet family (`VALVE_TABLE`, the standard
  fingering, one per note; = scoreread.FINGERING, kept there unchanged for the PDF engine):
  trumpet in Bb and in C, cornet in Bb, flugelhorn in Bb read the same chart (a trumpet in C
  reads in C and sounds in C: the same fingering on the written note). Instruments in F,
  Eb… (horn, alto horn) will be new rows with their own table.
- SLIDE (kind 'slide', fingering = the position '1'-'7'): tenor trombone in Bb without
  trigger, reading in C (concert pitch, bass clef). Positions DERIVED from the harmonic
  series of the Bb1 pedal (`_slide_table`): partials 2, 3, 4, 5, 6, 8, 9, 10, 12; a position
  lowers by one semitone each (1 = closed … 7 = E2); the closest position wins; the 7th
  partial (flat) only for the notes BELOW it (F#4 = 3, G4 = 2; Ab4 = 3 on the 8th). Range
  E2-F5. Result = the standard chart (B3 4, C4 3, D4 1, Eb4 3, F#4 3, G4 2, B4 2, C5 1,
  Eb5 3, F5 1).

HOW TO GROW IT: a new instrument = a new row of INSTRUMENTS (kind, transposition, clef,
table) with its source; the names are those of `theory.written_part` where they exist
("Trumpet in Bb"). One fingering per note for now (no alternatives).

OPTIONS OF THE INSTRUMENT (owner, 2026-11-24, "incremental, in order of simplicity, not a
final version"): per user (settings key `fingering_options`, Settings > Instruments):
- `four_valves` (euphonium, tubas): a 4th valve a fourth lower. 5 and 6 semitones down are
  '4' and '24' (instead of 13 and 123, as on 4-valve instruments, better in tune), 7-11
  semitones '14', '124', '234', '134', '1234': the notes between the 2nd partial and the
  pedal become playable. NOT compensating (no correction of the sharp combinations).
- `f_trigger` (tenor trombone; the bass trombone ALWAYS has it): the F attachment lowers the
  instrument a fourth (pedal F1). Trigger positions 'T1'… DERIVED as the slide (partials 2,
  3, 4 of F1, positions T1-T6): used where the Bb side needs position 6 or 7 and the trigger
  has T1-T3 (C3 = T1, B2 = T2, F2 = T1, E2 = T2) and below E2 (Eb2 … C2: T3-T6). The real
  trigger positions are longer than the Bb ones: the number is only the order.
- `double_horn` (horn in F): the Bb side (thumb valve 'T', fundamental a fourth higher) from
  written G#4 up (`DOUBLE_HORN_SWITCH`): 'T0', 'T2'…, derived from the Bb harmonic series as
  the F side.
"""
import math

# Bb / C trumpet family: WRITTEN pitch (MIDI number, C4 = 60) -> valves
VALVE_TABLE = {
    54: "123", 55: "13", 56: "23", 57: "12", 58: "1", 59: "2", 60: "0",
    61: "123", 62: "13", 63: "23", 64: "12", 65: "1", 66: "2", 67: "0",
    68: "23", 69: "12", 70: "1", 71: "2", 72: "0",
    73: "12", 74: "1", 75: "2", 76: "0", 77: "1", 78: "2", 79: "0",
    80: "23", 81: "12", 82: "1", 83: "2", 84: "0",
    85: "12", 86: "1", 87: "2", 88: "0", 89: "1", 90: "2", 91: "0",
}
VALVE_COMBINATIONS = ("0", "2", "1", "12", "23", "13", "123")
SLIDE_POSITIONS = ("1", "2", "3", "4", "5", "6", "7")

TROMBONE_PEDAL = 34                     # Bb1: fundamental of the tenor trombone
TROMBONE_PARTIALS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12)
TROMBONE_RANGE = (40, 77)               # E2 - F5 (concert = written)


def _slide_table(pedal=TROMBONE_PEDAL, partials=TROMBONE_PARTIALS, lo=TROMBONE_RANGE[0],
                 hi=TROMBONE_RANGE[1]):
    """Note -> position from the harmonic series: on partial k (pitch rounded) position n
    sounds n - 1 semitones lower; the lowest position number wins; the 7th partial (31
    cents flat) is used only from position 2 (its 1st position is never the chart's)."""
    out = {}
    for p in range(lo, hi + 1):
        best = None
        for k in partials:
            top = round(pedal + 12 * math.log2(k))
            pos = top - p + 1
            if not 1 <= pos <= 7 or (k == 7 and pos == 1):
                continue
            best = pos if best is None else min(best, pos)
        if best is not None:
            out[p] = str(best)
    return out


SLIDE_TABLE = _slide_table()
def valve_table(fundamental, lo, hi, partials=(2, 3, 4, 5, 6, 8, 10, 12, 16)):
    """{pitch: valves} of a 3-valve instrument DERIVED from its harmonic series (2026-11-19):
    on partial k (pitch rounded, of `fundamental`) the valves 0, 2, 1, 12, 23, 13, 123 lower
    it by 0-6 semitones; the fewest semitones win. The partials out of tune (7, 9, 11, 13,
    14, 15) are not used, as in the standard charts: with the trumpet's written fundamental
    (C3 = 48) this gives VALVE_TABLE exactly. `fundamental` and the result are in the
    pitches the instrument READS (written for the horn, concert for the tubas)."""
    out = {}
    tops = [round(fundamental + 12 * math.log2(k)) for k in partials]
    for p in range(lo, hi + 1):
        best = None
        for t in tops:
            d = t - p
            if 0 <= d <= 6 and (best is None or d < best):
                best = d
        if best is not None:
            out[p] = VALVE_COMBINATIONS[best]
    return out


# HORN in F (single F horn; written; fundamental written C2): F#2-C6
HORN_F_TABLE = valve_table(36, 42, 84)
# DOUBLE HORN (option double_horn): the Bb side, written (fundamental written F2), from G#4
DOUBLE_HORN_SWITCH = 68
HORN_BB_TABLE = valve_table(41, 47, 89)

# 4th VALVE (option four_valves): semitones down -> valves
FOUR_VALVE_COMBINATIONS = ("0", "2", "1", "12", "23", "4", "24", "14", "124", "234", "134",
                           "1234")


def valve_table4(fundamental, lo, hi, partials=(2, 3, 4, 5, 6, 8, 10, 12, 16)):
    """As valve_table() with a 4th valve (a fourth): 0-11 semitones below a partial."""
    out = {}
    tops = [round(fundamental + 12 * math.log2(k)) for k in partials]
    for p in range(lo, hi + 1):
        best = None
        for t in tops:
            d = t - p
            if 0 <= d < len(FOUR_VALVE_COMBINATIONS) and (best is None or d < best):
                best = d
        if best is not None:
            out[p] = FOUR_VALVE_COMBINATIONS[best]
    return out


# F TRIGGER of the trombones (option f_trigger; the bass trombone always): F1 pedal
TRIGGER_PEDAL = 29
TRIGGER_LOW = 36                        # C2: lowest note with the trigger


def _trigger_table(pedal=TRIGGER_PEDAL, partials=(2, 3, 4), lo=TRIGGER_LOW, hi=60):
    out = {}
    for p in range(lo, hi + 1):
        best = None
        for k in partials:
            top = round(pedal + 12 * math.log2(k))
            pos = top - p + 1
            if 1 <= pos <= 6:
                best = pos if best is None else min(best, pos)
        if best is not None:
            out[p] = best
    return out


TRIGGER_POSITIONS = _trigger_table()


def _with_trigger(slide):
    """The slide table with the F trigger: 'T<n>' where the Bb side needs 6 / 7 and the
    trigger has T1-T3, and below E2."""
    out = dict(slide)
    for p, t in TRIGGER_POSITIONS.items():
        bb = int(slide[p]) if p in slide else None
        if bb is None or (bb >= 6 and t <= 3):
            out[p] = f"T{t}"
    return out


TRIGGER_TABLE = _with_trigger(SLIDE_TABLE)
# TUBAS (3 valves, concert = written, bass clef): fundamentals BBb0, CC1, Eb1, F1
TUBA_TABLES = {"Bb": valve_table(22, 28, 70), "C": valve_table(24, 30, 72),
               "Eb": valve_table(27, 33, 72), "F": valve_table(29, 35, 75)}
# EUPHONIUM in the bass clef (concert pitch, owner 2026-11-19): the valves of the same note
# read in the treble clef in Bb (written = concert + 14) — the 3-valve chart, E2-E5; no 4th
# valve yet
EUPHONIUM_BASS_TABLE = {c: VALVE_TABLE[c + 14] for c in range(40, 78)
                        if c + 14 in VALVE_TABLE}

# name -> kind, transposition (written - concert), clef, table {written pitch: fingering},
# source
INSTRUMENTS = {
    "Trumpet in Bb": dict(kind="valves", transposition=2, clef="treble", table=VALVE_TABLE,
                          source="standard trumpet chart"),
    "Trumpet in C": dict(kind="valves", transposition=0, clef="treble", table=VALVE_TABLE,
                         source="standard trumpet chart"),
    "Cornet in Bb": dict(kind="valves", transposition=2, clef="treble", table=VALVE_TABLE,
                         source="standard trumpet chart"),
    "Flugelhorn in Bb": dict(kind="valves", transposition=2, clef="treble",
                             table=VALVE_TABLE, source="standard trumpet chart"),
    "Euphonium in Bb": dict(kind="valves", transposition=14, clef="treble",
                            table=VALVE_TABLE, source="standard trumpet chart (treble clef "
                                                     "in Bb, an octave + a tone lower)"),
    "Euphonium": dict(kind="valves", transposition=0, clef="bass", table=EUPHONIUM_BASS_TABLE,
                      source="3-valve chart on the concert note (= treble clef in Bb - 14)"),
    "Tenor Horn in Eb": dict(kind="valves", transposition=9, clef="treble", table=VALVE_TABLE,
                             source="standard trumpet chart on the written note"),
    "Mellophone in F": dict(kind="valves", transposition=7, clef="treble", table=VALVE_TABLE,
                            source="standard trumpet chart on the written note"),
    "Horn in F": dict(kind="valves", transposition=7, clef="treble", table=HORN_F_TABLE,
                      source="single F horn, harmonic series of written C2"),
    "Tuba in Bb": dict(kind="valves", transposition=0, clef="bass", table=TUBA_TABLES["Bb"],
                       source="BBb tuba, harmonic series of Bb0"),
    "Tuba in C": dict(kind="valves", transposition=0, clef="bass", table=TUBA_TABLES["C"],
                      source="CC tuba, harmonic series of C1"),
    "Tuba in Eb": dict(kind="valves", transposition=0, clef="bass", table=TUBA_TABLES["Eb"],
                       source="Eb tuba, harmonic series of Eb1"),
    "Tuba in F": dict(kind="valves", transposition=0, clef="bass", table=TUBA_TABLES["F"],
                      source="F tuba, harmonic series of F1"),
    "Bass trombone": dict(kind="slide", transposition=0, clef="bass", table=TRIGGER_TABLE,
                          source="tenor positions + F trigger (T1-T6); no second trigger"),
    "Tenor trombone": dict(kind="slide", transposition=0, clef="bass", table=SLIDE_TABLE,
                           source="harmonic series of Bb1, standard chart"),
}

# other names of the same instruments (exercise instruments, General MIDI names, Italian)
ALIASES = {
    "trumpet": "Trumpet in Bb", "Bb (trumpet)": "Trumpet in Bb", "tromba": "Trumpet in Bb",
    "Trumpet": "Trumpet in Bb", "Trumpet in Bb 1": "Trumpet in Bb",
    "C (trumpet)": "Trumpet in C", "cornet": "Cornet in Bb", "cornetta": "Cornet in Bb",
    "flugelhorn": "Flugelhorn in Bb", "flicorno": "Flugelhorn in Bb",
    "trombone": "Tenor trombone", "Trombone": "Tenor trombone",
    "euphonium treble": "Euphonium in Bb", "Bb (euphonium, treble clef)": "Euphonium in Bb",
    "euphonium": "Euphonium", "C (euphonium)": "Euphonium", "eufonio": "Euphonium",
    "trumpet in C": "Trumpet in C", "tenor horn": "Tenor Horn in Eb",
    "Eb (tenor horn)": "Tenor Horn in Eb", "flicorno contralto": "Tenor Horn in Eb",
    "mellophone": "Mellophone in F", "F (mellophone)": "Mellophone in F",
    "horn": "Horn in F", "F (horn)": "Horn in F", "corno": "Horn in F",
    "bass trombone": "Bass trombone", "C (bass trombone)": "Bass trombone",
    "tuba": "Tuba in Bb", "Bb (tuba)": "Tuba in Bb", "sousaphone": "Tuba in Bb",
    "Bb (sousaphone)": "Tuba in Bb", "tuba in C": "Tuba in C", "C (tuba)": "Tuba in C",
    "tuba in Eb": "Tuba in Eb", "Eb (tuba)": "Tuba in Eb", "tuba in F": "Tuba in F",
    "F (tuba)": "Tuba in F",
}


def instrument_of(name):
    """Name of INSTRUMENTS for a name (an exercise's instrument 'trumpet', 'trombone', a
    written part name 'Trumpet in Bb 2', an alias); None if it has no fingerings."""
    if not name:
        return None
    if name in INSTRUMENTS:
        return name
    if name in ALIASES:
        return ALIASES[name]
    base = name.rstrip(" 0123456789")             # "Trumpet in Bb 2" -> "Trumpet in Bb"
    return base if base in INSTRUMENTS else ALIASES.get(base)


def has_fingerings(name):
    return instrument_of(name) is not None


def kind_of(name):
    """'valves', 'slide' or None."""
    i = instrument_of(name)
    return INSTRUMENTS[i]["kind"] if i else None


def table(name):
    """{written pitch: fingering} of an instrument ({} if it has none)."""
    i = instrument_of(name)
    return dict(table_with_options(i)) if i else {}


OPTIONS = ("four_valves", "f_trigger", "double_horn")
OPTION_LABELS = {"four_valves": "4th valve (euphonium, tubas)",
                 "f_trigger": "F trigger (tenor trombone; the bass trombone always has it)",
                 "double_horn": "Double horn (horn in F: Bb side from written G#4)"}
FOUR_VALVE_INSTRUMENTS = ("Euphonium in Bb", "Euphonium", "Tuba in Bb", "Tuba in C",
                          "Tuba in Eb", "Tuba in F")
_FUNDAMENTALS = {"Tuba in Bb": (22, 23, 70), "Tuba in C": (24, 25, 72),
                 "Tuba in Eb": (27, 28, 72), "Tuba in F": (29, 30, 75),
                 "Euphonium": (34, 35, 77), "Euphonium in Bb": (48, 49, 91)}
_TABLES4 = {}


def options():
    """{option: bool} of the current user (settings key `fingering_options`); all False
    without settings (pure use, Android)."""
    out = {k: False for k in OPTIONS}
    try:
        from .progress import settings
        out.update({k: bool(v) for k, v in (settings().get("fingering_options") or {}).items()
                    if k in OPTIONS})
    except Exception:
        pass
    return out


def set_options(**opts):
    from .progress import settings, save_setting
    cur = dict(settings().get("fingering_options") or {})
    cur.update({k: bool(v) for k, v in opts.items() if k in OPTIONS})
    save_setting("fingering_options", cur)
    return cur


def table_with_options(name, opts=None):
    """{written pitch: fingering} of an instrument with the options (4th valve, F trigger,
    double horn) of the user, or `opts`."""
    i = instrument_of(name)
    if not i:
        return {}
    o = options() if opts is None else dict(options(), **opts)
    if i in FOUR_VALVE_INSTRUMENTS and o.get("four_valves"):
        if i not in _TABLES4:
            f, lo, hi = _FUNDAMENTALS[i]
            _TABLES4[i] = valve_table4(f, lo, hi)
        return _TABLES4[i]
    if i == "Bass trombone" or (i == "Tenor trombone" and o.get("f_trigger")):
        return TRIGGER_TABLE
    if i == "Horn in F" and o.get("double_horn"):
        t = dict(HORN_F_TABLE)
        for p, v in HORN_BB_TABLE.items():
            if p >= DOUBLE_HORN_SWITCH:
                t[p] = "T" + v
        return t
    return INSTRUMENTS[i]["table"]


def fingering(name, written, opts=None):
    """Fingering of a WRITTEN note on an instrument: '13' (valves), '4' (slide position),
    'T1' (trigger / Bb side of the double horn), None (no fingerings, or the note is out of
    the table). The options of the user (4th valve, F trigger, double horn) are applied."""
    i = instrument_of(name)
    return table_with_options(i, opts).get(int(written)) if i else None


def fingering_concert(name, concert):
    """Fingering of a note given at CONCERT pitch (written = concert + transposition)."""
    i = instrument_of(name)
    return fingering(i, int(concert) + INSTRUMENTS[i]["transposition"]) if i else None
