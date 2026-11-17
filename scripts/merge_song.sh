#!/bin/bash
# Merge all the MIDI files of one song (English version of the old fondi_midi.sh, owner
# 2026-11-08): every *.mid / *.midi under the current folder whose name contains TEXT
# (case-insensitive) is merged into OUTPUT.mid by merge_midi.py (same tempo map required:
# otherwise an error and nothing written). The output file itself is never an input.
#
#   cd ".../banda/parti";  bash /path/to/musictools_project/scripts/merge_song.sh misirlou "Misirlou - all parts"

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 TEXT OUTPUT"
    exit 1
fi

text="$1"
output="$2"
case "$output" in
    *.mid|*.midi) ;;
    *) output="$output.mid" ;;
esac
script="$(cd "$(dirname "$0")" && pwd)/merge_midi.py"

tmpfile=$(mktemp)
find . -type f \( -iname "*${text}*.mid" -o -iname "*${text}*.midi" \) -print0 |
    sort -z > "$tmpfile"

files=()
while IFS= read -r -d '' file; do
    [ "$(basename "$file")" = "$(basename "$output")" ] && continue
    files[${#files[@]}]="$file"
done < "$tmpfile"
rm -f "$tmpfile"

if [ "${#files[@]}" -eq 0 ]; then
    echo "No MIDI file found containing: $text"
    exit 1
fi

echo "MIDI files found: ${#files[@]}"
python3 "$script" "${files[@]}" "$output"
