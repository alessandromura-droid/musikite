"""
Workspace: the objects of a session (Midi, Notes, Score, Pdf, exercise sets, exercises
with their results — tasks.Task —, routines) in ONE JSON file, portable (no Qt; also for
Android). Old result objects (ExerciseResult, before 2026-11-07) are converted when loaded
into the exercise with its result (tasks.from_result; owner: there is no result object).

    save_workspace(path, {'duet 1': midi, ...}, user='Teresa')
    objects, warnings = load_workspace(path)      # list of (name, object)

MIDI data and exercises are stored inside the file; a Pdf is stored as the
path of its file (a missing file gives a warning when loading); a Score as
MusicXML. The last workspace of every user is saved automatically
(progress.workspace_path(user)) at exit and when the user changes.
"""
import base64
import datetime as _dt
import io
import json
import os

FORMAT = "musikite-workspace"
VERSION = 1


def _midi_bytes(m):
    buf = io.BytesIO()
    m.pm.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _midi_from(b64):
    import pretty_midi
    return pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(b64)))


def encode(obj):
    """(type, data) of an object, or None if it cannot be stored."""
    from .midi import Midi
    from .notes import Notes
    from .score import Score
    from .pdf import Pdf
    from .phrase import Phrase, ExerciseSet
    from .tasks import Task, Routine
    common = dict(title=getattr(obj, "title", None), source=getattr(obj, "source", None),
                  saved_path=getattr(obj, "_saved_path", None))
    if isinstance(obj, Notes):
        t = obj.table()
        return "Notes", dict(common, midi=_midi_bytes(obj),
                             table=json.loads(t.to_json(orient="records")),
                             program=getattr(obj, "program", 56))
    if isinstance(obj, Midi):
        return "Midi", dict(common, midi=_midi_bytes(obj), duet_info=obj.duet_info)
    if isinstance(obj, Score):
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".musicxml")
        os.close(fd)
        try:
            obj.m21.write("musicxml", fp=tmp)
            with open(tmp, encoding="utf-8") as f:
                xml = f.read()
        finally:
            os.remove(tmp)
        return "Score", dict(common, musicxml=xml, written=obj.written)
    if isinstance(obj, Pdf):
        return "Pdf", dict(common, path=obj.path)
    if isinstance(obj, ExerciseSet):
        return "ExerciseSet", obj.to_dict()
    if isinstance(obj, Phrase):
        return "Phrase", obj.to_dict()
    from .tasks import TaskGroup
    from .playover import PlayOver
    if isinstance(obj, PlayOver):
        return "PlayOver", obj.to_dict()
    if isinstance(obj, TaskGroup):
        return "TaskGroup", obj.to_dict()
    if isinstance(obj, Task):
        return "Task", obj.to_dict()
    if isinstance(obj, Routine):
        return "Routine", obj.to_dict()
    return None


def decode(typ, d):
    """Object from (type, data)."""
    from .midi import Midi
    from .notes import Notes
    from .score import Score
    from .pdf import Pdf
    from .phrase import Phrase, ExerciseSet
    from .tasks import Task, Routine, from_result
    if typ == "Notes":
        try:
            o = Notes.from_table(d["table"], program=d.get("program", 56))
        except Exception:
            o = Notes()
            o.pm = _midi_from(d["midi"])
            o._sync_from_pm()
    elif typ == "Midi":
        o = Midi()
        o.pm = _midi_from(d["midi"])
        o.duet_info = d.get("duet_info")
    elif typ == "Score":
        from music21 import converter
        o = Score(converter.parseData(d["musicxml"], format="musicxml"), d.get("title") or "",
                  d.get("written", True))
    elif typ == "Pdf":
        o = Pdf(d["path"])                     # FileNotFoundError if it was moved
    elif typ == "ExerciseSet":
        return ExerciseSet.from_dict(d)
    elif typ == "Phrase":
        return Phrase.from_dict(d)
    elif typ == "Task":
        return Task.from_dict(d)
    elif typ == "Routine":
        return Routine.from_dict(d)
    elif typ == "PlayOver":
        from .playover import PlayOver
        return PlayOver.from_dict(d)
    elif typ == "TaskGroup":
        from .tasks import TaskGroup
        return TaskGroup.from_dict(d)
    elif typ == "ExerciseResult":               # old result object -> the exercise + result
        return from_result(d)
    else:
        raise ValueError(f"unknown object type {typ}")
    if d.get("title"):
        o.title = d["title"]
    if d.get("saved_path"):
        o._saved_path = d["saved_path"]
    if d.get("source") and typ != "Pdf":
        o.source = d["source"]
    return o


def save_workspace(path, objects, user=None):
    """Write the objects ({name: object}, in order) to a workspace file; returns
    the names that could not be stored."""
    items, skipped = [], []
    for name, obj in objects.items():
        try:
            e = encode(obj)
        except Exception:
            e = None
        if e is None:
            skipped.append(name)
            continue
        items.append(dict(name=name, type=e[0], data=e[1]))
    doc = dict(format=FORMAT, version=VERSION, user=user,
               saved=_dt.datetime.now().isoformat(timespec="seconds"), objects=items)
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    os.replace(tmp, path)
    return skipped


def load_workspace(path):
    """(list of (name, object), list of warnings)."""
    with open(os.path.expanduser(path), encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != FORMAT:
        raise ValueError(f"{path}: not a MusiKitE workspace")
    out, warn = [], []
    for it in doc.get("objects", []):
        try:
            o = decode(it["type"], it["data"])
            name = it["name"]
            if it["type"] == "ExerciseResult":    # converted: named as the exercise
                name = getattr(o, "title", None) or name
                warn.append(f"{it['name']}: old result object converted into the exercise "
                            f"'{name}' with its result")
            out.append((name, o))
        except FileNotFoundError as e:
            warn.append(f"{it['name']}: file not found ({e})")
        except Exception as e:
            warn.append(f"{it['name']}: {type(e).__name__}: {e}")
    return out, warn
