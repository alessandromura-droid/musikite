"""
BRASS TRIO / QUARTET (owner, 2026-11-24; Generate > Brass trio / quartet): the duet
generator extended to 3-4 voices, FIXED ensembles (owner's choice):
- trio    = Trumpet in Bb 1, Trumpet in Bb 2, Trombone;
- quartet = Trumpet in Bb 1, Trumpet in Bb 2, Horn in F, Trombone.
The two trumpets are a duet of `duet.generate_duet` (same options, same seed = same lines);
the lower voices follow the same chords (theory engine, as the duet):
- TROMBONE = the bass: the root of every chord, in the octave nearest to the previous note
  inside `TROMBONE_RANGE` (concert); level 1 one note per chord, level 2-3 root then fifth
  on the second half of chords of 4 beats or more; the last chord the root.
- HORN (quartet) = an inner voice: a chord tone (third and seventh first, then fifth, root),
  the nearest to the previous one inside `HORN_RANGE` (concert), held for the chord, never
  the pitch class of the bass when the chord has 3+ other tones.
Result: a Midi at concert pitch (written for each instrument when engraved). No Qt.
"""
from . import duet as _duet

TROMBONE_RANGE = (40, 62)      # E2 - D4 concert
HORN_RANGE = (53, 69)          # F3 - A4 concert (written C4 - E5)
ENSEMBLES = {
    "trio": (("Trumpet in Bb 1", 56), ("Trumpet in Bb 2", 56), ("Trombone", 57)),
    "quartet": (("Trumpet in Bb 1", 56), ("Trumpet in Bb 2", 56), ("Horn in F", 60),
                ("Trombone", 57)),
}
ENSEMBLE_LABELS = {"trio": "Trio (2 trumpets, trombone)",
                   "quartet": "Quartet (2 trumpets, horn, trombone)"}
BB_TRUMPET = -2                # concert = written - 2


def segments(chords, rounds, concert=False):
    """[(start q, end q, root pc CONCERT, chord pcs CONCERT, quality)] of the progression
    (chords written for the Bb trumpet unless concert)."""
    shift = 2 if concert else 0
    bars = _duet.parse_progression(chords, shift) * int(rounds)
    out = []
    for b, bar in enumerate(bars):
        t = 4.0 * b
        for root, qual, beats in bar:
            r = (root + BB_TRUMPET) % 12
            ivs = _duet.QUALITIES[qual]
            out.append((t, t + beats, r, [(r + i) % 12 for i in ivs], qual))
            t += beats
    return out


def _nearest(pc, prev, lo, hi):
    cands = [p for p in range(lo, hi + 1) if p % 12 == pc]
    if not cands:
        return None
    ref = prev if prev is not None else (lo + hi) // 2
    return min(cands, key=lambda p: (abs(p - ref), p))


def bass_line(segs, level=1):
    notes, prev = [], None
    for k, (s, e, root, pcs, _) in enumerate(segs):
        p = _nearest(root, prev, *TROMBONE_RANGE)
        last = k == len(segs) - 1
        if level >= 2 and e - s >= 4 and not last and len(pcs) >= 3:
            half = s + (e - s) / 2
            fifth = (root + 7) % 12
            q = _nearest(fifth, p, *TROMBONE_RANGE) if fifth in pcs else p
            notes += [[s, half - s, p], [half, e - half, q]]
            prev = q
        else:
            notes.append([s, e - s, p])
            prev = p
    return notes


def inner_line(segs):
    notes, prev = [], None
    for s, e, root, pcs, _ in segs:
        order = pcs[1:2] + pcs[3:4] + pcs[2:3] + pcs[:1]       # third, seventh, fifth, root
        order += [x for x in pcs if x not in order]
        if len(pcs) >= 4:
            order = [x for x in order if x != root] or order
        best = None
        for rank, pc in enumerate(order):
            p = _nearest(pc, prev, *HORN_RANGE)
            if p is None:
                continue
            cost = abs(p - prev) + rank if prev is not None else rank
            if best is None or cost < best[0]:
                best = (cost, p)
        p = best[1] if best else _nearest(root, prev, *HORN_RANGE)
        notes.append([s, e - s, p])
        prev = p
    return notes


def generate_ensemble(voices="trio", chords=_duet.DEFAULT_CHORDS, rounds=2, level=1, key=None,
                      concert=False, seed=None, phrase=4, textures=None, repetition=0.7,
                      engine="classic"):
    """dict(parts=[(name, program, [[start q, dur q, pitch CONCERT]])], kpc, minor, nbars,
    seed, log): kpc / minor as the duet (written trumpet key)."""
    if voices not in ENSEMBLES:
        raise ValueError(f"voices must be one of {', '.join(ENSEMBLES)}")
    d = _duet.generate_duet(chords, rounds, level, key, concert, seed, phrase, textures,
                            repetition, engine)
    segs = segments(chords, rounds, concert)
    lines = {"Trumpet in Bb 1": [[s, du, p + BB_TRUMPET] for s, du, p in d["t1"]
                                 if p is not None],
             "Trumpet in Bb 2": [[s, du, p + BB_TRUMPET] for s, du, p in d["t2"]
                                 if p is not None],
             "Trombone": bass_line(segs, level),
             "Horn in F": inner_line(segs)}
    parts = [(name, prog, lines[name]) for name, prog in ENSEMBLES[voices]]
    return dict(parts=parts, kpc=d["kpc"], minor=d["minor"], nbars=d["nbars"], seed=d["seed"],
                log=d["log"])
