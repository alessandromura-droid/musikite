# Grading

[← Manual](README.md)

Every grade is between **0 and 10**. An exercise shows the **best grade of today**; the
[practice diary](diary.md) keeps every attempt.

## Read & play and Listen & repeat

**Microphone.** The recording is aligned with the score using the first click heard (if
the clicks are not heard, e.g. with headphones, the delay of the audio device is used).
Then, for every note:

1. the window of the note (its start and length after the count-in bar) is analysed with a
   frequency spectrum;
2. the note is **right** only if **its own pitch** is found in the window — a neighbouring
   note played again does not count;
3. the window may move up to a quarter of a beat (at most half the note) earlier or later,
   to allow for timing.

The steps above are for **wind instruments** (trumpet, trombone…), whose sound stays while
you blow. The **piano** (and later guitar, harp, mallets) is heard differently, because
its sound starts strong and dies away; frame by frame its pitch wobbles and jumps to the
octave as it decays, which made one note look like two. **The piano is meant to be played
on a MIDI keyboard**: from the microphone the recognition below is rough.

1. every note is found by its **attack** — the moment the sound suddenly grows, compared
   with the rest of the same take, so the distance of the microphone and the kind of
   piano (acoustic, electric, digital) do not matter;
2. its pitch is read **just after the attack** (the hammer noise skipped), from all its
   harmonics together; the decay is never split into a second note, and striking the same
   key again is a new note;
3. the notes found are paired one to one with the written ones, as with a MIDI keyboard;
4. **a chord is wrong**: if other notes (not harmonics of the note, nor the click) sound
   at its attack, the note is never right — the exercises are always one note at a time.

**MIDI keyboard.** Expected and played notes are paired one to one: same pitch, starts at
most half a beat apart, closest pairs first; every played note is used once.

**Grade** = 10 × fraction of notes recognised. Rating: > 9 *perfect*, > 8 *very good*,
> 7 *good*, > 6 *fair* (a right take), else *try again*.

## Long tones

For every note the pitch is measured many times per second, within ±150 cents of the
expected note. Then:

- **held** = fraction of the note's time within **50 cents** of the right pitch;
- **stability** = how much the pitch wobbles (standard deviation, in cents);
- **intonation** = how far the mean pitch is from the right one.

```
note score = held × stability factor × intonation factor
stability factor  = 1 up to 8 c of wobble, then down to 0.3 at 35 c
intonation factor = 1 up to 10 c off, then down to 0.5 at 40 c
grade = 10 × mean of the note scores
```

A note never within 50 cents scores 0. Example: two notes held 95 % and 98 % but with a
wobble of ±14 cents (stability factor ≈ 0.84) and one wrong note give about 5.2, not 6.4.
The text under the staff shows for every note *held %, mean cents ± wobble*.

## Scales and lip slurs

Only the **order** of the notes counts (timing is free). What you played is transcribed
(repeated notes in a row merged) and aligned with the expected sequence; the grade is
10 × the fraction of expected notes found in order.

## Rhythm reading

Claps (or taps / keys) are paired one to one with the written notes, closest first, at most
a quarter of a beat apart. Every extra clap (one not paired with a note) costs half a
note. The take is analysed again at higher sensitivities, so soft claps are not lost, but a
higher sensitivity is kept only if it adds notes **without** adding extra claps: noise never
raises a grade. The mean timing error in milliseconds is shown.

## Chord arpeggios

For every chord, the notes that start during it (half a beat early still belongs to it):

- **right** = a chord tone or a tension that fits the chord **in its context** (key,
  previous and next chord);
- **wrong** = an avoid note, a note of another scale, a chromatic note.

```
chord score = coverage × accuracy
coverage = different right notes / notes of the chord (max 1)
accuracy = right notes / notes played
grade = 10 × mean of the chord scores
```

Nothing played scores 0. A chord is green from 0.6. With the microphone, the exact notes the
piano is playing are not counted (they could be the loudspeaker).

## Blocks of questions

Intervals, interval reading, chord qualities, fingerings & note names:

```
points of a right answer = base (100)
                         × 1.2 for harmonic intervals (1.0 melodic)
                         × time factor (1 up to 3 s, then down to 0.5 at 15 s)
                         × 0.8 for every replay
wrong answer = 0
grade = 10 × points / (questions × maximum points)
```

The answer time starts when the question has finished sounding. All the values can be
changed in [Settings > Exercises](settings.md#exercises).
