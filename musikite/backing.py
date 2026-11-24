"""
BACKING TRACKS FOR IMPROVISATION (owner, 2026-11-18): Generate > Backing track from chords.
A MIDI with three tracks — bass, chords (piano, electric piano or jazz guitar), drums — on a
chord progression, in a simple "jazz pop" style (not too elaborate). Only the backing: the
exercise with grading stays "Chord arpeggios" (owner: inside a full backing the trumpet
could not be heard). Pure Python + pretty_midi, no Qt, no music21 (Android).

    from musikite.backing import make_backing, STYLES
    pm, info = make_backing("Dm7 G7 Cmaj7 Cmaj7", style="swing", bpm=140, choruses=3)

STYLES
  swing      walking bass (chord tones, scale steps, chromatic approach to the next root),
             comping on 2 and 4 / Charleston / anticipations, ride + hi-hat on 2 and 4
  bossa nova bass root-fifth (dotted), two-bar syncopated comping, side stick, hi-hat
             eighths
  ballad     bass root and fifth in half notes, chords held on the strong beats only,
             soft ride, cross-stick on 4
  jazz pop   straight eighths: syncopated bass, pushed chords, hi-hat eighths, backbeat

CHORDS are concert pitch here (the GUI turns written chords into concert ones). Voicings:
without the root (the bass has it): third, seventh (or sixth), and the 9th instead of the
5th on the chords that take it; each voicing is placed as close as possible to the previous
one (smooth voice leading) between D3 and C5.
Every chorus starts with a crash (not the first); the last bar of a chorus has a small
fill. A = one count-in bar (side stick), B = the choruses, C = the final chord (the first
chord of the progression). MARKER (owner, 2026-11-18): a MIDI text event
'musikite-backing {"b_q": …, "c_q": …}' (quarters where B and C start) tells that the MIDI
is a backing made here: Play in a loop then plays A, B repeated for about 10 minutes, C
(`loop_marks`, realtime.loop_events).
"""
import json
import random

import pretty_midi

MARKER = "musikite-backing"


def loop_marks(pm):
    """(b_q, c_q): quarters where B (the choruses) and C (the ending) start, if the MIDI
    is a backing made by MusiKitE (its text marker); else None."""
    for t in getattr(pm, "text_events", []) or []:
        txt = (t.text or "").strip()
        if txt.startswith(MARKER):
            try:
                d = json.loads(txt[len(MARKER):].strip())
                return float(d["b_q"]), float(d["c_q"])
            except Exception:
                return None
    return None

from . import theory as th

STYLES = {
    "swing": dict(label="Swing", bpm=140, swing=True),
    "bossa nova": dict(label="Bossa nova", bpm=130, swing=False),
    "ballad": dict(label="Ballad", bpm=70, swing=True),
    "jazz pop": dict(label="Jazz pop (straight eighths)", bpm=100, swing=False),
}
CHORD_SOUNDS = {"piano": ("Piano", 0), "electric piano": ("Electric piano", 4),
                "jazz guitar": ("Jazz guitar", 26)}
BASS_PROGRAM = {"swing": 32, "bossa nova": 32, "ballad": 32, "jazz pop": 33}
BASS_RANGE = (31, 50)                  # G1 .. D3 (sounding)
VOICE_RANGE = (50, 72)                 # D3 .. C5
KICK, SIDE, SNARE, HH_CLOSED, HH_PEDAL, CRASH, RIDE = 36, 37, 38, 42, 44, 49, 51
SWING_8 = 2.0 / 3.0                    # the "and" of a beat in swing (triplet feel)
_NINTH = {"maj7", "m7", "7", "6", "m6", "maj9", "m9", "9", "13", "m13", "6/9", "add9",
          "madd9", "m(maj7)"}


# ---------------------------------------------------------------- chords
def _timeline(chords, choruses):
    """[(start_beat, beats, Chord)] of the progression repeated `choruses` times, and the
    beats of one chorus."""
    bars = th.parse_progression(chords)
    one = th.timeline(bars)
    length = 4 * len(bars)
    out = []
    for c in range(int(choruses)):
        out += [(st + c * length, b, ch) for st, b, ch in one]
    return out, length


def _voice_pcs(ch):
    """Pitch classes of the voicing (no root): 3rd, 7th or 6th, 9th (or 5th), alterations."""
    iv = sorted({i % 12 for i in ch.intervals})
    tones = [i for i in iv if i != 0]
    if ch.quality in _NINTH:
        tones = [i for i in tones if i != 7]                       # the 5th leaves room
        if 2 not in tones:
            tones.append(2)                                        # for the 9th
    if len(tones) < 3:                                             # triads: the root back
        tones = [0] + tones
    tones = tones[:4]
    return [(ch.root + i) % 12 for i in tones]


def _voicing(ch, prev):
    """Close-position voicing of the chord near the previous one (smooth voice leading)."""
    pcs = _voice_pcs(ch)
    best, best_cost = None, None
    lo, hi = VOICE_RANGE
    for rot in range(len(pcs)):
        order = pcs[rot:] + pcs[:rot]
        for base in range(lo, lo + 12):
            if base % 12 != order[0]:
                continue
            notes = [base]
            for pc in order[1:]:
                n = notes[-1] + 1
                while n % 12 != pc:
                    n += 1
                notes.append(n)
            if notes[-1] > hi + 2:
                continue
            if prev:
                cost = sum(abs(a - b) for a, b in zip(sorted(notes), sorted(prev)))
                cost += abs(len(notes) - len(prev)) * 3
            else:
                cost = abs(sum(notes) / len(notes) - 61)
            if best_cost is None or cost < best_cost:
                best, best_cost = notes, cost
    return best or [60 + pc % 12 for pc in pcs]


# ---------------------------------------------------------------- bass
def _near(pc, ref, lo=BASS_RANGE[0], hi=BASS_RANGE[1]):
    """The pitch of a pitch class closest to ref inside [lo, hi]."""
    cands = [p for p in range(lo, hi + 1) if p % 12 == pc % 12]
    return min(cands, key=lambda p: (abs(p - ref), p))


def _scale_of(ch):
    try:
        return th.RULES.scale_for(ch)
    except Exception:
        return ch.pcs


def _walk(seg, nxt, cur, rng):
    """Walking bass of one chord: root on its first beat, chord / scale steps towards the
    next root, a chromatic (or fifth) approach on the last beat."""
    st, beats, ch = seg
    n = max(1, int(round(beats)))
    root = _near(ch.bass if ch.bass is not None else ch.root, cur)
    target = _near(nxt.root, root) if nxt is not None else root
    line = [root]
    scale = _scale_of(ch)
    for k in range(1, n):
        last = line[-1]
        if k == n - 1 and nxt is not None:               # approach the next root
            r = rng.random()
            if r < 0.55:
                p = target + (1 if rng.random() < 0.5 else -1)
            elif r < 0.8:
                p = _near((nxt.root + 7) % 12, target)
            else:
                steps = [x for x in range(target - 2, target + 3) if x != target and
                         x % 12 in scale]
                p = rng.choice(steps) if steps else target - 1
        else:
            pool = ch.pcs if k == 2 else scale
            up = target >= last
            cands = [x for x in range(last - 5, last + 6) if x != last and x % 12 in pool
                     and BASS_RANGE[0] <= x <= BASS_RANGE[1]]
            pref = [x for x in cands if (x > last) == up] or cands
            p = rng.choice(sorted(pref, key=lambda x: abs(x - last))[:3]) if pref else last
        p = max(BASS_RANGE[0], min(BASS_RANGE[1], p))
        line.append(p)
    return [(st + k, 0.92, p) for k, p in enumerate(line)], line[-1]


def _bass(style, segs, rng):
    out, cur = [], 40
    for i, seg in enumerate(segs):
        st, beats, ch = seg
        nxt = segs[i + 1][2] if i + 1 < len(segs) else None
        root = _near(ch.bass if ch.bass is not None else ch.root, cur)
        fifth = _near((ch.root + 7) % 12, root)
        if style == "swing":
            notes, cur = _walk(seg, nxt, cur, rng)
            out += notes
            continue
        if style == "ballad":                   # root and fifth (no chromatic notes held)
            out.append((st, min(beats, 2) - 0.1, root))
            if beats >= 4:
                out.append((st + 2, 1.9, fifth))
        elif style == "bossa nova":
            for b0 in range(0, int(beats), 2):
                out.append((st + b0, 1.4, root))
                out.append((st + b0 + 1.5, 0.45, fifth))
        else:                                            # jazz pop
            pat = [(0, 1.4, root), (1.5, 0.45, root), (2, 0.9, fifth), (3, 0.45, root + 12
                   if root + 12 <= BASS_RANGE[1] + 5 else root), (3.5, 0.45, fifth)]
            for o, d, p in pat:
                if o < beats:
                    out.append((st + o, d, p))
        cur = root
    return out


# ---------------------------------------------------------------- comping
def _comp_hits(style, beats, idx, rng):
    """(offset, duration) of the chord hits inside one chord of `beats` beats."""
    s8 = SWING_8
    if style == "ballad":                       # only on the strong beats (owner, 2026-11-18:
        if beats >= 4 and rng.random() < 0.5:   # the anticipations sounded out of time)
            return [(0, 1.9), (2, 1.9)]
        return [(0, beats - 0.1)]
    if style == "bossa nova":
        if beats < 4:
            return [(0, 1.4)]
        return [(0, 1.4), (1.5, 0.4), (3, 0.9)] if idx % 2 == 0 else [(1, 0.4), (2.5, 1.4)]
    if style == "jazz pop":
        if beats < 4:
            return [(0, 1.4)]
        return rng.choice([[(0, 1.4), (1.5, 0.4), (2.5, 1.4)], [(0, 2.9), (3.5, 0.45)],
                           [(0, 0.9), (1.5, 2.4)]])
    if beats < 4:                                        # swing
        return rng.choice([[(0, 0.6)], [(1, 0.5)], [(0, 1.5)]])
    return rng.choice([[(1, 0.5), (3, 0.5)],                       # 2 and 4
                       [(0, 0.9), (1 + s8, 0.5)],                  # Charleston
                       [(0, 1.5), (2 + s8, 0.9)],
                       [(1 + s8, 0.5), (3, 0.5)]])


def _comp(style, segs, rng):
    out, prev = [], None
    for i, (st, beats, ch) in enumerate(segs):
        v = _voicing(ch, prev)
        prev = v
        for off, dur in _comp_hits(style, beats, i, rng):
            if off >= beats:
                continue
            vel = rng.randint(58, 72) if style != "ballad" else rng.randint(48, 60)
            out += [(st + off, min(dur, beats - off + 0.5), p, vel) for p in v]
    return out


# ---------------------------------------------------------------- drums
def _drums(style, total, chorus, rng, count_in):
    """[(beat, duration, key, velocity)] of the drum track (channel 10)."""
    out = []
    s8 = SWING_8
    bars = int(total // 4)
    for b in range(bars):
        t = 4.0 * b
        last_of_chorus = (t + 4) % chorus == 0
        if t % chorus == 0 and t > 0:
            out.append((t, 1.0, CRASH, 80))
        if style == "swing":
            for beat in range(4):
                out.append((t + beat, 0.3, RIDE, 72 if beat % 2 else 62))
            out += [(t + 1 + s8, 0.2, RIDE, 50), (t + 3 + s8, 0.2, RIDE, 50)]
            out += [(t + 1, 0.2, HH_PEDAL, 64), (t + 3, 0.2, HH_PEDAL, 64)]
            for beat in range(4):
                out.append((t + beat, 0.2, KICK, 34))              # feathering
            if last_of_chorus:
                out += [(t + 3, 0.2, SNARE, 70), (t + 3 + s8, 0.2, SNARE, 80)]
            elif rng.random() < 0.25:
                out.append((t + 2 + s8, 0.2, SNARE, 40))           # comping on the snare
        elif style == "ballad":
            for beat in range(4):
                out.append((t + beat, 0.3, RIDE, 48))
            out += [(t + 1, 0.2, HH_PEDAL, 50), (t + 3, 0.2, HH_PEDAL, 50),
                    (t + 3, 0.2, SIDE, 45), (t, 0.2, KICK, 40)]
        elif style == "bossa nova":
            for e in range(8):
                out.append((t + 0.5 * e, 0.2, HH_CLOSED, 58 if e % 2 == 0 else 42))
            side = (0, 1.5, 3) if b % 2 == 0 else (1, 2.5)
            out += [(t + o, 0.2, SIDE, 66) for o in side]
            out += [(t + o, 0.3, KICK, 58) for o in (0, 1.5, 2, 3.5)]
        else:                                                      # jazz pop
            for e in range(8):
                out.append((t + 0.5 * e, 0.2, HH_CLOSED, 66 if e % 2 == 0 else 46))
            out += [(t, 0.3, KICK, 80), (t + 2.5, 0.3, KICK, 64),
                    (t + 1, 0.2, SNARE, 78), (t + 3, 0.2, SNARE, 78)]
            if last_of_chorus:
                out += [(t + 3.5, 0.2, SNARE, 70), (t + 3.75, 0.2, SNARE, 74)]
    return out


# ---------------------------------------------------------------- the track
def make_backing(chords, style="swing", bpm=None, choruses=3, sound="piano", key=None,
                 seed=None, count_in=True, ending=True):
    """(PrettyMIDI, info) of a backing track on CONCERT chords ('Dm7 G7 Cmaj7 Cmaj7';
    'A:B' = two chords in a bar). key: name of progressions.KEYS for the key signature
    (None = from the first chord)."""
    if style not in STYLES:
        raise ValueError(f"unknown style {style}; known: {', '.join(STYLES)}")
    if sound not in CHORD_SOUNDS:
        raise ValueError(f"unknown chord sound {sound}; known: {', '.join(CHORD_SOUNDS)}")
    seed = random.randrange(1000000) if seed is None else int(seed)
    rng = random.Random(seed)
    bpm = float(bpm or STYLES[style]["bpm"])
    segs, chorus = _timeline(chords, max(1, int(choruses)))
    total = segs[-1][0] + segs[-1][1]
    lead = 4.0 if count_in else 0.0
    end_beats = 4.0 if ending else 0.0
    spq = 60.0 / bpm

    def sec(q):
        return (q + lead) * spq

    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0.0))
    from .progressions import key_of_chords, key_parts
    k = key or key_of_chords(chords)
    try:
        tonic, minor = key_parts(k)
        pm.key_signature_changes.append(pretty_midi.KeySignature(tonic + (12 if minor else 0),
                                                                 0.0))
    except Exception:
        pass
    bass = pretty_midi.Instrument(program=BASS_PROGRAM[style], name="Bass")
    for st, d, p in _bass(style, segs, rng):
        bass.notes.append(pretty_midi.Note(rng.randint(78, 96), int(p), sec(st), sec(st + d)))
    name, prog = CHORD_SOUNDS[sound]
    comp = pretty_midi.Instrument(program=prog, name=name)
    for st, d, p, v in _comp(style, segs, rng):
        comp.notes.append(pretty_midi.Note(v, int(p), sec(st), sec(st + d)))
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    for st, d, p, v in _drums(style, total, chorus, rng, count_in):
        drums.notes.append(pretty_midi.Note(v, p, sec(st), sec(st + d)))
    if count_in:                                     # one bar of side stick
        for b in range(4):
            drums.notes.append(pretty_midi.Note(90 if b == 0 else 75, SIDE, b * spq,
                                                (b + 0.3) * spq))
    if ending:                                       # the first chord, held, with a crash
        first = segs[0][2]
        t0 = total
        root = _near(first.root, 36)
        bass.notes.append(pretty_midi.Note(95, root, sec(t0), sec(t0 + 3.5)))
        for p in _voicing(first, None):
            comp.notes.append(pretty_midi.Note(70, p, sec(t0), sec(t0 + 3.5)))
        drums.notes += [pretty_midi.Note(95, CRASH, sec(t0), sec(t0 + 2)),
                        pretty_midi.Note(90, KICK, sec(t0), sec(t0 + 0.3))]
    for st, b, ch in segs:                           # the chord names, as text events
        pm.lyrics.append(pretty_midi.Lyric(ch.symbol, sec(st)))
    b_q, c_q = lead, lead + total                    # quarters (4/4: beats = quarters)
    pm.text_events.append(pretty_midi.Text(
        MARKER + " " + json.dumps(dict(b_q=b_q, c_q=c_q, style=style)), 0.0))
    pm.instruments += [comp, bass, drums]
    info = dict(style=style, chords=chords, key=k, bpm=bpm, choruses=int(choruses),
                b_q=b_q, c_q=c_q,
                bars=int((total + lead + end_beats) // 4), seed=seed, sound=sound,
                count_in=bool(count_in), ending=bool(ending), backing=True)
    return pm, info
