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

## Install from the source code (macOS)

```
git clone https://github.com/alessandromura-droid/musikite.git
cd musikite && ./install.sh
```

`install.sh` asks before every step: conda (it offers to install Miniforge if there is
none), FluidSynth and PortAudio from conda-forge, the Python packages, MusiKitE itself
(`pip install -e .`, which makes the command `musikite`), the manual page, the dependency
check, the PATH line in `~/.zshrc` if needed; at the end it lists commands to try:

```
musikite gui
musikite --help
man musikite
```

## Manual

The full manual is in [`docs/`](docs/README.md), and inside the app: **Help > Manual** (F1).

## Licence

MusiKitE is free software under the **GNU General Public License v3.0** — see
[`LICENSE`](LICENSE). The soundfont *GeneralUser GS* is by S. Christian Collins, under its
own licence (`musikite/data/GeneralUser-GS-LICENSE.txt`). Fonts and libraries: see
[Credits](docs/credits.md).
