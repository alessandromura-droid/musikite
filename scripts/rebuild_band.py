#!/usr/bin/env python3
"""
Band parts: PDF -> MIDI for every part, then ONE merged MIDI per song (owner, 2026-11-08:
"the same thing as before, but with right results").

    python3 scripts/rebuild_band.py ".../banda/parti" --dry-run     # only shows what it would do
    python3 scripts/rebuild_band.py ".../banda/parti"

FOLDER holds one subfolder per instrument (Clarinetto, Tromba, Tuba …) with the PDF parts.
  1. every PDF of the subfolders is read again into "<name>.from_pdf.mid" next to it (the
     package's PDF reader: now with every TEMPO CHANGE of the part; as `scoreread.py --midi
     --force`: bars that do not add up are written anyway and listed in the log);
  2. the parts are grouped by SONG: the file name before " - " ("Misirlou - Tuba" ->
     "Misirlou"), else the name without the instrument and the part numbers ("Astarbene
     Clarinet in Bb 2 + 3" -> "Astarbene");
  3. every song with two parts or more is merged into  FOLDER/<song> - all parts.mid
     (musictools.midi.merge, strict: parts with different tempos -> the song is NOT merged
     and the difference is printed).
Nothing else is changed or deleted (old merged files stay where they are).
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

MERGED_SUFFIX = " - all parts.mid"


def song_of(path, words):
    """Song of a part file: the name before ' - ', else the name without instrument words
    and part numbers."""
    name = os.path.basename(path)
    name = re.sub(r"(\.from_pdf)?\.(pdf|mid|midi)$", "", name, flags=re.I)
    if " - " in name:
        return name.split(" - ")[0].strip()
    low = name
    for w in sorted(words, key=len, reverse=True):
        low = re.sub(re.escape(w), " ", low, flags=re.I)
    low = re.sub(r"\b(in\s+(si\s*b|sib|bb|eb|f|c))\b", " ", low, flags=re.I)
    low = re.sub(r"[\d+_]+", " ", low)
    return re.sub(r"\s+", " ", low).strip(" -") or name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folder")
    ap.add_argument("--dry-run", action="store_true", help="only show what would be done")
    a = ap.parse_args(argv)
    from musictools.pdf import scoreread
    from musictools.midi import merge
    sr = scoreread()
    words = [w for spec in sr.INSTRUMENTS.values() for w in spec[0]]
    words += ["Clarinetto", "Clarinet", "Sax", "Saxophone", "Drum", "Drums", "Rullante",
              "Batteria", "Banjo"]

    pdfs = sorted(os.path.join(d, f) for d in sorted(os.listdir(a.folder))
                  if os.path.isdir(os.path.join(a.folder, d))
                  for f in os.listdir(os.path.join(a.folder, d)) if f.lower().endswith(".pdf"))
    pdfs = [os.path.join(a.folder, p) for p in pdfs]

    # 1. PDF -> MIDI
    mids, failed = [], []
    for p in pdfs:
        out = os.path.splitext(p)[0] + ".from_pdf.mid"
        rel = os.path.relpath(p, a.folder)
        if a.dry_run:
            print(f"read   {rel}")
            mids.append(out)
            continue
        args = argparse.Namespace(filename=p, fontsize=12, font=sr.DEFAULT_FONT, space=12,
                                  color="k", no_repetition=False, midi=True,
                                  log=sr.DEFAULT_LOG, force=True, instrument=None)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                sr.process(args)
            last = [ln for ln in buf.getvalue().splitlines() if "->" in ln]
            nw = sum(1 for ln in buf.getvalue().splitlines() if ln.startswith("warning"))
            print(f"read   {rel}: " + (last[-1].split(" -> ")[0] if last else "done")
                  + (f"  [{nw} warnings]" if nw else ""))
            mids.append(out)
        except SystemExit as e:
            failed.append(rel)
            print(f"FAILED {rel}: {e}")
        except Exception as e:
            failed.append(rel)
            print(f"FAILED {rel}: {type(e).__name__}: {e}")

    # 2. songs
    songs = {}
    for m in mids:
        songs.setdefault(song_of(m, words).lower(), []).append(m)

    # 3. merge
    print()
    merged, refused = 0, []
    for key in sorted(songs):
        files = songs[key]
        title = song_of(files[0], words)
        out = os.path.join(a.folder, title + MERGED_SUFFIX)
        parts = ", ".join(os.path.basename(os.path.dirname(f)) for f in files)
        if len(files) < 2:
            print(f"single {title}: only {parts}")
            continue
        if a.dry_run:
            print(f"merge  {title}: {len(files)} parts ({parts}) -> {os.path.basename(out)}")
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                m = merge(*files, strict=True)
                m.write(out)
            tm = ", ".join(f"{b:g}" for _, b in m.tempo_map())
            print(f"merged {title}: {len(files)} parts, tempo {tm} -> {os.path.basename(out)}")
            merged += 1
        except ValueError as e:
            refused.append(title)
            print(f"NOT MERGED {title}: {e}")
    print(f"\n{len(pdfs)} PDF, {len(failed)} failed; {merged} songs merged"
          + (f", {len(refused)} not merged (different tempos): " + ", ".join(refused)
             if refused else ""))
    return 1 if failed or refused else 0


if __name__ == "__main__":
    sys.exit(main())
