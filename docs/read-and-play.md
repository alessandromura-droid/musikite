# Read & play and Listen & repeat

[← Manual](README.md)

Two exercises on short phrases, played with your instrument (microphone) or a MIDI
keyboard.

| | Read & play | Listen & repeat |
|---|---|---|
| What you see | The phrase on the staff | Nothing until the end |
| What you hear | One count-in bar and the click | The phrase, then the count-in and the click |
| What you do | Read and play it | Play it back by ear |
| Default length | 8 bars | 2 bars |
| Colour in Objects | orange ♩ | green ♩ |

![Read & play](images/read-and-play.png)

## Starting

- **Practice > Read & play** (or *Listen & repeat*): the **quick** tab. A **random
  exercise** made with the settings of the tab (bars, simplify, key, instrument) is **shown
  at once** (Listen & repeat: it is ready but stays hidden until the end of the take). The
  **key** is random, with at most the sharps / flats chosen in *Key* (*auto* = from
  Simplify: none at levels 1-2, see [Generate](generate.md#read--play--generate-random--listen--repeat--generate-random)).
  **Changing** bars, simplify, key or instrument makes it again; **New** makes another one with
  the same settings. **Start** does the exercise shown: it goes into Objects and the take
  starts; Start again does the same exercise again, until New or a change. Tempo, input,
  the Click button and positions do not change the exercise.
- **Double-click an exercise or a group** in Objects: a tab **bound** to it. Start does
  that exercise (a group: its exercises one after the other).
- In a [routine](routines.md): the routine opens each exercise in its own tab.

## A take

1. **Start**: one count-in bar of clicks (the first click of each bar is accented).
2. Play while the red cursor moves; the clicks go on.
3. At the end the take is analysed: right notes **green**, wrong ones **red**, the grade
   and the rating (*perfect* > 9, *very good* > 8, *good* > 7, *fair* > 6, else *try
   again*).
4. A **report** appears under it: the staff *Exercise* (green / red) and the staff
   *Played* (blue) with what the app heard.

Buttons: **Start** (then Pause / Resume), **Stop**, **Repeat** (the same exercises again),
**Again** (a new take of the same phrase), **Zoom + / −**, **Click** (the beat of the bar
in colour, and the audio click on / off, also during a take: see
[The Click button](getting-started.md#the-click-button)).

In a block of several exercises the next one starts by itself, after a pause long enough to
read the grade (8 s after a right take, 11 s after a wrong one).

## Options in the tab

| Option | Meaning |
|---|---|
| **Input** | *Microphone* or *MIDI keyboard*. Default in [Settings > Exercises](settings.md#exercises). |
| **Show positions** | Writes the **valves** (trumpet) or the **slide positions** (trombone) under every note, at once on the exercise shown (during a take: from the next one). The piano has none. |
| **First note** | "First note: G4" in the bar before you start (Settings > Exercises > *Show first note*; on for Listen & repeat). |
| **bpm** | Tempo of the take. |

## Microphone and headphones

- The microphone must hear your instrument **and** the clicks: the clicks are used to align
  the recording with the score. With headphones the app uses the delay measured by the
  audio device instead.
- Check the microphone in [Settings > Audio](settings.md#audio) (*Test microphone*: a
  level meter).
- A take writes to the Log its length, the latency and the peak level; a silent take is
  reported.

## MIDI keyboard

Choose *MIDI keyboard* as Input (and the keyboard in Settings > Audio > MIDI input).

- **Read & play** expects the **written** note (what you read: a trumpet part in B♭ is
  checked as written).
- **Listen & repeat** expects the note **heard** (concert pitch).
- The keys sound with the soundfont when *Keyboard sound* is on (Settings > Audio); turn it
  off for keyboards with their own sound.
- No MIDI keyboard? The **computer keyboard** works too (`a w s e d f t g y h u j k o l p ò`
  = C … E, `z` / `x` octave): see [Free player > Computer keyboard](free-player.md#computer-keyboard).

## Make a variant

In a tab bound to **one** exercise cut from a MIDI or a score, the panel **Make a variant**
makes a **new** exercise from the same music: bars from / to, part, simplify, instrument,
transformation, bpm.

- **Save as new**: adds the variant to Objects without results.
- **Start changed** (or Start with changes in the panel): adds it and the take is its first
  result.
- The original exercise is **never changed**. A different bpm also makes a new exercise,
  because grades at different tempi are not comparable.

Random exercises (made by the app) and exercises generated without the MIDI have no
*Make a variant* panel: there is no source to cut again.

## How a take is graded

See [Grading > Read & play](grading.md#read--play-and-listen--repeat). The microphone is
listened to according to the **instrument of the exercise**: wind instruments by the sound
held in each note's window, the **piano** by the attack of every note (a chord = wrong).
Play a piano exercise ("C (piano)"): an exercise for B♭ trumpet played on the piano is a
tone off. In short: each
note is right only if **its own pitch** is heard in its window (the window may shift up to
a quarter of a beat to allow for timing). The grade is 10 × the fraction of notes
recognised; the take counts as right above 60 %.

## Results

Every take is an attempt on its exercise, for the current user. The exercise shows the
**best grade of today**; the [practice diary](diary.md) keeps every attempt and the study
time.
