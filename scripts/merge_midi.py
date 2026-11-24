#!/usr/bin/env python3
"""
Merge MIDI files: all their tracks in one MIDI (English version of the old fondi_midi.py,
owner 2026-11-08).

    python3 scripts/merge_midi.py part1.mid part2.mid ... out.mid

The output keeps the TEMPO MAP of the files (the first tempo and every tempo change), their
time and key signatures and their resolution. The files must have the SAME tempo map: if
not, it stops with an error and writes nothing (the old fondi_midi.py made a new MIDI at
the default 120 bpm and the parts at 100 came out stretched by 1.2: right to listen to,
wrong in a score and against a metronome). Uses musikite.midi.merge(strict=True).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 1
    *inputs, out = argv
    if not out.lower().endswith((".mid", ".midi")):
        out += ".mid"
    out_abs = os.path.abspath(out)
    inputs = [f for f in inputs if os.path.abspath(f) != out_abs]   # never the output itself
    if not inputs:
        print("error: no input MIDI file")
        return 1
    from musikite.midi import merge
    try:
        m = merge(*inputs, strict=True)
    except ValueError as e:
        print(f"error: {e}")
        print("nothing written: the files have different tempos")
        return 2
    for f in inputs:
        print("  " + os.path.basename(f))
    m.write(out)
    ts = m.tempo_map()
    print(f"{len(inputs)} files, {len(m.pm.instruments)} tracks, tempo "
          + ", ".join(f"{b:g}" + (f" (quarter {q:g})" if q else "") for q, b in ts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
