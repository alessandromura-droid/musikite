"""
Piano roll model: the notes of a MIDI as rectangles on a grid, edited and quantized
(pure Python, no Qt: this logic goes to Android as it is; the Qt drawing is in
pianorollview.py).

Times are in QUARTER NOTES from the start (the tempo map of the MIDI converts them
back to seconds), pitches are MIDI numbers at concert pitch. A note is a list
[start_q, dur_q, pitch, velocity] (the same as recorder.Recorder), a track is a dict
(name, program, is_drum, notes). Every edit can be undone (undo/redo).

    r = Roll.from_midi(m)                    # or Roll.from_parts(recorder.parts, bpm, ts)
    n = r.add(0, start=4, dur=1, pitch=67)   # track 0, bar 2 beat 1, G4, a quarter
    r.move(0, [n], dq=0.5, dp=2)             # half a beat later, a tone up
    r.quantize("1/8+1/8T", strength=0.8)     # Ableton style (grid, strength, ends)
    r.undo(); r.redo()
    r.apply_to(m)                            # the Midi object now has the edited notes
    r.to_midi()                              # or a new Midi object

Quantize grids (GRIDS): "1/4", "1/8", "1/16", "1/32", triplets "1/8T", "1/16T" and the
mixed grids "1/8+1/8T", "1/16+1/16T" (every note goes to the nearest point of either
grid). strength 0..1 (1 = exactly on the grid, less = part of the human timing is
kept); ends=True quantizes the note ends too (else the length is kept).
"""
import copy

GRIDS = ("1/4", "1/8", "1/8T", "1/8+1/8T", "1/16", "1/16T", "1/16+1/16T", "1/32")
EDIT_GRIDS = ("Off", "1/4", "1/8", "1/8T", "1/16", "1/16T", "1/32")
MIN_DUR = 1.0 / 32                       # shortest note (quarters) left by editing
MAX_UNDO = 200


def grid_steps(spec):
    """Steps in quarters of a grid: '1/8' -> [0.5]; '1/8T' -> [1/3];
    '1/8+1/8T' -> [0.5, 1/3]; 'Off' / None -> []."""
    if not spec or str(spec).lower() == "off":
        return []
    out = []
    for p in str(spec).split("+"):
        p = p.strip()
        trip = p.upper().endswith("T")
        num, den = p.rstrip("tT").split("/")
        step = 4.0 * float(num) / float(den)
        out.append(step * 2.0 / 3.0 if trip else step)
    return out


def snap(q, step):
    """q rounded to the nearest multiple of step (step 0/None: unchanged)."""
    return round(q / step) * step if step else q


def snap_floor(q, step):
    """Start of the grid cell that contains q."""
    import math
    return math.floor(q / step + 1e-9) * step if step else q


def nearest(q, steps):
    """Nearest point of any of the grids (a straight point wins a tie)."""
    best = None
    for s in steps:
        c = snap(q, s)
        if best is None or abs(c - q) < abs(best - q) - 1e-9:
            best = c
    return q if best is None else best


class Roll:
    def __init__(self, tracks=None, bpm=120.0, ts=(4, 4), title=None, template=None):
        self.tracks = tracks or []           # [dict(name, program, is_drum, notes, ins)]
        self.bpm = float(bpm)
        self.ts = (int(ts[0]), int(ts[1]))
        self.title = title
        self._tmpl = template                # pretty_midi without notes: tempo map, metre, CCs
        self._undo = []
        self._redo = []
        self.version = 0                     # +1 at every change (views redraw)

    # ---------------------------------------------------------- build
    @classmethod
    def from_midi(cls, midi, title=None):
        """Roll of a Midi object (or a pretty_midi object): times converted to quarters
        with its tempo map; tempo changes, time/key signatures, controllers and pitch
        bends are kept for to_midi()."""
        pm = getattr(midi, "pm", midi)
        res = float(pm.resolution)
        tmpl = copy.deepcopy(pm)
        tracks = []
        for k, ins in enumerate(pm.instruments):
            notes = []
            for n in ins.notes:
                s = float(pm.time_to_tick(n.start)) / res
                e = float(pm.time_to_tick(n.end)) / res
                notes.append([round(s, 4), round(max(MIN_DUR, e - s), 4), int(n.pitch),
                              int(n.velocity)])
            notes.sort()
            tracks.append(dict(name=ins.name or _gm_name(ins.program, ins.is_drum),
                               program=int(ins.program), is_drum=bool(ins.is_drum),
                               notes=notes, ins=k))
            tmpl.instruments[k].notes = []
        _, tempi = pm.get_tempo_changes()
        bpm = float(tempi[0]) if len(tempi) else 120.0
        ts = ((pm.time_signature_changes[0].numerator, pm.time_signature_changes[0].denominator)
              if pm.time_signature_changes else (4, 4))
        return cls(tracks, bpm, ts, title or getattr(midi, "title", None), tmpl)

    @classmethod
    def from_parts(cls, parts, bpm=90, ts=(4, 4), title=None):
        """Roll of the parts of a recorder.Recorder (notes already in quarters)."""
        tracks = [dict(name=p["name"], program=int(p["program"]), is_drum=False,
                       notes=[list(n) for n in p["notes"]], ins=None) for p in parts]
        return cls(tracks, bpm, ts, title)

    def to_parts(self):
        """The tracks as recorder parts (for the next overdub)."""
        return [dict(program=t["program"], name=t["name"], notes=[list(n) for n in t["notes"]])
                for t in self.tracks if not t["is_drum"]]

    def add_track(self, name=None, program=0, is_drum=False):
        self.tracks.append(dict(name=name or _gm_name(program, is_drum), program=int(program),
                                is_drum=bool(is_drum), notes=[], ins=None))
        self.version += 1
        return len(self.tracks) - 1

    # ---------------------------------------------------------- time
    @property
    def beat_q(self):
        return 4.0 / self.ts[1]

    @property
    def bar_q(self):
        return self.ts[0] * self.beat_q

    def length_q(self):
        """End of the last note (at least one bar)."""
        end = max((n[0] + n[1] for t in self.tracks for n in t["notes"]), default=0.0)
        return max(self.bar_q, end)

    def bars(self):
        import math
        return int(math.ceil(self.length_q() / self.bar_q - 1e-9))

    def pitch_range(self):
        ps = [n[2] for t in self.tracks for n in t["notes"]]
        return (min(ps), max(ps)) if ps else (60, 72)

    def n_notes(self):
        return sum(len(t["notes"]) for t in self.tracks)

    # ---------------------------------------------------------- undo
    def _snap(self):
        return [[list(n) for n in t["notes"]] for t in self.tracks], len(self.tracks)

    def _restore(self, s):
        notes, ntr = s
        del self.tracks[ntr:]
        for t, nn in zip(self.tracks, notes):
            t["notes"] = nn
        self.version += 1

    def checkpoint(self):
        """Remember the current notes (one undo step); edits made with undo=False
        afterwards (a mouse drag) are undone together."""
        self._undo.append(self._snap())
        del self._undo[:-MAX_UNDO]
        self._redo = []
        return self

    def drop_checkpoint(self):
        """Forget the last checkpoint (the drag changed nothing)."""
        if self._undo:
            self._undo.pop()
        return self

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self._snap())
        self._restore(self._undo.pop())
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self._snap())
        self._restore(self._redo.pop())
        return True

    def revert(self):
        """Undo the last step without keeping it for redo (a cancelled preview)."""
        if not self._undo:
            return False
        self._restore(self._undo.pop())
        return True

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    # ---------------------------------------------------------- edit
    def _begin(self, undo):
        if undo:
            self.checkpoint()
        self.version += 1

    def add(self, track, start, dur, pitch, vel=90, undo=True):
        """New note; returns it (the list [start, dur, pitch, vel])."""
        self._begin(undo)
        n = [round(max(0.0, float(start)), 6), round(max(MIN_DUR, float(dur)), 6),
             max(0, min(127, int(pitch))), max(1, min(127, int(vel)))]
        self.tracks[track]["notes"].append(n)
        return n

    def remove(self, track, notes, undo=True):
        ids = {id(n) for n in notes}
        if not ids:
            return 0
        self._begin(undo)
        t = self.tracks[track]
        before = len(t["notes"])
        t["notes"] = [n for n in t["notes"] if id(n) not in ids]
        return before - len(t["notes"])

    def move(self, track, notes, dq=0.0, dp=0, undo=True):
        """Shift notes in time (quarters) and pitch (semitones)."""
        self._begin(undo)
        for n in notes:
            n[0] = round(max(0.0, n[0] + dq), 6)
            n[2] = max(0, min(127, n[2] + int(dp)))
        return self

    def set_length(self, track, notes, dur, undo=True):
        self._begin(undo)
        for n in notes:
            n[1] = round(max(MIN_DUR, float(dur)), 6)
        return self

    def set_velocity(self, track, notes, vel, undo=True):
        self._begin(undo)
        for n in notes:
            n[3] = max(1, min(127, int(vel)))
        return self

    def sort(self):
        for t in self.tracks:
            t["notes"].sort(key=lambda n: (n[0], n[2]))
        return self

    def quantize(self, grid="1/16", strength=1.0, ends=False, track=None, notes=None,
                 undo=True):
        """Move the note starts towards the nearest grid point (Ableton style).
        grid: one of GRIDS (or any 'a/b', 'a/bT', '+' combinations); strength 0..1;
        ends: the note ends too (else the length is kept); track: one track (index)
        or None = all; notes: only these notes (of `track`). Returns how many moved."""
        steps = grid_steps(grid)
        if not steps:
            return 0
        strength = max(0.0, min(1.0, float(strength)))
        if notes is not None:
            todo = list(notes)
        elif track is not None:
            todo = list(self.tracks[track]["notes"])
        else:
            todo = [n for t in self.tracks for n in t["notes"]]
        self._begin(undo)
        moved = 0
        for n in todo:
            s, d = n[0], n[1]
            ns = s + strength * (nearest(s, steps) - s)
            if ends:
                e = s + d
                ne = e + strength * (nearest(e, steps) - e)
                if ne <= ns + 1e-6:
                    ne = ns + min(steps) * max(strength, 0.25)
                nd = ne - ns
            else:
                nd = d
            ns, nd = round(max(0.0, ns), 6), round(max(MIN_DUR, nd), 6)
            if abs(ns - s) > 1e-6 or abs(nd - d) > 1e-6:
                moved += 1
            n[0], n[1] = ns, nd
        self.sort()
        return moved

    # ---------------------------------------------------------- find
    def hit(self, track, q, pitch):
        """The note of a track under (q, pitch), the most recent first; None."""
        for n in reversed(self.tracks[track]["notes"]):
            if n[2] == pitch and n[0] <= q < n[0] + n[1]:
                return n
        return None

    def notes_in(self, track, q0, q1, p0, p1):
        """Notes of a track touching the rectangle q0..q1 x p0..p1."""
        q0, q1 = min(q0, q1), max(q0, q1)
        p0, p1 = min(p0, p1), max(p0, p1)
        return [n for n in self.tracks[track]["notes"]
                if p0 <= n[2] <= p1 and n[0] < q1 and n[0] + n[1] > q0]

    # ---------------------------------------------------------- output
    def to_pm(self):
        """pretty_midi object: the tempo map / metre / controllers of the original MIDI
        (or the tempo and metre of the roll), one instrument per track."""
        import pretty_midi
        if self._tmpl is not None:
            pm = copy.deepcopy(self._tmpl)
            old = pm.instruments
        else:
            pm = pretty_midi.PrettyMIDI(initial_tempo=self.bpm, resolution=480)
            pm.time_signature_changes.append(pretty_midi.TimeSignature(self.ts[0], self.ts[1], 0))
            old = []
        res = pm.resolution
        out = []
        for t in self.tracks:
            k = t.get("ins")
            if k is not None and k < len(old):
                ins = old[k]
            else:
                ins = pretty_midi.Instrument(program=t["program"], is_drum=t["is_drum"],
                                             name=t["name"])
            ins.notes = []
            for s, d, p, v in sorted(t["notes"]):
                t0 = pm.tick_to_time(int(round(s * res)))
                t1 = pm.tick_to_time(int(round((s + d) * res)))
                ins.notes.append(pretty_midi.Note(int(v), int(p), t0, max(t1, t0 + 1e-3)))
            out.append(ins)
        pm.instruments = out
        return pm

    def to_midi(self, title=None):
        """New Midi object with the notes of the roll."""
        from .midi import Midi
        m = Midi()
        m.pm = self.to_pm()
        m.source = None
        m.title = title or self.title
        return m

    def apply_to(self, midi):
        """Put the notes of the roll into an existing Midi object (in place)."""
        midi.pm = self.to_pm()
        return midi

    def q_to_s(self, q, pm=None):
        """Seconds of a position in quarters (tempo map of pm / of the roll)."""
        pm = pm or self._tmpl
        if pm is None:
            return q * 60.0 / self.bpm
        return pm.tick_to_time(int(round(q * pm.resolution)))

    def s_to_q(self, t, pm=None):
        pm = pm or self._tmpl
        if pm is None:
            return t * self.bpm / 60.0
        return float(pm.time_to_tick(t)) / float(pm.resolution)

    def __repr__(self):
        tr = ", ".join(f"{t['name']} [{len(t['notes'])}]" for t in self.tracks)
        return (f"Roll({len(self.tracks)} tracks, {self.bars()} bars, {self.bpm:g} bpm, "
                f"{self.ts[0]}/{self.ts[1]}: {tr})")


def _gm_name(program, is_drum=False):
    if is_drum:
        return "Drums"
    from .midiin import GM_NAMES
    return GM_NAMES[int(program) % 128]


def quantize_midi(midi, grid="1/16", strength=1.0, ends=False):
    """Quantize a Midi object in place (all tracks); returns how many notes moved."""
    r = Roll.from_midi(midi)
    k = r.quantize(grid, strength, ends, undo=False)
    r.apply_to(midi)
    return k
