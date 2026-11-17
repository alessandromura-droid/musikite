"""Generate > Exercises to do (owner, 2026-11-07): exercises WITHOUT results, to be done
later (double click on them, or in a routine): Read & play from duets, long tones, scales &
arpeggios, lip slurs, rhythm reading, intervals, interval reading, chord qualities, flash
cards (Read & play / Listen &
repeat from a MIDI or score are in tools_basic). Generate > Make a routine: the selected
exercises, in their order, as a routine (copies). Logic in tasks.py / phrase.py / drills.py."""
from .registry import Tool, Param, register
from .. import drills as dr
from ..phrase import (LEVEL_LABELS, EXERCISE_INSTRUMENTS, INSTRUMENTS, DUET_PARTS,
                      exercises_from_duets, instrument_range)
from ..theory import note_name, parse_note

SUB = "Exercises to do"
NOTES = tuple(note_name(p) for p in range(48, 89))


def _saved(kind, key):
    """Default of an option: the last value used in the Practice tab of this drill."""
    def f():
        from ..progress import settings
        s = dr.settings_of(kind, settings().get("drills", {}).get(kind))
        v = s.get(key)
        if key in ("lowest", "highest"):
            lo, hi = instrument_range("Bb (trumpet)")
            v = note_name(int(v or (lo if key == "lowest" else hi)))
        if key == "level" and kind == "lip_slurs":
            v = dr.SLUR_LABELS.get(int(v), v)
        if key == "level" and kind == "rhythm":
            v = dr.RHYTHM_LEVELS.get(int(v), v)
        return v
    return f


def _count(default=5):
    return Param("count", "int", default, "How many", minimum=1, maximum=100,
                 help="number of exercises made (each one is an object to do)")


def _first_int(v):
    return int(str(v).split(" ")[0])


def _seed():
    return Param("seed", "int", -1, "Seed", minimum=-1, maximum=999999,
                 help="-1 = random; same seed = same exercises")


def _s(seed):
    return None if seed is None or seed < 0 else seed


# ---------------------------------------------------------------- Read & play / Listen & repeat
# "generate random" (owner, 2026-11-08): each exercise a piece of a NEW duet generated from the
# theory engine (the same ones Practice > Read & play / Listen & repeat make one at a time)
def _random_tool(purpose):
    kind = {"reading": "play_reading", "repeat": "listen_repeat"}[purpose]

    def f(count, bars, level, instrument, part, include_midi, seed):
        from ..exercise import exercise_settings
        st = exercises_from_duets(count, purpose, int(bars), _first_int(level), instrument,
                                  part, _s(seed))
        for ph in st.phrases:                # tempo of the exercises: Settings > <type>
            ph.practice_bpm = float(exercise_settings(kind).get("bpm", 90))
            if not include_midi:             # do not include MIDI: no trace of the duet
                ph.source_midi = None
                ph.origin = {k: v for k, v in (ph.origin or {}).items() if k != "midi"} or None
        return st
    return f


for _purpose, _name, _label, _bars, _instr in (
        ("reading", "todo_duets", "Read & play – generate random", 4, EXERCISE_INSTRUMENTS),
        ("repeat", "todo_duets_repeat", "Listen & repeat – generate random", 2,
         tuple(INSTRUMENTS))):
    register(Tool(
        name=_name, label=_label, category="Generate", kind="transform",
        submenu=SUB, func=_random_tool(_purpose), name_fn=lambda s, p: s.title,
        help="A group of new random exercises (made from the theory engine): different "
             "every time.",
        params=[_count(), Param("bars", "int", _bars, "Bars per exercise", minimum=1,
                                maximum=16),
                Param("level", "choice", LEVEL_LABELS[3], "Simplify",
                      choices=tuple(LEVEL_LABELS.values())),
                Param("instrument", "choice", "Bb (trumpet)", "Instrument", choices=_instr),
                Param("part", "choice", "random", "Part", choices=DUET_PARTS),
                Param("include_midi", "bool", True, "Include the MIDI",
                      help="unticked = do not include MIDI: the exercises keep no trace of "
                           "the duet (they cannot be cut again: only tempo and transposition)"),
                _seed()]))


# ---------------------------------------------------------------- drills
def _grouped(tasks):
    """Generate with How many > 1 -> ONE group ▦ of exercises (owner, 2026-11-08)."""
    from ..tasks import group_or_single
    tasks = list(tasks)
    return group_or_single(tasks, tasks[0].label if tasks else "Exercises")


def _drill_tool(kind, params, convert):
    def f(count, seed, **kw):
        from ..tasks import new_drill_tasks
        return _grouped(new_drill_tasks(kind, count, _s(seed), **convert(kw)))
    register(Tool(
        name=f"todo_{kind}", label=dr.LABELS[kind], category="Generate", kind="transform",
        submenu=SUB, func=f, name_fn=lambda t, p: t.title,
        help=f"{dr.LABELS[kind]} to do: new exercises with these settings (the metronome, "
             "the input and the bpm can be changed when doing them).",
        params=[_count()] + params + [_seed()]))


def _notes(kw):
    for k in ("lowest", "highest"):
        if k in kw and kw[k] is not None:
            kw[k] = parse_note(kw[k])
    return kw


def _lt(kw):
    return _notes(kw)


def _sc(kw):
    kw = _notes(kw)
    kw["keys"] = kw.get("keys") or list(dr.KEYS[:4])
    kw["types"] = kw.get("types") or ["major"]
    return kw


def _ls(kw):
    kw = _notes(kw)
    kw["positions"] = kw.get("positions") or ["0"]
    kw["level"] = _first_int(kw["level"])
    return kw


def _rh(kw):
    kw["level"] = _first_int(kw["level"])
    return kw


_drill_tool("long_tones", [
    Param("lowest", "choice", _saved("long_tones", "lowest"), "Lowest (written)", choices=NOTES),
    Param("highest", "choice", _saved("long_tones", "highest"), "Highest (written)", choices=NOTES),
    Param("notes", "int", _saved("long_tones", "notes"), "Notes per exercise", minimum=1, maximum=12),
    Param("beats", "int", _saved("long_tones", "beats"), "Beats each", minimum=2, maximum=16),
    Param("rest", "int", _saved("long_tones", "rest"), "Rest beats", minimum=1, maximum=8),
    Param("bpm", "int", _saved("long_tones", "bpm"), "bpm", minimum=30, maximum=220)], _lt)

_drill_tool("scales", [
    Param("keys", "multi", _saved("scales", "keys"), "Keys (written)", choices=dr.KEYS),
    Param("types", "multi", _saved("scales", "types"), "Types", choices=tuple(dr.SCALE_TYPES)),
    Param("octaves", "int", _saved("scales", "octaves"), "Octaves", minimum=1, maximum=2),
    Param("pattern", "choice", _saved("scales", "pattern"), "Pattern",
          choices=dr.SCALE_PATTERNS),
    Param("note", "choice", _saved("scales", "note"), "Rhythm",
          choices=dr.SCALE_NOTES),
    Param("instrument", "choice", _saved("scales", "instrument"), "Instrument",
          choices=("Bb (trumpet)", "C (piano)")),
    Param("lowest", "choice", _saved("scales", "lowest"), "Lowest (written)", choices=NOTES),
    Param("highest", "choice", _saved("scales", "highest"), "Highest (written)", choices=NOTES),
    Param("bpm", "int", _saved("scales", "bpm"), "bpm", minimum=30, maximum=220)], _sc)

_drill_tool("lip_slurs", [
    Param("positions", "multi", _saved("lip_slurs", "positions"), "Valves",
          choices=tuple(dr.VALVES)),
    Param("level", "choice", _saved("lip_slurs", "level"), "Level",
          choices=tuple(dr.SLUR_LABELS.values())),
    Param("note", "choice", _saved("lip_slurs", "note"), "Note value",
          choices=("whole", "half", "quarter")),
    Param("highest", "choice", _saved("lip_slurs", "highest"), "Highest (written)", choices=NOTES),
    Param("bpm", "int", _saved("lip_slurs", "bpm"), "bpm", minimum=30, maximum=220)], _ls)

_drill_tool("rhythm", [
    Param("level", "choice", _saved("rhythm", "level"), "Difficulty",
          choices=tuple(dr.RHYTHM_LEVELS.values())),
    Param("bars", "int", _saved("rhythm", "bars"), "Bars", minimum=1, maximum=8),
    Param("time", "choice", _saved("rhythm", "time"), "Time", choices=("4/4", "3/4", "2/4", "6/8")),
    Param("bpm", "int", _saved("rhythm", "bpm"), "bpm", minimum=30, maximum=220)], _rh)


def _ca(kw):
    kw["clicks"] = int(kw["clicks"])
    return kw


def _progression_names():
    from ..progressions import CATALOGUE
    return tuple(CATALOGUE)


_drill_tool("chord_arpeggios", [
    Param("progression", "choice", _saved("chord_arpeggios", "progression"), "Progression",
          choices=_progression_names()),
    Param("key", "choice", _saved("chord_arpeggios", "key"), "Key (written)", choices=dr.KEYS),
    Param("instrument", "choice", _saved("chord_arpeggios", "instrument"), "Instrument",
          choices=dr.CHORD_INSTRUMENTS),
    Param("clicks", "choice", lambda: str(_saved("chord_arpeggios", "clicks")()),
          "Clicks a chord", choices=tuple(str(n) for n in dr.CHORD_CLICKS)),
    Param("times", "int", _saved("chord_arpeggios", "times"), "Times", minimum=1, maximum=4),
    Param("help", "bool", _saved("chord_arpeggios", "help"), "Show the notes",
          help="easy version: the chord tones and tensions are shown"),
    Param("random", "bool", _saved("chord_arpeggios", "random"), "Random",
          help="change every time: progression, key and clicks a chord at random for every "
               "exercise (in a routine 'new each time': a different one every day)"),
    Param("bpm", "int", _saved("chord_arpeggios", "bpm"), "bpm", minimum=30, maximum=220)], _ca)


# ---------------------------------------------------------------- intervals
def _n_questions(kind):
    def f():
        from ..exercise import exercise_settings
        return int(exercise_settings(kind)["n_questions"])
    return f


def _intervals(count, n_questions, intervals, mode, instrument, seed):
    from ..eartraining import INTERVALS, DEFAULT_WEIGHTS
    from ..tasks import new_quiz_tasks
    chosen = {k for k, v in INTERVALS.items() if v in (intervals or [])}
    weights = {k: ((DEFAULT_WEIGHTS[k] or 1) if k in chosen else 0) for k in range(1, 13)} \
        if chosen else None
    return _grouped(new_quiz_tasks("intervals", count, n_questions, _s(seed), weights=weights,
                          mode=mode, instrument=instrument))


def _interval_names():
    from ..eartraining import INTERVALS, DEFAULT_WEIGHTS
    return tuple(INTERVALS[k] for k in range(1, 13)), \
        [INTERVALS[k] for k in range(1, 13) if DEFAULT_WEIGHTS[k] > 0]


def _modes():
    from ..eartraining import MODES, INSTRUMENTS
    return tuple(MODES), tuple(INSTRUMENTS)


_names, _default_names = _interval_names()
_mode_list, _instr_list = _modes()

register(Tool(
    name="todo_intervals", label="Intervals (ear training)", category="Generate",
    kind="transform", submenu=SUB, func=_intervals, name_fn=lambda t, p: t.title,
    help="Blocks of interval questions to do (the questions are drawn now; doing one again "
         "asks the same ones in another order).",
    params=[_count(3), Param("n_questions", "int", _n_questions("intervals"), "Questions each",
                             minimum=1, maximum=100),
            Param("intervals", "multi", _default_names, "Intervals", choices=_names),
            Param("mode", "choice", _mode_list[0], "Mode", choices=_mode_list),
            Param("instrument", "choice", _instr_list[0], "Instrument", choices=_instr_list),
            _seed()]))


def _reading(count, n_questions, answer, accidentals, clef, display, seed):
    from ..tasks import new_quiz_tasks
    return _grouped(new_quiz_tasks("interval_reading", count, n_questions, _s(seed),
                          answer="number" if answer == "number only" else "quality",
                          accidentals=accidentals, clef=clef, display=display))


def _reading_choices():
    from ..reading import CLEFS, DISPLAYS
    return tuple(CLEFS), tuple(DISPLAYS)


_clefs, _displays = _reading_choices()

register(Tool(
    name="todo_interval_reading", label="Interval reading", category="Generate",
    kind="transform", submenu=SUB, func=_reading, name_fn=lambda t, p: t.title,
    help="Blocks of interval-reading questions to do (same questions, another order, when "
         "done again).",
    params=[_count(3), Param("n_questions", "int", _n_questions("interval_reading"),
                             "Questions each", minimum=1, maximum=100),
            Param("answer", "choice", "number + quality", "Answer",
                  choices=("number + quality", "number only")),
            Param("accidentals", "bool", False, "Accidentals"),
            Param("clef", "choice", _clefs[0], "Clef", choices=_clefs),
            Param("display", "choice", _displays[0], "Notes", choices=_displays), _seed()]))


# ---------------------------------------------------------------- chord qualities, flash cards
def _chords(count, n_questions, qualities, mode, inversions, instrument, seed):
    from ..eartraining import CHORD_LABELS, DEFAULT_CHORDS
    from ..tasks import new_quiz_tasks
    q = [k for k, v in CHORD_LABELS.items() if v in (qualities or [])] or list(DEFAULT_CHORDS)
    return _grouped(new_quiz_tasks("chords", count, n_questions, _s(seed), qualities=q, mode=mode,
                          inversions=inversions, instrument=instrument))


def _chord_choices():
    from ..eartraining import CHORD_LABELS, DEFAULT_CHORDS, CHORD_MODES
    return (tuple(CHORD_LABELS.values()), [CHORD_LABELS[k] for k in DEFAULT_CHORDS],
            tuple(CHORD_MODES))


_chord_names, _chord_default, _chord_modes = _chord_choices()

register(Tool(
    name="todo_chords", label="Chord qualities (ear training)", category="Generate",
    kind="transform", submenu=SUB, func=_chords, name_fn=lambda t, p: t.title,
    help="Blocks of chord-quality questions to do (same questions, another order, when done "
         "again).",
    params=[_count(3), Param("n_questions", "int", _n_questions("chords"), "Questions each",
                             minimum=1, maximum=100),
            Param("qualities", "multi", _chord_default, "Qualities", choices=_chord_names),
            Param("mode", "choice", _chord_modes[0], "Mode", choices=_chord_modes),
            Param("inversions", "bool", False, "Inversions"),
            Param("instrument", "choice", _instr_list[0], "Instrument", choices=_instr_list),
            _seed()]))


def _flash(count, n_questions, answer, accidentals, lowest, highest, seed):
    from ..tasks import new_quiz_tasks
    return _grouped(new_quiz_tasks("flashcards", count, n_questions, _s(seed), answer=answer,
                          accidentals=accidentals, lowest=parse_note(lowest),
                          highest=parse_note(highest)))


def _flash_range(i):
    def f():
        return note_name(instrument_range("Bb (trumpet)")[i])
    return f


_FLASH_NOTES = tuple(note_name(p) for p in range(54, 92))

register(Tool(
    name="todo_flashcards", label="Fingerings & note names", category="Generate",
    kind="transform", submenu=SUB, func=_flash, name_fn=lambda t, p: t.title,
    help="Blocks of flash cards to do: a note on the staff -> its valves or its name.",
    params=[_count(3), Param("n_questions", "int", _n_questions("flashcards"), "Questions each",
                             minimum=1, maximum=100),
            Param("answer", "choice", "fingering", "Answer", choices=("fingering", "note name")),
            Param("accidentals", "bool", True, "Accidentals"),
            Param("lowest", "choice", _flash_range(0), "Lowest (written)", choices=_FLASH_NOTES),
            Param("highest", "choice", _flash_range(1), "Highest (written)",
                  choices=_FLASH_NOTES), _seed()]))


# ---------------------------------------------------------------- routine
def _routine(*objs, title, fresh):
    from ..tasks import Routine
    return Routine.from_objects(objs, title or "Routine", fresh)


def _routine_inputs():
    from ..phrase import Phrase, ExerciseSet
    from ..tasks import Task, Routine
    return (Phrase, ExerciseSet, Task, Routine)


register(Tool(
    name="routine", label="Make a routine", category="Generate", kind="transform",
    func=_routine, inputs=_routine_inputs(), multi=True, name_fn=lambda r, p: r.title,
    help="The selected exercises (in their order in Objects; a group = its exercises) as a "
         "ROUTINE: done one after the other, every day. The items are copies; 'New each time' "
         "makes drills, interval blocks and pieces of duets new every day (it can be changed "
         "per item in the routine). Order: Up / Down in the routine tab.",
    params=[Param("title", "str", "Routine", "Title"),
            Param("fresh", "bool", False, "New each time",
                  help="drills, interval blocks, Read & play from duets: a new exercise every "
                       "day; the others always the same")]))
