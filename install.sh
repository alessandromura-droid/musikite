#!/bin/bash
# MusiKitE: installation from the source code (macOS). Owner, 2026-11-24.
#
#   git clone https://github.com/alessandromura-droid/musikite.git
#   cd musikite && ./install.sh
#
# Every step that changes something is ASKED first ([Y/n]); --yes answers yes to all.
# What it does, in order:
#   1. checks macOS and the processor (Apple silicon / Intel; a Terminal under Rosetta
#      is refused);
#   2. finds conda; if there is none, proposes to install Miniforge (conda-forge, open
#      source) in ~/miniforge3 and to run `conda init zsh`;
#   3. in the conda BASE environment: the C libraries FluidSynth and PortAudio >= 19.7
#      (conda-forge);
#   4. the Python packages at the versions of the reference Mac (requirements-macbook.txt),
#      then MusiKitE itself, "editable" (`pip install -e .`): the command `musikite` is
#      made in the conda base and a `git pull` updates the program without reinstalling;
#   5. the manual page (`man musikite`): a link into the conda base;
#   6. `musikite check`: the same dependency check the program runs at every start;
#   7. if a new Terminal would not find `musikite`, proposes the PATH line for ~/.zshrc;
#   8. prints some examples to try.
# Nothing is deleted. Undo: `pip uninstall musikite`, remove the line marked "MusiKitE"
# from ~/.zshrc, remove the link <conda>/share/man/man1/musikite.1.

set -u
YES=0
for a in "$@"; do
    case "$a" in
        -y|--yes) YES=1 ;;
        -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "unknown option: $a (try --help)"; exit 2 ;;
    esac
done

PROJECT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B=$'\033[1m'; G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; N=$'\033[0m'
step() { echo; echo "${B}== $*${N}"; }
ok()   { echo "${G}ok${N}  $*"; }
warn() { echo "${Y}warning${N}  $*"; }
die()  { echo "${R}ERROR${N}  $*" >&2; exit 1; }
ask() {                       # ask "question" -> 0 = yes
    [ "$YES" = 1 ] && { echo "$1 [Y/n] y"; return 0; }
    local r
    read -r -p "$1 [Y/n] " r </dev/tty || r=""
    case "$r" in n|N|no|No|NO) return 1 ;; *) return 0 ;; esac
}

echo "${B}MusiKitE installation${N}  (project: $PROJECT)"
[ -d "$PROJECT/musikite" ] || die "the folder musikite/ is not next to install.sh"

# ------------------------------------------------------------------ 1. system
step "1. System"
[ "$(uname -s)" = "Darwin" ] || die "this script is for macOS (on other systems: pip install -e . and FluidSynth / PortAudio from the system)"
ARCH="$(uname -m)"
if [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = "1" ]; then
    die "this Terminal runs under Rosetta: open a native Terminal (Apple silicon) and run again"
fi
ok "macOS $(sw_vers -productVersion), processor $ARCH"

# ------------------------------------------------------------------ 2. conda
step "2. conda (base environment)"
CONDA=""
if command -v conda >/dev/null 2>&1; then
    CONDA="$(command -v conda)"
else
    for c in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" \
             /opt/homebrew/Caskroom/miniforge/base /usr/local/Caskroom/miniforge/base \
             /opt/homebrew/Caskroom/miniconda/base /usr/local/Caskroom/miniconda/base \
             /opt/miniconda3 /opt/anaconda3; do
        [ -x "$c/bin/conda" ] && { CONDA="$c/bin/conda"; break; }
    done
fi
if [ -z "$CONDA" ]; then
    warn "conda not found"
    echo "   Miniforge (conda from conda-forge, open source) would be installed in ~/miniforge3"
    echo "   (about 5 minutes, ~500 MB; undo: delete ~/miniforge3 and the conda lines in ~/.zshrc)."
    if ask "Download and install Miniforge now?"; then
        URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-$ARCH.sh"
        TMP="$(mktemp -t miniforge).sh"
        curl -fL "$URL" -o "$TMP" || die "download failed: $URL"
        bash "$TMP" -b -p "$HOME/miniforge3" || die "Miniforge installation failed"
        rm -f "$TMP"
        CONDA="$HOME/miniforge3/bin/conda"
        if ask "Run 'conda init zsh' (adds the conda lines to ~/.zshrc, so every Terminal has conda)?"; then
            "$CONDA" init zsh
        fi
    else
        die "conda is needed: install Miniforge (https://github.com/conda-forge/miniforge) and run ./install.sh again"
    fi
fi
BASE="$("$CONDA" info --base 2>/dev/null)" || die "conda does not answer: $CONDA"
PY="$BASE/bin/python3"
[ -x "$PY" ] || die "no python3 in the conda base ($BASE)"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || \
    die "the conda base has Python $("$PY" -c 'import sys;print(sys.version.split()[0])'): 3.10 or newer is needed (conda install -n base python=3.12)"
ok "conda base: $BASE (Python $("$PY" -c 'import sys;print(sys.version.split()[0])'))"

# ------------------------------------------------------------------ 3. C libraries
step "3. C libraries: FluidSynth, PortAudio >= 19.7 (conda-forge, base environment)"
echo "   (a few minutes the first time; undo: conda remove -n base fluidsynth portaudio)"
if ask "Install / update them now?"; then
    "$CONDA" install -y -n base -c conda-forge fluidsynth "portaudio>=19.7" || \
        die "conda could not install FluidSynth / PortAudio"
    ok "FluidSynth and PortAudio"
else
    warn "skipped: the check (step 6) will say if they are missing"
fi

# ------------------------------------------------------------------ 4. Python packages
step "4. Python packages (versions of the reference Mac) and MusiKitE"
echo "   pip install -r requirements-macbook.txt, then pip install -e . (editable: the"
echo "   program is used from this folder; the command 'musikite' is made in $BASE/bin)"
if ask "Install them now?"; then
    "$PY" -m pip install --upgrade pip || warn "pip could not be upgraded"
    "$PY" -m pip install -r "$PROJECT/requirements-macbook.txt" || \
        die "pip could not install the packages (see above)"
    "$PY" -m pip install --no-deps -e "$PROJECT" || die "pip could not install MusiKitE"
    ok "packages and MusiKitE"
else
    warn "skipped"
fi

# ------------------------------------------------------------------ 5. manual page
step "5. Manual page (man musikite)"
MANDIR="$BASE/share/man/man1"
if [ -L "$MANDIR/musikite.1" ] && [ "$(readlink "$MANDIR/musikite.1")" = "$PROJECT/man/man1/musikite.1" ]; then
    ok "already linked: $MANDIR/musikite.1"
elif ask "Link the manual page into $MANDIR?"; then
    mkdir -p "$MANDIR" && ln -sf "$PROJECT/man/man1/musikite.1" "$MANDIR/musikite.1" && \
        ok "linked $MANDIR/musikite.1" || warn "could not link the manual page"
fi

# ------------------------------------------------------------------ 6. check
step "6. Dependency check (musikite check)"
CHECK_OK=1
"$PY" -m musikite check || CHECK_OK=0
[ "$CHECK_OK" = 1 ] && ok "everything needed is there" || \
    warn "something is missing: see the RESULT above, then run ./install.sh again"

# ------------------------------------------------------------------ 7. PATH
step "7. The command 'musikite' in a new Terminal"
FOUND="$(/bin/zsh -ilc 'command -v musikite' 2>/dev/null </dev/null | tail -1)"
if [ -n "$FOUND" ]; then
    ok "a new Terminal finds it: $FOUND"
else
    LINE="export PATH=\"$BASE/bin:\$PATH\"  # MusiKitE: the command musikite (conda base)"
    echo "   A new Terminal would NOT find 'musikite'. This line in ~/.zshrc fixes it:"
    echo "     $LINE"
    if grep -q "# MusiKitE: the command musikite" "$HOME/.zshrc" 2>/dev/null; then
        warn "~/.zshrc already has the MusiKitE line: check it"
    elif ask "Add it at the end of ~/.zshrc? (undo: delete that line)"; then
        printf '\n%s\n' "$LINE" >> "$HOME/.zshrc" && ok "added to ~/.zshrc (open a new Terminal)"
    else
        warn "not added: use '$BASE/bin/musikite' or 'python3 -m musikite' from this folder"
    fi
fi

# ------------------------------------------------------------------ 8. examples
step "8. Try it (in a NEW Terminal)"
cat <<'TXT'
  musikite --help                       the commands
  man musikite                          the manual page
  musikite gui                          the app (window)
  musikite duet -l 2 -s 7 -o duet.mid --pdf duet.pdf
                                        a duet for two trumpets, MIDI and PDF
  musikite canon -d 3 -o canon.mid      a canon for two trumpets
  musikite view duet.mid --page         the duet on the staff, Play with the cursor
  musikite pdf part.pdf -o part.mid     a vector PDF part read into MIDI
  musikite fingering part.pdf           trumpet fingerings under the notes (part.noted.pdf)
  musikite merge a.mid b.mid -o all.mid all the tracks in one MIDI
  musikite check                        the dependency check again
TXT
echo
[ "$CHECK_OK" = 1 ] && echo "${G}${B}MusiKitE is installed.${N}" || \
    echo "${Y}${B}MusiKitE is installed, but the check found problems (step 6).${N}"
