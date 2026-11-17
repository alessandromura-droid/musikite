# Installation

[← Manual](README.md)

There are two ways to run MusiKitE on a Mac:

1. the **app** (`MusiKitE-arm64.dmg` for Apple silicon Macs, `MusiKitE-intel.dmg` for Intel
   Macs): everything is inside, nothing else to install;
2. the **source code** with Python (for development, Jupyter, the command line).

Which Mac do I have? Apple menu  > About This Mac: "Chip Apple M1/M2/M3/M4…" = Apple
silicon (arm64); "Processor … Intel" = Intel.

## 1. The app

1. Download the `.dmg` for your Mac from the **Releases** page of the GitHub repository.
2. Open it and drag **MusiKitE** onto **Applications**.
3. **First start.** The app is not signed with an Apple Developer ID, so macOS stops it the
   first time ("cannot be opened because the developer cannot be verified" or "is
   damaged"). Do one of these, once:
   - in Applications, **right-click MusiKitE > Open**, then **Open** in the dialog; or
   - System Settings > **Privacy & Security**, scroll down, **Open Anyway** next to
     MusiKitE.
   If macOS still says the app "is damaged", the download is quarantined; in Terminal:
   `xattr -dr com.apple.quarantine /Applications/MusiKitE.app` (it removes only the
   "downloaded from the Internet" mark of that app).
4. **Microphone.** The first exercise that listens asks for the microphone: answer
   **Allow**. If you said no: System Settings > Privacy & Security > **Microphone** > tick
   MusiKitE.
5. **Sound.** The app contains the soundfont *GeneralUser GS*, used when you have not
   chosen another one ([Settings > Audio > Soundfont](settings.md#soundfont)).

The app starts in a few seconds (it unpacks Python and its libraries).

### Where your data are

The app never stores your data inside itself, so updating it loses nothing:

| What | Where |
|---|---|
| Users, settings, results, practice diary, last workspace | `~/.musikite/` (hidden folder in your home) |
| Your files: workspaces, exercises, MIDI, PDF, scores, audio, results, soundfonts | `~/musikite/` (changeable in [Settings > Folders](settings.md#folders)) |
| Log | `~/.musikite/log.txt` |

`~` is your home folder. In Finder, Cmd+Shift+. shows hidden folders.

## 2. From the source code

MusiKitE needs Python ≥ 3.10 (3.12 recommended), the C libraries **FluidSynth** and
**PortAudio ≥ 19.7**, and the Python packages of `requirements.txt`. The reference set-up is
a conda environment:

1. Install Miniforge (or Miniconda) — https://github.com/conda-forge/miniforge
2. In Terminal:

   ```
   conda install -c conda-forge fluidsynth "portaudio>=19.7"
   python3 -m pip install -r requirements-macbook.txt
   ```

   `requirements-macbook.txt` lists the exact versions known to work;
   `requirements.txt` the same packages without versions.
3. Check everything:

   ```
   python3 -m musictools check
   ```

   It tells you what is missing and the commands to install it (see
   [Troubleshooting](troubleshooting.md#dependency-check)).
4. Start the window:

   ```
   python3 -m musictools gui
   ```

   or, in Jupyter (`demo.ipynb`): `import musictools; app = musictools.gui()`.

All the packages are required: the program does not start if one is missing or does not
load. Only `ipywidgets` and `jupyterlab` (for the demo notebook) are optional.

### PortAudio 19.6 crashes the microphone

With PortAudio 19.6 (old conda builds) the first recording closes the program
("libc++abi: terminating"). `python3 -m musictools check` reports it; the fix is
`conda install -c conda-forge "portaudio>=19.7"`.

## Updating

- App: download the new `.dmg`, drag MusiKitE onto Applications again (replace).
- Source: update the folder (git pull or a new copy); `python3 -m musictools check`.
