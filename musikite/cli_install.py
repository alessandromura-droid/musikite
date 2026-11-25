"""
COMMAND-LINE TOOL OF THE MAC APP (owner, 2026-11-24): Help > Install command-line tool…
(as VS Code's "Install 'code' command in PATH"). The app (MusiKitE.app, made by
scripts/build_mac_app.sh) carries
  Contents/Resources/bin/musikite      a bash script: exec Contents/MacOS/MusiKitE "$@"
  Contents/Resources/man/man1/musikite.1
and its executable runs the command line when it gets arguments (scripts/musikite_app.py).
Installing = ONE line at the end of ~/.zshrc, shown and confirmed by the user:
  export PATH="<app>/Contents/Resources/bin:$PATH"  # MusiKitE app: the command musikite
with bin/ in the PATH, `man musikite` finds ../man too (macOS man). Removing = the line
deleted. Only for the app in /Applications (an app in Downloads moves); at every start
`moved()` tells if the line points to another place (the app was moved). No Qt.
"""
import os
import subprocess
import sys

MARKER = "# MusiKitE app: the command musikite"
ZSHRC = os.path.expanduser("~/.zshrc")


def is_app():
    """Running as the packaged Mac app (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def app_bin():
    """<app>/Contents/Resources/bin of the running app (None from the source code)."""
    if not is_app():
        return None
    contents = os.path.dirname(os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.join(contents, "Resources", "bin")


def app_path():
    b = app_bin()
    return None if b is None else os.path.dirname(os.path.dirname(os.path.dirname(b)))


def in_applications():
    p = app_path()
    return bool(p) and (p.startswith("/Applications/") or
                        p.startswith(os.path.expanduser("~/Applications/")))


def line(bin_dir=None):
    return f'export PATH="{bin_dir or app_bin()}:$PATH"  {MARKER}'


def _lines():
    try:
        with open(ZSHRC, encoding="utf-8") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def installed_path():
    """The bin folder written in the MusiKitE line of ~/.zshrc (None: no line)."""
    for ln in _lines():
        if MARKER in ln and 'PATH="' in ln:
            return ln.split('PATH="', 1)[1].split(":", 1)[0]
    return None


def installed():
    return installed_path() is not None


def moved():
    """The line points to another app place (the app was moved): that old place, else None."""
    p, b = installed_path(), app_bin()
    return p if (p and b and os.path.realpath(p) != os.path.realpath(b)) else None


def other_command():
    """A `musikite` a new Terminal finds that is NOT this app's (e.g. the one of
    install.sh in the conda base): its path, else None."""
    try:
        out = subprocess.run(["/bin/zsh", "-ilc", "command -v musikite"], capture_output=True,
                             text=True, timeout=8, stdin=subprocess.DEVNULL).stdout
    except Exception:
        return None
    found = out.strip().splitlines()[-1] if out.strip() else ""
    b = app_bin()
    if not found or (b and os.path.realpath(os.path.dirname(found)) == os.path.realpath(b)):
        return None
    return found


def install():
    """The line at the end of ~/.zshrc (an old MusiKitE line replaced). Returns the line."""
    if not is_app():
        raise RuntimeError("only the Mac app installs this command (from the source code: "
                           "./install.sh)")
    if not in_applications():
        raise RuntimeError("move MusiKitE to Applications first (an app elsewhere may move)")
    keep = [ln for ln in _lines() if MARKER not in ln]
    while keep and not keep[-1].strip():
        keep.pop()
    new = line()
    with open(ZSHRC, "w", encoding="utf-8") as f:
        f.write("\n".join(keep + ["", new]) + "\n")
    return new


def uninstall():
    """The MusiKitE line deleted from ~/.zshrc (nothing else changed)."""
    ls = _lines()
    keep = [ln for ln in ls if MARKER not in ln]
    if len(keep) == len(ls):
        return False
    with open(ZSHRC, "w", encoding="utf-8") as f:
        f.write("\n".join(keep) + ("\n" if keep else ""))
    return True
