# Objects and files

[← Manual](README.md)

## The object types

| Object | What it holds | Made by |
|---|---|---|
| **MIDI** ♪ | Notes at concert pitch, tracks with their instruments, tempo map (tempo changes), time and key signatures | File > Open (.mid), Generate (duet, canon), Convert (PDF → MIDI, merge, transpose), Free player recordings |
| **Score** ♫ | Notation: bars, note values, key signature per part, written pitch | Convert > MIDI → Score, File > Open (MusicXML) |
| **PDF** ▤ | A PDF file (band parts, scores) | File > Open (.pdf), Convert > MIDI / Score → PDF, PDF → trumpet fingerings |
| **Recording** ≈ | A performance: notes with timing and intonation (cents) | (code) |
| **Exercise** ♩ | A short phrase to read (Read & play, orange) or repeat (Listen & repeat, green), with its instrument, tempo and results | Generate > Exercises to do, Practice > Read & play / Listen & repeat |
| **Group** ▦ | Several exercises together (expand it to see each one) | Generate > Exercises to do |
| **Exercise** ◆ | A drill or a quiz made by the app (long tones, scales, lip slurs, rhythm, chord arpeggios, intervals, interval reading, chord qualities, scales by ear, scale degrees, cadences, fingerings) with its results | Practice (Start), Generate > Exercises to do |
| **Play over MIDI** ♬ | A MIDI with the tracks you read | Practice / Generate > Play over MIDI |
| **Routine** ↻ | An ordered list of exercises for the day | Generate > Make a routine |

In the Exercises list every kind of exercise has **its own colour** (the same as in the
[practice diary](diary.md)). An exercise **to do** (not done today) is in bold, in a dark
shade of its colour on a light grey background; once done it is in a light shade of the
same colour on the dark background, with today's grade after the name in light blue.
Exercises of every instrument are drawn the same way.

Right-click a MIDI ♪ or a Read & play / Listen & repeat exercise ♩ > **Add to library…** puts
its melody in the [exercise library](library.md) (only a name is asked).

## One click: Preview; double click: open

**One click** on an object shows it in the tab **Preview**: the staff of a MIDI, score or
exercise ♩ (also an exercise inside a group), the pages of a PDF, the summary of an exercise
◆, and for a group ▦ / ◆, a routine ↻ or Play over MIDI ♬ a text about it (type, number of
exercises, instrument, where they come from, difficulty, how many are done today and
today's mean grade). The arrow keys in the lists show each object in turn. There is only
ever one Preview tab: it changes with the object clicked and disappears as soon as another
tab comes to the front. When you click another object the Preview first turns empty,
then shows the new one. While an exercise or a recording is going on, a click does not
take its place.

**Double click** opens the object: an exercise is done in its own tab, any other object
opens in a tab of its own.

## What can become what

The app offers only these conversions, one step at a time:

```
PDF ──Convert > PDF → MIDI──▶ MIDI ──Convert > MIDI → Score──▶ Score
 │                              │  ╲                              │
 │                              │   ╲─Convert > MIDI / Score → PDF┤
 └─Convert > PDF → fingerings   │                                 │
   (new PDF)                    └──Generate > Exercises to do ◀───┘
                                          │
                                   exercises ♩ ▦ ◆ ──▶ Practice (double-click)
                                          │
                                   Generate > Make a routine ──▶ routine ↻
```

- A MIDI or a score is **never practised directly**: first make exercises from it
  (Generate > Exercises to do), or use [Play over MIDI](play-over-midi.md).
- **Exercises stay exercises**: they are saved only as exercise files, never converted back
  to MIDI, score or PDF (they can still be printed).

## Note names on the staff

A MIDI file has only pitches, not their names: on every staff MusiKitE names the notes
after the key signature of that staff (for a transposing instrument, its written key).
In F# major you read A# and E#, not B♭ and F; in G minor the leading tone is F#; notes
outside the key get one sharp in sharp keys and one flat in flat keys, never a double
sharp or flat.

## Playing from a bar

**Play** (Objects panel) plays an object from the start. **Click a bar** on its staff (or on
the bar numbers of the piano roll): the next Play begins at that bar, after one count-in bar
of clicks. **Double-click a bar**: it plays from there at once (one count-in bar first),
also while it is already playing. Stop, Esc or the space bar stop it. The loop of
View > Loop playback applies only when it starts from the beginning.

## Editing a MIDI

A MIDI opens on the staff; the **Piano roll** button in its tab switches to the
[piano roll](free-player.md#piano-roll), where notes are moved, drawn, deleted and
quantised. The edits go into the MIDI object (Play plays them, Save writes them). For clean
notation afterwards: Convert > MIDI → Score.

## Files

| Extension | Content | Notes |
|---|---|---|
| `.mid` | MIDI | Standard MIDI file, concert pitch |
| `.pdf` | PDF | Vector PDFs (made by MuseScore, Sibelius, Finale, Dorico, MusiKitE…) can be read back into MIDI |
| `.musicxml` / `.xml` | Score | Opened as a Score object |
| `.mke` | One MusiKitE exercise, group or Play over MIDI | A small ZIP archive with JSON inside |
| `.mkr` | A routine | A ZIP archive with JSON inside |
| `.json` | Workspace, or exercises in the old format | Still read |
| `.wav` | Audio export of a MIDI / score | Save as… only |

**Save as…** proposes the right extension for each type. With several objects selected,
*Save as…* asks for one folder and saves each object there with its own name; if files with
the same names exist, one question decides for all (overwrite / skip / cancel).

A PDF made by a tool (e.g. with fingerings) lives in a temporary folder until you save it:
*Save* then asks where.

## Exercises remember where they come from

An exercise cut from a MIDI or a score keeps a copy of that MIDI and how it was cut (bars,
part, simplification, instrument, transformation, tempo). That is what makes
[Make a variant](read-and-play.md#make-a-variant) possible. Untick **Include the MIDI** when
generating if you want exercises without any trace of the source (for example to share
them).

## Print

*File > Print…* (or right-click > Print…) works on MIDI, scores, exercises and PDFs: the
object is engraved to a PDF and the system print dialog opens.
