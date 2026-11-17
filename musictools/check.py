"""
Dependency check (no third-party imports here, so it works even when
everything is missing).

    python3 -m musictools check        full report, exit code 1 if something required is missing
    musictools.check()                 same report from Jupyter (returns it as a dict)

`import musictools` refuses to start (ImportError with the report) if a
required Python package is missing.

Reference (owner's rule): the MacBook where the app works. Its versions are in
requirements-macbook.txt; every Mac is set up as the MacBook: conda's base Python
(Miniconda/Miniforge), the C libraries FluidSynth and PortAudio >= 19.7 from
conda-forge, the Python packages with pip at the MacBook's versions. The check lists
the versions that differ from the MacBook (information), and the commands print what
each one does. PortAudio < 19.7 is reported: it crashes on the microphone.
"""
import importlib.util
import os
import shutil
import sys
import sysconfig

MIN_PYTHON = (3, 10)
NEW_PYTHON = (3, 14)           # from here on, wheels of compiled packages may be missing
# module -> pip package
REQUIRED = {
    "numpy": "numpy", "pandas": "pandas", "pretty_midi": "pretty_midi", "music21": "music21",
    "pymupdf": "pymupdf", "verovio": "verovio", "svglib": "svglib", "reportlab": "reportlab",
    "PySide6": "PySide6", "fluidsynth": "pyfluidsynth",
    # ALL THE LIBRARIES OF THE PROGRAM ARE REQUIRED (owner, 2026-11-13: "the program must not
    # start anyway if not all the libraries are there"): microphone / metronome, note
    # recognition, MIDI keyboard
    "sounddevice": "sounddevice", "scipy": "scipy", "mido": "mido", "rtmidi": "python-rtmidi",
}
# needed only by Jupyter (demo notebook), not by the program
OPTIONAL = {
    "ipywidgets": ("ipywidgets", "audio_panel() in Jupyter"),
    "jupyterlab": ("jupyterlab", "the demo notebook (demo.ipynb)"),
}
# pip name -> distribution name for the version (importlib.metadata)
DIST = {"pymupdf": "PyMuPDF", "pyfluidsynth": "pyfluidsynth", "python-rtmidi": "python-rtmidi"}
SOUNDFONT_DIRS = ("/usr/share/sounds/sf2", "/usr/share/soundfonts", "/opt/homebrew/share/soundfonts",
                  "/usr/local/share/soundfonts")
BREW_INSTALL = ('/bin/bash -c "$(curl -fsSL '
                'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _missing(modules):
    return [m for m in modules if importlib.util.find_spec(m) is None]


def _externally_managed():
    """True if pip refuses to install outside a virtual environment (PEP 668)."""
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return False                                   # inside a venv
    std = sysconfig.get_paths().get("stdlib", "")
    return os.path.isfile(os.path.join(std, "EXTERNALLY-MANAGED"))


def _pip_cmd(packages):
    return f'"{sys.executable}" -m pip install ' + " ".join(packages)


LIB_DIRS = ("/opt/homebrew/opt/fluid-synth/lib", "/opt/homebrew/lib",
            "/usr/local/opt/fluid-synth/lib", "/usr/local/lib",
            "/usr/lib", "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu")
LIB_NAMES = ("libfluidsynth.dylib", "libfluidsynth.3.dylib", "libfluidsynth.so.3",
             "libfluidsynth.so")


BREW_CANDIDATES = ("/opt/homebrew/bin/brew", "/usr/local/bin/brew",
                   "~/.homebrew/bin/brew", "~/homebrew/bin/brew", "~/.linuxbrew/bin/brew",
                   "/home/linuxbrew/.linuxbrew/bin/brew")
_brew_cache = {}


def brew_executables():
    """Every Homebrew found: in the PATH, in the standard places and in a custom
    prefix (e.g. ~/.homebrew). Homebrew may be installed anywhere: never assume
    /opt/homebrew."""
    out = []
    for b in [shutil.which("brew")] + [os.path.expanduser(c) for c in BREW_CANDIDATES]:
        if b and os.path.isfile(b) and os.access(b, os.X_OK):
            b = os.path.realpath(b)
            if b not in out:
                out.append(b)
    return out


def brew_prefixes():
    """Prefixes of the Homebrew installations found ($HOMEBREW_PREFIX first): the
    folder whose lib/ and opt/<formula>/lib hold the libraries."""
    if "prefixes" in _brew_cache:
        return _brew_cache["prefixes"]
    out = []
    if os.getenv("HOMEBREW_PREFIX"):
        out.append(os.environ["HOMEBREW_PREFIX"])
    for b in brew_executables():
        p = os.path.dirname(os.path.dirname(b))          # <prefix>/bin/brew (or Homebrew/bin)
        if os.path.basename(p) == "Homebrew":            # <prefix>/Homebrew/bin/brew
            p = os.path.dirname(p)
        if p not in out:
            out.append(p)
    _brew_cache["prefixes"] = out
    return out


def brew_command():
    """How to call Homebrew in the commands printed: 'brew' if it is in the PATH,
    else its full path; None if there is no Homebrew."""
    if shutil.which("brew"):
        return "brew"
    found = brew_executables()
    return f'"{found[0]}"' if found else None


def find_fluidsynth_libs():
    """Paths of the FluidSynth C library found on disk (the running conda/venv
    prefix, every Homebrew prefix, system dirs)."""
    dirs = [os.path.join(sys.prefix, "lib")]          # conda environment first
    for pre in brew_prefixes():
        dirs += [os.path.join(pre, "opt", "fluid-synth", "lib"), os.path.join(pre, "lib")]
    dirs += LIB_DIRS
    out = []
    for d in dirs:
        for n in LIB_NAMES:
            p = os.path.realpath(os.path.join(d, n))
            if os.path.isfile(p) and p not in out:
                out.append(p)
    return out


def lib_archs(path):
    """CPU architectures of a Mach-O library ('x86_64', 'arm64'); [] if unknown."""
    import struct
    cpu = {0x01000007: "x86_64", 0x0100000C: "arm64"}
    try:
        with open(path, "rb") as f:
            head = f.read(8 + 20 * 8)
    except OSError:
        return []
    magic = struct.unpack(">I", head[:4])[0]
    if magic in (0xCAFEBABE,):                          # universal binary
        n = struct.unpack(">I", head[4:8])[0]
        return [cpu.get(struct.unpack(">I", head[8 + 20 * i:12 + 20 * i])[0], "?") for i in range(n)]
    if magic in (0xCFFAEDFE, 0xCEFAEDFE):               # thin, little endian
        return [cpu.get(struct.unpack("<I", head[4:8])[0], "?")]
    return []


def python_arch():
    import platform
    m = platform.machine()
    return "arm64" if m in ("arm64", "aarch64") else m


def prepare_fluidsynth():
    """Make pyfluidsynth find a FluidSynth library installed outside the standard
    search path (e.g. Homebrew on Apple silicon, the conda env): pyfluidsynth
    falls back to $HOMEBREW_PREFIX/lib/libfluidsynth.dylib. Returns the library used."""
    from ctypes.util import find_library
    if any(find_library(n) for n in ("fluidsynth", "libfluidsynth")):
        return None
    for lib in find_fluidsynth_libs():
        if lib.endswith(".dylib") and python_arch() in (lib_archs(lib) or [python_arch()]):
            prefix = os.path.dirname(os.path.dirname(lib))
            link = os.path.join(prefix, "lib", "libfluidsynth.dylib")
            if os.path.exists(link):
                os.environ["HOMEBREW_PREFIX"] = prefix
                return link
    return None


def _fluidsynth_library():
    """None if the FluidSynth C library loads, else the error text."""
    try:
        import fluidsynth  # noqa: F401  (pyfluidsynth loads the library at import)
        return None
    except ImportError as e:
        if importlib.util.find_spec("fluidsynth") is None:
            return "pyfluidsynth not installed"
        return str(e) or "library not found"
    except OSError as e:
        return str(e)


def _version(pip_name):
    try:
        from importlib.metadata import version
        return version(DIST.get(pip_name, pip_name))
    except Exception:
        return "?"


def _import_error(module):
    """None if the module really imports (native libraries included), else the error.
    find_spec only says it is installed: a wheel for another CPU, a missing PortAudio
    (sounddevice) or a broken Qt install are found only by importing."""
    try:
        importlib.import_module(module)
        return None
    except BaseException as e:                       # noqa: BLE001 (report everything)
        return f"{type(e).__name__}: {e}".strip()


def _find_soundfonts():
    """.sf2/.sf3 files in the user's soundfont folder and the usual system folders."""
    dirs = []
    try:
        from .progress import folder
        dirs.append(folder("soundfonts", create=False))
    except Exception:
        dirs.append(os.path.expanduser("~/musikite/soundfonts"))
    dirs += list(SOUNDFONT_DIRS)
    out = []
    for d in dirs:
        try:
            for f in sorted(os.listdir(d)):
                if f.lower().endswith((".sf2", ".sf3")):
                    out.append(os.path.join(d, f))
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- conda (as on the MacBook)
CONDA_BASES = ("~/miniforge3", "~/mambaforge", "~/miniconda3", "~/anaconda3",
               "/opt/homebrew/Caskroom/miniforge/base", "/usr/local/Caskroom/miniforge/base",
               "/opt/homebrew/Caskroom/miniconda/base", "/usr/local/Caskroom/miniconda/base",
               "/opt/miniforge3", "/opt/miniconda3")
MINIFORGE_URL = ("https://github.com/conda-forge/miniforge/releases/latest/download/"
                 "Miniforge3-$(uname)-$(uname -m).sh")


def in_conda():
    """Name of the conda environment this Python belongs to, or None."""
    if not os.path.isdir(os.path.join(sys.prefix, "conda-meta")):
        return None
    return os.environ.get("CONDA_DEFAULT_ENV") or os.path.basename(sys.prefix)


def conda_bases():
    """Conda installations found (folders with bin/conda)."""
    out = []
    exe = os.environ.get("CONDA_EXE") or shutil.which("conda")
    if exe:
        out.append(os.path.dirname(os.path.dirname(os.path.realpath(exe))))
    for c in CONDA_BASES:
        d = os.path.expanduser(c)
        if os.path.isfile(os.path.join(d, "bin", "conda")) and d not in out:
            out.append(d)
    return out


REFERENCE_FILE = "requirements-macbook.txt"   # the MacBook (where the app works) = paradigm
PORTAUDIO_MIN = (19, 7)                         # 19.6 crashes on the microphone (libc++abi)


def reference_versions():
    """{pip name (lower case): version} of REFERENCE_FILE for THIS machine
    (environment markers such as platform_machine are evaluated)."""
    import platform
    path = os.path.join(PROJECT, REFERENCE_FILE)
    out = {}
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return out
    machine = platform.machine()
    for ln in lines:
        ln = ln.split("#", 1)[0].strip()
        if not ln:
            continue
        req, _, marker = ln.partition(";")
        m = marker.strip()
        if m:                                        # only the markers used in the file
            ok = True
            mm = m.replace("'", '"')
            if "platform_machine" in mm:
                v = mm.split('"')[1] if '"' in mm else ""
                ok = (machine == v) if "==" in mm else (machine != v)
            if not ok:
                continue
        name, _, ver = req.partition("==")
        out[name.strip().lower()] = ver.strip() or None
    return out


def _pinned(pip_names):
    """pip names with the reference version (name==version) when there is one."""
    ref = reference_versions()
    return [f"{p}=={ref[p.lower()]}" if ref.get(p.lower()) else p for p in pip_names]


def conda_setup_lines():
    """The whole setup of a new Mac, as the MacBook (the reference): conda (Miniforge,
    conda-forge, open source) with its base environment, the C libraries FluidSynth
    and PortAudio >= 19.7 from conda-forge, the Python packages with pip at the
    versions of REFERENCE_FILE. Every command with what it does."""
    lines = []
    if not conda_bases():
        lines += [
            f'curl -L -o /tmp/miniforge.sh "{MINIFORGE_URL}"'
            "    # downloads the Miniforge installer (~90 MB) into /tmp; changes nothing else",
            'bash /tmp/miniforge.sh -b -p ~/miniforge3'
            "    # installs conda in ~/miniforge3 (~400 MB); undo = delete that folder",
            '~/miniforge3/bin/conda init "$(basename "$SHELL")"'
            "    # makes conda's Python the Terminal's python3 (as on the MacBook); then OPEN A "
            "NEW TERMINAL; undo = the same command with --reverse",
        ]
    lines += [
        'conda install -c conda-forge "fluidsynth" "portaudio>=19.7"'
        "    # the C libraries (audio synth, microphone); conda shows what changes and asks y/n",
        "python3 -m pip install --upgrade pip"
        "    # recent pip: ready packages instead of compiling them; seconds",
        f'python3 -m pip install -r "{os.path.join(PROJECT, REFERENCE_FILE)}"'
        "    # the Python packages at the MacBook's versions; a few minutes (PySide6 ~500 MB)",
        "cd to the project folder, then: python3 -m musictools check   and then   "
        "python3 -m musictools gui",
    ]
    return lines


def _portaudio_problem():
    """(text, command) if the PortAudio used by sounddevice is older than PORTAUDIO_MIN,
    else None."""
    try:
        import sounddevice as sd
        num, text = sd.get_portaudio_version()
        lib = getattr(sd, "_libname", "") or ""
    except Exception:
        return None
    major, minor = (num >> 16) & 0xFF, (num >> 8) & 0xFF
    if (major, minor) >= PORTAUDIO_MIN:
        return None
    where = os.path.realpath(lib) if lib and os.path.exists(lib) else lib
    msg = (f"PortAudio {major}.{minor} ({where}) is too old: opening the microphone CRASHES the "
           "program ('libc++abi: terminating / Abort trap: 6'); 19.7 or newer is needed")
    if in_conda() or (lib and sys.prefix in os.path.realpath(lib)):
        cmd = ('conda install -c conda-forge "portaudio>=19.7"'
               "    # updates PortAudio in this conda environment (FluidSynth keeps working); "
               "conda shows what changes and asks y/n; undo = conda install portaudio=19.6.0")
    else:
        cmd = ("python3 -m pip install --force-reinstall sounddevice"
               "    # reinstalls sounddevice (it brings its own recent PortAudio); seconds")
    return msg, cmd


def report(deep=True):
    """Dict: errors (the program cannot start), warnings (some functions will not work),
    info (what was found, with versions) and the commands to run, in order.
    deep=True: every package is really imported (native libraries checked too) and
    the audio / MIDI devices are listed.
    Reference: the MacBook (REFERENCE_FILE). Setup as there: conda's base Python, the C
    libraries (FluidSynth, PortAudio >= 19.7) from conda-forge, the Python packages with
    pip at the reference versions."""
    errors, warnings, info, commands = [], [], [], []
    mac = sys.platform == "darwin"
    py = sys.executable
    env = in_conda()

    info.append(f"Python {sys.version.split()[0]} ({python_arch()}): {py}")
    if env:
        info.append(f"conda environment: {env} ({sys.prefix})")
    elif sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        info.append(f"virtual environment: {sys.prefix}")
    if conda_bases():
        info.append(f"conda: {', '.join(conda_bases())}")
    if brew_prefixes():
        info.append(f"Homebrew: {', '.join(brew_prefixes())}")

    if sys.version_info < MIN_PYTHON:
        system_py = mac and py.startswith(("/usr/bin/", "/Library/Developer/CommandLineTools/",
                                            "/Applications/Xcode"))
        errors.append(f"Python {sys.version.split()[0]} is too old: "
                      f"{'.'.join(map(str, MIN_PYTHON))} or newer is needed (verovio, PySide6…)"
                      + (" — this is the macOS system Python: do not install packages in it"
                         if system_py else ""))
        commands += conda_setup_lines()
        return dict(ok=False, python=py, errors=errors, warnings=warnings, info=info,
                    commands=commands)
    if sys.version_info >= NEW_PYTHON and not env:
        warnings.append(f"Python {sys.version.split()[0]} is very new: some compiled packages "
                        f"(verovio, PySide6, scipy…) may have no ready wheel yet and pip tries "
                        f"to compile them, failing: use the conda setup")

    # ---- required Python packages (installed AND importable)
    req_missing = _missing(REQUIRED)
    broken = {}
    if deep:
        for m in REQUIRED:
            if m in req_missing or m == "fluidsynth":      # fluidsynth: library checked below
                continue
            err = _import_error(m)
            if err:
                broken[m] = err + (" (PortAudio library missing?)" if m == "sounddevice" else "")
            else:
                info.append(f"ok  {REQUIRED[m]} {_version(REQUIRED[m])}")
    if req_missing:
        errors.append("Python packages missing: " + ", ".join(REQUIRED[m] for m in req_missing))
    for m, err in broken.items():
        errors.append(f"{REQUIRED[m]} is installed but does not load: {err}")

    # ---- FluidSynth C library: look for it on disk, independently of pyfluidsynth
    libs = find_fluidsynth_libs()
    arch = python_arch()
    fs_problem = False
    if not libs:
        fs_problem = True
        errors.append("FluidSynth library (audio) not found"
                      + (f" (searched in this Python and in the Homebrew prefixes "
                         f"{', '.join(brew_prefixes())})" if brew_prefixes() else ""))
    elif "fluidsynth" not in req_missing:
        prepare_fluidsynth()
        err = _fluidsynth_library()
        if err:
            fs_problem = True
            good = [l for l in libs if arch in (lib_archs(l) or [arch])]
            if mac and not good:
                found = ", ".join(f"{l} ({'/'.join(lib_archs(l)) or '?'})" for l in libs)
                errors.append(f"FluidSynth library found but for another CPU architecture: {found}; "
                              f"this Python is {arch}")
            else:
                errors.append(f"FluidSynth library found ({', '.join(libs)}) but pyfluidsynth "
                              f"cannot load it: {err}")
        else:
            info.append(f"ok  FluidSynth library {libs[0]}; pyfluidsynth {_version('pyfluidsynth')}")

    # ---- optional packages
    opt_missing = _missing(OPTIONAL)
    opt_broken = []
    for m in OPTIONAL:
        pip_name, what = OPTIONAL[m]
        if m in opt_missing:
            warnings.append(f"{pip_name} missing: {what}")
            continue
        err = _import_error(m) if deep and m not in ("jupyterlab",) else None
        if err:
            hint = " (PortAudio library missing?)" if m == "sounddevice" else ""
            warnings.append(f"{pip_name} is installed but does not load: {err}{hint} — {what}")
            opt_broken.append(pip_name)
        elif deep:
            info.append(f"ok  {pip_name} {_version(pip_name)}")

    # ---- PortAudio (microphone): the version sounddevice really uses
    pa = None
    if deep and "sounddevice" not in req_missing and "sounddevice" not in broken:
        pa = _portaudio_problem()
        if pa:
            warnings.append(pa[0])

    # ---- versions different from the reference (the MacBook): information only
    ref = reference_versions()
    if deep and ref:
        diff = []
        for name, want in ref.items():
            if not want:
                continue
            have = _version(name)
            if have not in ("?", want):
                diff.append(f"{name} {have} (MacBook {want})")
        info.append("versions different from the MacBook: " + (", ".join(diff) if diff else "none"))

    # ---- the commands
    need = [REQUIRED[m] for m in req_missing] + [OPTIONAL[m][0] for m in opt_missing]
    redo = [REQUIRED[m] for m in broken] + opt_broken
    libs = (["fluidsynth"] if fs_problem else [])
    anything = bool(need or redo or fs_problem or pa)
    if env:                                            # conda (as the MacBook): fix it here
        if libs:
            commands.append("conda install -c conda-forge " + " ".join(f'"{l}"' for l in libs)
                            + ' "portaudio>=19.7"    # the C libraries into this conda '
                              "environment; conda shows what changes and asks y/n")
        elif pa:
            commands.append(pa[1])
        if need:
            commands.append("python3 -m pip install " + " ".join(_pinned(need))
                            + "    # the missing packages, at the MacBook's versions; seconds "
                              "to minutes; undo = pip uninstall")
        if redo:
            commands.append("python3 -m pip install --force-reinstall " + " ".join(_pinned(redo))
                            + "    # reinstall what does not load")
    elif anything:
        setup = (["As on the MacBook (the reference): conda's Python + FluidSynth and PortAudio "
                  "from conda-forge + the packages at the MacBook's versions:"]
                 + ["  " + l for l in conda_setup_lines()])
        quick = []                                     # only small pieces missing: in THIS Python
        if not errors and not _externally_managed():
            if need:
                quick.append(f'"{py}" -m pip install ' + " ".join(_pinned(need))
                             + "    # the missing packages, at the MacBook's versions")
            if redo:
                quick.append(f'"{py}" -m pip install --force-reinstall ' + " ".join(_pinned(redo))
                             + "    # reinstall what does not load")
            if pa:
                quick.append(pa[1])
        if quick:
            commands.append("In THIS Python:")
            commands += ["  " + l for l in quick]
            commands.append("OR, " + setup[0][0].lower() + setup[0][1:])
            commands += setup[1:]
        else:
            commands += setup

    # ---- files of the project
    for f, what in (("scoreread.py", "PDF reading (PDF → MIDI, fingerings)"),
                    ("data/TrumpetFing.ttf", "trumpet fingerings on PDFs")):
        path = os.path.join(PROJECT, "musictools", f)
        if not os.path.isfile(path):
            warnings.append(f"musictools/{f} not found: {what} disabled")
        elif os.path.getsize(path) == 0:
            warnings.append(f"musictools/{f} is EMPTY (incomplete copy / cloud file not "
                            f"downloaded): {what} disabled; copy it again")
    for f in ("Leland.ttf", "icon.png"):
        path = os.path.join(PROJECT, "musictools", "data", f)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            errors.append(f"musictools/data/{f} missing or empty: copy the whole musictools folder")
    try:
        from .pdf import digit_font
        if digit_font() is None:
            warnings.append("no font for the fingering digits (Arial, Helvetica, DejaVu Sans): "
                            "pass font= to Pdf.fingering()")
    except Exception:
        pass

    # ---- devices (only if the libraries load)
    if deep and "sounddevice" not in req_missing and _import_error("sounddevice") is None:
        try:
            from .realtime import output_devices, input_devices
            outs, ins = output_devices(), input_devices()
            info.append(f"audio outputs: {', '.join(outs) or 'none'}")
            info.append(f"audio inputs (microphones): {', '.join(ins) or 'none'}")
            if not outs:
                warnings.append("no audio output device found")
            if not ins:
                warnings.append("no microphone found: Read & play / Listen & repeat with the "
                                "trumpet will not work (MIDI keyboard still does)")
            elif mac:
                info.append("first use of the microphone: macOS asks the permission for the app "
                            "that runs Python (Terminal, VS Code…); if denied the recording is "
                            "silent: System Settings > Privacy & Security > Microphone")
        except Exception as e:
            warnings.append(f"audio devices cannot be listed: {type(e).__name__}: {e}")
    if deep and not ({"mido", "rtmidi"} & set(req_missing)) and _import_error("rtmidi") is None:
        try:
            from .midiin import input_names
            ports = input_names(computer=False)
            info.append(f"MIDI inputs: {', '.join(ports) or 'none connected (needed only for the keyboard)'}")
        except Exception as e:
            warnings.append(f"MIDI ports cannot be listed: {type(e).__name__}: {e}")

    # ---- soundfont
    sf2 = None
    try:
        from .progress import settings, current_user, last_user
        sf2 = settings(current_user() or last_user()).get("sf2")
    except Exception:
        pass
    if sf2 and os.path.isfile(sf2):
        info.append(f"ok  soundfont {sf2}")
    else:
        found = _find_soundfonts()
        what = f"the soundfont set ({sf2}) does not exist on this computer" if sf2 else "no soundfont set"
        if found:
            warnings.append(f"{what}: found {found[0]}" + (f" (+{len(found) - 1} more)" if len(found) > 1 else "")
                            + " — choose it in Settings > Soundfont (no sound until then)")
        else:
            warnings.append(f"{what}: no sound (playback, clicks, Listen & repeat) until one is "
                            "chosen. A General MIDI .sf2 is needed (e.g. FluidR3_GM.sf2 or "
                            "GeneralUser GS, free): put it in ~/musikite/soundfonts and choose it "
                            "in Settings > Soundfont")

    return dict(ok=not errors, python=py, errors=errors, warnings=warnings, info=info,
                commands=commands)


def text(r=None, verbose=False):
    """The report as text. verbose: also what was found (versions, devices)."""
    r = r or report()
    lines = [f"MusiKitE dependency check  (Python: {r['python']})"]
    if verbose:
        lines += [f"  {i}" for i in r.get("info", [])]
    lines += [f"  MISSING  {e}" for e in r["errors"]]
    lines += [f"  warning  {w}" for w in r["warnings"]]
    if r["ok"] and not r["warnings"]:
        lines.append("  RESULT: all OK")
    elif r["ok"]:
        lines.append("  RESULT: the program starts; the warnings above say what will not work")
    else:
        lines.append("  RESULT: the program cannot start: run the commands below, in this order")
    if r["commands"]:
        # the explanation goes on its own line, NOT as a shell comment: zsh (macOS) does not
        # accept '#' comments on the command line by default, so a pasted line must be pure
        lines.append("Commands (Terminal), in this order; copy only the command lines, the "
                     "lines starting with '->' say what each one does:")
        for c in r["commands"]:
            cmd, _, note = c.partition("    # ")
            ind = cmd[:len(cmd) - len(cmd.lstrip())]
            lines.append(f"  {cmd}")
            if note:
                lines.append(f"  {ind}    -> {note}")
    return "\n".join(lines)


def check(verbose=True):
    r = report()
    if verbose:
        print(text(r, verbose=True))
    return r


def require():
    """Called by `import musictools`: stop with a clear message if required
    Python packages are missing (fast: does not import them)."""
    if _missing(REQUIRED) or sys.version_info < MIN_PYTHON:
        msg = text(report(deep=False))
        if sys.argv and sys.argv[0] == "-m":       # python3 -m musictools …: no traceback
            print(msg, file=sys.stderr)
            raise SystemExit(1)
        raise ImportError("\n" + msg)
