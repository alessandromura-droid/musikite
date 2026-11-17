"""
What was played: notes transcribed from a microphone recording (port of MATLAB
mysmartmusic_obj audiodata.get_notes) or taken from a MIDI keyboard. No Qt.

audio_notes(y, fs, trasp): frames of 4096 samples every 2048, silence below
3% of the maximum power skipped, Welch spectrum (nfft 16384) limited to the
trumpet range (written MIDI 54..79), converted to written pitch and
interpolated on 40..90, values below max/4 set to 0, peaks >= max/4; the
fundamental is the first peak with a harmonic (k = 2..4) above 10% of the
maximum (HPS-like), else the lowest peak. As in the original, a note must be
stable for some consecutive frames. Unlike the original (which kept only the
list of distinct pitches) the TIME is kept: consecutive equal frames are merged
into notes [start_s, dur_s, written_pitch].
"""
import numpy as np

WIN, HOP, NFFT = 4096, 2048, 16384
SILENCE = 0.03                 # of the maximum power (MATLAB soglia_silenzio)
RANGE = (54, 79)               # written MIDI, trumpet
MIN_FRAMES = 3                 # MATLAB 4 (~170 ms at 48 kHz): 3 keeps fast eighths


def frame_pitches(y, fs, trasp=2, range_trasp=None, concert_range=None):
    """Written pitch (int) or None for every frame; frame k starts at k*HOP.
    range_trasp: transposition of the instrument really played (default trasp): the
    frequency range searched is that of the instrument (RANGE, written for it).
    concert_range: (lowest, highest) CONCERT MIDI searched instead (other instruments:
    phrase.DETECT_RANGE, e.g. the trombone)."""
    from scipy.signal import welch, find_peaks
    y = np.asarray(y, dtype=float).ravel()
    if len(y) < WIN:
        return []
    thr = SILENCE * float(np.max(y ** 2))
    X = np.arange(40.0, 90.0 + 1e-9, 0.01)
    rt = trasp if range_trasp is None else range_trasp
    lo, hi = (RANGE[0] - rt, RANGE[1] - rt) if concert_range is None else concert_range
    fmin = 440 * 2 ** ((lo - 69) / 12)                     # sounding frequency range
    fmax = 440 * 2 ** ((hi - 69) / 12)
    out = []
    for i in range(0, len(y) - WIN + 1, HOP):
        yc = y[i:i + WIN]
        if np.max(yc ** 2) < thr:
            out.append(None)
            continue
        r, e = welch(yc, fs=fs, window="hamming", nperseg=WIN, noverlap=WIN // 2, nfft=NFFT,
                     detrend=False)
        m = (r >= fmin) & (r <= fmax)
        r, e = r[m], e[m]
        if not len(r):
            out.append(None)
            continue
        V = trasp - 12 * (np.log(440) - np.log(r)) / np.log(2) + 69
        E = np.interp(X, V, e, left=0.0, right=0.0)
        mx = E.max()
        if mx <= 0:
            out.append(None)
            continue
        E[E < mx / 4] = 0
        c = find_peaks(E, prominence=(E.max() - E.min()) / 4)[0]
        c = [k for k in c if E[k] >= 0.25 * mx]
        if not c:
            out.append(None)
            continue
        note = None
        for k in c:
            cand = int(round(X[k]))
            for h in (2, 3, 4):
                mh = cand + 12 * np.log2(h)
                if X[0] <= mh <= X[-1] and np.interp(mh, X, E) > 0.1 * mx:
                    note = cand
                    break
            if note is not None:
                break
        out.append(note if note is not None else int(round(X[c[0]])))
    return out


def audio_notes(y, fs, trasp=2, min_frames=MIN_FRAMES, range_trasp=None, concert_range=None):
    """Notes [start_s, dur_s, written_pitch] played in a recording."""
    fr = frame_pitches(y, fs, trasp, range_trasp, concert_range)
    notes, k = [], 0
    while k < len(fr):
        p = fr[k]
        j = k
        while j < len(fr) and fr[j] == p:
            j += 1
        if p is not None and j - k >= min_frames:
            notes.append([k * HOP / fs, (j - k) * HOP / fs + (WIN - HOP) / fs, int(p)])
        k = j
    return notes


def to_quarters(notes_s, bpm, t0=0.0, lead_q=0.0):
    """[start_s, dur_s, p] -> [start_q, dur_q, p] relative to t0 minus the count-in."""
    k = bpm / 60.0
    return [[round((s - t0) * k - lead_q, 3), round(d * k, 3), p] for s, d, p in notes_s]


ONSET_TOLERANCE_Q = 0.5          # a played note may start this much (quarters) early / late


def check_notes(events, played, written_offset=0, tolerance_q=ONSET_TOLERANCE_Q):
    """Correctness of the expected notes from notes PLAYED on a keyboard
    ([start_q, dur_q, pitch]): expected and played notes are paired ONE TO ONE
    (standard note matching): a pair needs the SAME pitch and onsets at most
    `tolerance_q` quarters apart; the closest pairs are taken first and every played
    note counts once. An expected note is right only if it gets a pair (the pitch of
    the previous / next note no longer counts: playing the previous note again made the
    next one right). written_offset: added to the played pitch to compare with the
    written events (Bb trumpet: +2).
    Returns (ok, nn, [dict(ok, heard, window, matched)] or None for rests); heard =
    pitches sounding in the window of the note (for the report), matched = index of the
    played note paired with it (or None)."""
    played = [(float(s), float(d), int(p) + written_offset) for s, d, p in played]
    pairs = []
    for i, ev in enumerate(events):
        if ev["pitch"] is None:
            continue
        for j, (s, d, p) in enumerate(played):
            dt = abs(s - ev["start"])
            if p == ev["pitch"] and dt <= tolerance_q + 1e-9:
                pairs.append((dt, i, j))
    match, used = {}, set()
    for dt, i, j in sorted(pairs):
        if i not in match and j not in used:
            match[i] = j
            used.add(j)
    out, ok, nn = [], 0, 0
    for i, ev in enumerate(events):
        if ev["pitch"] is None:
            out.append(None)
            continue
        nn += 1
        a, b = ev["start"] - tolerance_q, ev["start"] + ev["dur"] + tolerance_q
        heard = sorted({p for s, d, p in played if s < b and s + d > a})
        good = i in match
        ok += good
        out.append(dict(ok=bool(good), heard=heard, window=(a, b), matched=match.get(i)))
    return ok, nn, out
