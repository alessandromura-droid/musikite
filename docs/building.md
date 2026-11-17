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
   (`musictools/data`), the fonts, this manual (`docs/`), the icon, and the microphone
   permission. A few minutes.
4. **Makes the dmg** (the app and a link to Applications) with `hdiutil`, then deletes the
   temporary folder.

The **version** of the app is the date of the newest `.py` file of the code: the same code
gives the same version on both Macs. Check it in Finder > Get Info, after Dropbox (or git)
has synchronised the code.

## Requirements

- macOS with conda installed (`python3 -m musictools check` explains how).
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

Upload the two dmg files to a new **Release** of the GitHub repository (Releases > Draft a
new release > attach the files). Do not commit them to the repository itself.
