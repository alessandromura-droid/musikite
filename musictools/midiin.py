"""
MIDI keyboard input (mido + python-rtmidi; no Qt).

    names = input_names()                      # connected MIDI input ports
    k = KeyboardSynth(sf2, program=0)          # play the keyboard with the soundfont
    k.open()                                   # port of the settings (or the first one)
    ...
    k.close()                                  # all notes off, port closed

KeyboardSynth forwards every channel message to FluidSynth (realtime.Player):
notes with their velocity, sustain pedal and the other controllers, pitch bend,
aftertouch. program=None ("From keyboard"): the channel and the program changes
sent by the keyboard are kept (channel 10 = percussion); a GM program number: every
note is played on channel 1 with that instrument. `listener(msg, t)` (optional) is
called for every message with its perf_counter time (exercises time the notes,
the Settings test shows them). Used by Practice > Free player, by Settings >
Audio > Test MIDI and by the exercises with a MIDI keyboard (sound "thru").

PORTS ARE ALWAYS CLOSED EXPLICITLY (crash found 2026-11-06, `debug_midi.py` cases J/K):
python-rtmidi 1.5.8 never destroys its C++ RtMidiIn when the Python MidiIn object is
freed (`__dealloc__` tests `hasattr(self, "thisptr")`, always false for a C attribute),
so a MidiIn freed with its port open keeps receiving and calls a Python callback that
no longer exists: Segmentation fault in the CoreMIDI thread ("no Python frame") at the
next key. So: `_RtPort.close()` = cancel_callback + close_port + delete(); the callbacks
reach the KeyboardSynth through a weak reference (no reference cycle), and a
KeyboardSynth that is dropped closes its port at once (`__del__`).
"""
import time
import weakref

FROM_KEYBOARD = None
GM_NAMES = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet", "Celesta", "Glockenspiel",
    "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion",
    "Harmonica", "Tango Accordion", "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)",
    "Electric Guitar (jazz)", "Electric Guitar (clean)", "Electric Guitar (muted)",
    "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass",
    "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1",
    "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani", "String Ensemble 1",
    "String Ensemble 2", "Synth Strings 1", "Synth Strings 2", "Choir Aahs", "Voice Oohs",
    "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "Synth Brass 1", "Synth Brass 2", "Soprano Sax", "Alto Sax",
    "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet", "Piccolo",
    "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)",
    "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)", "FX 2 (soundtrack)",
    "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)",
    "FX 7 (echoes)", "FX 8 (sci-fi)", "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba",
    "Bagpipe", "Fiddle", "Shanai", "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise",
    "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause",
    "Gunshot")
from .theory import note_name       # noqa: E402  (names live in the theory engine)


def input_names():
    """Names of the connected MIDI input ports ([] if mido / python-rtmidi are missing)."""
    try:
        import mido
        return list(mido.get_input_names())
    except Exception:
        return []


def port_name(want=None):
    """The port of the settings if connected, else the first one; None if there is none.
    Raises RuntimeError if mido / python-rtmidi are not installed or do not work."""
    try:
        import mido
        names = mido.get_input_names()
    except ImportError as e:
        raise RuntimeError(f"MIDI keyboard not available: {e.name} missing "
                           "(pip install mido python-rtmidi)") from e
    except Exception as e:
        raise RuntimeError(f"MIDI keyboard not available: {type(e).__name__}: {e} "
                           "(pip install mido python-rtmidi)") from e
    if want is None:
        from .realtime import audio_config
        want = audio_config().get("midi_input")
    if not names:
        return None
    return want if want in names else names[0]


def describe(msg):
    """Short text of a message for the test display."""
    t = msg.type
    if t == "note_on" and msg.velocity > 0:
        return f"{note_name(msg.note)} on  vel {msg.velocity}  ch {msg.channel + 1}"
    if t in ("note_on", "note_off"):
        return f"{note_name(msg.note)} off  ch {msg.channel + 1}"
    if t == "control_change":
        what = {64: "sustain", 1: "modulation", 7: "volume", 11: "expression"}.get(msg.control,
                                                                                  f"cc {msg.control}")
        return f"{what} {msg.value}  ch {msg.channel + 1}"
    if t == "pitchwheel":
        return f"pitch bend {msg.pitch}  ch {msg.channel + 1}"
    if t == "program_change":
        return f"program {msg.program + 1} ({GM_NAMES[msg.program]})  ch {msg.channel + 1}"
    return t


class _RtPort:
    """A python-rtmidi input that closes like a mido port, completely: callback
    removed, port closed and the C++ RtMidiIn destroyed (see the module doc)."""

    def __init__(self, mi):
        self.mi = mi

    def close(self):
        mi, self.mi = self.mi, None
        if mi is None:
            return
        for step in (mi.cancel_callback, mi.close_port, mi.delete):
            try:
                step()
            except Exception:
                pass

    def __del__(self):
        self.close()


def _weak(method):
    """Callback calling a bound method through a weak reference to its object (so
    that the port does not keep the KeyboardSynth alive: no reference cycle)."""
    ref = weakref.WeakMethod(method)

    def cb(*args):
        m = ref()
        if m is not None:
            return m(*args)
    return cb


class KeyboardSynth:
    """A MIDI keyboard played through the soundfont (see the module doc)."""

    def __init__(self, sf2=None, program=FROM_KEYBOARD, sound=True, listener=None, channel=0):
        """channel: synth channel used with a fixed program (0; the Free player uses 15,
        so that a recording played back on the other channels does not mix with it)."""
        self.sf2 = sf2
        self.program = program
        self.channel = int(channel)
        self.sound = sound
        self.listener = listener
        self.port = None
        self.name = None
        self.player = None
        self.count = 0
        self.last = ""

    # ---------------------------------------------------------- synth
    def _player(self):
        if self.player is None and self.sound:
            from .realtime import get_player
            from .midi import Midi
            sf2 = self.sf2 or Midi._default_sf2
            if not sf2:
                raise RuntimeError("no soundfont: choose one in Settings > Soundfont")
            self.player = get_player(sf2)
            self.player.stop()
        return self.player

    def set_program(self, program):
        """GM program number (0-127) or None = from the keyboard. Notes still
        sounding are stopped."""
        self.program = program
        if self.player is not None:
            self.player._all_off()
            if program is not None:
                self._select(self.channel, program)
            else:
                for ch in range(16):                      # back to the GM default
                    if ch != 9:
                        self._select(ch, 0)

    def _select(self, ch, program):
        p = self.player
        p.fs.program_select(ch, p.sfid, 0, int(program))
        p._programs[ch] = int(program)

    @property
    def latency_ms(self):
        return None if self.player is None else self.player.info.get("latency_ms")

    # ---------------------------------------------------------- port
    def open(self, name=None):
        """Open the MIDI input (default: the port of the settings or the first one)."""
        import mido
        self.close()
        name = name or port_name()
        if name is None:
            raise RuntimeError("no MIDI keyboard connected")
        if self.sound:
            self._player()
            self.set_program(self.program)
        self._dev = None                     # device clock (sum of the rtmidi deltas)
        self._off = None                     # perf_counter - device clock (smallest seen)
        self.port = self._open_rtmidi(name)  # exact times from the MIDI driver
        if self.port is None:
            self.port = mido.open_input(name, callback=_weak(self.message))
            self.timing = "python"
        else:
            self.timing = "driver"
        self.name = name
        return self

    def _open_rtmidi(self, name):
        """Open the port with python-rtmidi directly: every message comes with the time
        the MIDI driver measured (delta from the previous one), so the time of a note
        does not depend on when Python manages to read it (a busy window, the garbage
        collector…). None if python-rtmidi cannot open it (then mido, Python time)."""
        try:
            import rtmidi
            mi = rtmidi.MidiIn()
        except Exception:
            return None
        port = _RtPort(mi)                     # from here on it is closed completely
        try:
            ports = mi.get_ports()
            if name not in ports:
                port.close()
                return None
            mi.ignore_types(sysex=True, timing=True, active_sense=True)
            mi.open_port(ports.index(name))
            mi.set_callback(_weak(self._raw))
            return port
        except Exception:
            port.close()
            return None

    def _raw(self, event, data=None):
        """rtmidi callback: (bytes, delta seconds) -> message at the perf_counter time
        it was RECEIVED by the driver (device clock aligned on its smallest delay)."""
        import mido
        data_bytes, delta = event
        now = time.perf_counter()
        self._dev = 0.0 if self._dev is None else self._dev + float(delta)
        off = now - self._dev
        if self._off is None or off < self._off:
            self._off = off
        t = min(now, self._dev + self._off)
        try:
            msg = mido.Message.from_bytes(list(data_bytes))
        except Exception:
            return
        self.message(msg, t)

    def message(self, msg, t=None):
        """Handle one message (called by the MIDI thread; also usable from code).
        t: perf_counter time of the message (default: now)."""
        t = time.perf_counter() if t is None else t
        self.count += 1
        try:
            self.last = describe(msg)
        except Exception:
            self.last = str(msg)
        if self.sound and self.player is not None and hasattr(msg, "channel"):
            fs = self.player.fs
            ch = self.channel if self.program is not None else msg.channel
            ty = msg.type
            if ty == "note_on" and msg.velocity > 0:
                fs.noteon(ch, msg.note, msg.velocity)
            elif ty in ("note_on", "note_off"):
                fs.noteoff(ch, msg.note)
            elif ty == "control_change":
                fs.cc(ch, msg.control, msg.value)
            elif ty == "pitchwheel":
                fs.pitch_bend(ch, msg.pitch)
            elif ty == "program_change" and self.program is None and ch != 9:
                self._select(ch, msg.program)
            elif ty == "aftertouch" and hasattr(fs, "channel_pressure"):
                fs.channel_pressure(ch, msg.value)
        if self.listener is not None:
            try:
                self.listener(msg, t)
            except Exception:
                pass

    def all_off(self):
        if self.player is not None:
            self.player._all_off()
            for ch in range(16):
                self.player.fs.cc(ch, 64, 0)              # sustain pedal up

    def close(self):
        if self.port is not None:
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None
        self.all_off()
        return self

    @property
    def is_open(self):
        return self.port is not None

    def __del__(self):
        """Dropped without close(): the port is closed now (never left to the garbage
        collector, see the module doc). The notes of the shared synth are not touched."""
        port = getattr(self, "port", None)
        if port is not None:
            try:
                port.close()
            except Exception:
                pass
