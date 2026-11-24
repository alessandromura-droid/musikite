"""
DUET FROM A MELODY (owner, 2026-11-20: "fai accompagnamento", like making a duet but one of
the two parts is already there): a second voice for an existing melody — a track of a MIDI,
a score or an exercise — made with the theory engine of the duets. Pure Python, no Qt, no
music21 (Android).

    from musikite import accompany
    d = accompany.duet_from_melody(midi, mode="harmony")          # a NEW Midi, two tracks
    d = accompany.duet_from_melody(phrase, mode="canon", delay="1 bar")
    d = midi.duet_from_melody(mode="accompaniment", pattern="beats",
                              instrument="C (trombone)")
    accompany.chords_of(midi)                                      # the chords found

MODES
  harmony        the same rhythm, every note harmonised a third (or a sixth) below / above
                 IN THE KEY (major or minor third from the scale, not a transposition);
                 where the chord of the moment asks for it (strong beats, long notes, chord
                 tones of the melody, the last note) a chord tone: the other of the two
                 intervals, a fifth, the octave or a fourth; never the unison, no parallel
                 fifths / octaves.
  canon          the melody itself in the second voice, delayed (half bar, 1, 2, 4 bars) at
                 the unison / octave, the fifth, the fourth or the third, in the key (tonal
                 answer: steps of the scale); octave chosen by the second instrument's range.
                 "auto" tries every delay and interval and keeps the most consonant (strong
                 beats count twice). A melody that does not reach MIN_CONSONANCE is REFUSED
                 (owner: a canon does not work on every melody) unless allow_dissonant.
                 strict=False: a note of the follower dissonant on a strong beat is moved to
                 the nearest consonant chord tone, its last note to the tonic chord; the
                 melody voice holds a note of the tonic chord under the follower's last note.
  accompaniment  the chord of every bar / half bar (analyse) played by the second voice:
                 long notes (one a chord), half notes, one note a beat (root on the downbeat,
                 a step towards the next root before a change) or arpeggios (up, up, down);
                 "auto" from how busy the melody is (busy melody -> long notes).

HARMONIC ANALYSIS (analyse): candidates = the diatonic triads of the key, + the major
dominant and the dominant seventh (major / minor keys), + the secondary dominants V/ii, V/IV,
V/V, V/vi (major keys); every bar or half bar (4/4, 2/2, 6/8, 12/8…; 3/4 and 2/4 one chord a
bar) gets the chord that best covers the melody notes sounding in it (duration, the strong
beats count 1.5; passing notes of the key cost little, chromatic notes more), the sequence
chosen as a whole (Viterbi): the usual moves preferred (down a fifth, a dominant resolving,
IV -> V), one chord a bar preferred, a secondary dominant must resolve, tonic at the start and
at the end, the dominant before the end. Owner (2026-11-20): no field to correct the chords —
where the melody does not define a chord any one is good (ties: the commonest).

LIMITS: the bars follow the time signatures of the MIDI from its start (a pickup bar is not
detected: the strong beats are then shifted); one key for the whole melody (no modulations);
the melody is one voice (the top note of chords). Melody track of a MIDI: the one with the
MOST NOTES (owner's rule of libgen) unless chosen.

Times in quarters, pitches concert MIDI numbers (as Midi objects).
"""
import bisect
import copy
import os
import re

from . import theory as th

EPS = 1e-6
VERSION = 1                    # raise when a rule changes a result
MODES = ("harmony", "canon", "accompaniment")
SIDES = ("below", "above")
INTERVALS = ("thirds", "sixths")
DELAYS = ("auto", "half bar", "1 bar", "2 bars", "4 bars")
CANON_INTERVALS = {"auto": None, "unison / octave": 0, "fifth below (fourth above)": -4,
                   "fourth below (fifth above)": -3, "third below (sixth above)": -2}
PATTERNS = ("auto", "long notes", "half notes", "beats", "arpeggio")
MIN_CONSONANCE = 0.7           # canon: consonant fraction of the time (strong beats twice)
MIN_NOTES = 4
DISSONANT = (1, 2, 6, 10, 11)  # semitones mod 12 between the two voices (tritone included)

# harmonic analysis
FIT_W, PRIOR_W = 2.0, 0.5
PRIOR_MAJOR = (1.0, 0.6, 0.35, 0.8, 0.9, 0.6, 0.15)     # I ii iii IV V vi vii°
PRIOR_MINOR = (1.0, 0.25, 0.5, 0.8, 0.3, 0.6, 0.5)      # i ii° III iv v VI VII
PRIOR_MODAL = (1.0, 0.6, 0.45, 0.6, 0.6, 0.5, 0.4)
ROOT_MOVES = {0: 0.0, 5: 0.6, 7: 0.2, 2: 0.2, 9: 0.15, 3: 0.05, 4: 0.0, 8: 0.0,
              10: -0.15, 1: -0.2, 11: -0.1, 6: -0.4}    # root motion (semitones up) -> bonus
FROM_MAJOR = {"ionian": 0, "dorian": 2, "phrygian": 4, "lydian": 5, "mixolydian": 7,
              "aeolian": 9, "locrian": 11}

# harmony: cost of the interval (mod 12) between the melody and the second voice
HARMONY_COST = {"thirds": {3: 0.0, 4: 0.0, 8: 1.0, 9: 1.0, 7: 2.2, 0: 2.6, 5: 2.8},
                "sixths": {8: 0.0, 9: 0.0, 3: 1.0, 4: 1.0, 7: 2.2, 0: 2.6, 5: 2.8}}


# ======================================================================== bars and beats
def bars_of(ts, end_q):
    """Bars up to end_q: [(start, length, (num, den))] in quarters. ts: [(quarter, num, den)]
    of the time signatures (4/4 if none; the first one counts from the start)."""
    ts = sorted((float(q), int(n), int(d)) for q, n, d in ts if int(n) > 0 and int(d) > 0)
    if not ts:
        ts = [(0.0, 4, 4)]
    ts[0] = (0.0, ts[0][1], ts[0][2])
    out, t, i = [], 0.0, 0
    while t < end_q - EPS or not out:
        while i + 1 < len(ts) and ts[i + 1][0] <= t + EPS:
            i += 1
        num, den = ts[i][1], ts[i][2]
        L = num * 4.0 / den
        out.append((t, L, (num, den)))
        t += L
    return out


class Meter:
    """The bars of a piece: [(start, length, (num, den))] in quarters."""

    def __init__(self, bars):
        self.bars = bars
        self.starts = [b[0] for b in bars]

    def bar_at(self, t):
        i = bisect.bisect_right(self.starts, t + EPS) - 1
        return min(max(i, 0), len(self.bars) - 1)

    def half(self, i):
        """Length of half bar i when the metre has two halves (4/4, 2/2, 6/8, 12/8, 6/4),
        else None (3/4, 2/4, 5/4…)."""
        _, L, (num, _) = self.bars[i]
        return L / 2.0 if num % 2 == 0 and L >= 3 - EPS else None

    def beat(self, i):
        """The beat of bar i in quarters (6/8, 9/8, 12/8: the dotted quarter)."""
        _, _, (num, den) = self.bars[i]
        return 1.5 if den == 8 and num % 3 == 0 and num > 3 else 4.0 / den

    def strong(self, t):
        """2 = downbeat, 1 = middle of the bar (where the metre has halves), 0 = elsewhere."""
        i = self.bar_at(t)
        s, L, _ = self.bars[i]
        x = t - s
        if abs(x) < EPS or abs(x - L) < EPS:
            return 2
        h = self.half(i)
        return 1 if h is not None and abs(x - h) < EPS else 0

    def units(self, end):
        """Harmonic units up to end: [(start, stop, bar index)] = the halves of the bar where
        the metre has them, else the whole bar."""
        out = []
        for i, (s, L, _) in enumerate(self.bars):
            if s >= end - EPS:
                break
            h = self.half(i)
            if h is None:
                out.append((s, s + L, i))
            else:
                out += [(s, s + h, i), (s + h, s + L, i)]
        return out


def _octave_shift(pitches, lo, hi):
    """Whole octaves (k) that put most pitches inside [lo, hi] (a tie: the smallest |k|)."""
    best = None
    for k in range(-4, 5):
        out = sum(1 for p in pitches if not lo <= p + 12 * k <= hi)
        key = (out, abs(k), k)
        if best is None or key < best:
            best = key
    return best[2]


def _fold(p, lo, hi):
    while p < lo:
        p += 12
    while p > hi:
        p -= 12
    if p < lo:                       # range smaller than an octave: the nearer edge
        p = p + 12 if (p + 12 - hi) < (lo - p) else p
    return p


class _Scale:
    """The pitches of the key, for steps of the scale."""

    def __init__(self, key):
        self.pcs = frozenset(key.pcs)
        self.pitches = [p for p in range(128) if p % 12 in self.pcs]

    def nearest(self, p):
        i = bisect.bisect_left(self.pitches, p)
        cands = [j for j in (i - 1, i) if 0 <= j < len(self.pitches)]
        return min(cands, key=lambda j: (abs(self.pitches[j] - p), self.pitches[j]))

    def shift(self, p, k):
        """p moved by k steps of the scale (a chromatic note keeps its offset)."""
        j = self.nearest(p)
        off = p - self.pitches[j]
        j2 = min(max(j + k, 0), len(self.pitches) - 1)
        return self.pitches[j2] + off


def _sounding(notes, starts, t):
    """Pitches of a one-voice line sounding at t."""
    i = bisect.bisect_right(starts, t + EPS) - 1
    if i >= 0 and notes[i][0] + notes[i][1] > t + EPS:
        return [notes[i][2]]
    return []


def _overlapping(notes, starts, a, b):
    """[(where it starts to sound together, pitch)] of a one-voice line during [a, b)."""
    i0 = max(bisect.bisect_right(starts, a + EPS) - 1, 0)
    i1 = bisect.bisect_left(starts, b - EPS)
    out = []
    for s, d, p in notes[i0:i1]:
        x0, x1 = max(s, a), min(s + d, b)
        if x1 - x0 > EPS:
            out.append((x0, p))
    return out


# ======================================================================== the melody
def monophonic(notes):
    """One voice: the top note of every onset; a note is cut where the next one starts."""
    by = {}
    for s, d, p in notes:
        k = round(float(s), 6)
        if k not in by or int(p) > by[k][2]:
            by[k] = [float(s), float(d), int(p)]
    out = [by[k] for k in sorted(by)]
    for a, b in zip(out, out[1:]):
        if a[0] + a[1] > b[0] + EPS:
            a[1] = b[0] - a[0]
    return [n for n in out if n[1] > EPS]


def melody_tracks(midi):
    """[(index, label, number of notes)] of the pitched tracks of a Midi (drums left out)."""
    import pretty_midi
    out = []
    for i, ins in enumerate(midi.pm.instruments):
        if ins.is_drum or not ins.notes:
            continue
        name = ins.name or pretty_midi.program_to_instrument_name(ins.program)
        out.append((i, f"{i + 1}: {name} ({len(ins.notes)} notes)", len(ins.notes)))
    return out


def melody_track(midi):
    """Index of the melody track: the one with the MOST NOTES (owner's rule, libgen)."""
    tr = melody_tracks(midi)
    if not tr:
        raise ValueError("no notes: the MIDI has no pitched track")
    return max(tr, key=lambda x: (x[2], -x[0]))[0]


def _q(pm, t):
    return pm.time_to_tick(t) / float(pm.resolution)


def _rnd(x):
    return round(float(x) * 96) / 96.0


def _source(obj, track=None):
    """(Midi, melody track, melody [start, dur, pitch] in quarters, title, (tonic, mode) of
    an exercise or None). obj: Midi, Score, exercise (Phrase) or a MIDI file path."""
    from .midi import Midi
    from .phrase import Phrase
    from .score import Score
    given = None
    if isinstance(obj, str):
        m = Midi(obj)
        title = os.path.splitext(os.path.basename(obj))[0]
    elif isinstance(obj, Phrase):
        m = obj.to_midi()
        title = obj.title or "exercise"
        given = (obj.tonic, obj.mode)
        track = 0
    elif isinstance(obj, Score):
        m = obj.to_midi()
        title = getattr(obj, "title", None) or "score"
    elif isinstance(obj, Midi):
        m = obj
        title = getattr(obj, "title", None) or (
            os.path.splitext(os.path.basename(obj.source))[0] if obj.source else "MIDI")
    else:
        raise TypeError("the melody must be a MIDI, a score or an exercise")
    ok = [i for i, _, _ in melody_tracks(m)]
    if track is None or track not in ok:
        track = melody_track(m)
    pm = m.pm
    notes = []
    for n in pm.instruments[track].notes:
        s, e = _rnd(_q(pm, n.start)), _rnd(_q(pm, n.end))
        if e - s > EPS:
            notes.append([s, e - s, int(n.pitch)])
    return m, track, monophonic(notes), title, given


def meter_of(pm, end_q):
    """Meter of a pretty_midi object up to end_q quarters."""
    ts = [(_q(pm, t.time), t.numerator, t.denominator) for t in pm.time_signature_changes]
    return Meter(bars_of(ts, end_q))


def key_of(notes, given=None):
    """theory.Key of the melody: the exercise's own key, else estimated (tonalita.m)."""
    tonic, mode = given if given else th.key_of_notes(notes)
    try:
        return th.Key(tonic, mode)
    except ValueError:
        return th.Key(tonic, "ionian")


def key_label(key):
    name = th.BRASS_NAMES[key.tonic]
    return name + {"ionian": " major", "aeolian": " minor"}.get(key.mode, " " + key.mode)


# ======================================================================== harmonic analysis
def candidates(key):
    """Chords that may harmonise the melody: [(Chord, prior, kind)], kind 'diatonic',
    'dominant' or 'secondary' (must resolve down a fifth)."""
    major = key.mode == "ionian"
    minor = key.mode == "aeolian"
    pri = PRIOR_MAJOR if major else PRIOR_MINOR if minor else PRIOR_MODAL
    out, seen = [], set()

    def add(c, p, kind):
        if (c.root, c.quality) not in seen:
            seen.add((c.root, c.quality))
            out.append((c, p, kind))

    for d, c in enumerate(key.diatonic_chords(sevenths=False)):
        p = pri[d] if d < len(pri) else 0.4
        if c.quality not in ("", "m"):
            p = min(p, 0.2)
        add(c, p, "diatonic")
    if major or minor:
        dom = (key.tonic + 7) % 12
        add(th.Chord(dom, ""), 0.9, "dominant")
        add(th.Chord(dom, "7"), 0.6, "dominant")
    if major:
        for deg, q in ((2, ""), (4, ""), (9, ""), (0, "7")):    # V/V, V/vi, V/ii, V/IV
            add(th.Chord(key.tonic + deg, q), 0.25, "secondary")
    return out


def _fit(notes, chord, key_pcs, u0, u1, meter):
    """How well a chord covers the melody notes sounding in [u0, u1) (per quarter);
    returns (fit, number of notes)."""
    sc, n = 0.0, 0
    for s, d, p in notes:
        a, b = max(s, u0), min(s + d, u1)
        if b - a <= EPS:
            continue
        w = b - a
        strong = meter.strong(a) > 0
        if strong:
            w *= 1.5
        pc = p % 12
        if pc in chord.pcs:
            sc += w
        elif pc in key_pcs:
            sc -= (0.7 if strong else 0.3) * w
        else:
            sc -= w
        n += 1
    return sc / max(u1 - u0, EPS), n


def _move(a, b, mid_bar, empty):
    """Bonus of the move from candidate a to candidate b."""
    (c1, _, k1), (c2, _, _) = a, b
    if c1 == c2:
        return 0.4 if empty else 0.0
    iv = (c2.root - c1.root) % 12
    v = ROOT_MOVES[iv]
    if iv == 5 and c1.quality in ("", "7"):
        v += 0.3                                  # a dominant resolving
    if k1 == "secondary" and iv != 5:
        v -= 0.8
    if mid_bar:
        v -= 0.25                                 # one chord a bar preferred
    if empty:
        v -= 0.3                                  # nothing in the melody asks for a change
    return v


def analyse(notes, meter, key):
    """Chords of a melody: [(start, end, Chord)], one per bar or half bar (merged when the
    same chord goes on)."""
    end = max(s + d for s, d, _ in notes)
    units = meter.units(end)
    cands = candidates(key)
    kp = frozenset(key.pcs)
    starts = [n[0] for n in notes]
    dom = (key.tonic + 7) % 12
    local, filled = [], []
    for u0, u1, _ in units:
        i0 = max(bisect.bisect_right(starts, u0 + EPS) - 1, 0)
        i1 = bisect.bisect_left(starts, u1 - EPS)
        sub = notes[i0:i1]
        row, has = [], False
        for c, prior, _ in cands:
            f, n = _fit(sub, c, kp, u0, u1, meter)
            has = has or n > 0
            row.append(FIT_W * f + PRIOR_W * prior)
        local.append(row)
        filled.append(has)
    with_notes = [k for k, h in enumerate(filled) if h] or [0]
    first, last = with_notes[0], with_notes[-1]
    for j, (c, _, kind) in enumerate(cands):
        if c.root == key.tonic and kind == "diatonic":
            local[first][j] += 0.6
            local[last][j] += 1.0
        if c.root == dom and kind != "secondary" and last > first:
            local[last - 1][j] += 0.3
    N = len(cands)
    score = list(local[0])
    back = []
    for u in range(1, len(units)):
        mid = units[u][2] == units[u - 1][2]
        empty = not filled[u]
        new, bk = [], []
        for j in range(N):
            best, arg = None, 0
            for i in range(N):
                v = score[i] + _move(cands[i], cands[j], mid, empty)
                if best is None or v > best + 1e-9:
                    best, arg = v, i
            new.append(best + local[u][j])
            bk.append(arg)
        score = new
        back.append(bk)
    j = max(range(N), key=lambda k: (score[k], cands[k][1]))
    path = [j]
    for bk in reversed(back):
        j = bk[j]
        path.append(j)
    path.reverse()
    segs = []
    for (u0, u1, _), j in zip(units, path):
        c = cands[j][0]
        if segs and segs[-1][2] == c and abs(segs[-1][1] - u0) < EPS:
            segs[-1] = (segs[-1][0], u1, c)
        else:
            segs.append((u0, u1, c))
    return segs


class ChordMap:
    """The chord at any time (after the last segment: the last chord)."""

    def __init__(self, segs):
        self.segs = segs
        self.starts = [s for s, _, _ in segs]

    def at(self, t):
        i = bisect.bisect_right(self.starts, t + EPS) - 1
        return self.segs[min(max(i, 0), len(self.segs) - 1)][2]


def chords_text(segs, meter, end):
    """The chords as the duets write them: one token a bar, 'F:G' = two in a bar."""
    cm = ChordMap(segs)
    out = []
    for i, (s, _, _) in enumerate(meter.bars):
        if s >= end - EPS:
            break
        h = meter.half(i)
        a = cm.at(s).name()
        b = cm.at(s + h).name() if h is not None else a
        out.append(a if a == b else f"{a}:{b}")
    return " ".join(out)


def chords_of(src, track=None):
    """The chords found for the melody of a MIDI / score / exercise (text, as the duets)."""
    m, track, mel, _, given = _source(src, track)
    if not mel:
        raise ValueError("the melody has no notes")
    end = max(s + d for s, d, _ in mel)
    meter = meter_of(m.pm, end)
    key = key_of(mel, given)
    return chords_text(analyse(mel, meter, key), meter, end)


# ======================================================================== harmony
def harmony(mel, chords, meter, key, lo, hi, side="below", interval="thirds"):
    """The second voice in parallel thirds / sixths, chord tones where the harmony asks."""
    if interval not in INTERVALS:
        raise ValueError(f"interval must be one of {', '.join(INTERVALS)}")
    sc = _Scale(key)
    sign = -1 if side == "below" else 1
    costs = HARMONY_COST[interval]
    steps = 2 if interval == "thirds" else 5
    ideal = [sc.shift(p, sign * steps) for _, _, p in mel]
    k = _octave_shift(ideal, lo, hi)
    out = []
    prev_p = prev_q = None
    last = len(mel) - 1
    for i, (s, d, p) in enumerate(mel):
        chord = chords.at(s)
        i_bar = meter.bar_at(s)
        harmonic = (meter.strong(s) > 0 or d >= meter.beat(i_bar) - EPS
                    or p % 12 in chord.pcs or i == last)
        target = ideal[i] + 12 * k if prev_q is None else prev_q + (p - prev_p)
        best = None
        for q in range(lo, hi + 1):
            if q == p:
                continue
            ivc = abs(p - q) % 12
            if ivc not in costs:
                continue                                   # dissonant
            c = costs[ivc]
            if (q - p) * sign < 0:
                c += 6.0                                   # on the wrong side of the melody
            if harmonic and q % 12 not in chord.pcs:
                c += 3.0
            if not harmonic and q % 12 not in sc.pcs and q % 12 not in chord.pcs:
                c += 2.0
            c += 0.25 * abs(q - target)
            if prev_q is not None:
                leap = abs(q - prev_q)
                if leap > 7:
                    c += 0.3 * (leap - 7)
                piv = abs(prev_p - prev_q) % 12
                if ivc in (0, 7) and ivc == piv and (p - prev_p) * (q - prev_q) > 0:
                    c += 6.0                               # parallel fifths / octaves
            if best is None or c < best[0] - 1e-9:
                best = (c, q)
        q = best[1] if best else _fold(ideal[i] + 12 * k, lo, hi)
        out.append([s, d, q])
        prev_p, prev_q = p, q
    return out


# ======================================================================== canon
def _delays(meter, choice):
    if choice not in DELAYS:
        raise ValueError(f"delay must be one of {', '.join(DELAYS)}")
    bar = meter.bars[0][1]
    table = {"half bar": meter.half(0), "1 bar": bar, "2 bars": 2 * bar, "4 bars": 4 * bar}
    names = [choice] if choice != "auto" else ["1 bar", "2 bars", "half bar", "4 bars"]
    return [(n, table[n]) for n in names if table.get(n)]


def _fit_line(line, lo, hi):
    """The whole line moved by octaves into [lo, hi]; the notes still outside folded."""
    k = _octave_shift([p for _, _, p in line], lo, hi)
    return [[s, d, _fold(p + 12 * k, lo, hi)] for s, d, p in line]


def _pairs(a, b):
    """(start, stop, pitch of a, pitch of b) of every stretch where a and b sound together
    (b sorted by start)."""
    starts = [n[0] for n in b]
    maxd = max((n[1] for n in b), default=0.0)
    out = []
    for s, d, p in a:
        e = s + d
        j0 = bisect.bisect_left(starts, s - maxd - EPS)
        j1 = bisect.bisect_left(starts, e - EPS)
        for t, dd, q in b[j0:j1]:
            x0, x1 = max(s, t), min(e, t + dd)
            if x1 - x0 > EPS:
                out.append((x0, x1, p, q))
    return out


def consonance(lead, fol, meter):
    """Consonant fraction of the time the two voices sound together (strong beats twice;
    the unison counts half bad). None if they never sound together."""
    tot = bad = 0.0
    for x0, x1, p, q in _pairs(lead, fol):
        w = (x1 - x0) * (2.0 if meter.strong(x0) else 1.0)
        iv = abs(p - q) % 12
        tot += w
        if iv in DISSONANT:
            bad += w
        elif p == q:
            bad += 0.5 * w
    return (1.0 - bad / tot) if tot > EPS else None


def _smooth(lead, fol, chords, meter, key, lo, hi):
    """Not strict: follower notes dissonant on a strong beat -> the nearest consonant chord
    tone (within a major third); the last note -> the tonic chord."""
    starts = [n[0] for n in lead]
    tonic_pcs = key.diatonic_chords(sevenths=False)[0].pcs
    out, moved = [], 0
    for j, (s, d, p) in enumerate(fol):
        last = j == len(fol) - 1
        here = _sounding(lead, starts, s)
        bad = any(abs(p - q) % 12 in DISSONANT or p == q for q in here)
        if last:
            if p % 12 in tonic_pcs and not bad:
                out.append([s, d, p])
                continue
            pcs = tonic_pcs
        elif meter.strong(s) > 0 and bad:
            pcs = chords.at(s).pcs
        else:
            out.append([s, d, p])
            continue
        cands = [x for x in range(max(lo, p - 4), min(hi, p + 4) + 1)
                 if x % 12 in pcs and all(abs(x - q) % 12 not in DISSONANT and x != q
                                          for q in here)]
        if cands:
            x = min(cands, key=lambda x: (abs(x - p), x))
            moved += x != p
            out.append([s, d, x])
        else:
            out.append([s, d, p])
    return out, moved


def _tail(lead, fol, key, end):
    """The melody voice holds a note of the tonic chord under the follower's last note."""
    fs, fd, fp = fol[-1]
    if fs < end - EPS:
        return lead
    lp = lead[-1][2]
    tpcs = key.diatonic_chords(sevenths=False)[0].pcs
    cands = [x for x in range(lp - 7, lp + 8)
             if x % 12 in tpcs and x != fp and abs(x - fp) % 12 not in DISSONANT]
    if not cands:
        return lead
    x = min(cands, key=lambda x: (abs(x - lp), x))
    return lead + [[fs, fd, x]]


def canon(mel, chords, meter, key, lo, hi, delay="auto", canon_interval="auto",
          strict=False, allow_dissonant=False):
    """(melody voice, follower, info): the melody delayed in the second voice."""
    if canon_interval not in CANON_INTERVALS:
        raise ValueError(f"canon_interval must be one of {', '.join(CANON_INTERVALS)}")
    sc = _Scale(key)
    if canon_interval == "auto":
        ivs = [(n, k) for n, k in CANON_INTERVALS.items() if k is not None]
    else:
        ivs = [(canon_interval, CANON_INTERVALS[canon_interval])]
    delays = _delays(meter, delay)
    if not delays:
        raise ValueError(f"delay '{delay}': this metre has no half bar")
    end = max(s + d for s, d, _ in mel)
    best = None
    for dn, D in delays:
        if D >= end - EPS:
            continue
        for iname, k in ivs:
            fol = _fit_line([[s + D, d, sc.shift(p, k)] for s, d, p in mel], lo, hi)
            c = consonance(mel, fol, meter)
            if c is not None and (best is None or c > best[0] + 1e-9):
                best = (c, dn, iname, fol)
    if best is None:
        raise ValueError("the melody is too short for a canon with this delay")
    c, dn, iname, fol = best
    if c < MIN_CONSONANCE and not allow_dissonant:
        raise ValueError(f"this melody does not hold a canon: the best one (delay {dn}, "
                         f"{iname}) is only {c:.0%} consonant, at least "
                         f"{MIN_CONSONANCE:.0%} is needed. Tick 'Even if dissonant' to make "
                         "it anyway, or choose another mode")
    moved = 0
    if not strict:
        fol, moved = _smooth(mel, fol, chords, meter, key, lo, hi)
    lead = _tail([list(n) for n in mel], fol, key, end)
    after = consonance(mel, fol, meter)
    info = dict(delay=dn, canon_interval=iname, consonance=round(c, 3),
                consonance_after=round(after, 3) if after is not None else None,
                moved=moved, strict=bool(strict))
    return lead, fol, info


# ======================================================================== accompaniment
def _auto_pattern(mel, meter):
    end = max(s + d for s, d, _ in mel)
    beats = 0.0
    for i, (s, L, _) in enumerate(meter.bars):
        if s >= end - EPS:
            break
        beats += L / meter.beat(i)
    density = len(mel) / max(beats, 1.0)
    return "long notes" if density > 1.5 else "half notes" if density > 0.75 else "beats"


def _events(meter, segs, end, pattern):
    """Rhythm of the accompaniment: [(start, dur)], cut at every chord change too."""
    changes = [s for s, _, _ in segs]
    ev = []
    for i, (s, L, _) in enumerate(meter.bars):
        if s >= end - EPS:
            break
        if pattern == "long notes":
            cuts = [s, s + L]
        elif pattern == "half notes":
            h = meter.half(i)
            cuts = [s, s + h, s + L] if h else [s, s + L]
        else:
            b = meter.beat(i)
            cuts = [s + k * b for k in range(int(L / b + EPS) + 1)]
            if cuts[-1] < s + L - EPS:
                cuts.append(s + L)
        cuts += [c for c in changes if s + EPS < c < s + L - EPS]
        cuts = sorted({round(c, 6) for c in cuts})
        ev += [(a, b - a) for a, b in zip(cuts, cuts[1:]) if b - a > EPS]
    return ev


def accompaniment(mel, chords, segs, meter, key, lo, hi, side="below", pattern="auto"):
    """(second voice, pattern used): the chords played as long notes, half notes, beats or
    arpeggios, around the melody."""
    if pattern not in PATTERNS:
        raise ValueError(f"pattern must be one of {', '.join(PATTERNS)}")
    if pattern == "auto":
        pattern = _auto_pattern(mel, meter)
    sign = -1 if side == "below" else 1
    sc = _Scale(key)
    tonic = key.diatonic_chords(sevenths=False)[0]
    end = max(s + d for s, d, _ in mel)
    ev = _events(meter, segs, end, pattern)
    starts = [n[0] for n in mel]
    out, prev, k_in = [], None, 0
    for j, (s, d) in enumerate(ev):
        last = j == len(ev) - 1
        c = tonic if last else chords.at(s)
        new_chord = j == 0 or last or chords.at(ev[j - 1][0]) != c
        k_in = 0 if new_chord else k_in + 1
        accent = meter.strong(s) == 2 or new_chord
        nxt = chords.at(ev[j + 1][0]) if j + 1 < len(ev) else None
        approach = (pattern == "beats" and nxt is not None and nxt != c and not new_chord
                    and meter.strong(s) == 0)
        here = _overlapping(mel, starts, s, s + d)
        if here:
            ref = sum(p for _, p in here) / len(here)
        else:
            i = bisect.bisect_right(starts, s + EPS) - 1
            ref = mel[max(i, 0)][2]
        target = min(max(ref + sign * 9, lo + 2), hi - 2)
        cands = c.tones(lo, hi)
        if approach:
            pcs = {(nxt.root + x) % 12 for x in (-2, 2) if (nxt.root + x) % 12 in sc.pcs}
            pcs.add((nxt.root - 1) % 12)                 # the chromatic note below the root
            cands += [x for x in range(lo, hi + 1) if x % 12 in pcs and x not in cands]
        best = None
        for q in cands:
            cost = 0.12 * abs(q - target)
            pc = q % 12
            if pc in c.pcs:
                deg = (pc - c.root) % 12
                if deg == 0 and accent:
                    cost -= 1.2 if side == "below" else 0.3
                elif deg in (3, 4):
                    cost -= 0.5 if accent else 0.2
                if last and deg == 0:
                    cost -= 2.0
            else:
                cost -= 0.6                               # a step to the next root
            if prev is not None:
                mv = q - prev
                cost += 0.3 * abs(mv)
                if pattern in ("beats", "arpeggio") and mv == 0:
                    cost += 1.0
                if pattern == "arpeggio" and k_in > 0:
                    want = 1 if k_in % 4 in (1, 2) else -1
                    if mv * want <= 0:
                        cost += 2.5
            for x0, m in here:
                iv = abs(q - m) % 12
                if q == m:
                    cost += 3.0
                elif iv in (1, 2, 10, 11):
                    cost += 6.0 if meter.strong(x0) > 0 else 2.5
                elif iv == 6:
                    cost += 1.5
                if (q - m) * sign < 0:
                    cost += 4.0                           # on the wrong side of the melody
            if best is None or cost < best[0] - 1e-9:
                best = (cost, q)
        q = best[1] if best else _fold(int(round(target)), lo, hi)
        out.append([s, d, q])
        prev = q
    return out, pattern


# ======================================================================== the duet
def _base_name(name):
    return re.sub(r"\s*\d+$", "", name or "").strip()


def _key_number(key):
    if key.mode == "aeolian":
        return 12 + key.tonic
    return (key.tonic - FROM_MAJOR.get(key.mode, 0)) % 12


def _build(m, track, lead, second, instrument, row, key):
    """New Midi: the melody (its program / name) and the second voice (instrument row), with
    the tempo map, time and key signatures of the source."""
    import pretty_midi
    from .midi import Midi
    pm = copy.deepcopy(m.pm)
    src = pm.instruments[track]
    pm.instruments = []
    pm.lyrics = []
    if hasattr(pm, "text_events"):
        pm.text_events = []
    res = float(pm.resolution)

    def t(q):
        return pm.tick_to_time(int(round(q * res)))

    name1 = src.name or pretty_midi.program_to_instrument_name(src.program)
    name2 = row["part"]
    b1, b2 = _base_name(name1), _base_name(name2)
    if b1.lower() == b2.lower():
        name1, name2 = f"{b1} 1", f"{b2} 2"
    for name, program, line in ((name1, src.program, lead), (name2, row["program"], second)):
        ins = pretty_midi.Instrument(program=int(program), name=name)
        for s, d, p in sorted(line):
            ins.notes.append(pretty_midi.Note(80, int(p), t(s), t(s + d)))
        pm.instruments.append(ins)
    if not pm.key_signature_changes:
        pm.key_signature_changes.append(pretty_midi.KeySignature(_key_number(key), 0.0))
    out = Midi()
    out.pm = pm
    out.source = None
    out.sf2 = m.sf2
    return out


def duet_from_melody(src, mode="accompaniment", track=None, instrument=None, side="below",
                     interval="thirds", delay="auto", canon_interval="auto", strict=False,
                     allow_dissonant=False, pattern="arpeggio"):
    """A NEW Midi with two tracks: the melody of src and a second voice made for it.

    src            Midi, Score, exercise (Phrase: its own notes and key) or MIDI file path
    mode           'harmony', 'canon' or 'accompaniment' (see the module text)
    track          melody track of a MIDI (index; None = the one with the most notes)
    instrument     second voice: catalogue key ('Bb (trumpet)', 'C (trombone)'…; None = the
                   instrument chosen beside the user); its range = the user's range
    side           'below' / 'above' the melody (harmony, accompaniment)
    interval       harmony: 'thirds' or 'sixths'
    delay          canon: 'auto', 'half bar', '1 bar', '2 bars', '4 bars'
    canon_interval canon: 'auto' or a key of CANON_INTERVALS
    strict         canon: the follower is the exact melody (no note moved)
    allow_dissonant canon: make it even below MIN_CONSONANCE
    pattern        accompaniment: 'auto', 'long notes', 'half notes', 'beats', 'arpeggio'
    """
    from . import instruments as ins
    from .phrase import instrument_range
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    if side not in SIDES:
        raise ValueError(f"side must be one of {', '.join(SIDES)}")
    m, track, mel, title, given = _source(src, track)
    if len(mel) < MIN_NOTES:
        raise ValueError(f"the melody has fewer than {MIN_NOTES} notes")
    instrument = instrument or ins.current()
    if instrument not in ins.CATALOGUE:
        raise ValueError(f"unknown instrument {instrument}; known: {', '.join(ins.KEYS)}")
    row = ins.row(instrument)
    wlo, whi = instrument_range(instrument)
    T = int(row["transposition"])
    lo, hi = wlo - T, whi - T                          # concert range of the second voice
    end = max(s + d for s, d, _ in mel)
    meter = meter_of(m.pm, end + 32)                   # room for the tail of a canon
    key = key_of(mel, given)
    segs = analyse(mel, meter, key)
    chords = ChordMap(segs)
    text = chords_text(segs, meter, end)
    nbars = meter.bar_at(end - EPS) + 1
    info = dict(from_melody=True, mode=mode, version=VERSION, source=title, track=track,
                key=key_label(key), chords=text, instrument=instrument, side=side,
                bars=nbars)
    lead = [list(n) for n in mel]
    if mode == "harmony":
        second = harmony(mel, chords, meter, key, lo, hi, side, interval)
        info["interval"] = interval
        detail = f"{interval} {side}"
    elif mode == "canon":
        lead, second, extra = canon(mel, chords, meter, key, lo, hi, delay, canon_interval,
                                    strict, allow_dissonant)
        info.update(extra)
        info.pop("side")
        detail = (f"delay {extra['delay']}, {extra['canon_interval']}, "
                  f"{extra['consonance']:.0%} consonant"
                  + (f", {extra['moved']} notes moved" if extra["moved"] else ""))
    else:
        second, used = accompaniment(mel, chords, segs, meter, key, lo, hi, side, pattern)
        info["pattern"] = used
        detail = f"{used} {side}"
    out = _build(m, track, lead, second, instrument, row, key)
    out.title = f"{title} – {mode}"
    out.duet_info = info
    wrong = 0
    if mode != "canon":
        sign = -1 if side == "below" else 1
        wrong = sum(1 for (_, _, p), (_, _, q) in zip(mel, second) if (q - p) * sign < 0) \
            if mode == "harmony" else 0
    print(f"duet from a melody: {mode} ({detail}), {key_label(key)}, {nbars} bars, "
          f"second voice {ins.label(instrument)}")
    print(f"chords: {text}")
    if wrong > len(mel) // 4:
        print(f"warning: {wrong} notes of the second voice cross the melody (its range does "
              f"not fit '{side}')")
    return out
