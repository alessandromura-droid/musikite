"""
NOTE DETECTION PER INSTRUMENT (owner, 2026-11-17: "a module for an instrument like the
piano; trumpet or trombone use the wind module, the others the piano module; in the future
one adapted to every instrument"). No Qt (Android).

A FAMILY = an algorithm, a PROFILE = the numbers of one instrument (a table row, as the
fingerings):

- 'sustained' (trumpet, trombone, saxophones, clarinet, flute, voice, bowed strings): the
  sound stays while the player blows / bows. The algorithms of before, UNCHANGED:
  `playcheck.validate` (grade) and `transcribe.audio_notes` (the blue staff).
- 'decaying' (piano, guitar, harp, mallets): a strong attack, then a sound that dies away.
  Frame by frame the pitch "trembles" while the sound decays and the octave above takes
  over (seen 2026-11-17: a piano C became two notes and then a high C). Here a note is BORN
  AT ITS ATTACK and its pitch is read just after the attack (`decaying_notes`):
    * attack = the spectrum grows a lot more than usual in THIS take (positive spectral
      flux of the log spectrum, normalised by the take's maximum, above its local median),
      with the energy rising and above a floor relative to the loudest frame: no absolute
      level, so the distance of the microphone, an acoustic or an electric piano do not
      matter (owner: never tuned on one instrument);
    * pitch = harmonic sum of the spectrum 30-230 ms after the attack (hammer / pluck noise
      skipped): the semitone whose first 8 harmonics are strongest (a tolerance growing
      with the harmonic number: the partials of a piano are slightly sharp), the octave
      below taken when it explains the spectrum almost as well and its fundamental is
      there; a jump to the octave while the note decays cannot happen: the pitch is read
      once, at the attack;
    * the note lasts until the next attack (or the end of the take): the decay is never
      split into two notes; striking the same key again = a new attack = a new note;
    * CHORD = WRONG (owner: "the exercises are always monophonic"): at the attack another
      strong peak (>= CHORD_LEVEL of the strongest) that is not a harmonic of the note,
      of the previous note still ringing, or of the metronome click marks the note
      `chord`: it is never right.
  The grade pairs the notes found with the written ones ONE TO ONE as the MIDI keyboard
  does (`transcribe.check_notes`: same pitch, onsets at most half a quarter apart).

`profile(instrument)` -> dict(family, range); an instrument not in PROFILES takes its family
(DECAYING_INSTRUMENTS or 'sustained') and the default range.
"""
import numpy as np

PROFILES = {
    # range: CONCERT MIDI searched (None = the sustained default of transcribe / phrase)
    "trumpet": dict(family="sustained", range=None),
    "trombone": dict(family="sustained", range=(38, 74)),        # D2-D5 (phrase.DETECT_RANGE)
    "piano": dict(family="decaying", range=(36, 96)),            # C2-C7
}
DECAYING_INSTRUMENTS = ("piano", "guitar", "harp", "vibraphone", "marimba", "xylophone",
                        "glockenspiel", "celesta", "harpsichord")
DECAYING_RANGE = (36, 96)

# -- decaying family: every threshold is RELATIVE to the take (see the module doc)
WIN, HOP = 2048, 512                 # analysis frames (43 / 11 ms at 48 kHz)
FLUX_MEDIAN_S = 0.4                  # window of the local median of the flux
FLUX_DELTA = 0.08                    # an attack: flux above the local median by this
                                     # (fraction of the take's largest flux)
RISE = 1.2                           # energy just after / just before an attack
FLOOR_DB = -35.0                     # attacks quieter than this (vs. the loudest frame): noise
MIN_GAP_S = 0.06                     # two attacks closer than this = one
ATTACK_SKIP_S = 0.03                 # hammer / pluck noise skipped
PITCH_WIN_S = 0.2                    # analysed after it (at most: up to the next attack)
N_HARM = 8                           # harmonics of the harmonic sum
OCTAVE_BELOW = 0.75                  # the octave below wins with this share of the sum…
FUND_MIN = 0.1                       # …if its fundamental is at least this (of the peak)
TONAL_MIN = 0.2                      # the strongest peak must be a harmonic (>= this)
CHORD_LEVEL = 0.3                    # unexplained peak this strong (of the strongest) = chord
CLICK_NEAR_S = 0.04                  # an attack this close to a click may be the click


def profile(instrument):
    """dict(family='sustained'|'decaying', range=(lo, hi) concert MIDI or None)."""
    p = PROFILES.get(instrument)
    if p is None:
        dec = instrument in DECAYING_INSTRUMENTS
        p = dict(family="decaying" if dec else "sustained", range=DECAYING_RANGE if dec else None)
    return dict(p)


def family(instrument):
    return profile(instrument)["family"]


def _hz(m):
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def _midi(f):
    return 69.0 + 12.0 * np.log2(np.asarray(f, dtype=float) / 440.0)


# ---------------------------------------------------------------- attacks
def _frames(y, fs):
    n = 1 + (len(y) - WIN) // HOP
    if n < 3:
        return None
    w = np.hanning(WIN)
    S = np.empty((n, WIN // 2 + 1))
    for t in range(n):                               # frame by frame: little memory
        S[t] = np.abs(np.fft.rfft(y[t * HOP:t * HOP + WIN] * w))
    return S


def onsets(y, fs):
    """Attack times (s) of a take and the frame energies (see the module doc)."""
    from scipy.ndimage import median_filter
    y = np.asarray(y, dtype=float).ravel()
    S = _frames(y, fs)
    if S is None:
        return [], None
    mx = S.max()
    if mx <= 0:
        return [], None
    L = np.log1p(1000.0 * S / mx)
    flux = np.concatenate([[0.0], np.maximum(0.0, np.diff(L, axis=0)).sum(axis=1)])
    fmax = flux.max()
    energy = (S ** 2).sum(axis=1)
    emax = energy.max()
    if fmax <= 0 or emax <= 0:
        return [], energy
    flux = flux / fmax
    k = max(3, int(FLUX_MEDIAN_S * fs / HOP) | 1)
    med = median_filter(flux, size=k, mode="nearest")
    n = len(flux)
    cand = []
    for t in range(1, n - 1):
        if flux[t] < med[t] + FLUX_DELTA:
            continue
        if flux[t] < flux[max(0, t - 3):t + 4].max():
            continue
        before, after = energy[max(0, t - 2)], energy[min(n - 1, t + 3)]
        if after < RISE * before:
            continue
        if 10.0 * np.log10(after / emax + 1e-20) < FLOOR_DB:
            continue
        cand.append(t)
    keep = []
    for t in cand:
        if keep and (t - keep[-1]) * HOP / fs < MIN_GAP_S:
            if flux[t] > flux[keep[-1]]:
                keep[-1] = t
            continue
        keep.append(t)
    return [(t * HOP + WIN / 2.0) / fs for t in keep], energy


# ---------------------------------------------------------------- pitch at the attack
def _spectrum(seg, fs):
    n = 1 << int(np.ceil(np.log2(max(len(seg), 256) * 4)))
    n = min(n, 1 << 16)
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n))
    return spec, np.fft.rfftfreq(n, 1.0 / fs)


def _band_max(spec, freqs, f, cents):
    a = np.searchsorted(freqs, f * 2.0 ** (-cents / 1200.0))
    b = np.searchsorted(freqs, f * 2.0 ** (cents / 1200.0))
    if a >= len(spec):
        return 0.0
    return float(spec[a:max(a + 1, b + 1)].max())


def _peaks(spec, freqs, level, fmin, fmax):
    from scipy.signal import find_peaks
    if spec.max() <= 0:
        return []
    idx = find_peaks(spec, height=level * spec.max())[0]
    return [float(freqs[i]) for i in idx if fmin <= freqs[i] <= fmax]


def _explained(fp, f0s, extra=()):
    for f0 in f0s:
        if f0 is None or f0 <= 0:
            continue
        k = max(1, int(round(fp / f0)))
        if k <= 16 and abs(1200.0 * np.log2(fp / (k * f0))) <= 50.0:
            return True
    for fe in extra:
        if fe > 0 and abs(1200.0 * np.log2(fp / fe)) <= 50.0:
            return True
    return False


def note_at(y, fs, t0, t1, lo, hi, prev_f0=None, click_peaks=()):
    """(concert MIDI, chord, other pitches) of the note attacked at t0 (s), or None if
    nothing tonal is there."""
    a = int((t0 + ATTACK_SKIP_S) * fs)
    b = min(int((t0 + ATTACK_SKIP_S + PITCH_WIN_S) * fs), int(t1 * fs), len(y))
    if b - a < 1024:
        b = min(a + 1024, len(y))
    seg = np.asarray(y[a:b], dtype=float)
    if len(seg) < 512:
        return None
    spec, freqs = _spectrum(seg, fs)
    top = spec.max()
    if top <= 0:
        return None
    cands = np.arange(int(lo), int(hi) + 1)
    S = np.zeros(len(cands))
    for i, m in enumerate(cands):
        f = float(_hz(m))
        S[i] = sum(_band_max(spec, freqs, k * f, 30.0 + 5.0 * k) / np.sqrt(k)
                   for k in range(1, N_HARM + 1) if k * f < fs / 2)
    if S.max() <= 0:
        return None
    i = int(np.argmax(S))
    j = i - 12
    if j >= 0 and S[j] >= OCTAVE_BELOW * S[i] and \
            _band_max(spec, freqs, float(_hz(cands[j])), 40.0) >= FUND_MIN * top:
        i = j
    m = int(cands[i])
    f0 = float(_hz(m))
    if max(_band_max(spec, freqs, k * f0, 30.0 + 5.0 * k) for k in range(1, N_HARM + 1)
           if k * f0 < fs / 2) < TONAL_MIN * top:
        return None                                   # the strongest peak is not this note
    others = []
    for fp in _peaks(spec, freqs, CHORD_LEVEL, float(_hz(lo)) * 0.97, fs / 2):
        if not _explained(fp, (f0, prev_f0), click_peaks):
            p = int(round(float(_midi(fp))))
            if lo <= p <= hi:
                others.append(p)
    return m, bool(others), sorted(set(others))


def click_peaks(click_ref, fs):
    """Frequencies of the strong peaks of one metronome click (its sound as rendered):
    they are not "another note" when the microphone hears the click with the note."""
    if click_ref is None or len(click_ref) < 512:
        return []
    spec, freqs = _spectrum(np.asarray(click_ref, dtype=float), fs)
    return _peaks(spec, freqs, CHORD_LEVEL, 30.0, fs / 2)


def decaying_notes(y, fs, concert_range=None, click_times=(), click_ref=None):
    """Notes of a take of a decaying instrument: [start_s, dur_s, concert_pitch, chord,
    others] (see the module doc)."""
    y = np.asarray(y, dtype=float).ravel()
    lo, hi = concert_range or DECAYING_RANGE
    ons, _ = onsets(y, fs)
    cp = click_peaks(click_ref, fs)
    ct = list(click_times or ())
    end = len(y) / fs
    notes, prev = [], None
    for k, t0 in enumerate(ons):
        t1 = ons[k + 1] if k + 1 < len(ons) else end
        r = note_at(y, fs, t0, t1, lo, hi, prev, cp)
        if r is None:
            continue
        m, chord, others = r
        near = any(abs(t0 - c) <= CLICK_NEAR_S for c in ct)
        if near and cp and _explained(float(_hz(m)), (), cp):
            continue                                  # the click itself, not a note
        notes.append([round(t0, 4), round(max(0.02, t1 - t0), 4), m, chord, others])
        prev = float(_hz(m))
    return notes


def decaying_validate(y, fs, events, bpm, trasp, lead_q, concert_range=None,
                      click_times=(), click_ref=None):
    """Grade of a take of a decaying instrument: the notes found paired one to one with the
    written ones (transcribe.check_notes); a note found as a chord never pairs.
    Returns (ok, nn, per-event list, notes [start_s, dur_s, concert, chord, others])."""
    from .transcribe import to_quarters, check_notes
    notes = decaying_notes(y, fs, concert_range, click_times, click_ref)
    single = [[s, d, p] for s, d, p, chord, _ in notes if not chord]
    played_q = to_quarters(single, bpm, 0.0, lead_q)
    ok, nn, per = check_notes(events, played_q, written_offset=trasp)
    return ok, nn, per, notes


def click_info(click, fs):
    """(click times s, one click's sound) from a metronome track (sample 0 = the first
    count-in click)."""
    c = np.asarray(click, dtype=float).ravel()
    if not len(c) or np.max(np.abs(c)) <= 0:
        return [], None
    on = np.abs(c) > 1e-3 * np.max(np.abs(c))
    starts = np.flatnonzero(on & ~np.concatenate([[False], on[:-1]]))
    times, last = [], -1.0
    for s in starts:
        t = s / fs
        if t - last > 0.05:                          # a new click (not a wiggle of the same)
            times.append(t)
        last = t
    s0 = int(times[0] * fs) if times else 0
    return times, c[s0:s0 + int(0.2 * fs)]
