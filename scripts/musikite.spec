# PyInstaller recipe of the Mac app MusiKitE.app (owner, 2026-11-17). Run by
# scripts/build_mac_app.sh, once per processor, with the Python of a build conda
# environment (Apple silicon or Intel): the libraries of THAT environment go into the app.
# Environment variables set by the script:
#   MUSIKITE_ICNS     icon (.icns) of the app (optional)
#   MUSIKITE_VERSION  version shown by Finder (e.g. 2026.11.17)
#   MUSIKITE_ARCH     arm64 or x86_64
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

PROJECT = os.path.dirname(SPECPATH)                 # noqa: F821 (SPECPATH: PyInstaller)
ARCH = os.environ.get("MUSIKITE_ARCH") or None
VERSION = os.environ.get("MUSIKITE_VERSION", "0")

datas = [
    (os.path.join(PROJECT, "musictools", "data"), os.path.join("musictools", "data")),
    # check.py looks for these files in the package folder (warnings otherwise)
    (os.path.join(PROJECT, "musictools", "scoreread.py"), "musictools"),
    (os.path.join(PROJECT, "requirements-macbook.txt"), "."),
    # the manual (Help > Manual, gui/manual.py) and the licence it links to
    (os.path.join(PROJECT, "docs"), "docs"),
    (os.path.join(PROJECT, "LICENSE"), "."),
]
binaries = []
hiddenimports = collect_submodules("musictools") + [
    "fluidsynth", "sounddevice", "_sounddevice_data", "mido.backends.rtmidi", "rtmidi",
    "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtPrintSupport",
]

for pkg in ("verovio",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("pretty_midi")
datas += collect_data_files("reportlab")
datas += collect_data_files("music21", excludes=["corpus/**"])   # the corpus is not used
datas += collect_data_files("_sounddevice_data", include_py_files=False)

# FluidSynth C library of the build environment (conda-forge) -> Contents/Frameworks/lib,
# under the name pyfluidsynth asks for ($HOMEBREW_PREFIX/lib/libfluidsynth.dylib, set by
# musikite_app.py); PyInstaller also takes the libraries it needs (glib, libsndfile…)
import shutil
import tempfile

STAGE = tempfile.mkdtemp(prefix="musikite-stage-")
lib = os.path.join(sys.prefix, "lib", "libfluidsynth.dylib")
if not os.path.exists(lib):
    raise SystemExit(f"FluidSynth not found in {sys.prefix}/lib: "
                     "conda install -c conda-forge fluidsynth")
shutil.copy2(os.path.realpath(lib), os.path.join(STAGE, "libfluidsynth.dylib"))
binaries.append((os.path.join(STAGE, "libfluidsynth.dylib"), "lib"))

# the soundfont GeneralUser GS and its licence are in musictools/data (copied above with the
# whole folder): the app's default when the user has chosen none (gui/mainwindow.py)

a = Analysis(                                         # noqa: F821
    [os.path.join(PROJECT, "scripts", "musikite_app.py")],
    pathex=[PROJECT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "IPython", "ipywidgets", "jupyterlab", "notebook", "ipykernel"],
    noarchive=False,
)
pyz = PYZ(a.pure)                                     # noqa: F821
exe = EXE(                                            # noqa: F821
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MusiKitE",
    console=False,
    target_arch=ARCH,
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MusiKitE")   # noqa: F821
app = BUNDLE(                                         # noqa: F821
    coll,
    name="MusiKitE.app",
    icon=os.environ.get("MUSIKITE_ICNS") or None,
    bundle_identifier="org.musikite.app",
    version=VERSION,
    info_plist={
        "CFBundleName": "MusiKitE",
        "CFBundleDisplayName": "MusiKitE",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription":
            "MusiKitE listens to your instrument to check the exercises you play.",
        "LSMinimumSystemVersion": "11.0",
    },
)
