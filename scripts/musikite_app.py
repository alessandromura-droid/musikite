"""Entry point of the packaged Mac app (MusiKitE.app, made by scripts/build_mac_app.sh with
PyInstaller): sets up the libraries inside the app, then opens the main window as
`python3 -m musictools gui`. Not used when running from the project folder."""
import os
import sys

if getattr(sys, "frozen", False):
    # pyfluidsynth looks for $HOMEBREW_PREFIX/lib/libfluidsynth.dylib when the system
    # search finds nothing: the app carries the library in <app>/Contents/Frameworks/lib
    os.environ["HOMEBREW_PREFIX"] = sys._MEIPASS

from musictools.__main__ import main  # noqa: E402

main(["gui"])
