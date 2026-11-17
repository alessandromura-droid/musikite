#!/usr/bin/env python3
"""
canon_trumpets.py

Generate a very simple canon for two Bb trumpets as a MIDI file, starting
from a chord progression.

Pitches in the MIDI file are WRITTEN pitches for Bb trumpet (a real Bb
trumpet sounds a major second lower). By default the chord symbols (and
--key) are interpreted as CONCERT pitch and transposed up a major second;
use --written if you give them already in written (trumpet) pitch.

Canon structure:
  - trumpet 1 plays the progression N times (--cycles), each time with new
    melodic material;
  - trumpet 2 enters one full progression later and plays exactly what
    trumpet 1 played in the previous cycle (delay = length of the
    progression, so every line always fits the harmony);
  - while trumpet 2 plays its last cycle, trumpet 1 holds long chord tones;
  - both end on the tonic chord.

Chord symbols: English (C D E F G A B) or Italian (Do Re Mi Fa Sol La Si),
with # or b, followed by a quality:
  (none) maj M | m min - | 7 | m7 -7 | maj7 M7 | 6 | m6 | dim | dim7 |
  m7b5 | aug + | sus4 sus | sus2
Slash chords (C/E) are accepted; the bass note is ignored.

No external dependencies: the MIDI file is written directly.
"""
import argparse
import random
import re
import struct
import sys

TPQ = 480               # ticks per quarter note
TRUMPET_PROGRAM = 56    # General MIDI "Trumpet" (0-based)

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

# difficulty -> written range (MIDI note numbers), max leap (semitones),
# non-chord (passing/neighbour) tones allowed
LEVELS = {
    1: dict(low=60, high=72, max_leap=5, nct=False),    # C4-C5
    2: dict(low=57, high=74, max_leap=7, nct=False),    # A3-D5
    3: dict(low=55, high=76, max_leap=7, nct=True),     # G3-E5
    4: dict(low=55, high=79, max_leap=9, nct=True),     # G3-G5
    5: dict(low=55, high=79, max_leap=12, nct=True),    # G3-G5
}
# difficulty -> (duration in beats, weight); 0.5 = pair of eighth notes
# level 1: one note per chord
RHYTHMS = {
    2: [(4, 1), (2, 3)],
    3: [(2, 1), (1, 3)],
    4: [(2, 1), (1, 5), (0.5, 3)],
    5: [(1, 2), (0.5, 3)],
}


# --------------------------------------------------------------------------
# Harmony
# --------------------------------------------------------------------------
def split_symbol(sym):
    m = ROOT_RE.match(sym.split('/')[0])
    if not m:
        sys.exit(f"Cannot parse chord '{sym}'")
    name, acc, qual = m.groups()
    pc = PC_IT.get(name, PC_EN.get(name))
    pc += {'#': 1, 'b': -1, '': 0}[acc]
    if qual not in QUALITIES:
        sys.exit(f"Unknown chord quality '{qual}' in '{sym}'")
    return pc, qual


def parse_chord(sym, shift):
    pc, qual = split_symbol(sym)
    return (pc + shift) % 12, QUALITIES[qual], qual


def parse_key(sym, shift):
    pc, qual = split_symbol(sym)
    minor = qual in MINOR_QUALITIES
    return (pc + shift) % 12, minor


def nct_pcs(chord_set, scale_set):
    """Scale tones usable as passing/neighbour tones over this chord."""
    out = set()
    for pc in scale_set - chord_set:
        bad = any(((pc + d) % 12 in chord_set) and ((pc + d) % 12 not in scale_set)
                  for d in (-1, 1))
        if not bad:
            out.add(pc)
    return out


# --------------------------------------------------------------------------
# Melody generation
# --------------------------------------------------------------------------
def make_rhythm(span, level, r):
    out = []
    left = float(span)
    while left > 1e-9:
        opts = [(d, w) for d, w in RHYTHMS[level]
                if (1.0 if d == 0.5 else d) <= left + 1e-9]
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


def sounding(notes, t):
    for s, d, p in notes:
        if s <= t + 1e-9 and t < s + d - 1e-9:
            return p
    return None


def choose(cands, prev, other, strong, cfg, center, r):
    best, best_s = None, None
    for p in cands:
        s = 0.0
        if prev is not None:
            leap = abs(p - prev)
            if leap > cfg['max_leap']:
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


def generate_cycle(chords, bpc, level, cfg, scale_set, other, prev, r,
                   long_notes=False):
    lo, hi = cfg['low'], cfg['high']
    center = (lo + hi) / 2.0
    notes = []
    t = 0.0
    prev_nct = False
    for root, ivs, _ in chords:
        cset = {(root + i) % 12 for i in ivs}
        ct = [p for p in range(lo, hi + 1) if p % 12 in cset]
        nset = nct_pcs(cset, scale_set) if (cfg['nct'] and not long_notes) else set()
        nt = [p for p in range(lo, hi + 1) if p % 12 in nset]
        if long_notes or level == 1:
            durs = [float(bpc)]
        else:
            durs = make_rhythm(bpc, level, r)
        for i, d in enumerate(durs):
            on_beat = abs(t - round(t)) < 1e-9
            strong = i == 0 or (on_beat and round(t) % 2 == 0)
            other_p = sounding(other, t) if other else None
            if prev_nct:
                # resolve a non-chord tone by step onto a chord tone
                cands = [p for p in ct if 1 <= abs(p - prev) <= 2] or ct
            else:
                cands = list(ct)
                if nt and prev is not None and 0 < i < len(durs) - 1:
                    cands += [p for p in nt if 1 <= abs(p - prev) <= 2]
            p = choose(cands, prev, other_p, strong, cfg, center, r)
            prev_nct = p % 12 not in cset
            notes.append((t, d, p))
            prev = p
            t += d
    return notes, prev


# --------------------------------------------------------------------------
# MIDI writing
# --------------------------------------------------------------------------
def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def meta(kind, payload):
    return b'\xFF' + bytes([kind]) + vlq(len(payload)) + payload


def track_chunk(events):
    events.sort(key=lambda e: (e[0], e[1]))
    data = b''
    last = 0
    for tick, _, ev in events:
        data += vlq(tick - last) + ev
        last = tick
    data += vlq(0) + b'\xFF\x2F\x00'
    return b'MTrk' + struct.pack('>I', len(data)) + data


def voice_track(name, channel, notes, velocity=80):
    ev = [(0, -2, meta(0x03, name.encode('ascii'))),
          (0, -1, bytes([0xC0 | channel, TRUMPET_PROGRAM]))]
    for s, d, p in notes:
        on = int(round(s * TPQ))
        off = int(round((s + d) * TPQ))
        ev.append((on, 1, bytes([0x90 | channel, p, velocity])))
        ev.append((off, 0, bytes([0x80 | channel, p, 0])))
    return track_chunk(ev)


def write_midi(path, v1, v2, bpm):
    us = int(round(60_000_000 / bpm))
    tempo = [(0, 0, meta(0x03, b'Canon for two Bb trumpets')),
             (0, 1, meta(0x51, us.to_bytes(3, 'big'))),
             (0, 2, meta(0x58, bytes([4, 2, 24, 8])))]
    with open(path, 'wb') as f:
        f.write(b'MThd' + struct.pack('>IHHH', 6, 1, 3, TPQ))
        f.write(track_chunk(tempo))
        f.write(voice_track('Trumpet 1 in Bb', 0, v1))
        f.write(voice_track('Trumpet 2 in Bb', 1, v2))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description='Very simple canon for two Bb trumpets (MIDI, written pitch).')
    ap.add_argument('-c', '--chords', required=True,
                    help='chord progression, e.g. "D A Bm F#m G D G A" '
                         'or "Re La Sim Fa#m Sol Re Sol La"')
    ap.add_argument('-d', '--difficulty', type=int, default=2, choices=range(1, 6),
                    help='1 = one long note per chord ... 5 = eighth notes (default 2)')
    ap.add_argument('-b', '--beats-per-chord', type=int, default=4,
                    help='quarter-note beats per chord (default 4)')
    ap.add_argument('-n', '--cycles', type=int, default=4,
                    help='times trumpet 1 plays the progression (default 4)')
    ap.add_argument('-k', '--key',
                    help='key for passing tones, e.g. D or Bm (default: first chord)')
    ap.add_argument('-w', '--written', action='store_true',
                    help='chords and key are given in written (trumpet) pitch, '
                         'not concert pitch')
    ap.add_argument('-t', '--bpm', type=float, default=80, help='tempo (default 80)')
    ap.add_argument('-s', '--seed', type=int, help='random seed (same seed = same piece)')
    ap.add_argument('-o', '--out', default='canon.mid', help='output MIDI file')
    a = ap.parse_args()

    shift = 0 if a.written else 2
    symbols = [s for s in re.split(r'[\s,|]+', a.chords.strip()) if s]
    chords = [parse_chord(s, shift) for s in symbols]
    if a.key:
        kpc, minor = parse_key(a.key, shift)
    else:
        kpc, minor = chords[0][0], chords[0][2] in MINOR_QUALITIES
    scale_set = {(kpc + i) % 12 for i in (MINOR_SCALE if minor else MAJOR_SCALE)}

    cfg = LEVELS[a.difficulty]
    r = random.Random(a.seed)
    bpc = a.beats_per_chord
    L = len(chords) * bpc

    # trumpet 1 cycles (trumpet 2 plays cycle k-1 while trumpet 1 plays k)
    cycles = []
    prev1 = None
    for k in range(a.cycles):
        other = cycles[k - 1] if k > 0 else []
        notes, prev1 = generate_cycle(chords, bpc, a.difficulty, cfg, scale_set,
                                      other, prev1, r)
        cycles.append(notes)

    v1, v2 = [], []
    for k, notes in enumerate(cycles):
        v1 += [(s + k * L, d, p) for s, d, p in notes]
        v2 += [(s + (k + 1) * L, d, p) for s, d, p in notes]

    # coda for trumpet 1: long chord tones under trumpet 2's last cycle
    coda, prev1 = generate_cycle(chords, bpc, 1, cfg, scale_set, cycles[-1],
                                 prev1, r, long_notes=True)
    v1 += [(s + a.cycles * L, d, p) for s, d, p in coda]

    # final tonic chord (one 4/4 bar)
    t_end = (a.cycles + 1) * L
    tonic = {(kpc + i) % 12 for i in ((0, 3, 7) if minor else (0, 4, 7))}
    prev2 = cycles[-1][-1][2]
    roots = [p for p in range(cfg['low'], cfg['high'] + 1) if p % 12 == kpc]
    f2 = min(roots, key=lambda p: abs(p - prev2))
    good = (3, 4, 7, 8, 9)
    tones = [p for p in range(cfg['low'], cfg['high'] + 1) if p % 12 in tonic and p != f2]
    f1 = min(tones, key=lambda p: abs(p - prev1) + (0 if abs(p - f2) in good else 10))
    v1.append((t_end, 4.0, f1))
    v2.append((t_end, 4.0, f2))

    write_midi(a.out, v1, v2, a.bpm)
    print(f'Written {a.out}: {len(chords)} chords x {a.cycles} cycles, '
          f'difficulty {a.difficulty}, {"written" if a.written else "concert"} chords')


if __name__ == '__main__':
    main()
