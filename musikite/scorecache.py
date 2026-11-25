"""
CACHE OF THE SCORES MADE FROM A MIDI (owner, 2026-11-24: "the preview takes up to 20 s on
a multi-part MIDI"): Score.from_midi (music21: quantization, key, spelling) and the
MusicXML export are the slow steps of every staff of a MIDI (Preview, View, double click,
Play). They are kept
- in memory (this session) and
- on disk, `~/.musikite/cache/scores/` (THIS computer, not the shared data folder; at most
  `MAX_BYTES`, the oldest files removed first),
under a KEY = sha1 of the MIDI bytes + the parameters (written pitch, title) + the
music21 version + `FORMAT` (owner's rule: data and parameters, never the code text). An
edited MIDI (piano roll) has other bytes, hence another key. The score is stored frozen
(music21 pickle: every get gives a NEW object, so a caller may change it freely) with its
MusicXML text (Verovio reads it directly, no export).

FIRST BARS FIRST (same date): `head_midi` cuts the first `HEAD_BARS` bars of a long MIDI
(pretty_midi only) and `head_keys` gives the key of every part on the WHOLE piece, so the
staff of the first bars can be shown at once while `FullJob` converts the whole MIDI in a
background thread (StaffView swaps it in when ready). No Qt.
"""
import hashlib
import io
import os
import tempfile
import threading

CACHE_DIR = os.path.expanduser("~/.musikite/cache/scores")
MAX_BYTES = 500 * 1024 * 1024
FORMAT = 1
HEAD_BARS = 8              # first bars shown at once (owner, 2026-11-24: 16 -> 8)
LOG = None                      # f(text): the Log of the app (errors are never silent)
_mem = {}                       # key -> (frozen bytes, musicxml, title, written, rows)
_MEM_MAX = 40
_lock = threading.RLock()


def _log(text):
    try:
        (LOG or print)(f"score cache: {text}")
    except Exception:
        pass


# ---------------------------------------------------------------- key, MusicXML
def midi_bytes(midi):
    buf = io.BytesIO()
    midi.pm.write(buf)
    return buf.getvalue()


def key_of(midi, title=None, written=True):
    try:
        import music21
        v = music21.VERSION_STR
    except Exception:
        v = "?"
    h = hashlib.sha1(midi_bytes(midi))
    h.update(f"|{title}|{bool(written)}|music21 {v}|{FORMAT}".encode())
    return h.hexdigest()


def musicxml(score):
    """MusicXML text of a Score (music21 export)."""
    fd, tmp = tempfile.mkstemp(suffix=".musicxml")
    os.close(fd)
    try:
        score.m21.write("musicxml", fp=tmp)
        with open(tmp, encoding="utf-8") as f:
            return f.read()
    finally:
        os.remove(tmp)


def row_keys(score):
    """For every row of score.table() (every part): (staff, start, pitch|None) — what
    StaffView matches to the engraved notes; kept in the cache with the score (the table of
    11 parts x 104 bars took 1.5 s)."""
    keys = []
    for ip in range(len(score.m21.parts)):
        t = score.table(part=ip)
        for r in t.itertuples():
            p = None if r.pitch is None or str(r.pitch) == "<NA>" else int(r.pitch)
            keys.append((ip, round(float(r.start), 3), p))
    return keys


# ---------------------------------------------------------------- store
def _freeze(score):
    from music21 import converter
    return converter.freezeStr(score.m21, fmt="pickle")


def _thaw(data, title, written, source):
    from music21 import converter
    from .score import Score
    sc = Score(converter.thawStr(data), title, written)
    sc.source = source
    return sc


def _paths(key):
    return (os.path.join(CACHE_DIR, key + ".pickle"), os.path.join(CACHE_DIR, key + ".musicxml"),
            os.path.join(CACHE_DIR, key + ".txt"), os.path.join(CACHE_DIR, key + ".rows.json"))


def get(midi, title=None, written=True, key=None):
    """(Score, musicxml, rows | None) from the cache (memory, then disk), else None."""
    key = key or key_of(midi, title, written)
    with _lock:
        hit = _mem.get(key)
    if hit is None:
        pk, xm, tx, rw = _paths(key)
        try:
            with open(pk, "rb") as f:
                data = f.read()
            with open(xm, encoding="utf-8") as f:
                xml = f.read()
            with open(tx, encoding="utf-8") as f:
                t, w = (f.read().split("\n") + ["", "1"])[:2]
            rows = None
            if os.path.exists(rw):                    # older entries have no rows
                import json
                with open(rw, encoding="utf-8") as f:
                    rows = [tuple(r) for r in json.load(f)]
            hit = (data, xml, t, w == "1", rows)
            for p in (pk, xm, tx, rw):
                if os.path.exists(p):
                    os.utime(p, None)                 # recently used: pruned last
            with _lock:
                _remember(key, hit)
        except FileNotFoundError:
            return None                                # not in the cache
        except (OSError, ValueError) as e:
            _log(f"cannot read {key[:10]}…: {type(e).__name__}: {e}")
            return None
    data, xml, t, w, rows = hit
    try:
        return _thaw(data, t, w, getattr(midi, "source", None)), xml, rows
    except Exception as e:
        _log(f"cannot thaw {key[:10]}…: {type(e).__name__}: {e}")
        return None


def _remember(key, item):
    _mem[key] = item
    while len(_mem) > _MEM_MAX:
        _mem.pop(next(iter(_mem)))


def put(key, score, xml, rows=None):
    try:
        data = _freeze(score)
    except Exception as e:
        _log(f"cannot freeze the score: {type(e).__name__}: {e}")
        return False
    item = (data, xml, score.title or "", bool(score.written), rows)
    with _lock:
        _remember(key, item)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        pk, xm, tx, rw = _paths(key)
        if rows is not None:
            import json
            with open(rw, "w", encoding="utf-8") as f:
                json.dump([list(r) for r in rows], f)
        with open(pk + ".tmp", "wb") as f:
            f.write(data)
        os.replace(pk + ".tmp", pk)
        with open(xm, "w", encoding="utf-8") as f:
            f.write(xml)
        with open(tx, "w", encoding="utf-8") as f:
            f.write(f"{item[2]}\n{'1' if item[3] else '0'}")
        prune()
    except OSError as e:
        _log(f"cannot write {CACHE_DIR}: {type(e).__name__}: {e}")
        return False
    return True


_VEROVIO = []


def _verovio_version():
    if not _VEROVIO:
        try:
            import verovio
            _VEROVIO.append(verovio.toolkit().getVersion())
        except Exception:
            _VEROVIO.append("?")
    return _VEROVIO[0]


def _layout_path(key, layout, scale, width):
    v = _verovio_version()
    h = hashlib.sha1(f"{layout}|{scale}|{width}|verovio {v}".encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"{key}.layout-{h}.pickle")


_layouts = {}


def get_layout(key, layout, scale, width):
    """The Verovio layout state of a cached score (StaffView._Layout.state), or None."""
    import pickle
    p = _layout_path(key, layout, scale, width)
    with _lock:
        st = _layouts.get(p)
    if st is not None:
        return st
    try:
        with open(p, "rb") as f:
            st = pickle.load(f)
        os.utime(p, None)
    except FileNotFoundError:
        return None
    except Exception as e:
        _log(f"cannot read the layout {os.path.basename(p)}: {type(e).__name__}: {e}")
        return None
    with _lock:
        _layouts[p] = st
        while len(_layouts) > _MEM_MAX:
            _layouts.pop(next(iter(_layouts)))
    return st


def put_layout(key, layout, scale, width, state):
    import pickle
    p = _layout_path(key, layout, scale, width)
    with _lock:
        _layouts[p] = state
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(p + ".tmp", "wb") as f:
            pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(p + ".tmp", p)
        prune()
    except Exception as e:
        _log(f"cannot write the layout: {type(e).__name__}: {e}")


def save_rows(key, rows):
    """The note-table keys of an entry stored without them (older cache files)."""
    import json
    with _lock:
        it = _mem.get(key)
        if it is not None:
            _mem[key] = it[:4] + (rows,)
    try:
        if os.path.exists(_paths(key)[0]):
            with open(_paths(key)[3], "w", encoding="utf-8") as f:
                json.dump([list(r) for r in rows], f)
    except OSError as e:
        _log(f"cannot write the rows of {key[:10]}…: {e}")


def prune(max_bytes=MAX_BYTES):
    """The oldest files (last use) removed until the cache is under max_bytes."""
    try:
        files = [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)]
    except OSError:
        return
    files = [(os.path.getmtime(p), os.path.getsize(p), p) for p in files if os.path.isfile(p)]
    total = sum(s for _, s, _ in files)
    for _, s, p in sorted(files):
        if total <= max_bytes:
            break
        try:
            os.remove(p)
            total -= s
        except OSError:
            pass


def clear():
    with _lock:
        _mem.clear()
    prune(0)


# ---------------------------------------------------------------- build
def build(midi, title=None, written=True, key=None):
    """(Score, musicxml, rows) of the whole MIDI, made now and stored."""
    from .score import Score
    key = key or key_of(midi, title, written)
    sc = Score.from_midi(midi, title=title, written=written)
    xml = musicxml(sc)
    rows = row_keys(sc)
    put(key, sc, xml, rows)
    return sc, xml, rows


class FullJob:
    """The whole MIDI converted in a background thread: `done`, `result` (Score,
    musicxml, rows), `error`. The Score is made in the thread and only handed over."""

    def __init__(self, midi, title=None, written=True, key=None):
        import copy
        self.midi = copy.copy(midi)
        self.midi.pm = copy.deepcopy(midi.pm)          # the view may be edited meanwhile
        self.title, self.written = title, written
        self.key = key
        self.done, self.result, self.error = False, None, None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            self.result = build(self.midi, self.title, self.written, self.key)
        except Exception as e:                          # shown by the view, never silent
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.done = True


# ---------------------------------------------------------------- first bars
def _bar_q(pm):
    ts = pm.time_signature_changes
    return ts[0].numerator * 4.0 / ts[0].denominator if ts else 4.0


def length_q(midi):
    pm = midi.pm
    return pm.time_to_tick(pm.get_end_time()) / float(pm.resolution)


def head_midi(midi, bars=HEAD_BARS):
    """A Midi with only the first `bars` bars (notes cut at the end; the bar length of the
    first time signature), or None if the MIDI is not longer than that."""
    import copy
    from .midi import Midi
    pm = midi.pm
    q_cut = bars * _bar_q(pm)
    if length_q(midi) <= q_cut + 1e-6:
        return None
    t_cut = pm.tick_to_time(int(round(q_cut * pm.resolution)))
    head = copy.deepcopy(pm)
    for ins in head.instruments:
        ins.notes = [n for n in ins.notes if n.start < t_cut - 1e-6]
        for n in ins.notes:
            n.end = min(n.end, t_cut)
        ins.control_changes = [c for c in ins.control_changes if c.time < t_cut]
        ins.pitch_bends = [b for b in ins.pitch_bends if b.time < t_cut]
    head.time_signature_changes = [t for t in head.time_signature_changes if t.time < t_cut]
    head.key_signature_changes = [k for k in head.key_signature_changes if k.time < t_cut]
    head.lyrics = [x for x in head.lyrics if x.time < t_cut]
    m = Midi()
    m.pm = head
    m.source = midi.source
    m.title = getattr(midi, "title", None)
    return m


def head_keys(midi):
    """{index of the track among those with notes: (tonic, mode) CONCERT} of the WHOLE
    MIDI (theory engine), for Score.from_midi(keys=…) of its first bars."""
    from . import theory as th
    pm = midi.pm
    res = float(pm.resolution)
    out = {}
    for k, ins in enumerate([i for i in pm.instruments if i.notes]):
        if ins.is_drum:
            continue
        notes = [[pm.time_to_tick(n.start) / res, (pm.time_to_tick(n.end) - pm.time_to_tick(n.start)) / res,
                  n.pitch] for n in ins.notes]
        out[k] = th.key_of_notes(notes)
    return out


def head_score(midi, bars=HEAD_BARS):
    """(Score of the first bars, musicxml, rows) or None (short MIDI)."""
    from .score import Score
    h = head_midi(midi, bars)
    if h is None:
        return None
    sc = Score.from_midi(h, keys=head_keys(midi) if not midi.pm.key_signature_changes else None)
    return sc, musicxml(sc), None
