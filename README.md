# MusiKitE

A practice companion for musicians — first of all **wind instruments** (trumpet, trombone)
and the **piano**. MusiKitE generates exercises, listens to you through the microphone (or
reads a MIDI keyboard), grades every take, keeps a practice diary, and turns PDF parts and
MIDI files into material to study.

- **Read & play / Listen & repeat**: read or repeat short phrases; every note checked.
- **Drills**: long tones with a cents chart, scales & arpeggios with patterns and rhythms,
  lip slurs, rhythm reading, chord arpeggios over progressions.
- **Ear training**: intervals, interval reading, chord qualities, fingerings & note names.
- **Play over MIDI**: read your part while the app plays the rest of the band.
- **Generate**: duets and canons for two trumpets on any chord progression; exercises cut
  from your MIDI files and scores.
- **Convert**: vector PDF parts → MIDI (repeats, tempo changes, multi-bar rests); trumpet
  fingerings written on PDFs; MIDI → notation → PDF.
- **Routines** and a **practice diary** with grades and study time day by day.

## Download

macOS: get `MusiKitE-arm64.dmg` (Apple silicon) or `MusiKitE-intel.dmg` (Intel) from the
**Releases** page. The app is not signed: open it the first time with right-click > Open.
Details in [Installation](docs/installation.md).

## Run from the source code

```
conda install -c conda-forge fluidsynth "portaudio>=19.7"
python3 -m pip install -r requirements-macbook.txt
python3 -m musictools check
python3 -m musictools gui
```

## Manual

The full manual is in [`docs/`](docs/README.md), and inside the app: **Help > Manual** (F1).

## Licence

MusiKitE is free software under the **GNU General Public License v3.0** — see
[`LICENSE`](LICENSE). The soundfont *GeneralUser GS* is by S. Christian Collins, under its
own licence (`musictools/data/GeneralUser-GS-LICENSE.txt`). Fonts and libraries: see
[Credits](docs/credits.md).
