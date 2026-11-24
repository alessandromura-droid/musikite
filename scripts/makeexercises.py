#!/usr/bin/env python3
"""
Make Read & play exercises for the trumpet from every MIDI file of a folder (owner, 2026-11-08).

    python3 scripts/makeexercises.py "/personali/musica/tromba/esercizi musikite"

For every MIDI file of the folder (no subfolders), for every voice (a duet: one exercise per
voice), for every piece (a MIDI of MAX_BARS bars or more is cut into round(bars / PIECE_BARS)
equal pieces: 28 bars stay one piece, 48 -> 2 × 24, 60 -> 2 × 30, 72 -> 3 × 24):
  cycle 1  every transformation (none, reverse melody, reverse rhythm, inversion, remove
           accidentals, even eighths, every other church mode),
  cycle 2  every key: transposition -5 … +6 semitones (12 keys; -6 = +6),
  cycle 3  tempo 50 %, 100 %, 150 % of the MIDI tempo;
the result identical to the start (none, 0, 100 %) and results identical to another one are
skipped. RANGE (owner): every transposition is moved by WHOLE OCTAVES (the whole exercise,
never note by note) into LOWEST … HIGHEST, written for the Bb trumpet (G3 … C6); an
exercise wider than that range is skipped. TRUMPET = ONE VOICE: never polyphony (a chord
keeps its highest note; voices on separate tracks give separate exercises). Every exercise is rated (musikite.difficulty) and
saved AS AN EXERCISE (.json, not MIDI; it remembers its MIDI, so it can be changed in the
app; the key of every exercise is estimated again after the transformation and the
transposition — the key it is READ in — and is in its name and file name, e.g.
exercise0012_G_major.mke (.mke = one zip with the compact JSON inside); with --no-include_midi = "do not include MIDI": no trace of the MIDI, the exercise
cannot be cut again) in  <project>/exercises/trumpet/levelNN/exerciseNNNN_<key>.mke  (NN = difficulty rounded;
the numbers continue after the ones already there). The name inside every exercise is only
"exercise in <written key>" and the part "Trumpet in Bb" (owner: nothing of the MIDI).
"""
import argparse
import contextlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)

# ---------------------------------------------------------------- parameters
HIGHEST = "C6"              # highest WRITTEN note for the Bb trumpet (owner: the third C)
LOWEST = "G3"               # lowest written note (owner: low G … C6 = 2 octaves + a fourth)
MAX_BARS = 48               # longer MIDI files are cut into pieces …
PIECE_BARS = 24             # … of about this many bars
TRANSPOSITIONS = range(-5, 7)
SPEEDS = (0.5, 1.0, 1.5)
INSTRUMENT = "Bb (trumpet)"
OUT = os.path.join(PROJECT, "exercises", "trumpet")


def pieces(numbers):
    """Bar numbers -> list of (first, last) pieces."""
    n = len(numbers)
    k = max(1, int(round(n / PIECE_BARS))) if n >= MAX_BARS else 1
    edges = [round(i * n / k) for i in range(k + 1)]
    return [(numbers[edges[i]], numbers[edges[i + 1] - 1]) for i in range(k)]


MODE_NAMES = {"ionian": "major", "aeolian": "minor"}
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")


def key_title(ph):
    """Name of an exercise (owner, 2026-11-08): only 'exercise in <key>', the WRITTEN key
    (as read on the staff), e.g. 'exercise in G major', 'exercise in E minor',
    'exercise in D dorian' — nothing of the MIDI it comes from."""
    from musikite.theory import key_signature
    pc = (ph.tonic + ph.transposition) % 12
    flats = key_signature(pc, ph.mode) < 0               # spelled as its key signature
    tonic = (FLAT_NAMES if flats else SHARP_NAMES)[pc]
    return f"exercise in {tonic} {MODE_NAMES.get(ph.mode, ph.mode)}"


def octave_shift(written, lo, hi):
    """Whole octaves (closest to 0) that bring every note into lo … hi; None if the notes
    span more than the range."""
    if not written:
        return None
    a, b = min(written), max(written)
    if b - a > hi - lo:
        return None
    shifts = [12 * n for n in range(-6, 7) if lo <= a + 12 * n and b + 12 * n <= hi]
    return min(shifts, key=abs) if shifts else None


def next_number(out):
    last = 0
    for root, _, files in os.walk(out):
        for f in files:
            m = re.match(r"exercise(\d+)(?:_.*)?\.(?:mke|json)$", f)
            if m:
                last = max(last, int(m.group(1)))
    return last + 1


def transformations(mode):
    from musikite.phrase import TRANSFORMS, MODES
    tags = [t for t in TRANSFORMS if t not in ("transpose", "mode")]
    return tags + [f"mode {m}" for m in MODES if m != mode]


def main():
    ap = argparse.ArgumentParser(description="Read & play exercises for the trumpet from a "
                                             "folder of MIDI files")
    ap.add_argument("folder", help="folder with the MIDI files (no subfolders)")
    ap.add_argument("--out", default=OUT, help=f"output folder (default {OUT})")
    ap.add_argument("--highest", default=HIGHEST, help=f"highest written note (default {HIGHEST})")
    ap.add_argument("--lowest", default=LOWEST, help=f"lowest written note (default {LOWEST})")
    ap.add_argument("--include_midi", action=argparse.BooleanOptionalAction, default=True,
                    help="keep the source MIDI in every exercise (default); "
                         "--no-include_midi = do not include MIDI (no trace of it)")
    a = ap.parse_args()

    from musikite.midi import Midi
    from musikite.score import Score
    from musikite.phrase import exercises_from_midi, save_exercises, INSTRUMENTS
    from musikite.difficulty import difficulty
    from musikite.theory import parse_note, key_of_notes

    T = INSTRUMENTS[INSTRUMENT][0]                       # written = concert + T
    lo, hi = parse_note(a.lowest), parse_note(a.highest)
    files = sorted(f for f in os.listdir(a.folder)
                   if f.lower().endswith((".mid", ".midi"))
                   and os.path.isfile(os.path.join(a.folder, f)))
    if not files:
        sys.exit(f"no MIDI files in {a.folder}")
    os.makedirs(a.out, exist_ok=True)
    number = next_number(a.out)
    total = 0
    for fname in files:
        path = os.path.join(a.folder, fname)
        title = os.path.splitext(fname)[0]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                midi = Midi(path)
                score = Score.from_midi(midi, written=False)
        except Exception as e:
            print(f"{fname}: skipped ({type(e).__name__}: {e})")
            continue
        made = skipped = 0
        for ip, part in enumerate(score.m21.parts):
            numbers = [m.number for m in part.getElementsByClass("Measure")]
            if not numbers or not part.recurse().notes:
                continue
            for first, last in pieces(numbers):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        base = exercises_from_midi(
                            midi, purpose="reading", parts=[ip], bar_range=(first, last),
                            level=5, instrument=INSTRUMENT, remove_empty=False,
                            polyphony=False,                 # trumpet: one voice only
                            note_range=(0, 127), title=title,
                            include_midi=a.include_midi).phrases[0]
                except Exception as e:
                    print(f"{fname} part {ip + 1} bars {first}-{last}: {e}")
                    continue
                seen = set()
                for tag in transformations(base.mode):
                    t_ph = base.transformed(tag)
                    for k in TRANSPOSITIONS:
                        written = [p + T + k for _, _, p in t_ph.notes]
                        o = octave_shift(written, lo, hi)
                        if o is None:                        # wider than the range
                            skipped += len(SPEEDS)
                            continue
                        k_all = k + o
                        ph = t_ph.transpose(k_all) if k_all else t_ph
                        for f in SPEEDS:
                            if tag == "none" and k_all == 0 and f == 1.0:
                                continue                     # the start itself
                            bpm = round(base.bpm * f)
                            key = (tuple(tuple(n) for n in ph.notes), bpm)
                            if key in seen or (f == 1.0 and
                                               [list(n) for n in ph.notes] == base.notes):
                                skipped += 1
                                continue
                            seen.add(key)
                            ex = ph.copy()
                            ex.practice_bpm = float(bpm)
                            if a.include_midi:
                                om = dict((base.origin or {}).get("midi") or {})
                                om.update(transform=tag, transpose=int(k_all))
                                ex.origin = dict(base.origin or {}, midi=om)
                                ex.source_midi = base.source_midi
                            else:                            # do not include MIDI
                                ex.origin, ex.source_midi = None, None
                            # the key the transformed melody is READ in (owner, option 3):
                            # estimated again (tonalita.m + relative minor rule), so a
                            # 'mode lydian' made from F major is named / signed as it reads
                            ex.tonic, ex.mode = key_of_notes(ex.notes)
                            ex.title = key_title(ex)         # owner: only the key
                            ex.source = ""
                            if not ex.read_as:               # not the MIDI track name
                                ex.part = "Trumpet in Bb"
                            d = difficulty(ex)
                            level = int(round(d["score"]))
                            folder = os.path.join(a.out, f"level{level:02d}")
                            os.makedirs(folder, exist_ok=True)
                            fname_key = ex.title[len("exercise in "):].replace(" ", "_")
                            save_exercises(ex, os.path.join(
                                folder, f"exercise{number:04d}_{fname_key}.mke"))
                            number += 1
                            made += 1
        total += made
        print(f"{fname}: {made} exercises ({skipped} skipped: out of range / identical)")
    print(f"total: {total} exercises in {a.out}")


if __name__ == "__main__":
    main()
