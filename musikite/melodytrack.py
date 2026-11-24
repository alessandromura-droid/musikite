"""
MELODY TRACK of a MIDI file (owner, 2026-11-19): finds the track that most looks like a
melody and writes a MIDI with that track only. Same rules as `powertab.py` / `gptab.py`:
tempo changes kept, ONLY THE FIRST time signature, `monophonic=True` = the highest note at
every moment (`powertab.skyline`), `program=` = the GM program of the track (56 = trumpet).
Pure Python (mido), no Qt, no music21.

CANDIDATES: every (track, channel) with notes, the drum channel 10 excluded (a type-0 file
has one track: its channels are the candidates). Those with fewer than MIN_NOTES notes are
used only if no candidate has that many.

SCORE (the highest wins; a tie: more notes), every term 0..1 unless said:
- MONOPHONY x 2.0: fraction of the notes that start when no other note of the candidate is
  sounding (a melody is one voice; chords and accompaniments are not);
- HEIGHT x 1.5: mean pitch, scaled between the lowest and the highest mean of the
  candidates (the melody is usually on top);
- STEPS x 1.0: fraction of the intervals between consecutive notes (of the top voice) of at
  most STEP semitones (melodies move mostly by steps and small leaps; arpeggios and bass
  lines jump);
- COVERAGE x 1.0: fraction of the piece during which the candidate sounds;
- REPETITION penalty x -1.0: fraction of consecutive notes on the same pitch beyond
  REPEAT_FREE (ostinatos, pedal notes);
- RANGE penalty -0.5 if the range is wider than WIDE semitones;
- NAME +1 if the track name says melody / lead / voice / vocal / solo / canto / melodia /
  voce / tema / theme; -1 if it says bass / basso / chord / accordi / pad / rhythm / ritmica /
  accomp / drum / strings / comp;
- PROGRAM -1 for basses (GM 32-39), pads and effects (88-103); +0.3 for brass, reeds and
  pipes (56-79).
The terms and weights are constants at the top (WEIGHTS) so they can be tuned.

    from musikite import melodytrack
    info = melodytrack.convert("song.mid", "song.melody.mid", monophonic=True)
    melodytrack.candidates("song.mid")       # the score of every candidate
"""
import io

import mido

MIN_NOTES = 16
STEP = 5                      # semitones: a step or a small leap
REPEAT_FREE = 0.3             # this fraction of repeated notes is normal
WIDE = 36                     # semitones
WEIGHTS = dict(monophony=2.0, height=1.5, steps=1.0, coverage=1.0, repetition=-1.0)
DRUM_CHANNEL = 9
TRUMPET_PROGRAM = 56
GOOD_NAMES = ("melody", "melodia", "lead", "voice", "vocal", "voce", "solo", "canto", "tema",
              "theme")
BAD_NAMES = ("bass", "basso", "chord", "accordi", "pad", "rhythm", "ritmica", "accomp",
             "drum", "strings", "comp")


def _notes(mf):
    """Candidates {(track, channel): dict(name, program, notes=[[start, end, pitch, vel]])},
    tempos [(tick, tempo µs)], first time signature (tick, num, den) or None, last tick."""
    cands, tempos, ts, last = {}, [], None, 0
    for ti, track in enumerate(mf.tracks):
        t, name, prog, on = 0, "", {}, {}
        for msg in track:
            t += msg.time
            if msg.type == "track_name":
                name = msg.name
            elif msg.type == "set_tempo":
                tempos.append((t, msg.tempo))
            elif msg.type == "time_signature":
                if ts is None or t < ts[0]:
                    ts = (t, msg.numerator, msg.denominator)
            elif msg.type == "program_change":
                prog[msg.channel] = msg.program
            elif msg.type in ("note_on", "note_off") and msg.channel != DRUM_CHANNEL:
                key = (msg.channel, msg.note)
                if msg.type == "note_on" and msg.velocity > 0:
                    on.setdefault(key, []).append((t, msg.velocity))
                elif on.get(key):
                    s, v = on[key].pop(0)
                    c = cands.setdefault((ti, msg.channel), dict(name=name, notes=[]))
                    c["notes"].append([s, t, msg.note, v])
        for (ch, p), lst in on.items():                         # notes never closed
            for s, v in lst:
                c = cands.setdefault((ti, ch), dict(name=name, notes=[]))
                c["notes"].append([s, max(t, s + 1), p, v])
        for (tk, ch), c in cands.items():
            if tk == ti:
                c["name"] = c["name"] or name
                c["program"] = prog.get(ch, c.get("program", 0))
        last = max(last, t)
    for c in cands.values():
        c["notes"].sort(key=lambda n: (n[0], -n[2]))
    return cands, sorted(tempos), ts, last


def _features(notes, length):
    starts_alone, end_max = 0, -1
    for s, e, p, v in notes:
        if s >= end_max:
            starts_alone += 1
        end_max = max(end_max, e)
    top = {}
    for s, e, p, v in notes:
        if s not in top or p > top[s]:
            top[s] = p
    seq = [top[s] for s in sorted(top)]
    iv = [abs(b - a) for a, b in zip(seq, seq[1:])]
    covered, cur_s, cur_e = 0, None, None                     # union of the note intervals
    for s, e, p, v in sorted(notes):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                covered += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        covered += cur_e - cur_s
    pitches = [n[2] for n in notes]
    same = sum(1 for x in iv if x == 0) / len(iv) if iv else 0.0
    return dict(monophony=starts_alone / len(notes),
                mean=sum(pitches) / len(pitches),
                steps=sum(1 for x in iv if 0 < x <= STEP) / max(1, sum(1 for x in iv if x)),
                coverage=min(1.0, covered / max(1, length)),
                repetition=max(0.0, same - REPEAT_FREE) / (1 - REPEAT_FREE),
                range=max(pitches) - min(pitches))


def candidates(path_or_midifile):
    """Every candidate with its features and score, best first:
    [dict(track, channel, name, program, notes, score, features)]."""
    mf = mido.MidiFile(path_or_midifile) if isinstance(path_or_midifile, str) \
        else path_or_midifile
    cands, _, _, last = _notes(mf)
    pool = {k: c for k, c in cands.items() if len(c["notes"]) >= MIN_NOTES} or \
        {k: c for k, c in cands.items() if c["notes"]}
    out = []
    for (tk, ch), c in pool.items():
        f = _features(c["notes"], last)
        out.append(dict(track=tk, channel=ch, name=c["name"], program=c["program"],
                        notes=c["notes"], features=f))
    if not out:
        return []
    means = [o["features"]["mean"] for o in out]
    lo, hi = min(means), max(means)
    for o in out:
        f = o["features"]
        f["height"] = (f["mean"] - lo) / (hi - lo) if hi > lo else 0.5
        sc = sum(w * f[k] for k, w in WEIGHTS.items())
        if f["range"] > WIDE:
            sc -= 0.5
        nm = (o["name"] or "").lower()
        if any(w in nm for w in GOOD_NAMES):
            sc += 1
        if any(w in nm for w in BAD_NAMES):
            sc -= 1
        p = o["program"]
        if 32 <= p <= 39 or 88 <= p <= 103:
            sc -= 1
        elif 56 <= p <= 79:
            sc += 0.3
        o["score"] = sc
    out.sort(key=lambda o: (-o["score"], -len(o["notes"])))
    return out


def to_midi_file(path_or_midifile, monophonic=False, program=None):
    """(mido.MidiFile type 1 with the conductor track + the melody track, the chosen
    candidate) or (None, None) if the file has no notes."""
    from .powertab import skyline, _delta
    mf = mido.MidiFile(path_or_midifile) if isinstance(path_or_midifile, str) \
        else path_or_midifile
    best = candidates(mf)
    if not best:
        return None, None
    best = best[0]
    _, tempos, ts, _ = _notes(mf)
    notes = skyline(best["notes"]) if monophonic else best["notes"]
    out = mido.MidiFile(type=1, ticks_per_beat=mf.ticks_per_beat)
    ev = [(t, 0, mido.MetaMessage("set_tempo", tempo=v)) for t, v in tempos]
    if ts is not None:                                          # the first one only
        ev.append((0, 0, mido.MetaMessage("time_signature", numerator=ts[1],
                                          denominator=ts[2])))
    out.tracks.append(mido.MidiTrack(_delta(ev)))
    ch = 0
    nev = []
    for s, e, p, v in notes:
        if e > s:
            nev.append((s, 1, mido.Message("note_on", channel=ch, note=p, velocity=v)))
            nev.append((e, 0, mido.Message("note_off", channel=ch, note=p, velocity=0)))
    t = mido.MidiTrack()
    t.append(mido.MetaMessage("track_name", name=best["name"] or "Melody"))
    prog = best["program"] if program is None else int(program)
    t.append(mido.Message("program_change", channel=ch, program=prog & 127))
    t.extend(_delta(nev))
    out.tracks.append(t)
    return out, best


def convert(src, dst, monophonic=False, program=None):
    """Write the melody MIDI; returns the chosen candidate (None: no notes, nothing written)."""
    out, best = to_midi_file(src, monophonic, program)
    if out is not None:
        out.save(dst)
    return best


def to_midi(path, monophonic=False, program=None):
    """musikite Midi object with the melody track (None if no notes)."""
    import pretty_midi
    from .midi import Midi
    out, _ = to_midi_file(path, monophonic, program)
    if out is None:
        return None
    buf = io.BytesIO()
    out.save(file=buf)
    buf.seek(0)
    m = Midi()
    m.pm = pretty_midi.PrettyMIDI(buf)
    m.source = path
    return m
