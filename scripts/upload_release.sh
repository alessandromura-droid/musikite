#!/bin/bash
# upload_release.sh — uploads ~/Desktop/MusiKitE-arm64.dmg and/or MusiKitE-intel.dmg to the
# GitHub Releases of MusiKitE with curl (no gh): release v<version> created if missing, an
# asset with the same name replaced. Token: the one git saved in the Keychain, else asked
# (not stored). The token needs Contents: Read and write on the repository.
#
#   bash scripts/upload_release.sh
#
# It changes nothing on the Mac (the dmg are only mounted read-only to read the version);
# undo = delete the release on the Releases page.
set -euo pipefail

REPO="alessandromura-droid/musikite"
API="https://api.github.com/repos/$REPO"
DESK="$HOME/Desktop"
TMP="$(mktemp -d -t musikite-release)"
trap 'rm -rf "$TMP"' EXIT

# ---- token: git's credential in the Keychain, else typed (not stored)
TOKEN="$(printf 'protocol=https\nhost=github.com\n\n' | git credential-osxkeychain get 2>/dev/null \
         | sed -n 's/^password=//p')"
if [ -z "$TOKEN" ]; then
    read -r -s -p "GitHub token: " TOKEN; echo
fi
[ -n "$TOKEN" ] || { echo "ERROR: no token"; exit 1; }
AUTH=(-H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json"
      -H "X-GitHub-Api-Version: 2022-11-28")

# ---- a field of a JSON file (python3 of conda)
json() { python3 -c 'import json,sys; d=json.load(open(sys.argv[2])); print(eval(sys.argv[1]))' "$1" "$2"; }

# ---- version of the app inside a dmg (mounted read-only, then detached)
version_of() {
    local mnt="$TMP/mnt"
    mkdir -p "$mnt"
    hdiutil attach -readonly -nobrowse -quiet -mountpoint "$mnt" "$1"
    /usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" \
        "$mnt/MusiKitE.app/Contents/Info.plist"
    hdiutil detach -quiet "$mnt"
}

FOUND=0
for dmg in "$DESK/MusiKitE-arm64.dmg" "$DESK/MusiKitE-intel.dmg"; do
    [ -f "$dmg" ] || continue
    FOUND=1
    NAME="$(basename "$dmg")"
    VERSION="$(version_of "$dmg")"
    TAG="v$VERSION"
    echo "== $NAME: MusiKitE $VERSION -> release $TAG"

    # the release: existing, else created
    CODE="$(curl -s -o "$TMP/rel.json" -w '%{http_code}' "${AUTH[@]}" "$API/releases/tags/$TAG")"
    if [ "$CODE" != "200" ]; then
        BODY="$(python3 -c 'import json,sys; print(json.dumps({"tag_name": sys.argv[1],
            "target_commitish": "main", "name": "MusiKitE " + sys.argv[2],
            "body": "MusiKitE " + sys.argv[2] + " for macOS. MusiKitE-arm64.dmg = Apple silicon, "
                    "MusiKitE-intel.dmg = Intel. The app is not signed: open it the first time "
                    "with right-click > Open. Manual: docs/ in the repository, or Help > Manual "
                    "in the app."}))' "$TAG" "$VERSION")"
        CODE="$(curl -s -o "$TMP/rel.json" -w '%{http_code}' "${AUTH[@]}" \
                -X POST "$API/releases" -d "$BODY")"
        [ "$CODE" = "201" ] || { echo "ERROR creating the release ($CODE):"; cat "$TMP/rel.json"; exit 1; }
        echo "   release $TAG created"
    fi
    RID="$(json 'd["id"]' "$TMP/rel.json")"

    # an asset with the same name: deleted first
    OLD="$(json "next((a['id'] for a in d['assets'] if a['name'] == '$NAME'), '')" "$TMP/rel.json")"
    if [ -n "$OLD" ]; then
        curl -s -o /dev/null "${AUTH[@]}" -X DELETE "$API/releases/assets/$OLD"
        echo "   old $NAME removed from the release"
    fi

    # upload
    echo "   uploading $NAME ($(du -h "$dmg" | cut -f1))…"
    CODE="$(curl -s -o "$TMP/up.json" -w '%{http_code}' "${AUTH[@]}" \
            -H "Content-Type: application/x-apple-diskimage" --data-binary @"$dmg" \
            "https://uploads.github.com/repos/$REPO/releases/$RID/assets?name=$NAME")"
    [ "$CODE" = "201" ] || { echo "ERROR uploading ($CODE):"; cat "$TMP/up.json"; exit 1; }
    echo "   done"
done
[ "$FOUND" = 1 ] || { echo "ERROR: no MusiKitE-*.dmg on the Desktop"; exit 1; }
echo "https://github.com/$REPO/releases"
