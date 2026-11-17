# Play over MIDI

[← Manual](README.md)

Practise **your part in a band arrangement**: the app plays all the other tracks of a MIDI
with the soundfont while you read up to three tracks on the staff — those tracks are
**silent**, you play them.

![Play over MIDI](images/play-over-midi.png)

## Making one

- **Practice > Play over MIDI** on a selected MIDI (or score): makes the exercise ♬ in
  Objects and opens it.
- **Generate > Exercises to do > Play over MIDI**: only makes it (e.g. for a
  [routine](routines.md)).

The exercise keeps the whole MIDI inside it, so it works even if the original file moves.

## The tab

| Control | Meaning |
|---|---|
| **Show and mute (up to 3)** | The tracks you read: shown together on one staff with one cursor, and not played. **No track is ticked by default**: choose yours. Two parts of the same instrument are numbered ("Trumpet in Bb 1", "… 2"). |
| **Tempo %** | 25–200 % of the MIDI tempo. The tempo **map** of the MIDI is followed, tempo changes included. |
| **Accomp.** | Volume of the accompaniment, %. |
| **Click** | Metronome on / off. |
| **Bars from / to** | Play only a passage. "start" / "end" = the whole piece. Bars are numbered as in the MIDI, and the staff keeps the original bar numbers. |
| **Bar N** | The bar where the cursor is. Click on the staff (when stopped) to move the cursor and see the bar number. |

**Start**: one count-in bar, then the cursor and the accompaniment from the first bar
chosen. **Stop** stops.

Parts are shown **as written**: a trumpet in B♭ a tone above the sound, an alto sax in E♭
a major sixth above, horn in F a fifth above; bass instruments in bass clef. A track whose
name says the instrument ("Tromba 1", "Trumpet") is treated as that instrument even if the
MIDI uses another sound.

## No grade

Play over MIDI is **not graded**: a single instrument cannot be judged reliably inside a
band. It is *done* when you play it **to the end** (Stop = not done). *Done* lasts for the
session: after restarting the app it is to do again. In Objects and in routines it shows
"n/a".
