#!/usr/bin/env python3
"""
Power Tab (.ptb) -> MIDI for a whole folder (owner, 2026-11-19).

    python3 scripts/ptb2midi.py INPUT_FOLDER OUTPUT_FOLDER [--recursive] [--mono] [--trumpet]

Every .ptb file of INPUT_FOLDER (with --recursive also of its subfolders, kept as
subfolders of OUTPUT_FOLDER) becomes OUTPUT_FOLDER/<same name>.mid (musikite/powertab.py:
one track per guitar, tempo, ONE time signature — the first —, repeats and D.C. / D.S. / Coda expanded;
--mono: ONE track with the highest note at every moment, no polyphony; --trumpet: every
track with the trumpet sound, General MIDI program 56).
What it changes: it only WRITES the .mid files in OUTPUT_FOLDER (created if missing; a .mid
with the same name is REPLACED); the .ptb files are only read. A file that cannot be read is
reported and skipped. Time: well under a second per file.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def main(argv=None):
    from musikite import powertab
    ap = argparse.ArgumentParser(description="Power Tab (.ptb) files of a folder -> MIDI")
    ap.add_argument("input", help="folder with the .ptb files")
    ap.add_argument("output", help="folder for the .mid files")
    ap.add_argument("--recursive", action="store_true", help="also the subfolders")
    ap.add_argument("--mono", action="store_true",
                    help="no polyphony: one track, the highest note at every moment")
    ap.add_argument("--trumpet", action="store_true",
                    help="every track with the trumpet sound (GM program 56)")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.input):
        sys.exit(f"not a folder: {a.input}")
    files = []
    for root, dirs, names in os.walk(a.input):
        dirs.sort()
        files += [os.path.join(root, n) for n in sorted(names) if n.lower().endswith(".ptb")]
        if not a.recursive:
            break
    if not files:
        sys.exit(f"no .ptb files in {a.input}")
    ok = bad = 0
    for src in files:
        rel = os.path.relpath(src, a.input)
        dst = os.path.join(a.output, os.path.splitext(rel)[0] + ".mid")
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        try:
            n = powertab.convert(src, dst, monophonic=a.mono,
                                 program=powertab.TRUMPET_PROGRAM if a.trumpet else None)
            print(f"{rel}: {n} track{'s' if n != 1 else ''} -> {os.path.relpath(dst, a.output)}")
            ok += 1
        except Exception as e:
            print(f"{rel}: NOT converted ({type(e).__name__}: {e})")
            bad += 1
    print(f"{ok} converted, {bad} not converted")


if __name__ == "__main__":
    main()
