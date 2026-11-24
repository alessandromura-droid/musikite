"""
POWER TAB (.ptb) reader (owner, 2026-11-19): reads the files of Power Tab Editor 1.7
("ptab" version 4) and turns them into MIDI. Pure Python (mido for writing), no Qt, no
music21.

Port to Python of the Power Tab import of TuxGuitar (common/TuxGuitar-ptb:
PTInputStream, PTSongSynchronizerUtil, PTSongParser, TrackStartHelper — by Julián
Casadesús, GNU LGPL; https://github.com/helge17/tuxguitar), with these differences:
- the CAPO is applied (TuxGuitar ignores it): pitch = tuning + capo + fret;
- the time signature byte is read unsigned (numerator = high 5 bits + 1, denominator =
  2 ** low 3 bits); the common time / cut time flags give 4/4 / 2/2;
- a time signature counts only where Power Tab SHOWS it (flag 0x100000 of the time
  signature, or common / cut time): the bar lines where it is not shown keep the current
  one (owner, 2026-11-19: whole pieces came out in 1/4 — the hidden time signatures of the
  bar lines hold a meaningless meter);
- a TIED note lengthens the previous note on the same string (one MIDI note);
- dead notes (x) and grace notes are not written.

What is read: song information, the two scores (guitar score, bass score), every guitar
(name, GM program, volume, tuning, capo), the systems with their bar lines (repeats, time
signatures), directions (D.C., D.S., Coda, Fine…), alternate endings, "guitar in" marks
(which guitar plays on which staff), tempo markers, the notes of the two voices of every
staff (duration, dots, tuplets, multi-bar rests). Repeats, alternate endings and the
directions are EXPANDED as they are played (as TuxGuitar). Chord diagrams, floating texts,
dynamics, rhythm slashes, chord names and the note effects (bends, slides…) are read and
skipped.

    from musikite import powertab
    song = powertab.read("song.ptb")          # PTSong
    mf = powertab.to_midi_file("song.ptb")    # mido.MidiFile
    powertab.convert("song.ptb", "song.mid")
    m = powertab.to_midi("song.ptb")          # musikite Midi object

One MIDI track per guitar actually played (its name, GM program, a channel of its own; the
drum channel 10 is never used), plus the first track with tempo and time signatures;
resolution 960 ticks per quarter.

MONOPHONIC (owner, 2026-11-19; `monophonic=True`, script switch --mono): ONE track with the
HIGHEST note of all the guitars at every moment (`skyline`): at every onset the highest note
starting there; it is kept unless a higher note is still sounding, and it cuts the note
before it; the program and name of the first guitar.

PROGRAM (owner, 2026-11-19; `program=56`, script switch --trumpet): every track gets that
General MIDI program (56 = trumpet) instead of the guitar's.

ONE TIME SIGNATURE (owner, 2026-11-19: files gave absurd changes such as 4/4 -> 3/4 -> 1/4 ->
4/4): the MIDI gets ONLY the first time signature, the later changes are not written
(`midi_file_of_timeline`); the notes are not moved. Tempo (bpm) changes are kept. The same
writer is used by `gptab.py` (Guitar Pro), so the rule holds for both.
"""
TRUMPET_PROGRAM = 56
import io
import struct

QUARTER = 960                       # TuxGuitar's TGDuration.QUARTER_TIME
TS_SHOWN, TS_COMMON, TS_CUT = 0x100000, 0x400000, 0x800000   # Power Tab TimeSignature flags
PTB_VERSION = 4


class PTBError(ValueError):
    pass


# ---------------------------------------------------------------- data
class Bar:
    def __init__(self):
        self.repeat_start = False
        self.repeat_close = 0
        self.numerator = 0
        self.denominator = 0
        self.shown = False                  # time signature shown here (a real one)


class Beat:
    def __init__(self, staff, voice):
        self.staff, self.voice = staff, voice
        self.notes = []                     # Note
        self.duration = 4                   # 1 whole, 2 half, 4 quarter…
        self.dotted = self.double_dotted = False
        self.enters, self.times = 1, 1      # tuplet: `enters` notes in the time of `times`
        self.grace = False
        self.multibar_rest = 1


class Note:
    def __init__(self, string, fret, tied, dead):
        self.string, self.fret, self.tied, self.dead = string, fret, tied, dead


class GuitarIn:
    def __init__(self, staff, info):
        self.staff, self.info = staff, info


class Tempo:
    def __init__(self, bpm, triplet_feel=0):
        self.bpm, self.triplet_feel = bpm, triplet_feel


class Symbol:                               # alternate ending
    def __init__(self, end_number):
        self.end_number = end_number


class Direction:
    CODA, DOUBLE_CODA, SEGNO, SEGNO_SEGNO, FINE, DA_CAPO, DAL_SEGNO, DAL_SEGNO_SEGNO, \
        TO_CODA, TO_DOUBLE_CODA, DC_AL_CODA, DC_AL_DOUBLE_CODA, DS_AL_CODA, \
        DS_AL_DOUBLE_CODA, DSS_AL_CODA, DSS_AL_DOUBLE_CODA, DC_AL_FINE, DS_AL_FINE, \
        DSS_AL_FINE = range(19)
    ACTIVE_DC, ACTIVE_DS, ACTIVE_DSS = 1, 2, 3

    def __init__(self, direction, active_symbol, repeat):
        self.direction, self.active_symbol, self.repeat = direction, active_symbol, repeat


class Position:
    def __init__(self, position):
        self.position = position
        self.components = []

    def sort(self):
        """Directions after the other components (stable)."""
        self.components.sort(key=lambda c: isinstance(c, Direction))


class Section:
    def __init__(self, number):
        self.number = number
        self.staffs = 0
        self.positions = []

    def position(self, n):
        for p in self.positions:
            if p.position == n:
                return p
        p = Position(n)
        self.positions.append(p)
        return p

    def next_position_number(self):
        return max([p.position + 1 for p in self.positions] + [0])

    def sort(self):
        self.positions.sort(key=lambda p: p.position)


class TrackInfo:                           # a guitar of the score
    def __init__(self):
        self.number = 0
        self.name = ""
        self.program = 24
        self.volume = 104
        self.balance = 64
        self.capo = 0
        self.strings = []                   # MIDI note of every string, string 1 first


class Score:                               # the guitar score or the bass score
    def __init__(self):
        self.sections = []
        self.infos = []

    def section(self, index):
        while len(self.sections) <= index:
            self.sections.append(Section(len(self.sections)))
        return self.sections[index]

    def info(self, mask):
        for i in self.infos:
            if (1 << i.number) & mask:
                return i
        return None

    def default_info(self):
        return min(self.infos, key=lambda i: i.number) if self.infos else None


class PTSong:
    def __init__(self):
        self.info = {}
        self.scores = [Score(), Score()]   # guitar score, bass score


# ---------------------------------------------------------------- reader
class _Reader:
    def __init__(self, data):
        self.d = data
        self.i = 0

    def byte(self):
        if self.i >= len(self.d):
            raise PTBError("unexpected end of file")
        v = self.d[self.i]
        self.i += 1
        return v

    def bytes(self, n):
        if self.i + n > len(self.d):
            raise PTBError("unexpected end of file")
        v = self.d[self.i:self.i + n]
        self.i += n
        return v

    def short(self):
        return struct.unpack("<H", self.bytes(2))[0]

    def int(self):
        return struct.unpack("<I", self.bytes(4))[0]

    def boolean(self):
        return self.byte() > 0

    def string(self, length=None):
        if length is None:
            length = self.byte()
            if length == 0xff:
                length = self.short()
        return self.bytes(length).decode("cp1252", "replace")

    def header_items(self):
        """Count of an MFC object array (+ the class header of its first object)."""
        n = self.short()
        if n != 0:
            header = self.short()
            if header == 0xffff:
                if self.short() != 1:
                    raise PTBError("unknown object schema")
                self.string(self.short())
        return n


def read(path):
    """PTSong of a Power Tab file (PTBError if it is not a Power Tab 1.7 file)."""
    with open(path, "rb") as f:
        data = f.read()
    return read_bytes(data)


def read_bytes(data):
    r = _Reader(data)
    if r.bytes(4) != b"ptab" or r.short() != PTB_VERSION:
        raise PTBError("not a Power Tab Editor 1.7 file (ptab version 4)")
    song = PTSong()
    _song_info(r, song.info)
    for score in song.scores:
        _score(r, score)
    return song


def _song_info(r, info):
    info["classification"] = c = r.byte()
    if c == 0:
        r.bytes(1)
        info["title"] = r.string()
        info["artist"] = r.string()
        info["release_type"] = rt = r.byte()
        if rt == 0:
            r.byte()
            info["album"] = r.string()
            info["year"] = r.short()
            r.boolean()
        elif rt == 1:
            info["album"] = r.string()
            r.boolean()
        elif rt == 2:
            info["album"] = r.string()
            r.short(), r.short()
            info["year"] = r.short()
        if r.byte() == 0:
            info["author"] = r.string()
            info["lyricist"] = r.string()
        info["arranger"] = r.string()
        info["guitar_transcriber"] = r.string()
        info["bass_transcriber"] = r.string()
        info["copyright"] = r.string()
        info["lyrics"] = r.string()
        info["guitar_notes"] = r.string()
        info["bass_notes"] = r.string()
    elif c == 1:
        info["title"] = r.string()
        info["album"] = r.string()
        r.short()
        r.byte()
        info["author"] = r.string()
        info["notes"] = r.string()
        info["copyright"] = r.string()


def _score(r, score):
    n = r.header_items()                                      # guitars
    for j in range(n):
        _track_info(r, score)
        if j < n - 1:
            r.short()
    _skip_items(r, _chord)                                    # chord diagrams
    _skip_items(r, _floating_text)                            # floating texts
    n = r.header_items()                                      # guitar in
    for j in range(n):
        sec, staff, pos = r.short(), r.byte(), r.byte()
        r.bytes(1)
        info = r.byte()
        score.section(sec).position(pos).components.append(GuitarIn(staff, info))
        if j < n - 1:
            r.short()
    n = r.header_items()                                      # tempo markers
    for j in range(n):
        sec, pos, bpm, data = r.short(), r.byte(), r.short(), r.short()
        r.string()
        feel = 1 if data & 0x01 else (2 if data & 0x02 else 0)
        if bpm > 0:
            score.section(sec).position(pos).components.append(Tempo(bpm, feel))
        if j < n - 1:
            r.short()
    _skip_items(r, lambda rr: (rr.short(), rr.byte(), rr.byte(), rr.short()))   # dynamics
    n = r.header_items()                                      # section symbols (endings)
    for j in range(n):
        sec, pos, data = r.short(), r.byte(), r.int()
        score.section(sec).position(pos).components.append(Symbol(data >> 16))
        if j < n - 1:
            r.short()
    n = r.header_items()                                      # sections (systems)
    for j in range(n):
        _section(r, score.section(j))
        if j < n - 1:
            r.short()


def _skip_items(r, fn):
    n = r.header_items()
    for j in range(n):
        fn(r)
        if j < n - 1:
            r.short()


def _track_info(r, score):
    t = TrackInfo()
    t.number = r.byte()
    t.name = r.string()
    t.program = r.byte()
    t.volume = r.byte()
    t.balance = r.byte()
    r.byte(), r.byte(), r.byte(), r.byte()                     # reverb, chorus, tremolo, phaser
    t.capo = r.byte()
    r.string()                                                 # tuning name
    r.byte()                                                   # notation offset, sharps/flats
    t.strings = [r.byte() for _ in range(r.byte())]
    score.infos.append(t)


def _chord(r):
    r.short(), r.byte(), r.short(), r.byte(), r.byte()
    r.bytes(r.byte())


def _font(r):
    r.string(), r.int(), r.int(), r.boolean(), r.boolean(), r.boolean(), r.int()


def _floating_text(r):
    r.string()
    r.bytes(16)
    r.byte()
    _font(r)


def _bar_line(r, section):
    b = Bar()
    pos, typ = r.byte(), r.byte()
    b.repeat_start = (typ >> 5) == 3
    b.repeat_close = (typ - 128) if (typ >> 5) == 4 else 0
    r.byte()                                                   # key signature
    data = r.int()
    r.byte()                                                   # pulses
    top = (data >> 24) & 0xff
    b.numerator = (top >> 3) + 1
    b.denominator = 2 ** (top & 7)
    if data & TS_COMMON:
        b.numerator, b.denominator = 4, 4
    elif data & TS_CUT:
        b.numerator, b.denominator = 2, 2
    b.shown = bool(data & (TS_SHOWN | TS_COMMON | TS_CUT))
    r.byte()                                                   # rehearsal sign
    r.string()
    section.position(pos).components.append(b)


def _section(r, section):
    r.bytes(16)                                                # rectangle
    last = r.byte()
    r.bytes(4)
    _bar_line(r, section)
    n = r.header_items()                                      # directions
    for j in range(n):
        pos, count = r.byte(), r.byte()
        for _ in range(count):
            d = r.short()
            section.position(pos).components.append(
                Direction(d >> 8, (d & 0xc0) >> 6, d & 0x1f))
        if j < n - 1:
            r.short()
    _skip_items(r, lambda rr: (rr.byte(), rr.short(), rr.byte(), rr.short(), rr.byte()))
    _skip_items(r, lambda rr: (rr.byte(), rr.byte(), rr.int()))            # rhythm slashes
    section.staffs = r.header_items()                         # staves
    for st in range(section.staffs):
        r.bytes(5)
        for voice in (0, 1):
            n = r.header_items()
            for j in range(n):
                _position(r, section, st, voice)
                if j < n - 1:
                    r.short()
        if st < section.staffs - 1:
            r.short()
    n = r.header_items()                                      # bar lines inside the system
    for j in range(n):
        _bar_line(r, section)
        if j < n - 1:
            r.short()
    b = Bar()                                                  # the closing bar line
    b.repeat_close = (last - 128) if (last >> 5) == 4 else 0
    section.position(section.next_position_number()).components.append(b)


def _position(r, section, staff, voice):
    beat = Beat(staff, voice)
    pos = r.byte()
    beaming = r.byte()
    if beaming >= 128:
        beaming -= 128
    r.byte()
    data1 = r.byte()
    r.byte()
    data3 = r.byte()
    beat.duration = r.byte()
    multibar = 1
    for _ in range(r.byte()):                                  # complex symbols
        count = r.short()
        r.byte()
        if r.byte() & 0x08:
            multibar = count
    n = r.header_items()
    for j in range(n):
        p = r.byte()
        simple = r.short()
        r.bytes(4 * r.byte())                                  # note symbols (bends, slides)
        beat.notes.append(Note(((p & 0xe0) >> 5) + 1, p & 0x1f, bool(simple & 0x01),
                               bool(simple & 0x02)))
        if j < n - 1:
            r.short()
    beat.multibar_rest = multibar if n == 0 else 1
    beat.grace = bool(data3 & 0x01)
    beat.dotted = bool(data1 & 0x01)
    beat.double_dotted = bool(data1 & 0x02)
    beat.enters = (beaming - beaming % 8) // 8 + 1
    beat.times = beaming % 8 + 1
    section.position(pos).components.append(beat)


# ---------------------------------------------------------------- repeats and directions
class _Index:
    def __init__(self, s, p, c):
        self.s, self.p, self.c = s, p, c


class _Repeat:
    def __init__(self):
        self.start = None
        self.in_progress = False
        self.number = 0
        self.alternative = False
        self.skip = False
        self.find_active = 0


def expand(score):
    """A new Score with the components in PLAYING order: repeats, alternate endings and
    directions (D.C., D.S., Coda, Fine…) expanded (TuxGuitar PTSongSynchronizerUtil)."""
    dst = Score()
    dst.infos = list(score.infos)
    used = []
    _apply(score, dst, _Index(0, 0, 0), _Repeat(), used)
    return dst


def _can_use(d, used):
    if any(u is d for u in used):
        return False
    used.append(d)
    return True


def _find(src, used, value, s_end, p_end):
    n_sec = s_end + 1 if s_end >= 0 else len(src.sections)
    for s in range(n_sec):
        sec = src.sections[s]
        n_pos = p_end + 1 if s == s_end else len(sec.positions)
        for p in range(min(n_pos, len(sec.positions))):
            for c in sec.positions[p].components:
                if isinstance(c, Direction) and c.direction == value and _can_use(c, used):
                    return _Index(s, p, 0)
    return None


def _apply(src, dst, idx, rd, used, depth=0):
    if depth > 200:                                    # a broken file must not loop forever
        return
    D = Direction
    for s in range(idx.s, len(src.sections)):
        ssec = src.sections[s]
        ssec.sort()
        dsec = Section(ssec.number)
        dsec.staffs = ssec.staffs
        dst.sections.append(dsec)
        for p in range(idx.p if s == idx.s else 0, len(ssec.positions)):
            spos = ssec.positions[p]
            spos.sort()
            dpos = Position(spos.position)
            dsec.positions.append(dpos)
            for c in range(idx.c if (s == idx.s and p == idx.p) else 0, len(spos.components)):
                comp = spos.components[c]
                if not rd.skip:
                    dpos.components.append(comp)
                if isinstance(comp, Bar):
                    if comp.repeat_close > 0 and rd.start is not None:
                        rd.number += 1
                        rd.in_progress = True
                        rd.alternative = False
                        rd.skip = False
                        if rd.number < comp.repeat_close:
                            _apply(src, dst, rd.start, rd, used, depth + 1)
                            return
                        rd.start = None
                        rd.number = 0
                    if comp.repeat_start:
                        rd.start = _Index(s, p, c)
                        if not rd.in_progress:
                            rd.number = 0
                        rd.in_progress = False
                elif isinstance(comp, Symbol):
                    rd.skip = False
                    if not rd.alternative and (comp.end_number & 1):
                        valid = (comp.end_number & (1 << rd.number)) != 0
                        if rd.number > 0 and not valid:
                            rd.skip = True
                        rd.alternative = True
                elif isinstance(comp, Direction):
                    valid_repeat = comp.repeat == 0 or (rd.start is not None and
                                                        rd.number + 1 == comp.repeat)
                    if comp.active_symbol != rd.find_active or not valid_repeat:
                        continue
                    rd.find_active = 0
                    d = comp.direction
                    jump, active = None, 0
                    if d == D.FINE:
                        if _can_use(comp, used):
                            return
                        continue
                    if d == D.DA_CAPO:
                        if _can_use(comp, used):
                            jump = _Index(0, 0, 0)
                    elif d in (D.DAL_SEGNO, D.DAL_SEGNO_SEGNO):
                        if _can_use(comp, used):
                            jump = _find(src, used, D.SEGNO if d == D.DAL_SEGNO else
                                         D.SEGNO_SEGNO, s, p)
                    elif d in (D.TO_CODA, D.TO_DOUBLE_CODA):
                        if _can_use(comp, used):
                            jump = _find(src, used, D.CODA if d == D.TO_CODA else
                                         D.DOUBLE_CODA, -1, -1)
                    elif d in (D.DC_AL_CODA, D.DC_AL_DOUBLE_CODA, D.DC_AL_FINE):
                        if _can_use(comp, used):
                            jump, active = _Index(0, 0, 0), D.ACTIVE_DC
                    elif d in (D.DS_AL_CODA, D.DS_AL_DOUBLE_CODA):
                        if _can_use(comp, used):
                            jump, active = _find(src, used, D.SEGNO, s, p), D.ACTIVE_DS
                    elif d in (D.DSS_AL_CODA, D.DSS_AL_DOUBLE_CODA):
                        if _can_use(comp, used):
                            jump, active = _find(src, used, D.SEGNO_SEGNO, s, p), D.ACTIVE_DSS
                    elif d == D.DS_AL_FINE:
                        jump, active = _find(src, used, D.SEGNO, s, p), D.ACTIVE_DS
                    elif d == D.DSS_AL_FINE:
                        jump, active = _find(src, used, D.SEGNO_SEGNO, s, p), D.ACTIVE_DSS
                    if jump is not None:
                        if active:
                            rd.find_active = active
                        _apply(src, dst, jump, rd, used, depth + 1)
                        return


# ---------------------------------------------------------------- timeline
def _fix(v):
    """TuxGuitar's TrackStartHelper.fixValue: rounds a time near the next eighth."""
    h = QUARTER // 2
    return v + (h - v % h) if (v % h) + 10 > h else v


class _Starts:
    def init(self, staffs):
        self.voices = [[0, 0] for _ in range(max(1, staffs))]
        self.empty, self.rest = True, False
        self.bar_start = self.bar_len = 0

    def init_voices(self, start):
        for v in self.voices:
            v[0] = v[1] = _fix(start)
        self.empty, self.rest = True, False

    def max_start(self):
        r = max([QUARTER] + [x for v in self.voices for x in v])
        if self.rest and self.empty:
            r = max(r, self.bar_start + self.bar_len)
        return _fix(r)


def _beat_ticks(b):
    t = QUARTER * 4 // max(1, b.duration)
    if b.dotted:
        t = t * 3 // 2
    elif b.double_dotted:
        t = t * 7 // 4
    return t * b.times // max(1, b.enters)


def timeline(song):
    """Notes and markers in ticks (QUARTER per quarter; the song starts at 0):
    dict(tracks=[dict(name, program, volume, notes=[[start, end, pitch, velocity]])],
         tempos=[(tick, bpm)], meters=[(tick, num, den)], title)."""
    tracks, tempos, meters = {}, [], []
    primary = None                       # the first score read gives tempo and metre
    for si, score in enumerate(song.scores):
        if not score.sections or not score.infos:
            continue
        if primary is None:
            primary = si
        sc = expand(score)
        default = sc.default_info()
        staff_tracks = []                                      # info of every staff
        st = _Starts()
        start = QUARTER
        last_by_string = {}
        bar_len = QUARTER * 4                    # current meter (4/4 until one is shown)

        def track_of(info):
            key = (si, info.number)
            if key not in tracks:
                tracks[key] = dict(name=info.name or f"Guitar {info.number + 1}",
                                   program=info.program, volume=info.volume, notes=[],
                                   info=info)
            return tracks[key]

        for sec in sc.sections:
            sec.sort()
            st.init(sec.staffs)
            st.init_voices(start)
            for pos in sec.positions:
                for comp in pos.components:
                    if isinstance(comp, Bar):
                        st.init_voices(st.max_start())
                        if comp.numerator > 0 and comp.denominator > 0:   # not the closing bar
                            st.bar_start = st.max_start()
                            if comp.shown:
                                bar_len = comp.numerator * QUARTER * 4 // comp.denominator
                                if si == primary and (not meters or meters[-1][1:] !=
                                                      (comp.numerator, comp.denominator)):
                                    meters.append((st.bar_start - QUARTER, comp.numerator,
                                                   comp.denominator))
                            st.bar_len = bar_len
                    elif isinstance(comp, GuitarIn):
                        info = sc.info(comp.info)
                        if info is not None:
                            del staff_tracks[comp.staff:]
                            while len(staff_tracks) < comp.staff:
                                staff_tracks.append(default)
                            staff_tracks.append(info)
                    elif isinstance(comp, Tempo):
                        if si == primary:
                            tempos.append((st.max_start() - QUARTER, comp.bpm))
                    elif isinstance(comp, Beat):
                        b = comp
                        if b.grace or b.staff >= len(st.voices):
                            continue
                        if b.multibar_rest > 1:
                            st.voices[b.staff][b.voice] = _fix(st.bar_start +
                                                               b.multibar_rest * st.bar_len)
                            continue
                        t0 = st.voices[b.staff][b.voice]
                        info = staff_tracks[b.staff] if b.staff < len(staff_tracks) and \
                            staff_tracks[b.staff] is not None else default
                        dur = _beat_ticks(b)
                        rest = not b.notes
                        st.empty = st.empty and rest
                        st.rest = True
                        if rest and t0 == st.bar_start and dur > st.bar_len > 0:
                            dur = st.bar_len
                        tr = track_of(info)
                        for n in b.notes:
                            if n.dead or n.string > len(info.strings) or n.fret < 0:
                                continue
                            pitch = info.strings[n.string - 1] + info.capo + n.fret
                            key = (si, info.number, b.staff, n.string)
                            prev = last_by_string.get(key)
                            if n.tied and prev is not None and prev[2] == pitch:
                                prev[1] = t0 + dur - QUARTER
                                continue
                            note = [t0 - QUARTER, t0 + dur - QUARTER, pitch, 96]
                            tr["notes"].append(note)
                            last_by_string[key] = note
                        st.voices[b.staff][b.voice] = _fix(t0 + dur)
            start = st.max_start()
    out = [t for t in tracks.values() if t["notes"]]
    return dict(tracks=out, tempos=tempos or [(0, 120)], meters=meters or [(0, 4, 4)],
                title=song.info.get("title", ""))


# ---------------------------------------------------------------- MIDI
def skyline(notes):
    """One voice from notes [start, end, pitch, velocity]: the highest note at every moment
    (see the module doc). Returns new notes, no overlaps."""
    top = {}
    for n in notes:
        if n[0] not in top or n[2] > top[n[0]][2]:
            top[n[0]] = list(n)
    out = []
    for t in sorted(top):
        n = top[t]
        if out and out[-1][1] > t:
            if out[-1][2] > n[2]:
                continue                    # a higher note is still sounding
            out[-1][1] = t                  # the new (higher or equal) note cuts it
        out.append(n)
    return [n for n in out if n[1] > n[0]]


def to_midi_file(path_or_song, monophonic=False, program=None):
    """mido.MidiFile (type 1) of a Power Tab file (path) or of a PTSong; monophonic=True:
    one track, the highest note at every moment (skyline); program: the GM program of
    every track (e.g. TRUMPET_PROGRAM), None = the guitars' own."""
    song = read(path_or_song) if isinstance(path_or_song, str) else path_or_song
    return midi_file_of_timeline(timeline(song), monophonic, program)


def midi_file_of_timeline(tl, monophonic=False, program=None):
    """mido.MidiFile (type 1) of a timeline (format of `timeline`): conductor track with the
    tempos and ONLY THE FIRST time signature (owner's rule), one track per guitar."""
    import mido
    if monophonic and tl["tracks"]:
        first = tl["tracks"][0]
        tl["tracks"] = [dict(first, notes=skyline([n for t in tl["tracks"]
                                                   for n in t["notes"]]))]
    mf = mido.MidiFile(type=1, ticks_per_beat=QUARTER)
    events = []
    for tick, bpm in tl["tempos"]:
        events.append((max(0, tick), 0, mido.MetaMessage("set_tempo",
                                                        tempo=mido.bpm2tempo(bpm))))
    for tick, num, den in tl["meters"][:1]:              # one time signature only
        events.append((max(0, tick), 0, mido.MetaMessage("time_signature", numerator=num,
                                                        denominator=den)))
    conductor = mido.MidiTrack()
    if tl["title"]:
        conductor.append(mido.MetaMessage("track_name", name=_latin1(tl["title"])))
    conductor.extend(_delta(events))
    mf.tracks.append(conductor)
    channels = [c for c in range(16) if c != 9]
    for k, tr in enumerate(tl["tracks"]):
        ch = channels[k % len(channels)]
        ev = []
        for s, e, p, v in tr["notes"]:
            if e <= s or not 0 <= p <= 127:
                continue
            ev.append((s, 1, mido.Message("note_on", channel=ch, note=p, velocity=v)))
            ev.append((e, 0, mido.Message("note_off", channel=ch, note=p, velocity=0)))
        t = mido.MidiTrack()
        t.append(mido.MetaMessage("track_name", name=_latin1(tr["name"])))
        prog = tr["program"] if program is None else int(program)
        t.append(mido.Message("program_change", channel=ch, program=prog & 127))
        t.append(mido.Message("control_change", channel=ch, control=7,
                              value=min(127, tr["volume"])))
        t.extend(_delta(ev))
        mf.tracks.append(t)
    return mf


def _latin1(s):
    return str(s).encode("latin-1", "replace").decode("latin-1")


def _delta(events):
    """[(tick, order, msg)] -> messages with delta times (note offs before note ons)."""
    import mido
    out, now = [], 0
    for tick, _, msg in sorted(events, key=lambda e: (e[0], e[1])):
        out.append(msg.copy(time=tick - now))
        now = tick
    out.append(mido.MetaMessage("end_of_track", time=0))
    return out


def convert(src, dst, monophonic=False, program=None):
    """Write the MIDI file of a Power Tab file; returns the number of tracks with notes."""
    mf = to_midi_file(src, monophonic, program)
    mf.save(dst)
    return len(mf.tracks) - 1


def to_midi(path, monophonic=False, program=None):
    """musikite Midi object of a Power Tab file."""
    import pretty_midi
    from .midi import Midi
    buf = io.BytesIO()
    to_midi_file(path, monophonic, program).save(file=buf)
    buf.seek(0)
    m = Midi()
    m.pm = pretty_midi.PrettyMIDI(buf)
    m.source = path
    return m
