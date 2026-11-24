#!/bin/bash
# make_launcher.sh — makes "MusiKitE (source).app", a small app for the Dock that starts
# MusiKitE FROM THE SOURCE CODE of this project (python3 -m musikite gui), with the
# MusiKitE icon. No libraries inside (a few KB): every change of the code is used at the
# next start, nothing to rebuild.
#
#   bash scripts/make_launcher.sh [FOLDER]
#
# FOLDER = where the app is written (default: the project folder, so Dropbox brings it to
# every Mac). Then drag it to the Dock. Running the script again replaces it.
#
# At every start the launcher:
#   - finds the project: the folder that contains the app (if it holds musikite/),
#     else the project folder where the launcher was made;
#   - finds Python as Terminal does (a login + interactive zsh, so `conda init` in
#     ~/.zshrc is applied), else the base Python of the usual conda installs; Python
#     must be 3.10 or newer (the macOS system 3.9 is refused);
#   - writes what it does and every error to ~/.musikite/launcher.log (there is no
#     Terminal to show them);
#   - replaces itself with Python (exec), so the Dock shows one icon.
# The microphone permission is asked for this app the first time (Info.plist).
# Owner's request, 2026-11-17. NOT TESTED by Claude.

set -u

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$PROJECT}"
NAME="MusiKitE (source)"
APP="$DEST/$NAME.app"

say() { echo "== $*"; }

if [ ! -d "$PROJECT/musikite" ]; then
    echo "ERROR: $PROJECT/musikite not found: run the script from the project" >&2
    exit 1
fi
if [ ! -d "$DEST" ]; then
    echo "ERROR: folder $DEST does not exist" >&2
    exit 1
fi

say "making $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# icon (.icns from musikite/data/icon.png, as build_mac_app.sh)
ICON_PNG="$PROJECT/musikite/data/icon.png"
ICON_KEY=""
if [ -f "$ICON_PNG" ]; then
    WORK="$(mktemp -d)"
    SET="$WORK/MusiKitE.iconset"
    mkdir -p "$SET"
    for s in 16 32 128 256 512; do
        sips -z $s $s "$ICON_PNG" --out "$SET/icon_${s}x${s}.png" >/dev/null
        sips -z $((s * 2)) $((s * 2)) "$ICON_PNG" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
    done
    if iconutil -c icns "$SET" -o "$APP/Contents/Resources/MusiKitE.icns"; then
        ICON_KEY="    <key>CFBundleIconFile</key><string>MusiKitE</string>"
    else
        echo "WARNING: icon not made (iconutil failed): the app will have the generic icon"
    fi
    rm -rf "$WORK"
else
    echo "WARNING: $ICON_PNG not found: the app will have the generic icon"
fi

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>$NAME</string>
    <key>CFBundleDisplayName</key><string>$NAME</string>
    <key>CFBundleIdentifier</key><string>org.musikite.source</string>
    <key>CFBundleExecutable</key><string>MusiKitE</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleShortVersionString</key><string>source</string>
    <key>CFBundleVersion</key><string>1</string>
$ICON_KEY
    <key>NSHighResolutionCapable</key><true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>MusiKitE listens to your instrument to check the exercises you play.</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict>
</plist>
EOF

# the launcher itself; the project folder of today is written in it as a fallback
cat > "$APP/Contents/MacOS/MusiKitE" <<'EOF'
#!/bin/bash
# MusiKitE (source): starts `python3 -m musikite gui` from the project folder.
# Made by scripts/make_launcher.sh; log in ~/.musikite/launcher.log.

MADE_IN="@PROJECT@"
LOG="$HOME/.musikite/launcher.log"
mkdir -p "$HOME/.musikite"
exec >"$LOG" 2>&1
echo "MusiKitE (source) started $(date '+%Y-%m-%d %H:%M:%S')"

fail() {
    echo "ERROR: $*"
    osascript -e "display alert \"MusiKitE (source)\" message \"$*

See ~/.musikite/launcher.log\"" >/dev/null 2>&1
    exit 1
}

# the project: the folder that contains the app, else the one where it was made
HERE="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -d "$HERE/musikite" ]; then
    PROJECT="$HERE"
elif [ -d "$MADE_IN/musikite" ]; then
    PROJECT="$MADE_IN"
else
    fail "project folder not found (looked in $HERE and $MADE_IN). Make the launcher again with scripts/make_launcher.sh."
fi
echo "project: $PROJECT"

# Python 3.10 or newer
good() {
    [ -n "$1" ] && [ -x "$1" ] && \
        "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}
PY=""
# 1) as Terminal does (conda init is in ~/.zshrc: login + interactive shell)
CAND="$(/bin/zsh -ilc 'command -v python3' 2>/dev/null </dev/null | tail -1)"
good "$CAND" && PY="$CAND"
# 2) the base Python of the usual conda installs
if [ -z "$PY" ]; then
    for c in "$HOME/miniconda3" "$HOME/miniforge3" "$HOME/anaconda3" \
             /opt/homebrew/Caskroom/miniconda/base /usr/local/Caskroom/miniconda/base \
             /opt/homebrew/Caskroom/miniforge/base /usr/local/Caskroom/miniforge/base \
             /opt/miniconda3 /opt/anaconda3; do
        if good "$c/bin/python3"; then PY="$c/bin/python3"; break; fi
    done
fi
[ -n "$PY" ] || fail "no Python 3.10 or newer found (the conda Python of Terminal). Check with: python3 -m musikite check"
echo "python: $PY ($("$PY" -c 'import sys; print(sys.version.split()[0])'))"

cd "$PROJECT" || fail "cannot enter $PROJECT"
exec "$PY" -m musikite gui
EOF

# the project folder of today inside the launcher (fallback when the app is moved)
ESCAPED="$(printf '%s' "$PROJECT" | sed -e 's/[\/&|]/\\&/g')"
sed -i '' "s|@PROJECT@|$ESCAPED|" "$APP/Contents/MacOS/MusiKitE"
chmod +x "$APP/Contents/MacOS/MusiKitE"

# Finder / Dock read the new icon
touch "$APP"

say "done: $APP"
echo "   drag it to the Dock; log of every start: ~/.musikite/launcher.log"
echo "   to remove it: delete the app (and its icon from the Dock)"
