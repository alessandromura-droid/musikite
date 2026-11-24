#!/bin/bash
# build_mac_app.sh — MusiKitE.app and its .dmg for the processor of THIS Mac (owner,
# 2026-11-17: one Apple silicon Mac and one Intel Mac, each builds its own; no Rosetta).
#
#   bash scripts/build_mac_app.sh          (from the project folder, or from anywhere)
#
# What it does:
#   1. finds conda (Miniconda / Miniforge / Anaconda, Homebrew casks included);
#   2. the FIRST time creates the conda environment "musikite-build" (Python 3.12 +
#      FluidSynth from conda-forge, then the MacBook's packages of requirements-macbook.txt
#      + PyInstaller): 10-20 minutes and about 2-3 GB, ONCE; the next times it is reused and
#      updated only when requirements-macbook.txt changes. Your own Python / conda base
#      environment is NOT touched. To remove it:  conda env remove -n musikite-build
#   3. makes MusiKitE.app with PyInstaller (scripts/musikite.spec) in a temporary folder:
#      Python, PySide6, every library, FluidSynth, the soundfont GeneralUser GS, the fonts,
#      the manual (docs/) and the icon inside; the microphone permission declared;
#   4. writes ~/Desktop/MusiKitE-arm64.dmg (Apple silicon) or ~/Desktop/MusiKitE-intel.dmg
#      (Intel), REPLACING an older one with the same name; the temporary folder is deleted.
# The app is NOT signed with an Apple Developer ID: the first time, open it with right
# click > Open (or System Settings > Privacy & Security > Open Anyway).
set -euo pipefail

PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="musikite-build"
PY_VERSION="3.12"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || die "this script makes the Mac app: run it on a Mac"

# ---------------------------------------------------------------- processor
ARCH="$(uname -m)"                                   # arm64 or x86_64
if [ "$(sysctl -in hw.optional.arm64 2>/dev/null || echo 0)" = "1" ] && [ "$ARCH" != "arm64" ]; then
    die "this is an Apple silicon Mac but the Terminal runs under Rosetta (Intel mode): \
open a native Terminal (Finder > Applications > Utilities > Terminal > Get Info: untick \
'Open using Rosetta') and run the script again"
fi
case "$ARCH" in
    arm64)  LABEL="arm64" ; WHAT="Apple silicon" ;;
    x86_64) LABEL="intel" ; WHAT="Intel" ;;
    *)      die "unknown processor $ARCH" ;;
esac
say "MusiKitE for $WHAT ($ARCH), project: $PROJECT"

# ---------------------------------------------------------------- conda
CONDA="${CONDA_EXE:-}"
if [ -z "$CONDA" ] || [ ! -x "$CONDA" ]; then
    CONDA="$(type -P conda || true)"
fi
if [ -z "$CONDA" ]; then
    for c in "$HOME/miniconda3/bin/conda" "$HOME/miniforge3/bin/conda" \
             "$HOME/anaconda3/bin/conda" "$HOME/mambaforge/bin/conda" \
             /opt/homebrew/Caskroom/miniconda/base/bin/conda \
             /usr/local/Caskroom/miniconda/base/bin/conda \
             /opt/homebrew/Caskroom/miniforge/base/bin/conda \
             /usr/local/Caskroom/miniforge/base/bin/conda \
             /opt/miniconda3/bin/conda /opt/anaconda3/bin/conda; do
        if [ -x "$c" ]; then CONDA="$c"; break; fi
    done
fi
[ -n "$CONDA" ] || die "conda not found: install Miniconda or Miniforge first \
(python3 -m musikite check prints how)"
BASE="$("$CONDA" info --base)"
ENV_DIR="$BASE/envs/$ENV_NAME"
PY="$ENV_DIR/bin/python"
say "conda: $CONDA"

# ---------------------------------------------------------------- build environment
if [ ! -x "$PY" ]; then
    say "first time: creating the conda environment $ENV_NAME (10-20 minutes, once)"
    "$CONDA" create -y -n "$ENV_NAME" --override-channels -c conda-forge "python=$PY_VERSION" fluidsynth
fi
"$PY" -c 'import platform, sys; sys.exit(0 if platform.machine() == "'"$ARCH"'" else 1)' \
    || die "the environment $ENV_NAME is not for $ARCH: remove it (conda env remove -n \
$ENV_NAME) and run the script again"
[ -e "$ENV_DIR/lib/libfluidsynth.dylib" ] || {
    say "installing FluidSynth in $ENV_NAME"
    "$CONDA" install -y -n "$ENV_NAME" --override-channels -c conda-forge fluidsynth
}

REQ="$PROJECT/requirements-macbook.txt"
[ -f "$REQ" ] || die "requirements-macbook.txt not found in $PROJECT"
STAMP="$ENV_DIR/.musikite-requirements.md5"
NEW_MD5="$(md5 -q "$REQ")"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$NEW_MD5" ]; then
    say "installing the packages of requirements-macbook.txt + PyInstaller in $ENV_NAME"
    REQ_APP="$(mktemp -t musikite-req)"
    # the notebook packages are not part of the app
    grep -v -E '^[[:space:]]*(ipywidgets|jupyterlab)' "$REQ" > "$REQ_APP"
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r "$REQ_APP" "pyinstaller>=6.10"
    rm -f "$REQ_APP"
    echo "$NEW_MD5" > "$STAMP"
fi

# ---------------------------------------------------------------- build
WORK="$(mktemp -d -t musikite-build)"
trap 'rm -rf "$WORK"' EXIT

# version = the day of the newest file of the code (the same code gives the same version
# on both Macs: check it in Finder > Get Info after Dropbox has synchronised)
NEWEST="$(find "$PROJECT/musikite" "$PROJECT/scripts" -name '*.py' -type f \
          -exec stat -f '%m' {} + | sort -n | tail -1)"
VERSION="$(date -r "$NEWEST" +%Y.%m.%d)"
CODE_TIME="$(date -r "$NEWEST" '+%Y-%m-%d %H:%M')"

ICON_PNG="$PROJECT/musikite/data/icon.png"
ICNS=""
if [ -f "$ICON_PNG" ]; then
    SET="$WORK/MusiKitE.iconset"
    mkdir -p "$SET"
    for s in 16 32 128 256 512; do
        sips -z $s $s "$ICON_PNG" --out "$SET/icon_${s}x${s}.png" >/dev/null
        sips -z $((s * 2)) $((s * 2)) "$ICON_PNG" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
    done
    iconutil -c icns "$SET" -o "$WORK/MusiKitE.icns" && ICNS="$WORK/MusiKitE.icns"
fi

SF2="$PROJECT/musikite/data/GeneralUser-GS.sf2"
[ -f "$SF2" ] || echo "WARNING: $SF2 not found: the app will have no soundfont"
[ -f "$PROJECT/docs/README.md" ] || echo "WARNING: docs/ not found: the app will have no manual"

say "building MusiKitE.app $VERSION (code of $CODE_TIME) with PyInstaller (a few minutes)"
( cd "$WORK" && \
  MUSIKITE_ARCH="$ARCH" MUSIKITE_VERSION="$VERSION" MUSIKITE_ICNS="$ICNS" \
  "$PY" -m PyInstaller --noconfirm --clean --log-level WARN \
        --distpath "$WORK/dist" --workpath "$WORK/build" \
        "$PROJECT/scripts/musikite.spec" )
APP="$WORK/dist/MusiKitE.app"
[ -d "$APP" ] || die "PyInstaller made no MusiKitE.app (see the messages above)"

# ---------------------------------------------------------------- dmg
say "making the dmg"
DMG_DIR="$WORK/dmg"
mkdir -p "$DMG_DIR"
ditto "$APP" "$DMG_DIR/MusiKitE.app"
ln -s /Applications "$DMG_DIR/Applications"
OUT="$HOME/Desktop/MusiKitE-$LABEL.dmg"
hdiutil create -quiet -volname "MusiKitE $VERSION" -srcfolder "$DMG_DIR" -ov \
        -format UDZO "$OUT"

say "done: $OUT"
echo "   MusiKitE $VERSION for $WHAT, code of $CODE_TIME, $(du -h "$OUT" | cut -f1)"
echo "   Install: open the dmg, drag MusiKitE to Applications."
echo "   First start: right click on MusiKitE > Open (the app is not signed by Apple)."
