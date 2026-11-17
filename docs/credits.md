# Credits and licences

[← Manual](README.md)

## MusiKitE

© Alessandro Mura. MusiKitE is free software, released under the **GNU General Public
License, version 3** (see [`LICENSE`](../LICENSE)): you may use, study, share and modify it;
if you distribute it, modified or not, you must do so under the same licence and with the
source code.

## Soundfont

**GeneralUser GS** by S. Christian Collins — https://schristiancollins.com/generaluser.php —
included as the default soundfont. Its own licence (`musictools/data/GeneralUser-GS-LICENSE.txt`,
also inside the app) allows free use and redistribution.

Other free General MIDI soundfonts that can be chosen in
[Settings > Audio > Soundfont](settings.md#soundfont): **FluidR3_GM** (MIT licence,
~140 MB), **MuseScore_General** (MIT licence, ~200 MB).

## Fonts

| Font | Use | Licence |
|---|---|---|
| **Leland** (MuseScore) | Music symbols on screen and in the PDFs | SIL Open Font License 1.1 |
| **TrumpetFing** | Trumpet fingerings on PDFs | made for MusiKitE (licence: to be confirmed by the author) |

## Libraries

| Library | Use | Licence |
|---|---|---|
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | Window and graphics | LGPL-3.0 |
| [Verovio](https://www.verovio.org) | Music engraving | LGPL-3.0 |
| [music21](https://web.mit.edu/music21/) | Notation | BSD-3-Clause |
| [pretty_midi](https://github.com/craffel/pretty-midi) | MIDI | MIT |
| [FluidSynth](https://www.fluidsynth.org) + [pyfluidsynth](https://github.com/nwhitehead/pyfluidsynth) | Real-time sound | LGPL-2.1 / LGPL-2.1 |
| [PyMuPDF](https://pymupdf.readthedocs.io) | Reading and writing PDFs | AGPL-3.0 |
| [svglib](https://github.com/deeplook/svglib) + [ReportLab](https://www.reportlab.com/opensource/) | SVG → PDF | LGPL-3.0 / BSD |
| [sounddevice](https://python-sounddevice.readthedocs.io) + [PortAudio](https://www.portaudio.com) | Audio input / output | MIT |
| [NumPy](https://numpy.org), [SciPy](https://scipy.org), [pandas](https://pandas.pydata.org) | Signal processing, tables | BSD |
| [mido](https://mido.readthedocs.io) + [python-rtmidi](https://github.com/SpotlightKid/python-rtmidi) | MIDI keyboard | MIT |
| [PyInstaller](https://pyinstaller.org) | Building the Mac app | GPL-2.0 with bootloader exception |

Because the app contains PyMuPDF (AGPL-3.0), the app as a whole is distributed with its
complete source code, here on GitHub.

## Methods

- Chord–scale theory after Mark Levine, *The Jazz Theory Book*.
- Reading and pitch evaluation ported from the author's earlier MATLAB programs.
