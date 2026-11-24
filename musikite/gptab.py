"""
GUITAR PRO (.gp3, also .gp4 / .gp5) -> MIDI (owner, 2026-11-19): the twin of `powertab.py`
with the same rules. The files are read with the library PyGuitarPro (`pip install
pyguitarpro`, LGPL-3.0; `import guitarpro`), the MIDI is written by
`powertab.midi_file_of_timeline`, so the output is made exactly as for the Power Tab files:
one track per guitar (name, GM program, volume), resolution 960 ticks per quarter, ONLY THE
FIRST time signature (owner's rule), tempo changes kept, `monophonic=True` = one track with
the highest note at every moment (`powertab.skyline`), `program=` = the GM program of every
track (56 = trumpet). No Qt, no music21.

What is read: the tracks (percussion tracks are left out), their strings, capo (the track
"offset") and channel (program, volume); every beat of every voice; the initial tempo and
the tempo changes of the mix tables. Pitch = string + capo + fret. A TIED note lengthens the
previous note on the same string (one MIDI note); dead notes are not written. Repeats and
alternate endings are PLAYED OUT (`order`); the directions of Guitar Pro 5 (D.C., D.S.,
Coda) are NOT followed (Guitar Pro 3 has none).

    from musikite import gptab
    gptab.convert("song.gp3", "song.mid")
    m = gptab.to_midi("song.gp3")              # musikite Midi object
"""
import io

from . import powertab

QUARTER = powertab.QUARTER          # = PyGuitarPro's Duration.quarterTime (960)
TRUMPET_PROGRAM = powertab.TRUMPET_PROGRAM
EXTENSIONS = (".gp3", ".gp4", ".gp5")


def read(path):
    """PyGuitarPro Song of a Guitar Pro file."""
    try:
        import guitarpro
    except ImportError as e:
        raise ImportError("PyGuitarPro is needed for Guitar Pro files: "
                          "pip install pyguitarpro") from e
    return guitarpro.parse(path)


def order(headers):
    """Indices of the measures in the order they are played: repeats and alternate endings
    (bitmask of the endings, as PyGuitarPro gives them) played out; repeatClose = how many
    times to go back."""
    out, i, start, rep, back, guard = [], 0, 0, 0, False, 0
    n = len(headers)
    while i < n and guard < 100000:
        guard += 1
        h = headers[i]
        if h.isRepeatOpen and not back:
            start, rep = i, 0
        back = False
        alt = h.repeatAlternative or 0
        if alt > 0 and not (alt >> rep) & 1:
            i += 1                                   # ending of another pass
            continue
        out.append(i)
        close = h.repeatClose if h.repeatClose is not None else -1
        if close > 0:
            if rep < close:
                rep += 1
                i, back = start, True
                continue
            start, rep = i + 1, 0                   # the repeat is over
        i += 1
    return out


def _tempo_of(beat):
    mix = getattr(getattr(beat, "effect", None), "mixTableChange", None)
    t = getattr(mix, "tempo", None) if mix is not None else None
    v = getattr(t, "value", None) if t is not None else None
    return v if isinstance(v, (int, float)) and v > 0 else None


def timeline(song):
    """Same format as `powertab.timeline`: dict(tracks=[dict(name, program, volume,
    notes=[[start, end, pitch, velocity]])], tempos, meters, title)."""
    import guitarpro
    headers = song.measureHeaders
    if not headers:
        return dict(tracks=[], tempos=[(0, 120)], meters=[(0, 4, 4)],
                    title=song.title or "")
    played = order(headers)
    starts, t = [], 0                       # output start of every played measure
    for i in played:
        starts.append(t)
        t += headers[i].length
    tempos = [(0, song.tempo or 120)]
    ts = headers[0].timeSignature
    meters = [(0, ts.numerator, ts.denominator.value)]
    tracks = []
    tempo_track = None
    for track in song.tracks:
        if track.isPercussionTrack:
            continue
        strings = {s.number: s.value for s in track.strings}
        capo = track.offset or 0
        notes, last = [], {}
        for k, i in enumerate(played):
            if i >= len(track.measures):
                continue
            m = track.measures[i]
            h0 = headers[i].start
            for v in m.voices:
                for b in v.beats:
                    t0 = starts[k] + b.start - h0
                    if tempo_track in (None, track.number):
                        bpm = _tempo_of(b)
                        if bpm is not None:
                            tempo_track = track.number
                            tempos.append((t0, bpm))
                    if b.status == guitarpro.BeatStatus.rest or not b.notes:
                        continue
                    dur = b.duration.time
                    for n in b.notes:
                        if n.type == guitarpro.NoteType.dead or n.string not in strings:
                            continue
                        if n.type == guitarpro.NoteType.rest:
                            continue
                        pitch = strings[n.string] + capo + n.value
                        prev = last.get(n.string)
                        if n.type == guitarpro.NoteType.tie and prev is not None:
                            prev[1] = t0 + dur
                            continue
                        note = [t0, t0 + dur, pitch, 96]
                        notes.append(note)
                        last[n.string] = note
        if notes:
            notes.sort(key=lambda x: (x[0], x[2]))
            ch = track.channel
            tracks.append(dict(name=track.name or f"Guitar {track.number}",
                               program=ch.instrument, volume=ch.volume, notes=notes))
    tempos.sort(key=lambda x: x[0])
    return dict(tracks=tracks, tempos=tempos, meters=meters, title=song.title or "")


def to_midi_file(path_or_song, monophonic=False, program=None):
    """mido.MidiFile (type 1) of a Guitar Pro file (path) or of a PyGuitarPro Song."""
    song = read(path_or_song) if isinstance(path_or_song, str) else path_or_song
    return powertab.midi_file_of_timeline(timeline(song), monophonic, program)


def convert(src, dst, monophonic=False, program=None):
    """Write the MIDI file of a Guitar Pro file; returns the number of tracks with notes."""
    mf = to_midi_file(src, monophonic, program)
    mf.save(dst)
    return len(mf.tracks) - 1


def to_midi(path, monophonic=False, program=None):
    """musikite Midi object of a Guitar Pro file."""
    import pretty_midi
    from .midi import Midi
    buf = io.BytesIO()
    to_midi_file(path, monophonic, program).save(file=buf)
    buf.seek(0)
    m = Midi()
    m.pm = pretty_midi.PrettyMIDI(buf)
    m.source = path
    return m
