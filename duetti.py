#!/usr/bin/env python3
"""
duetti.py

Random generator of simple duets for two Bb trumpets (MIDI, via music21).
Extended version of duetto_trombe.py.

  - any chord progression (default: the one of duetto_trombe.py);
  - every phrase (default 4 bars) gets a texture chosen at random:
      thirds        parallel thirds, same rhythm
      sixths        parallel sixths, same rhythm
      melody_acc    melody against long notes (melody above or below)
      pedal         melody against a rhythmic pedal on root or fifth
      dialogue      question/answer every half bar
      echo          the second trumpet echoes the first one half a bar later
      canon_bar     free canon, second voice one bar later
      canon_half    free canon, second voice half a bar later
      mirror        contrary motion (melodic inversion)
      counterpoint  two independent lines with different rhythms
    plus "swap": a phrase over the same chords is repeated with the two
    parts exchanged;
  - roles change from phrase to phrase (sometimes trumpet 2 is on top);
  - rhythms change from bar to bar (half notes, quarters, eighths, dotted
    notes, rests) and the two parts do not need the same rhythm;
  - every phrase ends with a cadence bar.

Complexity (-l):
  1 = half and quarter notes, chord tones only, small leaps;
  2 = adds dotted rhythms, pairs of eighths, passing tones, mirror,
      counterpoint and half-bar canon;
  3 = adds runs of eighths, syncopations, larger leaps, full range.

Pitches are WRITTEN pitches for Bb trumpet, overall range G3-G5.
Chord symbols are taken as written pitch unless --concert is given.

Chord symbols: English (C D E F G A B) or Italian (Do Re Mi Fa Sol La Si),
with # or b, followed by a quality:
  (none) maj M | m min - | 7 | m7 -7 | maj7 M7 | 6 | m6 | dim | dim7 |
  m7b5 | aug + | sus4 sus | sus2
One symbol per bar; two or four chords in one bar are joined by ':'
(e.g. "C F:G C"). Slash chords (C/E) are accepted, the bass is ignored.

Run without arguments for interactive mode, or see --help.
"""
import argparse
import os
import random
import re
import sys

from music21 import stream, note, meter, instrument, tempo
from music21 import key as m21key

EPS = 1e-6
LOWEST, HIGHEST = 55, 79          # G3 - G5 written

PC_EN = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
PC_IT = {'Do': 0, 'Re': 2, 'Mi': 4, 'Fa': 5, 'Sol': 7, 'La': 9, 'Si': 11}
QUALITIES = {
    '': (0, 4, 7), 'maj': (0, 4, 7), 'M': (0, 4, 7),
    'm': (0, 3, 7), 'min': (0, 3, 7), '-': (0, 3, 7),
    '7': (0, 4, 7, 10),
    'm7': (0, 3, 7, 10), '-7': (0, 3, 7, 10),
    'maj7': (0, 4, 7, 11), 'M7': (0, 4, 7, 11),
    '6': (0, 4, 7, 9), 'm6': (0, 3, 7, 9),
    'dim': (0, 3, 6), 'dim7': (0, 3, 6, 9), 'm7b5': (0, 3, 6, 10),
    'aug': (0, 4, 8), '+': (0, 4, 8),
    'sus4': (0, 5, 7), 'sus': (0, 5, 7), 'sus2': (0, 2, 7),
}
MINOR_QUALITIES = ('m', 'min', '-', 'm7', '-7', 'm6')
ROOT_RE = re.compile(r'^(Do|Re|Mi|Fa|Sol|La|Si|[A-G])([#b]?)(.*)$')
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)
KEY_MAJOR = ['C', 'D-', 'D', 'E-', 'E', 'F', 'F#', 'G', 'A-', 'A', 'B-', 'B']
KEY_MINOR = ['c', 'c#', 'd', 'e-', 'e', 'f', 'f#', 'g', 'g#', 'a', 'b-', 'b']

DEFAULT_CHORDS = 'C F G G C F G C'

LEVELS = {
    1: dict(upper=(60, 76), lower=(55, 72), leap=5, nct=False),
    2: dict(upper=(60, 77), lower=(55, 74), leap=7, nct=True),
    3: dict(upper=(60, 79), lower=(55, 76), leap=9, nct=True),
}

# half-bar rhythmic cells (beats); a negative value is a rest
CELLS = {
    1: [[2], [1, 1]],
    2: [[1.5, 0.5], [0.5, 0.5, 1], [1, 0.5, 0.5], [1, -1]],
    3: [[0.5, 0.5, 0.5, 0.5], [0.5, 1, 0.5], [-0.5, 0.5, 1], [1, -0.5, 0.5]],
}
PEDAL_CELLS = {
    1: [[2], [1, 1]],
    2: [[1.5, 0.5], [1, 0.5, 0.5]],
    3: [[0.5, 0.5, 1], [0.5, 0.5, 0.5, 0.5]],
}
CADENCE_RHYTHMS = [[2, 2], [4], [1, 1, 2], [2, -2], [3, -1]]

TEXTURES = {          # name: minimum complexity
    'thirds': 1, 'sixths': 1, 'melody_acc': 1, 'pedal': 1,
    'dialogue': 1, 'echo': 1, 'canon_bar': 1,
    'canon_half': 2, 'mirror': 2, 'counterpoint': 2,
}
DISSONANT = (1, 2, 10, 11)


# --------------------------------------------------------------------------
# Harmony
# --------------------------------------------------------------------------
def split_symbol(sym):
    m = ROOT_RE.match(sym.split('/')[0])
    if not m:
        sys.exit(f"Cannot parse chord '{sym}'")
    name, acc, qual = m.groups()
    pc = PC_IT.get(name, PC_EN.get(name)) + {'#': 1, 'b': -1, '': 0}[acc]
    if qual not in QUALITIES:
        sys.exit(f"Unknown chord quality '{qual}' in '{sym}'")
    return pc, qual


def parse_progression(text, shift):
    """Return a list of bars; each bar is a list of (root, qual, beats)."""
    bars = []
    for tok in re.split(r'[\s,|]+', text.strip()):
        if not tok:
            continue
        parts = tok.split(':')
        if len(parts) not in (1, 2, 4):
            sys.exit(f"'{tok}': a bar can hold 1, 2 or 4 chords")
        bar = []
        for sym in parts:
            pc, qual = split_symbol(sym)
            bar.append(((pc + shift) % 12, qual, 4 / len(parts)))
        bars.append(bar)
    if not bars:
        sys.exit('Empty chord progression')
    return bars


class Ctx:
    def __init__(self, bars, kpc, minor, level, r):
        self.seg = []                       # (start, end, root, chord pc set)
        for b, bar in enumerate(bars):
            t = 4.0 * b
            for root, qual, beats in bar:
                cset = frozenset((root + i) % 12 for i in QUALITIES[qual])
                self.seg.append((t, t + beats, root, cset))
                t += beats
        self.nbars = len(bars)
        self.kpc, self.minor = kpc, minor
        self.scale_set = {(kpc + i) % 12 for i in (MINOR_SCALE if minor else MAJOR_SCALE)}
        self.scale = [p for p in range(36, 104) if p % 12 in self.scale_set]
        self.level = level
        self.cfg = LEVELS[level]
        self.r = r

    def chord_at(self, t):
        for s, e, root, cset in self.seg:
            if s - EPS <= t < e - EPS:
                return root, cset
        return self.seg[-1][2], self.seg[-1][3]

    def split(self, b):
        return any(4 * b + EPS < s < 4 * b + 4 - EPS for s, _, _, _ in self.seg)

    def body_signature(self, bars):
        t0 = 4 * bars[0]
        t1 = 4 * (bars[-1] + 1)
        return tuple((s - t0, e - t0, root, cset) for s, e, root, cset in self.seg
                     if t0 - EPS <= s < t1 - EPS)

    def nct(self, cset):
        """Scale tones usable as passing/neighbour tones over a chord."""
        out = set()
        for pc in self.scale_set - cset:
            if not any(((pc + d) % 12 in cset) and ((pc + d) % 12 not in self.scale_set)
                       for d in (-1, 1)):
                out.add(pc)
        return out

    def idx(self, p):
        return min(range(len(self.scale)), key=lambda i: abs(self.scale[i] - p))

    def shift(self, p, k):
        i = max(0, min(len(self.scale) - 1, self.idx(p) + k))
        return self.scale[i]

    def steps(self, a, b):
        return self.idx(b) - self.idx(a)


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------
def is_strong(t):
    pos = t % 4
    return abs(pos - round(pos)) < EPS and int(round(pos)) % 2 == 0


def overlapping(notes, s, d):
    return [(st, q) for st, du, q in notes
            if q is not None and st < s + d - EPS and st + du > s + EPS]


def static(notes):
    return lambda s, d, out: overlapping(notes, s, d)


def last_pitch(notes, default):
    for _, _, p in reversed(notes):
        if p is not None:
            return p
    return default


def fold(q, lo, hi):
    while q > hi:
        q -= 12
    while q < lo:
        q += 12
    return q if q <= hi else None


def chord_tones(cset, lo, hi):
    return [p for p in range(lo, hi + 1) if p % 12 in cset]


def cell(level, r):
    # cells of the current level are the most likely, simpler ones still appear
    lv = r.choices(range(1, level + 1), weights=range(1, level + 1))[0]
    return list(r.choice(CELLS[lv]))


def bar_durations(level, r, split):
    x = r.random()
    if not split and x < 0.10:
        return [4]
    if not split and level >= 2 and x < 0.18:
        return [3, 1]
    return cell(level, r) + cell(level, r)


def to_events(t, durs):
    ev = []
    for d in durs:
        ev.append((t, abs(d), d < 0))
        t += abs(d)
    return ev


def make_events(ctx, bars, level=None):
    level = level or ctx.level
    ev = []
    for b in bars:
        ev += to_events(4.0 * b, bar_durations(level, ctx.r, ctx.split(b)))
    return ev


# --------------------------------------------------------------------------
# Melody engine
# --------------------------------------------------------------------------
def score_note(p, prev, s, others, role, ctx, target, leap_max):
    sc = 0.0
    if prev is not None:
        leap = abs(p - prev)
        if leap > leap_max:
            return None
        sc += 0.5 * leap if leap <= 2 else leap + 1.0
        if leap == 0:
            sc += 1.5
        if leap == 6:
            sc += 5.0
    if target is not None:
        sc += 0.25 * abs(p - target)
    for st, q in others:
        iv = abs(p - q) % 12
        if p == q:
            sc += 3.0
        elif iv in DISSONANT:
            sc += 8.0 if is_strong(max(st, s)) else 2.5
        elif iv == 6:
            sc += 2.5
        if role == 'upper' and p < q:
            sc += 4.0
        if role == 'lower' and p > q:
            sc += 4.0
    return sc + 1.5 * ctx.r.random()


def pick(cands, prev, s, others, role, ctx, target, leap_max):
    best, best_s = None, None
    for p in cands:
        v = score_note(p, prev, s, others, role, ctx, target, leap_max)
        if v is not None and (best_s is None or v < best_s):
            best, best_s = p, v
    if best is None:
        best = min(cands, key=lambda p: abs(p - prev) if prev is not None else 0)
    return best


def melody(events, ctx, rng, prev, others_fn=None, role=None, nct=None,
           out=None, leap=None):
    lo, hi = rng
    nct = ctx.cfg['nct'] if nct is None else nct
    leap = leap or ctx.cfg['leap']
    out = [] if out is None else out
    prev_nct = False
    target, cur_bar = None, None
    for i, (s, d, rest) in enumerate(events):
        if rest:
            out.append((s, d, None))
            continue
        b = int(s // 4 + EPS)
        if b != cur_bar:
            cur_bar = b
            base = target if target is not None else (prev if prev is not None else (lo + hi) / 2)
            target = min(hi - 3, max(lo + 3, base + ctx.r.choice((-5, -3, 0, 3, 5))))
        _, cset = ctx.chord_at(s)
        ct = chord_tones(cset, lo, hi)
        if prev_nct and prev is not None:
            cands = [p for p in ct if 1 <= abs(p - prev) <= 2] or ct
        else:
            cands = list(ct)
            if (nct and prev is not None and not is_strong(s) and i + 1 < len(events)
                    and not events[i + 1][2] and ctx.chord_at(events[i + 1][0])[1] == cset):
                ns = ctx.nct(cset)
                cands += [p for p in range(lo, hi + 1)
                          if p % 12 in ns and 1 <= abs(p - prev) <= 2]
        others = others_fn(s, d, out) if others_fn else []
        p = pick(cands, prev, s, others, role, ctx, target, leap)
        prev_nct = p % 12 not in cset
        out.append((s, d, p))
        prev = p
    return out


def consonant_snap(ctx, q, s, p_other, lo, hi, below=True):
    """Nearest chord tone to q, consonant with p_other, preferably below it."""
    _, cset = ctx.chord_at(s)
    ct = [x for x in chord_tones(cset, lo, hi)
          if x != p_other and abs(x - p_other) % 12 not in DISSONANT]
    if not ct:
        ct = chord_tones(cset, lo, hi)
    side = (lambda x: x > p_other) if below else (lambda x: x < p_other)
    return min(ct, key=lambda x: abs(x - q) + (4 if side(x) else 0))


# --------------------------------------------------------------------------
# Textures: each returns (upper_line, lower_line) for the given bars
# --------------------------------------------------------------------------
def harm_below(ctx, p, s, kind):
    lo, hi = ctx.cfg['lower']
    _, cset = ctx.chord_at(s)
    first = (3, 4) if kind == 'thirds' else (8, 9)
    second = (8, 9) if kind == 'thirds' else (3, 4)
    if is_strong(s) or p % 12 in cset:
        for ivs in (first, second, (7, 12)):
            c = [p - i for i in ivs if lo <= p - i <= hi and (p - i) % 12 in cset]
            if c:
                return c[0]
    for k in ((-2, -5) if kind == 'thirds' else (-5, -2)):
        q = ctx.shift(p, k)
        if lo <= q <= hi:
            return q
    return consonant_snap(ctx, p - 4, s, p, lo, hi)


def tex_parallel(ctx, bars, r, pu, pl, kind):
    ulo, uhi = ctx.cfg['upper']
    ulo = max(ulo, ctx.cfg['lower'][0] + (9 if kind == 'sixths' else 4))
    U = melody(make_events(ctx, bars), ctx, (ulo, uhi), pu)
    L = [(s, d, None if p is None else harm_below(ctx, p, s, kind)) for s, d, p in U]
    return U, L


def tex_melody_acc(ctx, bars, r, pu, pl):
    mel_upper = r.random() < 0.65
    acc_ev = []
    for b in bars:
        t0 = 4.0 * b
        mode = r.choice(['whole', 'halves', 'halves', 'quarters'] if ctx.level > 1
                        else ['whole', 'halves'])
        if mode == 'whole' and not ctx.split(b):
            acc_ev += to_events(t0, [4])
        elif mode == 'quarters':
            acc_ev += to_events(t0, [1, 1, 1, 1])
        else:
            acc_ev += to_events(t0, [2, 2])
    if mel_upper:
        acc = melody(acc_ev, ctx, ctx.cfg['lower'], pl, nct=False, leap=5, role='lower')
        mel = melody(make_events(ctx, bars), ctx, ctx.cfg['upper'], pu,
                     others_fn=static(acc), role='upper')
        return mel, acc
    acc = melody(acc_ev, ctx, ctx.cfg['upper'], pu, nct=False, leap=5, role='upper')
    mel = melody(make_events(ctx, bars), ctx, ctx.cfg['lower'], pl,
                 others_fn=static(acc), role='lower')
    return acc, mel


def tex_pedal(ctx, bars, r, pu, pl):
    ped_lower = r.random() < 0.75
    pcell = list(r.choice(PEDAL_CELLS[r.randint(1, ctx.level)]))
    degree = r.choice((0, 7))
    lo, hi = ctx.cfg['lower'] if ped_lower else ctx.cfg['upper']
    prev = pl if ped_lower else pu
    ped = []
    for b in bars:
        for h in (0, 2):
            t = 4.0 * b + h
            root, cset = ctx.chord_at(t)
            pc = (root + degree) % 12
            if pc not in cset:
                pc = root
            cand = [p for p in range(lo, hi + 1) if p % 12 == pc]
            ref = prev if prev is not None else (lo + hi) / 2
            q = min(cand, key=lambda p: abs(p - ref))
            for d in pcell:
                ped.append((t, d, q))
                t += d
            prev = q
    if ped_lower:
        mel = melody(make_events(ctx, bars), ctx, ctx.cfg['upper'], pu,
                     others_fn=static(ped), role='upper')
        return mel, ped
    mel = melody(make_events(ctx, bars), ctx, ctx.cfg['lower'], pl,
                 others_fn=static(ped), role='lower')
    return ped, mel


def tex_dialogue(ctx, bars, r, pu, pl, echo=False):
    U, L = [], []
    a_upper = r.random() < 0.5
    alternate = r.random() < 0.5
    for b in bars:
        t0 = 4.0 * b
        A, B = (U, L) if a_upper else (L, U)
        rA, rB = (ctx.cfg['upper'], ctx.cfg['lower']) if a_upper else (ctx.cfg['lower'], ctx.cfg['upper'])
        roleA, roleB = ('upper', 'lower') if a_upper else ('lower', 'upper')
        pA = last_pitch(A, pu if a_upper else pl)
        pB = last_pitch(B, pl if a_upper else pu)
        # A: active first half
        a_cell = cell(ctx.level, r)
        melody(to_events(t0, a_cell), ctx, rA, pA, others_fn=static(B), role=roleA, out=A)
        # B: rest or hold during A
        if r.random() < 0.5:
            B.append((t0, 2.0, None))
        else:
            melody(to_events(t0, [2]), ctx, rB, pB, others_fn=static(A), role=roleB,
                   nct=False, out=B)
        # B: answer (or echo) in the second half
        if echo and not ctx.split(b):
            lo, hi = rB
            for s, d, p in [n for n in A if t0 - EPS <= n[0] < t0 + 2 - EPS]:
                q = None if p is None else fold(p, lo, hi)
                if p is not None and q is None:
                    q = consonant_snap(ctx, p, s + 2, -100, lo, hi)
                B.append((s + 2, d, q))
        else:
            b_cell = a_cell if r.random() < 0.5 else cell(ctx.level, r)
            melody(to_events(t0 + 2, b_cell), ctx, rB, last_pitch(B, pB),
                   others_fn=static(A), role=roleB, out=B)
        # A: rest or hold during B
        if r.random() < 0.5:
            A.append((t0 + 2, 2.0, None))
        else:
            melody(to_events(t0 + 2, [2]), ctx, rA, last_pitch(A, pA),
                   others_fn=static(B), role=roleA, nct=False, out=A)
        if alternate:
            a_upper = not a_upper
    return U, L


def build_follower(ctx, lead, D, start, end, rng, offsets):
    lo, hi = rng
    if D >= end - start - EPS:
        return [(start, end - start, None)]
    f = [(start, float(D), None)]
    pL = pF = None
    for s, d, p in lead:
        ns = s + D
        if ns >= end - EPS:
            break
        nd = min(d, end - ns)
        if p is None:
            f.append((ns, nd, None))
            continue
        _, cset = ctx.chord_at(ns)
        if pF is None:
            q = next((p + o for o in offsets if lo <= p + o <= hi), p)
        else:
            q = ctx.shift(pF, ctx.steps(pL, p))
        if (is_strong(ns) or q % 12 not in ctx.scale_set) and q % 12 not in cset:
            q = min(chord_tones(cset, lo, hi), key=lambda x: (abs(x - q), x))
        fq = fold(q, lo, hi)
        if fq is None:
            fq = min(chord_tones(cset, lo, hi), key=lambda x: abs(x - q))
        f.append((ns, nd, fq))
        pL, pF = p, fq
    return f


def tex_canon(ctx, bars, r, pu, pl, D):
    lead_upper = r.random() < 0.5
    start, end = 4.0 * bars[0], 4.0 * (bars[-1] + 1)
    Lr, Fr = (ctx.cfg['upper'], ctx.cfg['lower']) if lead_upper else (ctx.cfg['lower'], ctx.cfg['upper'])
    offsets = [0, -5, -7, -12] if lead_upper else [0, 5, 7, 12]
    r.shuffle(offsets)

    def others(s, d, out):
        return overlapping(build_follower(ctx, out, D, start, end, Fr, offsets), s, d)

    lead = melody(make_events(ctx, bars), ctx, Lr, pu if lead_upper else pl,
                  others_fn=others, role='upper' if lead_upper else 'lower')
    fol = build_follower(ctx, lead, D, start, end, Fr, offsets)
    return (lead, fol) if lead_upper else (fol, lead)


def tex_mirror(ctx, bars, r, pu, pl):
    ulo, uhi = ctx.cfg['upper']
    U = melody(make_events(ctx, bars), ctx, (max(ulo, 62), uhi), pu)
    lo, hi = ctx.cfg['lower']
    L = []
    pU = pLw = None
    for s, d, p in U:
        if p is None:
            L.append((s, d, None))
            continue
        _, cset = ctx.chord_at(s)
        if pLw is None:
            q = consonant_snap(ctx, p - 8, s, p, lo, hi)
        else:
            q = fold(ctx.shift(pLw, -ctx.steps(pU, p)), lo, hi)
            if (q is None or (is_strong(s) and q % 12 not in cset)
                    or abs(q - p) % 12 in DISSONANT or q == p):
                q = consonant_snap(ctx, q if q is not None else pLw, s, p, lo, hi)
        L.append((s, d, q))
        pU, pLw = p, q
    return U, L


def tex_counterpoint(ctx, bars, r, pu, pl):
    evU = make_events(ctx, bars)
    evL = make_events(ctx, bars, max(1, ctx.level - 1))
    if r.random() < 0.5:
        evU, evL = evL, evU
    if r.random() < 0.5:
        U = melody(evU, ctx, ctx.cfg['upper'], pu, role='upper')
        L = melody(evL, ctx, ctx.cfg['lower'], pl, others_fn=static(U), role='lower')
    else:
        L = melody(evL, ctx, ctx.cfg['lower'], pl, role='lower')
        U = melody(evU, ctx, ctx.cfg['upper'], pu, others_fn=static(L), role='upper')
    return U, L


TEX_FN = {
    'thirds': lambda c, b, r, u, l: tex_parallel(c, b, r, u, l, 'thirds'),
    'sixths': lambda c, b, r, u, l: tex_parallel(c, b, r, u, l, 'sixths'),
    'melody_acc': tex_melody_acc,
    'pedal': tex_pedal,
    'dialogue': lambda c, b, r, u, l: tex_dialogue(c, b, r, u, l, echo=False),
    'echo': lambda c, b, r, u, l: tex_dialogue(c, b, r, u, l, echo=True),
    'canon_bar': lambda c, b, r, u, l: tex_canon(c, b, r, u, l, 4),
    'canon_half': lambda c, b, r, u, l: tex_canon(c, b, r, u, l, 2),
    'mirror': tex_mirror,
    'counterpoint': tex_counterpoint,
}


# --------------------------------------------------------------------------
# Cadences and form
# --------------------------------------------------------------------------
def cadence(ctx, b, r, pu, pl, final):
    t0 = 4.0 * b
    ulo, uhi = ctx.cfg['upper']
    llo, lhi = ctx.cfg['lower']
    if final:
        U, L = [], []
        for s, d, _ in to_events(t0, [2, 2] if ctx.split(b) else [4]):
            root, cset = ctx.chord_at(s)
            lq = min([p for p in range(llo, lhi + 1) if p % 12 == root],
                     key=lambda p: abs(p - (pl if pl is not None else 60)))
            good = (3, 4, 7, 8, 9, 12, 15, 16)
            uq = min([p for p in chord_tones(cset, ulo, uhi) if p > lq] or chord_tones(cset, ulo, uhi),
                     key=lambda p: abs(p - (pu if pu is not None else 67))
                     + (0 if (p - lq) in good else 10))
            U.append((s, d, uq))
            L.append((s, d, lq))
            pu, pl = uq, lq
        return U, L
    opts = [o for o in CADENCE_RHYTHMS if not (ctx.split(b) and (4 in o or 3 in o))]
    if ctx.level == 1:
        opts = [o for o in opts if 3 not in o]
    U = melody(to_events(t0, r.choice(opts)), ctx, (ulo, uhi), pu, nct=False, role='upper')
    L = melody(to_events(t0, r.choice(opts)), ctx, (llo, lhi), pl, nct=False,
               others_fn=static(U), role='lower')
    return U, L


def generate(ctx, phrase_len, textures, r):
    T1, T2, log = [], [], []
    p1 = p2 = None
    n = ctx.nbars
    phrases = [list(range(i, min(i + phrase_len, n))) for i in range(0, n, phrase_len)]
    prev_tex, prev_body = None, None
    for k, ph in enumerate(phrases):
        final = k == len(phrases) - 1
        body, cad = ph[:-1], ph[-1]
        upper_t1 = r.random() < 0.7
        name = '-'
        if body:
            sig = ctx.body_signature(body)
            if (prev_body is not None and prev_body['sig'] == sig
                    and prev_tex != 'swap' and r.random() < 0.4):
                sh = 4.0 * (body[0] - prev_body['bars'][0])
                U = [(s + sh, d, p) for s, d, p in prev_body['U']]
                L = [(s + sh, d, p) for s, d, p in prev_body['L']]
                upper_t1 = not prev_body['upper_t1']
                name = 'swap'
            else:
                pool = [t for t in textures if t != prev_tex] or textures
                name = r.choice(pool)
                pu, pl = (p1, p2) if upper_t1 else (p2, p1)
                U, L = TEX_FN[name](ctx, body, r, pu, pl)
            if upper_t1:
                T1 += U
                T2 += L
            else:
                T1 += L
                T2 += U
            p1, p2 = last_pitch(T1, p1), last_pitch(T2, p2)
            prev_body = dict(sig=sig, bars=body, U=U, L=L, upper_t1=upper_t1)
        pu, pl = (p1, p2) if upper_t1 else (p2, p1)
        cu, cl = cadence(ctx, cad, r, pu, pl, final)
        if upper_t1:
            T1 += cu
            T2 += cl
        else:
            T1 += cl
            T2 += cu
        p1, p2 = last_pitch(T1, p1), last_pitch(T2, p2)
        log.append(name + ('' if upper_t1 else '*'))
        prev_tex = name
    return T1, T2, log


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def make_part(notes, name, kpc, minor, bpm):
    p = stream.Part(id=name)
    p.partName = name
    p.insert(0, instrument.Trumpet())
    p.insert(0, meter.TimeSignature('4/4'))
    p.insert(0, m21key.Key(KEY_MINOR[kpc] if minor else KEY_MAJOR[kpc]))
    if bpm:
        p.insert(0, tempo.MetronomeMark(number=bpm))
    for s, d, q in notes:
        if q is None:
            n = note.Rest(quarterLength=d)
        else:
            n = note.Note(quarterLength=d)
            n.pitch.midi = q
        p.insert(s, n)
    return p


def write_duet(path, T1, T2, kpc, minor, bpm):
    score = stream.Score()
    score.insert(0, make_part(T1, 'Tromba 1', kpc, minor, bpm))
    score.insert(0, make_part(T2, 'Tromba 2', kpc, minor, bpm))
    score.write('midi', fp=path)


def run(chords, rounds, level, number, out, key_sym, concert, seed, bpm,
        phrase_len, textures):
    shift = 2 if concert else 0
    bars = parse_progression(chords, shift) * rounds
    if key_sym:
        kpc, kq = split_symbol(key_sym)
        kpc = (kpc + shift) % 12
        minor = kq in MINOR_QUALITIES
    else:
        kpc, minor = bars[0][0][0], bars[0][0][1] in MINOR_QUALITIES
    allowed = [t for t, lv in TEXTURES.items() if lv <= level]
    if textures:
        wanted = [t.strip() for t in textures.split(',') if t.strip()]
        bad = [t for t in wanted if t not in TEXTURES]
        if bad:
            sys.exit(f"Unknown texture(s): {', '.join(bad)}. Available: {', '.join(TEXTURES)}")
        allowed = wanted
    master = random.Random(seed)
    stem, ext = os.path.splitext(out)
    ext = ext or '.mid'
    for i in range(number):
        s = master.randrange(1_000_000)
        r = random.Random(s)
        ctx = Ctx(bars, kpc, minor, level, r)
        T1, T2, log = generate(ctx, phrase_len, allowed, r)
        path = f'{stem}{ext}' if number == 1 else f'{stem}_{i + 1:03d}{ext}'
        write_duet(path, T1, T2, kpc, minor, bpm)
        print(f'{path}  level {level}  seed {s}  {len(bars)} bars:  {" | ".join(log)}')
    print('(* = trumpet 2 on top)')


def main():
    if len(sys.argv) == 1:
        print('--- DUETS FOR TWO TRUMPETS ---')
        chords = input(f'Chords (default "{DEFAULT_CHORDS}"): ').strip() or DEFAULT_CHORDS
        level = int(input('Complexity 1-3 (default 1): ').strip() or '1')
        rounds = int(input('How many times the progression (default 2): ').strip() or '2')
        number = int(input('How many duets (default 1): ').strip() or '1')
        out = input("File name (default 'duetto.mid'): ").strip() or 'duetto.mid'
        if level not in LEVELS:
            sys.exit('Complexity must be 1, 2 or 3')
        run(chords, rounds, level, number, out, None, False, None, None, 4, None)
        return

    ap = argparse.ArgumentParser(
        description='Random simple duets for two Bb trumpets (MIDI, written pitch).',
        epilog='Textures: ' + ', '.join(f'{t} (>= {lv})' for t, lv in TEXTURES.items()))
    ap.add_argument('-c', '--chords', default=DEFAULT_CHORDS,
                    help=f'chord progression, one chord per bar, "F:G" = two chords in a bar '
                         f'(default "{DEFAULT_CHORDS}")')
    ap.add_argument('-g', '--rounds', type=int, default=2,
                    help='times the progression is repeated (default 2)')
    ap.add_argument('-l', '--level', type=int, default=1, choices=(1, 2, 3),
                    help='complexity 1-3 (default 1)')
    ap.add_argument('-n', '--number', type=int, default=1,
                    help='number of duets to generate (default 1)')
    ap.add_argument('-o', '--out', default='duetto.mid',
                    help='output file; with -n > 1 a number is appended (default duetto.mid)')
    ap.add_argument('-k', '--key', help='key, e.g. C or Am (default: first chord)')
    ap.add_argument('--concert', action='store_true',
                    help='chords/key given in concert pitch (transposed up a tone)')
    ap.add_argument('-s', '--seed', type=int, help='master random seed')
    ap.add_argument('-t', '--bpm', type=float, help='tempo (default: none written)')
    ap.add_argument('-f', '--phrase', type=int, default=4,
                    help='bars per phrase, last one is the cadence (default 4)')
    ap.add_argument('-x', '--textures',
                    help='comma-separated list of textures to use (default: all allowed by level)')
    a = ap.parse_args()
    if a.phrase < 1 or a.rounds < 1 or a.number < 1:
        sys.exit('--phrase, --rounds and --number must be >= 1')
    run(a.chords, a.rounds, a.level, a.number, a.out, a.key, a.concert, a.seed,
        a.bpm, a.phrase, a.textures)


if __name__ == '__main__':
    main()
