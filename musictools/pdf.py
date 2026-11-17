"""
Pdf object: a single-part vector PDF score.

    Pdf('part.pdf').to_midi()            MIDI (scoreread --midi)
    Pdf('part.pdf').fingering()          new Pdf with the Bb trumpet fingerings written
                                         under the notes (scoreread without --midi)

The PDF reading engine is musictools/scoreread.py (font musictools/data/
TrumpetFing.ttf; scoreread.py in the project folder only keeps the old command):
to_midi() runs exactly the same code path as
    python3 scoreread.py score.pdf --midi [--instrument X] [--force]
the only difference being that the MIDI file is written to a temporary
file instead of next to the PDF.
"""
import argparse
import os
import shutil
import sys
import tempfile


# fonts for the fingering digits (scoreread default: Arial on macOS); first found is used
FONT_CANDIDATES = ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                   "/System/Library/Fonts/Helvetica.ttc",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                   "C:/Windows/Fonts/arial.ttf")


def digit_font():
    """A TTF/OTF font for the fingering digits (None if none is found)."""
    for f in FONT_CANDIDATES:
        if os.path.isfile(f):
            return f
    return None


def scoreread():
    """The scoreread module (musictools/scoreread.py)."""
    from . import scoreread as engine
    return engine


class Pdf:
    def __init__(self, path):
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        self.path = os.path.abspath(path)

    def __repr__(self):
        return f"Pdf('{self.path}')"

    def to_midi(self, instrument=None, force=False, log=None):
        """Return a Midi object read from the PDF (concert pitch, repeats expanded).

        instrument : name as accepted by scoreread --instrument (default: read from the PDF)
        force      : write the MIDI even if some bars do not add up (scoreread --force)
        log        : warnings log file (default: ~/.musikite/scoreread.log)
        """
        from .midi import Midi
        sr = scoreread()
        a = argparse.Namespace(filename=self.path, fontsize=12, font=sr.DEFAULT_FONT,
                               space=12, color="k", no_repetition=False, midi=True,
                               log=log or sr.DEFAULT_LOG,
                               force=force, instrument=instrument)
        fd, tmp = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        original = sr.write_midi

        def redirected(parts, tempo, inst, name, *args, **kw):
            return original(parts, tempo, inst, tmp, *args, **kw)

        sr.write_midi = redirected
        try:
            sr.process(a)
        except SystemExit as e:
            if e.code not in (None, 0):
                raise RuntimeError(str(e.code)) from None
        finally:
            sr.write_midi = original
        try:
            if os.path.getsize(tmp) == 0:
                raise RuntimeError("scoreread did not write a MIDI file")
            m = Midi(tmp)
        finally:
            os.remove(tmp)
        m.source = self.path
        return m

    def fingering(self, path=None, fontsize=12, font=None, space=12, color="k",
                  no_repetition=False, instrument=None, log=None):
        """New Pdf with the Bb trumpet valve fingerings written under the notes (same
        code as `python3 scoreread.py part.pdf`; trumpet parts only).

        path          : output file (default: a temporary file '<name>.noted.pdf')
        fontsize      : pt (12); font: TTF/OTF for single digits (default: Arial, or
                        another system font, see FONT_CANDIDATES)
        space         : gap in pt below the note or the bottom line (12)
        color         : 'r', 'g', 'b', 'k'
        no_repetition : repeated pairs of fingerings written once, then '-'
        instrument    : None = read from the PDF; 'trumpet' if the name is not written
        The original PDF is never changed."""
        sr = scoreread()
        font = font or digit_font()
        if font is None:
            raise RuntimeError("no font for the fingering digits found; give one with "
                               "font='/path/to/font.ttf'")
        tmpdir = tempfile.mkdtemp(prefix="musikite_fing_")
        src = os.path.join(tmpdir, os.path.basename(self.path))
        shutil.copyfile(self.path, src)                 # scoreread writes next to its input
        a = argparse.Namespace(filename=src, fontsize=float(fontsize), font=font,
                               space=float(space), color=color, no_repetition=bool(no_repetition),
                               midi=False, log=log or sr.DEFAULT_LOG,
                               force=False, instrument=instrument)
        try:
            sr.process(a)
        except SystemExit as e:
            if e.code not in (None, 0):
                raise RuntimeError(str(e.code)) from None
        out = os.path.splitext(src)[0] + ".noted.pdf"
        os.remove(src)
        if not os.path.isfile(out):
            raise RuntimeError("scoreread did not write the PDF with the fingerings")
        if path:
            path = os.path.abspath(os.path.expanduser(path))
            shutil.move(out, path)
            out = path
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass
        p = Pdf(out)
        p.source = self.path
        return p
