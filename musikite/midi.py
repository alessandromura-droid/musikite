"""
Midi object.

All pitches are CONCERT (sounding) pitch, as in any standard MIDI file:
a Bb trumpet part is stored one tone below the written note.

    m = Midi()                    empty
    m = Midi('file.mid')          read from file
    m = Midi.from_pdf('a.pdf')    read from a vector PDF (scoreread engine)
    m.merge(other, 'b.mid')       add the tracks of other MIDI objects/files
    m.makeduet(...)               replace the content with a duet for two trumpets
    m.duet_from_melody('harmony') a NEW duet: this MIDI's melody + a second voice (accompany)
    m.add_sf2('font.sf2')         soundfont used to play/render
    m.play(); m.stop()            real time with FluidSynth (Jupyter: non-blocking)
    m.render('x.wav')             export to WAV
    m.write('out.mid')
    m.to_score()                  Score object (notation), trumpet at written pitch
    m.quantize('1/8+1/8T', 0.8)   notes onto a grid (in place)
    m.roll(); m.pianoroll()       piano roll model (pianoroll.Roll) / edit window
    m.to_pdf('out.pdf')           engraved score (Verovio), trumpet at written pitch
"""
import copy
import os
import sys
import tempfile

import pretty_midi

from . import duet as _duet

TRUMPET_PROGRAM = 56          # General MIDI "Trumpet" (0-based)
BB_TRUMPET = -2               # sound = written - 2 semitones


def _in_notebook():
    try:
        return get_ipython().__class__.__name__ == "ZMQInteractiveShell"  # noqa: F821
    except NameError:
        return False


class Midi:
    _default_sf2 = None       # last soundfont given with add_sf2()

    def __init__(self, path=None):
        self.pm = pretty_midi.PrettyMIDI()
        self.source = None
        self.sf2 = Midi._default_sf2
        self.duet_info = None
        if path is not None:
            self.read(path)

    # ------------------------------------------------------------ I/O
    def read(self, path):
        """Replace the content with a MIDI file."""
        path = os.path.expanduser(path)
        self.pm = pretty_midi.PrettyMIDI(path)
        self.source = os.path.abspath(path)
        return self

    @classmethod
    def from_pdf(cls, pdf, instrument=None, force=False):
        """New Midi object from a vector PDF (path or Pdf object)."""
        from .pdf import Pdf
        if not isinstance(pdf, Pdf):
            pdf = Pdf(pdf)
        return pdf.to_midi(instrument=instrument, force=force)

    def write(self, path):
        path = os.path.expanduser(path)
        self.pm.write(path)
        print(f"written {path}")
        return self

    def to_score(self, title=None, written=True):
        """Score object (notation: bars, note values, key); transposing
        instruments at written pitch unless written=False."""
        from .score import Score
        return Score.from_midi(self, title=title, written=written)

    def to_pdf(self, path, title=None, scale=50):
        """Engrave the score to a PDF with Verovio (transposing instruments,
        e.g. Bb trumpet, at written pitch). title: default the file name."""
        if title is None:
            title = os.path.splitext(os.path.basename(self.source or path))[0]
        self.to_score(title).to_pdf(path, scale=scale)
        return self

    # ------------------------------------------------------------ editing
    def tempo_map(self):
        """[(quarter, bpm)] of every tempo of the file (position in quarters, so files with
        another resolution compare equal)."""
        ts, bpms = self.pm.get_tempo_changes()
        res = float(self.pm.resolution)
        return [(round(self.pm.time_to_tick(t) / res, 3), round(float(b), 2))
                for t, b in zip(ts, bpms)]

    def merge(self, *others, strict=False):
        """Add the tracks of other Midi objects or MIDI files to this one.
        The TEMPO MAP (every tempo change), time and key signatures of the first file are
        kept; notes are stored in seconds, so every track keeps its own timing.
        Files whose tempo map differs: strict=True -> ValueError (owner, 2026-11-08: the
        old fondi_midi.py made a new MIDI at 120 and the mix of parts at 100 was written
        stretched); otherwise a warning."""
        for o in others:
            name = o if isinstance(o, str) else getattr(o, "source", None) or "a MIDI"
            if not isinstance(o, Midi):
                o = Midi(o)
            if self.is_empty() and not self.pm.instruments:
                self.pm = copy.deepcopy(o.pm)
                self._first_name = name
                continue
            a, b = self.tempo_map(), o.tempo_map()
            if a != b:
                msg = (f"tempo of {os.path.basename(str(name))} {_tempo_text(b)} differs from "
                       f"{os.path.basename(str(getattr(self, '_first_name', 'the first file')))} "
                       f"{_tempo_text(a)}")
                if strict:
                    raise ValueError(msg)
                print(f"warning: {msg} (timing kept, notation tempo of the first file)")
            self.pm.instruments.extend(copy.deepcopy(o.pm.instruments))
        return self

    def quantize(self, grid="1/16", strength=1.0, ends=False):
        """Move the notes onto a grid, in place (pianoroll.Roll.quantize): grid '1/4',
        '1/8', '1/16', '1/32', triplets '1/8T', '1/16T', mixed '1/8+1/8T', '1/16+1/16T';
        strength 0..1; ends=True quantizes the note ends too."""
        from .pianoroll import quantize_midi
        n = quantize_midi(self, grid, strength, ends)
        print(f"quantized {grid} {strength * 100:g} %: {n} notes moved")
        return self

    def roll(self):
        """Piano roll model of this MIDI (pianoroll.Roll: edit, undo, quantize, then
        roll.apply_to(m))."""
        from .pianoroll import Roll
        return Roll.from_midi(self)

    def pianoroll(self, title=None):
        """Piano roll window (Qt) editing this object in place; returns the view."""
        from .pianorollview import PianoRollView
        return PianoRollView(self, title=title).show()

    def makeduet(self, chords=_duet.DEFAULT_CHORDS, rounds=2, level=1, key=None,
                 concert=False, seed=None, bpm=120, phrase=4, textures=None, repetition=0.7):
        """Replace the content with a random duet for two Bb trumpets
        (engine derived from duetti.py, same options plus repetition).

        chords   : progression, one chord per bar, 'F:G' = two chords in a bar
        rounds   : times the progression is repeated
        level    : complexity 1-3
        key      : e.g. 'C' or 'Am' (default: first chord)
        concert  : chords/key given in concert pitch (default: written trumpet pitch)
        seed     : random seed (same seed = same duet)
        bpm      : tempo
        phrase   : bars per phrase, the last one is the cadence
        textures : list or comma-separated string, e.g. 'thirds,canon_bar'
        repetition: 0..1, how much the motif is restated and developed
                   (0 = mostly free lines, 1 = strongly motivic; default 0.7)
        """
        if not self.is_empty():
            print("warning: previous content replaced by the duet")
        d = _duet.generate_duet(chords, rounds, level, key, concert, seed, phrase, textures,
                                repetition)
        pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        spq = 60.0 / bpm
        pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0.0))
        kc = (d["kpc"] + BB_TRUMPET) % 12
        pm.key_signature_changes.append(pretty_midi.KeySignature(kc + (12 if d["minor"] else 0), 0.0))
        for name, line in (("Trumpet in Bb 1", d["t1"]), ("Trumpet in Bb 2", d["t2"])):
            ins = pretty_midi.Instrument(program=TRUMPET_PROGRAM, name=name)
            for s, du, p in line:
                if p is not None:
                    ins.notes.append(pretty_midi.Note(80, p + BB_TRUMPET, s * spq, (s + du) * spq))
            pm.instruments.append(ins)
        self.pm = pm
        self.source = None
        self.duet_info = dict(seed=d["seed"], level=level, bars=d["nbars"], textures=d["log"],
                              chords=chords, rounds=rounds, repetition=repetition)
        print(f"duet: level {level}  seed {d['seed']}  {d['nbars']} bars:  "
              f"{' | '.join(d['log'])}   (* = trumpet 2 on top)")
        return self

    def makecanon(self, chords="C F G C", difficulty=2, beats_per_chord=4, cycles=4, key=None,
                  concert=False, seed=None, bpm=80):
        """Replace the content with a canon for two Bb trumpets (canon.py, port of
        canon_trumpets.py): trumpet 2 plays what trumpet 1 played one progression
        earlier. concert=False: chords / key in WRITTEN trumpet pitch (as makeduet)."""
        from . import canon as _canon
        if not self.is_empty():
            print("warning: previous content replaced by the canon")
        d = _canon.generate_canon(chords, difficulty, beats_per_chord, cycles, key, concert, seed)
        pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        spq = 60.0 / bpm
        pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0.0))
        kc = (d["kpc"] + BB_TRUMPET) % 12
        pm.key_signature_changes.append(pretty_midi.KeySignature(kc + (12 if d["minor"] else 0), 0.0))
        for name, line in (("Trumpet in Bb 1", d["t1"]), ("Trumpet in Bb 2", d["t2"])):
            ins = pretty_midi.Instrument(program=TRUMPET_PROGRAM, name=name)
            for s, du, p in line:
                ins.notes.append(pretty_midi.Note(80, p + BB_TRUMPET, s * spq, (s + du) * spq))
            pm.instruments.append(ins)
        self.pm = pm
        self.source = None
        self.duet_info = dict(seed=d["seed"], level=int(difficulty), bars=d["bars"],
                              chords=chords, canon=True, cycles=cycles)
        print(f"canon: difficulty {difficulty}  seed {d['seed']}  {d['bars']} bars")
        return self

    def makeensemble(self, voices="trio", chords=_duet.DEFAULT_CHORDS, rounds=2, level=1,
                     key=None, concert=False, seed=None, bpm=120, phrase=4, textures=None,
                     repetition=0.7):
        """Replace the content with a BRASS TRIO (2 trumpets, trombone) or QUARTET (2
        trumpets, horn, trombone) (ensemble.py, owner 2026-11-24): the trumpets are the duet
        of makeduet with the same options and seed, horn and trombone follow the chords."""
        from . import ensemble as _ens
        if not self.is_empty():
            print("warning: previous content replaced by the ensemble")
        d = _ens.generate_ensemble(voices, chords, rounds, level, key, concert, seed, phrase,
                                   textures, repetition)
        pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        spq = 60.0 / bpm
        pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0.0))
        kc = (d["kpc"] + BB_TRUMPET) % 12
        pm.key_signature_changes.append(pretty_midi.KeySignature(kc + (12 if d["minor"] else 0), 0.0))
        for name, prog, line in d["parts"]:
            ins = pretty_midi.Instrument(program=prog, name=name)
            for s, du, p in line:
                if p is not None and du > 0:
                    ins.notes.append(pretty_midi.Note(80, int(p), s * spq, (s + du) * spq))
            pm.instruments.append(ins)
        self.pm = pm
        self.source = None
        self.duet_info = dict(seed=d["seed"], level=level, bars=d["nbars"], textures=d["log"],
                              chords=chords, rounds=rounds, repetition=repetition,
                              ensemble=voices)
        print(f"{voices}: level {level}  seed {d['seed']}  {d['nbars']} bars")
        return self

    def makebacking(self, chords="Dm7 G7 Cmaj7 Cmaj7", style="swing", bpm=None, choruses=3,
                    sound="piano", key=None, seed=None, count_in=True, ending=True):
        """Replace the content with a BACKING TRACK (backing.py, owner 2026-11-18): bass,
        chords and drums on CONCERT chords, style swing / bossa nova / ballad / jazz pop."""
        from . import backing as _backing
        if not self.is_empty():
            print("warning: previous content replaced by the backing track")
        pm, info = _backing.make_backing(chords, style=style, bpm=bpm, choruses=choruses,
                                         sound=sound, key=key, seed=seed, count_in=count_in,
                                         ending=ending)
        self.pm = pm
        self.source = None
        self.duet_info = info                  # kept in the workspace (info['backing'])
        print(f"backing track: {style}, {info['bars']} bars, seed {info['seed']}")
        return self

    def duet_from_melody(self, mode="accompaniment", **kw):
        """A NEW Midi (this one is not changed): the melody of this MIDI (the track with the
        most notes, or track=) and a second voice made for it (accompany.py, owner
        2026-11-20): mode 'harmony' (thirds / sixths in the key, chord tones where the
        harmony asks), 'canon' (the melody delayed) or 'accompaniment' (the chords found,
        played as long notes, half notes, beats or arpeggios). Options: see
        accompany.duet_from_melody."""
        from .accompany import duet_from_melody
        return duet_from_melody(self, mode=mode, **kw)

    # ------------------------------------------------------------ sound
    def add_sf2(self, path):
        """Soundfont (.sf2) used by play() and render(). It also becomes the
        default for Midi objects created afterwards."""
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        self.sf2 = path
        Midi._default_sf2 = path
        return self

    def render(self, wav=None, fs=44100):
        """Export to a WAV file (FluidSynth via pyfluidsynth, same soundfont as play());
        returns its path. Listening uses play(), in real time."""
        import wave
        import numpy as np
        if self.sf2 is None:
            raise RuntimeError("no soundfont: use add_sf2(path) first")
        if self.is_empty():
            raise RuntimeError("empty MIDI: nothing to render")
        y = self.pm.fluidsynth(fs=fs, sf2_path=self.sf2)
        y = y / max(1e-9, float(np.abs(y).max())) * 0.9
        if wav is None:
            fd, wav = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        wav = os.path.expanduser(wav)
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(fs)
            w.writeframes((y * 32767).astype(np.int16).tobytes())
        return wav

    def player(self):
        """Real-time FluidSynth player for this object's soundfont."""
        from .realtime import get_player
        if self.sf2 is None:
            raise RuntimeError("no soundfont: use add_sf2(path) first")
        return get_player(self.sf2)

    def play(self, wait=None):
        """Play in real time with FluidSynth (no audio file). In Jupyter it returns
        at once (stop with .stop()); on the command line it waits for the end."""
        from .realtime import midi_events
        if self.is_empty():
            raise RuntimeError("empty MIDI: nothing to play")
        if wait is None:
            wait = not _in_notebook()
        self.player().play(midi_events(self.pm), wait=wait)
        return self

    def stop(self):
        if self.sf2 is not None:
            self.player().stop()
        return self

    # ------------------------------------------------------------ info
    def is_empty(self):
        return not any(i.notes for i in self.pm.instruments)

    def tempo(self):
        _, t = self.pm.get_tempo_changes()
        return float(t[0]) if len(t) else None

    def duration(self):
        return self.pm.get_end_time()

    def __repr__(self):
        if self.is_empty():
            return "Midi(empty)"
        tr = ", ".join(f"{i.name or pretty_midi.program_to_instrument_name(i.program)}"
                       f" [{len(i.notes)}]" for i in self.pm.instruments)
        return f"Midi({len(self.pm.instruments)} tracks, {self.duration():.1f} s, tempo {self.tempo():g}: {tr})"


# ---------------------------------------------------------------- shortcuts
def makeduet(m=None, **kw):
    """makeduet(pippo, level=2) == pippo.makeduet(level=2); returns the object."""
    return (m if m is not None else Midi()).makeduet(**kw)


def midiplay(m):
    return m.play()


def transposed(m, semitones):
    """New Midi object k semitones up (down if negative); drums and key signatures follow
    (drums stay as they are)."""
    out = Midi()
    out.pm = copy.deepcopy(m.pm)
    k = int(semitones)
    for ins in out.pm.instruments:
        if ins.is_drum:
            continue
        for n in ins.notes:
            n.pitch = max(0, min(127, n.pitch + k))
    for ks in out.pm.key_signature_changes:
        ks.key_number = (ks.key_number // 12) * 12 + (ks.key_number % 12 + k) % 12
    out.source = None
    return out


def merge(*items, strict=False):
    """New Midi object with the tracks of all the given Midi objects/files (tempo map of the
    first; strict=True: an error if the files' tempo maps differ)."""
    return Midi().merge(*items, strict=strict)


def _tempo_text(tmap):
    return ", ".join(f"{b:g} at quarter {q:g}" if q else f"{b:g}" for q, b in tmap)
