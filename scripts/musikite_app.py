"""Entry point of the packaged Mac app (MusiKitE.app, made by scripts/build_mac_app.sh with
PyInstaller): sets up the libraries inside the app, then
- without arguments (Finder, Dock): opens the main window, as `python3 -m musikite gui`;
- with arguments (the command `musikite` of the app, Contents/Resources/bin/musikite,
  owner 2026-11-24): the command line, as `python3 -m musikite ARGS…`.
Not used when running from the project folder."""
import os
import sys

if getattr(sys, "frozen", False):
    # pyfluidsynth looks for $HOMEBREW_PREFIX/lib/libfluidsynth.dylib when the system
    # search finds nothing: the app carries the library in <app>/Contents/Frameworks/lib
    os.environ["HOMEBREW_PREFIX"] = sys._MEIPASS

from musikite.__main__ import main  # noqa: E402

# old macOS versions pass "-psn_…" (process serial number) when the app is opened by Finder
ARGS = [a for a in sys.argv[1:] if not a.startswith("-psn")]
main(ARGS or ["gui"])
