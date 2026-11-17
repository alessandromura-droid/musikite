"""
Duet engine for two Bb trumpets, derived from duetti.py.

Version 2 (more "human" phrasing):
  1. motif: the first bar of each phrase is a motif, then restated as a
     sequence, inverted or fragmented in the following bars;
  2. periods: phrases grouped in pairs; the antecedent ends open (third or
     fifth), the consequent restates the motif and ends closed (root);
  3. contour: one arch per phrase with a single climax, and gap fill
     (after a leap the line steps back);
  4. rhythm: one rhythmic pattern per phrase, mostly repeated;
  5. the texture and the roles stay the same for a whole period (8 bars).
The harmonic / voice-leading scoring of duetti.py is unchanged: the motif
only proposes pitches, the scorer still decides.

generate_duet() returns the two lines as lists of (start, duration, midi)
in quarter notes; midi is the WRITTEN pitch for Bb trumpet (None = rest).
The Midi object converts them to concert pitch.
"""
import random

EPS = 1e-6
LOWEST, HIGHEST = 55, 79          # G3 - G5 written

# chord symbols, qualities and scales come from the theory engine (theory.py);
# the names below are kept for compatibility
from . import theory as _th
PC_EN = _th.LETTER_PC
PC_IT = _th.IT_PC
QUALITIES = _th.CHORD_TYPES                   # canonical quality -> intervals
MINOR_QUALITIES = ('m', 'm7', 'm6')           # canonical names of the old 'm', 'min', '-', '-7'
MAJOR_SCALE = _th.SCALES['ionian']
MINOR_SCALE = _th.SCALES['aeolian']
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
    """(root pitch class, canonical quality) of a chord symbol (theory.parse_chord;
    the bass of a slash chord is ignored, as before)."""
    c = _th.parse_chord(sym)
    return c.root, c.quality


def parse_progression(text, shift):
    """Return a list of bars; each bar is a list of (root, qual, beats)."""
    return [[((c.root + shift) % 12, c.quality, beats) for c, beats in bar]
            for bar in _th.parse_progression(text)]


class Ctx:
    def __init__(self, bars, kpc, minor, level, r, rep=0.7):
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
        self.rep = rep                      # 0..1: how much material is repeated/developed
        self.plan = {}                      # bar -> dict(durs, op, src) for the theme line
        self.motif = None                   # (durs, pitches) of the antecedent's first bar
        self.arc = None                     # phrase contour, see target()
        self.sec = {}                       # rhythm of the secondary lines in the phrase
        self.theme_out = None               # notes of the theme line of the last texture

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

    def target(self, s, lo, hi):
        """Arch contour of the phrase: start, single peak, end (fractions of the range)."""
        t0, t1, xp, f0, fp, f1 = self.arc
        x = min(1.0, max(0.0, (s - t0) / max(t1 - t0, EPS)))
        f = f0 + (fp - f0) * x / xp if x < xp else fp + (f1 - fp) * (x - xp) / (1 - xp)
        return lo + f * (hi - lo)


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


def bar_of(t):
    return int(t // 4 + EPS)


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


def fits(durs, split):
    """A bar rhythm can be used on a bar with two chords only if a note starts at beat 2."""
    if not split:
        return True
    t = 0.0
    for d in durs:
        if abs(t - 2) < EPS:
            return True
        t += abs(d)
    return False


def first_half(durs):
    """Durations of the first half bar, or None if a note crosses beat 2."""
    t, out = 0.0, []
    for d in durs:
        out.append(d)
        t += abs(d)
        if abs(t - 2) < EPS:
            return out
        if t > 2:
            return None
    return None


def to_events(t, durs):
    ev = []
    for d in durs:
        ev.append((t, abs(d), d < 0))
        t += abs(d)
    return ev


def make_events(ctx, bars, level=None):
    """Rhythm of a secondary line: one pattern per phrase, mostly repeated."""
    level = level or ctx.level
    keep = 0.5 + 0.4 * ctx.rep
    ev = []
    for b in bars:
        sp = ctx.split(b)
        R = ctx.sec.get(level)
        if R is None:
            R = bar_durations(level, ctx.r, sp)
            if R in ([4], [3, 1]):           # a held note repeated every bar is too static
                R = bar_durations(level, ctx.r, sp)
            durs = ctx.sec[level] = R
        elif fits(R, sp) and ctx.r.random() < keep:
            durs = R
        else:
            durs = bar_durations(level, ctx.r, sp)
        ev += to_events(4.0 * b, durs)
    return ev


def theme_events(ctx, bars):
    """Rhythm of the theme line, from the phrase plan."""
    ev = []
    for b in bars:
        pl = ctx.plan.get(b)
        durs = pl['durs'] if pl else bar_durations(ctx.level, ctx.r, ctx.split(b))
        ev += to_events(4.0 * b, durs)
    return ev


# --------------------------------------------------------------------------
# Phrase plan: motif and its development
# --------------------------------------------------------------------------
def make_plan(ctx, body, consequent, r):
    """For each body bar of a phrase: rhythm and how the pitches are derived.
    ops: free | copy (antecedent motif) | seq (sequence of the first bar)
         | inv (inverted first bar) | frag (first half of the first bar, twice)."""
    plan = {}
    if not body:
        return plan
    rep, lvl = ctx.rep, ctx.level
    b0 = body[0]
    sp0 = ctx.split(b0)
    if consequent and ctx.motif is not None and fits(ctx.motif[0], sp0) \
            and r.random() < 0.3 + 0.7 * rep:
        R = ctx.motif[0]
        plan[b0] = dict(durs=R, op='copy', src=None)
    else:
        R = bar_durations(lvl, r, sp0)
        if R == [4]:                          # a whole note is a poor motif
            R = bar_durations(lvl, r, sp0)
        plan[b0] = dict(durs=R, op='free', src=None)
    half = first_half(R)
    for i, b in enumerate(body[1:], 1):
        last = i == len(body) - 1 and len(body) > 2
        x = r.random()
        if last:
            if half and x < 0.6 * rep:
                op, durs = 'frag', half + half
            else:
                op, durs = 'free', bar_durations(lvl, r, ctx.split(b))
        else:
            if x < 0.65 * rep:
                op, durs = 'seq', R
            elif lvl >= 2 and x < 0.85 * rep:
                op, durs = 'inv', R
            elif x < 0.85 * rep + 0.15:
                op, durs = 'free', R              # same rhythm, new pitches
            else:
                op, durs = 'free', bar_durations(lvl, r, ctx.split(b))
        if not fits(durs, ctx.split(b)):
            op, durs = 'free', bar_durations(lvl, r, ctx.split(b))
        plan[b] = dict(durs=durs, op=op, src=b0)
    return plan


def proposal(ctx, out, b, j, prev):
    """Pitch suggested by the plan for the j-th event of bar b of the theme line."""
    pl = ctx.plan.get(b)
    if not pl or pl['op'] == 'free':
        return None
    if pl['op'] == 'copy':
        src = ctx.motif[1]
    else:
        src = [p for s, d, p in out if bar_of(s) == pl['src']]
    if pl['op'] == 'frag':
        n = len(first_half(pl['durs']) or [])
        if not n:
            return None
        j = j % n
    if j >= len(src):
        return None
    if j == 0:
        return src[0] if pl['op'] == 'copy' else None
    a, c = src[j - 1], src[j]
    if a is None or c is None or prev is None:
        return None
    k = ctx.steps(a, c)
    return ctx.shift(prev, -k if pl['op'] == 'inv' else k)


# --------------------------------------------------------------------------
# Melody engine
# --------------------------------------------------------------------------
def score_note(p, prev, s, others, role, ctx, target, leap_max, prop=None, last_leap=None):
    sc = 0.0
    if prev is not None:
        leap = abs(p - prev)
        if leap > leap_max:
            return None
        if leap == 0:                         # repeated notes: cheap once, then costly
            sc += 2.5 + (2.0 if last_leap == 0 else 0.0)
        elif leap <= 2:
            sc += 0.5 * leap
        elif leap <= 4:                       # thirds: normal melodic motion
            sc += 0.6 * leap
        elif leap in (5, 7):                  # fourths and fifths
            sc += 0.7 * leap + 0.5
        else:
            sc += leap + 1.0
        if leap == 6:
            sc += 5.0
        if last_leap is not None and abs(last_leap) >= 5:   # gap fill: after a leap, step back
            mv = p - prev
            if mv * last_leap > 0:
                sc += 3.0
            elif 0 < abs(mv) <= 2:
                sc -= 1.0
    if target is not None:
        sc += (0.35 if ctx.arc is not None else 0.25) * abs(p - target)
        if p > target + 4:                    # keep the climax where the contour wants it
            sc += p - target - 4
    if prop is not None:
        sc += 1.5 * abs(p - prop)
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


def pick(cands, prev, s, others, role, ctx, target, leap_max, prop=None, last_leap=None):
    best, best_s = None, None
    for p in cands:
        v = score_note(p, prev, s, others, role, ctx, target, leap_max, prop, last_leap)
        if v is not None and (best_s is None or v < best_s):
            best, best_s = p, v
    if best is None:
        best = min(cands, key=lambda p: abs(p - prev) if prev is not None else 0)
    return best


def melody(events, ctx, rng, prev, others_fn=None, role=None, nct=None,
           out=None, leap=None, theme=False):
    lo, hi = rng
    nct = ctx.cfg['nct'] if nct is None else nct
    leap = leap or ctx.cfg['leap']
    out = [] if out is None else out
    if theme:
        ctx.theme_out = out
    prev_nct = False
    target, cur_bar, j = None, None, 0
    last_leap = None
    for i, (s, d, rest) in enumerate(events):
        b = bar_of(s)
        if b != cur_bar:
            cur_bar, j = b, 0
            if ctx.arc is None:
                base = target if target is not None else (prev if prev is not None else (lo + hi) / 2)
                target = min(hi - 3, max(lo + 3, base + ctx.r.choice((-5, -3, 0, 3, 5))))
        if rest:
            out.append((s, d, None))
            j += 1
            continue
        if ctx.arc is not None:
            target = ctx.target(s, lo, hi)
        prop = proposal(ctx, out, b, j, prev) if theme else None
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
        p = pick(cands, prev, s, others, role, ctx, target, leap, prop, last_leap)
        prev_nct = p % 12 not in cset
        if prev is not None:
            last_leap = p - prev
        out.append((s, d, p))
        prev = p
        j += 1
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
    U = melody(theme_events(ctx, bars), ctx, (ulo, uhi), pu, theme=True)
    L = [(s, d, None if p is None else harm_below(ctx, p, s, kind)) for s, d, p in U]
    return U, L


def tex_melody_acc(ctx, bars, r, pu, pl):
    mel_upper = r.random() < 0.65
    mode = r.choice(['whole', 'halves', 'halves', 'quarters'] if ctx.level > 1
                    else ['whole', 'halves'])          # one accompaniment pattern per phrase
    acc_ev = []
    for b in bars:
        t0 = 4.0 * b
        if mode == 'whole' and not ctx.split(b):
            acc_ev += to_events(t0, [4])
        elif mode == 'quarters':
            acc_ev += to_events(t0, [1, 1, 1, 1])
        else:
            acc_ev += to_events(t0, [2, 2])
    if mel_upper:
        acc = melody(acc_ev, ctx, ctx.cfg['lower'], pl, nct=False, leap=5, role='lower')
        mel = melody(theme_events(ctx, bars), ctx, ctx.cfg['upper'], pu,
                     others_fn=static(acc), role='upper', theme=True)
        return mel, acc
    acc = melody(acc_ev, ctx, ctx.cfg['upper'], pu, nct=False, leap=5, role='upper')
    mel = melody(theme_events(ctx, bars), ctx, ctx.cfg['lower'], pl,
                 others_fn=static(acc), role='lower', theme=True)
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
        mel = melody(theme_events(ctx, bars), ctx, ctx.cfg['upper'], pu,
                     others_fn=static(ped), role='upper', theme=True)
        return mel, ped
    mel = melody(theme_events(ctx, bars), ctx, ctx.cfg['lower'], pl,
                 others_fn=static(ped), role='lower', theme=True)
    return ped, mel


def tex_dialogue(ctx, bars, r, pu, pl, echo=False):
    U, L = [], []
    a_upper = r.random() < 0.5
    alternate = r.random() < 0.5
    keep = 0.5 + 0.4 * ctx.rep
    a_fixed = first_half(ctx.plan[bars[0]]['durs']) if bars[0] in ctx.plan else None
    a_fixed = a_fixed or cell(ctx.level, r)           # one question rhythm per phrase
    for b in bars:
        t0 = 4.0 * b
        A, B = (U, L) if a_upper else (L, U)
        rA, rB = (ctx.cfg['upper'], ctx.cfg['lower']) if a_upper else (ctx.cfg['lower'], ctx.cfg['upper'])
        roleA, roleB = ('upper', 'lower') if a_upper else ('lower', 'upper')
        pA = last_pitch(A, pu if a_upper else pl)
        pB = last_pitch(B, pl if a_upper else pu)
        # A: active first half
        a_cell = a_fixed if r.random() < keep else cell(ctx.level, r)
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

    lead = melody(theme_events(ctx, bars), ctx, Lr, pu if lead_upper else pl,
                  others_fn=others, role='upper' if lead_upper else 'lower', theme=True)
    fol = build_follower(ctx, lead, D, start, end, Fr, offsets)
    return (lead, fol) if lead_upper else (fol, lead)


def tex_mirror(ctx, bars, r, pu, pl):
    ulo, uhi = ctx.cfg['upper']
    U = melody(theme_events(ctx, bars), ctx, (max(ulo, 62), uhi), pu, theme=True)
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
    ev_theme = theme_events(ctx, bars)
    ev_other = make_events(ctx, bars, max(1, ctx.level - 1))
    theme_upper = r.random() < 0.5
    evU, evL = (ev_theme, ev_other) if theme_upper else (ev_other, ev_theme)
    if r.random() < 0.5:
        U = melody(evU, ctx, ctx.cfg['upper'], pu, role='upper', theme=theme_upper)
        L = melody(evL, ctx, ctx.cfg['lower'], pl, others_fn=static(U), role='lower',
                   theme=not theme_upper)
    else:
        L = melody(evL, ctx, ctx.cfg['lower'], pl, role='lower', theme=not theme_upper)
        U = melody(evU, ctx, ctx.cfg['upper'], pu, others_fn=static(L), role='upper',
                   theme=theme_upper)
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
def cadence(ctx, b, r, pu, pl, kind):
    """kind: 'final' (tonic chord, held), 'closed' (upper ends on the root),
    'open' (upper ends on the third or fifth: the phrase asks for an answer)."""
    t0 = 4.0 * b
    ulo, uhi = ctx.cfg['upper']
    llo, lhi = ctx.cfg['lower']
    if kind == 'final':
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
    k = max((i for i, n in enumerate(U) if n[2] is not None), default=None)
    if k is not None:
        s, d, p = U[k]
        root, cset = ctx.chord_at(s)
        if kind == 'closed':
            cand = [x for x in range(ulo, uhi + 1) if x % 12 == root]
        else:
            cand = [x for x in chord_tones(cset, ulo, uhi) if x % 12 != root]
        ref = last_pitch(U[:k], pu if pu is not None else p)
        if cand:
            U[k] = (s, d, min(cand, key=lambda x: (abs(x - ref), x)))
    L = melody(to_events(t0, r.choice(opts)), ctx, (llo, lhi), pl, nct=False,
               others_fn=static(U), role='lower')
    return U, L


def generate(ctx, phrase_len, textures, r):
    """Phrases are grouped in periods of two (antecedent + consequent): same
    texture and roles, the consequent restates the antecedent's motif, the
    antecedent ends open, the consequent closed."""
    T1, T2, log = [], [], []
    p1 = p2 = None
    n = ctx.nbars
    phrases = [list(range(i, min(i + phrase_len, n))) for i in range(0, n, phrase_len)]
    prev_tex, prev_body = None, None
    tex, upper_t1, period_tex = None, True, None
    for k, ph in enumerate(phrases):
        final = k == len(phrases) - 1
        consequent = k % 2 == 1
        body, cad = ph[:-1], ph[-1]
        if not consequent:
            upper_t1 = r.random() < 0.7
            pool = [t for t in textures if t != period_tex] or textures
            tex = r.choice(pool)
            period_tex = tex
            ctx.motif = None
        ctx.sec = {}
        t0, t1 = 4.0 * ph[0], 4.0 * (ph[-1] + 1)
        open_end = not consequent and not final
        ctx.arc = (t0, t1, r.uniform(0.55, 0.75), 0.35, 0.85, 0.5 if open_end else 0.2)
        ctx.plan = make_plan(ctx, body, consequent, r)
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
                name = tex
                pu, pl = (p1, p2) if upper_t1 else (p2, p1)
                ctx.theme_out = None
                U, L = TEX_FN[name](ctx, body, r, pu, pl)
                if not consequent and ctx.theme_out is not None:
                    b0 = body[0]
                    ctx.motif = (ctx.plan[b0]['durs'],
                                 [p for s, d, p in ctx.theme_out if bar_of(s) == b0])
            if upper_t1:
                T1 += U
                T2 += L
            else:
                T1 += L
                T2 += U
            p1, p2 = last_pitch(T1, p1), last_pitch(T2, p2)
            prev_body = dict(sig=sig, bars=body, U=U, L=L, upper_t1=upper_t1)
        pu, pl = (p1, p2) if upper_t1 else (p2, p1)
        kind = 'final' if final else ('open' if open_end else 'closed')
        cu, cl = cadence(ctx, cad, r, pu, pl, kind)
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


def generate_duet(chords=DEFAULT_CHORDS, rounds=2, level=1, key=None, concert=False,
                  seed=None, phrase=4, textures=None, repetition=0.7):
    """One duet. Returns a dict with the two lines (written pitch), key,
    number of bars, seed and texture log.
    repetition: 0..1, how much the motif is restated and developed
    (0 = mostly free lines, 1 = strongly motivic)."""
    if level not in LEVELS:
        raise ValueError('level must be 1, 2 or 3')
    if phrase < 1 or rounds < 1:
        raise ValueError('phrase and rounds must be >= 1')
    if not 0 <= repetition <= 1:
        raise ValueError('repetition must be between 0 and 1')
    shift = 2 if concert else 0
    bars = parse_progression(chords, shift) * rounds
    if key:
        kpc, kq = split_symbol(key)
        kpc = (kpc + shift) % 12
        minor = kq in MINOR_QUALITIES
    else:
        kpc, minor = bars[0][0][0], bars[0][0][1] in MINOR_QUALITIES
    allowed = [t for t, lv in TEXTURES.items() if lv <= level]
    if textures:
        wanted = [t.strip() for t in (textures.split(',') if isinstance(textures, str) else textures)
                  if t.strip()]
        bad = [t for t in wanted if t not in TEXTURES]
        if bad:
            raise ValueError(f"Unknown texture(s): {', '.join(bad)}. Available: {', '.join(TEXTURES)}")
        allowed = wanted
    if seed is None:
        seed = random.randrange(1_000_000)
    r = random.Random(seed)
    ctx = Ctx(bars, kpc, minor, level, r, repetition)
    T1, T2, log = generate(ctx, phrase, allowed, r)
    return dict(t1=T1, t2=T2, kpc=kpc, minor=minor, nbars=len(bars), seed=seed, log=log)
