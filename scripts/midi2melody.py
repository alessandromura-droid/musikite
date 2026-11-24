#!/usr/bin/env python3
"""
MIDI -> MIDI with the MELODY track only, for a whole folder (owner, 2026-11-19): the third
script of the family of ptb2midi.py / gp2midi.py, same options and same rules.

    python3 scripts/midi2melody.py INPUT_FOLDER OUTPUT_FOLDER [--recursive] [--mono] [--trumpet]

Every .mid / .midi of INPUT_FOLDER (with --recursive also of its subfolders, kept as
subfolders of OUTPUT_FOLDER) becomes OUTPUT_FOLDER/<same name>.mid with ONE track: the one
that most looks like a melody (musikite/melodytrack.py: one voice, high, moving by steps,
present for most of the piece, name / instrument; drums never), plus tempo (every change)
and ONE time signature — the first —. --mono: the highest note at every moment, no
polyphony; --trumpet: the trumpet sound, General MIDI program 56.
For every file it prints the track chosen and its score.
What it changes: it only WRITES the .mid files in OUTPUT_FOLDER (created if missing; a .mid
with the same name is REPLACED); the input files are only read. OUTPUT_FOLDER, if inside
INPUT_FOLDER, is not searched. A file that cannot be read or has no notes is reported and
skipped. Time: well under a second per file.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def main(argv=None):
    from musikite import melodytrack
    ap = argparse.ArgumentParser(description="MIDI files of a folder -> their melody track")
    ap.add_argument("input", help="folder with the MIDI files")
    ap.add_argument("output", help="folder for the melody MIDI files")
    ap.add_argument("--recursive", action="store_true", help="also the subfolders")
    ap.add_argument("--mono", action="store_true",
                    help="no polyphony: the highest note at every moment")
    ap.add_argument("--trumpet", action="store_true",
                    help="the trumpet sound (GM program 56)")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.input):
        sys.exit(f"not a folder: {a.input}")
    out_abs = os.path.abspath(a.output)
    files = []
    for root, dirs, names in os.walk(a.input):
        dirs[:] = sorted(d for d in dirs if os.path.abspath(os.path.join(root, d)) != out_abs)
        files += [os.path.join(root, n) for n in sorted(names)
                  if n.lower().endswith((".mid", ".midi")) and not n.startswith("._")]
        if not a.recursive:
            break
    if not files:
        sys.exit(f"no MIDI files in {a.input}")
    ok = bad = 0
    for src in files:
        rel = os.path.relpath(src, a.input)
        dst = os.path.join(a.output, os.path.splitext(rel)[0] + ".mid")
        if os.path.abspath(dst) == os.path.abspath(src):
            print(f"{rel}: skipped (the output would replace the input)")
            bad += 1
            continue
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        try:
            best = melodytrack.convert(src, dst, monophonic=a.mono,
                                       program=melodytrack.TRUMPET_PROGRAM if a.trumpet else None)
        except Exception as e:
            print(f"{rel}: NOT converted ({type(e).__name__}: {e})")
            bad += 1
            continue
        if best is None:
            print(f"{rel}: NOT converted (no notes)")
            bad += 1
            continue
        print(f"{rel}: track {best['track']} channel {best['channel'] + 1} "
              f"'{best['name']}' ({len(best['notes'])} notes, score {best['score']:.2f})")
        ok += 1
    print(f"{ok} converted, {bad} not converted")


if __name__ == "__main__":
    main()
