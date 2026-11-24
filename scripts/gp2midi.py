#!/usr/bin/env python3
"""
Guitar Pro (.gp3, also .gp4 / .gp5) -> MIDI for a whole folder (owner, 2026-11-19): the twin
of ptb2midi.py, same options and same rules.

    python3 scripts/gp2midi.py INPUT_FOLDER OUTPUT_FOLDER [--recursive] [--mono] [--trumpet]

Every Guitar Pro file of INPUT_FOLDER (with --recursive also of its subfolders, kept as
subfolders of OUTPUT_FOLDER) becomes OUTPUT_FOLDER/<same name>.mid (musikite/gptab.py:
one track per guitar, tempo, ONE time signature — the first —, repeats and alternate endings
played out; --mono: ONE track with the highest note at every moment, no polyphony;
--trumpet: every track with the trumpet sound, General MIDI program 56).
Needs PyGuitarPro: pip install pyguitarpro.
What it changes: it only WRITES the .mid files in OUTPUT_FOLDER (created if missing; a .mid
with the same name is REPLACED); the Guitar Pro files are only read. A file that cannot be
read is reported and skipped. Time: well under a second per file.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def main(argv=None):
    from musikite import gptab
    ap = argparse.ArgumentParser(description="Guitar Pro files of a folder -> MIDI")
    ap.add_argument("input", help="folder with the .gp3 / .gp4 / .gp5 files")
    ap.add_argument("output", help="folder for the .mid files")
    ap.add_argument("--recursive", action="store_true", help="also the subfolders")
    ap.add_argument("--mono", action="store_true",
                    help="no polyphony: one track, the highest note at every moment")
    ap.add_argument("--trumpet", action="store_true",
                    help="every track with the trumpet sound (GM program 56)")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.input):
        sys.exit(f"not a folder: {a.input}")
    try:
        import guitarpro  # noqa: F401
    except ImportError:
        sys.exit("PyGuitarPro is missing: pip install pyguitarpro")
    files = []
    for root, dirs, names in os.walk(a.input):
        dirs.sort()
        files += [os.path.join(root, n) for n in sorted(names)
                  if n.lower().endswith(gptab.EXTENSIONS) and not n.startswith("._")]
        if not a.recursive:
            break
    if not files:
        sys.exit(f"no Guitar Pro files in {a.input}")
    ok = bad = 0
    for src in files:
        rel = os.path.relpath(src, a.input)
        dst = os.path.join(a.output, os.path.splitext(rel)[0] + ".mid")
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        try:
            n = gptab.convert(src, dst, monophonic=a.mono,
                              program=gptab.TRUMPET_PROGRAM if a.trumpet else None)
            print(f"{rel}: {n} track{'s' if n != 1 else ''} -> {os.path.relpath(dst, a.output)}")
            ok += 1
        except Exception as e:
            print(f"{rel}: NOT converted ({type(e).__name__}: {e})")
            bad += 1
    print(f"{ok} converted, {bad} not converted")


if __name__ == "__main__":
    main()
