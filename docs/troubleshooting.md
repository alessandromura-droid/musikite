# Troubleshooting

[← Manual](README.md)

## First look: the Log

Everything the app does, and every reason why something did not start, is written in the
**Log** panel (hidden at start: *View > Log*) and in `~/.musikite/log.txt` (with the full error when something fails).
Problems reading PDFs are in `~/.musikite/scoreread.log`.

## Dependency check

From the source code:

```
python3 -m musikite check
```

It reports Python, every package (really loaded, not only installed), FluidSynth, the
project files, the fonts, audio outputs and microphones, MIDI inputs and the soundfont,
then a **RESULT** line and the commands to fix what is missing, each with what it does, how
long it takes and how to undo it. The program does not start if a required package is
missing.

## The app does not open

- "cannot be opened because the developer cannot be verified" / "is damaged": see
  [Installation > First start](installation.md#1-the-app).
- It opens and closes at once: run it from Terminal to see the message:
  `/Applications/MusiKitE.app/Contents/MacOS/MusiKitE`.

## No sound

1. Settings > Audio > **Test sound**: it says what is active or why it failed.
2. Check the **output device** and the system volume.
3. Settings > Audio > **Soundfont**: without a soundfont there is no music (the clicks
   become synthetic "tocks").
4. A larger **buffer** if the sound crackles.

## The microphone hears nothing

1. Settings > Audio > **Input device**, then **Test microphone**: the bar must move.
2. macOS permission: System Settings > Privacy & Security > **Microphone** > MusiKitE (from
   source: your Terminal / Python).
3. The Log reports the peak level of every take; a silent take is reported.

## Grades seem too low (Read & play)

- The clicks must reach the microphone (they align the recording), unless you use
  headphones.
- Play the **written** note: for a B♭ trumpet the app expects what you read.
- Use a quiet room; the report shows in blue what the app heard.

## Chord arpeggios: the piano disturbs

Use **headphones**: otherwise the microphone hears the piano. The exact notes the piano is
playing are already ignored.

## The MIDI keyboard does nothing

Settings > Audio > **MIDI input**, then **Test MIDI**. If nothing arrives in 4 s: cable,
the keyboard's *local control*, the port chosen. The Free player connects the keyboard only
while its tab is in front.

## The microphone crashes the program (source installation)

PortAudio 19.6 (old conda builds) closes the program at the first recording ("libc++abi:
terminating"). Fix: `conda install -c conda-forge "portaudio>=19.7"`. The dependency check
reports it.

## A PDF gives no MIDI

- Only **vector** PDFs exported by notation programs can be read; scans cannot.
- If the instrument is not recognised, choose it in *Convert > PDF → MIDI* or tick
  *Force*.
- See `~/.musikite/scoreread.log`.

## Objects disappeared

Objects belong to the **current user**: check the user in the toolbar. The last workspace
of every user is saved automatically and reopened at the next start.

## A MIDI takes long to show

The first time a long MIDI with many parts is shown, its notation is made from the MIDI;
meanwhile the **first 8 bars** appear at once and the status says "the rest is loading…";
the whole score takes their place by itself (Play already plays everything). The result
is kept: the next time the same MIDI opens at once, also after restarting MusiKitE. The
kept scores are in `~/.musikite/cache/scores` (at most 500 MB, the oldest removed first);
the folder can be deleted at any time.
