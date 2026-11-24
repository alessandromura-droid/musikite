"""
PROGRESSIONS (owner, 2026-11-08): the chord progressions of the theory engine, written ONCE
in Roman numerals and played in any key. Part of the theory engine (`theory.PROGRESSIONS`
is the old table, kept here as `LEGACY`, unchanged). Pure Python, no music21, no Qt
(Android).

    from musikite.progressions import progression, names, roman_chord
    progression("ii-V-I major", "Bb")        # 'Cm7 F7 Bbmaj7 Bbmaj7'
    progression("jazz blues", "F")           # 12 bars, two chords in a bar joined by ':'
    roman_chord("V7/ii", "C")                # 'A7'
    names(style="jazz")

ROMAN NUMERALS (convention, Levine, The Jazz Theory Book): the degree is counted on the MAJOR
scale of the key's tonic; b / # before the numeral lower / raise it (bII, bIII, #IV, bVI,
bVII: in a minor key the third degree is bIII); UPPER case = major, lower case = minor;
the suffix is a chord suffix of `theory.CHORD_ALIASES` added to the root (I, I7, Imaj7, I6;
ii, ii7, iiø7 / ii7b5, iidim, iidim7, im6, im(maj7); V7b9, V7alt…); lower case + "7" = m7,
lower case + "6" = m6, lower case + "maj7" = m(maj7). SECONDARY chords: "V7/ii" = the V7 of
the ii degree (A7 in C). A bar with two chords: "Imaj7:vi7" (as `theory.parse_progression`).
Root spelling: the sign of the numeral first (bII -> flat, #IV -> sharp), else flats in
flat keys (F, Bb, Eb, Ab, Db, Gb) and sharps in the others. Half-diminished is written
m7b5 (iiø7 -> Dm7b5).

HOW TO GROW IT: a new progression = a new row of CATALOGUE (roman, style, level 1-5,
source); never change the meaning of an existing name (exercises remember the name).
"""
import re

# The old table (C, chord names): theory.PROGRESSIONS, unchanged (used by saved duets).
LEGACY = {
    "I-vi-IV-V": "C Am F G",
    "ii-V-I major": "Dm7 G7 Cmaj7 Cmaj7",
    "ii-V-i minor": "Dm7b5 G7b9 Cm6 Cm6",
    "I-vi-ii-V": "Cmaj7 Am7 Dm7 G7",
    "iii-vi-ii-V": "Em7 A7 Dm7 G7",
    "blues": "C7 F7 C7 C7 F7 F7 C7 A7 Dm7 G7 C7 G7",
    "minor blues": "Cm7 Fm7 Cm7 Cm7 Fm7 Fm7 Cm7 Cm7 Abmaj7 G7 Cm7 G7",
    "so what": "Dm7 Dm7 Dm7 Dm7 Dm7 Dm7 Dm7 Dm7 Ebm7 Ebm7 Ebm7 Ebm7 Ebm7 Ebm7 Ebm7 Ebm7",
    "circle of fourths": "C F Bb Eb Ab Db F# B E A D G",
    "rhythm changes A": "Cmaj7:Am7 Dm7:G7 Cmaj7:Am7 Dm7:G7 Cmaj7:C7 Fmaj7:F#dim7 Cmaj7:G7 Cmaj7",
}

# name -> dict(roman, style, level, source). One token = one bar ("A:B" = two chords).
CATALOGUE = {
    "I-vi-IV-V": dict(roman="I vi IV V", style="pop", level=1, source="common practice"),
    "ii-V-I major": dict(roman="ii7 V7 Imaj7 Imaj7", style="jazz", level=1, source="Levine"),
    "ii-V-i minor": dict(roman="iiø7 V7b9 im6 im6", style="jazz", level=2, source="Levine"),
    "I-vi-ii-V": dict(roman="Imaj7 vi7 ii7 V7", style="jazz", level=1, source="Levine"),
    "iii-vi-ii-V": dict(roman="iii7 VI7 ii7 V7", style="jazz", level=2, source="Levine"),
    "turnaround with secondary dominants": dict(roman="Imaj7 VI7 ii7 V7", style="jazz",
                                                level=2, source="Levine"),
    "tritone substitution ii-V-I": dict(roman="ii7 bII7 Imaj7 Imaj7", style="jazz",
                                        level=3, source="Levine"),
    "backdoor ii-V": dict(roman="iv7 bVII7 Imaj7 Imaj7", style="jazz", level=3,
                          source="Levine"),
    "descending ii-V chain": dict(roman="iii7 VI7 ii7 V7 i7 IV7 bVIImaj7 bVIImaj7",
                                  style="jazz", level=3, source="Levine"),
    "autumn leaves cycle": dict(roman="ii7 V7 Imaj7 IVmaj7 viiø7 III7 vi7 vi7", style="jazz",
                                level=2, source="standard (Autumn Leaves)"),
    "blues": dict(roman="I7 IV7 I7 I7 IV7 IV7 I7 VI7 ii7 V7 I7 V7", style="blues", level=1,
                  source="12-bar blues"),
    "jazz blues": dict(roman="I7 IV7 I7 v7:I7 IV7 #IVdim7 I7 VI7 ii7 V7 I7:VI7 ii7:V7",
                       style="jazz", level=2, source="Levine"),
    "minor blues": dict(roman="i7 iv7 i7 i7 iv7 iv7 i7 i7 bVImaj7 V7 i7 V7", style="blues",
                        level=2, source="12-bar minor blues"),
    "bird blues": dict(roman="Imaj7 viiø7:III7 vi7:II7 v7:I7 IV7 iv7:bVII7 iii7:VI7 "
                             "biii7:bVI7 ii7 V7 I7:VI7 ii7:V7",
                       style="jazz", level=4, source="Charlie Parker, Blues for Alice"),
    "rhythm changes A": dict(roman="Imaj7:vi7 ii7:V7 Imaj7:vi7 ii7:V7 Imaj7:I7 "
                                   "IVmaj7:#IVdim7 Imaj7:V7 Imaj7",
                             style="jazz", level=3, source="Gershwin, I Got Rhythm"),
    "rhythm changes B": dict(roman="III7 III7 VI7 VI7 II7 II7 V7 V7", style="jazz", level=2,
                             source="Gershwin, I Got Rhythm"),
    "coltrane changes": dict(roman="ii7:bIII7 bVImaj7:VII7 IIImaj7:V7 Imaj7", style="jazz",
                             level=5, source="Coltrane, Countdown"),
    "so what": dict(roman="i7 i7 i7 i7 i7 i7 i7 i7 bii7 bii7 bii7 bii7 bii7 bii7 bii7 bii7",
                    style="modal", level=1, source="Miles Davis, So What (key D)"),
    # STANDARDS (owner, 2026-11-18: backing tracks on the most common jazz standards): the
    # chord changes only, as in the common lead sheets (simplified: no alterations), style
    # 'standard'; the key in the source is the usual one. Never melodies or lyrics.
    "blue bossa": dict(roman="i7 i7 iv7 iv7 iiø7 V7 i7 i7 biii7 bVI7 bIImaj7 bIImaj7 "
                             "iiø7 V7 i7 iiø7:V7",
                       style="standard", level=2,
                       source="standard (Kenny Dorham, Blue Bossa; usual key C minor)"),
    "autumn leaves": dict(roman="iv7 bVII7 bIIImaj7 bVImaj7 iiø7 V7 i6 i6 "
                                "iv7 bVII7 bIIImaj7 bVImaj7 iiø7 V7 i6 i6 "
                                "iiø7 V7 i6 i6 iv7 bVII7 bIIImaj7 bVImaj7 "
                                "iiø7 V7 i7:IV7 bvii7:bIII7 bVImaj7 iiø7:V7 i6 i6",
                          style="standard", level=2,
                          source="standard (Kosma, Autumn Leaves; usual key G minor)"),
    "all of me": dict(roman="Imaj7 Imaj7 III7 III7 VI7 VI7 ii7 ii7 III7 III7 vi7 vi7 "
                            "II7 II7 ii7 V7 Imaj7 Imaj7 III7 III7 VI7 VI7 ii7 ii7 "
                            "IVmaj7 iv6 Imaj7:iii7 VI7 ii7 V7 I6 ii7:V7",
                      style="standard", level=2,
                      source="standard (Marks / Simons, All of Me; usual key C)"),
    "take the a train": dict(roman="Imaj7 Imaj7 II7 II7 ii7 V7 Imaj7 Imaj7 "
                                   "Imaj7 Imaj7 II7 II7 ii7 V7 Imaj7 Imaj7 "
                                   "IVmaj7 IVmaj7 IVmaj7 IVmaj7 II7 II7 ii7 V7 "
                                   "Imaj7 Imaj7 II7 II7 ii7 V7 Imaj7 Imaj7",
                             style="standard", level=2,
                             source="standard (Strayhorn, Take the A Train; usual key C)"),
}
# the usual key of a standard (the Backing track panel opens on it)
STANDARD_KEYS = {"blue bossa": "Cm", "autumn leaves": "Gm", "all of me": "C",
                 "take the a train": "C"}

MAJOR_STEPS = (0, 2, 4, 5, 7, 9, 11)          # I II III IV V VI VII on the major scale
NUMERALS = ("VII", "III", "VI", "IV", "II", "V", "I")   # longest first for the parser
DEGREE = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6}
FLAT_KEYS = {5, 10, 3, 8, 1, 6}                # F Bb Eb Ab Db Gb: spelled with flats
_TOKEN = re.compile(r"^([b#♭♯]?)(VII|III|VI|IV|II|V|I|vii|iii|vi|iv|ii|v|i)(.*)$")


def _root(acc, numeral, tonic):
    pc = (tonic + MAJOR_STEPS[DEGREE[numeral.upper()]]) % 12
    if acc in ("b", "♭"):
        pc -= 1
    elif acc in ("#", "♯"):
        pc += 1
    return pc % 12


def _name(pc, tonic, acc=""):
    """Root name: the sign of the numeral first (bII -> flat, #IV -> sharp), else the key
    (flats in F, Bb, Eb, Ab, Db, Gb)."""
    from .theory import FLAT_NAMES, SHARP_NAMES
    if acc in ("b", "♭"):
        return FLAT_NAMES[pc]
    if acc in ("#", "♯"):
        return SHARP_NAMES[pc]
    return FLAT_NAMES[pc] if tonic in FLAT_KEYS else SHARP_NAMES[pc]


def _suffix(lower, rest):
    """Chord suffix from the case of the numeral and what follows it."""
    rest = rest.replace("°", "dim").replace("Ø", "ø")
    rest = rest.replace("ø7", "m7b5").replace("ø", "m7b5")      # written as Dm7b5 (Levine)
    if not lower:
        return rest                                   # I, I7, Imaj7, I6, V7b9 …
    if rest in ("", "m"):
        return "m"
    if rest.startswith(("ø", "dim", "m7b5", "m")):
        return rest                                   # iiø7, iidim7, im6 written in full
    if rest == "7b5":
        return "m7b5"
    if rest.startswith("maj"):
        return "m(" + rest + ")"                      # i maj7 -> m(maj7)
    return "m" + rest                                 # ii7 -> m7, ii6 -> m6, ii9 -> m9


def roman_chord(token, key="C"):
    """Chord symbol of one Roman numeral in a key: 'ii7' in 'Bb' -> 'Cm7';
    'V7/ii' in 'C' -> 'A7' (the V7 of the ii degree)."""
    from .theory import pc_of, parse_chord
    tonic = pc_of(key) if isinstance(key, str) else int(key) % 12
    main, _, target = token.partition("/")
    if target:                                        # secondary: the key of the target
        mt = _TOKEN.match(target)
        if not mt:
            raise ValueError(f"unknown Roman numeral: {target}")
        tonic = _root(mt.group(1), mt.group(2), tonic)
    m = _TOKEN.match(main)
    if not m:
        raise ValueError(f"unknown Roman numeral: {token}")
    acc, num, rest = m.groups()
    pc = _root(acc, num, tonic)
    sym = _name(pc, tonic, acc) + _suffix(num.islower(), rest)
    parse_chord(sym)                                  # an unknown suffix raises here
    return sym


def in_key(roman, key="C"):
    """A whole Roman progression ('ii7 V7 Imaj7:vi7') as chord names in a key."""
    bars = []
    for bar in roman.split():
        bars.append(":".join(roman_chord(t, key) for t in bar.split(":")))
    return " ".join(bars)


def progression(name, key="C"):
    """Chord names of a progression: a CATALOGUE name or a Roman string, in a key."""
    row = CATALOGUE.get(name)
    return in_key(row["roman"] if row else name, key)


def names(style=None, level=None):
    """Names of the catalogue (optionally of one style / up to a level)."""
    return [n for n, r in CATALOGUE.items()
            if (style is None or r["style"] == style) and (level is None or r["level"] <= level)]


# ======================================================================== keys of the Generate panels
# (owner, 2026-11-13: duet / canon "Key" is a list, never typed — Android; changing the key
# moves the progression into it, "New" makes a different one in that key, minor included)
KEYS_MAJOR = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
KEYS_MINOR = ("Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "Bbm", "Bm")
KEYS = KEYS_MAJOR + KEYS_MINOR
_FLAT_KEY_NAMES = {"F", "Bb", "Eb", "Ab", "Db", "Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm"}

# major <-> minor of the same tonic, degree by degree: (interval from the tonic, minor?) ->
# (new interval, new minor?); the dominant V stays major; other chords keep their interval
_TO_MINOR = {(0, False): (0, True), (2, True): (2, "dim"), (4, True): (3, False),
             (5, False): (5, True), (9, True): (8, False), (11, "dim"): (10, False)}
_TO_MAJOR = {(0, True): (0, False), (2, "dim"): (2, True), (3, False): (4, True),
             (5, True): (5, False), (8, False): (9, True), (10, False): (11, "dim")}
# quality of the same chord made minor / major / diminished (sevenths kept as far as possible)
_AS_MINOR = {"": "m", "7": "m7", "maj7": "m7", "6": "m6", "9": "m9", "maj9": "m9",
             "add9": "madd9", "6/9": "m6", "13": "m13", "11": "m11", "dim": "m",
             "m7b5": "m7", "dim7": "m7"}
_AS_MAJOR = {"m": "", "m7": "maj7", "m6": "6", "m9": "maj9", "madd9": "add9", "m13": "13",
             "m11": "maj7", "m(maj7)": "maj7", "dim": "", "m7b5": "maj7", "dim7": "maj7"}
_AS_DIM = {"": "dim", "m": "dim", "7": "m7b5", "m7": "m7b5", "maj7": "m7b5", "m6": "dim",
           "6": "dim", "m9": "m7b5", "9": "m7b5"}


def key_parts(key):
    """(tonic pitch class, minor?) of a key name 'C', 'Cm', 'C#m', 'Bb'."""
    from .theory import pc_of
    k = key.strip()
    minor = k.endswith("m") and len(k) > 1
    return pc_of(k[:-1] if minor else k), minor


def key_name(tonic, minor):
    """Name in KEYS of a tonic pitch class and mode (C, Db, … ; Cm, C#m, …)."""
    return (KEYS_MINOR if minor else KEYS_MAJOR)[int(tonic) % 12]


def key_of_chords(text):
    """Key of a progression = its first chord (root, minor or major): 'Am F C G' -> 'Am'."""
    from .theory import parse_progression
    try:
        c = parse_progression(text)[0][0][0]
    except Exception:
        return "C"
    return key_name(c.root, c.is_minor)


def _class(chord):
    """True (minor), False (major), 'dim' (diminished / half-diminished), None (other)."""
    if chord.quality in ("dim", "dim7", "m7b5"):
        return "dim"
    if chord.third == 3:
        return True
    if chord.third == 4 and chord.quality not in ("aug", "aug7", "maj7#5"):
        return False
    return None


def _requalify(quality, cls):
    table = {True: _AS_MINOR, False: _AS_MAJOR, "dim": _AS_DIM}[cls]
    return table.get(quality, quality)


def _spell(pc, key):
    from .theory import FLAT_NAMES, SHARP_NAMES
    return (FLAT_NAMES if key in _FLAT_KEY_NAMES else SHARP_NAMES)[int(pc) % 12]


def chords_to_key(text, old_key, new_key):
    """The same progression moved from old_key to new_key, spelled for the new key:
    C F G G C F G C, C -> E = E A B B E A B E. Major -> minor of the tonic rewrites the
    diatonic chords in the minor key (I -> i, ii -> ii°, iii -> bIII, IV -> iv, vi -> bVI,
    vii° -> bVII; V stays major: the dominant), minor -> major the opposite; every other
    chord is only moved. Bars 'F:G' kept; Italian names come back in English."""
    from .theory import parse_chord, Chord
    o_t, o_m = key_parts(old_key)
    n_t, n_m = key_parts(new_key)
    table = _TO_MINOR if (not o_m and n_m) else _TO_MAJOR if (o_m and not n_m) else {}
    bars = []
    for tok in text.split():
        out = []
        for sym in tok.split(":"):
            c = parse_chord(sym)
            d, q = (c.root - o_t) % 12, c.quality
            hit = table.get((d, _class(c)))
            if hit:
                d, q = hit[0], _requalify(q, hit[1])
            root = (n_t + d) % 12
            name = _spell(root, new_key) + q
            if c.bass is not None:
                name += "/" + _spell(n_t + (c.bass - o_t) % 12, new_key)
            out.append(name)
        bars.append(":".join(out))
    return " ".join(bars)


# random diatonic progressions: degrees (Roman, as CATALOGUE) and their seventh-chord form
_RANDOM_MAJOR = dict(start="I", end=("V", "I"), pool=("ii", "iii", "IV", "V", "vi", "IV", "ii", "vi"))
_RANDOM_MINOR = dict(start="i", end=("V", "i"), pool=("iv", "V", "bVI", "bIII", "bVII", "ii°", "iv", "bVI"))
_SEVENTHS = {"I": "Imaj7", "ii": "ii7", "iii": "iii7", "IV": "IVmaj7", "V": "V7", "vi": "vi7",
             "i": "i7", "iv": "iv7", "bVI": "bVImaj7", "bIII": "bIIImaj7", "bVII": "bVII7",
             "ii°": "iiø7"}
_MINOR_CATALOGUE = ("ii-V-i minor", "minor blues", "so what")


def _random_roman(minor, rng):
    spec = _RANDOM_MINOR if minor else _RANDOM_MAJOR
    n = rng.choice((4, 8, 8))
    mid = [rng.choice(spec["pool"]) for _ in range(n - 3)]
    roman = [spec["start"]] + mid + list(spec["end"])
    if rng.random() < 0.4:
        roman = [_SEVENTHS.get(r, r) for r in roman]
    return " ".join(roman)


def new_progression(key="C", current=None, rng=None, level=2):
    """A progression in `key` (a name of KEYS) different from `current`: from the
    CATALOGUE (up to `level`, of the key's mode: minor keys the minor ones) or a random
    diatonic one (I … V I; minor: i iv V bVI bIII bVII ii°), spelled for the key."""
    import random
    rng = rng or random.Random()
    tonic, minor = key_parts(key)
    major_tonic = key_name(tonic, False)
    cat = [n for n in names(level=level) if (n in _MINOR_CATALOGUE) == minor
           and CATALOGUE[n]["style"] != "standard"]      # duets: never a whole standard
    norm = " ".join((current or "").split())
    out = None
    for _ in range(30):
        if cat and rng.random() < 0.5:
            roman = CATALOGUE[rng.choice(cat)]["roman"]
        else:
            roman = _random_roman(minor, rng)
        out = _respell(in_key(roman, major_tonic), key)
        if out != norm:
            break
    return out


def _respell(text, key):
    """Every chord root (and bass) spelled with the flats / sharps of `key`."""
    from .theory import parse_chord
    bars = []
    for tok in text.split():
        out = []
        for sym in tok.split(":"):
            c = parse_chord(sym)
            name = _spell(c.root, key) + c.quality
            if c.bass is not None:
                name += "/" + _spell(c.bass, key)
            out.append(name)
        bars.append(":".join(out))
    return " ".join(bars)
