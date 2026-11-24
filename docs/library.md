# Exercise library

[← Manual](README.md)

MusiKitE contains a **library of melodies** to read: you do not browse folders, you choose
by difficulty and key, and the exercise is made for your instrument. Open it with
**Practice > Exercise from library**.

## The library tab

| Control | Meaning |
|---|---|
| **Instrument** | The instrument chosen beside the user in the toolbar: every melody is shown for it. |
| **Difficulty** | *All*, or a level from 0 (very easy) to 10, computed for your instrument (in the key without sharps or flats). |
| **Key** | *Auto*: an easy level gets a key with few sharps / flats, a hard one many (with *All*: from the difficulty of each melody). Or a written tonic (C, D♭ … B): the mode of the melody (major, minor, dorian…) is kept. |
| **To do only** | Hides the melodies you have already done. |
| **Add to Objects** | The exercise of each selected melody goes into **Objects > Exercises** (also: drag it there). |
| **Do it** | Adds the exercise and opens it at once (also: double-click a melody). |
| **Refresh** | Reads the library and your results again. |

The list opens ordered by difficulty; click a column header to sort by that column, click
it again for the opposite order (numbers as numbers, titles in natural order, keys from C to
B). Melodies **you have never done** on this instrument (in any key) are in **bold**. An
exercise that is already in Objects is selected there, not added twice.

| Column | Meaning |
|---|---|
| **Title** | The name of the melody. |
| **Difficulty** | 0-10 for your instrument ("…" while it is still being computed). |
| **Key (written)** | The key the exercise will have. |
| **Bars** | Its length. |
| **Type** | *original* (the source itself), the transformation of a transformed melody (*dorian*, *lydian*… for the modes; *inversion*, *inversion, dorian*, *retrograde*, *retrograde, dorian*, *retrograde inversion*), *crossed*, *generated*, or *user* (added by a user). |

## From melody to exercise

1. the melody is moved to the **key** chosen;
2. the whole melody is moved by octaves into the range of your instrument
   ([Settings > Instruments](settings.md#instruments) — e.g. a trumpet that does not go
   above F5);
3. a note still too high goes an octave down (too low: up), to the octave nearest to the
   previous note;
4. notes too short for your instrument become longer **at the same tempo** (the exercise is
   simplified to eighths, quarters…): low notes need time to be recognised from the
   microphone, and some instruments (sousaphone) are slow by nature;
5. the exercise is written for your instrument: transposition, clef, sound.

Nothing is left out. The same melody, instrument and key always give the same exercise.
Your results are kept per instrument and key.

**Make a variant** works on library exercises as usual (bars, Simplify, transformation):
the variant is cut from the melody and made again for your instrument; it is a new
exercise of yours, not part of the library.

## Adding your own melodies

Right-click a **MIDI** ♪ (its melody is taken: the part with the most notes, one voice)
or a Read & play / Listen & repeat exercise ♩ in Objects > **Add to library…**: only a name
is asked; key, range, difficulty… are computed by the app. Your melodies are kept in the data
folder ([Settings > Folders](settings.md)), so they are shared by every user of that folder
(a teacher adds them for the pupils), and are used like the others.

## How the library is made (developers)

The library inside the app is the folder `musikite/data/library/` (`index.json` and one small
MIDI per melody in `mid/`), made directly from a folder of MIDI files:

    python3 scripts/build_library.py FOLDER --none --modal

Sources too repetitive (low *entropy*, e.g. scales repeated again and again) are skipped.
The flags say which melodies are made from each source (at least one):

| Flag | Melodies | File (and title in the app) |
|---|---|---|
| `--none` | the source file itself, unchanged | `<source>.mid` |
| `--modal` | the melody in the 6 other church modes, same tonic | `<source> - dorian.mid`… |
| `--inversion` | mirrored around its tonic | `<source> - inversion.mid` |
| `--inversion-modal` | the mirror in the 6 other modes | `<source> - inversion, dorian.mid`… |
| `--retrograde` | backwards | `<source> - retrograde.mid` |
| `--retrograde-modal` | backwards, in the 6 other modes | `<source> - retrograde, dorian.mid`… |
| `--retrograde-inversion` | backwards and mirrored | `<source> - retrograde inversion.mid` |

`--none` puts the source files themselves in the library: use it only with files you may
distribute. `--crossings N` (the pitches of one melody on the rhythm of another) and
`--generated N` (new melodies from a statistical model of all of them) add melodies titled
"Melody <n>"; `--min-entropy X` (default 3.5, 0 = no filter) and `--seed S` complete the
options.

The script only **adds**: the melodies already in the library stay as they are (file,
title, number) and nothing is removed, so a library can be made from several folders, one
run each; a melody with the same notes and the same name as one already there is not added
again. To start from an empty library, empty the folder by hand first.

The NAME of a melody is what the user sees: in the library list and in the title of the
exercise made from it, e.g. "Jean-Baptiste Arban - Etude 13 – G major – Trumpet in Bb". See
[Command line and scripts](command-line.md).
