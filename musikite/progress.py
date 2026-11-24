"""
Users, their settings and their results on disk. Every user is like a separate
installation of MusiKitE (a teacher creates one user per pupil):

    ~/.musikite/app.json                     list of users, last user
    ~/.musikite/settings.json                settings when no user is selected
    ~/.musikite/users/<user>/settings.json   settings of the user (audio, soundfont,
                                             exercises, folders, ...)
    ~/.musikite/users/<user>/progress.json   every answer and every exercise block
    ~/.musikite/users/<user>/workspace.json  last workspace (saved at exit / user change)

The visible folders for the user's files (MIDI, PDF, workspaces, ...) are shared
by all users: defaults ~/musikite/<kind>, changeable per user (folder(), set_folder()).
Data of the old ~/.musictools is copied once into this layout (the old folder is
left as it is).

DATA FOLDER (owner, 2026-11-18: everything in a shared Dropbox folder, the same user opened
on two MacBooks = exactly the same experience): users, settings, results, diary and
workspaces may live in a folder chosen in Settings > Folders (`set_data_home`); each
computer only keeps WHERE it is in ~/.musikite/location.json. Paths saved in settings and
workspaces are PORTABLE (`portable` / `local`): inside the data folder "@data/…", inside the
home "~/…", so the same Dropbox folder works on both Macs. A user open on another computer
is reported (`lock_user` / `user_open_elsewhere`: users/<user>/open.json, refreshed every
minute while open). User names are UNIQUE (case and file-name safe: "Ann" = "ann").

Python counterpart of MATLAB mylog.m (~/myeartraining.log): there each
session appended date, result (%) and number of exercises per user; here
every single answer is stored, so results per session, per day and per
interval can all be computed afterwards.

    set_current_user('Teresa')      # settings() / save_setting() now act on Teresa
    p = Progress()
    p.add_user('Teresa')
    p.record('Teresa', 'intervals', session, asked=7, answered=7, mode='harmonic')
    p.sessions('Teresa', 'intervals')   # DataFrame: one row per session
    p.by_item('Teresa', 'intervals')    # DataFrame: accuracy per interval
"""
import datetime as _dt
import json
import os
import re
import threading

APP_HOME = os.path.expanduser("~/.musikite")          # this computer (logs, location)
LOCATION_FILE = os.path.join(APP_HOME, "location.json")
APP_FILE = os.path.join(APP_HOME, "app.json")         # app.json of the default data folder
LOCK_FRESH_S = 180                                     # a lock older than this: computer gone
LEGACY_HOME = os.path.expanduser("~/.musictools")
FILES_HOME = os.path.expanduser("~/musikite")
FOLDERS = ("workspaces", "exercises", "midi", "pdf", "scores", "audio", "results", "soundfonts")
FOLDER_LABELS = dict(workspaces="Workspaces", exercises="Exercises", midi="MIDI files",
                     pdf="PDF files", scores="Scores (MusicXML)", audio="Audio (WAV)",
                     results="Exercise results", soundfonts="Soundfonts")
NO_USER = ""
_current = {"user": None}
_lock = threading.Lock()


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)                      # never leaves a half-written file


def _safe(name):
    """Folder name of a user."""
    s = re.sub(r"[^\w\- .]", "_", name).strip(" .") or "_"
    return s


# ---------------------------------------------------------------- data folder
def data_home():
    """Folder of users, settings, results (default ~/.musikite; Settings > Folders)."""
    loc = _load(LOCATION_FILE, {}).get("data_dir")
    if loc:
        p = local(loc, data=False)
        if os.path.isdir(p):
            return p
    return APP_HOME


def app_file():
    return os.path.join(data_home(), "app.json")


def set_data_home(path):
    """Use `path` as the data folder from now on. If it already holds MusiKitE data (the
    other computer put it there) it is used as it is; otherwise the current data (users,
    settings, results, diary, workspaces) is COPIED into it (the old copy stays where it
    is). None / '' = back to ~/.musikite. Returns a message."""
    import shutil
    old = data_home()
    if not path:
        _save(LOCATION_FILE, {"data_dir": None})
        return f"data folder: {APP_HOME} (default)"
    new = os.path.abspath(os.path.expanduser(path))
    if new == old:
        return f"data folder unchanged: {new}"
    os.makedirs(new, exist_ok=True)
    if os.path.isfile(os.path.join(new, "app.json")):
        msg = f"data folder: {new} (its users and results are used; nothing copied)"
    else:
        for name in ("app.json", "settings.json", "progress.json"):
            src = os.path.join(old, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(new, name))
        if os.path.isdir(os.path.join(old, "users")):
            shutil.copytree(os.path.join(old, "users"), os.path.join(new, "users"),
                            dirs_exist_ok=True)
        if not os.path.isfile(os.path.join(new, "app.json")):
            _save(os.path.join(new, "app.json"), {"users": [], "last_user": None})
        msg = f"data folder: {new} (users and results copied from {old}; the old copy stays)"
    _save(LOCATION_FILE, {"data_dir": portable(new, data=False)})
    return msg


def portable(path, data=True):
    """A path written so that it works on another computer: inside the data folder
    '@data/…', inside the home '~/…' (Dropbox in the same place under both homes)."""
    if not path or not isinstance(path, str) or path.startswith(("@data", "~")):
        return path
    p = os.path.abspath(path)
    if data:
        d = data_home()
        if p == d or p.startswith(d + os.sep):
            return "@data" + p[len(d):]
    home = os.path.expanduser("~")
    if p == home or p.startswith(home + os.sep):
        return "~" + p[len(home):]
    return path


def local(path, data=True):
    """The path on this computer of a portable path."""
    if not path or not isinstance(path, str):
        return path
    if data and path.startswith("@data"):
        return os.path.join(data_home(), path[len("@data"):].lstrip("/\\"))
    return os.path.expanduser(path)


def user_dir(user=None):
    """Hidden folder of a user (None: the current one; no user: the data folder)."""
    user = current_user() if user is None else user
    if not user:
        return data_home()
    return os.path.join(data_home(), "users", _safe(user))


# ---------------------------------------------------------------- app level
def _app():
    _migrate()
    return _load(app_file(), {"users": [], "last_user": None})


def _save_app(d):
    _save(app_file(), d)


_NAME_RE = re.compile(r"[A-Za-z0-9 ]+")


def valid_user_name(name):
    """None if the name is allowed, else why not (owner, 2026-11-18: only lower / upper
    case letters, digits and spaces)."""
    n = (name or "").strip()
    if not n:
        return "type a name"
    if not _NAME_RE.fullmatch(n):
        return "a name can have only letters (A-Z, a-z), digits and spaces"
    return None


def same_user(name, users_list=None):
    """The existing user with the same name ignoring case and the file-name rules
    ("Ann" = "ann" = "Ann?"), or None (owner, 2026-11-18: names must be different)."""
    key = _safe(name.strip()).casefold()
    for u in (users() if users_list is None else users_list):
        if _safe(u).casefold() == key:
            return u
    return None


# ---------------------------------------------------------------- open on another computer
def _host():
    import socket
    try:
        return socket.gethostname()
    except Exception:
        return "?"


def lock_user(name):
    """Mark a user as open on this computer (refreshed every minute by the app)."""
    if not name:
        return
    import time
    try:
        _save(os.path.join(user_dir(name), "open.json"), {"host": _host(), "time": time.time()})
    except Exception:
        pass


def unlock_user(name):
    if not name:
        return
    p = os.path.join(user_dir(name), "open.json")
    try:
        if _load(p, {}).get("host") == _host():
            os.remove(p)
    except Exception:
        pass


def user_open_elsewhere(name):
    """Name of the other computer where the user is open now, or None."""
    import time
    d = _load(os.path.join(user_dir(name), "open.json"), {}) if name else {}
    if d.get("host") and d.get("host") != _host() and \
            time.time() - float(d.get("time", 0)) < LOCK_FRESH_S:
        return d["host"]
    return None


def users():
    return list(_app()["users"])


def last_user():
    return _app().get("last_user")


def deleted_users():
    """Users removed from the list (Settings > Users > Delete user) whose folder is still in
    the data folder: New user… > Recover user puts one back (owner, 2026-11-20)."""
    root = os.path.join(data_home(), "users")
    try:
        names = sorted(os.listdir(root), key=str.casefold)
    except OSError:
        return []
    mine = {_safe(u).casefold() for u in users()}
    return [n for n in names if not n.startswith(".") and os.path.isdir(os.path.join(root, n))
            and n.casefold() not in mine]


def recover_user(name):
    """Put ONE deleted user back in the list, with his folder and data as they were."""
    if name not in deleted_users():
        raise ValueError(f"no deleted user named '{name}'")
    d = _app()
    other = same_user(name, d["users"])
    if other is not None:
        raise ValueError(f"a user named '{other}' already exists")
    d["users"].append(name)
    _save_app(d)
    return name


def set_current_user(name):
    """Select the user whose settings and data are used from now on."""
    _current["user"] = name or None
    try:
        from .instruments import reset_current
        reset_current()                        # the new user's preferred instrument
    except Exception:
        pass
    if name:
        d = _app()
        if name not in d["users"] and same_user(name, d["users"]) is None:
            d["users"].append(name)
        d["last_user"] = name
        _save_app(d)
    return name


def current_user():
    return _current["user"]


# ---------------------------------------------------------------- settings
def settings_path(user=None):
    return os.path.join(user_dir(user), "settings.json")


def settings(user=None):
    """Settings of the current user (or of `user`)."""
    _migrate()
    return _load(settings_path(user), {})


def save_setting(key, value, user=None):
    with _lock:
        s = settings(user)
        s[key] = value
        _save(settings_path(user), s)


def folder(kind, create=True):
    """Default folder of a kind of file (FOLDERS) for the current user."""
    if kind not in FOLDERS:
        raise ValueError(f"unknown folder kind {kind}; known: {', '.join(FOLDERS)}")
    path = local(settings().get("folders", {}).get(kind)) or os.path.join(FILES_HOME, kind)
    path = os.path.expanduser(path)
    if create:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            pass
    return path


def set_folder(kind, path):
    """Change the default folder of a kind for the current user (None = default)."""
    if kind not in FOLDERS:
        raise ValueError(f"unknown folder kind {kind}")
    f = dict(settings().get("folders", {}))
    if path:
        f[kind] = portable(os.path.expanduser(path))
    else:
        f.pop(kind, None)
    save_setting("folders", f)
    return folder(kind, create=False)


def workspace_path(user=None):
    """File of the last (automatic) workspace of a user."""
    return os.path.join(user_dir(user), "workspace.json")


# ---------------------------------------------------------------- migration from ~/.musictools
def _migrate():
    """Copy users, settings and results of ~/.musictools into ~/.musikite (once)."""
    if os.path.exists(APP_FILE) or not os.path.isdir(LEGACY_HOME) or data_home() != APP_HOME:
        return
    old = _load(os.path.join(LEGACY_HOME, "progress.json"), {})
    old_set = _load(os.path.join(LEGACY_HOME, "settings.json"), {})
    names = list(old.get("users", []))
    common = {k: v for k, v in old_set.items() if k not in ("user", "last_dir")}
    _save(os.path.join(APP_HOME, "settings.json"), common)
    for u in names:
        _save(os.path.join(APP_HOME, "users", _safe(u), "settings.json"), common)
        _save(os.path.join(APP_HOME, "users", _safe(u), "progress.json"), dict(
            answers=[a for a in old.get("answers", []) if a.get("user") == u],
            exercises=[e for e in old.get("exercises", []) if e.get("user") == u]))
    last = old_set.get("user")
    _save(APP_FILE, {"users": names, "last_user": last if last in names else None,
                     "migrated_from": LEGACY_HOME})


# ---------------------------------------------------------------- results
class Progress:
    """Answers and exercise blocks, one file per user (users/<user>/progress.json)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}                         # user -> {"answers": [], "exercises": []}

    def _user_data(self, user):
        user = user or NO_USER
        if user not in self._data:
            d = _load(os.path.join(user_dir(user) if user else APP_HOME, "progress.json"), {})
            d.setdefault("answers", [])
            d.setdefault("exercises", [])
            self._data[user] = d
        return self._data[user]

    def _save_user(self, user):
        user = user or NO_USER
        _save(os.path.join(user_dir(user) if user else APP_HOME, "progress.json"),
              self._user_data(user))

    @property
    def data(self):
        """All loaded data (compatibility): answers and exercises of every user."""
        out = {"users": users(), "answers": [], "exercises": []}
        for u in [NO_USER] + users():
            d = self._user_data(u)
            out["answers"] += d["answers"]
            out["exercises"] += d["exercises"]
        return out

    # ---------------------------------------------------------- users
    def users(self):
        return users()

    def add_user(self, name):
        """Create a user (an existing one with exactly this name: nothing to do). Another
        user with the same name in another case / spelling: ValueError (names are unique)."""
        name = name.strip()
        if not name:
            raise ValueError("empty user name")
        d = _app()
        if name not in d["users"]:              # new users only: old names stay valid
            why = valid_user_name(name)
            if why:
                raise ValueError(why)
        other = same_user(name, d["users"])
        if other is not None and other != name:
            raise ValueError(f"a user named '{other}' already exists")
        if name not in d["users"]:
            d["users"].append(name)
            _save_app(d)
            os.makedirs(user_dir(name), exist_ok=True)
        return name

    def recover_user(self, name):
        """A deleted user back in the list (his data as they were)."""
        return recover_user(name)

    def remove_user(self, name, keep_answers=True):
        """Remove a user from the list (his folder is kept: recover_user gives him back)."""
        d = _app()
        if name in d["users"]:
            d["users"].remove(name)
            if d.get("last_user") == name:
                d["last_user"] = None
            _save_app(d)

    # ---------------------------------------------------------- answers
    @staticmethod
    def new_session():
        """Session id: start time, e.g. '2026-11-04T15:20:31'."""
        return _dt.datetime.now().isoformat(timespec="seconds")

    def record(self, user, exercise, session, asked, answered, **extra):
        """Store one answer (saved immediately)."""
        a = dict(time=_dt.datetime.now().isoformat(timespec="seconds"), user=user,
                 exercise=exercise, session=session, asked=asked, answered=answered,
                 correct=asked == answered, **extra)
        with self._lock:
            self._user_data(user)["answers"].append(a)
            self._save_user(user)
        return a

    def save(self):
        for u in list(self._data):
            self._save_user(u)

    # ---------------------------------------------------------- exercises (blocks of N questions)
    def add_exercise(self, data):
        """Store a finished or stopped exercise (ExerciseResult.data)."""
        user = data.get("user")
        with self._lock:
            self._user_data(user)["exercises"].append(data)
            self._save_user(user)

    def exercises(self, user=None, kind=None):
        """List of stored exercises (dicts), oldest first."""
        src = self._user_data(user)["exercises"] if user else self.data["exercises"]
        return [e for e in src if kind is None or e.get("kind") == kind]

    def answers(self, user=None, exercise=None):
        import pandas as pd
        src = self._user_data(user)["answers"] if user else self.data["answers"]
        rows = [a for a in src if exercise is None or a["exercise"] == exercise]
        return pd.DataFrame(rows)

    def sessions(self, user, exercise):
        """One row per session: date, number of answers, correct, percentage."""
        import pandas as pd
        df = self.answers(user, exercise)
        if df.empty:
            return pd.DataFrame(columns=["session", "answers", "correct", "percent"])
        g = df.groupby("session")["correct"]
        out = pd.DataFrame({"answers": g.size(), "correct": g.sum()})
        out["percent"] = (100.0 * out["correct"] / out["answers"]).round(1)
        return out.reset_index().sort_values("session")

    def by_item(self, user, exercise, key="asked", last=None):
        """Accuracy per asked item (e.g. interval in semitones); last: only the
        most recent N answers."""
        import pandas as pd
        df = self.answers(user, exercise)
        if df.empty:
            return pd.DataFrame(columns=[key, "answers", "correct", "percent"])
        if last:
            df = df.tail(last)
        g = df.groupby(key)["correct"]
        out = pd.DataFrame({"answers": g.size(), "correct": g.sum()})
        out["percent"] = (100.0 * out["correct"] / out["answers"]).round(1)
        return out.reset_index()
