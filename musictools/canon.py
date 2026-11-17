"""
Canon for two Bb trumpets (port of canon_trumpets.py, which stays as it is; owner's planned
item "Canon for trumpets", 2026-11-08). No Qt.

  - trumpet 1 plays the progression `cycles` times, each time with new material;
  - trumpet 2 enters one full progression later and plays exactly what trumpet 1 played in
    the previous cycle (delay = length of the progression, so every line fits the harmony);
  - while trumpet 2 plays its last cycle, trumpet 1 holds long chord tones;
  - both end on the tonic chord.

Chords and key are parsed by the theory engine (English or Italian symbols, every quality it
knows). Convention as the duets (NOT as canon_trumpets.py): concert=False = chords and key
are WRITTEN trumpet pitch. generate_canon() returns WRITTEN pitches; Midi.makecanon() writes
the MIDI at concert pitch.

    m = Midi().makecanon('C F G C', difficulty=2, cycles=4, seed=1)
"""
import random
import re

from . import theory as _th

# difficulty -> written range, max leap (semitones), non-chord tones allowed
LEVELS = {
    1: dict(low=60, high=72, max_leap=5, nct=False),    # C4-C5
    2: dict(low=57, high=74, max_leap=7, nct=False),    # A3-D5
    3: dict(low=55, high=76, max_leap=7, nct=True),     # G3-E5
    4: dict(low=55, high=79, max_leap=9, nct=True),     # G3-G5
    5: dict(low=55, high=79, max_leap=12, nct=True),    # G3-G5
}
LEVEL_LABELS = {1: "1 – one long note per chord", 2: "2 – half notes", 3: "3 – quarter notes",
                4: "4 – + eighth notes", 5: "5 – mostly eighth notes"}
# difficulty -> (duration in beats, weight); 0.5 = a pair of eighth notes
RHYTHMS = {
    2: [(4, 1), (2, 3)],
    3: [(2, 1), (1, 3)],
    4: [(2, 1), (1, 5), (0.5, 3)],
    5: [(1, 2), (0.5, 3)],
}
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)
DEFAULT_CHORDS = "C F G C"


def _nct_pcs(chord_set, scale_set):
    """Scale tones usable as passing / neighbour tones over this chord."""
    out = set()
    for pc in scale_set - chord_set:
        bad = any(((pc + d) % 12 in chord_set) and ((pc + d) % 12 not in scale_set)
                  for d in (-1, 1))
        if not bad:
            out.add(pc)
    return out


def _rhythm(span, level, r):
    out, left = [], float(span)
    while left > 1e-9:
        opts = [(d, w) for d, w in RHYTHMS[level] if (1.0 if d == 0.5 else d) <= left + 1e-9]
        if not opts:
            out.append(left)
            break
        d = r.choices([o[0] for o in opts], weights=[o[1] for o in opts])[0]
        if d == 0.5:
            out += [0.5, 0.5]
            left -= 1.0
        else:
            out.append(float(d))
            left -= d
    return out


def _sounding(notes, t):
    for s, d, p in notes:
        if s <= t + 1e-9 and t < s + d - 1e-9:
            return p
    return None


def _choose(cands, prev, other, strong, cfg, center, r):
    best, best_s = None, None
    for p in cands:
        s = 0.0
        if prev is not None:
            leap = abs(p - prev)
            if leap > cfg["max_leap"]:
                continue
            s += 0.5 * leap if leap <= 2 else leap + 1.0
            if leap == 0:
                s += 1.5
            if leap == 6:
                s += 5.0
        s += 0.15 * abs(p - center)
        if other is not None:
            iv = abs(p - other) % 12
            if p == other:
                s += 3.0
            elif iv in (1, 2, 10, 11):
                s += 6.0 if strong else 2.5
            elif iv == 6:
                s += 2.0
        s += 1.5 * r.random()
        if best_s is None or s < best_s:
            best, best_s = p, s
    if best is None:
        best = min(cands, key=lambda p: abs(p - prev))
    return best


def _cycle(chords, bpc, level, cfg, scale_set, other, prev, r, long_notes=False):
    lo, hi = cfg["low"], cfg["high"]
    center = (lo + hi) / 2.0
    notes, t, prev_nct = [], 0.0, False
    for ch in chords:
        cset = set(ch.pcs)
        ct = [p for p in range(lo, hi + 1) if p % 12 in cset]
        nset = _nct_pcs(cset, scale_set) if (cfg["nct"] and not long_notes) else set()
        nt = [p for p in range(lo, hi + 1) if p % 12 in nset]
        durs = [float(bpc)] if (long_notes or level == 1) else _rhythm(bpc, level, r)
        for i, d in enumerate(durs):
            on_beat = abs(t - round(t)) < 1e-9
            strong = i == 0 or (on_beat and round(t) % 2 == 0)
            other_p = _sounding(other, t) if other else None
            if prev_nct:                      # a non-chord tone resolves by step
                cands = [p for p in ct if 1 <= abs(p - prev) <= 2] or ct
            else:
                cands = list(ct)
                if nt and prev is not None and 0 < i < len(durs) - 1:
                    cands += [p for p in nt if 1 <= abs(p - prev) <= 2]
            p = _choose(cands, prev, other_p, strong, cfg, center, r)
            prev_nct = p % 12 not in cset
            notes.append((t, d, p))
            prev = p
            t += d
    return notes, prev


def generate_canon(chords=DEFAULT_CHORDS, difficulty=2, beats_per_chord=4, cycles=4, key=None,
                   concert=False, seed=None):
    """dict(t1, t2: [(start_q, dur_q, written pitch)], kpc, minor (written), seed, bars)."""
    if seed is None:
        seed = random.randrange(1000000)
    r = random.Random(seed)
    shift = 2 if concert else 0                 # concert chords -> written trumpet pitch
    symbols = [x for x in re.split(r"[\s,|]+", str(chords).strip()) if x]
    if not symbols:
        raise ValueError("no chords")
    chs = [_th.parse_chord(x).transpose(shift) for x in symbols]
    if key:
        kc = _th.parse_chord(key).transpose(shift)
        kpc, minor = kc.root, kc.is_minor
    else:
        kpc, minor = chs[0].root, chs[0].is_minor
    scale_set = {(kpc + i) % 12 for i in (MINOR_SCALE if minor else MAJOR_SCALE)}
    level = int(difficulty)
    cfg = LEVELS[level]
    bpc = int(beats_per_chord)
    L = len(chs) * bpc
    cyc, prev1 = [], None
    for k in range(int(cycles)):
        notes, prev1 = _cycle(chs, bpc, level, cfg, scale_set, cyc[k - 1] if k else [], prev1, r)
        cyc.append(notes)
    v1, v2 = [], []
    for k, notes in enumerate(cyc):
        v1 += [(s + k * L, d, p) for s, d, p in notes]
        v2 += [(s + (k + 1) * L, d, p) for s, d, p in notes]
    coda, prev1 = _cycle(chs, bpc, 1, cfg, scale_set, cyc[-1], prev1, r, long_notes=True)
    v1 += [(s + int(cycles) * L, d, p) for s, d, p in coda]
    t_end = (int(cycles) + 1) * L
    tonic = {(kpc + i) % 12 for i in ((0, 3, 7) if minor else (0, 4, 7))}
    prev2 = cyc[-1][-1][2]
    roots = [p for p in range(cfg["low"], cfg["high"] + 1) if p % 12 == kpc]
    f2 = min(roots, key=lambda p: abs(p - prev2))
    good = (3, 4, 7, 8, 9)
    tones = [p for p in range(cfg["low"], cfg["high"] + 1) if p % 12 in tonic and p != f2]
    f1 = min(tones, key=lambda p: abs(p - prev1) + (0 if abs(p - f2) in good else 10))
    v1.append((t_end, 4.0, f1))
    v2.append((t_end, 4.0, f2))
    return dict(t1=v1, t2=v2, kpc=kpc, minor=minor, seed=seed,
                bars=int(round((t_end + 4.0) / 4.0)))
