"""
FINGERINGS of the brass instruments (owner, 2026-11-09): the valves / slide positions to
show under the notes. Part of the theory engine (as `progressions.py`); pure Python, no
music21, no Qt (Android). Saxophones, clarinets and flutes will have NO written fingerings
(owner).

    from musictools.fingerings import fingering, has_fingerings, instrument_of
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
    return dict(INSTRUMENTS[i]["table"]) if i else {}


def fingering(name, written):
    """Fingering of a WRITTEN note on an instrument: '13' (valves), '4' (slide position),
    None (no fingerings, or the note is out of the table)."""
    i = instrument_of(name)
    return INSTRUMENTS[i]["table"].get(int(written)) if i else None


def fingering_concert(name, concert):
    """Fingering of a note given at CONCERT pitch (written = concert + transposition)."""
    i = instrument_of(name)
    return fingering(i, int(concert) + INSTRUMENTS[i]["transposition"]) if i else None
