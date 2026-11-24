"""
Notes object: a PERFORMANCE (e.g. a trumpet recording) as a Midi object
with extra data per note that a MIDI file cannot hold.

Python counterpart of the MATLAB `notes` object returned by
audiodata.get_notes (mysmartmusic_obj): times in seconds, not quantized,
no bars. Everything a Midi does (play, merge, to_score, to_pdf, write)
works on it; write() saves only the MIDI part.

Per-note table (pandas DataFrame, `n.table()`):
    track, start, end, dur (s), pitch (MIDI, concert), name (concert),
    written (name at written pitch, e.g. Bb trumpet a tone higher),
    cents (deviation from the tempered note, + = sharp), velocity,
    confidence (0..1, from the pitch detector; NaN if unknown)

    n = Notes(bpm=90)                              empty performance
    n.add_note(0.0, 0.5, 60.2, confidence=0.9)     fractional pitch -> pitch + cents
    n = Notes.from_table(df, bpm=90)               columns start, end|dur, pitch[, ...]
    n.intonation()                                 mean deviation in cents per note
    n.clean(min_dur=0.06, min_confidence=0.5)      drop spurious detections
"""
import math

import numpy as np
import pandas as pd
import pretty_midi

from .midi import Midi, TRUMPET_PROGRAM

COLUMNS = ["track", "start", "end", "dur", "pitch", "name", "written", "cents", "velocity",
           "confidence"]
from .theory import BRASS_NAMES as _NAMES   # names live in the theory engine
_KEY_DIGITS = 4               # rounding of start times used to match notes after edits


def note_name(p):
    """MIDI number -> name with the spelling usual for brass (Bb, Eb, Ab, C#, F#)."""
    from .theory import note_name as _name
    return _name(p)


def written_shift(program):
    """Semitones to add to the concert pitch to get the written pitch (Bb trumpet: +2)."""
    from music21 import instrument
    try:
        t = instrument.instrumentFromMidiProgram(program).transposition
    except Exception:
        return 0
    return -int(t.semitones) if t is not None else 0


def _split_pitch(p):
    """Fractional MIDI pitch -> (integer pitch, cents)."""
    q = int(round(p))
    return q, round(100.0 * (p - q), 1)


class Notes(Midi):
    def __init__(self, path=None, bpm=120, name="Recording", program=TRUMPET_PROGRAM):
        self._df = pd.DataFrame(columns=COLUMNS)
        self.track_names = [name]
        self.program = program
        super().__init__(path)
        if path is None:
            self.pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)

    # ------------------------------------------------------------ build
    @classmethod
    def from_table(cls, df, bpm=120, name="Recording", program=TRUMPET_PROGRAM):
        """New Notes from a table (DataFrame or list of dicts) with columns
        start, end (or dur) in seconds, pitch (may be fractional: the
        fraction becomes cents); optional cents, velocity, confidence, track."""
        df = pd.DataFrame(df).copy()
        if "end" not in df:
            df["end"] = df["start"] + df["dur"]
        n = cls(bpm=bpm, name=name, program=program)
        for r in df.to_dict("records"):
            n._add(r["start"], r["end"], r["pitch"], r.get("velocity", 80),
                   r.get("cents"), r.get("confidence"), int(r.get("track", 0) or 0))
        n._rebuild_pm()
        return n

    @classmethod
    def from_midi(cls, midi):
        """Notes from a Midi object (no extra data: cents 0, confidence NaN)."""
        import copy
        n = cls(bpm=midi.tempo() or 120)
        n.pm = copy.deepcopy(midi.pm)
        n.source = midi.source
        n._sync_from_pm()
        return n

    def add_note(self, start, end, pitch, velocity=80, cents=None, confidence=None, track=0):
        """Add one note (seconds). A fractional pitch is split into pitch + cents."""
        self._add(start, end, pitch, velocity, cents, confidence, track)
        self._rebuild_pm()
        return self

    def _add(self, start, end, pitch, velocity, cents, confidence, track):
        if end <= start:
            raise ValueError(f"note end {end} <= start {start}")
        q, c = _split_pitch(float(pitch))
        if cents is not None and not (isinstance(cents, float) and math.isnan(cents)):
            c = float(cents)
        while track >= len(self.track_names):
            self.track_names.append(f"Track {len(self.track_names) + 1}")
        start = max(0.0, float(start))
        row = dict(track=track, start=start, end=float(end), dur=float(end) - start,
                   pitch=q, name=note_name(q), written=note_name(q + written_shift(self.program)),
                   cents=c,
                   velocity=int(velocity) if velocity is not None else 80,
                   confidence=np.nan if confidence is None else float(confidence))
        self._df = pd.concat([self._df if len(self._df) else None, pd.DataFrame([row])],
                             ignore_index=True)

    # ------------------------------------------------------------ table <-> pretty_midi
    def _rebuild_pm(self):
        """pretty_midi content from the table (tempo/key/time signatures kept)."""
        df = self._df.sort_values(["track", "start", "pitch"]).reset_index(drop=True)
        self._df = df
        self.pm.instruments = []
        for t, name in enumerate(self.track_names):
            ins = pretty_midi.Instrument(program=self.program, name=name)
            for r in df[df.track == t].itertuples():
                ins.notes.append(pretty_midi.Note(int(r.velocity), int(r.pitch), r.start, r.end))
            if ins.notes:
                self.pm.instruments.append(ins)

    def _sync_from_pm(self):
        """Table from pretty_midi (after read/merge/...), keeping the extra
        data of the notes that were already there."""
        old = {}
        for r in self._df.itertuples():
            old[(int(r.pitch), round(r.start, _KEY_DIGITS))] = (r.cents, r.confidence)
        rows, names = [], []
        for t, ins in enumerate(self.pm.instruments):
            names.append(ins.name or f"Track {t + 1}")
            for nt in ins.notes:
                c, conf = old.get((nt.pitch, round(nt.start, _KEY_DIGITS)), (0.0, np.nan))
                rows.append(dict(track=t, start=nt.start, end=nt.end, dur=nt.end - nt.start,
                                 pitch=nt.pitch, name=note_name(nt.pitch),
                                 written=note_name(nt.pitch + written_shift(ins.program)),
                                 cents=c, velocity=nt.velocity, confidence=conf))
        self.track_names = names or self.track_names
        if self.pm.instruments:
            self.program = self.pm.instruments[0].program
        self._df = pd.DataFrame(rows, columns=COLUMNS).sort_values(
            ["track", "start", "pitch"]).reset_index(drop=True)

    # Midi methods that replace or extend the content: keep the table in step
    def read(self, path):
        super().read(path)
        self._sync_from_pm()
        return self

    def merge(self, *others):
        super().merge(*others)
        self._sync_from_pm()
        return self

    def makeduet(self, *args, **kw):
        super().makeduet(*args, **kw)
        self._sync_from_pm()
        return self

    # ------------------------------------------------------------ analysis
    def table(self):
        """Per-note data (a copy)."""
        return self._df.copy()

    def intonation(self, by="written"):
        """Deviation from the tempered pitch, in cents (+ = sharp), grouped by
        written note (by='written', default), concert note (by='name'),
        pitch class (by='class') or overall (by=None)."""
        df = self._df
        if not len(df):
            return pd.DataFrame(columns=["count", "mean", "std", "min", "max"])
        if by is None:
            return df["cents"].astype(float).describe()[["count", "mean", "std", "min", "max"]]
        if by in ("written", "name"):
            key = df[by]
        else:
            key = df["name"].str.replace(r"-?\d+$", "", regex=True)
        g = df.assign(key=key, cents=df["cents"].astype(float)).groupby("key")["cents"]
        out = g.agg(["count", "mean", "std", "min", "max"]).round(1)
        order = df.assign(key=key).groupby("key")["pitch"].min().sort_values().index
        return out.loc[order]

    def clean(self, min_dur=None, min_confidence=None):
        """Drop notes shorter than min_dur seconds or below min_confidence (in place)."""
        df = self._df
        keep = pd.Series(True, index=df.index)
        if min_dur is not None:
            keep &= df["dur"] >= min_dur
        if min_confidence is not None:
            keep &= df["confidence"].isna() | (df["confidence"] >= min_confidence)
        n = int((~keep).sum())
        self._df = df[keep].reset_index(drop=True)
        self._rebuild_pm()
        print(f"{n} notes removed, {len(self._df)} left")
        return self

    def __repr__(self):
        if not len(self._df):
            return "Notes(empty)"
        c = self._df["cents"].astype(float)
        return (f"Notes({len(self._df)} notes, {self.duration():.1f} s, tempo {self.tempo():g}, "
                f"intonation {c.mean():+.0f} ± {c.std() if len(c) > 1 else 0:.0f} cents)")
