# Convert

[← Manual](README.md)

*Convert* turns the **selected objects** into new ones. The original is never changed.

## PDF → MIDI

Reads a **vector PDF** (a part or a score exported by a notation program: MuseScore,
Sibelius, Finale, Dorico, MusiKitE) and writes the MIDI of what is written.

- Notes, rests, ties, dots, triplets, accidentals, key and time signatures, clefs.
- **Repeats and endings** are played out (the MIDI lasts as long as the performance).
- **Multi-bar rests**: a number over a short bar with a vertical stroke at each end counts
  as that many bars.
- **Tempo marks** (`q = 100`, `♩ = 190`) anywhere in the part: every change is written in
  the MIDI where it happens.
- **Several staves of the same instrument** in a system (e.g. a duet score) become
  separate tracks.

| Option | Meaning |
|---|---|
| **Instrument** | `auto` (read from the name at the start of the part: "Trumpet", "Tromba"…) or chosen from the list. |
| **Force** | Read it even when the instrument is not recognised. |

Scanned PDFs (images) cannot be read: there is no text or vector inside.

Problems found while reading are written to `~/.musikite/scoreread.log`.

## PDF → trumpet fingerings

Writes the **valves** (0, 1, 2, 12, 13, 23, 123) under every note of the trumpet parts of
the PDF, on a white background so they can be read over other markings. Result: a new PDF.

| Option | Meaning |
|---|---|
| **Font size**, **Gap** | Size of the digits and distance from the staff. |
| **Colour** | black, red, green, blue. |
| **No repetitions** | A fingering is not written again on the same repeated note. |
| **Instrument** | `auto` or `trumpet` (if the part name is missing). |
| **Save next to the original** | Each new PDF is written at once next to its original as `<name>.noted.pdf` (an older one is replaced). Handy for many PDFs at once. |

The same from the command line: `python3 -m musictools fingering part.pdf`
(see [Command line](command-line.md)).

## MIDI → Score

Builds the notation of a MIDI: note values quantised to sixteenths and eighth-note
triplets, a key signature for each part (estimated from the notes if the MIDI has none),
transposing instruments written as they are read. Quantise the MIDI first in the
[piano roll](free-player.md#piano-roll) if it was played by hand.

## MIDI / Score → PDF

Engraves the selected MIDI or score into a PDF (Verovio, font Leland). The PDF can be read
back with *PDF → MIDI*. Option: **Title**.

## Merge MIDI

All the selected MIDI objects in **one** MIDI, one track each. The **tempo map of the first**
is kept (every tempo change). MIDI files with different tempos are refused, because the
merged result would be wrong against a metronome.

## Transpose

A **new** MIDI or score *k* semitones up or down. Drum tracks do not move; key signatures
follow.

## Print

Not a conversion but close to it: *File > Print…* engraves MIDI, scores and exercises and
opens the system print dialog.
