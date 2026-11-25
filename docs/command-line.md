# Command line and scripts

[← Manual](README.md)

From the project folder (source installation, see [Installation](installation.md#2-from-the-source-code)).

## `musikite` (= `python3 -m musikite`)

The command **`musikite`** is made by `./install.sh` (`pip install -e .`, in the conda
base) and `man musikite` works after it. With the **Mac app** (the .dmg): Help > **Install
command-line tool…** (one line in `~/.zshrc`, asked first; the commands below are the same). Without installing, the script `bin/musikite` of
the project does the same (file names relative to the folder you are in): add once to
`~/.zshrc` (then open a new Terminal) — NOT together with the installed command:

```
export PATH="<project folder>/bin:$PATH"
```

`musikite --help` lists the commands; `musikite COMMAND --help` the options of one
command; **`man musikite`** is the classic manual page (found because `bin` is in the
PATH; otherwise `man ./man/man1/musikite.1` from the project folder). Without the PATH
line, `python3 -m musikite …` from the project folder does the same. The old name
`python3 -m musictools …` still works.

| Command | What it does |
|---|---|
| `gui` | Opens the main window. |
| `check` | Dependency check: what is missing and how to install it ([Troubleshooting](troubleshooting.md#dependency-check)). |
| `duet` | A random duet for two B♭ trumpets. |
| `canon` | A canon for two B♭ trumpets. |
| `second_voice FILE.mid` | A duet from a melody: the melody of the MIDI and a second voice ([Duet from a melody](generate.md#duet-from-a-melody)). |
| `pdf FILE.pdf` | MIDI from a vector PDF. |
| `merge A.mid B.mid …` | All the tracks in one MIDI. |
| `fingering FILE.pdf` | PDF with the trumpet fingerings under the notes. |
| `play FILE.mid` | Plays a MIDI. |
| `view FILE.mid|FILE.pdf` | A window with the staff and Play / Stop / Zoom. |

Options common to `duet`, `canon`, `second_voice`, `pdf`, `merge`, `play`:

| Option | Meaning |
|---|---|
| `-o, --out FILE.mid` | Output MIDI |
| `--pdf FILE.pdf` | Also engrave the result to a PDF |
| `--sf2 FILE.sf2` | Soundfont used to play |
| `--play` | Play the result |

### duet

```
python3 -m musikite duet -c "C F G C" -g 2 -l 1 -k C -s 42 -t 120 -o duet.mid --pdf duet.pdf
```

| Option | Meaning (default) |
|---|---|
| `-c, --chords` | Progression (`C F G G C F G C`) |
| `-g, --rounds` | Repetitions (2) |
| `-l, --level` | 1–3 (1) |
| `-k, --key` | Key, e.g. `E` or `Am` (first chord) |
| `--concert` | Chords / key at concert pitch (default: written for the trumpet) |
| `-s, --seed` | Random seed |
| `-t, --bpm` | Tempo (120) |
| `-f, --phrase` | Bars per phrase (4) |
| `-x, --textures` | Textures allowed |
| `-r, --repetition` | 0–1 (0.7) |
| `-e, --engine` | `classic` (default) or `counterpoint`: melody made by rules, second voice by the rules of counterpoint |

### canon

```
python3 -m musikite canon -c "C F G C" -d 2 -b 4 -n 4 -k C -t 80 -o canon.mid
```

`-d, --difficulty` 1–5, `-b, --beats_per_chord`, `-n, --cycles`, `-k, --key`, `--concert`,
`-s, --seed`, `-t, --bpm`.

### second_voice

```
python3 -m musikite second_voice melody.mid -m harmony --interval sixths -o duet.mid
python3 -m musikite second_voice melody.mid -m canon --delay "2 bars" -o canon.mid
python3 -m musikite second_voice melody.mid -m accompaniment --pattern beats --instrument "C (trombone)"
```

| Option | Meaning (default) |
|---|---|
| `-m, --mode` | `harmony`, `canon`, `accompaniment` (accompaniment) |
| `--track` | Melody track, 0 = the first (the track with the most notes) |
| `--instrument` | Second voice, e.g. `"Bb (trumpet)"`, `"C (trombone)"` (your current instrument) |
| `--side` | `below` / `above` the melody (below) |
| `--interval` | Harmony: `thirds` / `sixths` (thirds) |
| `--delay` | Canon: `auto`, `"half bar"`, `"1 bar"`, `"2 bars"`, `"4 bars"` (auto) |
| `--canon_interval` | Canon: `auto`, `"unison / octave"`, `"fifth below (fourth above)"`, `"fourth below (fifth above)"`, `"third below (sixth above)"` (auto) |
| `--strict` | Canon: the exact melody, no note moved |
| `--allow_dissonant` | Canon: make it even when the melody does not hold a canon |
| `--pattern` | Accompaniment: `auto`, `"long notes"`, `"half notes"`, `beats`, `arpeggio` (arpeggio) |

### pdf

```
python3 -m musikite pdf part.pdf -o part.mid [--instrument trumpet] [--force]
```

### merge

```
python3 -m musikite merge part1.mid part2.mid -o all.mid [--allow_tempo_mismatch]
```

The tempo map of the first file is kept; files with a different tempo map are refused unless
`--allow_tempo_mismatch`.

### fingering

```
python3 -m musikite fingering part.pdf [-o out.pdf] [--fontsize 12] [--font F.ttf]
        [--space 12] [--color k|r|g|b] [--no_repetition] [--instrument trumpet]
```

Default output: `part.noted.pdf` next to the input. The same as the old
`python3 scoreread.py part.pdf`, which still works.

### view

```
python3 -m musikite view file.mid [--page] [--bpm 90]
python3 -m musikite view part.pdf [--instrument trumpet]
```

## Scripts (`scripts/`)

| Script | What it does |
|---|---|
| `scripts/build_mac_app.sh` | Builds the Mac app and its .dmg: see [Building the Mac app](building.md). |
| `scripts/upload_release.sh` | Uploads the dmg on the Desktop to the GitHub Releases: see [Building the Mac app](building.md#publishing). |
| `scripts/makeexercises.py FOLDER [--out DIR] [--lowest G3] [--highest C6] [--no-include_midi]` | Read & play exercises for the trumpet from **every MIDI** of a folder: every transformation × every key × tempo 50 / 100 / 150 %, keeping only those inside the range; each exercise rated 0–10 and saved as `exercises/trumpet/levelNN/exerciseNNNN_<key>.mke`. About 700 exercises per 16-bar duet. |
| `scripts/build_library.py FOLDER [flags] [--out DIR]` | The **exercise library** of the app (the folder `musikite/data/library/`) directly from a folder of MIDI files (each thrown away if too repetitive). Flags, at least one: `--none` (the source file itself, unchanged), `--modal` (the melody in the 6 other church modes), `--inversion`, `--inversion-modal`, `--retrograde`, `--retrograde-modal`, `--retrograde-inversion`; `--crossings N`, `--generated N` (crossed / generated melodies, default 0), `--min-entropy X` (default 3.5, 0 = no filter), `--seed S`. Every file is named, and titled in the app, after its source and what was done: `mid/<source>.mid`, `mid/<source> - dorian.mid`, `mid/<source> - inversion, lydian.mid`… **Additive**: the melodies already there stay (file, title, number), nothing is removed, a melody with the same notes and name is not added twice — run it once per source folder. Minutes to tens of minutes; only the output folder is written. See [Exercise library](library.md). |
| `scripts/ptb2midi.py INPUT OUTPUT [--recursive] [--mono] [--trumpet]` | Every **Power Tab** file (.ptb, Power Tab Editor 1.7) of INPUT → a MIDI file with the same name in OUTPUT (one track per guitar, tempo, only the first time signature, repeats and D.C. / D.S. / Coda played out; `--mono`: one track with the highest note at every moment, no polyphony; `--trumpet`: every track with the trumpet sound). Only writes the .mid files (a file with the same name is replaced). |
| `scripts/gp2midi.py INPUT OUTPUT [--recursive] [--mono] [--trumpet]` | The same for **Guitar Pro** files (.gp3, also .gp4 / .gp5): same options and rules (one track per guitar, only the first time signature, repeats and alternate endings played out; the D.C. / D.S. / Coda of Guitar Pro 5 are not followed). Needs `pip install pyguitarpro`. Only writes the .mid files. |
| `scripts/midi2melody.py INPUT OUTPUT [--recursive] [--mono] [--trumpet]` | Every **MIDI** file of INPUT → a MIDI with the same name in OUTPUT containing **only the melody**: the track that most looks like one (one voice, high, moving by steps, present for most of the piece, its name and instrument; never the drums). Same options and rules as `ptb2midi.py` (tempo changes kept, only the first time signature). Prints the track chosen for every file. Only writes the .mid files. |
| `scripts/fit_range.py INPUT OUTPUT LOWEST HIGHEST [--recursive]` | Every **MIDI** file of INPUT → a MIDI with the same name in OUTPUT with the notes brought into the range LOWEST..HIGHEST (MIDI numbers, C4 = 60, as in the files: concert pitch; e.g. trumpet in Bb from written G below the staff to A above it = `53 79`). Track by track (drums untouched): the track is transposed by semitones (the shift with the fewest notes outside, then the most centred), the notes still outside are moved by octaves into the range, notes falling on the same pitch at the same time become one. Everything else is kept. Only writes the .mid files. |
| `scripts/rebuild_band.py FOLDER [--dry-run]` | FOLDER has one subfolder per instrument with the PDF parts: every PDF is read again into `<name>.from_pdf.mid`, the parts are grouped by song and every song is merged into `<song> - all parts.mid`. Deletes nothing. `--dry-run` only lists what it would do. |
| `scripts/merge_midi.py IN1.mid IN2.mid … OUT.mid` | All the tracks in one MIDI, keeping the tempo map; refuses files with different tempi. |
| `scripts/merge_song.sh TEXT OUTPUT` | In the current folder, merges every MIDI below it whose name contains TEXT into OUTPUT.mid. |

## Python and Jupyter

The same objects are available from Python; `demo.ipynb` has an example for every feature.

```python
import musikite as mt
m = mt.Midi().makeduet(chords="C F G C", key="E", seed=1)
m.to_pdf("duet.pdf")
app = mt.gui()            # the main window, driven from Jupyter
```
