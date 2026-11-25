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

EDITOR TOOLS (owner, 2026-11-25; the Midi editor, not the Free player): edits that also
move the tempo map, time / key signatures, controllers, pitch bends, lyrics and texts of
the MIDI (`_remap`; the template is replaced, never changed, so undo takes it back):
    r.insert_bars(5, 2)          # two empty bars before bar 5 (a note held across: cut,
                                 # its rest continues after them)
    r.delete_bars(5, 6)          # bars 5-6 removed (notes starting there dropped, notes
                                 # held into them shortened), the rest moved back
    r.double(keep_speed=True)    # every value twice as long (tempo x 2: it sounds the same)
    r.resample(0, 0.5)           # track 0 = a line of eighths (rework.resample)
    r.quantize_from_playing(0)   # timing from the playing of track 0 (rework.quantize):
                                 # one tempo, its commonest inter-onset time = an eighth
Bars here are those of the roll (the first time signature, as the bar numbers drawn).
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
    def __init__(self, tracks=None, bpm=120.0, ts=(4, 4), title=None, template=None,
                 end_q=None):
        self.tracks = tracks or []           # [dict(name, program, is_drum, notes, ins)]
        self.end_q = None if end_q is None else float(end_q)   # length if longer than the
                                             # notes (an exercise with empty bars at the end)
        self.bpm = float(bpm)
        self.ts = (int(ts[0]), int(ts[1]))
        self.title = title
        self._tmpl = template                # pretty_midi without notes: tempo map, metre, CCs
        self._undo = []
        self._redo = []
        self.version = 0                     # +1 at every change (views redraw)

    # ---------------------------------------------------------- build
    @classmethod
    def from_midi(cls, midi, title=None, end_q=None):
        """Roll of a Midi object (or a pretty_midi object): times converted to quarters
        with its tempo map; tempo changes, time/key signatures, controllers and pitch
        bends are kept for to_midi(). end_q: length in quarters if longer than the notes."""
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
        return cls(tracks, bpm, ts, title or getattr(midi, "title", None), tmpl, end_q)

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
        return max(self.bar_q, end, self.end_q or 0.0)

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
        # the template is never changed in place (`_remap` makes a new one): a reference
        return ([[list(n) for n in t["notes"]] for t in self.tracks], len(self.tracks),
                self._tmpl, self.bpm, self.end_q)

    def _restore(self, s):
        notes, ntr, self._tmpl, self.bpm, self.end_q = s
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

    # ---------------------------------------------------------- editor tools (2026-11-25)
    def _template(self):
        """The template (tempo map, metre, controllers…); a roll without one gets one made
        from its tempo and metre."""
        if self._tmpl is not None:
            return self._tmpl
        import pretty_midi
        pm = pretty_midi.PrettyMIDI(initial_tempo=self.bpm, resolution=480)
        pm.time_signature_changes.append(pretty_midi.TimeSignature(self.ts[0], self.ts[1], 0))
        return pm

    def _remap(self, fq, tempo=None, tempo_factor=1.0):
        """A NEW template whose events are moved in time by fq(quarters) -> quarters
        (non-decreasing): tempo changes (bpm x tempo_factor; tempo = one constant tempo
        instead), time / key signatures, lyrics, texts (the loop marker of a backing too),
        controllers and pitch bends. Events that land on the same place: the last wins."""
        import json
        old = self._template()
        res = float(old.resolution)
        pm = copy.deepcopy(old)

        def oq(t):
            return float(old.time_to_tick(t)) / res

        def nq(q):
            return max(0.0, float(fq(q)))

        if tempo is not None:
            scales = [(0, 60.0 / (float(tempo) * res))]
        else:
            scales = []
            for tick, sc in old._tick_scales:
                nt = int(round(nq(tick / res) * res))
                sc = sc / float(tempo_factor)
                if scales and nt <= scales[-1][0]:
                    scales[-1] = (scales[-1][0], sc)
                else:
                    scales.append((nt, sc))
            if scales[0][0] != 0:
                scales.insert(0, (0, scales[0][1]))
        events = []                                      # (object, new quarter)
        for e in pm.time_signature_changes + pm.key_signature_changes + list(pm.lyrics) \
                + list(getattr(pm, "text_events", None) or []):
            events.append((e, nq(oq(e.time))))
        for ins in pm.instruments:
            for e in list(ins.control_changes) + list(ins.pitch_bends):
                events.append((e, nq(oq(e.time))))
        top = max([q for _, q in events] + [nq(self.length_q()), scales[-1][0] / res])
        pm._tick_scales = scales
        pm._update_tick_to_time(int((top + 64) * res))
        for e, q in events:
            e.time = pm.tick_to_time(int(round(q * res)))
        try:
            from .backing import MARKER
            for e in getattr(pm, "text_events", None) or []:
                txt = (e.text or "").strip()
                if txt.startswith(MARKER):
                    d = json.loads(txt[len(MARKER):].strip())
                    d["b_q"], d["c_q"] = nq(float(d["b_q"])), nq(float(d["c_q"]))
                    e.text = f"{MARKER} {json.dumps(d)}"
        except Exception:
            pass

        def last_wins(lst):
            out = {}
            for e in sorted(lst, key=lambda e: e.time):
                out[round(e.time, 6)] = e
            return [out[k] for k in sorted(out)]

        pm.time_signature_changes = last_wins(pm.time_signature_changes)
        pm.key_signature_changes = last_wins(pm.key_signature_changes)
        self._tmpl = pm
        self.bpm = float(tempo) if tempo is not None else self.bpm * float(tempo_factor)
        return pm

    def insert_bars(self, at_bar, n=1, undo=True):
        """n empty bars before bar `at_bar` (1 = at the start; bars() + 1 = at the end).
        Everything from there moves later; a note held across that point is cut there and
        its rest continues after the new bars."""
        n = int(n)
        if n < 1:
            return 0
        a = max(0, int(at_bar) - 1) * self.bar_q
        L = n * self.bar_q
        old_len = max(self.length_q(), a)
        self._begin(undo)
        for t in self.tracks:
            more = []
            for nt in t["notes"]:
                s, d = nt[0], nt[1]
                e = s + d
                if s >= a - 1e-9:
                    nt[0] = round(s + L, 6)
                elif e > a + 1e-9:
                    nt[1] = round(max(MIN_DUR, a - s), 6)
                    more.append([round(a + L, 6), round(max(MIN_DUR, e - a), 6), nt[2], nt[3]])
            t["notes"] += more

        def fq(q):
            return q if q < a - 1e-9 else q + L

        self._remap(fq)
        self.end_q = fq(old_len)
        self.sort()
        return n

    def delete_bars(self, first, last, undo=True):
        """Bars first..last removed: notes starting in them dropped, notes held into them
        shortened, everything after moved back."""
        first, last = int(first), int(last)
        if last < first:
            first, last = last, first
        a = max(0, first - 1) * self.bar_q
        b = max(a, last * self.bar_q)
        L = b - a
        if L <= 0:
            return 0
        old_len = self.length_q()
        self._begin(undo)
        dropped = 0
        for t in self.tracks:
            keep = []
            for nt in t["notes"]:
                s, d = nt[0], nt[1]
                e = s + d
                if a - 1e-9 <= s < b - 1e-9:
                    dropped += 1
                    continue
                if s < a - 1e-9:
                    if e > a + 1e-9:
                        nt[1] = round(max(MIN_DUR, a + max(0.0, e - b) - s), 6)
                else:
                    nt[0] = round(s - L, 6)
                keep.append(nt)
            t["notes"] = keep

        def fq(q):
            return q if q < a - 1e-9 else (a if q < b - 1e-9 else q - L)

        self._remap(fq)
        self.end_q = max(self.bar_q, fq(old_len))
        self.sort()
        return dropped

    def double(self, keep_speed=True, undo=True):
        """MATLAB `double` (rework.double): every value twice as long, the piece twice the
        bars. keep_speed=True: every tempo x 2 too, so it SOUNDS the same (only the
        writing changes); False: it plays twice as slowly."""
        old_len = self.length_q()
        self._begin(undo)
        for t in self.tracks:
            for nt in t["notes"]:
                nt[0], nt[1] = round(nt[0] * 2, 6), round(nt[1] * 2, 6)
        self._remap(lambda q: 2.0 * q, tempo_factor=2.0 if keep_speed else 1.0)
        self.end_q = 2.0 * old_len
        return self

    def resample(self, track, step=0.5, undo=True):
        """MATLAB `resample` (rework.resample) on one track: the melody sampled every
        `step` quarters (default an eighth): at every grid point the note sounding nearest
        to it (start or end of a note), one voice (in a chord the highest note); the track
        becomes a line of equal values to the end of its last note. Returns the notes."""
        import math
        t = self.tracks[track]
        if not t["notes"] or step <= 0:
            return 0
        top = {}
        for s, d, p, v in t["notes"]:
            if s not in top or p > top[s][1]:
                top[s] = (d, p, v)
        knots = []                                   # (time, pitch, velocity)
        for s in sorted(top):
            d, p, v = top[s]
            knots.append((s, p, v))
            knots.append((s + max(d - 1.0 / 16, 0.0), p, v))
        knots.sort()
        start = math.floor(knots[0][0] / step + 1e-9) * step
        end = max(s + d for s, d, _, _ in t["notes"])
        self._begin(undo)
        out, k, q = [], 0, start
        while q < end - 1e-9:
            while k + 1 < len(knots) and abs(knots[k + 1][0] - q) <= abs(knots[k][0] - q):
                k += 1
            out.append([round(q, 6), float(step), int(knots[k][1]), int(knots[k][2])])
            q += step
        t["notes"] = out
        return len(out)

    def quantize_from_playing(self, track, undo=True):
        """MATLAB `quantize` (rework.quantize) for a piece played WITHOUT a metronome: the
        basic period T0 = the commonest time between two onsets of `track` (seconds) is an
        EIGHTH; the onsets of the track go to whole numbers of T0 (accumulated) and each of
        its notes lasts to the next onset (the last: an eighth; a chord = notes with the
        same onset). The other tracks and every event of the MIDI follow the same time map
        (linear between the onsets of the track). The tempo becomes ONE tempo 60 / (2 T0).
        Returns (T0 seconds, bpm)."""
        from .rework import basic_period, stamps
        t = self.tracks[track]
        tm = self._template()
        sec = {id(n): self.q_to_s(n[0], tm) for n in t["notes"]}
        onsets = sorted({round(x, 6) for x in sec.values()})
        if len(onsets) < 2:
            raise ValueError("at least two notes at different times are needed in the track")
        t0s = [x - onsets[0] for x in onsets]
        T0 = basic_period(t0s)
        qk = [x / T0 * 0.5 for x in stamps(t0s, T0)]

        def map_s(x):
            import bisect
            if x <= onsets[0]:
                return qk[0] + (x - onsets[0]) / T0 * 0.5
            if x >= onsets[-1]:
                return qk[-1] + (x - onsets[-1]) / T0 * 0.5
            i = bisect.bisect_right(onsets, x) - 1
            f = (x - onsets[i]) / (onsets[i + 1] - onsets[i])
            return qk[i] + f * (qk[i + 1] - qk[i])

        def fq(q):
            return max(0.0, map_s(self.q_to_s(q, tm)))

        new = {}                                         # notes of the track: start
        for n in t["notes"]:
            new[id(n)] = qk[onsets.index(round(sec[id(n)], 6))]
        starts = sorted(set(new.values()))
        others = []
        for k, tr in enumerate(self.tracks):
            if k == track:
                continue
            for n in tr["notes"]:
                s1, e1 = fq(n[0]), fq(n[0] + n[1])
                others.append((n, s1, max(MIN_DUR, e1 - s1)))
        self._begin(undo)
        for n in t["notes"]:
            s1 = new[id(n)]
            nxt = next((x for x in starts if x > s1 + 1e-9), None)
            n[0] = round(max(0.0, s1), 6)
            n[1] = round(max(MIN_DUR, (nxt - s1) if nxt is not None else 0.5), 6)
        for n, s1, d1 in others:
            n[0], n[1] = round(s1, 6), round(d1, 6)
        self.end_q = None
        bpm = 60.0 / (2 * T0)
        self._remap(fq, tempo=bpm)
        self.sort()
        return T0, bpm

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
