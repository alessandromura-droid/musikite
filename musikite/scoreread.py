#!/usr/bin/env python3
"""
trumpet_fingering.py - write Bb trumpet valve fingerings under the notes of a
single-staff, vector PDF (exported by a notation program).

Usage:
    python3 trumpet_fingering.py score.pdf [--fontsize 12] [--font Arial.ttf]
                                           [--space 12] [--color k]
                                           [--no_repetition true]
    python3 trumpet_fingering.py score.pdf --midi [--instrument NAME]
Output: score.noted.pdf (fingerings, trumpet only), or score.from_pdf.mid with
        --midi (concert pitch, repeats / voltas / D.C. / D.S. / Coda expanded).
The instrument is read from the PDF text (see INSTRUMENTS) unless --instrument
is given; if it cannot be identified the script stops with an error.

Requirements: PyMuPDF (pip install pymupdf).
The file TrumpetFing.ttf (glyphs 12, 23, 13, 123) must sit next to this script.

Supported music fonts: SMuFL fonts (Bravura, Leland, Petaluma, Finale Maestro,
Sebastian, ...) and Sonata-compatible fonts (Maestro, Opus, Petrucci, Jazz,
Engraver, Broadway, Sonata, ...). Notes are read as written pitch, treble clef.
"""

import argparse
import os
import sys
import re
import statistics
from fractions import Fraction as F
import pymupdf

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# inside the musikite package: the font is in musikite/data (also in a packaged app);
# the log goes to ~/.musikite (the package folder may not be writable)
FING_FONT = os.path.join(SCRIPT_DIR, "data", "TrumpetFing.ttf")
LOG_DIR = os.path.join(os.path.expanduser("~"), ".musikite")
DEFAULT_LOG = os.path.join(LOG_DIR, "scoreread.log")
DEFAULT_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"

# ---------------------------------------------------------------- fingerings
# Written pitch (MIDI number) -> valve combination, Bb trumpet.
FINGERING = {
    54: "123", 55: "13", 56: "23", 57: "12", 58: "1", 59: "2", 60: "0",
    61: "123", 62: "13", 63: "23", 64: "12", 65: "1", 66: "2", 67: "0",
    68: "23", 69: "12", 70: "1", 71: "2", 72: "0",
    73: "12", 74: "1", 75: "2", 76: "0", 77: "1", 78: "2", 79: "0",
    80: "23", 81: "12", 82: "1", 83: "2", 84: "0",
    85: "12", 86: "1", 87: "2", 88: "0", 89: "1", 90: "2", 91: "0",
}
# Combined glyphs in TrumpetFing.ttf (private use area)
COMBO = {"12": "", "23": "", "13": "", "123": ""}

COLORS = {"r": (1, 0, 0), "g": (0, 0.5, 0), "b": (0, 0, 1), "k": (0, 0, 0)}

# ---------------------------------------------------------------- music glyphs
# kind: 'head' (value = base duration in quarters) | 'acc' (alteration) |
#       'bar' | 'rest' (duration, 'W' = whole-bar rest) | 'flag' (n. of flags) |
#       'dot' | 'digit' (value) | 'tsig' ((num, den))
SMUFL = {
    0xE0A0: ("head", F(8)), 0xE0A1: ("head", F(8)), 0xE0A2: ("head", F(4)),
    0xE0A3: ("head", F(2)), 0xE0A4: ("head", F(1)),
    0xE4E3: ("rest", "W"), 0xE4E4: ("rest", F(2)), 0xE4E5: ("rest", F(1)),
    0xE4E6: ("rest", F(1, 2)), 0xE4E7: ("rest", F(1, 4)), 0xE4E8: ("rest", F(1, 8)),
    0xE4E9: ("rest", F(1, 16)),
    0xE240: ("flag", 1), 0xE241: ("flag", 1), 0xE242: ("flag", 2),
    0xE243: ("flag", 2), 0xE244: ("flag", 3), 0xE245: ("flag", 3),
    0xE246: ("flag", 4), 0xE247: ("flag", 4),
    0xE1E7: ("dot", None),
    0xE08A: ("tsig", (4, 4)), 0xE08B: ("tsig", (2, 2)),
    0xE050: ("clef", ("G", 0)), 0xE052: ("clef", ("G", -7)), 0xE053: ("clef", ("G", 7)),
    0xE062: ("clef", ("F", 0)), 0xE064: ("clef", ("F", -7)), 0xE05C: ("clef", ("C", 0)),
    0xE069: ("clef", ("P", 0)), 0xE06A: ("clef", ("P", 0)),
    0xE043: ("rdots", None), 0xE044: ("dot", None),
    0xE047: ("segno", None), 0xE048: ("coda", None),
    0xE0A8: ("head", F(4)), 0xE0A9: ("head", F(2)), 0xE0AA: ("head", F(1)),
    0xE260: ("acc", -1), 0xE261: ("acc", 0), 0xE262: ("acc", 1),
    0xE263: ("acc", 2), 0xE264: ("acc", -2),
    0xE030: ("bar", None), 0xE031: ("bar", None), 0xE032: ("bar", None),
    0xE033: ("bar", None), 0xE034: ("bar", None),
    0xE040: ("rep", "start"), 0xE041: ("rep", "end"), 0xE042: ("rep", "both"),
}
for _d in range(10):
    SMUFL[0xE080 + _d] = ("digit", _d)
SONATA = {
    0xCF: ("head", F(1)), 0xFA: ("head", F(2)), 0x77: ("head", F(4)),
    0x57: ("head", F(8)),
    0x62: ("acc", -1), 0x6E: ("acc", 0), 0x23: ("acc", 1),
    0xDC: ("acc", 2), 0xBA: ("acc", -2),
    0xB7: ("rest", "W"), 0xEE: ("rest", F(2)), 0xD3: ("rest", F(2)), 0xCE: ("rest", F(1)),
    0xE4: ("rest", F(1, 2)), 0xC5: ("rest", F(1, 4)), 0xA8: ("rest", F(1, 8)),
    0x6A: ("flag", 1), 0x4A: ("flag", 1), 0x72: ("flag", 2), 0x52: ("flag", 2),
    0x4B: ("flag", 1), 0xEF: ("flag", 1),               # extra flag (32nd, 64th)
    0x6B: ("dot", None), 0x2E: ("dot", None),
    0x63: ("tsig", (4, 4)), 0x43: ("tsig", (2, 2)),
    0x26: ("clef", ("G", 0)), 0x3F: ("clef", ("F", 0)), 0x42: ("clef", ("C", 0)),
    0x56: ("clef", ("G", -7)),
    0x25: ("segno", None), 0xDE: ("coda", None),
    0xC0: ("head", F(1)),
}
for _d in range(10):
    SONATA[0x30 + _d] = ("digit", _d)
SONATA_FONTS = ("maestro", "opus", "petrucci", "sonata", "jazz", "engraver",
                "broadway", "inkpen", "reprise", "golden", "tamburo", "anastasia",
                "pmusic")

# Key signature order as letters (C = 0 ... B = 6)
SHARP_ORDER = [3, 0, 4, 1, 5, 2, 6]           # F C G D A E B
FLAT_ORDER = [6, 2, 5, 1, 4, 0, 3]            # B E A D G C F
STEP_SEMI = [0, 2, 4, 5, 7, 9, 11]
E4_DN = 30                                     # bottom line of treble staff
G2_DN = 18                                     # bottom line of bass staff

# ---------------------------------------------------------------- instruments
# slug: (keywords, transposition in semitones (sound = written + T) for
#        treble clef, for bass clef, GM program, percussion key or None,
#        default bottom-line diatonic number, number of staves per system)
INSTRUMENTS = {
    "accordion":     (["Accordion", "Fisarmonica"], 0, 0, 21, None, E4_DN, 2),
    "banjo":         (["Banjo"], -12, -12, 105, None, E4_DN, 1),
    "clarinet":      (["Clarinet in Bb", "Clarinetto in SIb"], -2, -2, 71, None, E4_DN, 1),
    "bass_clarinet": (["Bass Clarinet in Bb"], -14, -2, 71, None, E4_DN, 1),
    "horn":          (["Horn in F", "Corno in F"], -7, -7, 60, None, E4_DN, 1),
    "bass_drum":     (["Bass Drum", "Grancassa"], 0, 0, 0, 36, E4_DN, 1),
    "snare_drum":    (["Snare Drum", "Rullante"], 0, 0, 0, 38, E4_DN, 1),
    "cymbals":       (["Cymbals", "Piatti"], 0, 0, 0, 49, E4_DN, 1),
    "timpani":       (["Timpani"], 0, 0, 47, None, G2_DN, 1),
    "euphonium":     (["Euphonium", "Eufonio"], -14, 0, 58, None, G2_DN, 1),
    "flute":         (["Flute", "Flauto"], 0, 0, 73, None, E4_DN, 1),
    "oboe":          (["Oboe"], 0, 0, 68, None, E4_DN, 1),
    "piccolo":       (["Piccolo", "Ottavino"], 12, 12, 72, None, E4_DN, 1),
    "alto_sax":      (["Alto Saxophone", "Sax alto"], -9, -9, 65, None, E4_DN, 1),
    "baritone_sax":  (["Baritone Saxophone", "Sax Baritono"], -21, -21, 67, None, E4_DN, 1),
    "soprano_sax":   (["Soprano Saxophone", "Sax soprano"], -2, -2, 64, None, E4_DN, 1),
    "tenor_sax":     (["Tenor Saxophone", "Sax Tenore"], -14, -14, 66, None, E4_DN, 1),
    "trumpet":       (["Trumpet", "Tromba", "Trumpet in Bb", "Tromba in SIb"], -2, -2, 56, None, E4_DN, 1),
    "trombone":      (["Trombone"], -14, 0, 57, None, G2_DN, 1),
    "tuba":          (["Tuba"], -26, 0, 58, None, G2_DN, 1),
    "violin":        (["Violin", "Violino"], 0, 0, 40, None, E4_DN, 1),
    "cello":         (["Violoncello"], 0, 0, 42, None, G2_DN, 1),
}


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("true", "t", "yes", "y", "1"):
        return True
    if v.lower() in ("false", "f", "no", "n", "0"):
        return False
    raise argparse.ArgumentTypeError("expected true/false")


def classify(font, code):
    if code in SMUFL:
        return SMUFL[code]
    f = font.lower()
    if 0xF000 <= code <= 0xF0FF:      # symbol fonts mapped to U+F0xx
        code -= 0xF000
    elif code > 0xFF:                 # Sibelius "Std" fonts: Mac Roman mapping
        try:
            code = chr(code).encode("mac_roman")[0]
        except (UnicodeEncodeError, ValueError):
            pass
    if "text" in f or "chord" in f:   # text / chord-symbol fonts of the notation program
        return None
    if "special" in f:                # OpusSpecial: augmentation dot
        return ("dot", None) if code == 0xAA else None
    if any(k in f for k in SONATA_FONTS) and code in SONATA:
        return SONATA[code]
    return None


# ---------------------------------------------------------------- page parsing
def segments(page):
    """Return horizontal and vertical segments as (x0, y0, x1, y1, thickness)
    and the bounding rectangles of curved paths (ties/slurs)."""
    hor, ver, curves, polys = [], [], [], []
    slant = []
    for p in page.get_drawings():
        w = p.get("width") or 0
        if "f" in (p.get("type") or ""):
            its = p["items"]
            if its and all(it[0] == "l" for it in its) and len(its) >= 3:
                polys.append([it[1] for it in its] + [its[-1][2]])
            elif len(its) == 1 and its[0][0] == "re":
                r = its[0][1]
                polys.append([r.tl, r.tr, r.br, r.bl])
            elif len(its) == 1 and its[0][0] == "qu":
                q = its[0][1]
                polys.append([q.ul, q.ur, q.lr, q.ll])
        if any(it[0] == "c" for it in p["items"]):
            r = p["rect"]
            if not any(abs(r.x0 - q.x0) < 0.5 and abs(r.x1 - q.x1) < 0.5 and
                       abs(r.y0 - q.y0) < 1 for q in curves):
                curves.append(r)
        for it in p["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 0.2:
                    hor.append((min(a.x, b.x), a.y, max(a.x, b.x), a.y, w))
                elif abs(a.x - b.x) < 0.2:
                    ver.append((a.x, min(a.y, b.y), a.x, max(a.y, b.y), w))
                elif abs(a.y - b.y) < 0.35 * abs(a.x - b.x) and "f" not in (p.get("type") or ""):
                    l, r_ = (a, b) if a.x < b.x else (b, a)
                    slant.append((l.x, l.y, r_.x, r_.y))
            elif it[0] == "re":
                r = it[1]
                if r.height < 1.5 and r.width > 3 * r.height:
                    hor.append((r.x0, (r.y0 + r.y1) / 2, r.x1, (r.y0 + r.y1) / 2, r.height))
                elif r.width < 4 and r.height > 3 * r.width:
                    ver.append(((r.x0 + r.x1) / 2, r.y0, (r.x0 + r.x1) / 2, r.y1, r.width))
            elif it[0] == "qu":
                r = it[1].rect
                if r.height < 1.5 and r.width > 3 * r.height:
                    hor.append((r.x0, (r.y0 + r.y1) / 2, r.x1, (r.y0 + r.y1) / 2, r.height))
                elif r.width < 4 and r.height > 3 * r.width:
                    ver.append(((r.x0 + r.x1) / 2, r.y0, (r.x0 + r.x1) / 2, r.y1, r.width))
    segments.slant = slant
    return hor, ver, curves, polys


def find_staves(hor):
    """Merge collinear horizontal segments and group them in 5-line staves."""
    # short pieces (ledger lines) never belong to staff lines, even when
    # dense ledger lines touch each other
    hor = sorted((h for h in hor if h[2] - h[0] >= 15), key=lambda s: (round(s[1], 1), s[0]))
    lines = []
    for x0, y, x1, _, w in hor:
        for L in lines:
            if (abs(L[1] - y) < 0.3 and abs(L[3] - w) < 0.1
                    and x0 <= L[2] + 0.5 and x1 >= L[0] - 0.5):
                L[0], L[2] = min(L[0], x0), max(L[2], x1)
                break
        else:
            lines.append([x0, y, x1, w])
    lines = [L for L in lines if L[2] - L[0] > 60]
    lines.sort(key=lambda L: L[1])
    staves, used = [], set()
    for i in range(len(lines)):
        if i in used:
            continue
        group = [i]
        for j in range(i + 1, len(lines)):
            if len(group) == 5:
                break
            if j in used:
                continue
            a, b = lines[group[-1]], lines[j]
            if b[0] > a[2] or b[2] < a[0]:
                continue
            if b[2] - b[0] < 0.5 * (a[2] - a[0]):
                continue                 # much shorter: not a staff line (e.g. rest bar)
            gap = b[1] - a[1]
            # the next overlapping line below must be the next staff line
            if len(group) == 1:
                if 2 < gap < 20:
                    group.append(j)
                else:
                    break
            else:
                ref = lines[group[1]][1] - lines[group[0]][1]
                if abs(gap - ref) < 0.15 * ref:
                    group.append(j)
                else:
                    break
        if len(group) == 5:
            used.update(group)
            ys = [lines[k][1] for k in group]
            staves.append({
                "top": ys[0], "bot": ys[4], "s": (ys[4] - ys[0]) / 4,
                "x0": min(lines[k][0] for k in group),
                "x1": max(lines[k][2] for k in group),
                "heads": [], "accs": [], "bars": [], "curves": [],
                "tuplets": [], "obstacles": [], "rests": [], "flags": [],
                "dots": [], "tsd": [], "tsig": [], "tdig": [], "tups": [],
                "multirests": [], "polys": [], "clefs": [], "reps": [],
                "signs": [], "texts": [], "single": False,
            })
    return staves


def single_line_staves(hor, staves, s_est, ver=()):
    """One-line (percussion) staves: long lines not belonging to 5-line staves."""
    used = set()
    for st in staves:
        used.add(round(st["top"], 0))
    hor = sorted(hor, key=lambda q: (round(q[1], 1), q[0]))
    lines = []
    for x0, y, x1, _, _ in hor:
        for L in lines:
            if abs(L[1] - y) < 0.3 and x0 <= L[2] + 0.5 and x1 >= L[0] - 0.5:
                L[0], L[2] = min(L[0], x0), max(L[2], x1)
                break
        else:
            lines.append([x0, y, x1])
    out = []
    for x0, y, x1 in lines:
        if x1 - x0 < 100:
            continue
        if any(st["top"] - 0.5 <= y <= st["bot"] + 0.5 and st["x0"] - 1 <= x0 for st in staves):
            continue
        # a staff line is crossed by barlines (volta brackets are not)
        if ver and not any(x0 - 1 <= vx <= x1 + 1 and vy0 < y - 0.5 * s_est and vy1 > y + 0.5 * s_est
                           and vy1 - vy0 < 6 * s_est for vx, vy0, _, vy1, _ in ver):
            continue
        out.append({
            "top": y - 2 * s_est, "bot": y + 2 * s_est, "s": s_est, "line": y,
            "x0": x0, "x1": x1,
            "heads": [], "accs": [], "bars": [], "curves": [],
            "tuplets": [], "obstacles": [], "rests": [], "flags": [],
            "dots": [], "tsd": [], "tsig": [], "tdig": [], "tups": [],
            "multirests": [], "polys": [], "clefs": [], "reps": [],
            "signs": [], "texts": [], "single": True,
        })
    return out


def nearest_staff(staves, x, y):
    best, bd = None, None
    for st in staves:
        if not (st["x0"] - 2 * st["s"] <= x <= st["x1"] + 2 * st["s"]):
            continue
        # distance from the staff (0 inside it)
        d = max(st["top"] - y, y - st["bot"], 0)
        if d < 6 * st["s"] and (bd is None or d < bd):
            best, bd = st, d
    return best


def reassign_symbols(staves, hor, ver=()):
    """Close staves: a note above/below a staff may be nearer to the
    neighbouring staff. Ledger lines tell which staff it belongs to; the
    accidentals, dots, flags and beams follow their notes."""
    if len(staves) < 2:
        return
    ledgers = [(x0, y, x1) for x0, y, x1, _, _ in hor if x1 - x0 < 4 * staves[0]["s"]]

    def score(st, h):
        s = st["s"]
        if not (st["x0"] - 2 * s <= h["x"] <= st["x1"] + 2 * s):
            return None
        if st["top"] - 0.6 * s <= h["y"] <= st["bot"] + 0.6 * s:
            return 0
        if h["y"] < st["top"]:
            n = int((st["top"] - h["y"]) / s + 0.25)
            pos = [st["top"] - k * s for k in range(1, n + 1)]
        else:
            n = int((h["y"] - st["bot"]) / s + 0.25)
            pos = [st["bot"] + k * s for k in range(1, n + 1)]
        if abs(h["y"] - (st["top"] + st["bot"]) / 2) > 10 * s:
            return None
        miss = sum(1 for py in pos if not any(abs(ly - py) < 0.4 and lx0 < h["x1"] and lx1 > h["x"]
                                              for lx0, ly, lx1 in ledgers))
        return miss + abs(h["y"] - (st["top"] + st["bot"]) / 2) / (100 * s)

    heads = [(h, st) for st in staves for h in st["heads"]]
    for st in staves:
        st["heads"] = []
    allh = []
    for h, st0 in heads:
        best = min(((score(q, h), i) for i, q in enumerate(staves) if score(q, h) is not None),
                   default=(None, None))
        q = staves[best[1]] if best[1] is not None else st0
        q["heads"].append(h)
        allh.append((h, q))

    def owner(x0, x1, y, dymax):
        c = [(abs(h["y"] - y), q) for h, q in allh if x0 <= h["xc"] <= x1 and abs(h["y"] - y) < dymax]
        return min(c, key=lambda t: t[0])[1] if c else None

    stems_ = [(x, y0, y1) for x, y0, _, y1, w in ver if w <= 1.5]

    def flag_owner(f, s):
        """Staff of the note whose stem ends at the flag."""
        for vx, vy0, vy1 in stems_:
            if abs(vx - f["x"]) > 0.8 * s:
                continue
            for tip, base in ((vy0, vy1), (vy1, vy0)):
                if abs(tip - f["y"]) < 3 * s:
                    for h, q in allh:
                        if h["x"] - 0.6 <= vx <= h["x1"] + 0.6 and abs(h["y"] - base) < 0.8 * s:
                            return q
        return None

    flags = [(it, st) for st in staves for it in st["flags"]]
    for st in staves:
        st["flags"] = []
    for it, st in flags:
        q = flag_owner(it, st["s"]) or owner(it["x"] - 2 * st["s"], it["x"] + 0.5 * st["s"],
                                               it["y"], 4 * st["s"]) or st
        q["flags"].append(it)
    for key, dx0, dx1, dy in (("accs", 0, 4, 0.6), ("dots", -3, 0, 1.0)):
        items = [(it, st) for st in staves for it in st[key]]
        for st in staves:
            st[key] = []
        for it, st in items:
            s = st["s"]
            q = owner(it["x"] + dx0 * s, it["x"] + dx1 * s + (it.get("w", 0) if dx1 else 0),
                      it["y"], dy * s) or st
            q[key].append(it)
    polys = [(pts, st) for st in staves for pts in st["polys"]]
    for st in staves:
        st["polys"] = []
    stems = [(x, y0, y1) for x, y0, _, y1, w in ver if w <= 1.5]
    for pts, st in polys:
        xs = [q.x for q in pts]
        ys = [q.y for q in pts]
        s = st["s"]
        votes = {}
        for h, q in allh:
            if not (min(xs) - 1.5 * s <= h["xc"] <= max(xs) + 1.5 * s):
                continue
            for vx, vy0, vy1 in stems:
                if not (h["x"] - 0.6 <= vx <= h["x1"] + 0.6):
                    continue
                yr = poly_yrange(pts, vx)
                if yr is None:
                    continue
                py = (yr[0] + yr[1]) / 2
                if vy0 <= min(h["y"], py) + 1.0 * s and vy1 >= max(h["y"], py) - 1.0 * s:
                    votes[id(q)] = (votes.get(id(q), (0, q))[0] + 1, q)
                    break
        if votes:
            q = max(votes.values(), key=lambda t: t[0])[1]
        else:
            q = owner(min(xs) - 1.5 * s, max(xs) + 1.5 * s, (min(ys) + max(ys)) / 2, 6 * s) or st
        q["polys"].append(pts)


def collect_symbols(page, staves):
    raw = page.get_text("rawdict")
    for blk in raw["blocks"]:
        for line in blk.get("lines", []):
            for span in line["spans"]:
                for ch in span["chars"]:
                    k = classify(span["font"], ord(ch["c"]))
                    if k is None:
                        txt = "".join(c["c"] for sp in line["spans"] for c in sp["chars"]).strip()
                        if len(txt) == 1:
                            tuplet_digit(staves, ch)
                        continue
                    ox, oy = ch["origin"]
                    bb = ch["bbox"]
                    st = nearest_staff(staves, ox, oy)
                    if st is None:
                        continue
                    item = {"x": ox, "y": oy, "xc": (bb[0] + bb[2]) / 2,
                            "w": bb[2] - bb[0], "x1": bb[2], "val": k[1],
                            "size": span["size"]}
                    if k[0] == "head":
                        st["heads"].append(item)
                    elif k[0] == "acc":
                        st["accs"].append(item)
                    elif k[0] == "rest":
                        st["rests"].append(item)
                    elif k[0] == "flag":
                        st["flags"].append(item)
                    elif k[0] == "dot":
                        st["dots"].append(item)
                    elif k[0] == "tsig":
                        st["tsig"].append((ox, k[1]))
                    elif k[0] == "clef":
                        st["clefs"].append((ox, oy, k[1]))
                    elif k[0] == "rep":
                        st["reps"].append((ox, k[1]))
                        st["bars"].append(ox)
                    elif k[0] == "rdots":
                        st["reps"].append((ox, "dots"))
                    elif k[0] in ("segno", "coda"):
                        st["signs"].append((ox, k[0]))
                    elif k[0] == "digit":
                        if st["top"] - 0.3 * st["s"] < oy < st["bot"] + 0.3 * st["s"]:
                            st["tsd"].append(item)          # time signature
                        else:
                            st["tdig"].append({"rect": pymupdf.Rect(bb), "n": k[1],
                                               "music": True})
                    else:
                        st["bars"].append(ox)


def tuplet_digit(staves, ch):
    """Single digits outside the staff written with a text font: tuplet numbers
    (measure numbers are discarded later)."""
    code = ord(ch["c"])
    if 0xF030 <= code <= 0xF039:
        code -= 0xF000
    if not 0x30 <= code <= 0x39:
        return
    bb = pymupdf.Rect(ch["bbox"])
    cy = (bb.y0 + bb.y1) / 2
    st = nearest_staff(staves, (bb.x0 + bb.x1) / 2, cy)
    if st is None or st["top"] <= cy <= st["bot"]:
        return
    st["tdig"].append({"rect": bb, "n": code - 0x30, "music": False})


def poly_yrange(pts, x):
    """Vertical extent of polygon at abscissa x (None if outside)."""
    xs = [p.x for p in pts]
    if x < min(xs) - 0.6 or x > max(xs) + 0.6:
        return None
    x = min(max(x, min(xs) + 0.01), max(xs) - 0.01)
    ys = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if (a.x - x) * (b.x - x) <= 0 and a.x != b.x:
            ys.append(a.y + (b.y - a.y) * (x - a.x) / (b.x - a.x))
    return (min(ys), max(ys)) if ys else None


def multirest_bar(st, cx, ver):
    """Is there a multi-measure rest under abscissa cx? The discriminant (owner,
    2026-11-13; Caravan, Opus font: the H-bar is only ~2 staff spaces wide, the old
    test wanted more than 3) is the SHAPE: a horizontal bar inside the staff with a
    short vertical stroke at each end (the strokes as separate lines, or as part of the
    same filled shape)."""
    s = st["s"]
    for pts in st["polys"]:
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        ym = (y0 + y1) / 2
        if not (st["top"] < ym < st["bot"]) or not (x0 - 0.5 * s < cx < x1 + 0.5 * s):
            continue
        if x1 - x0 < s or y1 - y0 > 2.5 * s:
            continue

        def stroke(xe):
            return any(abs(vx - xe) < 0.5 * s and vy0 < ym < vy1 and vy1 - vy0 < 4 * s
                       for vx, vy0, _, vy1, _ in ver)

        def end_spread(xe):                  # strokes drawn inside the same shape ("H")
            e = [p.y for p in pts if abs(p.x - xe) < 0.3 * s]
            return max(e) - min(e) if e else 0.0
        if (stroke(x0) and stroke(x1)) or (end_spread(x0) > 1.2 * s and end_spread(x1) > 1.2 * s):
            return True
    return False


def finalize_digits(st, ver=()):
    """Split digits outside the staff into multi-measure rest counts and
    tuplet numbers; discard measure numbers."""
    s = st["s"]
    tdig = sorted(st["tdig"], key=lambda d: d["rect"].x0)
    # group adjacent music-font digits (e.g. "12")
    groups = []
    for d in tdig:
        g = groups[-1] if groups else None
        if (g and d["music"] and g["music"] and abs(d["rect"].y0 - g["rect"].y0) < 0.5 * s
                and d["rect"].x0 - g["rect"].x1 < 0.5 * s):
            g["n"] = 10 * g["n"] + d["n"]
            g["rect"] = g["rect"] | d["rect"]
        else:
            groups.append(dict(d))
    for g in groups:
        r = g["rect"]
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        if g["music"] and cy < st["top"]:
            if multirest_bar(st, cx, ver):
                st["multirests"].append((cx, g["n"]))
                continue
        if cx < st["x0"] + 3 * s or any(abs(cx - b) < 1.5 * s for b in st["bars"]):
            continue                                   # measure number
        st["tups"].append(g)
        if cy > st["bot"]:
            st["tuplets"].append(r)


def tuplet_brackets(staves, hor, ver):
    """Add the bracket lines around each tuplet number to the obstacles."""
    for st in staves:
        s = st["s"]
        obst = []
        for t in st["tuplets"]:
            obst.append(t)
            cy = (t.y0 + t.y1) / 2
            xa, xb = t.x0 - 15 * s, t.x1 + 15 * s
            for x0, y0, x1, y1, _ in hor:
                if abs(y0 - cy) < 1.5 * s and x1 - x0 < 30 * s and x1 > xa and x0 < xb:
                    obst.append(pymupdf.Rect(x0, y0 - 0.5, x1, y0 + 0.5))
            for x0, y0, x1, y1, _ in ver:
                if xa < x0 < xb and y1 - y0 < 2 * s and abs((y0 + y1) / 2 - cy) < 1.5 * s:
                    obst.append(pymupdf.Rect(x0 - 0.5, y0, x0 + 0.5, y1))
        st["obstacles"] = obst


def collect_barlines(staves, ver):
    for st in staves:
        s = st["s"]
        for x, y0, _, y1, _ in ver:
            if not (st["x0"] - 1 <= x <= st["x1"] + 1):
                continue
            if st["single"]:
                ok = y0 < st["line"] - 0.5 * s and y1 > st["line"] + 0.5 * s and y1 - y0 < 6 * s
            else:
                # covers the whole staff; may extend above/below (volta hooks,
                # barlines joining the staves of a system)
                ok = y0 < st["top"] + 0.3 * s and y1 > st["bot"] - 0.3 * s
            if ok:
                # reject stems: a notehead touching one end of the line
                stem = any(h["x"] - 0.6 <= x <= h["x1"] + 0.6 and
                           (abs(h["y"] - y0) < 0.8 * s or abs(h["y"] - y1) < 0.8 * s)
                           for h in st["heads"])
                if not stem:
                    st["bars"].append(x)
        st["bars"] = sorted(set(round(b, 1) for b in st["bars"]))


def setup_clefs(st, default_bottom):
    """Clef changes along the staff as (x, diatonic number of bottom line)."""
    s = st["s"]
    out = []
    for x, y, (kind, octv) in sorted(st["clefs"]):
        line = round((st["bot"] - y) / s)          # 0 = bottom line
        if kind == "G":
            bottom = 32 - 2 * line
        elif kind == "F":
            bottom = 24 - 2 * line
        elif kind == "C":
            bottom = 28 - 2 * line
        else:
            bottom = E4_DN
        out.append((x, bottom + octv))
    st["clef0"] = out[0][1] if out else default_bottom
    st["clefmap"] = out
    return st["clef0"] if not out else out[-1][1]


def dn_of(st, y, x=None):
    """Diatonic number (C4 = 28) of a vertical position (clef-aware)."""
    bottom = st.get("clef0", E4_DN)
    if x is not None:
        for cx, b in st.get("clefmap", []):
            if cx <= x + 0.5:
                bottom = b
    return bottom + round((st["bot"] - y) / (st["s"] / 2))


def match_keysig(run, st):
    """Longest prefix of accidentals matching the sharp/flat key order."""
    if not run:
        return {}, 0
    first = run[0]["val"]
    if first not in (1, -1):
        return {}, 0
    order = SHARP_ORDER if first == 1 else FLAT_ORDER
    n = 0
    for a, letter in zip(run, order):
        if a["val"] == first and dn_of(st, a["y"], a["x"]) % 7 == letter:
            n += 1
        else:
            break
    key = {order[i]: first for i in range(n)}
    return key, n


def attached(acc, heads, s):
    return any(0 < h["x"] - acc["x"] < 2.2 * s and abs(h["y"] - acc["y"]) < 0.3 * s
               for h in heads)


def find_ties(st, heads):
    """ids of noteheads tied to the previous note (same pitch position).
    A curve starting at the first note of the staff, coming from the staff
    start, is an incoming tie from the previous staff."""
    s = st["s"]
    tied = set()
    if not heads:
        return tied
    x_first = min(h["x"] for h in heads)
    for c in st["curves"]:
        if c.width < 1.0 * s or c.height > 2.5 * s:
            continue
        cy = (c.y0 + c.y1) / 2
        bs = sorted((h for h in heads if abs(c.x1 - h["xc"]) <= 1.5 * s
                     and abs(cy - h["y"]) <= 2 * s), key=lambda h: abs(cy - h["y"]))
        for b in bs:
            dnb = dn_of(st, b["y"], b["x"])
            prev = [h for h in heads if h["x"] < b["x"] - 0.5 * s
                    and abs(c.x0 - h["xc"]) < 1.5 * s
                    and dn_of(st, h["y"], h["x"]) == dnb]
            if prev:
                tied.add(id(b))
                break
            if abs(b["x"] - x_first) < 0.5 * s and c.x0 < b["xc"] - 1.5 * s:
                tied.add(id(b))
                break
    return tied


def analyse_staff(st, chords=False):
    """Return list of (head, midi, measure, tied) for the staff, in reading order.
    chords=False keeps only the top note at each position."""
    s = st["s"]
    heads = sorted(st["heads"], key=lambda h: (round(h["xc"] / (0.5 * s)), h["y"]))
    uniq = []
    for h in heads:
        if uniq and abs(h["xc"] - uniq[-1]["xc"]) < 0.5 * s:
            if not chords or any(abs(h["y"] - u["y"]) < 0.25 * s and abs(h["xc"] - u["xc"]) < 0.5 * s
                                 for u in uniq[-8:]):
                continue
        uniq.append(h)
    heads = sorted(uniq, key=lambda h: h["x"])
    tied = find_ties(st, heads)
    accs = sorted(st["accs"], key=lambda a: a["x"])
    bars = st["bars"]

    # key signature at the start of the staff
    x_first = heads[0]["x"] if heads else st["x1"]
    run = [a for a in accs if a["x"] < x_first]
    key, n = match_keysig(run, st)
    keysig_ids = set(id(a) for a in run[:n])

    # mid-staff key changes: >= 2 matching accidentals right after a barline
    keychanges = []
    for b in bars:
        nxt = [h["x"] for h in heads if h["x"] > b]
        xe = min(nxt) if nxt else st["x1"]
        r = [a for a in accs if b < a["x"] < xe and id(a) not in keysig_ids]
        nats = [a for a in r if a["val"] == 0 and not attached(a, heads, s)]
        rest = [a for a in r if a not in nats]
        k2, n2 = match_keysig(rest, st)
        if n2 >= 2 or (nats and n2 >= 1) or (nats and not rest):
            keychanges.append((b, k2))
            keysig_ids.update(id(a) for a in nats + rest[:n2])

    events = sorted(
        [("bar", b, None) for b in bars] +
        [("key", b + 0.01, k) for b, k in keychanges] +
        [("acc", a["x"], a) for a in accs if id(a) not in keysig_ids] +
        [("head", h["x"], h) for h in heads],
        key=lambda e: e[1])

    out, local, meas = [], {}, 0
    pending = []          # accidentals waiting for their notehead
    for kind, x, obj in events:
        if kind == "bar":
            local = {}
            meas += 1
        elif kind == "key":
            key = obj
            local = {}
        elif kind == "acc":
            pending.append(obj)
        else:
            dn = dn_of(st, obj["y"], obj["x"])
            for a in pending:
                if abs(a["y"] - obj["y"]) < 0.3 * s and obj["x"] - a["x"] < 3 * s:
                    local[dn] = a["val"]
            pending = [a for a in pending if (abs(a["y"] - obj["y"]) >= 0.3 * s or chords)
                       and obj["x"] - a["x"] < 3 * s]
            alt = local.get(dn, key.get(dn % 7, 0))
            midi = 12 * (dn // 7 + 1) + STEP_SEMI[dn % 7] + alt
            out.append((obj, midi, meas, id(obj) in tied))
    return out


# ---------------------------------------------------------------- rendering
class Writer:
    def __init__(self, user_font, size, color):
        self.size = size
        self.color = color
        self.uf_path = user_font
        self.uf = pymupdf.Font(fontfile=user_font)
        self.ff = pymupdf.Font(fontfile=FING_FONT)
        self.cap = 0.72 * size

    def label(self, text):
        """text -> (font key, string)"""
        if text in COMBO:
            return "ff", COMBO[text]
        return "uf", text

    def width(self, text):
        f, t = self.label(text)
        return (self.ff if f == "ff" else self.uf).text_length(t, self.size)

    def setup_page(self, page):
        page.insert_font(fontname="tfUser", fontfile=self.uf_path)
        page.insert_font(fontname="tfFing", fontfile=FING_FONT)

    def draw(self, page, text, x_left, y_top):
        f, t = self.label(text)
        # WHITE BACKGROUND under the fingering (owner, 2026-11-13: over other text it could
        # not be read): a white box as large as the glyphs (font ascender / descender)
        font = self.ff if f == "ff" else self.uf
        base = y_top + self.cap
        pad = 0.08 * self.size
        box = pymupdf.Rect(x_left - pad, base - font.ascender * self.size - pad,
                           x_left + font.text_length(t, self.size) + pad,
                           base - font.descender * self.size + pad)
        page.draw_rect(box, color=None, fill=(1, 1, 1), overlay=True)
        page.insert_text((x_left, y_top + self.cap), t,
                         fontname="tfFing" if f == "ff" else "tfUser",
                         fontsize=self.size, color=self.color)


def apply_no_repetition(notes):
    """notes: list of dicts with 'text'. Pairs A B repeated -> '-' per repetition."""
    n = len(notes)

    def reps(i):
        if i + 3 >= n:
            return 0
        a, b = notes[i]["text"], notes[i + 1]["text"]
        if a == b:
            return 0
        k, j = 0, i + 2
        while j + 1 < n and notes[j]["text"] == a and notes[j + 1]["text"] == b:
            k, j = k + 1, j + 2
        return k

    i = 0
    while i < n:
        r = reps(i)
        if r == 0:
            i += 1
            continue
        # if the first pair crosses a barline and the next phase is as good, shift
        if notes[i]["meas"] != notes[i + 1]["meas"] and reps(i + 1) >= r:
            i += 1
            continue
        a, b = notes[i]["text"], notes[i + 1]["text"]
        j = i + 2
        for _ in range(r):
            p, q = notes[j], notes[j + 1]
            p["text"], q["text"] = "-", None
            if p["page"] == q["page"] and p["staff"] is q["staff"]:
                p["xc"] = (p["xc"] + q["xc"]) / 2
            j += 2
        i = j


# ---------------------------------------------------------------- rhythm / MIDI
def find_stem(st, h):
    """Return (stem x, tip y, up) of the stem carrying notehead h, or None.
    Works for chords: the head may lie anywhere along the stem."""
    s = st["s"]
    best, bd = None, None
    for x, y0, _, y1, w in st["ver"]:
        if w > 1.5 or y1 - y0 < 2 * s:
            continue
        if not (h["x"] - 0.6 <= x <= h["x1"] + 0.6):
            continue
        if not (y0 - 0.8 * s <= h["y"] <= y1 + 0.8 * s):
            continue
        near = [k for k in st["heads"] if k["x"] - 0.6 <= x <= k["x1"] + 0.6]
        if any(abs(k["y"] - y1) < 0.8 * s for k in near):
            cand = (x, y0, True)
        elif any(abs(k["y"] - y0) < 0.8 * s for k in near):
            cand = (x, y1, False)
        else:
            continue
        up = cand[2]

        def on_side(k):     # up-stem on the right of the head, down-stem on the left
            if up:              # (glyph origin = left edge of the ink)
                return 0.8 * s < x - k["x"] < 1.9 * s
            return abs(x - k["x"]) < 0.4 * s
        penalty = 0
        if not on_side(h):
            # allowed only for the displaced head of a second in a chord,
            # and only if the head has no stem of its own
            if not any(k is not h and abs(k["y"] - h["y"]) <= 0.6 * s and on_side(k) for k in near):
                continue
            penalty = 100
        d = 0 if y0 <= h["y"] <= y1 else min(abs(h["y"] - y0), abs(h["y"] - y1))
        d += penalty
        if bd is None or d < bd:
            bd, best = d, cand
    return best


def count_beams(st, stem):
    s = st["s"]
    x, tip, up = stem
    n = 0
    for pts in st["polys"]:
        xs = [q.x for q in pts]
        if max(xs) - min(xs) < 0.8 * s:
            continue
        yr = poly_yrange(pts, x)
        if yr is None or yr[1] - yr[0] > 1.2 * s:
            continue
        if up and tip - 1.2 * s <= yr[0] and yr[1] <= tip + 3.2 * s:
            n += 1
        elif not up and tip - 3.2 * s <= yr[0] and yr[1] <= tip + 1.2 * s:
            n += 1
    return n


def count_flags(st, stem):
    s = st["s"]
    x, tip, up = stem
    return sum(f["val"] for f in st["flags"]
               if abs(f["x"] - x) < 0.8 * s and abs(f["y"] - tip) < 3 * s)


def is_repeat_dot(st, d):
    """Repeat-sign dot: exactly two dots on this x, around the middle line,
    with a barline close by."""
    s = st["s"]
    mid = (st["top"] + st["bot"]) / 2
    same = [e for e in st["dots"] if abs(e["x"] - d["x"]) < 0.3]
    if len(same) != 2:
        return False
    if not all(abs(abs(e["y"] - mid) - 0.5 * s) < 0.3 * s for e in same):
        return False
    return any(abs(b - d["x"]) < 2.5 * s for b in st["bars"])


def count_dots(st, obj, dy):
    """Augmentation dots right of a notehead/rest (distinct columns)."""
    s = st["s"]
    cols = []
    for d in st["dots"]:
        if obj["x1"] < d["x"] < obj["x1"] + 2.0 * s and abs(d["y"] - obj["y"]) < dy * s:
            if is_repeat_dot(st, d):
                continue
            # another notehead between this one and the dot: the dot is not ours
            between = [k for k in st["heads"] if obj["x"] + 0.3 * s < k["x"] < d["x"]]
            if between:
                so = find_stem(st, obj) if "ver" in st and "val" in obj else None
                if not so or any((find_stem(st, k) or (None,))[0] != so[0] for k in between):
                    continue
            # staccato dot: placed over/under a notehead, not beside it
            if any(h["x"] - 0.2 * s <= d["x"] <= h["x1"] + 0.2 * s and abs(d["y"] - h["y"]) < 2.5 * s
                   for h in st["heads"]):
                continue
            if not any(abs(c - d["x"]) < 0.3 * s for c in cols):
                cols.append(d["x"])
    return len(cols)


def with_dots(dur, nd):
    return dur * (2 - F(1, 2 ** nd)) if nd else dur


def tuplet_range(st, t, events):
    rg = _tuplet_range(st, t, events)
    if rg is None:
        return None
    r = t["rect"]
    cx = (r.x0 + r.x1) / 2
    left = max([b for b in st["bars"] if b < cx] + [st["x0"]])
    right = min([b for b in st["bars"] if b > cx] + [st["x1"]])
    return max(rg[0], left), min(rg[1], right)


def _tuplet_range(st, t, events):
    s = st["s"]
    r, n = t["rect"], t["n"]
    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
    left_b = max([b for b in st["bars"] if b < cx] + [st["x0"]])
    right_b = min([b for b in st["bars"] if b > cx] + [st["x1"]])
    events = [e for e in events if left_b < e["x"] < right_b]
    segs = [(x0, y0, x1, y0) for x0, y0, x1, _, _ in st["hor"]] + st.get("slant", [])
    # bracket halves: at least 0.8 spaces long (dashed lines are not brackets)
    left = [x0 for x0, y0, x1, y1 in segs
            if abs(y1 - cy) < 1.5 * s and r.x0 - 2 * s <= x1 <= r.x0 + 0.5
            and 0.8 * s <= x1 - x0 < 30 * s]
    right = [x1 for x0, y0, x1, y1 in segs
             if abs(y0 - cy) < 1.5 * s and r.x1 - 0.5 <= x0 <= r.x1 + 2 * s
             and 0.8 * s <= x1 - x0 < 30 * s]
    if left and right:
        return min(left) - 0.5 * s, max(right) + 0.5 * s
    for pts in st["polys"]:
        xs = [q.x for q in pts]
        yr = poly_yrange(pts, cx)
        if yr and max(xs) - min(xs) > 0.8 * s and min(abs(yr[0] - cy), abs(yr[1] - cy)) < 3.5 * s:
            return min(xs) - 0.2 * s, max(xs) + 0.2 * s
    near = sorted((e for e in events if e["kind"] in ("note", "rest")),
                  key=lambda e: abs(e["x"] - cx))[:n]
    if not near:
        return None
    return min(e["x"] for e in near) - 0.1, max(e["x"] for e in near) + 0.1


def staff_events(st, staff_notes):
    s = st["s"]
    ev = []
    sizes = [n["head"]["size"] for n in staff_notes]
    med = statistics.median(sizes) if sizes else 0
    for n in staff_notes:
        h = n["head"]
        if h["size"] < 0.8 * med:
            continue                                    # grace / cue note
        dur = h["val"]
        stem = find_stem(st, h) if dur <= 2 else None
        if dur == 1 and stem:
            k = count_beams(st, stem) + count_flags(st, stem)
            dur = F(1, 2 ** k)
        dur = with_dots(dur, count_dots(st, h, 0.8))
        ev.append({"x": h["xc"], "kind": "note", "note": n, "dur": dur,
                   "stem": stem[0] if stem else None})
    # fingered tremolo: two long notes joined by tremolo strokes share the value
    notes = sorted((e for e in ev if e["note"]["head"]["val"] >= 2), key=lambda e: e["x"])
    for a, b in zip(notes, notes[1:]):
        ha, hb = a["note"]["head"], b["note"]["head"]
        if hb["x"] - ha["x1"] > 8 * s or hb["x"] - ha["x"] < 1.5 * s:
            continue
        strokes = 0
        for pts in st["polys"]:
            xs = [q.x for q in pts]
            ys = [q.y for q in pts]
            if (min(xs) > ha["x"] and max(xs) < hb["x1"] and max(xs) - min(xs) > 1.0 * s
                    and max(ys) - min(ys) < 2 * s
                    and min(ha["y"], hb["y"]) - 3 * s < (min(ys) + max(ys)) / 2 < max(ha["y"], hb["y"]) + 3 * s):
                strokes += 1
        if strokes >= 1:
            a["dur"] /= 2
            b["dur"] /= 2
    inside = [r for r in st["rests"] if st["top"] - 1.0 * s <= r["y"] <= st["bot"] + 1.0 * s]
    for r in st["rests"]:
        if r not in inside and any(abs(q["x"] - r["x"]) < 1.5 * s for q in inside):
            continue                    # rest of another voice, outside the staff
        if any(abs(n["head"]["xc"] - r["xc"]) < 0.8 * s for n in staff_notes):
            continue                    # rest of another voice, under/over a note
        d = r["val"]
        if d != "W":
            d = with_dots(d, count_dots(st, r, 1.0))
        ev.append({"x": r["xc"], "kind": "rest", "dur": d})
    for cx, n in st["multirests"]:
        ev.append({"x": cx, "kind": "mrest", "n": n})
    for t in st["tups"]:
        rg = tuplet_range(st, t, ev)
        if rg is None or t["n"] < 2:
            continue
        p = 1
        while p * 2 < t["n"]:
            p *= 2
        ratio = F(3, 2) if t["n"] == 2 else F(p, t["n"])
        for e in ev:
            ex = e["stem"] if e.get("stem") is not None else e["x"]   # beams end at the stems
            if (e["kind"] in ("note", "rest") and rg[0] <= ex <= rg[1] and e["dur"] != "W"
                    and not e.get("tuplet")):
                e["dur"] *= ratio
                e["tuplet"] = True
    # time signatures
    mid = (st["top"] + st["bot"]) / 2
    tsd = sorted(st["tsd"], key=lambda d: d["x"])
    groups = []
    for d in tsd:
        if groups and d["x"] - groups[-1][-1]["x"] < 1.5 * s:
            groups[-1].append(d)
        else:
            groups.append([d])
    for g in groups:
        num = "".join(str(d["val"]) for d in sorted(g, key=lambda d: d["x"]) if d["y"] < mid)
        den = "".join(str(d["val"]) for d in sorted(g, key=lambda d: d["x"]) if d["y"] > mid)
        if num and den:
            ev.append({"x": g[0]["x"] - 0.01, "kind": "tsig", "val": (int(num), int(den))})
    for x, val in st["tsig"]:
        ev.append({"x": x - 0.01, "kind": "tsig", "val": val})
    last = None
    for b in st["bars"]:
        if last is None or b - last > 1.5 * s:
            ev.append({"x": b, "kind": "bar"})
        last = b
    return sorted(ev, key=lambda e: e["x"])


def find_tempo(doc):
    m = re.search(r"=\s*(\d{2,3})", doc[0].get_text())
    return int(m.group(1)) if m else 120


TEMPO_RE = re.compile(r"=\s*(\d{2,3})(?!\d)")


def mark_tempos(sts):
    """TEMPO CHANGES (owner, 2026-11-08: a "q=190" at letter C was ignored, the whole MIDI
    stayed at the first tempo): every tempo mark ("q=100", "♩ = 190") written over a staff
    is put on the bar under it (m["tempo"]). Returns the marks found [(bar_no, bpm)]."""
    found = []
    for st in sts:
        ms = st.get("ms") or []
        if not ms:
            continue
        for t, r in st.get("texts", []):
            mt = TEMPO_RE.search(t)
            if not mt:
                continue
            bpm = int(mt.group(1))
            if not 20 <= bpm <= 400:
                continue
            x = (r.x0 + r.x1) / 2
            m = measure_at(ms, x, st["s"]) or (ms[0] if x < ms[0]["x0"] else
                                                  measure_at(ms, r.x0, st["s"]))
            if m is None:
                continue
            m["tempo"] = bpm
            found.append((m["bar_no"], bpm))
    return sorted(found)


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


# ---------------------------------------------------------------- instrument detection
def norm_text(t):
    t = t.lower().replace("♭", "b")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\bsi\s*b\b", "bb", t)
    t = re.sub(r"\bb\s*b\b", "bb", t)
    t = re.sub(r"\bmi\s*b\b", "eb", t)
    t = re.sub(r"\be\s*b\b", "eb", t)
    t = re.sub(r"\bfa\b", "f", t)
    return t.strip()


def find_instrument(text):
    """Instrument whose keyword appears last in the text (the part name usually
    follows the title, e.g. 'rockin accordion Trombone 1'); longer keyword wins
    when two matches start at the same place."""
    text = norm_text(text)
    best = None
    for slug, spec in INSTRUMENTS.items():
        for kw in spec[0]:
            k = norm_text(kw)
            for m in re.finditer(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text):
                key = (m.start(), len(k))
                if best is None or key > best[0]:
                    best = (key, slug)
    return best[1] if best else None


def detect_instrument(doc, filename=None):
    """Look at the PDF title, then the file name, then the first page text."""
    title = (doc.metadata or {}).get("title") or ""
    for src in (title, os.path.splitext(os.path.basename(filename or ""))[0]):
        if src:
            inst = find_instrument(src)
            if inst:
                return inst
    # first page: the part name is normally a separate text line
    lines = [l.strip() for l in doc[0].get_text().splitlines() if l.strip()]
    for l in lines:
        inst = find_instrument(l)
        if inst and len(norm_text(l)) <= 40:
            return inst
    return find_instrument(" ".join(lines))


def resolve_instrument(name):
    n = norm_text(name.replace("_", " "))
    hits = set()
    for slug, spec in INSTRUMENTS.items():
        cands = [slug.replace("_", " ")] + [norm_text(k) for k in spec[0]]
        if n in cands:
            return slug
        words = set(n.split())
        if any(words <= set(c.split()) for c in cands):
            hits.add(slug)
    if len(hits) == 1:
        return hits.pop()
    return None


# ---------------------------------------------------------------- measures and repeats
def page_texts(page, staves):
    """Text lines (any font) assigned to the nearest staff."""
    d = page.get_text("dict")
    for blk in d["blocks"]:
        for line in blk.get("lines", []):
            t = "".join(sp["text"] for sp in line["spans"]).strip()
            if not t:
                continue
            r = pymupdf.Rect(line["bbox"])
            cy = (r.y0 + r.y1) / 2
            n = norm_text(t).replace(" ", "")
            if re.fullmatch(r"\d+(?:[.,\-]\d+)*\.", n):
                # volta label: belongs to the staff below it
                below = [q for q in staves if q["top"] > cy and q["top"] - cy < 8 * q["s"]
                         and q["x0"] - 2 * q["s"] <= r.x0 <= q["x1"]]
                st = min(below, key=lambda q: q["top"]) if below else None
            else:
                st = nearest_staff(staves, (r.x0 + r.x1) / 2, cy)
            if st is not None:
                st["texts"].append((t, r))


def split_missing_barlines(cur, mlen, s):
    """A 'measure' lasting an exact multiple of the bar length, whose bar
    boundaries all fall between events, is split (barlines missing in the PDF)."""
    if any(e["kind"] == "mrest" for e in cur):
        return [cur]
    t, cuts = F(0), []
    prev = None
    for i, e in enumerate(cur):
        if (e["kind"] == "note" and prev is not None and prev["kind"] == "note"
                and ((e.get("stem") is not None and prev.get("stem") is not None
                      and abs(e["stem"] - prev["stem"]) < 0.5)
                     or (e.get("stem") is None and abs(e["x"] - prev["x"]) < 0.6 * s))):
            continue                                  # chord member
        if t > 0 and t % mlen == 0:
            cuts.append(i)
        t += mlen if e["dur"] == "W" else e["dur"]
        prev = e
    if t <= mlen or t % mlen or len(cuts) != t / mlen - 1:
        return [cur]
    out, a = [], 0
    for c in cuts:
        out.append(cur[a:c])
        a = c
    out.append(cur[a:])
    return out


def build_measures(st, ev, state, bar_no):
    """Split staff events at barlines. state: dict with current time signature."""
    s = st["s"]
    out = []
    cur = []
    x0 = st["x0"]
    for e in ev + [{"x": st["x1"] + 1e6, "kind": "bar"}]:
        if e["kind"] == "tsig":
            state["tsig"] = e["val"]
            continue
        if e["kind"] != "bar":
            cur.append(e)
            continue
        if cur:
            tsig = state["tsig"]
            mlen = F(4 * tsig[0], tsig[1])
            for chunk in split_missing_barlines(cur, mlen, s):
                nb = 1
                for m in chunk:
                    if m["kind"] == "mrest":
                        nb = m["n"]
                cx0 = x0 if chunk is cur or chunk[0] is cur[0] else chunk[0]["x"] - 0.5 * s
                out.append({"staff": st, "x0": cx0, "x1": min(e["x"], st["x1"]), "events": chunk,
                            "tsig": tsig, "mlen": mlen, "nbars": nb, "bar_no": bar_no,
                            "start": False, "end": False, "times": None, "volta": set(),
                            "fine": False, "dc": False, "ds": False, "al": None,
                            "segno": False, "coda": False, "tocoda": False})
                bar_no += nb
        elif x0 > st["x0"] + 0.5 and e["x"] <= st["x1"] + 1 and e["x"] - x0 > 4 * s:
            # empty bar (no notes, no rests drawn): silent
            tsig = state["tsig"]
            out.append({"staff": st, "x0": x0, "x1": min(e["x"], st["x1"]), "events": [],
                        "tsig": tsig, "mlen": F(4 * tsig[0], tsig[1]), "nbars": 1,
                        "bar_no": bar_no, "start": False, "end": False, "times": None,
                        "volta": set(), "fine": False, "dc": False, "ds": False, "al": None,
                        "segno": False, "coda": False, "tocoda": False, "empty": True})
            bar_no += 1
        cur = []
        x0 = e["x"]
    return out, bar_no


def grand_staff(staves):
    """True if staves come in pairs joined by barlines (piano-like systems)."""
    if len(staves) < 2 or len(staves) % 2:
        return False
    for a, b in zip(staves[0::2], staves[1::2]):
        if a["page"] != b["page"]:
            return False
        s = a["s"]
        joined = any(y0 < a["top"] + 0.3 * s and y1 > b["bot"] - 0.3 * s
                     for x, y0, _, y1, w in a["ver"])
        ka = [c[2][0] for c in a["clefs"]][:1]
        kb = [c[2][0] for c in b["clefs"]][:1]
        if not joined and not (ka == ["G"] and kb == ["F"]):
            return False
    return True


def is_staff_line(st, y):
    """True if y is a line of any staff on the same page."""
    for q in st.get("pagestaves", []):
        if q.get("single"):
            if abs(y - q["line"]) < 0.5:
                return True
        elif q["top"] - 0.5 <= y <= q["bot"] + 0.5:
            k = (y - q["top"]) / q["s"]
            if abs(k - round(k)) * q["s"] < 0.5:
                return True
    return False


def measure_at(ms, x, s, prefer_end=False):
    for m in ms:
        if m["x0"] - 0.5 * s <= x <= m["x1"] + (1.0 * s if prefer_end else 0.5 * s):
            return m
    return None


def mark_staff(st, ms, nxt_ms):
    """Repeat signs, voltas, D.C./D.S./Fine/Coda on the measures of a staff."""
    if not ms:
        return
    s = st["s"]
    mid = (st["top"] + st["bot"]) / 2
    # repeat dots: pairs of dots on the same x around the middle line
    xs = []
    for d in st["dots"]:
        if is_repeat_dot(st, d) and not any(abs(x - d["x"]) < 0.3 for x in xs):
            xs.append(d["x"])
    reps = [(x, "dots") for x in xs] + st["reps"]
    for x, kind in reps:
        if kind in ("start", "both"):
            m = next((m for m in ms if m["x0"] >= x - 2 * s), None)
            if m:
                m["start"] = True
        if kind in ("end", "both"):
            m = next((m for m in reversed(ms) if m["x1"] <= x + 2 * s), None)
            if m:
                m["end"] = True
        if kind == "dots":
            bars = [m["x0"] for m in ms] + [ms[-1]["x1"]]
            b = min(bars, key=lambda b: abs(b - x))
            if abs(b - x) > 3 * s:
                if x < ms[0]["x0"] + 3 * s or x < min(e["x"] for e in ms[0]["events"]):
                    ms[0]["start"] = True
                continue
            if x > b:
                m = next((m for m in ms if abs(m["x0"] - b) < 0.5), None)
                if m:
                    m["start"] = True
                elif b <= ms[0]["x0"] + 0.5:
                    ms[0]["start"] = True
            else:
                m = next((m for m in ms if abs(m["x1"] - b) < 0.5), None)
                if m:
                    m["end"] = True
    # segno / coda glyphs
    codas = sorted(x for x, k in st["signs"] if k == "coda")
    for x, k in st["signs"]:
        if k == "segno":
            m = measure_at(ms, x, s)
            if m:
                m["segno"] = True
    st["coda_glyphs"] = [(x, measure_at(ms, x, s)) for x in codas]
    # texts
    for t, r in st["texts"]:
        n = norm_text(t).replace(" ", "")
        cy = (r.y0 + r.y1) / 2
        mv = re.fullmatch(r"(\d+(?:[.,\-]\d+)*)\.?", n)
        if mv and "." in n and cy < st["top"]:
            nums = set()
            for part in re.split(r"[.,]", mv.group(1)):
                if "-" in part:
                    a, b = part.split("-")[:2]
                    if a.isdigit() and b.isdigit():
                        nums.update(range(int(a), int(b) + 1))
                elif part.isdigit():
                    nums.add(int(part))
            # bracket line above the text
            lines = [(x0, x1) for x0, y0, x1, _, _ in st["hor"]
                     if r.y0 - 1.5 * s <= y0 <= r.y1 and r.x0 - 2 * s <= x0 <= r.x0 + 0.5
                     and x1 > r.x1 and not is_staff_line(st, y0)]
            if lines:
                lx0, lx1 = min(l[0] for l in lines), max(l[1] for l in lines)
            else:
                lx0, lx1 = r.x0, r.x1
            for m in ms:
                if lx0 - 0.5 * s <= (m["x0"] + m["x1"]) / 2 <= lx1 + 0.5 * s:
                    m["volta"] |= nums
            if lines and lx1 >= st["x1"] - 1.0 * s and nxt_ms:
                nst = nxt_ms[0]["staff"]
                cont = [(x0, x1) for x0, y0, x1, _, _ in nst["hor"]
                        if nst["top"] - 6 * nst["s"] < y0 < nst["top"] - 0.5 * nst["s"]
                        and x0 < nxt_ms[0]["x1"] and x1 - x0 > 2 * nst["s"]
                        and not is_staff_line(nst, y0)]
                if cont:
                    cx1 = max(c[1] for c in cont)
                    for m in nxt_ms:
                        if (m["x0"] + m["x1"]) / 2 <= cx1 + 0.5 * nst["s"]:
                            m["volta"] |= nums
            continue
        mt = re.search(r"(\d+)\s*(?:x|×|volte|times)|(?:x|×)\s*(\d+)", norm_text(t))
        if mt and len(n) <= 8:
            m = measure_at(ms, r.x1, s, prefer_end=True)
            if m:
                m["times"] = int(mt.group(1) or mt.group(2))
            continue
        dc = "d.c." in n or "dacapo" in n
        ds = "d.s." in n or "dalsegno" in n
        if dc or ds:
            m = measure_at(ms, r.x1, s, prefer_end=True) or ms[-1]
            m["dc" if dc else "ds"] = True
            m["al"] = "fine" if "fine" in n else ("coda" if "coda" in n else None)
            continue
        if n in ("fine", "fine."):
            m = measure_at(ms, r.x1, s, prefer_end=True)
            if m:
                m["fine"] = True
            continue
        if "tocoda" in n or n == "alcoda":
            m = measure_at(ms, r.x1, s, prefer_end=True)
            if m:
                m["tocoda"] = True
            continue
        if n == "coda":
            m = measure_at(ms, r.x0, s)
            if m:
                m["coda"] = True


def expand(M):
    """Order of measure indices after repeats, voltas, D.C./D.S., Fine, Coda."""
    n = len(M)
    # volta groups: runs of consecutive measures with voltas
    gmax = [0] * n
    i = 0
    while i < n:
        if M[i]["volta"]:
            j = i
            while j < n and M[j]["volta"]:
                j += 1
            mx = max(max(M[k]["volta"]) for k in range(i, j))
            for k in range(i, j):
                gmax[k] = mx
            i = j
        else:
            i += 1
    order = []
    cur = {"start": 0, "pass": 1, "vpass": None}
    jumped, mode = False, None
    i, guard = 0, 0
    while i < n and guard < 100000:
        guard += 1
        m = M[i]
        if m["start"] and i != cur["start"]:
            cur = {"start": i, "pass": 1, "vpass": None}
        if m["volta"]:
            if jumped:
                play = gmax[i] in m["volta"]
            else:
                vp = cur["vpass"] or cur["pass"]
                play = vp in m["volta"]
            if not play:
                if m["end"]:
                    cur = {"start": i + 1, "pass": 1, "vpass": cur["vpass"] or cur["pass"]}
                i += 1
                continue
        else:
            cur["vpass"] = None
        order.append(i)
        if jumped and mode == "fine" and m["fine"]:
            break
        if jumped and mode == "coda" and m["tocoda"]:
            k = next((k for k in range(i + 1, n) if M[k]["coda"]), None)
            if k is None:
                break
            mode = "done"
            i = k
            continue
        if m["end"] and not jumped:
            times = m["times"] or (max(m["volta"]) + 1 if m["volta"] else 2)
            if cur["pass"] < times:
                cur["pass"] += 1
                i = cur["start"]
                continue
            cur = {"start": i + 1, "pass": 1, "vpass": cur["pass"]}
        if (m["dc"] or m["ds"]) and not jumped:
            jumped = True
            mode = m["al"]
            if m["ds"]:
                i = next((k for k in range(n) if M[k]["segno"]), 0)
            else:
                i = 0
            cur = {"start": i, "pass": 1, "vpass": None}
            continue
        i += 1
    return order


def render_part(M, order, inst_key, transp, warnings, tempo=None):
    """Notes [start, dur, key] of one part following the measure order; also the time
    signatures and the TEMPOS [(quarters, bpm)] in the order played: a bar has the tempo
    of the last mark at or before it in the written order (`tempo` = the first tempo)."""
    t = F(0)
    played = []
    tsigs = []
    tempos = []
    last_tsig = None
    at, cur = [], tempo
    for m in M:                                    # tempo of every written bar
        cur = m.get("tempo", cur)
        at.append(cur)
    last_tempo = None
    for idx in order:
        m = M[idx]
        if m["tsig"] != last_tsig:
            tsigs.append((t, m["tsig"]))
            last_tsig = m["tsig"]
        if at and at[idx] is not None and at[idx] != last_tempo:
            tempos.append((t, at[idx]))
            last_tempo = at[idx]
        evs = m["events"]
        s = m["staff"]["s"]
        total = F(0)
        prev_x, prev_dur, prev_stem = None, None, None
        first = idx == 0
        for e in evs:
            if e["kind"] == "mrest":
                d = m["mlen"] * e["n"]
            elif e["dur"] == "W":
                d = m["mlen"] if len(evs) == 1 else F(0)   # whole rest beside notes: other voice
            else:
                d = e["dur"]
            same = False
            if e["kind"] == "note" and prev_x is not None:
                if e["stem"] is not None and prev_stem is not None:
                    same = abs(e["stem"] - prev_stem) < 0.5
                else:
                    same = abs(e["x"] - prev_x) < 0.6 * s
            if same:
                onset = t - prev_dur              # chord: same onset as previous note
            else:
                onset = t
                t += d
                total += d
            if e["kind"] == "note":
                nt = e["note"]
                key = inst_key if inst_key is not None else nt["midi"] + transp
                if nt.get("tied"):
                    # same written position (keeps the accidental of the first note)
                    for p in reversed(played):
                        if p[0] + p[1] == onset and (p[3] == nt["dn"] or p[2] == key):
                            p[1] += d
                            break
                    else:
                        played.append([onset, d, key, nt["dn"]])
                else:
                    played.append([onset, d, key, nt["dn"]])
                if not same:
                    prev_x, prev_dur, prev_stem = e["x"], d, e["stem"]
            else:
                prev_x = None
        expected = m["mlen"] * m["nbars"]
        if m.get("empty"):
            t += expected
            continue
        pickup = (idx == 0 or idx == len(M) - 1) and total < expected
        if total != expected and not pickup and not m.get("warned"):
            m["warned"] = True
            warnings.append(f"bar {m['bar_no']}: {total} quarters instead of {expected}")
    return played, tsigs, tempos


def write_log(logname, pdfname, warnings):
    """Append the warnings of one PDF to the log file."""
    d = os.path.dirname(os.path.abspath(logname))
    if not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(logname, "a", encoding="utf-8") as f:
        f.write(f"=== {os.path.abspath(pdfname)}\n")
        for w in warnings:
            f.write(f"warning: {w}\n")


def write_midi(parts, tempo, inst, name, bass_clef, force=False, tpq=480,
               logname=None, pdfname=None):
    spec = INSTRUMENTS[inst]
    transp = spec[2] if bass_clef else spec[1]
    program, perc = spec[3], spec[4]
    warnings = []
    ref = parts[0]
    order = expand(ref)
    for M in parts:                     # pickup bar: printed numbering starts at 0
        if M:
            m0 = M[0]
            tot = sum((e["dur"] for e in m0["events"] if e["kind"] in ("note", "rest")
                       and e["dur"] != "W"), F(0))
            if tot and tot < m0["mlen"]:
                for m in M:
                    m["bar_no"] -= 1
    allnotes, tsigs, byparts, tempos = [], [], [], []
    for k, M in enumerate(parts):
        o = order if len(M) == len(ref) else list(range(len(M)))
        if o is not order:
            warnings.append(f"staff group {k + 1}: measure count differs, repeats not applied")
        played, ts, tp = render_part(M, o, perc, transp, warnings, tempo)
        allnotes += played
        byparts.append(played)
        if k == 0:
            tsigs, tempos = ts, tp
    if warnings and logname:
        write_log(logname, pdfname, warnings)
    if warnings and not force:
        for w in warnings:
            print("warning:", w)
        sys.exit(f"{len(warnings)} warnings: MIDI not written (use --force to write it anyway).")
    if not tempos or tempos[0][0] != 0:
        tempos.insert(0, (F(0), tempo))
    meta = []
    for tt, bpm in tempos:                         # first tempo + every change (owner)
        us = int(round(60_000_000 / bpm))
        meta.append((int(tt * tpq), 0, b"\xff\x51\x03" + us.to_bytes(3, "big")))
    for tt, (nn, dd) in tsigs:
        meta.append((int(tt * tpq), 0, bytes([0xFF, 0x58, 4, nn, max(dd.bit_length() - 1, 0), 24, 8])))

    def track(evs):
        evs.sort(key=lambda e: (e[0], e[1]))
        trk, now = b"", 0
        for tick, _, data in evs:
            trk += vlq(tick - now) + data
            now = tick
        trk += b"\x00\xff\x2f\x00"
        return b"MTrk" + len(trk).to_bytes(4, "big") + trk

    def note_events(notes, ch):
        evs = [] if perc is not None else [(0, 1, bytes([0xC0 | ch, program]))]
        for start, dur, key, _ in notes:
            if not 0 <= key <= 127 or dur <= 0:
                continue
            a = int(round(start * tpq))
            b = int(round((start + dur) * tpq))
            evs.append((a, 3, bytes([0x90 | ch, key, 80])))
            evs.append((b, 2, bytes([0x80 | ch, key, 64])))
        return evs

    if len(byparts) == 1:              # one part: format 0, one track
        ch = 9 if perc is not None else 0
        tracks = [track(meta + note_events(allnotes, ch))]
    else:                              # several parts (e.g. a duet): format 1, one track/channel each
        chans = [c for c in range(16) if c != 9]
        tracks = [track(meta)] + [track(note_events(n, 9 if perc is not None else chans[k % 15]))
                                  for k, n in enumerate(byparts)]
    with open(name, "wb") as f:
        f.write(b"MThd" + (6).to_bytes(4, "big") + (0 if len(tracks) == 1 else 1).to_bytes(2, "big") +
                len(tracks).to_bytes(2, "big") + tpq.to_bytes(2, "big"))
        for t in tracks:
            f.write(t)
    for w in warnings:
        print("warning:", w)
    nbars = sum(m["nbars"] for m in ref)
    played_bars = sum(ref[i]["nbars"] for i in order)
    changes = "" if len(tempos) < 2 else \
        " (changes: " + ", ".join(f"{b:g}" for _, b in tempos[1:]) + ")"
    print(f"{inst}: {len(allnotes)} notes, {nbars} bars written, {played_bars} bars played, "
          f"tempo {tempos[0][1]}{changes} -> {name}")


def main():
    ap = argparse.ArgumentParser(description="Write Bb trumpet fingerings under the notes of a vector PDF.")
    ap.add_argument("filename", help="input PDF, or a folder: every PDF below it is processed")
    ap.add_argument("--fontsize", type=float, default=12, help="font size in pt (default 12)")
    ap.add_argument("--font", default=DEFAULT_FONT, help="TTF/OTF font for single digits (default Arial)")
    ap.add_argument("--space", type=float, default=12,
                    help="gap in pt below the note or below the E4 line, whichever is lower (default 12)")
    ap.add_argument("--color", choices=list(COLORS), default="k", help="r, g, b, k (default k)")
    ap.add_argument("--no_repetition", type=str2bool, default=False,
                    help="true: repeated pairs of fingerings written once, then '-' per repetition")
    ap.add_argument("--midi", action="store_true",
                    help="write a MIDI file (concert pitch) instead of the annotated PDF")
    ap.add_argument("--log", default=DEFAULT_LOG,
                    help="file where warnings are appended (default: ~/.musikite/scoreread.log)")
    ap.add_argument("--force", action="store_true",
                    help="write the MIDI file even if some bars do not add up")
    ap.add_argument("--instrument", default=None,
                    help="instrument (e.g. trumpet, trombone, 'baritone sax'); default: read from the PDF")
    a = ap.parse_args()

    if os.path.isdir(a.filename):
        pdfs = []
        for d, _, files in os.walk(a.filename):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(d, f))
        pdfs.sort()
        if not pdfs:
            sys.exit(f"No PDF files in {a.filename}")
        failed = []
        for i, f in enumerate(pdfs, 1):
            print(f"=== [{i}/{len(pdfs)}] {f}")
            b = argparse.Namespace(**vars(a))
            b.filename = f
            try:
                process(b)
            except SystemExit as e:
                if e.code not in (None, 0):
                    print(e.code)
                    failed.append(f)
            except Exception as e:                  # keep going with the other files
                print(f"error: {type(e).__name__}: {e}")
                failed.append(f)
        print(f"\n{len(pdfs) - len(failed)} of {len(pdfs)} PDF processed, {len(failed)} not written:")
        for f in failed:
            print("  " + f)
        return
    process(a)


def system_size(staves):
    """Staves per system when every system has the same number (> 1) of
    staves joined at the left by the system line (e.g. a duet score);
    None otherwise."""
    sizes, k = [], 0
    while k < len(staves):
        n = 1
        while k + n < len(staves):
            a, b = staves[k + n - 1], staves[k + n]
            s = a["s"]
            if a["page"] != b["page"] or abs(a["x0"] - b["x0"]) > 2 * s:
                break
            if not any(abs(x - a["x0"]) < 1.5 * s and y0 < a["top"] + 0.3 * s
                       and y1 > b["bot"] - 0.3 * s for x, y0, _, y1, w in a["ver"]):
                break
            n += 1
        sizes.append(n)
        k += n
    if len(set(sizes)) == 1 and sizes[0] > 1:
        return sizes[0]
    return None


def process(a):
    """Process one PDF with the options in a."""
    if not os.path.isfile(a.filename):
        sys.exit(f"File not found: {a.filename}")
    if not os.path.isfile(FING_FONT):
        sys.exit(f"Missing {FING_FONT}")
    if not a.midi and not os.path.isfile(a.font):
        sys.exit(f"Font not found: {a.font}")

    root, _ = os.path.splitext(a.filename)
    out_name = root + ".noted.pdf"
    doc = pymupdf.open(a.filename)

    if a.instrument:
        inst = resolve_instrument(a.instrument)
        if inst is None:
            sys.exit(f"Unknown instrument '{a.instrument}'. Known: " + ", ".join(INSTRUMENTS))
    else:
        inst = detect_instrument(doc, a.filename)
        if inst is None:
            sys.exit("Instrument not found in the PDF; use --instrument. Known: " + ", ".join(INSTRUMENTS))
    spec = INSTRUMENTS[inst]
    if not a.midi and inst != "trumpet":
        sys.exit(f"Fingerings are available only for trumpet (instrument: {inst}); use --midi.")
    print(f"instrument: {inst}")
    wr = None if a.midi else Writer(a.font, a.fontsize, COLORS[a.color])

    notes = []
    all_staves = []
    for pno, page in enumerate(doc):
        if page.rotation:
            page.remove_rotation()
        hor, ver, curves, polys = segments(page)
        staves = find_staves(hor)
        if not staves and spec[4] is not None:
            sizes = [sp["size"] for b in page.get_text("dict")["blocks"]
                     for l in b.get("lines", []) for sp in l["spans"]
                     if any(k in sp["font"].lower() for k in SONATA_FONTS + ("bravura", "leland", "petaluma"))]
            if sizes:
                staves = single_line_staves(hor, staves, statistics.median(sizes) / 4, ver)
        for c in curves:
            st = nearest_staff(staves, (c.x0 + c.x1) / 2, (c.y0 + c.y1) / 2)
            if st is not None:
                st["curves"].append(c)
        for pts in polys:
            xs = [q.x for q in pts]
            ys = [q.y for q in pts]
            st = nearest_staff(staves, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            if st is not None:
                st["polys"].append(pts)
        collect_symbols(page, staves)
        reassign_symbols(staves, hor, ver)
        collect_barlines(staves, ver)
        for st in staves:
            finalize_digits(st, ver)
            st["ver"] = ver
            st["hor"] = hor
            st["slant"] = segments.slant
        tuplet_brackets(staves, hor, ver)
        staves = [st for st in staves if st["heads"] or st["rests"] or st["multirests"]]
        page_texts(page, staves)
        for st in staves:
            st["page"] = pno
            st["pagestaves"] = staves
        all_staves.extend(staves)

    # clefs: carried over from staff to staff (per part)
    nparts = spec[6]
    if nparts == 2 and not grand_staff(all_staves):
        nparts = 1                       # e.g. accordion part written on one staff
    if nparts == 1 and a.midi:
        nparts = system_size(all_staves) or 1    # several parts of the same instrument
    last = [spec[5]] * nparts
    for k, st in enumerate(all_staves):
        last[k % nparts] = setup_clefs(st, last[k % nparts])

    if a.midi:
        parts = [[] for _ in range(nparts)]
        bar_no = [1] * nparts
        state = [{"tsig": (4, 4)} for _ in range(nparts)]
        prev_ms = [None] * nparts
        for k, st in enumerate(all_staves):
            pk = k % nparts
            sn = []
            for h, midi, meas, tie_in in analyse_staff(st, chords=True):
                sn.append({"head": h, "midi": midi, "tied": tie_in,
                           "dn": dn_of(st, h["y"], h["x"])})
            ev = staff_events(st, sn)
            ms, bar_no[pk] = build_measures(st, ev, state[pk], bar_no[pk])
            st["ms"] = ms
            parts[pk].append(st)
        sts0 = list(parts[0])                      # staves of the first part (tempo marks)
        for pk in range(nparts):
            sts = parts[pk]
            for j, st in enumerate(sts):
                nxt = sts[j + 1]["ms"] if j + 1 < len(sts) else None
                mark_staff(st, st["ms"], nxt)
            # coda glyphs: with two or more, the first is the jump, the last the target
            glyphs = [m for st in sts for x, m in st.get("coda_glyphs", []) if m is not None]
            if len(glyphs) >= 2:
                glyphs[0]["tocoda"] = True
                glyphs[-1]["coda"] = True
            elif len(glyphs) == 1 and any(m["tocoda"] for st in sts for m in st["ms"]):
                glyphs[0]["coda"] = True
            parts[pk] = [m for st in sts for m in st["ms"]]
        if not parts[0]:
            sys.exit("No notes found (unsupported music font or not a vector PDF).")
        bass = all_staves[0].get("clef0", E4_DN) <= 24 if all_staves else False
        marks = mark_tempos(sts0)
        first = marks[0][1] if marks else find_tempo(doc)
        write_midi(parts, first, inst, root + ".from_pdf.mid", bass, a.force,
                   logname=a.log, pdfname=a.filename)
        return

    for st in all_staves:
        pno = st["page"]
        if True:
            for h, midi, meas, tie_in in analyse_staff(st):
                if tie_in and notes:
                    # tied note: same pitch as the previous one, no fingering
                    notes.append({"page": pno, "staff": st, "xc": h["xc"], "head": h,
                                  "meas": (pno, id(st), meas), "y": h["y"],
                                  "midi": notes[-1]["midi"], "text": None,
                                  "tied": True})
                    continue
                notes.append({"page": pno, "staff": st, "xc": h["xc"], "head": h,
                              "meas": (pno, id(st), meas),
                              "y": h["y"], "midi": midi,
                              "text": FINGERING.get(midi, "?")})

    if not notes:
        sys.exit("No notes found (unsupported music font or not a vector PDF).")

    if a.no_repetition:
        apply_no_repetition([n for n in notes if n["text"] is not None])

    row_h = 1.15 * a.fontsize
    pad = 0.15 * a.fontsize
    placed = {}           # id(staff) -> list of rects
    pages_ready = set()
    for nt in notes:
        if nt["text"] is None:
            continue
        page = doc[nt["page"]]
        if nt["page"] not in pages_ready:
            wr.setup_page(page)
            pages_ready.add(nt["page"])
        st = nt["staff"]
        ref = max(nt["y"] + st["s"] / 2, st["bot"])
        top0 = ref + a.space
        w = wr.width(nt["text"])
        x0 = nt["xc"] - w / 2
        rects = placed.setdefault(id(st), list(st["obstacles"]))
        k = 0
        while True:
            r = pymupdf.Rect(x0, top0 + k * row_h, x0 + w, top0 + k * row_h + wr.cap)
            if not any((r + (-pad, 0, pad, 0)).intersects(q) for q in rects):
                break
            k += 1
        rects.append(r)
        wr.draw(page, nt["text"], x0, r.y0)

    unknown = sum(1 for n in notes if n["text"] == "?")
    ties = sum(1 for n in notes if n.get("tied"))
    doc.save(out_name, garbage=3, deflate=True)
    print(f"{len(notes)} notes, {ties} tied, {unknown} out of range -> {out_name}")


if __name__ == "__main__":
    main()
