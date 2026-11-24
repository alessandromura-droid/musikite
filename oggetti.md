# MusiKitE – objects and what they can become

Rule: the interface offers only these conversions (no shortcut that skips a step).
In particular a MIDI is never practised directly: first it becomes exercises.

Objects panel = TWO lists, one above the other (own scrolling, movable divider, position
saved): MATERIAL (Midi, Score, Pdf, Notes) and EXERCISES (♩ ▦ ◆ ↻). There is NO result
object: an exercise that has been done is an exercise with results (attempts per user);
its name shows the grade (best of today, else the last). TO DO = never done today by the
current user (the day starts at 04:00): bold, a DARK shade of the colour of its kind on a
light grey background; once done today a LIGHT shade of the same colour on the dark
background of the app, the grade after the name in light sky blue (2026-11-19).

## Midi ♪ (blue)
Origin: MIDI file opened, duet generated, result of PDF → MIDI, Free player recording (Save).

| Becomes | How |
|---|---|
| Edited Midi (same object) | View: staff, button "Piano roll" → piano roll: hand, pencil, eraser, Quantize… (grid, triplets, strength), undo |
| Score | Convert > MIDI → Score |
| Midi (all tracks together) | Convert > Merge MIDI (several selected) |
| Midi transposed | Convert > Transpose (a new object) |
| Midi (duet from its melody) | Generate > Duet from a melody: the melody (track with the most notes, or chosen) + a second voice — harmony, canon, accompaniment (a new object) |
| Pdf | Convert > MIDI / Score → PDF |
| ExerciseSet | Generate > Exercises to do > Read & play / Listen & repeat from MIDI / score (also right click); own options per type: difficulty 1-5, instrument Bb / C / trumpet in C, D, Eb, E, F, A (transposition), remove empty bars (default on), transformation; polyphony only for Listen & repeat |
| Play over MIDI ♬ | Practice > Play over MIDI (made and opened) or Generate > Exercises to do > Play over MIDI (also right click) |
| Print | File > Print… / right click (through a temporary PDF) |
| File .mid / .pdf / .wav | Save / Save as… |

## Score ♫ (teal)
Origin: MusicXML file opened, MIDI → Score. (Not edited as notation: notes are edited in the
piano roll of a Midi, then MIDI → Score.)

| Becomes | How |
|---|---|
| Pdf | Convert > MIDI / Score → PDF |
| ExerciseSet | Generate > Exercises to do > Read & play / Listen & repeat from MIDI / score |
| Midi (duet from its melody) | Generate > Duet from a melody |
| Print | File > Print… / right click |
| File .mid / .pdf / .wav | Save / Save as… |

## Pdf ▤ (red)
Origin: PDF file opened, result of MIDI / Score → PDF.

| Becomes | How |
|---|---|
| Midi | Convert > PDF → MIDI |
| Pdf with trumpet fingerings | Convert > PDF → trumpet fingerings (scoreread; trumpet parts only; new object, the original stays) |
| Print | File > Print… / right click |
| File .pdf / .mid | Save / Save as… |

## ExerciseSet ▦ (orange = Read & play, green = Listen & repeat)
A group of exercises (difficulty level, instrument Bb / C; notes kept inside the range of
Settings > Instruments, default G3–F5 written).

| Becomes | How |
|---|---|
| Practice | Double click (or right click > Do it): Read & play / Listen & repeat on the whole group (trumpet or MIDI keyboard); every take = an attempt on its exercise |
| Routine | Generate > Make a routine (with other exercises) |
| Midi (duets) | Generate > Duet from a melody: one duet for every exercise (owner's exception, 2026-11-20) |
| File .mke | Save / Save as… (zipped; exercises are saved only as exercises; .json still possible) |

## Phrase ♩ (orange = Read & play, green = Listen & repeat)
A single exercise.

| Becomes | How |
|---|---|
| Practice | Double click: its own exercise tab; every take = an attempt (grade in its name); report (exercise green/red + what was played) at the end |
| Variant ♩ (a NEW exercise) | In its tab, "Make a variant": bars, part, simplify, instrument / transposition, transformation, tempo. "Save as new" = new exercise without results; doing it = new exercise with that result; the old one stays (exercises from 2026-11-08 remember their MIDI; older ones: only tempo and transposition) |
| Routine | Generate > Make a routine |
| Midi (duet) | Generate > Duet from a melody: its notes + a second voice (owner's exception to "exercises stay exercises", 2026-11-20) |
| View | View: tab "View: exercise" (arrow keys browse the other exercises) |
| Print | File > Print… / right click |
| File .mke | Save / Save as… (zipped, one exercise; File > Open… gives it back as an exercise ♩). No .mid / .pdf / .wav: exercises stay exercises |

## Exercise ◆ (purple; tasks.Task)
Intervals / Interval reading / Chord qualities / Fingerings & note names (a block of
questions + settings) and Long tones, Scales &
arpeggios, Lip slurs, Rhythm reading, Chord arpeggios (the exercise + its settings), with
their attempts.
Origin: Practice (every Start = a new exercise, done at once, then it is here with its
result; Again / Repeat add attempts to it) or Generate > Exercises to do (no result yet).
Old result objects ★ (workspaces, .json) are converted into these when loaded.

| Becomes | How |
|---|---|
| Practice | Double click: its tab bound to it (its settings shown); intervals: the same questions in another order |
| View | Summary, staff of the last attempt (drills; cents chart for long tones), one row per attempt, Do it |
| Routine | Generate > Make a routine |
| File .mke | Save / Save as… (zipped) |

## Routine ↻ (dark blue; tasks.Routine)
A sequence of exercises done one after the other, every day. Origin: Generate > Make a
routine on the selected exercises (their order in Objects). The items are COPIES; each has
"New each time" (drills, interval blocks, Read & play from duets: a new exercise every day).

| Becomes | How |
|---|---|
| Practice | Double click: runner tab (list, done-today ticks, grades; Start / Next, Auto-advance; Add… / Up / Down / Remove) |
| More exercises | Add… in the runner: selected in Objects, exercise files, or a NEW exercise (new each time) |
| File .mkr | Save / Save as… (zipped; .json still possible) |

## Play over MIDI ♬ (dark green; playover.PlayOver)
A MIDI to play over: up to three tracks shown and muted ("Show and mute"), the others played
by the app. Remembers only the MIDI (always inside) and the tracks to read (+ tempo %,
accompaniment volume, click). Grade n/a, no results, nothing in the diary; played to the end
= done for the session (routines go on).

| Becomes | How |
|---|---|
| Practice | Double click: its tab (tracks, Bars from / to, Tempo %, Accompaniment, Click; Start / Stop) |
| Routine | Generate > Make a routine, Add…, drag into the routine |
| File .mke | Save / Save as… (zipped, the MIDI inside) |

## Group of exercises ▦ (purple; tasks.TaskGroup)
Several exercises ◆ generated together (Generate > Exercises to do, "How many" > 1: long
tones, scales, lip slurs, rhythm, chord arpeggios, intervals, interval reading, chord
qualities, flash cards).
Expands in Objects; each child is an exercise with its own results.

| Becomes | How |
|---|---|
| Practice | Double click: runner tab (one after the other, like a routine); double click on a child = that exercise |
| Routine | Generate > Make a routine (the group = its exercises) |
| File .mke | Save / Save as… (zipped) |

## Notes ≈ (blue-grey)
A transcribed recording; for now only from code.

## No input
Generate > Duet → Midi, Generate > Canon for trumpets → Midi, Generate > Backing track from
chords → Midi (Melodies and etudes, Brass trio / quartet are in the menu as "(to do)"). Generate > Exercises to do: Read & play from duets (▦),
Long tones, Scales & arpeggios, Lip slurs, Rhythm reading, Chord arpeggios, Intervals,
Interval reading, Chord qualities, Fingerings & note names (◆, N at a time, without results). PRACTICE = QUICK EXERCISE: Start makes ONE new exercise and does it
at once; it goes to Objects (Exercises) with its result — Intervals / Interval reading (a
block), Long tones, Scales & arpeggios, Lip slurs, Rhythm reading, Chord arpeggios (settings
in the tab), Read
& play / Listen & repeat (a piece of a new duet: part, bars, difficulty, instrument in the
tab). Every attempt also goes to the practice diary.
Practice > Free player: the MIDI keyboard played with the soundfont; Rec records takes (one
part per instrument, overdub); at Stop the recording appears as a piano roll and Quantize… is
offered; edit it there; Save → Midi.

Play (Objects panel only) = listen: staff in the centre, red cursor, sound. Start (exercises
only) = practise: click (optional), red cursor, no sound.

## Open points
1. Exercises are not converted back to Midi / Score / Pdf (owner's decision, for now). Exception
   (owner, 2026-11-20): Generate > Duet from a melody makes a NEW duet (Midi) from an exercise.
2. The ScoreReport is not an object: seen in the exercise tab, stored in the results archive.
3. The difficulty of an exercise (`difficulty.py`) exists only for scripts, not in the interface.
