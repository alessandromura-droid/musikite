# MusiKitE manual

MusiKitE is a practice companion for musicians, made first of all for **wind instruments**
(brass, woodwinds, the band) and the **piano**. It generates exercises, listens to you through the
microphone (or reads a MIDI keyboard), grades every take, keeps a practice diary and turns
PDF parts and MIDI files into material to study.

This manual describes the Mac application and the Python package it is built on. It is
written in Markdown: every page can be read on GitHub, inside the app (**Help > Manual**,
F1) and edited with any text editor.

> Screenshots are referenced as `images/<name>.png`; the files in `docs/images/` are added
> by the author.

## Contents

| Page | What it covers |
|---|---|
| [Installation](installation.md) | The Mac app (.dmg), running from the source code, first start, microphone permission, soundfont |
| [Getting started](getting-started.md) | The main window, users, objects, tabs, **Play** (listen) versus **Start** (practise), workspaces, the Log |
| [Objects and files](objects.md) | MIDI, scores, PDFs, exercises, groups, routines; what can become what; file formats (.mid, .pdf, .mke, .mkr) |
| [Generate](generate.md) | Duets, canons, exercises to do, routines |
| [Convert](convert.md) | PDF → MIDI, PDF → trumpet fingerings, MIDI → score / PDF, merge, transpose |
| [Read & play and Listen & repeat](read-and-play.md) | Reading and repeating phrases with the microphone or a MIDI keyboard; variants; how takes are graded |
| [Drills](drills.md) | Long tones, scales & arpeggios, lip slurs, rhythm reading, chord arpeggios |
| [Exercise library](library.md) | Melodies made into exercises for your instrument, by difficulty and key; adding your own |
| [Ear training and reading quizzes](ear-training.md) | Intervals, interval reading, chord qualities, scales and modes, scale degrees, cadences, fingerings & note names |
| [Play over MIDI](play-over-midi.md) | Reading your part while the app plays the rest of the band |
| [Free player, recording and piano roll](free-player.md) | Playing a MIDI keyboard with the soundfont, recording takes, editing notes |
| [Routines](routines.md) | Daily sequences of exercises, auto-advance, ◀ ▶ |
| [Practice diary](diary.md) | Grades and study time day by day: calendar, candles, trend, weekly time |
| [Settings](settings.md) | Every page of the Settings window |
| [Grading](grading.md) | How every exercise type computes its grade |
| [Command line and scripts](command-line.md) | `python3 -m musikite …` and the scripts in `scripts/` |
| [Building the Mac app](building.md) | `scripts/build_mac_app.sh` |
| [Troubleshooting](troubleshooting.md) | Dependency check, logs, no sound, no microphone, Gatekeeper |
| [Credits and licences](credits.md) | Licence of MusiKitE, the soundfont, the fonts and the libraries |

## The ideas in one minute

- **Everything is an object.** MIDI files, scores, PDFs, exercises and routines appear in
  the **Objects** panel on the left. Tools take the selected objects and make new ones.
- **Play means listen, Start means practise.** *Play* exists only in the Objects panel and
  plays an object with the red cursor moving on the staff. *Start* exists only in exercises:
  you get the count-in and the click, the music is **not** played, you play it.
- **An exercise keeps its results.** There is no separate "result" object: every attempt is
  stored in the exercise itself, per user. The grade of the day is your **best** attempt of
  the day (the day starts at 04:00).
- **To do = not done today.** Exercises not yet done today are shown in bold on grey.
- **Every user is separate.** A teacher can create one user per pupil: settings, results
  and workspace are kept apart.
