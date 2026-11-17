"""
Real-time audio: FluidSynth (through pyfluidsynth) driven note by note from a
scheduling thread. Used by Midi.play() and StaffView.play(); no audio files,
no external player.

Timing: events are sent on time.perf_counter(); the sound leaves the speakers
`latency` seconds later (audio buffer: period_size * periods / sample_rate,
a few ms). `Player.sound_time(t)` gives the perf_counter instant at which an
event scheduled at t (s from the start) is heard: this is what the recording
code will use to align the trumpet with the clicks.

Metronome clicks are MIDI notes on the percussion channel (10, i.e. index 9):
Hi Wood Block (76) on the first beat of the bar, Low Wood Block (77) otherwise.
"""
import sys
import threading
import time

DRUM_CH = 9
CLICK_ACCENT, CLICK_BEAT = 76, 77
CLICK_DUR = 0.06

_players = {}                 # one running synth per soundfont

DRIVERS = ("coreaudio", "portaudio", "sdl3", "sdl2", "pulseaudio", "pipewire", "alsa", "jack")
BUFFER_FALLBACK = (256, 512, 1024)
DEFAULT_AUDIO = dict(driver="coreaudio" if sys.platform == "darwin" else None, device=None,
                     period_size=64, periods=2, sample_rate=44100, gain=0.5,
                     input_device=None,          # microphone (Read & play), None = default
                     midi_input=None,            # MIDI keyboard, None = first connected
                     midi_thru=True,             # exercises: keyboard notes also sound (soundfont)
                     record_offset_ms=0)         # extra output delay of the audio device (ms): recorded notes moved that much earlier


def audio_config():
    """Current audio settings (settings of the current user, key 'audio')."""
    from .progress import settings
    cfg = dict(DEFAULT_AUDIO)
    cfg.update({k: v for k, v in settings().get("audio", {}).items() if k in DEFAULT_AUDIO})
    return cfg


def set_audio_config(**changes):
    """Change and save audio settings; running players are restarted at next use.
    Keys: driver, device, period_size, periods, sample_rate, gain (None = default)."""
    from .progress import save_setting
    bad = set(changes) - set(DEFAULT_AUDIO)
    if bad:
        raise ValueError(f"unknown audio setting(s): {', '.join(sorted(bad))}; "
                         f"known: {', '.join(DEFAULT_AUDIO)}")
    cfg = audio_config()
    cfg.update(changes)
    save_setting("audio", cfg)
    close_players()
    return cfg


def close_players():
    for p in list(_players.values()):
        p.close()
    _players.clear()


def get_player(sf2, **kw):
    """Shared Player for a soundfont (loading a soundfont takes time), built
    with the current audio settings."""
    p = _players.get(sf2)
    if p is None:
        p = _players[sf2] = Player(sf2, **kw)
    return p


def output_devices():
    """Names of the audio output devices (via sounddevice/PortAudio); on macOS
    the Core Audio names, which are also FluidSynth's coreaudio device names."""
    try:
        import sounddevice as sd
    except Exception:
        return []
    try:
        apis = sd.query_hostapis()
        out = []
        for d in sd.query_devices():
            if d["max_output_channels"] > 0:
                api = apis[d["hostapi"]]["name"]
                if sys.platform != "darwin" or api == "Core Audio":
                    out.append(d["name"])
        return out
    except Exception:
        return []


def input_devices():
    """Names of the audio input devices (microphones), as output_devices()."""
    try:
        import sounddevice as sd
    except Exception:
        return []
    try:
        apis = sd.query_hostapis()
        out = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0:
                api = apis[d["hostapi"]]["name"]
                if sys.platform != "darwin" or api == "Core Audio":
                    out.append(d["name"])
        return out
    except Exception:
        return []


def test_input(device=None, seconds=2.0, fs=48000):
    """Record `seconds` from the microphone: dict(device, peak_db, rms_db, silent,
    samplerate). A silent result usually means no microphone permission (macOS:
    System Settings > Privacy & Security > Microphone, for the Terminal / Python
    that runs the app) or the wrong input device."""
    import numpy as np
    import sounddevice as sd
    y = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="float32", device=device)
    sd.wait()
    y = np.asarray(y, dtype=float).ravel()
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    rms = float(np.sqrt(np.mean(y ** 2))) if len(y) else 0.0
    db = (lambda v: round(20 * np.log10(v), 1) if v > 0 else -999.0)
    name = device or sd.query_devices(kind="input")["name"]
    return dict(device=name, peak_db=db(peak), rms_db=db(rms), silent=peak < 1e-4,
                samplerate=fs)


class InputMeter:
    """Live level of the microphone (no Qt): start(device), level() -> dBFS of the
    loudest sample since the previous call (-120 = silence), stop()."""

    def __init__(self, fs=48000):
        self.fs = fs
        self.stream = None
        self._peak = 0.0
        self.max_peak = 0.0
        self.device = None
        self.error = None

    def start(self, device=None):
        import sounddevice as sd
        self.stop()
        self._peak = self.max_peak = 0.0
        self.error = None

        def cb(indata, frames, t, status):
            import numpy as np
            p = float(np.max(np.abs(indata))) if frames else 0.0
            if p > self._peak:
                self._peak = p
            if p > self.max_peak:
                self.max_peak = p

        try:
            self.stream = sd.InputStream(samplerate=self.fs, channels=1, dtype="float32",
                                         device=device, callback=cb)
            self.stream.start()
            self.device = device or sd.query_devices(kind="input")["name"]
        except Exception as e:
            self.stream = None
            self.error = f"{type(e).__name__}: {e}"
        return self

    def level(self):
        import math
        p, self._peak = self._peak, 0.0
        return 20 * math.log10(p) if p > 1e-6 else -120.0

    def stop(self):
        if self.stream is not None:
            try:
                self.stream.abort()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        return self


def midi_events(pm, start=0.0, scale=1.0, offset=0.0):
    """Events (t, on, ch, key, vel, program) from a pretty_midi object.
    Notes starting before `start` seconds are skipped; times are
    (t - start) * scale + offset."""
    ev, ch_next = [], 0
    for ins in pm.instruments:
        if ins.is_drum:
            ch = DRUM_CH
        else:
            ch = ch_next
            ch_next += 1
            if ch_next == DRUM_CH:
                ch_next += 1
            ch %= 16
        for n in ins.notes:
            if n.start + 1e-6 < start:
                continue
            t0 = (n.start - start) * scale + offset
            t1 = (n.end - start) * scale + offset
            ev.append((t0, True, ch, n.pitch, n.velocity, ins.program))
            ev.append((t1, False, ch, n.pitch, 0, ins.program))
    return ev


def click_events(n_beats, spb, beats_per_bar, first_beat=0, offset=0.0, vel=110):
    """Metronome: n_beats clicks every spb seconds; beat index first_beat+k,
    accent when it is a multiple of beats_per_bar."""
    ev = []
    for k in range(n_beats):
        t = offset + k * spb
        b = first_beat + k
        key = CLICK_ACCENT if b % beats_per_bar == 0 else CLICK_BEAT
        ev.append((t, True, DRUM_CH, key, vel, 0))
        ev.append((t + CLICK_DUR, False, DRUM_CH, key, 0, 0))
    return ev


class Player:
    def __init__(self, sf2, driver=None, device=None, period_size=None, periods=None,
                 sample_rate=None, gain=None):
        """Settings not given are taken from audio_config(). driver=False: no
        audio output at all (tests). If the audio driver refuses the buffer, larger
        buffers are tried (256, 512, 1024 samples); `info` says what is active."""
        try:
            from .check import prepare_fluidsynth
            prepare_fluidsynth()
            import fluidsynth
        except ImportError as e:
            raise RuntimeError("pyfluidsynth missing: pip install pyfluidsynth "
                               "(and brew install fluid-synth)") from e
        cfg = audio_config()
        for k, v in dict(driver=driver, device=device, period_size=period_size, periods=periods,
                         sample_rate=sample_rate, gain=gain).items():
            if v is not None:
                cfg[k] = v
        self.sf2 = sf2
        self.config = cfg
        self.info = dict(cfg, ok=False, error=None, latency_ms=None)
        sizes = [int(cfg["period_size"])] + [b for b in BUFFER_FALLBACK if b > int(cfg["period_size"])]
        self.fs = None
        for size in sizes:
            fs = fluidsynth.Synth(gain=float(cfg["gain"]), samplerate=int(cfg["sample_rate"]),
                                  **{"audio.period-size": size, "audio.periods": int(cfg["periods"])})
            if cfg["driver"] is False:
                self.fs, self.info["period_size"] = fs, size
                self.info.update(ok=True, error="no audio output (driver=False)")
                break
            drv = cfg["driver"] or fs.get_setting("audio.driver")
            fs.setting("audio.driver", drv)
            if cfg["device"]:
                fs.setting(f"audio.{drv}.device", str(cfg["device"]))
            fs.audio_driver = fluidsynth.new_fluid_audio_driver(fs.settings, fs.synth)
            if fs.audio_driver:
                self.fs = fs
                dev = fs.get_setting(f"audio.{drv}.device")
                self.info.update(ok=True, driver=drv, device=dev, period_size=size,
                                 error=None if size == sizes[0] else
                                 f"buffer {sizes[0]} refused, using {size}")
                break
            fs.delete()
            self.info["error"] = (f"audio driver '{drv}' did not start with device "
                                  f"'{cfg['device'] or 'default'}' (buffers tried: "
                                  f"{', '.join(str(b) for b in sizes)})")
        if self.fs is None:
            raise RuntimeError(self.info["error"] + ". Check Audio settings (driver, device).")
        self.latency = self.info["period_size"] * int(cfg["periods"]) / float(cfg["sample_rate"])
        self.info["latency_ms"] = round(1000 * self.latency, 1)
        self.sfid = self.fs.sfload(sf2)
        if self.sfid == -1:
            raise RuntimeError(f"cannot load soundfont {sf2}")
        self.fs.program_select(DRUM_CH, self.sfid, 128, 0)
        self._programs = {}
        self._seq = None                   # FluidSynth sequencer of play_sequenced()
        self._thread = None
        self._stop = threading.Event()
        self.t0 = None                     # perf_counter of t = 0 of the current timeline
        self.duration = 0.0

    # ---------------------------------------------------------- control
    def play(self, events, wait=False, delay=0.05):
        """Play a list of events (t, on, ch, key, vel, program), t in seconds
        from now + delay. Non-blocking unless wait=True."""
        self.stop()
        events = sorted(events, key=lambda e: (e[0], e[1]))     # note-offs before note-ons
        for t, on, ch, key, vel, prog in events:
            if on and ch != DRUM_CH and self._programs.get(ch) != prog:
                self.fs.program_select(ch, self.sfid, 0, prog)
                self._programs[ch] = prog
        self.duration = events[-1][0] if events else 0.0
        self._stop.clear()
        self.t0 = time.perf_counter() + delay
        self._thread = threading.Thread(target=self._run, args=(events, self.t0), daemon=True)
        self._thread.start()
        if wait:
            self.wait()
        return self

    def play_sequenced(self, events, delay=0.15):
        """Like play(), but the events are handed at once to FluidSynth's own
        sequencer, which plays them in step with the audio it renders (no Python
        thread: nothing a busy program does can delay a click). Used for the
        metronome of the recordings. Falls back to play() if the sequencer is not
        available. t0 = perf_counter of t = 0 (heard latency seconds later)."""
        try:
            import fluidsynth
            self.stop()
            events = sorted(events, key=lambda e: (e[0], e[1]))
            for t, on, ch, key, vel, prog in events:
                if on and ch != DRUM_CH and self._programs.get(ch) != prog:
                    self.fs.program_select(ch, self.sfid, 0, prog)
                    self._programs[ch] = prog
            seq = fluidsynth.Sequencer(time_scale=1000, use_system_timer=False)
            dest = seq.register_fluidsynth(self.fs)
            tick0 = seq.get_tick()
            self.t0 = time.perf_counter() + delay
            base = tick0 + int(round(delay * 1000))
            for t, on, ch, key, vel, prog in events:
                tick = base + int(round(t * 1000))
                if on:
                    seq.note_on(tick, ch, key, vel, dest=dest)
                else:
                    seq.note_off(tick, ch, key, dest=dest)
            self._seq = seq
            self.duration = events[-1][0] if events else 0.0
            self.info["scheduler"] = "fluidsynth sequencer"
            return self
        except Exception as e:
            self.info["scheduler"] = f"python thread ({type(e).__name__}: {e})"
            return self.play(events, delay=delay)

    def _run(self, events, t0):
        fs = self.fs
        for t, on, ch, key, vel, _ in events:
            target = t0 + t
            while not self._stop.is_set():
                dt = target - time.perf_counter()
                if dt <= 0:
                    break
                time.sleep(dt - 0.002 if dt > 0.004 else 0.0002)
            if self._stop.is_set():
                break
            if on:
                fs.noteon(ch, key, vel)
            else:
                fs.noteoff(ch, key)
        self._all_off()

    def _all_off(self):
        for ch in range(16):
            self.fs.cc(ch, 123, 0)            # all notes off

    def stop(self):
        if self._seq is not None:                    # pending sequencer events are dropped
            try:
                self._seq.delete()
            except Exception:
                pass
            self._seq = None
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._all_off()
        return self

    def wait(self):
        while self.is_playing():
            time.sleep(0.05)
        return self

    def is_playing(self):
        if self._seq is not None:
            return time.perf_counter() < (self.t0 or 0) + self.duration
        return self._thread is not None and self._thread.is_alive()

    # ---------------------------------------------------------- timing
    def elapsed(self):
        """Seconds of the timeline that have been HEARD (send time minus output latency)."""
        if self.t0 is None:
            return 0.0
        return time.perf_counter() - self.t0 - self.latency

    def sound_time(self, t):
        """perf_counter instant at which timeline time t is heard."""
        return self.t0 + t + self.latency

    def close(self):
        self.stop()
        self.fs.delete()
        _players.pop(self.sf2, None)


def test(sf2=None, program=0):
    """Audio check: a note (C5, piano by default) and four metronome clicks.
    Returns the active settings (driver, device, buffer, latency, errors)."""
    from .midi import Midi
    sf2 = sf2 or Midi._default_sf2
    if sf2 is None:
        raise RuntimeError("no soundfont: use Midi().add_sf2(path) or the Audio settings")
    p = get_player(sf2)
    ev = [(0.0, True, 0, 72, 100, program), (0.8, False, 0, 72, 0, program)]
    ev += click_events(4, 0.4, 4, offset=1.0)
    p.play(ev, wait=True)
    return dict(p.info)
