# Drills

[← Manual](README.md)

Drills are exercises **made by the app**: *Practice > Long tones*, *Scales & arpeggios*,
*Lip slurs*, *Rhythm reading*, *Chord arpeggios*.

Common to all of them:

- The **settings are in the tab** and remembered per user.
- **Start** makes **one new exercise** and records a take: one count-in bar, the clicks,
  the cursor, then the notes coloured green / red and the grade.
- **Again** repeats the **same** exercise (the best attempt of the day counts).
- **Keep** puts the exercise in Objects at once (it goes there anyway after its first
  take); its takes then go into it.
- Every exercise made with Start becomes an exercise ◆ in Objects with its attempts;
  double-click it to do it again with the same settings.
- **View** on a drill shows a summary, the staff of the last attempt, the cents chart (long
  tones) and the table of the attempts.

![A drill tab](images/drill.png)

## Long tones

Long notes to hold in tune (microphone).

| Option | Meaning |
|---|---|
| **Lowest / Highest** | Range (written pitch; default from [Settings > Instruments](settings.md#instruments)). |
| **Notes per exercise** | 1–12 notes chosen at random in the range. |
| **Beats each** | Length of each note. |
| **Rest beats** | Rest between notes (every note starts on a bar line). |
| **bpm**, **Click** | |

Under the staff a **chart** shows the pitch of each note in **cents** (−150 … +150), with
dashed lines at ±50 cents: points beyond them are red. A note never within 50 cents is
reported as "out of tune, +100 c" instead of "not heard". Grading: see
[Grading > Long tones](grading.md#long-tones).

## Scales & arpeggios

| Option | Meaning |
|---|---|
| **Keys** | Check list of the **written** keys. |
| **Types** | major; natural, harmonic, melodic minor (melodic down = natural); chromatic; major, minor, dominant 7th, diminished 7th arpeggios. |
| **Octaves** | 1 or 2. |
| **Pattern** | `straight`, `thirds`, `groups of 3`, `groups of 4`, `turns`, `arpeggio & scale` (7-note scales only), or `varied` (one at random each time). |
| **Rhythm** | `half`, `quarter`, `eighth`, or `varied`: rhythmic cells, triplets, 3/4, 6/8, quarters up and eighths down, 4/4 → 3/4, alternating 4/4 + 3/4. The click follows the time-signature changes. |
| **Instrument** | B♭ trumpet or C piano. |
| **Lowest / Highest** | A scale that does not fit is not used (never folded). |
| **Input** | Microphone or MIDI keyboard (the note **read**). |
| **bpm**, **Click** | |

Graded on the **order** of the notes only (timing is free): see
[Grading](grading.md#scales-and-lip-slurs).

## Lip slurs

One **module** (a figure on the open partials + a rhythm) repeated identically on every
valve combination chosen, in the classic order 0, 2, 1, 12, 23, 13, 123, with a rest after
each.

| Option | Meaning |
|---|---|
| **Valves** | Which combinations (check list). |
| **Level** | 1 2nd–3rd partial · 2 2nd–3rd–4th · 3 up to the 5th · 4 skips (2–4, 3–5) · 5 up to the 6th · 6 up to the 8th (the 7th, out of tune, is skipped). A level also uses the figures of the lower ones, its own most often. |
| **Note value** | Basic note value; rhythms: even, long, long top note (tied over the bar line), long with a short end. |
| **Highest** | A figure that goes above it is not used. |
| **bpm**, **Click** | |

The title says level, figure and rhythm. Graded on the order of the notes, like scales; a
note tied over the bar line counts as one.

## Rhythm reading

A rhythm on one note (B4, the middle line); you clap it, tap the space bar or play any key.

| Option | Meaning |
|---|---|
| **Difficulty** | 1 whole/half · 2 + quarters · 3 + eighths · 4 + rests and dots · 5 + sixteenths · 6 + triplets · 7 + syncopation |
| **Bars**, **Time** (4/4, 3/4, 2/4, 6/8), **bpm** | |
| **Input** | *Clap* (microphone), *Key* (space bar), *MIDI keyboard*. |
| **Metronome** | *High click (filtered)*: a pure high tone removed before the claps are searched, so the click is never mistaken for a clap · *Normal click* · *Count-in only* · *No metronome*. |
| **Volume** | Volume of the clicks. |

The grading is **lenient** with soft claps; see [Grading](grading.md#rhythm-reading).

## Chord arpeggios

Improvise on a chord progression: every chord **sounds once** on the piano, its **name**
appears big in the tab, and you have some clicks to arpeggiate it.

| Option | Meaning |
|---|---|
| **Progression** | From the catalogue: I-vi-IV-V, ii-V-I, ii-V-i minor, I-vi-ii-V, blues, minor blues, jazz blues, rhythm changes, Autumn Leaves cycle, So What, Coltrane changes… |
| **Key (written)** | The key you read in. |
| **Instrument** | C (piano) or B♭ (trumpet): chord names are written for it. |
| **Clicks a chord** | 4, 8 or 12. |
| **Times** | The progression 1–4 times. |
| **Show the notes** | Easy version: the chord tones and the right **tensions** of each chord are shown under its name, and the staff with the chords is visible. |
| **Random** | Progression, key and clicks drawn at random at every new exercise. The instrument is never random. |
| **bpm**, **Click** | |

The exercise **loops**: after each take the next one starts by itself (the same exercise,
or a new random one with *Random*), until **Stop**. The grade of the take just done stays
visible during the next.

The piano plays low (root in octave 2, chord tones in the octave below middle C);
**headphones are recommended**, otherwise the microphone hears the piano. Grading: see
[Grading > Chord arpeggios](grading.md#chord-arpeggios).
