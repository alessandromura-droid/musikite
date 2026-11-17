# Generate

[← Manual](README.md)

*Generate* makes **new material**: music (duets, canons) and **exercises to do** (without
results). The options of every tool appear in the **Tools** panel on the right; **Run**
makes the objects. Tools that work on existing objects (e.g. exercises from a MIDI) use the
objects **selected** in the Objects panel and run once for each of them.

To practise something **at once** use the [Practice](read-and-play.md) menu instead:
*Generate* prepares, *Practice* plays.

## Duet for two trumpets

A random duet for two trumpets in B♭ on a chord progression. Result: a MIDI with two
parts, "Trumpet in Bb 1" and "Trumpet in Bb 2".

| Option | Meaning |
|---|---|
| **Chords** | One chord per bar, e.g. `C F G C` or in Italian `Do Fa Sol Do`; `F:G` = two chords in one bar. Any chord the app knows: `Dm7`, `Bbmaj7`, `F#m7b5`, `C/E`, `Solm7`… On the Mac you can type it; **New** makes a different progression in the chosen key. |
| **Key** | The key of the progression (C … B, Cm … Bm), chosen from the list. **Changing the key moves the chords into it**: `C F G G C F G C` in E becomes `E A B B E A B E`. From major to the minor of the same tonic the chords become minor where the key requires it (C F G → Cm Fm G; the dominant stays major). If you type the chords by hand, the key follows their first chord. |
| **Chords in concert pitch** | Unticked (default): chords and key are **written** for the trumpet (what the player reads). Ticked: they are concert pitch. |
| **Rounds** | How many times the progression is repeated (1–16). |
| **Level** | 1–3: rhythmic and melodic complexity. |
| **Seed** | −1 = random. The same seed with the same options gives the same duet. |
| **Tempo (bpm)** | Tempo written in the MIDI. |
| **Bars per phrase** | Length of the musical phrases (antecedent / consequent). |
| **Textures** | How the two voices relate: `thirds`, `sixths`, `melody_acc` (melody and accompaniment), `pedal`, `dialogue`, `echo`, `canon_bar`, and from level 2 `canon_half`, `mirror`, `counterpoint`. None selected = all those allowed by the level. |
| **Repetition** | 0 = free lines, 1 = strongly motivic (the motif is restated and developed). |

The object is named "Duet L*level* seed *seed*": the seed lets you make it again.

## Canon for trumpets

Trumpet 2 plays exactly what trumpet 1 played one progression earlier.

| Option | Meaning |
|---|---|
| **Chords**, **Key**, **New**, **Chords in concert pitch** | As for the duet. |
| **Difficulty** | 1 one long note per chord · 2 half notes · 3 quarter notes · 4 + eighth notes · 5 mostly eighth notes |
| **Beats per chord** | 1–8 |
| **Cycles** | How many times trumpet 1 plays the progression (1–12). |
| **Seed**, **Tempo** | As for the duet. |

## Exercises to do

*Generate > Exercises to do* makes exercises **without results**, to be done later
(double-click) or put into a [routine](routines.md). Every tool has **How many** and
**Seed**. With *How many* > 1 the exercises are collected in **one group** ▦ (expand it to
see them; double-click the group to do them one after the other).

### Read & play – generate from MIDI / Listen & repeat – generate from MIDI

Cuts the **selected MIDI or scores** into short phrases. One group per input.

| Option | Meaning |
|---|---|
| **Bars per exercise** | Starts from [Settings > Exercises](settings.md#exercises) (Read & play 8, Listen & repeat 2). Phrases with fewer than 4 notes are skipped. |
| **Simplify** | 1 whole and half notes · 2 + quarter notes · 3 + eighth notes (default) · 4 + sixteenth notes · 5 all notes. Notes shorter than the level are removed; each note kept lasts until the next one. |
| **Instrument** | The instrument you will **play**: `Bb (trumpet)` (written a tone above the sound, treble clef, one voice), `C (piano)`, `C (trombone)` (bass clef, one voice). |
| **Transformation** | `none`, `transpose` (±1–6 semitones, staying in range), `reverse_melody` (pitches backwards, rhythm kept), `reverse_rhythm`, `inversion` (diatonic mirror around the tonic), `mode` (another church mode on the same tonic), `remove_accidentals`, `even_eighths`, or `random` (a different one for each phrase; written in its title). |
| **Remove empty bars** | Bars with rests only are removed before cutting (default on). |
| **Polyphony** | Listen & repeat only (for a MIDI keyboard): all the selected parts together, chords included. Off = one exercise per part, highest note of each chord. |
| **Include the MIDI** | On (default): every exercise keeps a copy of the source MIDI, so it can be [changed later](read-and-play.md#make-a-variant). Off: no trace of the source. |

Notes outside the [range of the instrument](settings.md#instruments) are moved by octaves
into it.

### Read & play – generate random / Listen & repeat – generate random

Pieces of **new random music** made by the app (no file needed): bars, simplify,
instrument, part. Listen & repeat: 2 bars, trumpet or piano.

### Drills

*Long tones*, *Scales & arpeggios*, *Lip slurs*, *Rhythm reading*, *Chord arpeggios*: the
same options as their Practice tab (see [Drills](drills.md)), starting from the values you
used last there.

### Quizzes

*Intervals*, *Interval reading*, *Chord qualities*, *Fingerings & note names*: **Questions
each** plus the options of the quiz (see [Ear training](ear-training.md)). The questions
are drawn now and stay the same every time the exercise is done (in a different order).

### Play over MIDI

Makes a [Play over MIDI](play-over-midi.md) exercise from the selected MIDI: tracks to read
("Show and mute", up to 3), tempo %, bars from / to.

## Make a routine

*Generate > Make a routine* (also right-click) puts the **selected exercises**, in their
order, into a new [routine](routines.md). A group counts as its exercises.

| Option | Meaning |
|---|---|
| **Title** | Name of the routine. |
| **New each time** | Exercises made by the app (drills, quizzes, random pieces) are made **new every day**. |

The routine holds **copies**: the original exercises are not changed.
