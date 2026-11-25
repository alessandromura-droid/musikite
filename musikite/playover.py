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

PLAY-ALONG GRADED (owner, 2026-11-24): with `grade` on, ONE track shown (`graded_track`)
is graded from the microphone as Read & play (`playcheck.PlayCheck`): the accompaniment is
rendered with the soundfont into the take (`backing`, after the count-in bar) at ONE
constant tempo (the first tempo of the bars to play × Tempo %; tempo changes are not
followed in a graded take: `play_along()` says so). It works ONLY WITH HEADPHONES (the
microphone must not hear the band): the tab warns when the output is the loudspeakers.
Every take goes to the practice diary (kind 'play_along'); the exercise keeps no results.

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
                 bar_to=None, grade=False, graded_track=None):
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
        self.grade = bool(grade)         # play-along graded (owner, 2026-11-24)
        self.graded_track = None if graded_track is None else int(graded_track)
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

    def fingering_name(self, i):
        """Name of fingerings.INSTRUMENTS for track i (None: no fingerings)."""
        from .fingerings import instrument_of
        ins = self.pm.instruments[i]
        w = th.written_part(ins.program, ins.is_drum, ins.name)["name"]
        return instrument_of(w) or instrument_of(w.lower())

    def has_positions(self):
        """A track shown has fingerings (valves / slide positions)."""
        return any(self.fingering_name(i) for i in self.tracks)

    def score(self, positions=False):
        """Score of the tracks shown, at WRITTEN pitch for each instrument, with its clef and
        its key signature (estimated on the written notes); only the bars to play, with
        their ORIGINAL numbers. positions=True (owner, 2026-11-23: "Show positions" as in
        Read & play): a COPY with the valves / slide positions under the notes of every
        part that has fingerings."""
        if positions and self.has_positions():
            return self._with_positions(self.score())
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

    def _with_positions(self, sc):
        """Copy of a score of the tracks shown with the fingering of every written note as
        a lyric (parts in the order of self.tracks); tied continuations and chords none."""
        from .score import Score
        from .fingerings import fingering
        m = copy.deepcopy(sc.m21)
        for part, i in zip(m.parts, self.tracks):
            name = self.fingering_name(i)
            if not name:
                continue
            for n in part.recurse().notes:
                if n.isChord:
                    continue
                if n.tie is not None and n.tie.type in ("stop", "continue"):
                    continue
                f = fingering(name, n.pitch.midi)       # the notes are already WRITTEN
                if f:
                    n.addLyric(f)
        out = Score(m, sc.title, False)
        out.source = getattr(sc, "source", None)
        return out

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

    # ---------------------------------------------------------- play-along graded
    def graded(self):
        """The track graded: graded_track if shown, else the first track shown."""
        if self.graded_track in self.tracks:
            return self.graded_track
        return self.tracks[0] if self.tracks else None

    def tempo_bpm(self):
        """(bpm at the start of the bars to play × Tempo %, True if the tempo changes inside
        them)."""
        pm = self.pm
        res = float(pm.resolution)
        a, b = self.range_q()
        times, tempi = pm.get_tempo_changes()
        qs = [pm.time_to_tick(t) / res for t in times]
        cur = float(tempi[0]) if len(tempi) else 120.0
        changes = False
        for q, bpm in zip(qs, tempi):
            if q <= a + 1e-6:
                cur = float(bpm)
            elif q < b - 1e-6 and abs(float(bpm) - cur) > 0.5:
                changes = True
        return cur * self.tempo_pct / 100.0, changes

    def accompaniment_audio(self, bpm, lead_q, fs, sf2, gain=0.5):
        """The accompaniment (tracks not shown, volume %) of the bars to play, at ONE
        constant tempo `bpm`, rendered with the soundfont: float array at fs, sample 0 =
        the first count-in click (the music starts after lead_q quarters)."""
        import numpy as np
        import pretty_midi
        src = self.accompaniment().pm
        res = float(src.resolution)
        a, b = self.range_q()
        spq = 60.0 / float(bpm)
        out = pretty_midi.PrettyMIDI(initial_tempo=float(bpm))
        for ins in src.instruments:
            new = pretty_midi.Instrument(ins.program, is_drum=ins.is_drum, name=ins.name)
            for n in ins.notes:
                q0 = src.time_to_tick(n.start) / res
                q1 = src.time_to_tick(n.end) / res
                if q0 < a - 1e-6 or q0 >= b - 1e-6:
                    continue
                new.notes.append(pretty_midi.Note(n.velocity, n.pitch, (q0 - a) * spq,
                                                  (min(q1, b) - a) * spq))
            for cc in ins.control_changes:
                q = src.time_to_tick(cc.time) / res
                if a - 1e-6 <= q < b:
                    new.control_changes.append(pretty_midi.ControlChange(cc.number, cc.value,
                                                                         (q - a) * spq))
            if new.notes:
                out.instruments.append(new)
        lead = np.zeros(int(round(lead_q * spq * fs)))
        if not out.instruments:
            return lead.astype(np.float32)
        y = out.fluidsynth(fs=fs, sf2_path=sf2)
        if y is None or not len(y):
            raise RuntimeError("the accompaniment could not be rendered")
        y = gain * y / max(1e-9, float(np.max(np.abs(y))))
        return np.concatenate([lead, y]).astype(np.float32)

    def play_along(self, user=None, click=True, sf2=None):
        """dict(pc=PlayCheck of one graded take, part=index of the graded part in the
        score shown, track, bpm, tempo_changes, instrument)."""
        from .playcheck import PlayCheck, FS
        from .phrase import instrument_of_program, DETECT_RANGE
        from .midi import Midi
        t = self.graded()
        if t is None:
            raise ValueError("choose the tracks to read (Show and mute)")
        sf2 = sf2 or Midi._default_sf2
        if not sf2:
            raise RuntimeError("no soundfont: Settings > Soundfont")
        part = self.tracks.index(t)
        ins = self.pm.instruments[t]
        w = th.written_part(ins.program, ins.is_drum, ins.name)
        prog = th.program_of_name(ins.name) or ins.program
        played = instrument_of_program(prog)
        bpm, changes = self.tempo_bpm()
        sc = self.score()
        ts = sc.time_signature().split("/")
        lead_q = int(ts[0]) * 4.0 / float(ts[1])
        backing = self.accompaniment_audio(bpm, lead_q, FS, sf2)
        pc = PlayCheck(sc, part, None, bpm, int(w["transposition"]), user=user, click=click,
                       backing=backing, instrument=played,
                       detect_range=DETECT_RANGE.get(played))
        return dict(pc=pc, part=part, track=t, bpm=bpm, tempo_changes=changes,
                    instrument=played)

    def diary_key(self):
        return f"play_along:{self.uid}:{self.graded()}"

    # ---------------------------------------------------------- object
    def edited(self, midi):
        """EDITED IN THE PIANO ROLL (owner, 2026-11-25): a NEW Play over MIDI with the
        edited MIDI, the same tracks (those still readable), tempo %, volume, click, grade;
        the bars to play are reset (the bars may have changed). Title "… – edited"."""
        new = PlayOver(_b64(midi.pm), None, source=self.source, tempo_pct=self.tempo_pct,
                       volume_pct=self.volume_pct, click=self.click, grade=self.grade)
        new.set_tracks(self.tracks)
        if self.graded_track in new.tracks:
            new.graded_track = self.graded_track
        new.title = f"{self.title} – edited"
        return new

    def copy(self):
        return PlayOver(self.midi_b64, list(self.tracks), self.title, self.source,
                        self.tempo_pct, self.volume_pct, self.click,
                        bar_from=self.bar_from, bar_to=self.bar_to, grade=self.grade,
                        graded_track=self.graded_track)

    def __repr__(self):
        return f"PlayOver('{self.title}', tracks {[i + 1 for i in self.tracks]})"

    def to_dict(self):
        return dict(kind=self.kind, title=self.title, source=self.source, uid=self.uid,
                    created=self.created, tracks=list(self.tracks), tempo_pct=self.tempo_pct,
                    volume_pct=self.volume_pct, click=self.click, bar_from=self.bar_from,
                    bar_to=self.bar_to, grade=self.grade, graded_track=self.graded_track,
                    midi=self.midi_b64)

    @classmethod
    def from_dict(cls, d):
        return cls(d["midi"], d.get("tracks"), d.get("title"), d.get("source", ""),
                   d.get("tempo_pct", 100), d.get("volume_pct", 100), d.get("click", True),
                   d.get("uid"), d.get("created"), d.get("bar_from"), d.get("bar_to"),
                   d.get("grade", False), d.get("graded_track"))


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
