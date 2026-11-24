"""
REWORK OF RECORDED / KEYBOARD MATERIAL (owner, 2026-11-24): port of the methods of the
owner's MATLAB class `mysmartmusic_obj/exercise.m` that were not ported to phrase.py —
adapt, split (with double), resample, quantize. Pure Python, no Qt, no music21 (Android).
Not in the GUI yet: they will be added to the editor (todo.md).

    from musikite import rework
    parts = rework.split(ph)            # the phrase cut in two halves (bars)
    parts = rework.adapt(ph)            # notes shorter than an eighth: values doubled, cut in two
    ph2 = rework.resample(ph, 0.5)      # the melody sampled every eighth (nearest note)
    ph3 = rework.quantize(times_s, pitches)   # a performance (seconds) -> a phrase in quarters

Phrases are `phrase.Phrase` (notes [start, dur, pitch] in quarters, concert pitch); every
result is a NEW exercise (new uid, no results), titled with what was done.
"""
from . import theory as th

MIN_VALUE_Q = 0.5          # adapt: a note shorter than an eighth (rounded to 1/16) doubles
HIST_STEP_S = 1e-3         # quantize: bins of the histogram of the inter-onset times (s)
HIST_SMOOTH_S = 0.1        # quantize: width of the running sum that smooths it (s)


def _new(ph, what, **changes):
    """A copy of a phrase as a new exercise, its title saying what was done."""
    p = ph.copy(**changes)
    p.transform = what if ph.transform == "none" else f"{ph.transform}+{what}"
    p.title = f"{ph.title} – {what}" if ph.title else what
    return p


def double(ph):
    """Every value twice as long (MATLAB `double`): the phrase has twice the bars."""
    return _new(ph, "doubled", notes=[[s * 2, d * 2, p] for s, d, p in ph.notes],
                bars=ph.bars * 2, ts_changes=None)


def split(ph):
    """The phrase cut in two halves of its bars (MATLAB `split`): the notes starting before
    the middle in the first one, the others (moved to start at 0) in the second one. A
    phrase whose notes all start before the middle, or with fewer than 2 bars, is returned
    alone: [ph]."""
    if ph.bars < 2 or not ph.notes:
        return [ph]
    half_bars = ph.bars // 2
    mid = half_bars * ph.bar_q
    a = [n for n in ph.notes if n[0] < mid - 1e-9]
    b = [n for n in ph.notes if n[0] >= mid - 1e-9]
    if not b or not a:
        return [ph]
    t0 = b[0][0]
    first = _new(ph, "part 1", notes=[[s, min(d, mid - s), p] for s, d, p in a],
                 bars=half_bars, ts_changes=None)
    second = _new(ph, "part 2", notes=[[s - t0, d, p] for s, d, p in b],
                  bars=ph.bars - half_bars, start_bar=ph.start_bar + half_bars,
                  ts_changes=None)
    return [first, second]


def adapt(ph, min_value=MIN_VALUE_Q):
    """MATLAB `adapt`: if the shortest note (rounded to a sixteenth) is shorter than
    `min_value` quarters (an eighth), every value is doubled — the same music written
    with longer values, easier to read — and the phrase, now twice as long, is cut in two
    (`split`). Otherwise [ph] unchanged."""
    if not ph.notes:
        return [ph]
    shortest = min(round(d * 4) / 4 for _, d, _ in ph.notes)
    if shortest >= min_value:
        return [ph]
    return split(double(ph))


def resample(ph, step=0.5):
    """MATLAB `resample`: the melody sampled every `step` quarters (default an eighth): at
    every grid point the note sounding nearest to it (start or end of a note), so the
    result is a line of equal values `step` long over the whole phrase. One voice: in a
    chord the highest note."""
    if not ph.notes:
        return _new(ph, f"resampled {step:g}")
    top = {}
    for s, d, p in ph.notes:
        if s not in top or p > top[s][1]:
            top[s] = (d, p)
    knots = []                                   # (time, pitch): starts and ends of notes
    for s in sorted(top):
        d, p = top[s]
        knots.append((s, p))
        knots.append((s + max(d - 1.0 / 16, 0.0), p))
    knots.sort()
    L = ph.length_q
    out, k, t = [], 0, 0.0
    while t < L - 1e-9:
        while k + 1 < len(knots) and abs(knots[k + 1][0] - t) <= abs(knots[k][0] - t):
            k += 1
        out.append([round(t, 6), float(step), int(knots[k][1])])
        t += step
    return _new(ph, f"resampled {step:g}", notes=out)


def quantize(times, pitches, program=56, title="Quantized", transposition=None,
             instrument=None):
    """MATLAB `quantize`: a performance (note onsets in SECONDS, any start) -> a phrase in
    quarters. The basic period T0 = the commonest time between two onsets (histogram in
    1 ms bins smoothed over 100 ms, its maximum) and it is taken as an EIGHTH; every time
    between onsets is rounded to a whole number of T0. Values = the time to the next
    onset, the last an eighth; 4/4, tempo 60 / (2 T0), bars = ceil(last onset / 4), key
    estimated by the theory engine (tonalita.m)."""
    from .phrase import Phrase
    pairs = sorted(zip((float(x) for x in times), (int(p) for p in pitches)))
    if not pairs:
        raise ValueError("quantize: no notes")
    t = [x - pairs[0][0] for x, _ in pairs]
    pitch = [p for _, p in pairs]
    if len(t) < 2:
        notes = [[0.0, 0.5, pitch[0]]]
        bpm = 120.0
    else:
        da = [t[i] - t[i - 1] for i in range(1, len(t))]
        nb = int(max(da) / HIST_STEP_S) + 11
        hist = [0] * nb
        for x in da:
            hist[min(nb - 1, int(round(x / HIST_STEP_S)))] += 1
        w = max(1, int(round(HIST_SMOOTH_S / HIST_STEP_S)))
        half = w // 2                                   # centred running sum (filter2)
        sm, acc = [], 0
        pre = [0]
        for v in hist:
            pre.append(pre[-1] + v)
        for i in range(nb):
            lo, hi = max(0, i - half), min(nb, i - half + w)
            sm.append(pre[hi] - pre[max(0, lo)])
        i_max = max(range(nb), key=lambda i: sm[i])
        T0 = max(i_max * HIST_STEP_S, HIST_STEP_S)
        stamp = [0.0]
        for i in range(1, len(t)):
            stamp.append(stamp[-1] + round((t[i] - t[i - 1]) / T0) * T0)
        q = [s / T0 * 0.5 for s in stamp]
        dur = [q[i + 1] - q[i] for i in range(len(q) - 1)] + [0.5]
        notes = [[q[i], dur[i], pitch[i]] for i in range(len(q)) if dur[i] > 0]
        bpm = 60.0 / (2 * T0)
    bars = max(1, int(-(-max(n[0] for n in notes) // 4)))
    if max(n[0] + n[1] for n in notes) > bars * 4:
        bars += 1
    tonic, mode = th.key_of_notes(notes)
    return Phrase(notes, bars, (4, 4), tonic, mode, bpm, program=program, title=title,
                  transform="quantized", transposition=transposition, instrument=instrument)


def quantize_notes(notes_obj, track=0, **kw):
    """quantize() on a recording (`notes.Notes`, or any Midi): the onsets and pitches of a
    track."""
    ins = notes_obj.pm.instruments[track]
    ns = sorted(ins.notes, key=lambda n: n.start)
    return quantize([n.start for n in ns], [n.pitch for n in ns], program=ins.program, **kw)
