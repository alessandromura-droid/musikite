#!/usr/bin/env python3
"""
Select MIDI files by their range (owner, 2026-11-19).

    python3 scripts/select_by_range.py INPUT_FOLDER OUTPUT_FOLDER --max_range 24

Every .mid / .midi in INPUT_FOLDER and its subfolders whose range (highest note - lowest
note, in SEMITONES) is at most --max_range is COPIED into OUTPUT_FOLDER (no subfolders
there; 12 = an octave, 24 = two octaves, 26 = two octaves and a major second).

- The range is measured on ALL the notes of the file, every track together; drum notes
  (MIDI channel 10) are not counted.
- A file in a subfolder gets the subfolder path in its name, so that two files with the
  same name in different subfolders never overwrite each other:
  INPUT_FOLDER/bach/inventions/inv01.mid -> OUTPUT_FOLDER/bach__inventions__inv01.mid
  (a file directly in INPUT_FOLDER keeps its name). A file already in OUTPUT_FOLDER with
  the same name is replaced.
- The files are copied as they are (bytes unchanged). Files without notes or that cannot
  be read are skipped and listed. OUTPUT_FOLDER, if inside INPUT_FOLDER, is not searched.
"""
import argparse
import os
import shutil
import sys

import mido

DRUM_CHANNEL = 9          # MIDI channel 10, counted from 0
SEPARATOR = "__"


def note_range(path):
    """(lowest, highest) MIDI pitch of the non-drum notes of a file, None if no notes."""
    lo, hi = None, None
    for track in mido.MidiFile(path).tracks:
        for msg in track:
            if msg.type == "note_on" and msg.velocity > 0 and msg.channel != DRUM_CHANNEL:
                lo = msg.note if lo is None else min(lo, msg.note)
                hi = msg.note if hi is None else max(hi, msg.note)
    return None if lo is None else (lo, hi)


def midi_files(folder, skip):
    """Every .mid / .midi below folder (sorted), the folder `skip` excluded."""
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs
                         if os.path.abspath(os.path.join(root, d)) != skip)
        for f in sorted(files):
            if f.lower().endswith((".mid", ".midi")) and not f.startswith("._"):
                yield os.path.join(root, f)


def flat_name(path, folder):
    """Name in the output folder: the subfolder path joined with SEPARATOR."""
    rel = os.path.relpath(path, folder)
    return SEPARATOR.join(rel.split(os.sep))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Copy the MIDI files whose range is at most --max_range semitones.")
    ap.add_argument("input", help="folder searched, subfolders included")
    ap.add_argument("output", help="folder where the selected files are copied")
    ap.add_argument("--max_range", type=int, required=True,
                    help="largest range in semitones (24 = two octaves)")
    a = ap.parse_args(argv)

    src = os.path.abspath(a.input)
    dst = os.path.abspath(a.output)
    if not os.path.isdir(src):
        print(f"error: {a.input} is not a folder")
        return 1
    if a.max_range < 0:
        print("error: --max_range must be 0 or more")
        return 1
    os.makedirs(dst, exist_ok=True)

    kept, too_wide, empty, bad = 0, 0, [], []
    for path in midi_files(src, dst):
        rel = os.path.relpath(path, src)
        try:
            r = note_range(path)
        except Exception as e:                       # corrupt / not a MIDI file
            bad.append(f"{rel} ({e})")
            continue
        if r is None:
            empty.append(rel)
            continue
        width = r[1] - r[0]
        if width > a.max_range:
            too_wide += 1
            continue
        name = flat_name(path, src)
        shutil.copy2(path, os.path.join(dst, name))
        kept += 1
        print(f"  {width:3d}  {name}")

    print(f"{kept} copied (range <= {a.max_range} semitones), {too_wide} too wide, "
          f"{len(empty)} without notes, {len(bad)} unreadable")
    for rel in empty:
        print(f"  no notes: {rel}")
    for rel in bad:
        print(f"  unreadable: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
