# Settings

[← Manual](README.md)

*Settings > Settings…* (Cmd+,). The tree on the left chooses the page. **Save** saves every
page; **Reset page** restores the defaults of the page shown. Settings belong to the
**current user**.

## Folders

Where your files go: workspaces, exercises, MIDI, PDF, scores, audio, results, soundfonts.
Defaults: `~/musikite/<kind>`. File dialogs open in the folder of the object type. The
folders are shared by all users (one MIDI for 30 pupils); names of a user's own files
(workspaces, exercises, results) start with the user name.

### Data folder

Where MusiKitE keeps **users, settings, results, practice diary and last workspaces**
(default `~/.musikite`). Put it in a **shared Dropbox folder** to have the same users on two
computers: choose the same folder on both, and opening the same user on either one gives
exactly the same app. When you choose a folder:

- if it has no MusiKitE data, the current data is **copied** into it (the old copy stays);
- if it already has (the other computer put it there), it is **used as it is**.

Paths saved in the settings and in the workspaces (folders, soundfont, files of the
objects) are written relative to the data folder or to your home folder, so they work on
both computers if Dropbox is in the same place under the home.

Do not open the **same user on two computers at once**: they would overwrite each other's
results. If you do, the app warns you ("user open on another computer").

## Users

The users of the data folder. **Delete user** removes the user selected from the list at
once (no need to press Save) and asks for a confirmation. His data — settings, results,
practice diary, workspace — **stay** in the data folder: **New user… > Recover user** in the
toolbar brings him back. Deleting the user you are using closes Settings and opens another
user; deleting the **last** user asks for a new one (or *Cancel and exit*): the app never
works without a user.

## Audio

| Setting | Meaning |
|---|---|
| **Output device** | Where the sound goes (system default if empty). |
| **Driver** | `coreaudio` on macOS. |
| **Buffer (period size) / Periods** | Latency = period size × periods / sample rate. Default 256 × 2 (at least 256: smaller buffers gave no sound) ≈ 12 ms at 44.1 kHz. If the device refuses it, larger buffers are tried and the Log says which one is used. |
| **Sample rate**, **Gain** | |
| **Test sound** | A note and four clicks; reports what is active or why it failed. |
| **Input device** | The microphone used by the exercises. |
| **Test microphone** | A level meter (−60 … 0 dBFS). If nothing moves after 4 s, check the microphone permission (System Settings > Privacy & Security > Microphone) or choose another device. |
| **MIDI input** | Your MIDI keyboard, or **Computer keyboard** (the letters of the computer as a keyboard, see [Free player > Computer keyboard](free-player.md#computer-keyboard)). With no MIDI keyboard connected the computer keyboard is used. |
| **Test MIDI** | Shows the last messages (note, velocity, channel, pedal, pitch bend) and plays them. If nothing arrives in 4 s: check the cable, *local control*, the port. |
| **Keyboard sound** | The keys sound with the soundfont during exercises (turn off for keyboards with their own sound). |
| **Recording offset (ms)** | Corrects a constant delay of the recordings of the Free player. |

### Soundfont

The `.sf2` file that makes every sound. **Browse…** (or Return in the field) loads it and
saves it at once. With no soundfont chosen, the app uses the one it contains (*GeneralUser
GS*). Other free soundfonts: see [Credits](credits.md#soundfont).

## Instruments

The instruments of the **current user**:

| Setting | Meaning |
|---|---|
| **Played** | Tick the instruments you play. Brass: trumpet in B♭ and in C, cornet, flugelhorn, tenor horn in E♭, mellophone, horn in F, euphonium (in B♭ treble clef, or in C bass clef), trombone, bass trombone, tuba in B♭ / C / E♭ / F, sousaphone. Woodwinds: saxophones (soprano, alto, tenor, baritone), clarinet in B♭ / A / E♭, bass clarinet, flute, piccolo, oboe, English horn, bassoon. The **piano** is always there. They are the choices of **Instrument** in the toolbar. |
| **Lowest / Highest** | Range of the generated exercises for each instrument, in **written** pitch (C4 = middle C). Defaults: trumpet, cornet, flugelhorn, tenor horn, mellophone, horn G3–F5; trombone E2–B♭4; bass trombone C2–F4; euphonium treble clef F♯3–C6, bass clef E2–B♭4; tuba and sousaphone in B♭ B♭1–B♭3 (C: C2–C4, E♭: E♭2–E♭4, F: F2–F4); saxophones C4–C6; clarinets G3–G5; flute C4–D6; piccolo D4–G6 (written); oboe and English horn C4–C6; bassoon C2–G4; piano G3–F5. At least one octave. Generated exercises keep their notes inside it (moved by octaves). |
| **Preferred instrument** | The instrument selected when the user is opened; the toolbar changes it for the session. |

Each drill (long tones, scales, lip slurs) also remembers its own *Lowest / Highest* for
each instrument, and *Show positions* of Read & play is remembered for each instrument.

**Fingerings shown** (*Show positions*), for the current user:

| Box | Meaning |
|---|---|
| **4th valve** | Euphonium and tubas with a 4th valve: 4 and 2-4 instead of 1-3 and 1-2-3, and the low notes down to the pedal (4th valve combinations, not compensating). |
| **F trigger** | Tenor trombone with an F trigger: T1, T2… instead of the 6th / 7th position and below E2. The bass trombone always uses the trigger. |
| **Double horn** | Horn in F: the B♭ side (T…) from written G♯4 up. |

## Exercises

General page:

| Setting | Meaning |
|---|---|
| **To do in Objects** | Which exercises are shown as *to do* (bold, in a dark shade of their colour on light grey; once done: a light shade on the dark background). For now: *never done today*. |
| **Routine: next exercise after** | Seconds before Auto-advance opens the next exercise of a [routine](routines.md) (default 10). |
| **Cursor** | How the red cursor moves on every staff: **1 = notes** (default: it is on each note or rest when it starts) or **2 = bars** (it goes at constant speed from one bar line to the next, and is on the bar line at the downbeat, with the click; inside the bar it can be slightly ahead of or behind the note, because notation is not spaced in proportion to time). |

One page per exercise type (Intervals, Interval reading, Chord qualities, Fingerings & note
names, Read & play, Listen & repeat):

| Setting | Meaning |
|---|---|
| **Questions** | Questions in a block (default 10). |
| **Points** | Base points, harmonic factor, time factor, replay penalty (see [Grading](grading.md#blocks-of-questions)). |
| **Default bars** | Read & play 8, Listen & repeat 2. |
| **bpm** | Default tempo (Read & play 90). |
| **Input** | Microphone or MIDI keyboard. |
| **Show first note** | Read & play off, Listen & repeat on. |
| **Click** | First state of the **Click** button of the tab (audio click on). |
