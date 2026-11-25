# Generate

[← Manual](README.md)

*Generate* makes **new material**: music (duets, canons, brass trios and quartets, backing
tracks, duets from a melody, melodies and etudes) and **exercises to do** (without
results). Every tool is in the menu; a tool that is not for the **Instrument** chosen in
the toolbar (e.g. the duet for two trumpets when the instrument is the piano) is greyed and
cannot be chosen (the same in Practice). The exercises are in the submenu **Exercises to
do**. The options of every tool appear in the **Tools** panel on the right; **Run**
makes the objects. Tools that work on existing objects (e.g. exercises from a MIDI) use the
objects **selected** in the Objects panel and run once for each of them.

To practise something **at once** use the [Practice](read-and-play.md) menu instead:
*Generate* prepares, *Practice* plays.

## Duet for two trumpets

A random duet for two trumpets in B♭ on a chord progression. Result: a MIDI with two
parts, "Trumpet in Bb 1" and "Trumpet in Bb 2".

| Option | Meaning |
|---|---|
| **Engine** | *classic*: the first duet engine. *counterpoint*: the melody is made by rules (phrases in pairs, the motif restated, cadences, chord tones on the strong beats, passing and neighbour tones) and the second voice by the rules of two-voice counterpoint: consonances on the strong beats, no parallel fifths or octaves, contrary motion preferred, a **complementary rhythm** (one voice moves while the other holds). The melody passes to trumpet 2 in some periods (an asterisk in the Log). |
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

## Backing track from chords

A **backing track for improvisation**: a MIDI with three tracks — **bass**, **chords**
(piano, electric piano or jazz guitar) and **drums** — on a chord progression, in a simple
jazz / "jazz pop" style. It is only the backing, to play over with *Play* in Objects; to
practise improvisation **with a grade** use [Chord arpeggios](drills.md#chord-arpeggios)
(inside a full backing your instrument could not be heard).

| Option | Meaning |
|---|---|
| **Progression** | A progression of the catalogue put in the *Chords* field: ii-V-I, blues, rhythm changes, So What… and the changes of some common **standards** (Blue Bossa, Autumn Leaves, All of Me, Take the A Train; chords only, simplified as in the common lead sheets; they start in their usual key). *(chords)* = the chords typed. |
| **Chords** / **Key** | As in the duet: one chord per bar, `F:G` = two in a bar; changing the key moves the chords; **New** = another progression. |
| **Chords in concert pitch** | Unticked (default): chords and key are **written for your instrument** (the one beside the user). Ticked: concert pitch. |
| **Style** | `swing` (walking bass, comping on 2 and 4 / Charleston, ride and hi-hat), `bossa nova`, `ballad` (slow, held chords), `jazz pop` (straight eighths, backbeat). Choosing a style sets its usual tempo. |
| **Tempo (bpm)** | Swing 140, bossa nova 130, ballad 70, jazz pop 100 by default. |
| **Choruses** | How many times the progression is played. |
| **Chords played by** | Piano, electric piano or jazz guitar. |
| **Seed** | −1 = random. The same seed with the same options gives the same backing. |

The chord voicings have no root (the bass plays it) and move as little as possible from
one chord to the next; every chorus after the first starts with a crash and ends with a
small fill. The backing has one **count-in bar** (side stick) and a **final chord** (the
first chord again, held, with a crash). With *Play* in Objects in a loop (the default) you
hear the count-in once, the choruses over and over for about 10 minutes without any gap,
then the final chord. The chord names are stored in the MIDI as text, with a mark that
tells the app it is a backing made here.

## Duet from a melody

A **duet made from a melody that already exists**: select a **MIDI**, a **score**, an
**exercise** or a group of exercises in Objects and run it. The result is a new MIDI with two
parts: the **melody** (unchanged) and a **second voice** written for it. For a MIDI with
several tracks the melody is the track with the most notes, unless you tick another one; an
exercise gives its own notes and key (a group: one duet for every exercise).

First the app finds the **chords** of the melody: one chord per bar, or two where the metre
has two halves (4/4, 2/2, 6/8…), chosen among the chords of the key (plus the dominant
seventh and the secondary dominants) so that they cover the notes of the melody and follow
each other in the usual way, starting and ending on the tonic. Where the melody does not
decide the chord, any good chord is taken. The chords found are written in the Log.

| Option | Meaning |
|---|---|
| **Mode** | Default `accompaniment`. `harmony`: the same melody **harmonised** a third (or a sixth) below or above, in the key — major or minor third as the scale and the chord require; on the strong beats, long notes and chord notes the second voice takes a note of the chord (a sixth, a fifth, the octave…); never the unison, no parallel fifths or octaves. `canon`: the **melody itself** in the second voice, entering later. `accompaniment`: the second voice **plays the chords** found. |
| **Melody track** | The track that is the melody (MIDI and score only). |
| **Second voice** | The instrument of the second voice; it starts as the instrument beside the user. Its notes stay inside **your range** for that instrument (Settings > Instruments). |
| **Below / above** | Harmony and accompaniment: the second voice under or over the melody. |
| **Harmony: interval** | Parallel `thirds` or `sixths`. |
| **Canon: delay** | Half bar, 1, 2 or 4 bars; `auto` = the one that sounds best. |
| **Canon: interval** | Unison / octave, fifth, fourth or third, always inside the key; the octave is chosen by the range of the second instrument. `auto` = the one that sounds best. |
| **Canon: strict** | Ticked: the second voice is exactly the melody. Unticked (default): a note that clashes on a strong beat is moved to the nearest note of the chord, and the last note goes to the tonic chord. |
| **Canon: even if dissonant** | A canon does not work on every melody: when the best delay and interval are consonant less than 70 % of the time, the app says so and makes nothing. Tick this to make it anyway. |
| **Accompaniment: pattern** | `long notes` (one note per chord), `half notes`, `beats` (one note a beat, the root on the downbeat and a step towards the next chord before it changes), `arpeggio` (up, up, down; the default); `auto` = long notes under a busy melody, more notes under a slow one. |

Only the options of the chosen mode are used. The object is named "*melody* – *mode*"; the
tempo, time and key signatures are those of the source. Limits: a pickup bar (upbeat) is not
recognised, so the strong beats are taken from the start of the MIDI; one key for the whole
melody; a melody with chords is read as its top notes.

## Brass trio / quartet

A **trio** (two trumpets in B♭ and a trombone) or a **quartet** (two
trumpets, horn in F and trombone) on a chord progression. The two trumpets are a
[duet](#duet-for-two-trumpets) with the same options (engine, chords, key, rounds, level,
seed, tempo, bars per phrase, textures, repetition: the same seed gives the same trumpet
lines);
the trombone plays the bass (the root of every chord; at levels 2-3 root and fifth on long
chords), the horn an inner voice (third or seventh of the chord, moving as little as
possible). The result is a MIDI; its score shows every part written for its instrument.

## Melodies and etudes

New melodies to read (Read & play exercises) for the **instrument beside you**:

| Option | Meaning |
|---|---|
| **How many** | Number of melodies (one group ▦). |
| **Engine** | How the notes are chosen (see below). |
| **Key (written)** | The key you read in; *Auto* = a key signature suited to the difficulty. |
| **Difficulty** | 0–10 for your instrument (a melody is kept if it is within 1); *Any* = a different difficulty for every melody. |
| **Time** | 4/4, 3/4, 2/4 or 6/8 (the voice of a duet is always 4/4). |
| **Bars** | Length of every melody. |
| **Seed** | The same seed gives the same melodies. |

Every melody is **planned** before its notes: a **form** (an 8-bar *sentence* — an idea of
two bars, its repetition, shorter fragments, the cadence — or a *period* — a phrase ending
open on the dominant, answered by a phrase that starts again with the same idea and ends on
the tonic; longer melodies put themes together and often come back to the first idea at the
end), a **harmony** (from the tonic, usual chord successions, cadences), a **rhythm** (the
idea's rhythm comes back with it). The difficulty decides the note values, the largest
leap, the range, the notes outside the chords (passing and neighbour notes from level 2,
chromatic neighbours from level 6). Then the **engine** chooses the notes:

- **Skeleton and elaboration (Povel)**: chord notes on the strong beats first, along an
  arch and a line that goes down to the cadence; then the notes between them (passing and
  neighbour notes, always resolved by step).
- **Probabilistic (Temperley)**: note by note, the likely notes are those near the middle
  of the range, near the previous note and important in the key; chord notes on the
  strong beats.
- **Scale degrees (Markov)**: note by note on the degrees of the scale, with their
  tendencies (the leading note goes to the tonic, the fourth degree down to the third…).
- **Voice of a new duet**: one of the two voices of a new duet (the classic engine).

The melodies do not come from the [exercise library](library.md). If not enough melodies
of the difficulty asked are made, the group has fewer (its title says so).

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
| **Transformation** | `none`, `transpose` (±1–6 semitones, staying in range), `reverse_melody` (pitches backwards, rhythm kept), `reverse_rhythm`, `inversion` (diatonic mirror around the tonic), `mode` (another church mode on the same tonic), `remove_accidentals`, `even_eighths`, or `random` (a different one for each phrase; written in its title). |
| **Remove empty bars** | Bars with rests only are removed before cutting (default on). |
| **Polyphony** | Listen & repeat only (for a MIDI keyboard): all the selected parts together, chords included. Off = one exercise per part, highest note of each chord. |
| **Include the MIDI** | On (default): every exercise keeps a copy of the source MIDI, so it can be [changed later](read-and-play.md#make-a-variant). Off: no trace of the source. |

The exercises are for the **instrument chosen beside the user** (see
[The instrument](getting-started.md#the-instrument)): written for it, in its clef, one
voice for wind instruments. Notes outside the [range of the instrument](settings.md#instruments)
are moved by octaves into it.

### Read & play – generate random / Listen & repeat – generate random

Pieces of **new random music** made by the app (no file needed): bars, simplify,
key signature, part; for the instrument chosen beside the user. Listen & repeat: 2 bars.

**Key signature**: every exercise is in a **random key** (major or minor), written for the
instrument you play, with at most this many sharps / flats. *auto* follows Simplify:

| Simplify | Key signature |
|---|---|
| 1, 2 | none (C major / A minor) |
| 3 | up to 1 |
| 4 | up to 3 |
| 5 | up to 5 |

So the piano reads in C at the easy levels (before, every random piano exercise was in B♭:
the music was written in C for the B♭ trumpet), and so does the trumpet.

### Drills

*Long tones*, *Scales & arpeggios*, *Lip slurs*, *Rhythm reading*, *Chord arpeggios*: the
same options as their Practice tab (see [Drills](drills.md)), starting from the values you
used last there.

### Quizzes

*Intervals*, *Interval reading*, *Chord qualities*, *Scales and modes by ear*, *Scale
degrees by ear*, *Cadences by ear*, *Fingerings & note names*: **Questions
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
