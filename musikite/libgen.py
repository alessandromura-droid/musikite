"""
GENERATION OF THE EXERCISE LIBRARY (owner, 2026-11-19), used by scripts/build_library.py
and by "Add to library…" (the melody of a MIDI). Pure Python but `melody_of_midi`, which
reads a MIDI through Score (music21, desktop).

The library is made of MELODIES (one voice, concert pitch, in their original register and
tempo), each stored as a small MIDI file (library.py). The source MIDI files (piano and
trumpet exercises, WITH COPYRIGHT) never go into the library: only melodies made from them
that are far from the originals —
1. TRANSFORMED: `transformations(ph, which)` — which = a list of the allowed TRANSFORMS
   (owner, 2026-11-19: flags of build_library.py): none (the melody itself: an EXCEPTION
   to the rule above, chosen by the owner), modal, inversion, inversion-modal,
   retrograde, retrograde-modal, retrograde-inversion; the old settings "inversion" (7)
   and "all" (15) are PRESETS;
2. CROSSED: the pitches of a transformed melody A on the rhythm of a melody B with the same
   metre (at most MAX_CROSSINGS, drawn at random), the last note moved to A's tonic;
3. GENERATED: new melodies from a Markov model of the source melodies (intervals, order 2
   with back-off; rhythm = bar patterns of the corpus, order 1), in a major or minor key,
   starting on a chord tone and ending on the tonic; a melody that copies more than
   COPY_MAX consecutive intervals of a source is thrown away.
Every melody must pass the ENTROPY filter (`entropy`: Shannon entropy in bits of the
pairs of consecutive (interval, duration) tokens; scales repeated over and over, typical of
the piano exercises' right hand, are low) — the source melodies too, before anything is made
from them, and the Markov model learns only from those that pass.

The melody of a source MIDI (`melody_of_midi`): the part with the MOST NOTES (owner's rule),
at least MIN_NOTES, reduced to one voice (the highest note of every chord); the whole piece,
not cut.
"""
import math
from collections import Counter, defaultdict

MIN_NOTES = 16
COPY_MAX = 7                      # consecutive intervals a generated melody may share with a source


# ---------------------------------------------------------------- melody of a MIDI
def melody_of_midi(midi, title=None):
    """Phrase: the melody of a Midi object (see the module doc), concert pitch, whole piece;
    None if no part has MIN_NOTES notes."""
    import contextlib
    import io
    from .score import Score
    from .phrase import exercises_from_midi
    with contextlib.redirect_stdout(io.StringIO()):
        score = Score.from_midi(midi, written=False)
    best = None
    for ip, part in enumerate(score.m21.parts):
        ps = [n.pitch.midi for n in part.recurse().notes if not n.isChord] + \
             [max(p.midi for p in c.pitches) for c in part.recurse().notes if c.isChord]
        if len(ps) < MIN_NOTES:
            continue
        if best is None or len(ps) > best[0]:          # the part with the most notes (owner)
            best = (len(ps), ip, part)
    if best is None:
        return None
    _, ip, part = best
    numbers = [m.number for m in part.getElementsByClass("Measure")]
    with contextlib.redirect_stdout(io.StringIO()):
        st = exercises_from_midi(midi, purpose="reading", parts=[ip],
                                 bar_range=(numbers[0], numbers[-1]), level=5,
                                 instrument="C (piano)", remove_empty=True, polyphony=False,
                                 note_range=(0, 127), title=title, include_midi=False)
    if not st.phrases:
        return None
    ph = st.phrases[0]
    ph.practice_bpm = ph.practice_bpm or ph.bpm
    return neutral(ph, title)


def neutral(ph, title=None):
    """A library melody: no instrument (translated at use), no results, no origin, one
    voice, key estimated again (the key it is read in)."""
    from .theory import key_of_notes
    top = {}
    for s, d, p in ph.notes:
        k = round(s, 6)
        if k not in top or p > top[k][2]:
            top[k] = [s, d, p]
    p2 = ph.copy()
    p2.notes = [top[k] for k in sorted(top)]
    p2.tonic, p2.mode = key_of_notes(p2.notes)
    p2.instrument = "library"
    p2.program, p2.transposition, p2.part = 0, 0, "Melody"
    p2.origin, p2.source_midi, p2.source, p2.transform = None, None, "", "none"
    p2.results, p2.grades, p2.level, p2.start_bar = {}, {}, 5, 1
    p2.title = title or ph.title
    return p2


# ---------------------------------------------------------------- entropy filter
def _tokens(ph):
    notes = sorted(ph.notes)
    out = []
    for (s0, d0, p0), (s1, d1, p1) in zip(notes, notes[1:]):
        iv = max(-12, min(12, p1 - p0))
        out.append((iv, round(d1 / d0, 2) if d0 > 0 else 0))
    return out


def entropy(ph):
    """Shannon entropy (bits) of the pairs of consecutive (interval, duration ratio)
    tokens: low = the same figure again and again (scales, repeated patterns)."""
    t = _tokens(ph)
    pairs = Counter(zip(t, t[1:]))
    n = sum(pairs.values())
    if n == 0:
        return 0.0
    return -sum(c / n * math.log2(c / n) for c in pairs.values())


def passes(ph, min_entropy):
    return len(ph.notes) >= MIN_NOTES and entropy(ph) >= float(min_entropy)


# ---------------------------------------------------------------- 1. transformations
def _modes_other(mode):
    from .phrase import MODES
    return [m for m in MODES if m != mode]


# the transformations allowed (owner, 2026-11-19: flags of build_library.py), in this order
TRANSFORMS = ("none", "modal", "inversion", "inversion-modal", "retrograde", "retrograde-modal",
              "retrograde-inversion")
# the old settings of build_library.py
PRESETS = {"inversion": ("inversion", "inversion-modal"),
           "all": ("retrograde", "inversion", "retrograde-inversion", "retrograde-modal",
                   "inversion-modal")}


def transformations(ph, which="inversion"):
    """The melodies made from ph: [(tag, Phrase)]. which = a list of TRANSFORMS names (or one
    name, or a PRESETS name):
      none                 the melody itself                         tag "none"
      modal                the melody in the 6 other church modes    tag "dorian", "lydian"…
      inversion            mirror around the tonic, its own mode     tag "inversion"
      inversion-modal      the mirror in the 6 other modes           tag "inversion, dorian"…
      retrograde           the melody backwards                      tag "retrograde"
      retrograde-modal     the retrograde in the 6 other modes       tag "retrograde, dorian"…
      retrograde-inversion retrograde of the mirror                  tag "retrograde inversion"
    The key of every result is estimated again (the key it is read in)."""
    from .theory import key_of_notes
    names = PRESETS.get(which, which) if isinstance(which, str) else which
    if isinstance(names, str):
        names = (names,)
    bad = [n for n in names if n not in TRANSFORMS]
    if bad:
        raise ValueError(f"unknown transformation(s) {bad}; allowed: {', '.join(TRANSFORMS)}")
    others = _modes_other(ph.mode)
    made = {}

    def inv():
        if "i" not in made:
            made["i"] = ph.inversion()
        return made["i"]

    def ret():
        if "r" not in made:
            made["r"] = ph.reverse_melody()
        return made["r"]

    out = []
    for name in TRANSFORMS:
        if name not in names:
            continue
        if name == "none":
            out.append(("none", ph))
        elif name == "modal":
            out += [(m, ph.to_mode(m)) for m in others]
        elif name == "inversion":
            out.append(("inversion", inv()))
        elif name == "inversion-modal":
            out += [(f"inversion, {m}", inv().to_mode(m)) for m in others]
        elif name == "retrograde":
            out.append(("retrograde", ret()))
        elif name == "retrograde-modal":
            out += [(f"retrograde, {m}", ret().to_mode(m)) for m in others]
        elif name == "retrograde-inversion":
            out.append(("retrograde inversion", inv().reverse_melody()))
    res = []
    for tag, p in out:
        p = p.copy()
        p.tonic, p.mode = key_of_notes(p.notes)
        res.append((tag, p))
    return res


# ---------------------------------------------------------------- 2. crossing
def cross(a, b):
    """The pitches of melody A on the rhythm of melody B (same metre); as long as the shorter
    of the two; the last note moved to A's tonic (nearest octave). None if not possible."""
    from .theory import key_of_notes
    if tuple(a.ts) != tuple(b.ts) or a.ts_changes or b.ts_changes:
        return None
    pitches = [p for _, _, p in sorted(a.notes)]
    rhythm = [(s, d) for s, d, _ in sorted(b.notes)]
    n = min(len(pitches), len(rhythm))
    if n < MIN_NOTES:
        return None
    notes = [[s, d, p] for (s, d), p in zip(rhythm[:n], pitches[:n])]
    last = notes[-1][2]
    cands = [last + k for k in range(-6, 7) if (last + k) % 12 == a.tonic]
    notes[-1][2] = min(cands, key=lambda x: abs(x - last))
    end = notes[-1][0] + notes[-1][1]
    c = a.copy()
    c.notes = notes
    c.bars = max(1, int(math.ceil(end / a.bar_q - 1e-9)))
    c.bpm = b.bpm
    c.practice_bpm = b.practice_bpm or b.bpm
    c.tonic, c.mode = key_of_notes(notes)
    return c


# ---------------------------------------------------------------- 3. Markov generation
def _bar_patterns(ph):
    """[(onset, dur) …] of every bar (onsets from the bar start; durations cut at its end);
    empty bars left out."""
    bq = ph.bar_q
    bars = defaultdict(list)
    for s, d, _ in sorted(ph.notes):
        b = int(s // bq + 1e-9)
        o = round(s - b * bq, 4)
        bars[b].append((o, round(min(d, bq - o), 4)))
    return [tuple(bars[k]) for k in sorted(bars)]


class Markov:
    """Intervals (order 2 with back-off) and bar rhythms (order 1 per metre) of a corpus of
    melodies; `generate` makes a new melody."""

    def __init__(self, melodies):
        self.iv2 = defaultdict(Counter)
        self.iv1 = defaultdict(Counter)
        self.iv0 = Counter()
        self.bars = defaultdict(lambda: defaultdict(Counter))   # ts -> prev pattern -> next
        self.firsts = defaultdict(Counter)                      # ts -> first patterns
        self.lengths = defaultdict(list)                        # ts -> bars
        self.bpms = defaultdict(list)
        self.grams = set()                                      # source interval n-grams
        for ph in melodies:
            ps = [p for _, _, p in sorted(ph.notes)]
            ivs = [max(-12, min(12, b - a)) for a, b in zip(ps, ps[1:])]
            for k, iv in enumerate(ivs):
                self.iv0[iv] += 1
                if k >= 1:
                    self.iv1[ivs[k - 1]][iv] += 1
                if k >= 2:
                    self.iv2[(ivs[k - 2], ivs[k - 1])][iv] += 1
            for k in range(len(ivs) - COPY_MAX):
                self.grams.add(tuple(ivs[k:k + COPY_MAX + 1]))
            ts = tuple(ph.ts)
            pats = _bar_patterns(ph)
            if not pats:
                continue
            self.firsts[ts][pats[0]] += 1
            for x, y in zip(pats, pats[1:]):
                self.bars[ts][x][y] += 1
            self.lengths[ts].append(ph.bars)
            self.bpms[ts].append(float(ph.practice_bpm or ph.bpm))

    @staticmethod
    def _pick(counter, rng):
        items = list(counter.items())
        return rng.choices([k for k, _ in items], weights=[w for _, w in items])[0]

    def _next_iv(self, h, rng):
        if len(h) >= 2 and self.iv2.get((h[-2], h[-1])):
            return self._pick(self.iv2[(h[-2], h[-1])], rng)
        if h and self.iv1.get(h[-1]):
            return self._pick(self.iv1[h[-1]], rng)
        return self._pick(self.iv0, rng)

    def copies(self, pitches):
        ivs = [max(-12, min(12, b - a)) for a, b in zip(pitches, pitches[1:])]
        return any(tuple(ivs[k:k + COPY_MAX + 1]) in self.grams
                   for k in range(len(ivs) - COPY_MAX))

    def generate(self, rng, tries=20):
        """A new Phrase (or None after `tries` melodies that copied a source)."""
        from .phrase import Phrase
        from .theory import SCALES
        metres = [ts for ts in self.firsts if self.lengths[ts]]
        if not metres or not self.iv0:
            return None
        ts = rng.choices(metres, weights=[len(self.lengths[t]) for t in metres])[0]
        bq = ts[0] * 4.0 / ts[1]
        for _ in range(int(tries)):
            nbars = max(4, min(32, rng.choice(self.lengths[ts])))
            pats = [self._pick(self.firsts[ts], rng)]
            while len(pats) < nbars:
                nxt = self.bars[ts].get(pats[-1])
                pats.append(self._pick(nxt, rng) if nxt else self._pick(self.firsts[ts], rng))
            rhythm = [(b * bq + o, d) for b, pat in enumerate(pats) for o, d in pat]
            if len(rhythm) < MIN_NOTES:
                continue
            mode = rng.choice(("ionian", "aeolian"))
            tonic = rng.randrange(12)
            scale = {(tonic + i) % 12 for i in SCALES[mode]}
            lo, hi = 55 + tonic - 7, 55 + tonic + 19
            third = 3 if mode == "aeolian" else 4
            p = 55 + tonic + 12 + rng.choice((0, third, 7, 0))
            pitches, h = [p], []
            for _ in rhythm[1:]:
                iv = self._next_iv(h, rng)
                q = p + iv
                if q % 12 not in scale:                        # snap into the key
                    q += 1 if (q + 1) % 12 in scale else -1
                if not lo <= q <= hi:
                    q = p - iv
                    if q % 12 not in scale:
                        q += 1 if (q + 1) % 12 in scale else -1
                    if not lo <= q <= hi:
                        q = p
                h.append(max(-12, min(12, q - p)))
                pitches.append(q)
                p = q
            last = pitches[-1]
            pitches[-1] = min((last + k for k in range(-6, 7) if (last + k) % 12 == tonic),
                              key=lambda x: abs(x - last))
            if self.copies(pitches):
                continue
            notes = [[s, d, q] for (s, d), q in zip(rhythm, pitches)]
            s, d, q = notes[-1]
            notes[-1][1] = max(d, nbars * bq - s)                # the last note to the end
            bpm = rng.choice(self.bpms[ts])
            ph = Phrase(notes, nbars, ts, tonic, mode, bpm, 0, "Melody", "", "", "none",
                        "reading", 1, instrument="library", practice_bpm=bpm)
            return ph
        return None


def generate(sources, n, min_entropy, rng):
    """n new melodies from the source melodies (each must pass the entropy filter)."""
    if int(n) <= 0:
        return []
    model = Markov(sources)
    out, attempts = [], 0
    while len(out) < int(n) and attempts < int(n) * 10:
        attempts += 1
        ph = model.generate(rng)
        if ph is not None and passes(ph, min_entropy):
            out.append(ph)
    return out


def crossings(melodies, n, min_entropy, rng):
    """At most n crossed melodies from random pairs (A transformed, B any) of the same
    metre."""
    by_ts = defaultdict(list)
    for m in melodies:
        by_ts[tuple(m.ts)].append(m)
    pools = [v for v in by_ts.values() if len(v) >= 2]
    out, attempts = [], 0
    while pools and len(out) < int(n) and attempts < int(n) * 10:
        attempts += 1
        pool = rng.choice(pools)
        a, b = rng.sample(pool, 2)
        c = cross(a, b)
        if c is not None and passes(c, min_entropy):
            out.append(c)
    return out
