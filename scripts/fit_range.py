#!/usr/bin/env python3
"""
MIDI -> MIDI with the notes brought into a RANGE, for a whole folder (owner, 2026-11-19;
e.g. for the trumpet: concert F3-G5 = MIDI 53 79 = written G below the staff - A above it).

    python3 scripts/fit_range.py INPUT_FOLDER OUTPUT_FOLDER LOWEST HIGHEST [--recursive]

LOWEST, HIGHEST = MIDI note numbers (C4 = 60) as they are in the files (concert pitch).
Every .mid / .midi of INPUT_FOLDER (with --recursive also of its subfolders, kept as
subfolders of OUTPUT_FOLDER) becomes OUTPUT_FOLDER/<same name>.mid. Method, TRACK BY TRACK
(drums, channel 10, never touched):
1. the whole track is TRANSPOSED BY SEMITONES (the key changes): among the shifts that leave
   the fewest notes outside LOWEST..HIGHEST, the one that best centres the track in the
   range (a track not wider than the range always fits entirely);
2. the notes still outside are moved by octaves, one by one, into the range;
3. two notes that end on the same pitch at the same time become one (held until the last
   one ends).
Tempo, time / key signatures, controllers, programs, lyrics and resolution are kept.
What it changes: it only WRITES the .mid files in OUTPUT_FOLDER (created if missing; a .mid
with the same name is REPLACED); the input files are only read. OUTPUT_FOLDER, if inside
INPUT_FOLDER, is not searched. A file that cannot be read is reported and skipped.
Time: well under a second per file.
"""
import argparse
import os
import sys

import mido

DRUM_CHANNEL = 9


def _is_on(m):
    return m.type == "note_on" and m.velocity > 0


def _is_off(m):
    return m.type == "note_off" or (m.type == "note_on" and m.velocity == 0)


def fold(p, lo, hi):
    """Pitch p moved by octaves into lo..hi (unchanged if already inside)."""
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    return p


def best_shift(pitches, lo, hi):
    """Semitone shift: fewest notes outside lo..hi, then the closest to the centre."""
    pmin, pmax = min(pitches), max(pitches)
    centre = (lo + hi) / 2.0
    best = None
    for s in range(lo - pmax - 12, hi - pmin + 13):
        out = sum(1 for p in pitches if not lo <= p + s <= hi)
        key = (out, abs((pmin + pmax) / 2.0 + s - centre), abs(s))
        if best is None or key < best[0]:
            best = (key, s)
    return best[1], best[0][0]


def fit_track(track, lo, hi):
    """New track with the notes in lo..hi; returns (track, shift, notes outside after the shift, notes)."""
    pitches = [m.note for m in track
               if _is_on(m) and getattr(m, "channel", 0) != DRUM_CHANNEL]
    if not pitches:
        return track, None, 0, 0
    shift, out = best_shift(pitches, lo, hi)
    new = mido.MidiTrack()
    sounding = {}          # (channel, new pitch) -> notes sounding on it
    pending = 0            # delta time of the messages dropped
    for m in track:
        t = m.time + pending
        pending = 0
        if (m.type in ("note_on", "note_off") and m.channel != DRUM_CHANNEL):
            q = min(127, max(0, fold(m.note + shift, lo, hi)))
            k = (m.channel, q)
            if _is_on(m):
                n = sounding.get(k, 0)
                sounding[k] = n + 1
                if n:
                    pending = t
                    continue
            else:
                n = sounding.get(k, 0)
                if n > 1:
                    sounding[k] = n - 1
                    pending = t
                    continue
                sounding.pop(k, None)
            m = m.copy(note=q)
        new.append(m.copy(time=t))
    return new, shift, out, len(pitches)


def fit_file(src, dst, lo, hi):
    mf = mido.MidiFile(src)
    out = mido.MidiFile(type=mf.type, ticks_per_beat=mf.ticks_per_beat)
    report = []
    for i, tr in enumerate(mf.tracks):
        new, shift, outside, n = fit_track(tr, lo, hi)
        out.tracks.append(new)
        if shift is not None:
            report.append(f"track {i} shift {shift:+d}, {outside}/{n} notes moved by octaves")
    out.save(dst)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="MIDI files of a folder -> notes brought into a range")
    ap.add_argument("input", help="folder with the MIDI files")
    ap.add_argument("output", help="folder for the new MIDI files")
    ap.add_argument("lowest", type=int, help="lowest MIDI note (C4 = 60)")
    ap.add_argument("highest", type=int, help="highest MIDI note (C4 = 60)")
    ap.add_argument("--recursive", action="store_true", help="also the subfolders")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.input):
        sys.exit(f"not a folder: {a.input}")
    if not 0 <= a.lowest <= 127 or not 0 <= a.highest <= 127:
        sys.exit("LOWEST and HIGHEST must be MIDI notes 0-127")
    if a.highest - a.lowest < 11:
        sys.exit("the range must be at least 11 semitones (every note must fit by octaves)")
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
            report = fit_file(src, dst, a.lowest, a.highest)
        except Exception as e:
            print(f"{rel}: NOT converted ({type(e).__name__}: {e})")
            bad += 1
            continue
        print(f"{rel}: " + ("; ".join(report) if report else "no notes, copied"))
        ok += 1
    print(f"{ok} converted, {bad} not converted")


if __name__ == "__main__":
    main()
