"""
Read & play (trumpet): the player reads a score excerpt and plays it, the
microphone records, and every note is checked. Close port of the MATLAB
mysmartmusic (mysmart.m, audiodata.m: metronome, latency2, validate):

  1. a metronome track (one count-in bar, then one click per beat, accent on
     the first beat of the bar) is played while the microphone records
     (48 kHz, mono) for the metronome length + 2 s, in ONE full-duplex
     sounddevice stream; the clicks are the woodblock of the soundfont (as the
     other metronomes of the app, rendered offline with FluidSynth into the
     track) or, without soundfont, a short damped "tock" (the MATLAB tic/toc of
     100 samples at ~7.6/15 kHz was too harsh). The stream clock tells when
     the first sample reaches the speaker: heard_time() drives the cursor;
  2. latency: the first count-in click is found in the recording (energy
     smoothed with a gaussian of half a beat, first local maximum, as latency2);
  3. every note is checked in its time window (start/duration at the chosen
     bpm, after the count-in bar): Welch spectrum, frequency -> written pitch
     (sound = written - trasp), interpolated on 40..90, values below max/10
     set to 0, peaks (peakfinder: selectivity (max-min)/4); the note is right
     only if a peak rounds to ITS pitch, the window moving up to 1/4 beat
     earlier / later (the original also accepted the pitch of the previous /
     next note: repeating the previous note made the next one right);
  4. rating on the fraction recognised: > 0.9 perfect, > 0.8 very good,
     > 0.7 good, > 0.6 fair, else try again.

No Qt here (portable). The microphone needs the clicks to be heard (no
headphones): if the first click is not found where expected, the delay
reported by the audio device is used.

    pc = PlayCheck(score, part=0, bars=(1, 8), bpm=90)
    pc.run()                       # blocking: count-in, record, evaluate
    pc.result['ok'], pc.result['rating'], pc.errors   # table rows of wrong notes
"""
import numpy as np

FS = 48000
TRASP = 2                       # Bb trumpet: sound = written - 2 semitones
X = np.arange(40.0, 90.0 + 1e-9, 0.01)          # accepted written range (MATLAB X=40:.01:90)
EXERCISE = "play_reading"
RATINGS = ((0.9, "perfect"), (0.8, "very good"), (0.7, "good"), (0.6, "fair"))


def rating(fraction):
    for th, name in RATINGS:
        if fraction > th:
            return name
    return "try again"


# ---------------------------------------------------------------- audio (MATLAB audiodata)
def metronome(fs, bpm, beats_bar, measures, beat_q=1.0):
    """audiodata.metronome: clicks of 100 samples, sin(k) on every beat and
    sin(2k) on the first beat of the bar. Duration measures*beats_bar beats."""
    spb = beat_q * 60.0 / bpm
    T = measures * beats_bar * spb
    y = np.zeros(int(round(T * fs)) + 1)
    nio = 100
    tic = np.sin(np.arange(2, 2 * nio + 1, 2))
    toc = np.sin(np.arange(1, nio + 1))
    n = len(y)
    for k in range(int(np.floor(T / spb + 1e-9)) + 1):
        i = int(round(k * spb * fs))
        seg = tic if k % beats_bar == 0 else toc
        m = min(nio, n - i)
        if m > 0:
            y[i:i + m] = seg[:m]
    return y


def latency2(y, fs, bpm):
    """audiodata.latency2: seconds from the start of the recording to the
    first click (first local maximum of the smoothed energy)."""
    from scipy.signal import fftconvolve
    y = np.asarray(y, dtype=float).copy()
    y[:int(0.1 * fs)] = 0
    nfil = int(round(60.0 / bpm * fs * 0.5))
    fil = np.exp(-np.arange(-nfil, nfil + 1) ** 2 / nfil ** 2)
    Y = fftconvolve(y ** 2, fil, mode="same")
    Y = fftconvolve(Y, np.ones(100), mode="same")
    dY = np.diff(Y)
    # numerical noise of the FFT where the signal is ~0: ignore maxima below 1e-8 of the max
    ok = (dY[:-1] > 0) & (dY[1:] < 0) & (Y[1:-1] > 1e-8 * Y.max())
    idx = np.flatnonzero(ok)
    if not len(idx):
        return None
    return (idx[0] + 1) / fs


def pwelch(y, fs):
    """MATLAB pwelch defaults: 8 segments with 50% overlap, Hamming window,
    nfft = max(256, next power of 2); one-sided."""
    from scipy.signal import welch
    n = len(y)
    L = max(8, int(np.floor(n / 4.5)))
    nfft = max(256, 1 << int(np.ceil(np.log2(L))))
    r, e = welch(y, fs=fs, window="hamming", nperseg=L, noverlap=L // 2, nfft=nfft,
                 return_onesided=True, detrend=False)
    return e, r


def peakfinder(E):
    """peakfinder with its default selectivity (max - min)/4."""
    from scipy.signal import find_peaks
    sel = (E.max() - E.min()) / 4.0
    if sel <= 0:
        return np.array([], dtype=int)
    return find_peaks(E, prominence=sel)[0]


def written_range(detect_range, trasp):
    """Written pitches searched by validate: the MATLAB range 40..90, widened to the
    instrument's detection range when that goes beyond it (2026-11-19: tubas below E2,
    piccolo above F#6); None = the default X."""
    if not detect_range:
        return None
    lo, hi = int(detect_range[0]) + int(trasp), int(detect_range[1]) + int(trasp)
    if lo >= 40 and hi <= 90:
        return None
    return (min(40, lo), max(90, hi))


def note_pitches(segment, fs, trasp=TRASP, x_range=None):
    """Written pitches (rounded) of the spectral peaks of a segment (validate); x_range =
    (lo, hi) written pitches searched (default X = 40..90)."""
    if len(segment) < 64:
        return []
    e, r = pwelch(segment, fs)
    e, r = e[:len(e) // 2], r[:len(r) // 2]           # as in the original: e(1:end/2)
    pos = r > 0
    V = trasp - 12.0 * (np.log(440.0) - np.log(r[pos])) / np.log(2.0) + 69
    x = X if x_range is None else np.arange(float(x_range[0]), float(x_range[1]) + 1e-9, 0.01)
    E = np.interp(x, V, e[pos], left=0.0, right=0.0)
    if E.max() <= 0:
        return []
    E[E < E.max() / 10] = 0
    return sorted(set(int(round(v)) for v in x[peakfinder(E)]))


SHIFT_Q = 0.25            # the window of a note may move this much (quarters) to find it


def validate(y, fs, events, bpm, trasp=TRASP, lead_q=4.0, shift_q=SHIFT_Q, x_range=None):
    """audiodata.validate. events: list of dict(start, dur [quarters], pitch
    [written MIDI or None for rests]); y starts at the first count-in click.
    A note is right only if ITS pitch is heard in its window (Welch spectrum peaks);
    the window may move up to shift_q quarters (at most half the note) earlier or later
    to allow for playing a little early / late. The pitch of the previous / next note no
    longer counts (MATLAB did: repeating the previous note made the next one right).
    Returns (ok, nn, per-event list of dict(ok, heard, window))."""
    y = np.asarray(y, dtype=float)
    spb = 60.0 / bpm
    out, ok, nn = [], 0, 0
    for i, ev in enumerate(events):
        if ev["pitch"] is None:
            out.append(None)
            continue
        nn += 1
        ti = (lead_q + ev["start"]) * spb
        to = ti + ev["dur"] * spb
        sh = min(shift_q * spb, 0.5 * (to - ti))
        good, heard, win = False, [], (ti, to)
        for k, d in enumerate((0.0, -sh, sh)):
            a, b = ti + d, to + d
            ni = max(0, int(round(a * fs)) - 1)
            nf = min(int(round(b * fs)), len(y))
            h = note_pitches(y[ni:nf], fs, trasp, x_range) if nf > ni else []
            if k == 0:
                heard, win = h, (a, b)
            if ev["pitch"] in h:
                good, heard, win = True, h, (a, b)
                break
        ok += good
        out.append(dict(ok=bool(good), heard=heard, window=(round(win[0], 3), round(win[1], 3))))
    return ok, nn, out


# ---------------------------------------------------------------- score excerpt
def excerpt(score, part=0, bars=None):
    """Score with one part and the bars (first, last) of `score` (Score or Midi),
    starting at offset 0; clef, key and time signature kept."""
    import copy
    from music21 import stream
    from .score import Score
    from .midi import Midi
    if isinstance(score, Midi):
        score = score.to_score()
    src = score.m21.parts[part]
    ms = list(src.getElementsByClass(stream.Measure))
    if bars is not None:
        a, b = bars
        sel = src.measures(a, b)
        ms = list(sel.getElementsByClass(stream.Measure))
    p = stream.Part()
    p.partName = src.partName
    off = 0.0
    for k, m in enumerate(ms):
        m = copy.deepcopy(m)
        if k == 0:
            for cls in ("Clef", "KeySignature", "TimeSignature", "Instrument"):
                if not m.recurse().getElementsByClass(cls):
                    ctx = ms[0].getContextByClass(cls)
                    if ctx is not None:
                        m.insert(0, copy.deepcopy(ctx))
        p.insert(off, m)
        off += m.barDuration.quarterLength
    s = stream.Score()
    s.insert(0, p)
    title = score.title or ""
    if bars is not None and " bars " not in title:
        title = f"{title} bars {bars[0]}-{bars[1]}".strip()
    s.insert(0, __import__("music21").metadata.Metadata(title=title))
    out = Score(s, title=title)
    return out


def events_of(score):
    """Rows of score.table(part=0) as events (start, dur, pitch, measure, name)."""
    t = score.table(part=0)
    ev = []
    for r in t.itertuples():
        p = None if r.pitch is None or str(r.pitch) == "<NA>" else int(r.pitch)
        ev.append(dict(start=float(r.start), dur=float(r.dur), pitch=p,
                       measure=None if r.measure is None else int(r.measure), name=str(r.name)))
    return ev


_CLICK_CACHE = {}


def click_sounds(fs, sf2=None):
    """(accent, beat) click samples (float arrays): the woodblock of the
    soundfont (GM drum keys of realtime.click_events) rendered offline with
    FluidSynth, or synthetic damped tones without soundfont."""
    key = (fs, sf2)
    if key in _CLICK_CACHE:
        return _CLICK_CACHE[key]
    out = None
    if sf2:
        try:
            from .check import prepare_fluidsynth
            from .realtime import CLICK_ACCENT, CLICK_BEAT, CLICK_DUR
            prepare_fluidsynth()
            import fluidsynth
            out = []
            for k in (CLICK_ACCENT, CLICK_BEAT):
                syn = fluidsynth.Synth(samplerate=float(fs))
                sfid = syn.sfload(sf2)
                syn.program_select(9, sfid, 128, 0)
                syn.noteon(9, k, 110)
                a = np.asarray(syn.get_samples(int(CLICK_DUR * fs)), dtype=float)
                syn.noteoff(9, k)
                b = np.asarray(syn.get_samples(int(0.25 * fs)), dtype=float)
                syn.delete()
                st = np.concatenate([a, b]).reshape(-1, 2).mean(axis=1)
                if not np.any(st):
                    raise RuntimeError("silent click")
                out.append(st)
            m = max(np.abs(x).max() for x in out)
            out = tuple(0.6 * x / m for x in out)
        except Exception:
            out = None
    if out is None:                                    # synthetic "tock"
        t = np.arange(int(0.04 * fs)) / fs
        env = np.minimum(1.0, t / 0.001) * np.exp(-t / 0.008)
        out = (0.6 * env * np.sin(2 * np.pi * 1500 * t), 0.45 * env * np.sin(2 * np.pi * 1000 * t))
    _CLICK_CACHE[key] = out
    return out


def click_track(fs, bpm, beats_bar, measures, beat_q=1.0, sf2=None):
    """Metronome track as audiodata.metronome (same click times: every beat,
    accent on the first of the bar) with pleasant click sounds."""
    spb = beat_q * 60.0 / bpm
    T = measures * beats_bar * spb
    acc, beat = click_sounds(fs, sf2)
    y = np.zeros(int(round(T * fs)) + max(len(acc), len(beat)))
    for k in range(int(np.floor(T / spb + 1e-9)) + 1):
        i = int(round(k * spb * fs))
        c = acc if k % beats_bar == 0 else beat
        y[i:i + len(c)] += c
    return y[:int(round(T * fs)) + 1 + int(0.25 * fs)]


HIGH_CLICK_HZ = 4000.0          # 'high' click: a pure tone, removed by a notch filter


def high_click_track(fs, bpm, beats_bar, measures, beat_q=1.0, hz=HIGH_CLICK_HZ):
    """Metronome of short PURE tones (narrow spectrum): a notch filter at `hz` removes
    it from the recording while a clap (broadband) stays (rhythm reading)."""
    spb = beat_q * 60.0 / bpm
    T = measures * beats_bar * spb
    n = int(0.03 * fs)
    t = np.arange(n) / fs
    tone = np.sin(2 * np.pi * hz * t) * np.hanning(n)
    acc, beat = 0.6 * tone, 0.4 * tone
    y = np.zeros(int(round(T * fs)) + n)
    for k in range(int(np.floor(T / spb + 1e-9)) + 1):
        i = int(round(k * spb * fs))
        c = acc if k % beats_bar == 0 else beat
        y[i:i + n] += c[:len(y) - i]
    return y[:int(round(T * fs)) + 1 + int(0.25 * fs)]


def _variable_click_track(score, fs, bpm, lead_beats, lead_beat_q, end_q, mode, sf2):
    """Metronome track for scores with mid-piece time signature changes (e.g. 4/4 -> 3/4):
    count-in in the initial time signature, then each measure's beats and downbeat accent."""
    spq = 60.0 / bpm
    lead_q = lead_beats * lead_beat_q
    clicks = [(k * lead_beat_q, k == 0) for k in range(lead_beats)]
    last_b, last_bq, q_end = lead_beats, lead_beat_q, 0.0
    for m in score.m21.parts[0].getElementsByClass("Measure"):
        mts = m.timeSignature or m.getContextByClass("TimeSignature")
        b_bar = mts.numerator if mts else last_b
        b_q = (4.0 / mts.denominator) if mts else last_bq
        m_off = float(m.offset)
        for k in range(b_bar):
            clicks.append((lead_q + m_off + k * b_q, k == 0))
        q_end = m_off + b_bar * b_q
        last_b, last_bq = b_bar, b_q
    while q_end < end_q - 1e-6:
        for k in range(last_b):
            clicks.append((lead_q + q_end + k * last_bq, k == 0))
        q_end += last_b * last_bq
    total_q = lead_q + max(end_q, q_end)
    if mode == "high":
        n = int(0.03 * fs)
        t = np.arange(n) / fs
        tone = np.sin(2 * np.pi * HIGH_CLICK_HZ * t) * np.hanning(n)
        acc, beat = 0.6 * tone, 0.4 * tone
    else:
        acc, beat = click_sounds(fs, sf2)
    y = np.zeros(int(round(total_q * spq * fs)) + max(len(acc), len(beat)))
    for q, is_acc in clicks:
        i = int(round(q * spq * fs))
        c = acc if is_acc else beat
        if i < len(y):
            y[i:i + len(c)] += c[:len(y) - i]
    return y[:int(round(total_q * spq * fs)) + 1 + int(0.25 * fs)]


class PlayCheck:
    """One read & play exercise on a score excerpt (portable logic)."""

    def __init__(self, score, part=0, bars=None, bpm=90, trasp=TRASP, fs=FS, user=None,
                 sf2=None, prelude=None, gap_s=0.6, click=True, click_mode=None,
                 click_gain=1.0, play_trasp=None, backing=None, detect_range=None,
                 instrument=None):
        """prelude: audio (float array at fs) played BEFORE the count-in (Listen &
        repeat: the phrase to repeat), followed by gap_s of silence.
        click=False: the clicks are SILENT at the start (the cursor still moves; the
        delay of the recording is then the device latency, there are no clicks to find);
        the click track is built anyway, so `set_click(True)` during the take makes it
        heard from then on (owner, 2026-11-17: the Click button of the tabs switches the
        audio click on / off at any time).
        click_mode: 'normal' (default), 'high' (pure tones, see high_click_track),
        'count_in' (only the count-in bar), 'none' (no click track at all: set_click
        cannot make one heard); click_gain: volume of the clicks (0..1). play_trasp: transposition of the instrument really played
        (Bb trumpet 2) when the part is written for another one (transposition
        exercises): the pitch detection keeps the range of the real instrument.
        backing: audio (float array at fs) MIXED into the click track, sample 0 = the
        first count-in click (Chord arpeggios: the chords, `chord_audio`).
        detect_range: (lowest, highest) CONCERT MIDI where the played notes are searched
        (instruments other than the trumpet: phrase.DETECT_RANGE; None = the trumpet's).
        instrument: the instrument played ('trumpet', 'piano'…): its profile in
        `detect` chooses how the notes are found in the recording (sustained: as before;
        decaying — the piano —: by attacks, see detect.py)."""
        self.score = excerpt(score, part, bars)
        self.part, self.bars = part, bars
        self.bpm, self.trasp, self.fs, self.user = float(bpm), trasp, fs, user
        ts = self.score.time_signature().split("/")
        self.beats_bar, self.beat_q = int(ts[0]), 4.0 / float(ts[1])
        self.lead_q = self.beats_bar * self.beat_q            # one count-in bar
        self.events = events_of(self.score)
        end_q = max(e["start"] + e["dur"] for e in self.events) if self.events else 0
        measures = 1 + int(np.ceil(end_q / self.lead_q - 1e-9))
        if sf2 is None:
            from .midi import Midi
            sf2 = Midi._default_sf2
        mode = click_mode or "normal"
        self.click_mode = mode
        ts_objs = list(self.score.m21.parts[0].recurse().getElementsByClass("TimeSignature"))
        if len({t.ratioString for t in ts_objs}) > 1 and mode in ("normal", "high"):
            self.click = _variable_click_track(self.score, fs, self.bpm, self.beats_bar,
                                               self.beat_q, end_q, mode, sf2)
        elif mode == "high":
            self.click = high_click_track(fs, self.bpm, self.beats_bar, measures, self.beat_q)
        else:
            self.click = click_track(fs, self.bpm, self.beats_bar, measures, self.beat_q, sf2)
        self.click = self.click * float(click_gain)
        self.click_audible = bool(click) and mode != "none"   # switched live by set_click
        self.click_on = self.click_audible     # heard at the first click (set by start)
        if mode == "none":
            self.click = np.zeros_like(self.click)
        elif mode == "count_in":                    # silence after the count-in bar
            self.click[int(round(self.lead_q * 60.0 / self.bpm * fs)) - int(0.01 * fs):] = 0.0
        # chords etc. on the same clock, in their OWN track: switching the clicks off
        # never silences them
        self.backing = None if backing is None else np.asarray(backing, dtype=float).ravel()
        self.play_trasp = trasp if play_trasp is None else play_trasp
        self.detect_range = None if detect_range is None else tuple(detect_range)
        from .detect import profile
        self.instrument = instrument
        self.profile = profile(instrument)
        self.taps = []                                        # key / pad taps (stream clock)
        self.prelude = None if prelude is None else np.asarray(prelude, dtype=np.float32)
        self.offset = 0 if self.prelude is None else len(self.prelude) + int(gap_s * fs)
        n_track = max(len(self.click), 0 if self.backing is None else len(self.backing))
        self.duration = (self.offset + n_track) / fs + 2.0   # recording length (s)
        self.midi_played = []                                 # notes from a MIDI keyboard
        self.midi_written = False      # True (Read & play): the keyboard plays the WRITTEN note
        self.recording = None
        self.result = None
        self._stream_latency = None
        self.stream = None
        self._t_dac0 = None

    # ---------------------------------------------------------- recording
    def start(self, input_device=None, output_device=None):
        """Start metronome + recording in one full-duplex stream (non-blocking)."""
        import threading
        import time as _time
        import sounddevice as sd
        # two tracks of the same length: the clicks (switched live by set_click) and
        # the rest (prelude, backing chords), always heard
        off = self.offset
        n_track = max(len(self.click), 0 if self.backing is None else len(self.backing))
        n = off + n_track + int(2.0 * self.fs)
        out_click = np.zeros(n, dtype=np.float32)
        out_click[off:off + len(self.click)] = self.click
        out = np.zeros(n, dtype=np.float32)
        if self.prelude is not None:
            out[:len(self.prelude)] = self.prelude
        if self.backing is not None:
            out[off:off + len(self.backing)] += self.backing
        self.click_on = self.click_audible          # the first click heard: alignment
        self.recording = np.zeros(n, dtype=np.float32)
        self._pos = 0
        self._t_dac0 = None
        self._perf0 = None
        self._done = threading.Event()

        def callback(indata, outdata, frames, tinfo, status):
            i = self._pos
            k = max(0, min(frames, n - i))
            if self._t_dac0 is None:
                self._t_dac0 = tinfo.outputBufferDacTime
                self._t_adc0 = tinfo.inputBufferAdcTime
                self._perf0 = _time.perf_counter()
            if self.click_audible:
                outdata[:k, 0] = out[i:i + k] + out_click[i:i + k]
            else:
                outdata[:k, 0] = out[i:i + k]
            outdata[k:] = 0
            self.recording[i:i + k] = indata[:k, 0]
            self._pos = i + k
            if self._pos >= n:
                raise sd.CallbackStop

        self.stream = sd.Stream(samplerate=self.fs, channels=1, dtype="float32",
                                device=(input_device, output_device), callback=callback,
                                finished_callback=self._done.set)
        self._out_latency = float(self.stream.latency[1])
        self._stream_latency = float(sum(self.stream.latency))
        self.stream.start()
        return self

    def set_click(self, on):
        """Clicks heard (True) or silent (False) from now on, also during the take (the
        Click button of the tabs). Alignment uses the clicks only if the first count-in
        click was heard (`click_on`, fixed at the start)."""
        self.click_audible = bool(on) and self.click_mode != "none"
        return self

    def heard_time(self):
        """Seconds of the metronome track already heard (stream clock: when the
        first sample reached the speaker; the prelude excluded); 0 before."""
        t = self.track_time()
        return 0.0 if t is None else max(0.0, t)

    def track_time(self):
        """Like heard_time but negative during the prelude (None before the start)."""
        if self.stream is None or self._t_dac0 is None:
            return None if self._t_dac0 is None else 0.0
        if self._t_dac0 > 0:
            t = self.stream.time - self._t_dac0
        else:
            import time as _time                        # host without timing info
            t = _time.perf_counter() - self._perf0 - self._out_latency
        return t - self.offset / self.fs

    # ---------------------------------------------------------- MIDI keyboard
    def midi_message(self, on, note):
        """A note on/off from a MIDI keyboard, timed on the stream clock."""
        t = self.track_time()
        if t is None:
            return
        if on:
            self._open = getattr(self, "_open", {})
            self._open[note] = t
        else:
            t0 = getattr(self, "_open", {}).pop(note, None)
            if t0 is not None:
                self.midi_played.append([t0, max(0.02, t - t0), int(note)])

    def tap(self):
        """A tap (key, pad, any MIDI key) at the time heard now (rhythm reading)."""
        t = self.track_time()
        if t is not None:
            self.taps.append(float(t))

    def _measured_latency(self):
        """Output-to-input delay of the stream (dac time - adc time of sample 0)."""
        if self._t_dac0 and getattr(self, "_t_adc0", 0):
            d = self._t_dac0 - self._t_adc0
            if 0 <= d < 1.0:
                return d
        return self._stream_latency

    def wait(self, timeout=None):
        """Wait for the end of the take (default: its duration + 5 s), then close the
        stream (aborted if it is still running)."""
        if self.stream is not None:
            finished = self._done.wait(timeout if timeout is not None else self.duration + 5.0)
            self._stream_latency = self._measured_latency()
            try:
                if not finished:
                    self.stream.abort()
                self.stream.close()
            finally:
                self.stream = None
        return self

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.abort()
                self.stream.close()
            finally:
                self.stream = None
        return self

    def run(self, **kw):
        """Blocking: count-in, record, evaluate. Returns the result dict."""
        self.start(**kw).wait()
        return self.evaluate()

    # ---------------------------------------------------------- evaluation
    def align(self, y):
        """Delay of the first click in the recording (latency2, with a fallback
        on the device latency when the clicks are not heard or switched off)."""
        if not getattr(self, "click_on", True):         # no clicks to find: device latency
            exp = self._stream_latency
            return (exp, "device latency (no clicks)") if exp is not None else (0.0, "none")
        d = latency2(y, self.fs, self.bpm)
        exp = self._stream_latency
        spb = self.beat_q * 60.0 / self.bpm
        source = "clicks"
        if d is None or (exp is not None and abs(d - exp) > 0.25 * spb):
            if exp is not None:
                d, source = exp, "device latency"
            elif d is None:
                d, source = 0.0, "none"
        return d, source

    def evaluate(self, y=None, source="microphone"):
        """source 'microphone': the recording (validate + transcription of what was
        played); 'midi': the notes played on a MIDI keyboard (midi_played)."""
        from .transcribe import audio_notes, to_quarters, check_notes
        if source == "midi":
            for n, t0 in list(getattr(self, "_open", {}).items()):   # keys still down
                self.midi_played.append([t0, max(0.02, (self.duration - self.offset / self.fs) - t0), n])
            self._open = {}
            played = [[s, d, p] for s, d, p in to_quarters(sorted(self.midi_played), self.bpm,
                                                           0.0, self.lead_q)]
            # Read & play: the key pressed is the note READ (written pitch); Listen & repeat:
            # the note heard (concert pitch). The report shows concert pitch.
            off = 0 if self.midi_written else self.trasp
            ok, nn, per = check_notes(self.events, played, written_offset=off)
            played = [[s, d, p + off - self.trasp] for s, d, p in played]
            delay, how = 0.0, "midi"
        else:
            y = np.asarray(self.recording if y is None else y, dtype=float).ravel()
            y = y[self.offset:]
            delay, how = self.align(y)
            y3 = y[max(0, int(round(self.fs * delay)) - 1):]
            if self.profile["family"] == "decaying":     # piano…: notes by their attacks
                from .detect import decaying_validate, click_info
                times, ref = click_info(self.click, self.fs) if self.click_mode != "none" \
                    else ([], None)
                ok, nn, per, found = decaying_validate(
                    y3, self.fs, self.events, self.bpm, self.trasp, self.lead_q,
                    self.profile["range"], times, ref)
                played = to_quarters([[s, d, p] for s, d, p, _, _ in found],
                                     self.bpm, 0.0, self.lead_q)
            else:                                        # wind instruments: as before
                ok, nn, per = validate(y3, self.fs, self.events, self.bpm, self.trasp,
                                       self.lead_q,
                                       x_range=written_range(self.detect_range, self.trasp))
                played = [[s, d, p - self.trasp] for s, d, p in
                          to_quarters(audio_notes(y3, self.fs, self.trasp,
                                                  range_trasp=self.play_trasp,
                                                  concert_range=self.detect_range),
                                      self.bpm, 0.0, self.lead_q)]
        source = how
        frac = ok / nn if nn else 0.0
        items = []
        for row, (ev, r) in enumerate(zip(self.events, per)):
            if r is None:
                continue
            items.append(dict(row=row, measure=ev["measure"], start=ev["start"],
                              expected=ev["name"], pitch=ev["pitch"], correct=r["ok"],
                              heard=" ".join(str(p) for p in r["heard"])))
        played = [[max(0.0, s), d, p] for s, d, p in played if s + d > 0]
        self.result = dict(ok=ok, nn=nn, fraction=frac, rating=rating(frac),
                           grade=round(10.0 * frac, 2), delay=round(float(delay), 4),
                           delay_source=source, items=items, played=played,
                           correct_rows={it["row"]: it["correct"] for it in items})
        return self.result

    @property
    def errors(self):
        """Rows of score.table() played wrong."""
        return [it["row"] for it in (self.result or {}).get("items", []) if not it["correct"]]

    def settings(self):
        return dict(part=self.part, bars=list(self.bars) if self.bars else None,
                    bpm=self.bpm, trasp=self.trasp, excerpt=self.musicxml())

    def musicxml(self):
        import os
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".musicxml")
        os.close(fd)
        try:
            self.score.m21.write("musicxml", fp=tmp)
            with open(tmp, encoding="utf-8") as f:
                return f.read()
        finally:
            os.remove(tmp)

    @classmethod
    def from_settings(cls, q, user=None):
        """Same excerpt again (ExerciseResult.repeat)."""
        from music21 import converter
        from .score import Score
        m = converter.parseData(q["excerpt"], format="musicxml")
        s = Score(m, title=(m.metadata.title if m.metadata else "") or "")
        return cls(s, 0, None, q["bpm"], q["trasp"], user=user)

    def result_data(self, started, seconds, complete=True):
        """Data of an ExerciseResult (kind 'play_reading')."""
        r = self.result
        return dict(kind=EXERCISE, user=self.user, start=started, session=None,
                    complete=complete, n_questions=r["nn"], answered=r["nn"], correct=r["ok"],
                    seconds=round(seconds, 1), points=float(r["ok"]), grade=r["grade"],
                    rating=r["rating"], scoring={}, quiz=self.settings(), questions=[],
                    items=r["items"])


# ---------------------------------------------------------------- exercise type
EXERCISE_REPEAT = "listen_repeat"


def phrase_audio(phrase, bpm, fs=FS, sf2=None, gain=0.5):
    """The phrase rendered with the soundfont (its instrument, concert pitch) at bpm:
    float array at fs, for the prelude of Listen & repeat."""
    from .phrase import Phrase
    from .midi import Midi
    ph = Phrase.from_dict(phrase) if isinstance(phrase, dict) else phrase
    sf2 = sf2 or Midi._default_sf2
    if not sf2:
        raise RuntimeError("no soundfont: Settings > Soundfont…")
    m = ph.copy(bpm=float(bpm)).to_midi()
    y = m.pm.fluidsynth(fs=fs, sf2_path=sf2)
    if y is None or not len(y):
        raise RuntimeError("the phrase could not be rendered")
    return (gain * y / max(1e-9, float(np.max(np.abs(y))))).astype(np.float32)


CHORD_ROOT_LO = 36            # backing chords: root in octave 2, chord tones in C3-B3
CHORD_VOICING_LO = 48


def chord_audio(chords, bpm, lead_q=4.0, fs=FS, sf2=None, gain=0.35, program=0):
    """Chord arpeggios: every chord [(theory.Chord at CONCERT pitch, start_q, dur_q)]
    played ONCE at its start, held to its end with the sustain pedal (piano with a strong
    sustain, owner); low register (root in octave 2, chord tones in C3-B3) to leave the
    range of the player free. Float array at fs, sample 0 = the first count-in click
    (start_q after the count-in of lead_q quarters). Without soundfont: decaying sines."""
    spq = 60.0 / float(bpm)
    end_s = max(st + du for _, st, du in chords) * spq + lead_q * spq + 0.5
    from .drills import chord_voicing
    voiced = [(chord_voicing(ch), (lead_q + st) * spq, (lead_q + st + du) * spq)
              for ch, st, du in chords]
    if sf2 is None:
        from .midi import Midi
        sf2 = Midi._default_sf2
    y = None
    if sf2:
        try:
            import pretty_midi
            pm = pretty_midi.PrettyMIDI(initial_tempo=float(bpm))
            ins = pretty_midi.Instrument(program)
            for ps, t0, t1 in voiced:
                ins.control_changes.append(pretty_midi.ControlChange(64, 127, t0))
                for p in ps:
                    ins.notes.append(pretty_midi.Note(80, int(p), t0, t1 - 0.02))
                ins.control_changes.append(pretty_midi.ControlChange(64, 0, t1 - 0.02))
            pm.instruments.append(ins)
            y = pm.fluidsynth(fs=fs, sf2_path=sf2)
        except Exception:
            y = None
    if y is None or not len(y):
        y = np.zeros(int(end_s * fs))
        for ps, t0, t1 in voiced:
            a, b = int(t0 * fs), min(len(y), int(t1 * fs))
            t = np.arange(b - a) / fs
            env = np.exp(-t / 1.5) * np.minimum(1.0, t / 0.005)
            for p in ps:
                y[a:b] += env * np.sin(2 * np.pi * 440.0 * 2 ** ((p - 69) / 12.0) * t)
    return (gain * y / max(1e-9, float(np.max(np.abs(y))))).astype(np.float32)


class PlayQuiz:
    """Read & play (mode 'reading') and Listen & repeat (mode 'repeat') as exercise
    types for exercise.Exercise: every question is a phrase (phrase.Phrase, see
    exercises_from_midi); the answer is one take: the microphone recording (source
    'microphone') or the notes of a MIDI keyboard (source 'midi'). In 'repeat' the
    phrase is first played (soundfont), then one count-in bar, then the player
    repeats it. Points = base × fraction of the notes recognised; 'correct' when
    more than 60% (at least 'fair'). Every answer carries a ScoreReport (expected
    notes green/red + what was played)."""
    kind = EXERCISE

    def __init__(self, phrases, user=None, bpm=90, trasp=TRASP, progress=None, seed=None,
                 mode="reading", source="microphone", click=True, positions=False):
        import random
        from .phrase import Phrase
        self.pool = [p.to_dict() if isinstance(p, Phrase) else dict(p) for p in phrases]
        if not self.pool:
            raise ValueError("no phrases: generate exercises from a MIDI first")
        self.user, self.bpm, self.trasp, self.progress = user, float(bpm), trasp, progress
        self.mode, self.source = mode, source
        self.click = bool(click)
        self.positions = bool(positions)        # valves / slide positions under the notes
        if mode == "repeat":
            self.kind = EXERCISE_REPEAT
        self.rng = random.Random(seed)
        self._left = []
        self.current = None
        self.check = None
    @property
    def pool_size(self):
        return len(self.pool)

    def new(self, play=False):
        """A phrase not used yet in this block (random order)."""
        if not self._left:
            self._left = list(range(len(self.pool)))
            self.rng.shuffle(self._left)
        return dict(self.pool[self._left.pop()])

    def ask(self, question):
        from .phrase import Phrase
        self.current = question
        from .phrase import DETECT_RANGE
        ph = Phrase.from_dict(question)
        score = ph.to_score(positions=self.positions and self.mode == "reading")
        prelude = phrase_audio(question, self.bpm) if self.mode == "repeat" else None
        # written = sound + transposition of the exercise (Bb 2, C 0)
        # transposition exercise: the part is written for another trumpet, played on the Bb
        self.check = PlayCheck(score, 0, None, self.bpm, ph.transposition, user=self.user,
                               prelude=prelude, click=self.click,   # set_click: live
                               play_trasp=TRASP if ph.read_as else None,
                               detect_range=DETECT_RANGE.get(ph.instrument),
                               instrument=ph.instrument)
        self.check.midi_written = self.mode == "reading" and not ph.read_as
        return question

    def response_delay(self, q):
        return 0.0

    def replay(self):
        """Another take of the same phrase (the GUI restarts the recording)."""
        return None

    def answer(self, recording):
        """recording: the samples of the take (or None = not played: 0)."""
        from .report import ScoreReport
        q = self.current
        if recording is None and self.source != "midi":
            r = dict(ok=0, nn=len([e for e in self.check.events if e["pitch"] is not None]),
                     fraction=0.0, rating=rating(0.0), items=[], delay=None, delay_source="none",
                     played=[], correct_rows={})
        else:
            r = self.check.evaluate(recording, source=self.source)
        self.current = None
        try:                                   # practice diary: one attempt per take
            from .diary import record_take
            record_take(self.kind, q.get("uid"), 10.0 * r["fraction"],
                        getattr(self.check, "duration", 0.0) or 0.0, q.get("title", ""),
                        user=self.user)
        except Exception:
            pass
        rep = ScoreReport(q, r["played"], r["correct_rows"], q.get("title", ""),
                          info=dict(user=self.user, rating=r["rating"],
                                    grade=round(10.0 * r["fraction"], 1), source=self.source))
        return dict(asked=q.get("title", ""), answered=f"{r['ok']}/{r['nn']}",
                    correct=r["fraction"] > RATINGS[-1][0], fraction=r["fraction"],
                    rating=r["rating"], errors=[k for k, v in r["correct_rows"].items() if not v],
                    full=q.get("title", ""), report=rep,
                    detail=dict(rating=r["rating"], fraction=round(r["fraction"], 3),
                                delay=r["delay"], delay_source=r["delay_source"],
                                notes=r["items"], report=rep.to_dict()))

    def points(self, cfg, r, seconds, replays, question):
        return cfg["base"] * r["fraction"]

    def max_points(self, cfg):
        return cfg["base"]

    def settings(self):
        return dict(bpm=self.bpm, trasp=self.trasp, mode=self.mode, source=self.source,
                    click=self.click)
