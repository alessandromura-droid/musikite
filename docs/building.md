# Building the Mac app

[← Manual](README.md)

`scripts/build_mac_app.sh` makes **MusiKitE.app** and its **.dmg** for the processor of
the Mac it runs on. To have both versions, run it once on an Apple silicon Mac and once on
an Intel Mac.

```
bash scripts/build_mac_app.sh
```

Result on the Desktop:

| Mac | File |
|---|---|
| Apple silicon (M1, M2, …) | `~/Desktop/MusiKitE-arm64.dmg` |
| Intel | `~/Desktop/MusiKitE-intel.dmg` |

An older dmg with the same name is **replaced**.

## What it does

1. **Finds conda** (Miniconda, Miniforge, Anaconda, also when installed with Homebrew).
2. **The first time** creates the conda environment `musikite-build`: Python 3.12 and
   FluidSynth from conda-forge, then the packages of `requirements-macbook.txt` and
   PyInstaller. This takes **10–20 minutes and 2–3 GB, once**. It is outside the project
   folder (in conda's own folder) and does not touch your Python. Later runs reuse it and
   update it only when `requirements-macbook.txt` changes.
3. **Builds the app** with PyInstaller (`scripts/musikite.spec`) in a temporary folder:
   Python, PySide6 and every library, FluidSynth, the soundfont *GeneralUser GS* with its licence
   (`musikite/data`), the fonts, this manual (`docs/`), the icon, and the microphone
   permission. A few minutes.
4. **Makes the dmg** (the app and a link to Applications) with `hdiutil`, then deletes the
   temporary folder.

The **version** of the app is the date of the newest `.py` file of the code: the same code
gives the same version on both Macs. Check it in Finder > Get Info, after Dropbox (or git)
has synchronised the code.

## Starting the source version from the Dock

```
bash scripts/make_launcher.sh
```

makes **MusiKitE (source).app** in the project folder: a small app (a few KB, no
libraries inside) that starts MusiKitE **from the source code**
(`python3 -m musikite gui`) with the MusiKitE icon. Drag it to the Dock. Every change of
the code is used at the next start: nothing to rebuild. With the project in Dropbox the app
reaches every Mac.

- **Python**: the one Terminal uses (conda, set up by `conda init`), else the base Python
  of the usual conda installs; 3.10 or newer (the macOS system Python is refused).
- **Project**: the folder that contains the app; if the app is moved elsewhere (e.g.
  Applications), the folder where it was made.
- **Microphone**: macOS asks the permission for this app the first time.
- **Errors**: there is no Terminal, so everything is written to
  `~/.musikite/launcher.log` (Python used, project, errors before the Log of the app
  opens); if Python or the project are not found a message appears.
- Running the script again replaces the app; to remove it, delete it. A different folder:
  `bash scripts/make_launcher.sh FOLDER`. The app is not in the repository (`.gitignore`).

## Requirements

- macOS with conda installed (`python3 -m musikite check` explains how).
- On Apple silicon, a **native** Terminal: if Terminal is set to *Open using Rosetta* the
  script stops and says so.
- Internet the first time (conda and pip packages).

## Removing what it installed

```
conda env remove -n musikite-build
```

This deletes the build environment (2–3 GB). The next run creates it again.

## Signing

The app is **not signed** with an Apple Developer ID, so on other Macs it must be opened
the first time with right-click > Open (see [Installation](installation.md#1-the-app)).
Signing and notarisation need a paid Apple Developer account and are not part of the
script.

## Publishing

```
bash scripts/upload_release.sh
```

uploads the dmg found on the Desktop (`MusiKitE-arm64.dmg` and / or `MusiKitE-intel.dmg`)
to the GitHub **Releases** of the repository: it reads the version from the app inside the
dmg, creates the release `v<version>` if it does not exist, and replaces a file with the same
name already in it (so the second dmg, built on the other Mac, joins the same release). It
uses `curl` and the token git saved in the Keychain at your first `git push` (or asks for
it); the token needs *Contents: Read and write* on the repository. Nothing on the Mac is
changed; to undo, delete the release on the Releases page.

By hand: Releases > Draft a new release > attach the files. Never commit the dmg to the
repository itself.
