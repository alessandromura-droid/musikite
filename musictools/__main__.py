"""
Command line:  python3 -m musictools <command> ...   (from the project folder)

  duet   [-c CHORDS] [-g ROUNDS] [-l LEVEL] [-k KEY] [--concert] [-s SEED] [-t BPM]
         [-f PHRASE] [-x TEXTURES] [-r REPETITION]
  canon  [-c CHORDS] [-d DIFFICULTY] [-b BEATS_PER_CHORD] [-n CYCLES] [-k KEY] [--concert]
         [-s SEED] [-t BPM]           canon for two Bb trumpets (was canon_trumpets.py)
  pdf    score.pdf [--instrument NAME] [--force]
  merge  a.mid b.mid ... -o out.mid     (tracks of all the files in one MIDI; was fondi_midi.py)
  fingering  part.pdf [-o out.pdf] [--fontsize 12] [--space 12] [--color k]
         [--no_repetition] [--instrument trumpet]   Bb trumpet fingerings under the notes
  play   file.mid
  check  dependency check (what to install)
  gui    main window
  view   file.mid|file.pdf [--page] [--bpm BPM] [--instrument NAME]

common:  -o OUT.mid   --pdf OUT.pdf   --sf2 FONT.sf2   --play
"""
import argparse
import sys

from .midi import Midi
from . import duet as _duet


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m musictools",
                                 description="musictools: MIDI objects from file, PDF, merge or duet.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--out", help="output MIDI file")
    common.add_argument("--pdf", help="engrave the result to this PDF file")
    common.add_argument("--sf2", help="soundfont (.sf2) used to play")
    common.add_argument("--play", action="store_true", help="play the result (needs --sf2)")

    d = sub.add_parser("duet", parents=[common], help="random duet for two Bb trumpets")
    d.add_argument("-c", "--chords", default=_duet.DEFAULT_CHORDS)
    d.add_argument("-g", "--rounds", type=int, default=2)
    d.add_argument("-l", "--level", type=int, default=1, choices=(1, 2, 3))
    d.add_argument("-k", "--key")
    d.add_argument("--concert", action="store_true")
    d.add_argument("-s", "--seed", type=int)
    d.add_argument("-t", "--bpm", type=float, default=120)
    d.add_argument("-f", "--phrase", type=int, default=4)
    d.add_argument("-x", "--textures")
    d.add_argument("-r", "--repetition", type=float, default=0.7,
                   help="0..1, how much the motif is restated (default 0.7)")

    c = sub.add_parser("canon", parents=[common], help="canon for two Bb trumpets")
    c.add_argument("-c", "--chords", default="C F G C")
    c.add_argument("-d", "--difficulty", type=int, default=2, choices=range(1, 6))
    c.add_argument("-b", "--beats_per_chord", type=int, default=4)
    c.add_argument("-n", "--cycles", type=int, default=4)
    c.add_argument("-k", "--key")
    c.add_argument("--concert", action="store_true",
                   help="chords / key in concert pitch (default: written trumpet pitch)")
    c.add_argument("-s", "--seed", type=int)
    c.add_argument("-t", "--bpm", type=float, default=80)

    p = sub.add_parser("pdf", parents=[common], help="MIDI from a vector PDF")
    p.add_argument("filename")
    p.add_argument("--instrument")
    p.add_argument("--force", action="store_true")

    m = sub.add_parser("merge", parents=[common], help="merge MIDI files (all their tracks in one)")
    m.add_argument("files", nargs="+")
    m.add_argument("--allow_tempo_mismatch", action="store_true",
                   help="merge also files with different tempo maps (default: error)")

    f = sub.add_parser("fingering", help="PDF with the Bb trumpet fingerings under the notes")
    f.add_argument("filename")
    f.add_argument("-o", "--out", help="output PDF (default: part.noted.pdf next to the input)")
    f.add_argument("--fontsize", type=float, default=12)
    f.add_argument("--font", help="TTF/OTF font for the digits (default: Arial or a system font)")
    f.add_argument("--space", type=float, default=12)
    f.add_argument("--color", choices=("r", "g", "b", "k"), default="k")
    f.add_argument("--no_repetition", action="store_true")
    f.add_argument("--instrument", help="trumpet, if the name is not written in the PDF")

    pl = sub.add_parser("play", parents=[common], help="play a MIDI file")
    pl.add_argument("filename")

    sub.add_parser("check", help="dependency check: what is missing and how to install it")
    sub.add_parser("gui", help="main window (container of tools)")

    v = sub.add_parser("view", help="StaffView window on a MIDI or PDF file")
    v.add_argument("filename")
    v.add_argument("--page", action="store_true", help="wrapped systems instead of one line")
    v.add_argument("--bpm", type=float, help="tempo for Play (default: the score tempo)")
    v.add_argument("--instrument", help="for a PDF: instrument (default: read from the PDF)")

    a = ap.parse_args(argv)
    from .check import check
    if a.cmd == "check":
        sys.exit(0 if check()["ok"] else 1)
    if a.cmd in ("gui", "view", "play") or getattr(a, "play", False):
        r = check(verbose=False)
        if not r["ok"] or r["warnings"]:
            from .check import text
            print(text(r))
        if not r["ok"]:
            sys.exit("Install the missing dependencies above, then start again.")
    try:
        if a.cmd == "fingering":
            import os
            from .pdf import Pdf
            out = a.out or os.path.splitext(a.filename)[0] + ".noted.pdf"
            p = Pdf(a.filename).fingering(out, a.fontsize, a.font, a.space, a.color,
                                          a.no_repetition, a.instrument)
            print(f"written {p.path}")
            return
        if a.cmd == "gui":
            from .gui import main as gui_main
            gui_main()
            return
        if a.cmd == "view":
            from .staffview import StaffView
            if a.filename.lower().endswith(".pdf"):
                m = Midi.from_pdf(a.filename, a.instrument)
            else:
                m = Midi(a.filename)
            sv = StaffView(m.to_score(), layout="page" if a.page else "line")
            if a.bpm:
                sv.bpm_default = a.bpm
            sv.run()
            return
        if a.cmd == "duet":
            obj = Midi().makeduet(a.chords, a.rounds, a.level, a.key, a.concert, a.seed,
                                  a.bpm, a.phrase, a.textures, a.repetition)
        elif a.cmd == "canon":
            obj = Midi().makecanon(a.chords, a.difficulty, a.beats_per_chord, a.cycles, a.key,
                                   a.concert, a.seed, a.bpm)
        elif a.cmd == "pdf":
            obj = Midi.from_pdf(a.filename, a.instrument, a.force)
        elif a.cmd == "merge":
            obj = Midi().merge(*a.files, strict=not a.allow_tempo_mismatch)
        else:
            obj = Midi(a.filename)
            a.play = True
        print(obj)
        if a.out:
            obj.write(a.out)
        if a.pdf:
            obj.to_pdf(a.pdf)
        if a.sf2:
            obj.add_sf2(a.sf2)
        if a.play:
            obj.play()
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
