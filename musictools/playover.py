"""
PLAY OVER MIDI (owner, 2026-11-08): open a MIDI, choose up to three tracks to READ ("show
and mute": they are shown on the staff and are silent), play them while the app plays all
the other tracks. No grade ("n/a"): the trumpet cannot be heard among a whole band. It is
an exercise object only so that it can go into routines (parts to study): it remembers ONLY
the MIDI (always inside the exercise: it is a MIDI that is played) and the tracks to read
(plus tempo %, accompaniment volume, click). It keeps no results and writes nothing in the
diary; in a routine, playing it to the end marks it done for the session only
(`tasks.mark_done`). No Qt.

    po = PlayOver.from_midi(midi)                 # no track chosen: the user chooses
    po.readable()                                 # [(track index, label)]
    po.set_tracks([0, 2])                         # at most MAX_TRACKS
    po.score()                                    # Score of the tracks shown, WRITTEN
    po.accompaniment()                            # Midi of the other tracks (velocity scaled)

Written parts: `theory.written_part(program)` (transposition and clef of every General MIDI
instrument: trumpet in Bb, alto sax in Eb, horn in F, bass an octave lower…); the key
signature of each part is estimated on its WRITTEN notes. A trumpet part is one voice (the
highest note of a chord, as every trumpet exercise).
"""
import base64
import copy
import datetime as _dt
import io
import uuid

from . import theory as th

MAX_TRACKS = 3
FORMAT = "musikite-playover"
LABEL = "Play over MIDI"
TRUMPET_PROGRAMS = (56, 59)


def _b64(pm):
    buf = io.BytesIO()
    pm.write(buf)
    return base64.b64encode(buf.getvalue()).decode("ascii")


class PlayOver:
    graded = False                      # grade n/a (tasks: never in the means)
    kind = "play_over"
    label = LABEL

    def __init__(self, midi_b64, tracks=None, title=None, source="", tempo_pct=100,
                 volume_pct=100, click=True, uid=None, created=None, bar_from=None,
                 bar_to=None):
        self.midi_b64 = midi_b64
        self.source = source or ""
        self.uid = uid or uuid.uuid4().hex
        self.created = created or _dt.datetime.now().isoformat(timespec="seconds")
        self.tempo_pct = int(tempo_pct)
        self.volume_pct = int(volume_pct)
        self.click = bool(click)
        self.bar_from = int(bar_from) if bar_from else None   # bars to play (owner): numbers
        self.bar_to = int(bar_to) if bar_to else None         # of the MIDI, None = all
        self.results = {}               # never filled (no grade)
        self.instrument = None
        self._pm = None
        self._score = None
        self.tracks = []
        self.set_tracks(tracks or [])           # none by default: the user chooses (owner)
        self.title = title or self.make_title()

    # ---------------------------------------------------------- MIDI
    @classmethod
    def from_midi(cls, midi, tracks=None, **kw):
        """From a Midi object (or a Score: its MIDI)."""
        from .midi import Midi
        if not isinstance(midi, Midi):
            midi = midi.to_midi()
        src = getattr(midi, "title", None) or (
            __import__("os").path.splitext(__import__("os").path.basename(midi.source))[0]
            if midi.source else "MIDI")
        return cls(_b64(midi.pm), tracks, source=src, **kw)

    @property
    def pm(self):
        if self._pm is None:
            import pretty_midi
            self._pm = pretty_midi.PrettyMIDI(io.BytesIO(base64.b64decode(self.midi_b64)))
        return self._pm

    def midi(self):
        from .midi import Midi
        m = Midi()
        m.pm = copy.deepcopy(self.pm)
        m.title = self.source
        return m

    # ---------------------------------------------------------- tracks
    def track_label(self, i):
        ins = self.pm.instruments[i]
        w = th.written_part(ins.program, ins.is_drum, ins.name)
        name = (ins.name or "").strip() or w["name"]
        return f"{i + 1}. {name}" + (f" ({w['name']})" if w["name"] not in name else "")

    def readable(self):
        """[(track index, label)]: the tracks that can be read (notes, not drums)."""
        return [(i, self.track_label(i)) for i, ins in enumerate(self.pm.instruments)
                if ins.notes and not ins.is_drum]

    def is_trumpet(self, i):
        ins = self.pm.instruments[i]
        return th.written_part(ins.program, ins.is_drum, ins.name)["name"] == "Trumpet in Bb"

    def set_tracks(self, tracks):
        ok = {i for i, _ in self.readable()}
        t = [int(i) for i in tracks if int(i) in ok]
        t = sorted(dict.fromkeys(t))[:MAX_TRACKS]
        if t != self.tracks:
            self.tracks = t
            self._score = None
        return self.tracks

    def make_title(self):
        names = ", ".join(self.track_label(i).split(". ", 1)[1] for i in self.tracks)
        bars = self.bars_text()
        return (f"{LABEL}: {self.source}" + (f" – {names}" if names else "")
                + (f" – {bars}" if bars else ""))

    # ---------------------------------------------------------- score / sound
    # ---------------------------------------------------------- bars to play
    def bar_starts(self):
        """Start (quarters) of every bar of the MIDI, from its time signatures (bar 1 at 0;
        a pickup is not detected), plus the end of the last bar."""
        pm = self.pm
        res = float(pm.resolution)
        end = pm.time_to_tick(pm.get_end_time()) / res
        ts = sorted(((pm.time_to_tick(t.time) / res, t.numerator, t.denominator)
                     for t in pm.time_signature_changes), key=lambda x: x[0]) or [(0.0, 4, 4)]
        if ts[0][0] > 0:
            ts.insert(0, (0.0, 4, 4))
        out, q = [], 0.0
        for k, (q0, num, den) in enumerate(ts):
            nxt = ts[k + 1][0] if k + 1 < len(ts) else None
            bar = num * 4.0 / den
            q = max(q, q0)
            while (nxt is None and q < end - 1e-6) or (nxt is not None and q < nxt - 1e-6):
                out.append(q)
                q += bar
        out.append(q)
        return out

    def n_bars(self):
        return max(1, len(self.bar_starts()) - 1)

    def set_bars(self, first=None, last=None):
        """Bars to play (MIDI numbering, inclusive); None / 0 = from the start / to the end."""
        n = self.n_bars()
        a = max(1, min(n, int(first))) if first else None
        b = max(1, min(n, int(last))) if last else None
        if a and b and b < a:
            a, b = b, a
        if (a, b) != (self.bar_from, self.bar_to):
            self.bar_from, self.bar_to = a, b
            self._score = None
        return a, b

    def range_q(self):
        """(start, end) in quarters of the bars to play."""
        st = self.bar_starts()
        n = len(st) - 1
        a = (self.bar_from or 1) - 1
        b = min(n, self.bar_to or n)
        return st[a], st[b]

    def bars_text(self):
        if not (self.bar_from or self.bar_to):
            return ""
        return f"bars {self.bar_from or 1}-{self.bar_to or self.n_bars()}"

    def score(self):
        """Score of the tracks shown, at WRITTEN pitch for each instrument, with its clef and
        its key signature (estimated on the written notes); only the bars to play, with
        their ORIGINAL numbers."""
        if self._score is not None:
            return self._score
        full = self._full_score()
        if self.bar_from or self.bar_to:
            from .score import Score
            ex = full.m21.measures(self.bar_from or 1, self.bar_to or self.n_bars())
            sc = Score(ex, self.title, False)
            sc.source = full.source
            self._score = sc
        else:
            self._score = full
        return self._score

    def _full_score(self):
        if getattr(self, "_full", None) is not None and self._full[0] == tuple(self.tracks):
            return self._full[1]
        if not self.tracks:
            raise ValueError("choose the tracks to read (Show and mute)")
        import pretty_midi
        from .midi import Midi
        from .score import Score
        pm = copy.deepcopy(self.pm)
        keep, clefs, used = [], [], {}
        for i in self.tracks:
            ins = pm.instruments[i]
            w = th.written_part(ins.program, ins.is_drum, ins.name)
            notes = ins.notes
            if self.is_trumpet(i):                     # trumpet: one voice (highest note)
                top = {}
                for n in notes:
                    k = round(n.start, 4)
                    if k not in top or n.pitch > top[k].pitch:
                        top[k] = n
                notes = sorted(top.values(), key=lambda n: n.start)
            new = pretty_midi.Instrument(th.program_of_name(ins.name) or ins.program,
                                         name=w["name"])
            new.notes = [pretty_midi.Note(n.velocity, n.pitch + w["transposition"], n.start,
                                          n.end) for n in notes]
            used[w["name"]] = used.get(w["name"], 0) + 1
            keep.append(new)
            clefs.append(w["clef"])
        same = {k for k, v in used.items() if v > 1}  # two trumpets: "Trumpet in Bb 1", "… 2"
        cnt = {}
        for ins in keep:
            if ins.name in same:
                cnt[ins.name] = cnt.get(ins.name, 0) + 1
                ins.name = f"{ins.name} {cnt[ins.name]}"
        pm.instruments = keep
        pm.key_signature_changes = []                 # concert keys: estimated again, written
        m = Midi()
        m.pm = pm
        s = Score.from_midi(m, title=self.title, written=False)
        # the notes are ALREADY written (transposition applied above): mark the score so,
        # or the MusicXML export transposes the transposing instruments AGAIN (bug
        # 2026-11-09: a trumpet D concert shown as F# instead of E)
        s.m21.atSoundingPitch = False
        for p in s.m21.parts:
            p.atSoundingPitch = False
        _clefs(s, clefs)
        self._full = (tuple(self.tracks), s)
        return s

    def accompaniment(self):
        """Midi of every track NOT shown (shown = muted), velocities × volume %."""
        from .midi import Midi
        pm = copy.deepcopy(self.pm)
        f = max(0.0, self.volume_pct / 100.0)
        pm.instruments = [ins for i, ins in enumerate(pm.instruments) if i not in self.tracks]
        for ins in pm.instruments:
            for n in ins.notes:
                n.velocity = max(1, min(127, int(round(n.velocity * f))))
        m = Midi()
        m.pm = pm
        return m

    def end_q(self):
        """Length in quarters of what is played (the bars chosen; the whole MIDI: also after
        the last note of the parts shown)."""
        a, b = self.range_q()
        return b - a

    def start_q(self):
        """Where the bars to play begin in the MIDI (quarters)."""
        return self.range_q()[0]

    # ---------------------------------------------------------- object
    def copy(self):
        return PlayOver(self.midi_b64, list(self.tracks), self.title, self.source,
                        self.tempo_pct, self.volume_pct, self.click,
                        bar_from=self.bar_from, bar_to=self.bar_to)

    def __repr__(self):
        return f"PlayOver('{self.title}', tracks {[i + 1 for i in self.tracks]})"

    def to_dict(self):
        return dict(kind=self.kind, title=self.title, source=self.source, uid=self.uid,
                    created=self.created, tracks=list(self.tracks), tempo_pct=self.tempo_pct,
                    volume_pct=self.volume_pct, click=self.click, bar_from=self.bar_from,
                    bar_to=self.bar_to, midi=self.midi_b64)

    @classmethod
    def from_dict(cls, d):
        return cls(d["midi"], d.get("tracks"), d.get("title"), d.get("source", ""),
                   d.get("tempo_pct", 100), d.get("volume_pct", 100), d.get("click", True),
                   d.get("uid"), d.get("created"), d.get("bar_from"), d.get("bar_to"))


def _clefs(score, clefs):
    """Clef of each part from the instrument table (None: the one music21 chose)."""
    from music21 import clef
    make = {"treble": clef.TrebleClef, "bass": clef.BassClef, "alto": clef.AltoClef}
    for part, c in zip(score.m21.parts, clefs):
        if c not in make:
            continue
        for old in list(part.recurse().getElementsByClass("Clef")):
            old.activeSite.remove(old)
        ms = part.getElementsByClass("Measure")
        (ms[0] if len(ms) else part).insert(0, make[c]())
    return score
