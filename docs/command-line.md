# Command line and scripts

[← Manual](README.md)

From the project folder (source installation, see [Installation](installation.md#2-from-the-source-code)).

## `python3 -m musictools`

| Command | What it does |
|---|---|
| `gui` | Opens the main window. |
| `check` | Dependency check: what is missing and how to install it ([Troubleshooting](troubleshooting.md#dependency-check)). |
| `duet` | A random duet for two B♭ trumpets. |
| `canon` | A canon for two B♭ trumpets. |
| `pdf FILE.pdf` | MIDI from a vector PDF. |
| `merge A.mid B.mid …` | All the tracks in one MIDI. |
| `fingering FILE.pdf` | PDF with the trumpet fingerings under the notes. |
| `play FILE.mid` | Plays a MIDI. |
| `view FILE.mid|FILE.pdf` | A window with the staff and Play / Stop / Zoom. |

Options common to `duet`, `canon`, `pdf`, `merge`, `play`:

| Option | Meaning |
|---|---|
| `-o, --out FILE.mid` | Output MIDI |
| `--pdf FILE.pdf` | Also engrave the result to a PDF |
| `--sf2 FILE.sf2` | Soundfont used to play |
| `--play` | Play the result |

### duet

```
python3 -m musictools duet -c "C F G C" -g 2 -l 1 -k C -s 42 -t 120 -o duet.mid --pdf duet.pdf
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

### canon

```
python3 -m musictools canon -c "C F G C" -d 2 -b 4 -n 4 -k C -t 80 -o canon.mid
```

`-d, --difficulty` 1–5, `-b, --beats_per_chord`, `-n, --cycles`, `-k, --key`, `--concert`,
`-s, --seed`, `-t, --bpm`.

### pdf

```
python3 -m musictools pdf part.pdf -o part.mid [--instrument trumpet] [--force]
```

### merge

```
python3 -m musictools merge part1.mid part2.mid -o all.mid [--allow_tempo_mismatch]
```

The tempo map of the first file is kept; files with a different tempo map are refused unless
`--allow_tempo_mismatch`.

### fingering

```
python3 -m musictools fingering part.pdf [-o out.pdf] [--fontsize 12] [--font F.ttf]
        [--space 12] [--color k|r|g|b] [--no_repetition] [--instrument trumpet]
```

Default output: `part.noted.pdf` next to the input. The same as the old
`python3 scoreread.py part.pdf`, which still works.

### view

```
python3 -m musictools view file.mid [--page] [--bpm 90]
python3 -m musictools view part.pdf [--instrument trumpet]
```

## Scripts (`scripts/`)

| Script | What it does |
|---|---|
| `scripts/build_mac_app.sh` | Builds the Mac app and its .dmg: see [Building the Mac app](building.md). |
| `scripts/upload_release.sh` | Uploads the dmg on the Desktop to the GitHub Releases: see [Building the Mac app](building.md#publishing). |
| `scripts/makeexercises.py FOLDER [--out DIR] [--lowest G3] [--highest C6] [--no-include_midi]` | Read & play exercises for the trumpet from **every MIDI** of a folder: every transformation × every key × tempo 50 / 100 / 150 %, keeping only those inside the range; each exercise rated 0–10 and saved as `exercises/trumpet/levelNN/exerciseNNNN_<key>.mke`. About 700 exercises per 16-bar duet. |
| `scripts/rebuild_band.py FOLDER [--dry-run]` | FOLDER has one subfolder per instrument with the PDF parts: every PDF is read again into `<name>.from_pdf.mid`, the parts are grouped by song and every song is merged into `<song> - all parts.mid`. Deletes nothing. `--dry-run` only lists what it would do. |
| `scripts/merge_midi.py IN1.mid IN2.mid … OUT.mid` | All the tracks in one MIDI, keeping the tempo map; refuses files with different tempi. |
| `scripts/merge_song.sh TEXT OUTPUT` | In the current folder, merges every MIDI below it whose name contains TEXT into OUTPUT.mid. |

## Python and Jupyter

The same objects are available from Python; `demo.ipynb` has an example for every feature.

```python
import musictools as mt
m = mt.Midi().makeduet(chords="C F G C", key="E", seed=1)
m.to_pdf("duet.pdf")
app = mt.gui()            # the main window, driven from Jupyter
```
