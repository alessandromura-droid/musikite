"""
DUET ENGINE 'counterpoint' (owner, 2026-11-24: "the duets are very lacking too"), beside
the classic engine of duet.py (option `engine` of generate_duet / makeduet).

On the chords given (the same options as the classic engine), period by period (two
phrases: antecedent ending open, consequent ending closed, the last one on the tonic):
1. THE MELODY is made by melodygen.py (engine 'skeleton', Povel: chord tones on the
   strong beats, passing and neighbour tones resolved by step; form with the motif of the
   antecedent restated in the consequent; cadence goals);
2. THE SECOND VOICE is chosen note by note by a second-order Viterbi search of the lowest
   COST, with the rules of two-voice counterpoint (Fux, as formalised by FuxCP,
   Sprockeels et al. 2023): consonance on the strong beats (imperfect preferred to
   perfect), no parallel fifths / octaves, no direct fifth / octave with a leap of the
   melody, contrary and oblique motion preferred, no crossing, spacing within about an
   octave and a half, steps before leaps, a leap followed by a step the other way,
   non-chord tones approached and left by step, the final note on the root;
3. TEXTURES, one per period (the duet's names): counterpoint (COMPLEMENTARY RHYTHM: the
   second voice moves when the melody holds and holds when it moves), thirds / sixths
   (same rhythm, the interval preferred), melody_acc (long chord tones), pedal (root or
   fifth held), canon_bar / canon_half / dialogue / echo (IMITATION: the melody one bar /
   half a bar later, moved by an octave, fifth or fourth, the counterpoint rules adjusting
   it), mirror (same rhythm, contrary motion preferred);
4. ROLES: the melody is on trumpet 1 or (30 %) on trumpet 2, period by period (log '*').
Lines at WRITTEN pitch for the Bb trumpet, as duet.py. No Qt.
"""
import bisect
import random

from . import duet as _duet
from . import melodygen as mg

EPS = 1e-6
LEVEL_DIFFICULTY = {1: 2.0, 2: 4.0, 3: 6.0}     # melodygen level of the melody
COUNTER_LEAP = {1: 5, 2: 7, 3: 9}
TEXTURE_KIND = {"thirds": "parallel", "sixths": "parallel", "melody_acc": "melody_acc",
                "pedal": "pedal", "dialogue": "imitation", "echo": "imitation",
                "canon_bar": "imitation", "canon_half": "imitation", "mirror": "mirror",
                "counterpoint": "counterpoint"}
DISSONANT = (1, 2, 10, 11)
MELODY_ON_2 = .3                                 # share of periods with the melody on trumpet 2


def is_strong(t):
    return _duet.is_strong(t)


def _cells(count, level):
    """Second voice in half a bar where the melody has `count` onsets (complementary)."""
    if count >= 3:
        return [[2.0]] + ([[1.0, 1.0]] if level >= 2 else [])
    if count == 2:
        return [[1.0, 1.0], [2.0]] + ([[1.5, .5]] if level >= 2 else [])
    return ([[1.0, 1.0]] + ([[.5, .5, 1.0], [1.0, .5, .5]] if level >= 2 else [])
            + ([[.5, .5, .5, .5]] if level >= 3 else []))


def _split(H, t0):
    return any(t0 + EPS < s[0] < t0 + 4.0 - EPS for s in H.segs)


def counter_rhythm(mel, H, form, kind, name, level, rng, lo, hi, role):
    """Events (start, dur, proposal pitch or None) of the second voice."""
    n = len(form)
    if kind in ("parallel", "mirror"):
        return [(s, d, None) for s, d, _ in mel]
    ev = []
    if kind == "imitation":
        D = 2.0 if name == "canon_half" else 4.0
        offs = [-12, -7, -5, 0] if role == "below" else [12, 7, 5, 0]
        rng.shuffle(offs)
        off = min(offs, key=lambda o: sum(1 for _, _, p in mel if not lo <= p + o <= hi))
        end = 4.0 * (n - 1)
        for s, d, p in mel:
            ns = s + D
            if ns >= end - EPS:
                break
            ev.append((ns, min(d, end - ns), p + off))
        t0 = end
        ev += [(t0, 2.0, None), (t0 + 2.0, 2.0, None)] if _split(H, t0) else [(t0, 4.0, None)]
        return ev
    onsets = [s for s, _, _ in mel]
    for b, f in enumerate(form):
        t0 = 4.0 * b
        if f["role"] == "cad" or kind in ("melody_acc", "pedal"):
            two = _split(H, t0) or (kind == "melody_acc" and f["role"] != "cad"
                                    and level >= 2 and rng.random() < .4)
            ev += [(t0, 2.0, None), (t0 + 2.0, 2.0, None)] if two else [(t0, 4.0, None)]
            continue
        for h in (0.0, 2.0):
            a = t0 + h
            cnt = sum(1 for s in onsets if a - EPS <= s < a + 2.0 - EPS)
            t = a
            for d in rng.choice(_cells(cnt, level)):
                ev.append((t, d, None))
                t += d
    return ev


def counter_line(mel, H, key, form, role, lo, hi, kind, name, level, rng, final):
    """The second voice: [(start, dur, pitch)] by a second-order Viterbi search."""
    mel = sorted(mel)
    starts = [s for s, _, _ in mel]

    def m_at(t):
        i = bisect.bisect_right(starts, t + EPS) - 1
        if i >= 0 and mel[i][0] + mel[i][1] > t + EPS:
            return mel[i][2]
        return None

    def m_onsets(t0, t1):
        return [(s, p) for s, _, p in mel if t0 + EPS < s < t1 - EPS]

    ev = counter_rhythm(mel, H, form, kind, name, level, rng, lo, hi, role)
    if not ev:
        return []
    leap = COUNTER_LEAP.get(level, 7)
    pref = (3, 4) if name == "thirds" else ((8, 9) if name == "sixths" else None)
    C = [[p for p in range(lo, hi + 1) if p % 12 in H.scale(s)] for s, _, _ in ev]
    last = len(ev) - 1

    def unary(k, p):
        s, d, prop = ev[k]
        pcs, root = H.pcs(s), H.root(s)
        ct = p % 12 in pcs
        c = rng.uniform(0, .7)
        if not ct:
            c += 5.0 if is_strong(s) else 0.0
            if kind in ("melody_acc", "pedal"):
                c += 6.0
        if kind == "pedal":
            c += 0.0 if p % 12 in (root, (root + 7) % 12) else 4.0
        elif kind == "melody_acc":
            c += 0.0 if p % 12 == root else (.6 if ct else 0.0)
        for t, m in [(s, m_at(s))] + m_onsets(s, s + d):
            if m is None:
                continue
            st = is_strong(t)
            iv = abs(p - m)
            cls = iv % 12
            if (role == "below" and p > m) or (role == "above" and p < m):
                c += 12.0
            if p == m:
                c += 3.0
            elif cls in DISSONANT:
                c += 12.0 if st else 2.5
            elif cls == 6:
                c += 4.0 if st else 2.0
            elif cls == 5 and role == "below":
                c += 3.0 if st else .8
            elif cls in (0, 7) and st:
                c += 1.0
            if iv > 19:
                c += iv - 19
            if pref and cls not in pref:
                c += 2.5 if st else 1.5
        if prop is not None:
            c += .8 * abs(p - prop)
        if final and k == last:
            if role == "below" and p % 12 != root:
                c += 6.0
            if not ct:
                c += 6.0
        return c

    def pair(k, q, p):
        sq, sp = ev[k - 1][0], ev[k][0]
        ic = mg.icost(q, p, leap)
        c = 10.0 + abs(p - q) if ic is None else ic
        if kind == "pedal" and p == q:
            c -= 1.0
        if key.minor and abs(p - q) == 3 and {p % 12, q % 12} == {key.pcs[5], key.lead}:
            c += 10.0
        if p % 12 not in H.pcs(sp) and not 0 < abs(p - q) <= 2:
            c += 6.0
        mq, mp = m_at(sq), m_at(sp)
        if mq is not None and mp is not None:
            dc = (p > q) - (p < q)
            dm = (mp > mq) - (mp < mq)
            cp, cq = abs(p - mp) % 12, abs(q - mq) % 12
            if cp in (0, 7) and dc == dm != 0:
                c += 40.0 if cq == cp else (6.0 if abs(mp - mq) > 2 else 0.0)
            if kind == "parallel":
                c += 0.0 if dc == dm else 1.0
            elif kind == "mirror":
                c += -.5 if dc * dm < 0 else 1.0
            else:
                c += 0.0 if dc * dm < 0 else (.4 if dc == 0 or dm == 0 else 1.0)
        return c

    def triple(k, q0, q1, p):
        c = 0.0
        if q1 % 12 not in H.pcs(ev[k - 1][0]) and not 0 < abs(p - q1) <= 2:
            c += 6.0
        if q0 is not None and abs(q1 - q0) >= 5 and (p - q1) * (q1 - q0) > 0:
            c += 2.0
        return c

    backs = [{(None, p): (unary(0, p), None) for p in C[0]}]
    for k in range(1, len(ev)):
        U = {p: unary(k, p) for p in C[k]}
        PC = {(q, p): pair(k, q, p) for q in C[k - 1] for p in C[k]}
        new = {}
        for (q0, q1), (cst, _) in backs[-1].items():
            for p in C[k]:
                v = cst + PC[(q1, p)] + triple(k, q0, q1, p) + U[p]
                key2 = (q1, p)
                if key2 not in new or v < new[key2][0]:
                    new[key2] = (v, q0)
        backs.append(new)
    state = min(backs[-1], key=lambda kk: backs[-1][kk][0])
    seq = [state[1]]
    for k in range(len(backs) - 1, 0, -1):
        q0 = backs[k][state][1]
        state = (q0, state[0])
        seq.append(state[1])
    seq.reverse()
    return [(s, d, p) for (s, d, _), p in zip(ev, seq)]


def generate(bars, kpc, minor, level, allowed, seed, phrase=4, repetition=0.7):
    """bars as duet.parse_progression (written, shifted); returns the dict of
    duet.generate_duet (t1, t2 written pitch, kpc, minor, nbars, seed, log)."""
    r = random.Random(seed)
    key = mg.Key(kpc, "aeolian" if minor else "ionian")
    cbars = [[(root, [(root + i) % 12 for i in _duet.QUALITIES[q]], beats)
              for root, q, beats in bar] for bar in bars]
    H = mg.harmony_from_chords(cbars, key)
    cfg = _duet.LEVELS[level]
    up, low = cfg["upper"], cfg["lower"]
    n, P = len(bars), max(1, int(phrase))
    T1, T2, log = [], [], []
    prev_kind = None
    starts = list(range(0, n, 2 * P))
    for k, b0 in enumerate(starts):
        b1 = min(n, b0 + 2 * P)
        final = b1 == n
        name = r.choice([t for t in allowed if TEXTURE_KIND[t] != prev_kind] or list(allowed))
        kind = TEXTURE_KIND[name]
        prev_kind = kind
        mel_t1 = k == 0 or r.random() >= MELODY_ON_2
        mlo, mhi = up if mel_t1 else low
        clo, chi = low if mel_t1 else up
        if kind == "parallel":
            gap = 9 if name == "sixths" else 4
            if mel_t1:
                mlo = max(mlo, low[0] + gap)
            else:
                mhi = min(mhi, up[1] - gap)
        form = mg.phrase_form(b1 - b0, P, r, repetition, final=final)
        Hs = H.shifted(4.0 * b0, 4.0 * b1)
        mel = mg.compose(form, Hs, key, (4, 4), mlo, mhi, LEVEL_DIFFICULTY[level], r,
                         "skeleton")
        cnt = counter_line(mel, Hs, key, form, "below" if mel_t1 else "above", clo, chi,
                           kind, name, level, r, final)
        off = 4.0 * b0
        mel = [(s + off, d, p) for s, d, p in mel]
        cnt = [(s + off, d, p) for s, d, p in cnt]
        if mel_t1:
            T1 += mel
            T2 += cnt
        else:
            T1 += cnt
            T2 += mel
        log.append(name + ("" if mel_t1 else "*"))
    return dict(t1=T1, t2=T2, kpc=kpc, minor=minor, nbars=n, seed=seed, log=log)
