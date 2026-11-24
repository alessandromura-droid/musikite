"""
EXERCISE LIBRARY (owner, 2026-11-19). Pure Python, no Qt (Android); reading a MIDI uses
pretty_midi.

The library is made of MELODIES stored as small MIDI files (owner: "MIDI, it is simpler"),
with their metadata in an index; the exercise is made when it is used:
Practice > Exercise from library lists every melody for the instrument chosen beside the
user, ordered by difficulty (selector Difficulty: All / 0-10, and Key: Auto or a written
tonic), the ones NEVER DONE by the user in bold; a double click / Add / a drag puts the
EXERCISE in Objects > Exercises: the melody moved to the KEY chosen (Auto: a key signature
with few accidentals for an easy level, many for a hard one), then TRANSLATED for the
instrument (translate.py: the whole melody by octaves into the user's range of the
instrument — Settings > Instruments —, notes still outside folded, notes too short for the
instrument made longer at the same tempo).

TWO LIBRARIES, ONE VIEW:
- the SYSTEM library, in the package: the FOLDER `musikite/data/library/` (owner,
  2026-11-19: a folder, not a zip, so the MIDI files can be looked at) with `index.json` and
  `mid/<id>.mid` or `mid/<name>.mid`; made by scripts/build_library.py from a folder of
  MIDI files (libgen.py: transformed, crossed and generated melodies; the sources themselves
  only with --none, an exception chosen by the owner, 2026-11-19); read only (packaged app,
  Android).
- the USER library, `<data folder>/library/`: `index.json` + `<id>.mid` (shared by every
  user of the data folder). Right click > Add to library… on a MIDI ♪ (its melody,
  libgen.melody_of_midi) or on an exercise ♩: only a name is asked.

ENTRY (index): id (hash of the music and of the name), number, title (the NAME shown to the
user, e.g. "Jean-Baptiste Arban - Etude 13 - dorian"; "Melody <n>" for crossed / generated
melodies), kind (original / transformed / crossed / generated / user), ts, bars, bpm, tonic (concert pitch class), mode, lowest, highest (concert
MIDI), notes, shortest (quarters), entropy, difficulty (of the melody as it is, no
instrument), member.

IDENTITY: an exercise made from the library has uid = hash(id | instrument | written tonic |
translate.VERSION); "done" = the user has at least one attempt (ever) on the melody for that
instrument in ANY key (practice diary keys play_reading: / listen_repeat:<uid>).

DIFFICULTY for an instrument (the list and the selector) = difficulty.py on the exercise for
that instrument in the key WITHOUT accidentals (the key is chosen after); computed once per
instrument (60 per timer tick in the tab) and kept in `<data folder>/library_cache.json`.

MAKE A VARIANT: the exercise keeps the library MIDI (`source_midi`, a melody already far from
any source) and `origin['midi']` (piano, transposition to the key chosen): phrase.remake cuts
it again and translates it again for the instrument.
"""
import base64
import hashlib
import io
import json
import os
import threading

FORMAT = "musikite-library"
SYSTEM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "library")
LIBRARY_PURPOSES = ("reading", "repeat")
WRITTEN_TONICS = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
MODE_NAMES = {"ionian": "major", "aeolian": "minor"}
# Auto key: accidentals of the key signature allowed for a difficulty (rounded 0-10)
LEVEL_KEY_ACCIDENTALS = {0: (0, 0), 1: (0, 0), 2: (0, 1), 3: (0, 1), 4: (0, 2), 5: (1, 3),
                         6: (2, 4), 7: (3, 5), 8: (4, 6), 9: (5, 7), 10: (5, 7)}
_lock = threading.RLock()
_shared = {"lib": None}


# ---------------------------------------------------------------- melodies <-> MIDI
def content_id(ph, name=None):
    """Library id of a melody: hash of its music and of its NAME (16 hex digits). Owner,
    2026-11-19: the name is in the hash, so two files with different names are two
    melodies even with the same notes; without a name (crossed / generated melodies) the
    music only, as before."""
    key = dict(notes=[[round(float(s), 4), round(float(d), 4), int(p)] for s, d, p in ph.notes],
               bars=int(ph.bars), ts=list(ph.ts), bpm=float(ph.practice_bpm or ph.bpm))
    if name:
        key["name"] = str(name)
    return hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]


def midi_bytes(ph):
    """The melody as a one-track MIDI file (tempo, metre, key signature); NO NAMES (owner,
    2026-11-19: no track name, nothing of where it comes from)."""
    import copy as _copy
    p = _copy.copy(ph)
    p.bpm = float(ph.practice_bpm or ph.bpm)
    m = p.to_midi()
    for ins in m.pm.instruments:
        ins.name = ""
    buf = io.BytesIO()
    m.pm.write(buf)
    return buf.getvalue()


def melody_from_midi_bytes(data, entry):
    """Phrase of a library MIDI (times in quarters at its own tempo, rounded to 1/96)."""
    import pretty_midi
    from .phrase import Phrase
    pm = pretty_midi.PrettyMIDI(io.BytesIO(data))
    bpm = float(entry.get("bpm") or (pm.get_tempo_changes()[1][:1] or [90.0])[0])
    qps = bpm / 60.0
    notes = []
    for ins in pm.instruments:
        for n in ins.notes:
            s = round(n.start * qps * 96) / 96
            e = round(n.end * qps * 96) / 96
            notes.append([s, max(1 / 96, e - s), int(n.pitch)])
    ph = Phrase(notes, int(entry["bars"]), tuple(entry.get("ts") or (4, 4)),
                int(entry.get("tonic", 0)), entry.get("mode", "ionian"), bpm, 0, "Melody",
                entry.get("title", ""), "", "none", "reading", 1, instrument="library",
                practice_bpm=bpm, transposition=0)
    return ph


def metadata(ph):
    """Index fields of a melody (no id / number / title / kind / member)."""
    from .libgen import entropy
    from .difficulty import score_of
    ps = [p for _, _, p in ph.notes]
    return dict(ts=list(ph.ts), bars=int(ph.bars), bpm=float(ph.practice_bpm or ph.bpm),
                tonic=int(ph.tonic), mode=ph.mode, lowest=min(ps), highest=max(ps),
                notes=len(ps), shortest=round(min(d for _, d, _ in ph.notes), 4),
                entropy=round(entropy(ph), 2), difficulty=score_of(ph))


def key_name(written_tonic, mode):
    return f"{WRITTEN_TONICS[int(written_tonic) % 12]} {MODE_NAMES.get(mode, mode)}"


CHURCH_MODES = ("ionian", "dorian", "phrygian", "lydian", "mixolydian", "aeolian", "locrian")
TRANSFORM_TAGS = ("inversion", "retrograde", "retrograde inversion")


def transformation_of(entry):
    """The transformation of a 'transformed' melody (column Type of the library tab, owner,
    2026-11-20): the field `transform` if the entry has one, else the tag at the end of the
    title "<source> - <tag>" written by build_library: a mode ("dorian"…), "inversion",
    "inversion, dorian", "retrograde", "retrograde, dorian", "retrograde inversion".
    None if the title has no such tag."""
    t = entry.get("transform")
    if t:
        return t
    title = entry.get("title") or ""
    if " - " not in title:
        return None
    tag = title.rsplit(" - ", 1)[1].strip()
    head, _, mode = tag.partition(", ")
    if mode:
        ok = head in ("inversion", "retrograde") and mode in CHURCH_MODES
    else:
        ok = tag in CHURCH_MODES or tag in TRANSFORM_TAGS
    return tag if ok else None


def type_label(entry):
    """Column Type of the library tab (owner, 2026-11-20): 'original'; for a transformed
    melody its transformation ("dorian", "inversion", "retrograde, lydian"…); else the kind
    (crossed, generated, user)."""
    kind = entry.get("kind", "")
    if kind == "transformed":
        return transformation_of(entry) or kind
    return kind


def neutral_tonic(mode):
    """Written tonic whose key signature has no accidentals (C major, A minor, D dorian…)."""
    from .theory import key_signature
    return next(t for t in range(12) if key_signature(t, mode) == 0)


def auto_tonic(entry, level, salt=""):
    """Written tonic for a difficulty: a key signature with the accidentals allowed for the
    level (LEVEL_KEY_ACCIDENTALS); among the possible ones, a fixed one per melody."""
    from .theory import key_signature
    lv = max(0, min(10, int(round(float(level if level is not None else 3)))))
    a, b = LEVEL_KEY_ACCIDENTALS[lv]
    mode = entry.get("mode", "ionian")
    cands = [t for t in range(12) if a <= abs(key_signature(t, mode)) <= b] or \
        [neutral_tonic(mode)]
    h = int(hashlib.sha1(f"{entry['id']}|{salt}".encode()).hexdigest(), 16)
    return cands[h % len(cands)]


def chosen_tonic(entry, instrument, written_tonic=None, level=None):
    """The written tonic of the exercise: the one chosen, else Auto for the level (None:
    the melody's own difficulty)."""
    if written_tonic is not None:
        return int(written_tonic) % 12
    return auto_tonic(entry, entry.get("difficulty") if level is None else level, instrument)


def exercise_uid(lid, instrument, written_tonic):
    from .translate import VERSION
    return hashlib.sha1(f"{lid}|{instrument}|{int(written_tonic) % 12}|{VERSION}".encode()
                        ).hexdigest()[:12]


# ---------------------------------------------------------------- the library
class Library:
    def __init__(self, system_dir=None, user_dir=None, cache_file=None):
        from .progress import data_home
        self.system_dir = system_dir or SYSTEM_DIR
        self.user_dir = user_dir or os.path.join(data_home(), "library")
        self.cache_file = cache_file or os.path.join(data_home(), "library_cache.json")
        self._system = None
        self._user = None
        self._cache = None
        self._dirty = False

    # ---------------------------------------------------------- entries
    def system_entries(self):
        if self._system is None:
            self._system = [dict(e, user=False) for e in read_index(self.system_dir)]
        return self._system

    def user_entries(self):
        if self._user is None:
            p = os.path.join(self.user_dir, "index.json")
            self._user = []
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    self._user = [dict(e, user=True) for e in json.load(f).get("entries", [])]
        return self._user

    def entries(self):
        """Every melody: the system library, then the user's (one id once)."""
        seen, out = set(), []
        for e in self.system_entries() + self.user_entries():
            if e["id"] not in seen:
                seen.add(e["id"])
                out.append(e)
        return out

    def entry(self, lid):
        return next((e for e in self.entries() if e["id"] == lid), None)

    def reload(self):
        self._system = self._user = None
        return self

    # ---------------------------------------------------------- melodies and exercises
    def midi_data(self, entry):
        folder = self.user_dir if entry.get("user") else self.system_dir
        with open(os.path.join(folder, entry["member"]), "rb") as f:
            return f.read()

    def melody(self, entry):
        """The melody as it is in the library (Phrase, concert pitch, no instrument)."""
        return melody_from_midi_bytes(self.midi_data(entry), entry)

    def exercise(self, entry, instrument, written_tonic=None, level=None):
        """The EXERCISE for an instrument (catalogue key): the melody moved to the written
        tonic (None: auto_tonic for `level`, default the melody's difficulty), translated
        for the instrument (translate.py); deterministic uid (exercise_uid)."""
        from .translate import translate
        from .instruments import CATALOGUE
        T = int(CATALOGUE[instrument]["transposition"])
        written_tonic = chosen_tonic(entry, instrument, written_tonic, level)
        ph = self.melody(entry)
        k = ((written_tonic - T) - ph.tonic) % 12
        if k > 6:
            k -= 12
        if k:
            ph = ph.transpose(k)
        ph.transform, ph.title = "none", entry.get("title", "")
        uid = exercise_uid(entry["id"], instrument, written_tonic)
        ex = translate(ph, instrument, source_id=entry["id"])
        ex.uid = uid
        ex.source_midi = base64.b64encode(self.midi_data(entry)).decode("ascii")
        origin = dict(ex.origin or {})
        origin["midi"] = dict(title=entry.get("title", ""), part=0, parts=["Melody"], first=1,
                              last=int(entry["bars"]), bars=[1, int(entry["bars"])], level=5,
                              instrument="C (piano)", transform="none", transpose=int(k),
                              remove_empty=False, polyphony=False, purpose="reading")
        origin["library"] = dict(id=entry["id"], number=entry.get("number"),
                                 user=bool(entry.get("user")), written_tonic=written_tonic)
        ex.origin = origin
        ex.practice_bpm = float(entry.get("bpm") or ex.bpm)
        ex.title = self.title(entry, instrument, written_tonic)
        return ex

    def title(self, entry, instrument, written_tonic):
        """Title of the exercise: the NAME of the melody (owner, 2026-11-19: "the user must
        know he is playing the Arban"), its key and the instrument."""
        from .instruments import label
        name = entry.get("title") or f"Library {entry.get('number', '')}"
        return (f"{name} – "
                f"{key_name(written_tonic, entry.get('mode', 'ionian'))} – {label(instrument)}")

    # ---------------------------------------------------------- difficulty per instrument
    def _cache_data(self):
        if self._cache is None:
            try:
                with open(self.cache_file, encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (OSError, ValueError):
                self._cache = {}
        return self._cache

    def _table(self, instrument):
        from .translate import VERSION
        return self._cache_data().setdefault(f"{instrument}|v{VERSION}|lib2", {})

    def known_difficulty(self, entry, instrument):
        return self._table(instrument).get(entry["id"])

    def difficulty(self, entry, instrument):
        """Difficulty of the exercise for the instrument, in the key without accidentals."""
        d = self.known_difficulty(entry, instrument)
        if d is None:
            from .difficulty import score_of
            try:
                d = score_of(self.exercise(entry, instrument,
                                           neutral_tonic(entry.get("mode", "ionian"))))
            except Exception:
                d = entry.get("difficulty")
            self._table(instrument)[entry["id"]] = d
            self._dirty = True
        return d

    def pending(self, instrument):
        return [e for e in self.entries() if self.known_difficulty(e, instrument) is None]

    def save_cache(self):
        if not self._dirty:
            return
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        tmp = self.cache_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cache_data(), f, separators=(",", ":"))
        os.replace(tmp, self.cache_file)
        self._dirty = False

    # ---------------------------------------------------------- done by a user
    def done_uids(self, user=None):
        """uids of the exercises with at least one attempt of the user (practice diary)."""
        from . import diary
        try:
            atts = diary.get(user).data.get("attempts", [])
        except Exception:
            return set()
        return {str(a.get("key", "")).split(":", 1)[1] for a in atts
                if str(a.get("key", "")).startswith(("play_reading:", "listen_repeat:"))}

    def is_done(self, entry, instrument, done_uids):
        """At least one attempt on the melody for the instrument, in any key."""
        if not done_uids:
            return False
        return any(exercise_uid(entry["id"], instrument, t) in done_uids for t in range(12))

    # ---------------------------------------------------------- the user's additions
    def add(self, obj, name):
        """Add to the USER library a melody: a Midi (its melody, libgen.melody_of_midi) or a
        Read & play / Listen & repeat exercise (its notes). Returns (entry, added: False if
        the same melody is already there)."""
        from .phrase import Phrase
        from .midi import Midi
        from . import libgen
        if isinstance(obj, Midi):
            ph = libgen.melody_of_midi(obj, name)
            if ph is None:
                raise ValueError(f"no melody with at least {libgen.MIN_NOTES} notes")
        elif isinstance(obj, Phrase) and obj.purpose in LIBRARY_PURPOSES:
            ph = libgen.neutral(obj, name)
            ph.practice_bpm = obj.practice_bpm or obj.bpm
        else:
            raise ValueError("only a MIDI or a Read & play / Listen & repeat exercise")
        lid = content_id(ph, name or ph.title)
        old = self.entry(lid)
        if old is not None:
            return old, False
        os.makedirs(self.user_dir, exist_ok=True)
        n = max([e.get("number", 0) for e in self.entries()] + [0]) + 1
        member = f"{lid}.mid"
        with open(os.path.join(self.user_dir, member), "wb") as f:
            f.write(midi_bytes(ph))
        e = dict(id=lid, number=n, title=name or ph.title, kind="user", member=member,
                 **metadata(ph))
        entries = [{k: v for k, v in x.items() if k != "user"} for x in self.user_entries()]
        entries.append(e)
        p = os.path.join(self.user_dir, "index.json")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(dict(format=FORMAT, entries=entries), f, separators=(",", ":"))
        os.replace(p + ".tmp", p)
        self._user = None
        return dict(e, user=True), True


def get():
    """The library of the current data folder (one shared object)."""
    from .progress import data_home
    lib = _shared["lib"]
    if lib is None or lib.user_dir != os.path.join(data_home(), "library"):
        lib = _shared["lib"] = Library()
    return lib


# ---------------------------------------------------------------- building the system library
def file_name(name):
    """A melody name usable as a file name (no / \\ : and control characters)."""
    out = "".join("-" if c in '/\\:' or ord(c) < 32 else c for c in str(name))
    return out.strip().strip(".") or "melody"


def write_library(items, folder):
    """ADD melodies to the system library FOLDER (mid/<file>.mid + index.json). ADDITIVE
    (owner, 2026-11-19: "the library can be built from different sources"): the melodies
    already there stay (index entry, MIDI file, number), nothing is ever removed; a melody
    whose id (music + name) is already there is not added again. items: [(kind, Phrase)]
    or [(kind, Phrase, name)] or [(kind, Phrase, name, midi_bytes)]:
    - without a name: title "Melody <n>", file mid/<id>.mid (crossed / generated);
    - with a name (owner: "clarity on the files"; the user must see the names): title =
      name, file mid/<name>.mid (e.g. "Matteo Carcassi - I 07 Waltz - dorian"; a name
      already used by another file: "<name> (<id[:6]>).mid");
    - with midi_bytes: the file is written with THOSE bytes (option none of build_library:
      the source MIDI unchanged), else made from the Phrase (`midi_bytes`).
    New melodies get the numbers after the highest one. Returns (added, total)."""
    entries = read_index(folder)
    ids = {e["id"] for e in entries}
    members = {e["member"].lower() for e in entries}
    nxt = max([e.get("number", 0) for e in entries] + [0]) + 1
    os.makedirs(os.path.join(folder, "mid"), exist_ok=True)
    added = 0
    for item in items:
        kind, ph = item[0], item[1]
        name = item[2] if len(item) > 2 else None
        data = item[3] if len(item) > 3 else None
        lid = content_id(ph, name)
        if lid in ids:
            continue
        ids.add(lid)
        num, nxt = nxt, nxt + 1
        if name:
            member = f"mid/{file_name(name)}.mid"
            if member.lower() in members or os.path.exists(os.path.join(folder, member)):
                member = f"mid/{file_name(name)} ({lid[:6]}).mid"
        else:
            member = f"mid/{lid}.mid"
        members.add(member.lower())
        e = dict(id=lid, number=num, title=name or f"Melody {num}", kind=kind,
                 member=member, **metadata(ph))
        with open(os.path.join(folder, e["member"]), "wb") as f:
            f.write(data if data is not None else midi_bytes(ph))
        entries.append(e)
        added += 1
    entries.sort(key=lambda e: e["number"])
    p = os.path.join(folder, "index.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(dict(format=FORMAT, entries=entries), f, separators=(",", ":"),
                  ensure_ascii=False)
    os.replace(p + ".tmp", p)
    return added, len(entries)


def read_index(folder):
    """Entries of a library folder ([] if it has no index)."""
    p = os.path.join(folder, "index.json")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f).get("entries", [])
