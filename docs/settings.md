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

## Audio

| Setting | Meaning |
|---|---|
| **Output device** | Where the sound goes (system default if empty). |
| **Driver** | `coreaudio` on macOS. |
| **Buffer (period size) / Periods** | Latency = period size × periods / sample rate. Default 64 × 2 at 48 kHz ≈ 3 ms. If the device refuses it, larger buffers are tried and the Log says which one is used. |
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

**Min / Max** for trumpet, piano and trombone, in **written** pitch (C4 = middle C). Default
for the trumpet G3–F5; trombone E2–B♭4. At least one octave. Generated exercises keep their
notes inside the range (moved by octaves); long tones, scales and flash cards start from it.

## Exercises

General page:

| Setting | Meaning |
|---|---|
| **To do in Objects** | Which exercises are shown as *to do* (bold on grey). For now: *never done today*. |
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
