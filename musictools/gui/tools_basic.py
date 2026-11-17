"""Transform tools: Generate > Duet, Generate > Exercises to do > (Read & play / Listen & repeat from MIDI or score), Convert > PDF -> MIDI,
Convert > MIDI -> PDF score, Convert > PDF -> trumpet fingerings. Input = the objects selected in Objects."""
import os
import tempfile

from ..duet import TEXTURES, DEFAULT_CHORDS
from ..midi import Midi
from ..pdf import Pdf
from ..score import Score
from ..phrase import (exercises_from_midi, PURPOSES, TRANSFORM_CHOICES, LEVEL_LABELS,
                      EXERCISE_INSTRUMENTS)
from .registry import Tool, Param, register
from ..progressions import KEYS, key_of_chords, chords_to_key, new_progression


# ---------------------------------------------------------------- Key and Chords linked
# (owner, 2026-11-13): Key is a list (never typed: Android), always filled; changing it
# moves the chords into the new key, "New" makes a different progression in the key, a
# chord list edited by hand (Mac only; on Android the chords will only be randomised)
# sets the key to its first chord.
def _key_changed(old, new, values):
    return {"chords": chords_to_key(values["chords"], old or key_of_chords(values["chords"]),
                                    new)}


def _new_chords(values):
    return {"chords": new_progression(values["key"], current=values["chords"])}


def _chords_changed(old, new, values):
    return {"key": key_of_chords(new)}


def _chord_params(default_chords, help_text):
    return [
        Param("chords", "str", default_chords, "Chords", help=help_text, button="New",
              action=_new_chords, on_change=_chords_changed),
        Param("key", "choice", key_of_chords(default_chords), "Key", choices=KEYS,
              on_change=_key_changed,
              help="key of the progression: changing it moves the chords into it"),
    ]


# ---------------------------------------------------------------- duet
def _duet(chords, rounds, level, key, concert, seed, bpm, phrase, textures, repetition):
    return Midi().makeduet(chords=chords, rounds=rounds, level=int(level), key=key or None,
                           concert=concert, seed=None if seed < 0 else seed, bpm=bpm,
                           phrase=phrase, textures=textures, repetition=repetition)


register(Tool(
    name="duet", label="Duet for two trumpets", category="Generate", kind="transform",
    func=_duet,
    name_fn=lambda m, p: f"Duet L{m.duet_info['level']} seed {m.duet_info['seed']}",
    help="Random duet for two Bb trumpets on a chord progression (concert-pitch MIDI).",
    params=[
        *_chord_params(DEFAULT_CHORDS, "one chord per bar, e.g. 'C F G C' or 'Do Fa Sol Do'; "
                       "'F:G' = two chords in a bar; New = a different progression in the key"),
        Param("rounds", "int", 2, "Rounds", minimum=1, maximum=16,
              help="times the progression is repeated"),
        Param("level", "choice", 1, "Level", choices=(1, 2, 3)),
        Param("concert", "bool", False, "Chords in concert pitch",
              help="unchecked: chords/key are written trumpet pitch"),
        Param("seed", "int", -1, "Seed", minimum=-1, maximum=999999,
              help="-1 = random; same seed = same duet"),
        Param("bpm", "float", 120, "Tempo (bpm)", minimum=30, maximum=240, step=1),
        Param("phrase", "int", 4, "Bars per phrase", minimum=1, maximum=16),
        Param("textures", "multi", None, "Textures", choices=tuple(TEXTURES),
              help="none selected = all allowed by the level"),
        Param("repetition", "float", 0.7, "Repetition", minimum=0, maximum=1, step=0.1,
              help="0 = free lines, 1 = strongly motivic"),
    ]))


# ---------------------------------------------------------------- canon
def _canon(chords, difficulty, beats_per_chord, cycles, key, concert, seed, bpm):
    return Midi().makecanon(chords=chords, difficulty=int(str(difficulty).split(" ")[0]),
                            beats_per_chord=beats_per_chord, cycles=cycles, key=key or None,
                            concert=concert, seed=None if seed < 0 else seed, bpm=bpm)


def _canon_levels():
    from ..canon import LEVEL_LABELS
    return tuple(LEVEL_LABELS.values())


register(Tool(
    name="canon", label="Canon for trumpets", category="Generate", kind="transform",
    func=_canon, name_fn=lambda m, p: f"Canon L{m.duet_info['level']} seed {m.duet_info['seed']}",
    help="Canon for two Bb trumpets on a chord progression: trumpet 2 plays what trumpet 1 "
         "played one progression earlier (port of canon_trumpets.py).",
    params=[
        *_chord_params("C F G C", "one chord per bar (or per 'Beats per chord'), e.g. 'C F G C' "
                       "or 'Do Fa Sol Do'; New = a different progression in the key"),
        Param("difficulty", "choice", _canon_levels()[1], "Difficulty", choices=_canon_levels()),
        Param("beats_per_chord", "int", 4, "Beats per chord", minimum=1, maximum=8),
        Param("cycles", "int", 4, "Cycles", minimum=1, maximum=12,
              help="times trumpet 1 plays the progression"),
        Param("concert", "bool", False, "Chords in concert pitch",
              help="unchecked: chords/key are written trumpet pitch (as the duet)"),
        Param("seed", "int", -1, "Seed", minimum=-1, maximum=999999,
              help="-1 = random; same seed = same canon"),
        Param("bpm", "float", 80, "Tempo (bpm)", minimum=30, maximum=240, step=1),
    ]))


# ---------------------------------------------------------------- merge, transpose
def _merge(*objs, title):
    from ..midi import merge
    m = merge(*objs)
    m.title = title or " + ".join((getattr(o, "title", None) or "MIDI") for o in objs)
    return m


register(Tool(
    name="merge", label="Merge MIDI", category="Convert", kind="transform",
    func=_merge, inputs=(Midi,), multi=True, name_fn=lambda m, p: m.title,
    help="One MIDI with all the tracks of the selected MIDI objects (was fondi_midi.py; "
         "every track keeps its own timing).",
    params=[Param("title", "str", "", "Title", help="empty = the names joined")]))


def _transpose(obj, semitones):
    from ..midi import transposed
    if isinstance(obj, Score):
        import copy
        sc = Score(copy.deepcopy(obj.m21), obj.title, obj.written).transpose(int(semitones))
        sc.title = f"{obj.title} ({int(semitones):+d})"
        return sc
    m = transposed(obj, semitones)
    m.title = f"{getattr(obj, 'title', None) or 'MIDI'} ({int(semitones):+d})"
    return m


register(Tool(
    name="transpose", label="Transpose", category="Convert", kind="transform",
    func=_transpose, inputs=(Midi, Score), name_fn=lambda m, p: m.title,
    help="A new MIDI / score k semitones up (down if negative); drums stay.",
    params=[Param("semitones", "int", 2, "Semitones", minimum=-24, maximum=24)]))


# ---------------------------------------------------------------- PDF -> MIDI
def _instruments():
    try:
        from ..pdf import scoreread
        return ("auto",) + tuple(sorted(scoreread().INSTRUMENTS))
    except Exception:
        return ("auto",)


def _pdf2midi(pdf, instrument, force):
    m = pdf.to_midi(instrument=None if instrument == "auto" else instrument, force=force)
    pdf._midi = m                      # Play on the PDF object reuses this conversion
    return m


register(Tool(
    name="pdf2midi", label="PDF → MIDI", category="Convert", kind="transform",
    func=_pdf2midi, inputs=(Pdf,),
    name_fn=lambda m, p: os.path.splitext(os.path.basename(m.source or "pdf"))[0] + " (MIDI)",
    help="Reads a single-part vector PDF (scoreread engine): concert pitch, repeats expanded.",
    params=[
        Param("instrument", "choice", "auto", "Instrument", choices=_instruments(),
              help="auto = read from the PDF text"),
        Param("force", "bool", False, "Write even with warnings",
              help="write the MIDI even if some bars do not add up"),
    ]))


# ---------------------------------------------------------------- MIDI -> PDF score
def _midi2pdf(midi, title):
    title = title or getattr(midi, "title", None) or "score"
    name = title.replace(os.sep, "_")
    path = os.path.join(tempfile.mkdtemp(prefix="musictools_"), f"{name}.pdf")
    if isinstance(midi, Score):
        midi.to_pdf(path)
    else:
        midi.to_pdf(path, title=title or None)
    p = Pdf(path)
    p.title = title
    return p


register(Tool(
    name="midi2pdf", label="MIDI / Score → PDF", category="Convert", kind="transform",
    func=_midi2pdf, inputs=(Midi, Score),
    name_fn=lambda p, prm: (p.title or "score") + " (PDF)",
    help="Engraved score (Verovio), transposing instruments at written pitch. "
         "Save it with 'Save as…'.",
    params=[Param("title", "str", "", "Title", help="empty = name of the object")]))


# ---------------------------------------------------------------- MIDI -> Score
def _midi2score(midi, title):
    title = title or getattr(midi, "title", None) or "score"
    return midi.to_score(title)


register(Tool(
    name="midi2score", label="MIDI → Score", category="Convert", kind="transform",
    func=_midi2score, inputs=(Midi,),
    name_fn=lambda sc, p: (sc.title or "score") + " (score)",
    help="Notation (bars, note values, key; transposing instruments at written pitch). "
         "A score editor will come later.",
    params=[Param("title", "str", "", "Title", help="empty = name of the object")]))


# ---------------------------------------------------------------- PDF -> fingerings
def _fingering(pdf, fontsize, space, color, no_repetition, instrument, save_next=False):
    """save_next (owner, 2026-11-13: 20 PDFs to save one by one): the new PDF is written
    at once next to the original as '<name>.noted.pdf' (as the command `fingering`; an
    older one with that name is replaced), and the object is that file."""
    path = None
    if save_next:
        src = getattr(pdf, "source", None) or pdf.path
        path = os.path.splitext(src)[0] + ".noted.pdf"
    out = pdf.fingering(path=path, fontsize=fontsize, space=space, color=color[0],
                        no_repetition=no_repetition,
                        instrument=None if instrument == "auto" else instrument)
    if path:
        out._saved_path = path
    return out


register(Tool(
    name="fingering", label="PDF → trumpet fingerings", category="Convert", kind="transform",
    func=_fingering, inputs=(Pdf,),
    name_fn=lambda s, p: os.path.splitext(os.path.basename(getattr(s, "source", s.path)))[0]
    + " (fingerings)",
    help="New PDF with the Bb trumpet valve fingerings under the notes (scoreread). "
         "Trumpet parts of vector PDFs only; the original is not changed.",
    params=[
        Param("fontsize", "float", 12, "Font size (pt)", minimum=6, maximum=30, step=1),
        Param("space", "float", 12, "Gap below the staff (pt)", minimum=0, maximum=60, step=1,
              help="below the note or the bottom line, whichever is lower"),
        Param("color", "choice", "k – black", "Colour",
              choices=("k – black", "r – red", "g – green", "b – blue")),
        Param("no_repetition", "bool", False, "No repetitions",
              help="repeated pairs of fingerings written once, then '-'"),
        Param("instrument", "choice", "auto", "Instrument", choices=("auto", "trumpet"),
              help="auto: read from the PDF; trumpet: when the name is not written in it"),
        Param("save_next", "bool", False, "Save next to the original",
              help="write each new PDF at once next to its original as '<name>.noted.pdf' "
                   "(an older one with that name is replaced); no Save needed"),
    ]))


# ---------------------------------------------------------------- exercises from MIDI
# one tool per exercise type (Generate > Exercises to do; owner 2026-11-07: Generate makes
# exercises TO DO, Practice does a quick exercise at once): each has its own options
def _bars_default(kind):
    def f():
        from ..exercise import exercise_settings
        return int(exercise_settings(kind).get("bars") or 1)
    return f


def _common_params(kind, polyphony=False):
    ps = [
        Param("bars", "int", _bars_default(kind), "Bars per exercise", minimum=1, maximum=64,
              help="starts from Settings > Exercises (default bars); change it for this "
                   "generation only"),
        Param("level", "choice", LEVEL_LABELS[3], "Simplify", choices=tuple(LEVEL_LABELS.values()),
              help="shortest note value kept; the other notes are removed"),
        Param("instrument", "choice", "Bb (trumpet)", "Instrument", choices=EXERCISE_INSTRUMENTS,
              help="Bb: written a tone above the sound (trumpet, clarinet…); C: piano, as it sounds"),
        Param("remove_empty", "bool", True, "Remove empty bars",
              help="bars with rests only are removed before cutting the exercises"),
        Param("include_midi", "bool", True, "Include the MIDI",
              help="unticked = do not include MIDI: no trace of the source MIDI in the "
                   "exercises (they cannot be cut again: only tempo and transposition)"),
    ]
    if polyphony:
        ps.append(Param("polyphony", "bool", False, "Polyphony",
                        help="off: one exercise per part, one voice (highest note of a chord); "
                             "on: all the parts together in one exercise (keyboard)"))
    ps += [
        Param("transform", "choice", "none", "Transformation", choices=TRANSFORM_CHOICES,
              help="transpose, reverse melody/rhythm, inversion, mode, remove accidentals, "
                   "even eighths; random = a different one (or none) for every exercise"),
        Param("seed", "int", -1, "Seed", minimum=-1, maximum=999999,
              help="-1 = random; same seed = same transformations"),
    ]
    return ps


def _make_exercises(purpose):
    kind = {"reading": "play_reading", "repeat": "listen_repeat"}[purpose]

    def f(obj, bars, level, instrument, remove_empty, transform, seed, polyphony=False,
          include_midi=True):
        bars = int(bars or 0) or None
        lv = int(str(level).split(" ")[0])
        from ..exercise import exercise_settings
        return exercises_from_midi(obj, purpose=purpose, bars=bars, transform=transform,
                                   seed=None if seed < 0 else seed, polyphony=polyphony,
                                   level=lv, instrument=instrument, remove_empty=remove_empty,
                                   practice_bpm=float(exercise_settings(kind).get("bpm", 90)),
                                   include_midi=include_midi)
    return f


register(Tool(
    name="exercises_reading", label="Read & play – generate from MIDI", category="Generate", kind="transform",
    submenu="Exercises to do", func=_make_exercises("reading"), inputs=(Midi, Score),
    name_fn=lambda s, p: s.title,
    help="Read & play exercises: every part of each selected MIDI/score cut into phrases "
         "(bars per exercise: default from Settings > Exercises > Read & play), one voice.",
    params=_common_params("play_reading")))

register(Tool(
    name="exercises_repeat", label="Listen & repeat – generate from MIDI", category="Generate", kind="transform",
    submenu="Exercises to do", func=_make_exercises("repeat"), inputs=(Midi, Score),
    name_fn=lambda s, p: s.title,
    help="Listen & repeat exercises: phrases to listen to and repeat (trumpet or MIDI "
         "keyboard); bars per exercise: default from Settings > Exercises > Listen & repeat.",
    params=_common_params("listen_repeat", polyphony=True)))


from . import tools_exercises  # noqa: E402,F401  (Generate > Exercises to do, Make a routine)
from . import playover_ui  # noqa: E402,F401  (Practice / Generate > Play over MIDI)

# Generate: planned tools (owner, 2026-11-06: menu items that do nothing yet, to remember them)
for _name, _label, _help in (
        ("backing_track", "Backing track from chords", "bass, chords and drums from a chord "
                                                        "sequence (also for improvisation)"),
        ("second_voice", "Second voice for a melody", "a second part (thirds / sixths, "
                                                       "counter-melody) for a MIDI melody"),
        ("melodies", "Melodies and etudes", "new melodies in a key and difficulty, as reading "
                                            "material"),
        ("brass_ensemble", "Brass trio / quartet", "the duet generator extended to 3-4 voices")):
    register(Tool(name=f"planned_{_name}", label=_label, category="Generate", kind="planned",
                  help=_help))
