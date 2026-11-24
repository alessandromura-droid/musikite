"""
Score object: the music as notation (bars, beats, note values, key, time
signature), the Python counterpart of the MATLAB `notes` object
(mysmartmusic_obj/notes.m: `tab` + `Info`).

Built on a music21 Score (kept in .m21). By default it is at WRITTEN pitch:
transposing instruments (e.g. Bb trumpet) are a tone above the Midi object.

    s = Score.from_midi(m)        or  m.to_score()
    s.table()                     one row per note/rest (pandas DataFrame)
    s.key(), s.time_signature(), s.tempo(), s.parts()
    s.transpose(2)
    s.show()                      engraved score inline in Jupyter
    s.view()                      StaffView window: cursor, play-along, coloured notes
    s.to_pdf('x.pdf')
    s.to_midi()                   back to a Midi object (concert pitch)

Columns of table() and the corresponding MATLAB tab columns:
    part, measure, beat (in the bar, from 1), start (beats, tab col 9),
    dur (beats, col 10), pitch (MIDI, col 3; <NA> = rest), name,
    velocity (col 4), tie, bpm (col 11)
"""
import os
import tempfile
import warnings

STEP_DIVISORS = (4, 3)        # quantization grid: sixteenths and eighth triplets


from . import theory as _th


def _part_notes(p):
    """[offset, duration, midi] of every note of a music21 part (chords: every note)."""
    out = []
    for n in p.flatten().notes:
        for pt in getattr(n, "pitches", ()):
            out.append([float(n.offset), float(n.quarterLength), int(pt.midi)])
    return out


def respell(m21):
    """NAMES OF THE NOTES FOLLOW THE KEY SIGNATURE (owner, 2026-11-20: from a MIDI every
    pitch got a fixed name — A# written Bb in F# major): every pitched note of every part
    is spelled for the key signature in force where it is (`theory.spell_pitch`, on the
    pitch AS WRITTEN on that staff, so a transposing part is spelled for its written key),
    then the accidentals shown are made again. Key signatures beyond 7 sharps / flats
    (e.g. after a transposition) become their enharmonic key (10 sharps -> 2 flats). The
    MIDI pitches never change (rows of table() and the StaffView matching are by pitch).
    Percussion parts are left alone. Works in place; returns the stream."""
    from music21 import key as m21key, pitch as m21pitch, instrument
    for p in m21.parts:
        inst = p.recurse().getElementsByClass(instrument.Instrument).first()
        if isinstance(inst, (instrument.Percussion, instrument.UnpitchedPercussion)):
            continue
        for ks in list(p.recurse().getElementsByClass(m21key.KeySignature)):
            k = int(ks.sharps)
            if -7 <= k <= 7:
                continue
            k = k - 12 if k > 7 else k + 12
            new = m21key.KeySignature(k)
            if isinstance(ks, m21key.Key):
                new = new.asKey(ks.mode if ks.mode in ("major", "minor") else "major")
            site = ks.activeSite
            if site is not None:
                site.replace(ks, new)
        flat = p.flatten()
        kss = sorted(((float(flat.elementOffset(k)), k) for k in
                      flat.getElementsByClass(m21key.KeySignature)), key=lambda x: x[0])
        changed = False
        for n in flat.notes:
            off = float(flat.elementOffset(n)) + 1e-6
            ks = None
            for o, k in kss:
                if o <= off:
                    ks = k
                else:
                    break
            sharps = int(ks.sharps) if ks is not None else 0
            mode = ks.mode if isinstance(ks, m21key.Key) else None
            for pt in getattr(n, "pitches", ()):
                try:
                    midi = int(round(pt.ps))
                    if abs(pt.ps - midi) > 1e-6:
                        continue                          # microtones: as they are
                    L, a, o = _th.spell_pitch(midi, sharps, mode)
                    if pt.step == L and int(pt.alter) == a and pt.octave == o:
                        continue
                    old = (pt.step, pt.accidental, pt.octave)
                    pt.step = L
                    pt.accidental = m21pitch.Accidental(a) if a else None
                    pt.octave = o
                    if int(round(pt.ps)) != midi:          # never a different pitch
                        pt.step, pt.accidental, pt.octave = old
                    else:
                        changed = True
                except Exception:
                    continue
        if changed or kss:
            try:
                p.makeAccidentals(inPlace=True, overrideStatus=True)
            except Exception:
                pass
    return m21


class Score:
    def __init__(self, m21=None, title="", written=True):
        self.m21 = m21
        self.title = title
        self.written = written
        self.source = None

    # ------------------------------------------------------------ build
    @classmethod
    def from_midi(cls, midi, title=None, written=True, divisors=STEP_DIVISORS):
        """Score from a Midi object (or a MIDI file path).

        written  : True = transposing instruments at written pitch (default)
        divisors : quantization grid in divisions of the quarter note
        """
        import music21
        from music21 import instrument, metadata, key as m21key
        from .midi import Midi
        if not isinstance(midi, Midi):
            midi = Midi(midi)
        if midi.is_empty():
            raise RuntimeError("empty MIDI: no score")
        pm = midi.pm
        fd, tmp = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        try:
            pm.write(tmp)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                s = music21.converter.parse(tmp, quantizePost=True,
                                            quarterLengthDivisors=divisors)
        finally:
            os.remove(tmp)
        tracks = [i for i in pm.instruments if i.notes]
        if len(tracks) == len(s.parts):
            for p, t in zip(s.parts, tracks):
                new = instrument.Percussion() if t.is_drum else instrument.instrumentFromMidiProgram(t.program)
                name = t.name or new.instrumentName or ""
                for old in list(p.recurse().getElementsByClass(instrument.Instrument)):
                    p.remove(old, recurse=True)
                new.partName = name
                new.partAbbreviation = name           # full name in every system
                new.instrumentAbbreviation = name
                p.insert(0, new)
                p.partName = name
                p.partAbbreviation = name
        s.atSoundingPitch = True
        if written:
            s.toWrittenPitch(inPlace=True)
        if not pm.key_signature_changes:       # e.g. MIDI from a PDF: estimate the key per part
            for p in s.parts:
                if p.recurse().getElementsByClass(m21key.KeySignature) or not p.recurse().notes:
                    continue
                # theory engine (port of the owner's tonalita.m; no music21 analysis)
                ks = m21key.KeySignature(_th.key_signature(*_th.key_of_notes(_part_notes(p))))
                first = p.getElementsByClass("Measure").first()
                (first or p).insert(0, ks)
                p.makeAccidentals(inPlace=True, overrideStatus=True)
        respell(s)                             # note names by the key signature (2026-11-20)
        if title is None:
            title = os.path.splitext(os.path.basename(midi.source))[0] if midi.source else ""
        s.metadata = metadata.Metadata()
        s.metadata.title = title
        s.metadata.movementName = title             # Verovio prints the movement title
        out = cls(s, title, written)
        out.source = midi.source
        return out

    # ------------------------------------------------------------ info
    def parts(self):
        return [p.partName or f"part {i + 1}" for i, p in enumerate(self.m21.parts)]

    def key(self, part=0):
        """Key signature of a part, e.g. 'Bb major (-2)'; estimated if none is written."""
        from music21 import key as m21key
        p = self.m21.parts[part]
        ks = p.recurse().getElementsByClass(m21key.KeySignature).first()
        if ks is None:                         # estimated by the theory engine (tonalita.m)
            notes = _part_notes(p)
            if not notes:
                return "C major (+0)"
            tonic, mode = _th.key_of_notes(notes)
            name = _th.note_name(tonic + 60, octave=False)
            return (f"{name} {'minor' if mode == 'aeolian' else 'major'} "
                    f"({_th.key_signature(tonic, mode):+d})")
        k = ks if isinstance(ks, m21key.Key) else ks.asKey()
        return f"{k.tonic.name.replace('-', 'b')} {k.mode} ({k.sharps:+d})"

    def time_signature(self):
        ts = self.m21.recurse().getElementsByClass("TimeSignature").first()
        return ts.ratioString if ts is not None else "4/4"

    def tempo(self):
        mm = self.m21.recurse().getElementsByClass("MetronomeMark").first()
        return float(mm.number) if mm is not None and mm.number else None

    def measures(self):
        return max((len(p.getElementsByClass("Measure")) for p in self.m21.parts), default=0)

    def table(self, part=None):
        """One row per note (chords: one row per note) or rest, as a DataFrame."""
        import pandas as pd
        rows = []
        bpm = self.tempo()
        for ip, p in enumerate(self.m21.parts):
            if part is not None and ip != part:
                continue
            name = p.partName or f"part {ip + 1}"
            for n in p.recurse().notesAndRests:
                m = n.getContextByClass("Measure")
                start = float(n.getOffsetInHierarchy(p))
                common = dict(part=name, measure=m.number if m is not None else None,
                              beat=float(n.beat), start=start, dur=float(n.quarterLength))
                if n.isRest:
                    rows.append(dict(common, pitch=None, name="rest", velocity=None, tie=None, bpm=bpm))
                    continue
                for pt in n.pitches:
                    rows.append(dict(common, pitch=pt.midi, name=pt.nameWithOctave.replace("-", "b"),
                                     velocity=n.volume.velocity,
                                     tie=n.tie.type if n.tie is not None else None, bpm=bpm))
        df = pd.DataFrame(rows, columns=["part", "measure", "beat", "start", "dur", "pitch",
                                         "name", "velocity", "tie", "bpm"])
        df["pitch"] = df["pitch"].astype("Int64")
        df["velocity"] = df["velocity"].astype("Int64")
        return df

    def __repr__(self):
        if self.m21 is None:
            return "Score(empty)"
        pitch = "written" if self.written else "concert"
        return (f"Score('{self.title}', {len(self.m21.parts)} parts {self.parts()}, "
                f"{self.measures()} bars, {self.time_signature()}, key {self.key()}, "
                f"tempo {self.tempo()}, {pitch} pitch)")

    # ------------------------------------------------------------ editing
    def transpose(self, semitones):
        """Transpose all parts by a number of semitones (in place); the names of the notes
        follow the new key signature (respell)."""
        self.m21.transpose(semitones, inPlace=True)
        respell(self.m21)
        return self

    # ------------------------------------------------------------ output
    def to_midi(self):
        """Midi object at concert pitch."""
        import copy
        from .midi import Midi
        s = copy.deepcopy(self.m21)
        if self.written:
            s.toSoundingPitch(inPlace=True)
        fd, tmp = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        try:
            s.write("midi", fp=tmp)
            m = Midi(tmp)
        except Exception:
            # music21 sometimes writes a MIDI file that mido refuses ("running status
            # without last_status"): build it directly from the notes instead
            m = self._midi_direct(s)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        m.source = self.source
        return m

    def _midi_direct(self, s):
        """Midi built note by note from a (sounding-pitch) music21 score: one
        instrument per part, GM program of the part (default trumpet), tempo of the
        score (default 120), ties joined."""
        import pretty_midi
        from .midi import Midi
        bpm = self.tempo() or 120.0
        spq = 60.0 / bpm
        pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        for part in s.parts:
            inst = part.getInstrument(returnDefault=True)
            prog = inst.midiProgram if inst is not None and inst.midiProgram is not None else 56
            ins = pretty_midi.Instrument(program=int(prog), name=part.partName or "")
            for el in part.stripTies().flatten().notes:
                t0 = float(el.offset) * spq
                t1 = t0 + float(el.quarterLength) * spq
                vel = el.volume.velocity or 80
                for p in (el.pitches if el.isChord else [el.pitch]):
                    ins.notes.append(pretty_midi.Note(int(vel), int(p.midi), t0, max(t1, t0 + 0.01)))
            pm.instruments.append(ins)
        m = Midi()
        m.pm = pm
        return m

    def to_pdf(self, path, scale=50):
        from .engrave import score_to_pdf
        md = self.m21.metadata
        n = score_to_pdf(self.m21, path, scale=scale, title=(md.title if md else None))
        print(f"written {path} ({n} page{'s' if n != 1 else ''})")
        return self

    def view(self, layout="line", **kw):
        """StaffView window (Qt) on this score: cursor, play-along, marks."""
        from .staffview import StaffView
        return StaffView(self, layout=layout, **kw).show()

    def show(self, scale=35, width=2100):
        """Engraved score inline in Jupyter (all pages, one below the other)."""
        from IPython.display import SVG, display
        from .engrave import svg_pages
        for page in svg_pages(self.m21, scale=scale, page_width=width, page_height=60000, adjust=True):
            display(SVG(page))
