"""
Recording from the MIDI keyboard (no Qt): Practice > Free player > Rec.

A recording is a list of PARTS, one per take, each with the GM instrument it was
played with: record a take with the trumpet, then another one with the piano while
the first one plays back (overdub), and so on. Optional metronome (one count-in bar
+ clicks). The notes are kept in quarter notes from the first beat after the
count-in; `to_midi()` gives a Midi object (one instrument per part, the tempo of
the recording), `to_score()` a Score (music21 quantization: sixteenths and eighth
triplets).

    r = Recorder(bpm=90, ts=(4, 4))
    events, lead = r.take_events(click=True)        # clicks (+ the parts already recorded)
    r.start(program=56, t_zero=heard_time_of_event_0 + lead)
    r.note_on(60, 100, t); r.note_off(60, t2)      # perf_counter times
    r.stop()
    r.to_score()
"""
import time

from .realtime import click_events, midi_events, DRUM_CH

MAX_TAKE_S = 30 * 60                     # clicks scheduled for at most 30 minutes


class Recorder:
    def __init__(self, bpm=90, ts=(4, 4), title="Recording"):
        self.bpm = float(bpm)
        self.ts = (int(ts[0]), int(ts[1]))
        self.title = title
        self.parts = []                   # [dict(program, name, notes=[[start_q, dur_q, pitch, vel]])]
        self._cur = None
        self._open = {}
        self._t_zero = None

    # ---------------------------------------------------------- timing
    @property
    def beat_q(self):
        return 4.0 / self.ts[1]

    @property
    def bar_q(self):
        return self.ts[0] * self.beat_q

    def q_per_s(self):
        return self.bpm / 60.0

    def take_events(self, click=True, live_channel=15):
        """Real-time events of a take, t = 0 at the first event: one count-in bar of
        clicks + clicks for the whole take (click=True; else none), and the parts
        already recorded played back (overdub). Returns (events, lead seconds:
        when the first beat of the music is heard). The channel used for the live
        keyboard (live_channel, and channel 0 used by "from keyboard") is kept free."""
        spb = self.beat_q * 60.0 / self.bpm
        lead = self.ts[0] * spb if click else 0.0
        ev = []
        if click:
            n = self.ts[0] + int(MAX_TAKE_S / spb)
            ev += click_events(n, spb, self.ts[0])
        if self.parts:
            pm = self.to_midi().pm
            free = [c for c in range(1, 15) if c not in (DRUM_CH, live_channel)]
            chmap = {}
            for e in midi_events(pm, offset=lead):    # the keyboard keeps channels 0 and 15
                if e[2] != DRUM_CH:
                    c = chmap.setdefault(e[2], free[len(chmap) % len(free)])
                    e = (e[0], e[1], c, e[3], e[4], e[5])
                ev.append(e)
        return ev, lead

    # ---------------------------------------------------------- recording
    def start(self, program=0, t_zero=None, name=None):
        """New take (part) with a GM program; t_zero = perf_counter instant of the
        first beat of the music (after the count-in)."""
        from .midiin import GM_NAMES
        self._cur = dict(program=int(program), name=name or GM_NAMES[int(program) % 128],
                         notes=[])
        self._open = {}
        self._t_zero = time.perf_counter() if t_zero is None else float(t_zero)
        return self

    @property
    def recording(self):
        return self._cur is not None

    def now_q(self, t=None):
        """Position (quarters from the first beat) of a perf_counter instant."""
        if self._t_zero is None:
            return 0.0
        return ((time.perf_counter() if t is None else t) - self._t_zero) * self.q_per_s()

    def note_on(self, pitch, vel, t=None):
        if self._cur is None:
            return
        self._open[int(pitch)] = (self.now_q(t), int(vel))

    def note_off(self, pitch, t=None):
        if self._cur is None:
            return
        o = self._open.pop(int(pitch), None)
        if o is None:
            return
        s, v = o
        e = self.now_q(t)
        if e <= 0:                                    # played during the count-in: ignored
            return
        s = max(0.0, s)
        self._cur["notes"].append([round(s, 4), round(max(0.05, e - s), 4), int(pitch), v])

    def stop(self, t=None):
        """End of the take: keys still down are closed; an empty take is dropped.
        Returns the part (or None)."""
        if self._cur is None:
            return None
        for p in list(self._open):
            self.note_off(p, t)
        part, self._cur = self._cur, None
        if part["notes"]:
            part["notes"].sort()
            self.parts.append(part)
            return part
        return None

    def clear(self):
        self.parts = []
        self._cur = None
        self._open = {}

    def current_notes(self):
        """Notes of the take in progress (for a live display)."""
        return list(self._cur["notes"]) if self._cur else []

    # ---------------------------------------------------------- output
    def to_midi(self, with_current=False):
        """Midi object: one instrument per part (its GM program), tempo of the recording."""
        import pretty_midi
        from .midi import Midi
        spq = 60.0 / self.bpm
        pm = pretty_midi.PrettyMIDI(initial_tempo=self.bpm)
        pm.time_signature_changes.append(pretty_midi.TimeSignature(self.ts[0], self.ts[1], 0))
        parts = list(self.parts)
        if with_current and self._cur and self._cur["notes"]:
            parts.append(self._cur)
        for part in parts:
            ins = pretty_midi.Instrument(program=part["program"], name=part["name"])
            for s, d, p, v in part["notes"]:
                ins.notes.append(pretty_midi.Note(int(v), int(p), s * spq, (s + d) * spq))
            pm.instruments.append(ins)
        m = Midi()
        m.pm = pm
        m.source = None
        return m

    def to_score(self, with_current=False, title=None):
        """Score of the recording (or an empty bar if nothing was played yet)."""
        from .score import Score
        if not self.parts and not (with_current and self._cur and self._cur["notes"]):
            return empty_score(self.ts, self.bpm, title or self.title)
        return Score.from_midi(self.to_midi(with_current), title=title or self.title)


def empty_score(ts=(4, 4), bpm=90, title="Recording", bars=2):
    """A Score with empty bars (whole-bar rests), treble clef."""
    from music21 import stream, meter, note, tempo, metadata, clef
    from .score import Score
    s = stream.Score()
    s.metadata = metadata.Metadata(title=title)
    p = stream.Part()
    for k in range(bars):
        m = stream.Measure(number=k + 1)
        if k == 0:
            m.append(clef.TrebleClef())
            m.append(meter.TimeSignature(f"{ts[0]}/{ts[1]}"))
            m.append(tempo.MetronomeMark(number=bpm))
        r = note.Rest(quarterLength=ts[0] * 4.0 / ts[1])
        r.fullMeasure = True
        m.append(r)
        p.append(m)
    s.append(p)
    return Score(s, title)
