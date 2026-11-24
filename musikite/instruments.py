"""
INSTRUMENTS PLAYED (owner, 2026-11-17/18): the catalogue of the instruments a user can study
and the CURRENT INSTRUMENT of the session. Pure Python, no Qt, no music21 (Android).

Every user says which instruments they play ("instruments played", settings key
`instruments`); the PIANO is given to every user (as in the conservatories). Beside the user
in the toolbar the user chooses the instrument studied now: exercises are proposed and
generated for it (no Instrument field inside the exercises any more), the Practice menu
offers what fits it (lip slurs only on valve brass, long tones only on wind instruments),
every instrument's exercises are drawn the same way in Objects. The PREFERRED instrument
(settings key `preferred_instrument`) is the one selected when the user is opened.

Keys of the catalogue = the old exercise instrument names ("Bb (trumpet)", "C (piano)",
"C (trombone)"), kept so that saved exercises and settings stay valid.

    from musikite import instruments as ins
    ins.current()                     # 'Bb (trumpet)'
    ins.played()                      # 'trumpet' (Phrase.instrument of its exercises)
    ins.row('Eb (alto sax)')['transposition']   # 9
    ins.user_instruments()            # ['Bb (trumpet)', 'C (piano)']

Columns: played = the name stored in the exercises (Phrase.instrument); label; part = the
name of the part on the staff; family ('brass', 'sax', 'woodwind', 'keyboard'); transposition
= written - concert (semitones); program = General MIDI sound; clef forced on its exercises
(None = chosen from the notes); range = default WRITTEN range of the exercises (MIDI);
detect = CONCERT range searched in a recording (None = the trumpet's, transcribe.RANGE);
lip_slurs = lip slur drills (valve brass). The piano is meant for a MIDI keyboard: from the
microphone its notes are recognised only roughly (detect.py, family 'decaying').
"""
PIANO = "C (piano)"
TRUMPET = "Bb (trumpet)"

CATALOGUE = {
    "Bb (trumpet)": dict(played="trumpet", label="Trumpet in Bb", part="Trumpet in Bb",
                         family="brass", transposition=2, program=56, clef="treble",
                         range=(55, 77), detect=None, lip_slurs=True),
    "Bb (cornet)": dict(played="cornet", label="Cornet in Bb", part="Cornet in Bb",
                        family="brass", transposition=2, program=56, clef="treble",
                        range=(55, 77), detect=None, lip_slurs=True),
    "Bb (flugelhorn)": dict(played="flugelhorn", label="Flugelhorn in Bb",
                            part="Flugelhorn in Bb", family="brass", transposition=2,
                            program=56, clef="treble", range=(55, 77), detect=None,
                            lip_slurs=True),
    "C (trumpet)": dict(played="trumpet in C", label="Trumpet in C", part="Trumpet in C",
                        family="brass", transposition=0, program=56, clef="treble",
                        range=(55, 77), detect=(53, 84), lip_slurs=True),
    # treble-clef valve brass reading the trumpet's chart on the written note (2026-11-19)
    "Eb (tenor horn)": dict(played="tenor horn", label="Tenor horn in Eb (alto horn)",
                            part="Tenor Horn in Eb", family="brass", transposition=9,
                            program=60, clef="treble", range=(55, 77), detect=(44, 72),
                            lip_slurs=True),
    "F (mellophone)": dict(played="mellophone", label="Mellophone in F", part="Mellophone in F",
                           family="brass", transposition=7, program=60, clef="treble",
                           range=(55, 77), detect=(46, 74), lip_slurs=True),
    "F (horn)": dict(played="horn", label="Horn in F", part="Horn in F", family="brass",
                     transposition=7, program=60, clef="treble", range=(55, 77),
                     detect=(36, 74), lip_slurs=False),
    # EUPHONIUM (owner, 2026-11-19, from todo.md): in Bb reading the TREBLE clef (the British
    # baritone / euphonium part: written a major ninth above, the trumpet's chart on the
    # written note, lip slurs as the trumpet) or in C reading the BASS clef (concert pitch);
    # 3 valves (no 4th valve yet: notes below E2 concert have no fingering); GM 58 as scoreread
    "Bb (euphonium, treble clef)": dict(played="euphonium treble",
                                        label="Euphonium in Bb (treble clef)",
                                        part="Euphonium in Bb", family="brass",
                                        transposition=14, program=58, clef="treble",
                                        range=(54, 84), detect=(38, 74), lip_slurs=True),
    "C (euphonium)": dict(played="euphonium", label="Euphonium (bass clef)", part="Euphonium",
                          family="brass", transposition=0, program=58, clef="bass",
                          range=(40, 70), detect=(38, 74), lip_slurs=False),
    "C (trombone)": dict(played="trombone", label="Trombone", part="Trombone", family="brass",
                         transposition=0, program=57, clef="bass", range=(40, 70),
                         detect=(38, 74), lip_slurs=False),
    "C (bass trombone)": dict(played="bass trombone", label="Bass trombone",
                              part="Bass Trombone", family="brass", transposition=0,
                              program=57, clef="bass", range=(36, 65), detect=(30, 70),
                              lip_slurs=False),
    # TUBAS (2026-11-19): all read the bass clef at concert pitch; the fingerings change with
    # the key of the instrument (fingerings.py); the sousaphone = the tuba in Bb, slower
    # notes (min_note_s: the shortest note a translated exercise keeps, seconds)
    "Bb (tuba)": dict(played="tuba", label="Tuba in Bb (BBb)", part="Tuba", family="brass",
                      transposition=0, program=58, clef="bass", range=(34, 58),
                      detect=(26, 65), lip_slurs=False),
    "C (tuba)": dict(played="tuba in C", label="Tuba in C (CC)", part="Tuba", family="brass",
                     transposition=0, program=58, clef="bass", range=(36, 60),
                     detect=(26, 67), lip_slurs=False),
    "Eb (tuba)": dict(played="tuba in Eb", label="Tuba in Eb", part="Tuba", family="brass",
                      transposition=0, program=58, clef="bass", range=(39, 63),
                      detect=(29, 70), lip_slurs=False),
    "F (tuba)": dict(played="tuba in F", label="Tuba in F", part="Tuba", family="brass",
                     transposition=0, program=58, clef="bass", range=(41, 65),
                     detect=(31, 72), lip_slurs=False),
    "Bb (sousaphone)": dict(played="sousaphone", label="Sousaphone in Bb", part="Sousaphone",
                            family="brass", transposition=0, program=58, clef="bass",
                            range=(34, 58), detect=(26, 65), lip_slurs=False,
                            min_note_s=0.25),
    "Bb (soprano sax)": dict(played="soprano sax", label="Soprano saxophone in Bb",
                             part="Soprano Saxophone in Bb", family="sax", transposition=2,
                             program=64, clef="treble", range=(60, 84), detect=(54, 89),
                             lip_slurs=False),
    "Eb (alto sax)": dict(played="alto sax", label="Alto saxophone in Eb",
                          part="Alto Saxophone in Eb", family="sax", transposition=9,
                          program=65, clef="treble", range=(60, 84), detect=(47, 82),
                          lip_slurs=False),
    "Bb (tenor sax)": dict(played="tenor sax", label="Tenor saxophone in Bb",
                           part="Tenor Saxophone in Bb", family="sax", transposition=14,
                           program=66, clef="treble", range=(60, 84), detect=(42, 77),
                           lip_slurs=False),
    "Eb (baritone sax)": dict(played="baritone sax", label="Baritone saxophone in Eb",
                              part="Baritone Saxophone in Eb", family="sax", transposition=21,
                              program=67, clef="treble", range=(60, 84), detect=(35, 70),
                              lip_slurs=False),
    "Bb (clarinet)": dict(played="clarinet", label="Clarinet in Bb", part="Clarinet in Bb",
                          family="woodwind", transposition=2, program=71, clef="treble",
                          range=(55, 79), detect=(48, 96), lip_slurs=False),
    "A (clarinet)": dict(played="clarinet in A", label="Clarinet in A", part="Clarinet in A",
                         family="woodwind", transposition=3, program=71, clef="treble",
                         range=(55, 79), detect=(48, 94), lip_slurs=False),
    "Eb (clarinet)": dict(played="clarinet in Eb", label="Clarinet in Eb",
                          part="Clarinet in Eb", family="woodwind", transposition=-3,
                          program=71, clef="treble", range=(55, 79), detect=(55, 98),
                          lip_slurs=False),
    "Bb (bass clarinet)": dict(played="bass clarinet", label="Bass clarinet in Bb",
                               part="Bass Clarinet in Bb", family="woodwind",
                               transposition=14, program=71, clef="treble", range=(55, 79),
                               detect=(34, 70), lip_slurs=False),
    "C (oboe)": dict(played="oboe", label="Oboe", part="Oboe", family="woodwind",
                     transposition=0, program=68, clef="treble", range=(60, 84),
                     detect=(57, 94), lip_slurs=False),
    "F (english horn)": dict(played="english horn", label="English horn in F",
                             part="English Horn in F", family="woodwind", transposition=7,
                             program=69, clef="treble", range=(60, 84), detect=(50, 86),
                             lip_slurs=False),
    "C (bassoon)": dict(played="bassoon", label="Bassoon", part="Bassoon", family="woodwind",
                        transposition=0, program=70, clef="bass", range=(36, 67),
                        detect=(33, 77), lip_slurs=False),
    "C (piccolo)": dict(played="piccolo", label="Piccolo", part="Piccolo", family="woodwind",
                        transposition=-12, program=72, clef="treble", range=(62, 91),
                        detect=(72, 108), lip_slurs=False),
    "C (flute)": dict(played="flute", label="Flute", part="Flute", family="woodwind",
                      transposition=0, program=73, clef="treble", range=(60, 86),
                      detect=(58, 98), lip_slurs=False),
    "C (piano)": dict(played="piano", label="Piano", part="Piano", family="keyboard",
                      transposition=0, program=0, clef=None, range=(55, 77), detect=None,
                      lip_slurs=False),
}
KEYS = tuple(CATALOGUE)
FAMILY_LABELS = {"brass": "Brass", "sax": "Saxophones", "woodwind": "Woodwinds",
                 "keyboard": "Keyboard"}
_PLAYED = {r["played"]: k for k, r in CATALOGUE.items()}
# GM program -> played name (exercises without an instrument: from their sound)
PROGRAM_PLAYED = {56: "trumpet", 59: "trumpet", 57: "trombone", 58: "tuba", 60: "horn",
                  68: "oboe", 69: "english horn", 70: "bassoon", 72: "piccolo",
                  64: "soprano sax",
                  65: "alto sax", 66: "tenor sax", 67: "baritone sax", 71: "clarinet",
                  73: "flute"}
_current = {"key": None}


def row(key):
    """The catalogue row of an instrument key (KeyError if unknown)."""
    return CATALOGUE[key]


def label(key):
    return CATALOGUE[key]["label"] if key in CATALOGUE else str(key)


def played(key=None):
    """Name stored in the exercises ('trumpet', 'alto sax', 'piano') of a key (None: the
    current instrument)."""
    key = current() if key is None else key
    return CATALOGUE[key]["played"] if key in CATALOGUE else None


def key_of_played(name):
    """Catalogue key of a played name ('trumpet' -> 'Bb (trumpet)'); None if unknown."""
    return _PLAYED.get(name)


def is_wind(key):
    return key in CATALOGUE and CATALOGUE[key]["family"] != "keyboard"


def has_lip_slurs(key):
    return key in CATALOGUE and bool(CATALOGUE[key]["lip_slurs"])


# ---------------------------------------------------------------- the user's instruments
def _settings():
    try:
        from .progress import settings
        return settings()
    except Exception:
        return {}


def user_instruments(user=None):
    """Instruments played by a user (catalogue order); the piano is always there. A user
    who never chose: the trumpet and the piano (the app's first users)."""
    try:
        from .progress import settings
        s = settings(user)
    except Exception:
        s = {}
    chosen = s.get("instruments")
    if not chosen:
        chosen = [TRUMPET]
    out = [k for k in KEYS if k in chosen and k != PIANO]
    return out + [PIANO]


def set_user_instruments(keys, user=None):
    """Save the instruments played (unknown keys dropped; the piano always added)."""
    from .progress import save_setting
    keys = [k for k in KEYS if k in (keys or ()) and k != PIANO] + [PIANO]
    save_setting("instruments", keys, user)
    pref = preferred(user)
    if pref not in keys:
        save_setting("preferred_instrument", keys[0], user)
    return keys


def preferred(user=None):
    """The instrument selected when the user is opened (the first one played if none)."""
    try:
        from .progress import settings
        p = settings(user).get("preferred_instrument")
    except Exception:
        p = None
    mine = user_instruments(user)
    return p if p in mine else mine[0]


def set_preferred(key, user=None):
    from .progress import save_setting
    if key not in user_instruments(user):
        raise ValueError(f"{key} is not among the instruments played")
    save_setting("preferred_instrument", key, user)
    return key


def current():
    """The instrument studied now (the toolbar choice; at the start the preferred one)."""
    k = _current["key"]
    if k in CATALOGUE:                 # chosen by the app among the user's instruments
        return k
    return preferred()


def set_current(key):
    """Choose the instrument studied now (None = back to the preferred one)."""
    if key is not None and key not in CATALOGUE:
        raise ValueError(f"unknown instrument {key}; known: {', '.join(KEYS)}")
    _current["key"] = key
    return current()


def reset_current():
    """A new user: the preferred instrument again."""
    _current["key"] = None
