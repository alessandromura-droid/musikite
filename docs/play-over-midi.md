# Play over MIDI

[← Manual](README.md)

Practise **your part in a band arrangement**: the app plays all the other tracks of a MIDI
with the soundfont while you read up to three tracks on the staff — those tracks are
**silent**, you play them.

![Play over MIDI](images/play-over-midi.png)

## Making one

- **Practice > Play over MIDI** on a selected MIDI (or score): makes the exercise ♬ in
  Objects and opens it.
- **Practice > Play over MIDI** with nothing selected: an empty tab. **Drag** a MIDI, a
  PDF or a score into it (from *Objects > Material* or from the Finder), or press
  **Open…** to choose a file. A file is opened in Objects first; a PDF is read to MIDI
  (as *Convert > PDF → MIDI*, the MIDI goes into Objects too). Then the exercise is made
  and the tab shows it. On a tablet, Open… is the way (dragging between apps works only in
  split screen).
- **Generate > Exercises to do > Play over MIDI**: only makes it (e.g. for a
  [routine](routines.md)).

The exercise keeps the whole MIDI inside it, so it works even if the original file moves.

## The tab

| Control | Meaning |
|---|---|
| **Show and mute (up to 3)** | The tracks you read: shown together on one staff with one cursor, and not played. **No track is ticked by default**: choose yours. Two parts of the same instrument are numbered ("Trumpet in Bb 1", "… 2"). |
| **Tempo %** | 25–200 % of the MIDI tempo. The tempo **map** of the MIDI is followed, tempo changes included. |
| **Accomp.** | Volume of the accompaniment, %. |
| **Bars from / to** | Play only a passage. "start" / "end" = the whole piece. Bars are numbered as in the MIDI, and the staff keeps the original bar numbers. |
| **Bar N** | The bar where the cursor is. Click on the staff (when stopped) to move the cursor to the start of that bar and see its number. |
| **Show positions** | The valves (trumpet, cornet, flugelhorn, horns, tubas, euphonium) or the slide positions (trombones) under the notes of every part shown that has them. Shown only when such a part is shown; remembered per user and per instrument, together with the same box of [Read & play](read-and-play.md). |

**Start**: one count-in bar, then the cursor and the accompaniment from the first bar
chosen, or from the bar you **clicked** on the staff. A **double click** on a bar starts at
once from that bar (after the count-in bar), also while it is playing. **Start** becomes **Stop** while it plays. The **space bar** does the same as this button
(start / stop), except while you type in a field. **Click** (last button of the bar): the beat of the bar in colour,
and the metronome on / off at once, also while playing (off = no clicks after the count-in
bar, which is always heard); kept in the exercise. See [The Click button](getting-started.md#the-click-button).

Parts are shown **as written**: a trumpet in B♭ a tone above the sound, an alto sax in E♭
a major sixth above, horn in F a fifth above; bass instruments in bass clef. A track whose
name says the instrument ("Tromba 1", "Trumpet") is treated as that instrument even if the
MIDI uses another sound.

## Grade (play-along graded)

Tick **Grade** to have the part you play **graded**: **Start** records one take from the
microphone while the app plays the other tracks, and the part is graded as in
[Read & play](read-and-play.md) (its notes green / red on the staff, the grade shown and
written in the [practice diary](diary.md)). With several tracks shown, **Graded** chooses
which one is yours.

**It works only with HEADPHONES**: the microphone must not hear the band. If the sound
goes to the computer's loudspeakers a warning is shown. A graded take plays at one
constant tempo (the tempo of the first bar chosen × Tempo %: tempo changes are not
followed) and starts from the first of the bars to play.

## Done

Without *Grade*, Play over MIDI is **not graded**: a single instrument cannot be judged
reliably inside a band unless you use headphones. It is *done* when you play it **to the end** from its first bar (Stop, or a start from a
bar clicked = not done). *Done* lasts for the
session: after restarting the app it is to do again. In Objects and in routines it shows
"n/a".
