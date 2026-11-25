"""
MELODY ENGINES (owner, 2026-11-24: "make these melodies more beautiful"; "not a generator
based on a library"). Rule-based, from the literature (docs/credits.md):
 - Povel, "Melody Generator: a device for algorithmic music construction" (2010): metre
   and key, harmony (Piston's table of usual root progressions, cadence formulas), a
   SKELETON of chord tones on the strong beats, then its ELABORATION (passing and
   neighbour tones, always resolved by step);
 - Caplin, Classical Form (1998): the SENTENCE (basic idea, its repetition, continuation
   with fragmentation, cadence) and the PERIOD (antecedent ending on a half cadence,
   consequent restating the basic idea and ending on a perfect cadence);
 - Temperley, "A probabilistic model of melody perception" (2008): every note drawn from
   range x proximity x key profile;
 - Sprockeels et al., FuxCP (2023): hard rules + costs, the solution of lowest cost.

The PLAN is the same for every engine: form (`melody_form` / `phrase_form`), harmony
(`melody_harmony`, or the chords given: `harmony_from_chords`), rhythm (`rhythms`); the
ENGINE only chooses the pitches:
  'skeleton'       Povel: chord tones on the strong beats first (Viterbi along a contour
                   and a line that descends to the cadence), then the weak beats filled
                   (beam search: chord tones, passing and neighbour tones);
  'probabilistic'  Temperley: note by note, range x proximity x key profile, chord tones
                   favoured on the strong beats;
  'degrees'        a Markov chain on SCALE DEGREES written from common-practice tendencies
                   (no corpus): leading tone -> tonic, 4 -> 3, 6 -> 5, steps before leaps.
Where the form repeats material (repetition of the basic idea, consequent, fragments)
the notes are COPIED, moved by scale steps to fit the harmony. GENERATE AND TEST: several
melodies, the one with the lowest cost (one of the best two at random).
Every rule is a hard constraint or a cost: leaps within the level's limit, a leap of a
fourth or more followed by a step the other way, no augmented second, a non-chord tone
approached and left by step (weak beats; appoggiaturas from level 7), no chromatic note
below level 6 (then only lower chromatic neighbours).

Pitches are MIDI numbers in the caller's space (concert for the melodies, written for
the trumpet duets). No Qt, no music21 (Android).

    notes = melody(bars=16, ts=(4, 4), tonic=0, mode="ionian", lo=60, hi=79, level=4,
                   engine="skeleton", seed=1)       # [[start q, dur q, pitch]]
"""
import bisect
import math
import random

from .theory import SCALES

EPS = 1e-6
ENGINES = ("skeleton", "probabilistic", "degrees")
ENGINE_LABELS = {"skeleton": "Skeleton and elaboration (Povel)",
                 "probabilistic": "Probabilistic (Temperley)",
                 "degrees": "Scale degrees (Markov)"}
TIMES = ("4/4", "3/4", "2/4", "6/8")
STRONG = {(4, 4): (0.0, 2.0), (3, 4): (0.0,), (2, 4): (0.0,), (6, 8): (0.0, 1.5)}
TRIES = 4                        # melodies made for every result (generate and test)

# melodic interval cost (semitones 0..12): steps cheapest, tritone and sevenths dear
ICOST = (1.2, .3, .4, .9, 1.0, 1.6, 6.0, 2.0, 3.0, 3.2, 5.0, 6.0, 3.0)

# key profiles by scale degree (Temperley's model; values approximated from the
# common-practice distributions: tonic, third and fifth highest)
PROFILE = {"ionian": (.20, .12, .17, .09, .20, .11, .08),
           "aeolian": (.20, .12, .17, .10, .19, .11, .08)}
CHROMATIC_WEIGHT = .01

# Markov chain on scale degrees (engine 'degrees'): weight of a move of k scale steps
MOVE_W = {0: .5, 1: 4.0, 2: 2.2, 3: 1.1, 4: .8, 5: .35, 6: .1, 7: .5}
# tendencies (degree 0-6, move in scale steps) -> factor
TENDENCY = {(6, 1): 5.0, (6, -1): .5, (3, -1): 2.5, (5, -1): 1.8, (1, -1): 2.0, (1, 1): 1.2,
            (0, 0): .6, (4, 3): 1.5, (4, -4): 1.5}

# Piston's table of usual root progressions (degree -> {next: weight}); 0 = I / i
WALK = {
    "ionian": {0: {3: .3, 4: .3, 5: .2, 1: .1, 2: .1}, 1: {4: .75, 5: .15, 3: .1},
               2: {5: .6, 3: .3, 1: .1}, 3: {4: .45, 0: .25, 1: .2, 5: .1},
               4: {0: .7, 5: .2, 3: .1}, 5: {1: .4, 3: .4, 4: .1, 2: .1}, 6: {0: 1.0}},
    "aeolian": {0: {3: .35, 4: .25, 5: .2, 2: .1, 6: .1}, 1: {4: .85, 5: .15},
                2: {5: .5, 3: .4, 1: .1}, 3: {4: .5, 0: .2, 1: .15, 6: .15},
                4: {0: .7, 5: .3}, 5: {1: .3, 3: .45, 4: .15, 2: .1}, 6: {2: .8, 0: .2}},
}
PRIMARY = (0, 3, 4)
# basic idea (two bars), cadential formulas (bar before the cadence)
BI = (((0,), (0,)), ((0,), (4,)), ((0,), (3,)), ((0,), (5,)), ((0,), (3, 4)), ((0, 5), (3, 4)))
BI_PRIMARY = (((0,), (0,)), ((0,), (4,)), ((0,), (3,)), ((0,), (3, 4)))
PRE_PAC = ((1, 4), (3, 4), (4,))
PRE_PAC_PRIMARY = ((3, 4), (4,))
PRE_HC = ((3,), (1,), (0, 3), (5, 1), (0, 1))
PRE_HC_PRIMARY = ((3,), (0, 3))
DOMINANT_VERSION = {0: 4, 3: 0, 4: 0, 5: 1, 1: 4, 2: 5, 6: 2}

# rhythmic units: (minimum level, beats, durations in quarters (negative = rest), weight)
SIMPLE_UNITS = (
    (0, 4, (4.0,), .4), (0, 3, (3.0,), .5), (0, 2, (2.0,), 1.2), (0, 1, (1.0,), 2.0),
    (2, 1, (.5, .5), 2.0), (3, 2, (1.5, .5), 1.2), (4, 1, (-.5, .5), .5),
    (5, 1, (.75, .25), 1.0), (5, 1, (.5, .25, .25), 1.0), (5, 1, (.25, .25, .5), 1.0),
    (6, 1, (.25, .25, .25, .25), .9), (7, 2, (.5, 1.0, .5), .7),
    (7, 1, (1 / 3, 1 / 3, 1 / 3), .6), (8, 1, (.25, .5, .25), .6))
COMPOUND_UNITS = (                     # beat = dotted quarter
    (0, 2, (3.0,), .6), (0, 1, (1.5,), 2.0), (1, 1, (1.0, .5), 2.0), (2, 1, (.5, .5, .5), 2.0),
    (4, 1, (-.5, .5, .5), .5), (5, 1, (.75, .25, .5), 1.0), (6, 1, (.5, .25, .25, .5), .9),
    (7, 1, (.25,) * 6, .7))


# ---------------------------------------------------------------- level, metre, key
def params(level):
    """Difficulty 0-10 -> the rules of the melody (constructed, not filtered)."""
    L = max(0, min(10, int(round(float(level)))))
    return dict(
        level=L,
        leap=(5, 5, 7, 7, 8, 9, 9, 12, 12, 12, 12)[L],
        width=(9, 10, 12, 12, 14, 15, 17, 19, 21, 24, 24)[L],
        neighbours=L >= 2,
        chromatic=L >= 6,
        appoggiatura=L >= 7,
        primaries=L <= 2,
        two_chords=(0, 0, 0, 0, .1, .15, .25, .3, .35, .4, .4)[L],
        sevenths=L >= 4,
        prox=(2.0, 2.0, 2.3, 2.5, 2.8, 3.0, 3.3, 3.6, 4.0, 4.2, 4.5)[L],
    )


def parse_ts(ts):
    if isinstance(ts, str):
        a, b = ts.split("/")
        ts = (int(a), int(b))
    ts = (int(ts[0]), int(ts[1]))
    if ts not in STRONG:
        raise ValueError(f"time signature must be one of {', '.join(TIMES)}")
    return ts


def bar_q(ts):
    return ts[0] * 4.0 / ts[1]


def split_at(ts):
    """Where the second chord of a bar with two chords starts (quarters)."""
    return {(4, 4): 2.0, (3, 4): 2.0, (2, 4): 1.0, (6, 8): 1.5}[ts]


class Key:
    def __init__(self, tonic, mode="ionian"):
        self.tonic = int(tonic) % 12
        self.mode = "aeolian" if mode in ("aeolian", "minor") else "ionian"
        self.minor = self.mode == "aeolian"
        self.pcs = [(self.tonic + s) % 12 for s in SCALES[self.mode]]   # degree -> pc
        self.lead = (self.tonic + 11) % 12

    def chord(self, deg, seventh=False):
        pcs = [self.pcs[(deg + k) % 7] for k in ((0, 2, 4, 6) if seventh else (0, 2, 4))]
        if self.minor and deg == 4:                     # V: raised leading tone
            pcs = [self.lead if p == self.pcs[6] else p for p in pcs]
        return pcs

    def scale_for(self, pcs, root=None):
        """Scale tones over a chord: the key's, a chromatic chord tone replacing its
        neighbour (a raised third: the note below; a lowered note: the note above)."""
        s = set(self.pcs)
        root = pcs[0] if root is None else root
        for c in pcs:
            if c in s:
                continue
            raised = c == (root + 4) % 12 or c == self.lead
            n = (c - 1) % 12 if raised else (c + 1) % 12
            if n in s and n not in pcs:
                s.discard(n)
            s.add(c)
        return frozenset(s)

    def degree(self, pc):
        pc %= 12
        if pc in self.pcs:
            return self.pcs.index(pc)
        if pc == self.lead:
            return 6
        return None


class Harmony:
    """Chord segments (start q, end q, root pc, chord pcs, scale pcs)."""

    def __init__(self, segs):
        self.segs = sorted(segs, key=lambda s: s[0])
        self.starts = [s[0] for s in self.segs]

    def at(self, t):
        i = bisect.bisect_right(self.starts, t + EPS) - 1
        return self.segs[max(0, i)]

    def pcs(self, t):
        return self.at(t)[3]

    def scale(self, t):
        return self.at(t)[4]

    def root(self, t):
        return self.at(t)[2]

    def shifted(self, t0, t1):
        """The segments in [t0, t1) moved to start at 0."""
        out = []
        for s, e, r, p, sc in self.segs:
            if e <= t0 + EPS or s >= t1 - EPS:
                continue
            out.append((max(s, t0) - t0, min(e, t1) - t0, r, p, sc))
        return Harmony(out)


def harmony_from_degrees(bar_chords, key, ts):
    """bar_chords: per bar a tuple of (degree, seventh) — one or two chords."""
    bq, sp = bar_q(ts), split_at(ts)
    segs = []
    for b, chords in enumerate(bar_chords):
        t0 = b * bq
        bounds = [t0, t0 + bq] if len(chords) == 1 else [t0, t0 + sp, t0 + bq]
        for (deg, sev), s, e in zip(chords, bounds, bounds[1:]):
            pcs = key.chord(deg, sev)
            segs.append((s, e, pcs[0], frozenset(pcs), key.scale_for(pcs, pcs[0])))
    return Harmony(segs)


def harmony_from_chords(bars, key):
    """bars: per bar a list of (root pc, chord pcs, beats) — the chords given by the user
    (duets, 4/4)."""
    segs = []
    for b, bar in enumerate(bars):
        t = 4.0 * b
        for root, pcs, beats in bar:
            pcs = list(pcs)
            segs.append((t, t + beats, root, frozenset(pcs), key.scale_for(pcs, root)))
            t += beats
    return Harmony(segs)


# ---------------------------------------------------------------- form
def _entry(role, unit, ustart, **kw):
    d = dict(role=role, unit=unit, ustart=ustart, src=None, exact=False, rep=False,
             cad=None, phrase=None)
    d.update(kw)
    return d


def _phrase_roles(form, b0, L, unit, cad, phrase, bi_src=None, exact=False):
    """A phrase of L bars from b0: basic idea (or its copy), free bars, the bar before
    the cadence, the cadence."""
    for k in range(L):
        form[b0 + k] = _entry("free", unit, b0, phrase=phrase)
    if L >= 3:
        for k in (0, 1):
            if bi_src is None:
                form[b0 + k] = _entry("bi", unit, b0, phrase=phrase)
            else:
                form[b0 + k] = _entry("copy", unit, b0, src=bi_src + k,
                                      exact=exact and k == 0, phrase=phrase)
    elif L == 2:
        form[b0] = (_entry("bi", unit, b0, phrase=phrase) if bi_src is None else
                    _entry("copy", unit, b0, src=bi_src, exact=exact, phrase=phrase))
    if L >= 4:
        form[b0 + L - 2] = _entry("precad", unit, b0, cad=cad, phrase=phrase)
    form[b0 + L - 1] = _entry("cad", unit, b0, cad=cad, phrase=phrase)


def melody_form(nbars, rng, repetition=0.7):
    """Per bar: role ('bi' basic idea, 'copy' of an earlier bar, 'frag' fragment of the
    basic idea, 'free', 'precad', 'cad'), src bar, cadence ('PAC' / 'HC'), phrase."""
    n = max(1, int(nbars))
    lens = [n] if n < 4 else [4] * (n // 4)
    if n >= 4:
        lens[-1] += n % 4
    units, i = [], 0
    while i < len(lens):
        units.append(lens[i:i + 2])
        i += 2
    form = [None] * n
    bar, first_bi = 0, None
    for u, lu in enumerate(units):
        last = u == len(units) - 1
        b0, total = bar, sum(lu)
        src, exact = None, False                  # the basic idea: new, or the first's
        if first_bi is not None:
            if last and len(units) >= 3 and rng.random() < .8:
                src, exact = first_bi, True       # reprise: A ... A
            elif rng.random() < .3 * repetition + .1:
                src = first_bi                    # a variant of A
        if len(lu) == 2:
            kind = rng.choice(("period", "sentence")) if lu[0] == 4 else "period"
            if kind == "period":
                la = lu[0]
                _phrase_roles(form, b0, la, u, "HC", (b0, b0 + la), src, exact)
                _phrase_roles(form, b0 + la, lu[1], u, "PAC", (b0 + la, b0 + total),
                              bi_src=b0, exact=rng.random() < .5 + .5 * repetition)
            else:
                ph = (b0, b0 + total)
                cad = "PAC" if last else "HC"
                for k in range(total):
                    form[b0 + k] = _entry("frag", u, b0, src=b0, phrase=ph)
                for k in (0, 1):
                    form[b0 + k] = (_entry("bi", u, b0, phrase=ph) if src is None else
                                    _entry("copy", u, b0, src=src + k, exact=exact,
                                           phrase=ph))
                    form[b0 + 2 + k] = _entry("copy", u, b0, src=b0 + k, rep=True, phrase=ph)
                form[b0 + total - 2] = _entry("precad", u, b0, cad=cad, phrase=ph)
                form[b0 + total - 1] = _entry("cad", u, b0, cad=cad, phrase=ph)
        else:
            _phrase_roles(form, b0, total, u, "PAC" if last else "HC", (b0, b0 + total),
                          src, exact)
        if first_bi is None:
            first_bi = b0
        bar += total
    form[-1]["cad"] = "PAC"
    form[-1]["role"] = "cad"
    return form


def phrase_form(nbars, phrase, rng, repetition=0.7, final=True):
    """Form of a duet section: phrases of `phrase` bars, in pairs antecedent ('HC', open)
    + consequent ('PAC', closed, the antecedent's first bar again); the last one closed."""
    n, P = int(nbars), max(1, int(phrase))
    form = [None] * n
    starts = list(range(0, n, P))
    for k, b0 in enumerate(starts):
        L = min(P, n - b0)
        consequent = k % 2 == 1
        cad = "PAC" if (consequent or (final and k == len(starts) - 1)) else "HC"
        ph = (b0, b0 + L)
        for j in range(L):
            form[b0 + j] = _entry("free", k // 2, starts[k - k % 2], phrase=ph)
        if L >= 2:
            if consequent and rng.random() < .3 + .7 * repetition:
                form[b0] = _entry("copy", k // 2, b0, src=starts[k - 1], phrase=ph)
            else:
                form[b0] = _entry("bi", k // 2, b0, phrase=ph)
        if L >= 3:
            form[b0 + L - 2] = _entry("precad", k // 2, b0, cad=cad, phrase=ph)
        form[b0 + L - 1] = _entry("cad", k // 2, b0, cad=cad, phrase=ph)
    if final:
        form[-1]["cad"] = "PAC"
    return form


def _pick(rng, weights):
    items = list(weights.items())
    return rng.choices([k for k, _ in items], weights=[w for _, w in items])[0]


def _walk(prev, key, prm, rng):
    table = dict(WALK[key.mode].get(prev, {0: 1.0}))
    if prm["primaries"]:
        table = {d: w for d, w in table.items() if d in PRIMARY} or {0: .5, 3: .25, 4: .25}
    return _pick(rng, table)


def melody_harmony(form, key, ts, prm, rng):
    """Chords of every bar from the form: the basic idea from its templates, the copies
    with their source's chords (the repetition of a sentence sometimes in its dominant
    version), the cadence formulas, Piston's table elsewhere."""
    n = len(form)
    chords = [None] * n
    bi_tpl = {}
    prev = 0
    for b, f in enumerate(form):
        role = f["role"]
        if role == "bi":
            tpl = bi_tpl.get(f["unit"])
            if tpl is None:
                tpl = bi_tpl[f["unit"]] = rng.choice(BI_PRIMARY if prm["primaries"] else BI)
            degs = tpl[min(1, b - f["ustart"])]
        elif role == "copy" and chords[f["src"]] is not None:
            degs = tuple(d for d, _ in chords[f["src"]])
            if f["rep"] and rng.random() < .5:
                degs = tuple(DOMINANT_VERSION.get(d, d) for d in degs)
        elif role == "precad":
            if f["cad"] == "PAC":
                degs = rng.choice(PRE_PAC_PRIMARY if prm["primaries"] else PRE_PAC)
            else:
                degs = rng.choice(PRE_HC_PRIMARY if prm["primaries"] else PRE_HC)
        elif role == "cad":
            degs = (4,) if f["cad"] == "HC" else (0,)
        else:
            d1 = _walk(prev, key, prm, rng)
            degs = (d1, _walk(d1, key, prm, rng)) if rng.random() < prm["two_chords"] else (d1,)
        sev = [False] * len(degs)
        if role == "precad" and prm["sevenths"] and degs[-1] == 4 and rng.random() < .5:
            sev[-1] = True
        chords[b] = tuple(zip(degs, sev))
        prev = degs[-1]
    return harmony_from_degrees(chords, key, ts)


# ---------------------------------------------------------------- rhythm
def bar_rhythm(ts, level, rng):
    compound = ts[1] == 8
    beat = 1.5 if compound else 1.0
    nbeats = int(round(bar_q(ts) / beat))
    units = COMPOUND_UNITS if compound else SIMPLE_UNITS
    out, k = [], 0
    while k < nbeats:
        opts = []
        for m, nb, durs, w in units:
            if m > level or nb > nbeats - k:
                continue
            if k == 0 and durs[0] < 0:               # the bar starts with a note
                continue
            if not compound and ts == (4, 4) and nb >= 2 and k % 2 and level < 7:
                continue                             # no long note across beat 3
            opts.append((durs, nb, w * (1.6 if m >= level - 2 else 1.0)))
        durs, nb, _ = rng.choices(opts, weights=[o[2] for o in opts])[0]
        out += list(durs)
        k += nb
    return out


def cad_rhythm(ts, final, rng):
    q = bar_q(ts)
    if final:
        return [q]
    opts = {(4, 4): ([4.0], [2.0, -2.0], [3.0, -1.0]), (3, 4): ([3.0], [2.0, -1.0]),
            (2, 4): ([2.0], [1.0, -1.0]), (6, 8): ([3.0], [1.5, -1.5])}[ts]
    return list(rng.choice(opts))


def first_half(durs, ts):
    """Durations of the first half of a bar, or None (a note across the middle, 3/4)."""
    if ts == (3, 4):
        return None
    half, t, out = bar_q(ts) / 2, 0.0, []
    for d in durs:
        out.append(d)
        t += abs(d)
        if abs(t - half) < EPS:
            return out
        if t > half:
            return None
    return None


def rhythms(form, ts, level, rng):
    n = len(form)
    R = [None] * n
    last = None
    for b, f in enumerate(form):
        role = f["role"]
        if role == "cad":
            R[b] = cad_rhythm(ts, b == n - 1, rng)
            continue
        if role == "copy" and R[f["src"]] is not None:
            R[b] = list(R[f["src"]])
        elif role == "frag" and R[f["src"]] is not None:
            h = first_half(R[f["src"]], ts)
            R[b] = (h + h) if h else list(R[f["src"]])
        elif role == "precad":
            R[b] = bar_rhythm(ts, max(0, level - 2), rng)
            if R[b][-1] < 0:
                R[b][-1] = -R[b][-1]
        elif role == "free" and last is not None and rng.random() < .35:
            R[b] = list(last)
        else:
            R[b] = bar_rhythm(ts, level, rng)
        last = R[b]
    return R


# ---------------------------------------------------------------- pitches
def icost(a, b, leap):
    """Cost of a melodic interval; None = beyond the leap allowed (an octave is allowed
    from a leap limit of a fifth)."""
    d = abs(b - a)
    if d > leap and not (d == 12 and leap >= 7):
        return None
    return ICOST[d] if d < len(ICOST) else 6.0


def gauss(x, m, s):
    return math.exp(-.5 * ((x - m) / s) ** 2)


class Ctx:
    """One melody being made: events, harmony, goals, contour."""

    def __init__(self, form, harmony, key, ts, lo, hi, prm, rng, rhythm):
        self.form, self.h, self.key, self.ts = form, harmony, key, ts
        self.prm, self.rng = prm, rng
        self.bq = bar_q(ts)
        self.n = len(form)
        w = min(prm["width"], hi - lo)
        centre = lo + .45 * (hi - lo) + rng.uniform(-2, 2)
        self.lo = int(max(lo, round(centre - w / 2)))
        self.hi = int(min(hi, self.lo + w))
        self.lo = int(max(lo, self.hi - w))
        self.centre = (self.lo + self.hi) / 2 + rng.uniform(-1.5, 1.5)
        self.changes = {round(s[0], 6) for s in harmony.segs}
        # events: [start, dur, rest, bar]
        self.ev, self.bar_ev = [], [[] for _ in range(self.n)]
        for b in range(self.n):
            t = b * self.bq
            for d in rhythm[b]:
                self.bar_ev[b].append(len(self.ev))
                self.ev.append((t, abs(d), d < 0, b))
                t += abs(d)
        # contour of every phrase: start, single peak, end (fractions of the range)
        self.arc = {}
        for f in form:
            ph = f["phrase"]
            if ph not in self.arc:
                cad = form[ph[1] - 1]["cad"]
                self.arc[ph] = (rng.uniform(.5, .75), rng.uniform(.3, .5),
                                rng.uniform(.75, .95), .15 if cad == "PAC" else .45)
        self.goal, self.soft = {}, {}
        for b, f in enumerate(form):
            idx = [i for i in self.bar_ev[b] if not self.ev[i][2]]
            if not idx:
                continue
            if f["role"] == "cad":
                t = self.ev[idx[0]][0]
                pcs = harmony.pcs(t)
                if f["cad"] == "PAC":
                    self.goal[idx[0]] = {harmony.root(t)}
                else:
                    self.goal[idx[0]] = (set(pcs) - {harmony.root(t)}) or set(pcs)
                for i in idx[1:]:                 # after the cadence note: chord tones
                    self.goal[i] = set(harmony.pcs(self.ev[i][0]))
            elif f["role"] == "precad" and f["cad"] == "PAC":
                lead = key.lead if key.minor else key.pcs[6]
                self.soft[idx[-1]] = ({key.pcs[1], lead}, 1.5)
        self.P = [None] * len(self.ev)
        self.frag_shift = None

    # ---- helpers
    def strong(self, t):
        b = int(t / self.bq + EPS)
        pos = round(t - b * self.bq, 6)
        return any(abs(pos - s) < 1e-4 for s in STRONG[self.ts]) or round(t, 6) in self.changes

    def ct(self, p, i):
        return p % 12 in self.h.pcs(self.ev[i][0])

    def in_scale(self, p, i):
        return p % 12 in self.h.scale(self.ev[i][0])

    def target(self, i):
        t = self.ev[i][0]
        ph = self.form[self.ev[i][3]]["phrase"]
        xp, f0, fp, f1 = self.arc[ph]
        t0, t1 = ph[0] * self.bq, ph[1] * self.bq
        x = min(1.0, max(0.0, (t - t0) / max(t1 - t0, EPS)))
        f = f0 + (fp - f0) * x / xp if x < xp else fp + (f1 - fp) * (x - xp) / (1 - xp)
        return self.lo + f * (self.hi - self.lo)

    def late(self, i):
        """In the second half of its phrase (the line descends to the cadence)."""
        t = self.ev[i][0]
        ph = self.form[self.ev[i][3]]["phrase"]
        return (t - ph[0] * self.bq) / max((ph[1] - ph[0]) * self.bq, EPS) > .55

    def goal_ok(self, i, p):
        g = self.goal.get(i)
        return g is None or p % 12 in g

    def soft_cost(self, i, p):
        s = self.soft.get(i)
        return 0.0 if s is None or p % 12 in s[0] else s[1]

    def aug2(self, a, b):
        if not self.key.minor or abs(a - b) != 3:
            return False
        return {a % 12, b % 12} == {self.key.pcs[5], self.key.lead}

    def cands(self, i, chord_only=False):
        t = self.ev[i][0]
        pcs = self.h.pcs(t) if chord_only else self.h.scale(t)
        out = [p for p in range(self.lo, self.hi + 1) if p % 12 in pcs and self.goal_ok(i, p)]
        if not chord_only and self.prm["chromatic"] and not self.strong(t) and i not in self.goal:
            out += [p - 1 for p in range(self.lo + 1, self.hi + 1)
                    if p % 12 in self.h.pcs(t) and (p - 1) % 12 not in self.h.scale(t)]
        if not out:
            out = [p for p in range(self.lo, self.hi + 1) if p % 12 in self.h.pcs(t)]
        return out

    def step_cost(self, q0, q, p, iq, ip):
        """Cost of going from q (event iq) to p (event ip); q0 = the note before q. None =
        a rule broken."""
        c = icost(q, p, self.prm["leap"])
        if c is None or self.aug2(q, p):
            return None
        t = self.ev[ip][0]
        if not self.ct(p, ip):
            chrom = not self.in_scale(p, ip)
            if self.strong(t):
                if chrom or not self.prm["appoggiatura"]:
                    return None
                c += 4.0
            elif chrom:
                if q != p + 1:
                    return None
            elif not 0 < abs(p - q) <= 2:
                return None
        if iq is not None and not self.ct(q, iq):
            if not self.in_scale(q, iq):
                if p != q + 1:
                    return None
            elif not 0 < abs(p - q) <= 2:
                return None
        if q0 is not None:
            m0, m1 = q - q0, p - q
            if abs(m0) >= 5:                         # gap fill
                if m0 * m1 > 0:
                    c += 2.5
                elif 0 < abs(m1) <= 2:
                    c -= .5
            if abs(m0) >= 3 and abs(m1) >= 3 and m0 * m1 > 0:
                c += .5 if (self.ct(q, iq) and self.ct(p, ip)) else 1.5
            if m0 == 0 and m1 == 0:
                c += 2.0
        return c

    def prev_of(self, i):
        """(pitch, index) of the last note before event i, and the one before it."""
        out = []
        for j in range(i - 1, -1, -1):
            if self.P[j] is not None:
                out.append(j)
                if len(out) == 2:
                    break
        q = self.P[out[0]] if out else None
        iq = out[0] if out else None
        q0 = self.P[out[1]] if len(out) > 1 else None
        return q0, q, iq

    # ---- engines on a run of free bars (indices of the pitched events)
    def run_skeleton(self, idx):
        rng, leap = self.rng, self.prm["leap"]
        q0, prev, iprev = self.prev_of(idx[0])
        strong = [i for k, i in enumerate(idx) if k == 0 or self.strong(self.ev[i][0])]
        layers = [self.cands(i, chord_only=True) for i in strong]

        def unary(i, p):
            return (.25 * abs(p - self.target(i)) + self.soft_cost(i, p)
                    + rng.uniform(0, 1.2))

        back = []
        cur = {}
        for p in layers[0]:
            c0 = 0.0 if prev is None else icost(prev, p, leap)
            if c0 is None:
                c0 = 8.0 + .5 * abs(p - prev)
            cur[p] = (c0 + unary(strong[0], p), None)
        back.append(cur)
        for k in range(1, len(strong)):
            i = strong[k]
            cur = {}
            for p in layers[k]:
                u = unary(i, p)
                best = None
                for q, (cq, _) in back[-1].items():
                    ic = icost(q, p, leap)
                    if ic is None or self.aug2(q, p):
                        continue
                    v = cq + ic + u + (.6 if p > q and self.late(i) else 0.0)
                    if best is None or v < best[0]:
                        best = (v, q)
                if best is not None:
                    cur[p] = best
            if not cur:                               # nothing within the leap: the nearest
                for p in layers[k]:
                    q = min(back[-1], key=lambda x: back[-1][x][0] + abs(x - p))
                    cur[p] = (back[-1][q][0] + 6.0 + abs(q - p) + unary(i, p), q)
            back.append(cur)
        end = min(back[-1], key=lambda p: back[-1][p][0])
        skel = [end]
        for k in range(len(back) - 1, 0, -1):
            skel.append(back[k][skel[-1]][1])
        skel.reverse()
        # weak notes between two skeleton notes: beam search
        pos = {i: k for k, i in enumerate(idx)}
        out = {i: p for i, p in zip(strong, skel)}
        bounds = [pos[i] for i in strong] + [len(idx)]
        for k in range(len(strong)):
            gap = idx[bounds[k] + 1:bounds[k + 1]]
            a = skel[k]
            b = skel[k + 1] if k + 1 < len(strong) else None
            ib = strong[k + 1] if k + 1 < len(strong) else None
            if k == 0:
                a0 = prev
            else:
                a0 = out.get(idx[bounds[k] - 1], skel[k - 1])
            fill = self._fill(a0, a, strong[k], gap, b, ib)
            for i, p in zip(gap, fill):
                out[i] = p
        return [out[i] for i in idx]

    def _fill(self, a0, a, ia, gap, b, ib, width=40):
        if not gap:
            return []
        rng = self.rng
        beams = [(0.0, [(a0, None), (a, ia)])]
        for i in gap:
            lo_b = min(a, b if b is not None else a) - 7
            hi_b = max(a, b if b is not None else a) + 7
            cand = [p for p in self.cands(i) if lo_b <= p <= hi_b]
            nb = {}
            for cost, seq in beams:
                (q0, _), (q, iq) = seq[-2], seq[-1]
                for p in cand:
                    c = self.step_cost(q0, q, p, iq, i)
                    if c is None:
                        continue
                    v = (cost + c + .15 * abs(p - self.target(i)) + self.soft_cost(i, p)
                         + rng.uniform(0, .6))
                    key = (q, p)
                    if key not in nb or v < nb[key][0]:
                        nb[key] = (v, seq + [(p, i)])
            if not nb:                                # no valid note: chord tones only
                for cost, seq in beams:
                    q = seq[-1][0]
                    for p in self.cands(i, chord_only=True):
                        v = cost + 6.0 + abs(p - q)
                        key = (q, p)
                        if key not in nb or v < nb[key][0]:
                            nb[key] = (v, seq + [(p, i)])
            beams = sorted(nb.values(), key=lambda x: x[0])[:width]
        done = []
        for cost, seq in beams:
            (q0, _), (q, iq) = seq[-2], seq[-1]
            if b is not None:
                c = self.step_cost(q0, q, b, iq, ib)
                v = cost + (8.0 + abs(b - q) if c is None else c)
            else:
                v = cost + (0.0 if self.ct(q, iq) else 8.0)
            done.append((v, seq))
        done.sort(key=lambda x: x[0])
        top = done[:3]
        seq = rng.choices([s for _, s in top], weights=[3, 2, 1][:len(top)])[0]
        return [p for p, _ in seq[2:]]

    def _sample_run(self, idx, weight, tries=24):
        """Note by note with `weight(i, p, q, strong)`; the rules (step_cost) always hold;
        the best of `tries` runs (one of the best three at random)."""
        rng = self.rng
        res = []
        for _ in range(tries):
            q0, q, iq = self.prev_of(idx[0])
            seq, cost, ok = [], 0.0, True
            for k, i in enumerate(idx):
                t = self.ev[i][0]
                strong = k == 0 or self.strong(t)
                last = k == len(idx) - 1
                opts = []
                for p in self.cands(i):
                    c = 0.0 if q is None else self.step_cost(q0, q, p, iq, i)
                    if c is None:
                        continue
                    ct = self.ct(p, i)
                    if last and not ct:
                        continue
                    w = weight(i, p, q, strong) * math.exp(-.35 * c)
                    w *= (6.0 if ct else .04) if strong else (1.4 if ct else 1.0)
                    w *= math.exp(-abs(p - self.target(i)) / 7.0)
                    w *= math.exp(-self.soft_cost(i, p))
                    if w > 0:
                        opts.append((p, w, c))
                if not opts:
                    ok = False
                    break
                p, _, c = rng.choices(opts, weights=[o[1] for o in opts])[0]
                seq.append(p)
                cost += c
                q0, q, iq = q, p, i
            if ok:
                res.append((cost + .1 * sum(abs(p - self.target(i)) for p, i in zip(seq, idx)),
                            seq))
        if not res:
            return self.run_skeleton(idx)
        res.sort(key=lambda x: x[0])
        top = res[:3]
        return rng.choices([s for _, s in top], weights=[3, 2, 1][:len(top)])[0]

    def run_probabilistic(self, idx):
        sr = max(3.0, (self.hi - self.lo) / 3.0)
        prof = PROFILE[self.key.mode]

        def weight(i, p, q, strong):
            d = self.key.degree(p)
            w = gauss(p, self.centre, sr) * (prof[d] if d is not None else CHROMATIC_WEIGHT)
            if q is not None:
                w *= gauss(p, q, self.prm["prox"])
            return w
        return self._sample_run(idx, weight)

    def _ladder_index(self, p):
        return 7 * (p // 12) + (self.key.degree(p) if self.key.degree(p) is not None else 0)

    def run_degrees(self, idx):
        def weight(i, p, q, strong):
            if q is None:
                return gauss(p, self.centre, 4.0)
            m = self._ladder_index(p) - self._ladder_index(q)
            if abs(m) > 7:
                return 0.0
            w = MOVE_W[abs(m)]
            dq = self.key.degree(q)
            if dq is not None:
                w *= TENDENCY.get((dq, m), 1.0)
            return w
        return self._sample_run(idx, weight)

    # ---- copies of earlier material, moved by scale steps
    def _ladder(self, scale):
        return [p for p in range(0, 128) if p % 12 in scale]

    def _move(self, p, t_src, t_dst, k):
        src, dst = self._ladder(self.h.scale(t_src)), self._ladder(self.h.scale(t_dst))
        j = bisect.bisect_right(src, p) - 1
        off = p - src[j] if j >= 0 else 0
        j = max(0, min(len(dst) - 1, j + k))
        return dst[j] + off

    def place_copy(self, b):
        f = self.form[b]
        src_idx = [i for i in self.bar_ev[f["src"]] if not self.ev[i][2]]
        dst_idx = [i for i in self.bar_ev[b] if not self.ev[i][2]]
        if not dst_idx:
            return
        if f["role"] == "frag":
            half = self.bq / 2
            s0 = f["src"] * self.bq
            h = [i for i in src_idx if self.ev[i][0] < s0 + half - EPS]
            if 2 * len(h) == len(dst_idx) and h:
                pairs = [(h[k % len(h)], 1 if k >= len(h) else 0)
                         for k in range(len(dst_idx))]
            else:
                pairs = [(src_idx[k % len(src_idx)], 0) for k in range(len(dst_idx))]
        else:
            if len(src_idx) != len(dst_idx) or not src_idx:
                self._free([dst_idx])
                return
            pairs = [(s, 0) for s in src_idx]
        if any(self.P[si] is None for si, _ in pairs):
            self._free([dst_idx])
            return
        q0, prev, _ = self.prev_of(dst_idx[0])
        step2 = self.rng.choice((-1, -1, 1))          # sequence of a fragment: down a step
        best = None
        for k in range(-4, 5):
            ps = []
            for (si, second), di in zip(pairs, dst_idx):
                kk = k + (step2 if second else 0)
                ps.append(self._move(self.P[si], self.ev[si][0], self.ev[di][0], kk))
            c = 0.0
            for p, di in zip(ps, dst_idx):
                if not self.lo <= p <= self.hi:
                    c += 20.0
                if self.strong(self.ev[di][0]) and not self.ct(p, di):
                    c += 4.0
                if not self.goal_ok(di, p):
                    c += 10.0
            if prev is not None:
                ic = icost(prev, ps[0], self.prm["leap"])
                c += 10.0 if ic is None else ic
            if f["role"] == "frag":
                pref = -1 if self.frag_shift is None else self.frag_shift - 1
                c += .8 * abs(k - pref)
            elif f["exact"]:
                c += 0.0 if k == 0 else 2.5
            else:
                c += .3 * abs(k)
            c += self.rng.uniform(0, .8)
            if best is None or c < best[0]:
                best = (c, k, ps)
        _, k, ps = best
        if f["role"] == "frag":
            self.frag_shift = k
        for p, di in zip(ps, dst_idx):
            if ((self.strong(self.ev[di][0]) and not self.ct(p, di)) or not self.goal_ok(di, p)
                    or not self.lo <= p <= self.hi):
                cts = self.cands(di, chord_only=True)
                p = min(cts, key=lambda x: (abs(x - p), x))
            self.P[di] = p

    def _free(self, runs):
        for idx in runs:
            if not idx:
                continue
            eng = getattr(self, "run_" + self.engine)
            for i, p in zip(idx, eng(idx)):
                self.P[i] = p

    def repair(self):
        """Non-chord tones not approached / left by step, strong non-chord tones, augmented
        seconds: the nearest chord tone."""
        idx = [i for i, e in enumerate(self.ev) if not e[2] and self.P[i] is not None]
        for k, i in enumerate(idx):
            p = self.P[i]
            q = self.P[idx[k - 1]] if k else None
            r = self.P[idx[k + 1]] if k + 1 < len(idx) else None
            bad = not self.goal_ok(i, p)
            if not self.ct(p, i):
                strong = self.strong(self.ev[i][0])
                chrom = not self.in_scale(p, i)
                left = r is not None and 0 < abs(r - p) <= 2
                if chrom:
                    bad = bad or strong or q != p + 1 or r != p + 1
                elif strong:
                    bad = bad or not self.prm["appoggiatura"] or not left
                else:
                    bad = bad or q is None or not 0 < abs(p - q) <= 2 or not left
            if q is not None and self.aug2(q, p):
                bad = True
            if bad:
                cts = [x for x in self.cands(i, chord_only=True)
                       if q is None or not self.aug2(q, x)]
                ref = q if q is not None else p
                self.P[i] = min(cts, key=lambda x: (abs(x - p) + .3 * abs(x - ref), x))

    def make(self, engine):
        self.engine = engine
        b = 0
        while b < self.n:
            if self.form[b]["role"] in ("copy", "frag"):
                self.place_copy(b)
                b += 1
                continue
            e = b
            while e < self.n and self.form[e]["role"] not in ("copy", "frag"):
                e += 1
            idx = [i for bb in range(b, e) for i in self.bar_ev[bb] if not self.ev[i][2]]
            self._free([idx])
            b = e
        self.repair()
        return self.P

    def cost(self):
        """Total cost of the melody (generate and test)."""
        idx = [i for i, e in enumerate(self.ev) if not e[2] and self.P[i] is not None]
        c, q0, q, iq = 0.0, None, None, None
        for i in idx:
            p = self.P[i]
            if q is not None:
                s = self.step_cost(q0, q, p, iq, i)
                c += 8.0 if s is None else s
            c += .05 * abs(p - self.target(i))
            q0, q, iq = q, p, i
        ps = [self.P[i] for i in idx]
        if ps:
            top = max(ps)
            c += 1.5 * max(0, ps.count(top) - 2)      # one climax
        return c

    def notes(self):
        return [[s, d, self.P[i]] for i, (s, d, rest, _) in enumerate(self.ev)
                if not rest and self.P[i] is not None]


def compose(form, harmony, key, ts, lo, hi, level, rng, engine="skeleton", tries=TRIES):
    """The melody of a form on a harmony: [[start q, dur q, pitch]] (pitches in lo..hi)."""
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {', '.join(ENGINES)}")
    prm = params(level)
    R = rhythms(form, ts, prm["level"], rng)
    made = []
    for _ in range(max(1, int(tries))):
        ctx = Ctx(form, harmony, key, ts, lo, hi, prm, rng, R)
        ctx.make(engine)
        made.append((ctx.cost(), ctx))
    made.sort(key=lambda x: x[0])
    ctx = rng.choice([c for _, c in made[:2]])
    return ctx.notes()


def melody(bars=16, ts=(4, 4), tonic=0, mode="ionian", lo=60, hi=79, level=4,
           engine="skeleton", seed=None, repetition=0.7, rng=None):
    """A new melody: [[start q, dur q, pitch]] in lo..hi (the caller's pitch space)."""
    rng = rng or random.Random(seed)
    ts = parse_ts(ts)
    key = Key(tonic, mode)
    prm = params(level)
    form = melody_form(bars, rng, repetition)
    harmony = melody_harmony(form, key, ts, prm, rng)
    return compose(form, harmony, key, ts, lo, hi, level, rng, engine)
