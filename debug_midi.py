"""
Debug of the crash "Free player: Rec, first key -> the app closes" (SIGSEGV in the
python-rtmidi callback). Isolation test OUTSIDE the app: every case adds one
ingredient of the recording; the first case that crashes names the culprit.

    python debug_midi.py info        versions, MIDI ports, soundfont, audio settings
    python debug_midi.py A           rtmidi callback only (no sound)
    python debug_midi.py B           A + keyboard sound (FluidSynth noteon from the callback)
    python debug_midi.py C           B + metronome by the FluidSynth sequencer (= Rec)
    python debug_midi.py D           C + the notes recorded by recorder.Recorder (= Rec, full)
    python debug_midi.py E           C but the keyboard read by mido (the pre-mt44 way)
    python debug_midi.py F           B + metronome by the Python thread (the pre-mt44 way)
    python debug_midi.py G           the app's own classes (KeyboardSynth + Recorder), no Qt
    python debug_midi.py H           G inside a Qt event loop, listener = method of a QWidget
    python debug_midi.py I           the real Free player widget in a small window, Rec pressed
                                     by code 2 s after the start (just play the keyboard)
    python debug_midi.py J           CONFIRMATION: a second python-rtmidi port left orphan
                                     (as the Free player does), then gc.collect(): play
                                     before and after; expected: crash at the first key
                                     after the collection (no sound, no clicks, no Qt)
    python debug_midi.py K           control: the same, but the orphan port is closed
                                     properly (cancel_callback, close_port, delete):
                                     expected: no crash

Each case lasts 20 s (or `python debug_midi.py C 40`): play the keyboard the whole time.
faulthandler is on: if Python crashes it prints where every thread was. Nothing is
written anywhere (no settings, no files). Run it from the project folder.
"""
import faulthandler
import sys
import threading
import time

faulthandler.enable(all_threads=True)


def say(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def info():
    import platform
    say("python", sys.version.replace("\n", " "), platform.machine())
    for mod in ("rtmidi", "mido", "fluidsynth", "sounddevice", "PySide6", "Cython"):
        try:
            m = __import__(mod)
            say(f"{mod:12s}", getattr(m, "__version__", "?"), getattr(m, "__file__", ""))
        except Exception as e:
            say(f"{mod:12s} not importable: {type(e).__name__}: {e}")
    try:
        from importlib.metadata import version
        say("python-rtmidi (metadata)", version("python-rtmidi"))
    except Exception as e:
        say("python-rtmidi metadata:", e)
    try:
        import rtmidi
        mi = rtmidi.MidiIn()
        say("rtmidi API", rtmidi.get_api_name(mi.get_current_api()), "ports", mi.get_ports())
        mi.delete()
    except Exception as e:
        say("rtmidi:", type(e).__name__, e)
    say("soundfont", soundfont())
    from musikite.realtime import audio_config
    say("audio", audio_config())


def soundfont():
    """The soundfont of the last user of the app (read only)."""
    import os
    from musikite import progress
    progress._current["user"] = progress.last_user()      # no write: only for reading
    sf2 = progress.settings().get("sf2")
    if not sf2 or not os.path.isfile(sf2):
        sys.exit("no soundfont in the app settings: choose one in Settings > Soundfont")
    return sf2


def port():
    import rtmidi
    names = rtmidi.MidiIn().get_ports()
    if not names:
        sys.exit("no MIDI keyboard connected")
    from musikite.midiin import port_name
    from musikite import progress
    progress._current["user"] = progress.last_user()
    return port_name()


def run(case, seconds):
    import rtmidi
    import mido
    case = case.upper()
    name = port()
    say(f"case {case}, port '{name}', {seconds} s: PLAY THE KEYBOARD NOW")
    stats = dict(n=0, last="")
    player = None
    if case in "BCDEF":
        from musikite.realtime import get_player
        player = get_player(soundfont())
        player.stop()
        say("synth", {k: player.info.get(k) for k in ("driver", "period_size", "latency_ms")})
        player.fs.program_select(15, player.sfid, 0, 0)
    rec = None
    if case == "D":
        from musikite.recorder import Recorder
        rec = Recorder(bpm=90, ts=(4, 4))

    def handle(msg, t):
        stats["n"] += 1
        stats["last"] = str(msg)
        if player is not None and msg.type in ("note_on", "note_off"):
            if msg.type == "note_on" and msg.velocity > 0:
                player.fs.noteon(15, msg.note, msg.velocity)
            else:
                player.fs.noteoff(15, msg.note)
        if rec is not None and rec.recording and msg.type in ("note_on", "note_off"):
            if msg.type == "note_on" and msg.velocity > 0:
                rec.note_on(msg.note, msg.velocity, t)
            else:
                rec.note_off(msg.note, t)

    # metronome
    if case in "CDE":
        from musikite.realtime import click_events
        ev = click_events(4 + int(seconds * 1.5) + 4, 60 / 90, 4)
        player.play_sequenced(ev)
        say("clicks by", player.info.get("scheduler"))
    elif case == "F":
        from musikite.realtime import click_events
        player.play(click_events(4 + int(seconds * 1.5) + 4, 60 / 90, 4))
        say("clicks by the Python thread")
    if rec is not None:
        rec.start(56, t_zero=player.t0 + player.latency + 4 * 60 / 90)

    # keyboard input
    keep = []
    if case == "E":
        port_ = mido.open_input(name, callback=lambda m: handle(m, time.perf_counter()))
        keep.append(port_)
        say("input: mido callback")
    else:
        mi = rtmidi.MidiIn()
        ports = mi.get_ports()
        mi.ignore_types(sysex=True, timing=True, active_sense=True)
        mi.open_port(ports.index(name))

        def cb(event, data=None):
            data_bytes, delta = event
            try:
                msg = mido.Message.from_bytes(list(data_bytes))
            except Exception:
                return
            handle(msg, time.perf_counter())

        mi.set_callback(cb)
        keep.append(mi)
        say("input: python-rtmidi callback")

    t_end = time.time() + seconds
    shown = 0
    while time.time() < t_end:
        time.sleep(0.5)
        if stats["n"] != shown:
            shown = stats["n"]
            say(f"{shown} messages, last: {stats['last']}"
                + (f", recorded {len(rec.current_notes())} notes" if rec else ""))
    say("closing")
    for k in keep:
        try:
            if hasattr(k, "cancel_callback"):
                k.cancel_callback()
                k.close_port()
            else:
                k.close()
        except Exception as e:
            say("close:", e)
    if player is not None:
        player.stop()
    say(f"case {case}: NO CRASH ({stats['n']} messages)")


def _setup_app_settings():
    """The app's soundfont and settings of the last user (read only)."""
    from musikite import progress
    from musikite.midi import Midi
    sf2 = soundfont()
    progress._current["user"] = progress.last_user()
    Midi._default_sf2 = sf2
    return sf2


def _app_classes(seconds, listener_owner=None):
    """KeyboardSynth + Recorder exactly as the Free player uses them (channel 15,
    clicks + take events by play_sequenced, t_zero as in freeplayer.rec)."""
    from musikite import midiin as mi
    from musikite.recorder import Recorder
    from musikite.realtime import audio_config
    sf2 = _setup_app_settings()
    rec = Recorder(bpm=90, ts=(4, 4))

    def on_message(msg, t):
        if not rec.recording:
            return
        if msg.type == "note_on" and msg.velocity > 0:
            rec.note_on(msg.note, msg.velocity, t)
        elif msg.type in ("note_on", "note_off"):
            rec.note_off(msg.note, t)

    listener = on_message if listener_owner is None else listener_owner.bind(rec)
    name = port()
    kb = mi.KeyboardSynth(sf2, program=56, channel=15, listener=listener).open(name)
    say(f"KeyboardSynth open on '{name}', timing {kb.timing}, latency {kb.latency_ms} ms")
    player = kb._player()
    events, lead = rec.take_events(click=True, live_channel=15)
    player.play_sequenced(events)
    kb.set_program(56)
    offset = float(audio_config().get("record_offset_ms") or 0) / 1000.0
    rec.start(56, t_zero=player.t0 + player.latency + lead + offset)
    say(f"recording: {len(events)} events, clicks by {player.info.get('scheduler')}: PLAY NOW")
    return kb, rec


def run_g(seconds):
    kb, rec = _app_classes(seconds)
    t_end = time.time() + seconds
    shown = -1
    while time.time() < t_end:
        time.sleep(0.5)
        if kb.count != shown:
            shown = kb.count
            say(f"{kb.count} messages, last: {kb.last}, recorded {len(rec.current_notes())} notes")
    rec.stop()
    kb.close()
    kb.player.stop()
    say(f"case G: NO CRASH ({kb.count} messages)")


def run_h(seconds):
    from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
    from PySide6.QtCore import QTimer
    app = QApplication.instance() or QApplication([])

    class Owner(QWidget):
        """The listener is a method of a QWidget, as in the Free player."""
        def __init__(self):
            super().__init__()
            self.rec_ = None
            self.label = QLabel("case H: play the keyboard")
            QVBoxLayout(self).addWidget(self.label)

        def bind(self, rec):
            self.rec_ = rec
            return self._on_message

        def _on_message(self, msg, t):
            r = self.rec_
            if r is None or not r.recording:
                return
            if msg.type == "note_on" and msg.velocity > 0:
                r.note_on(msg.note, msg.velocity, t)
            elif msg.type in ("note_on", "note_off"):
                r.note_off(msg.note, t)

    w = Owner()
    w.show()
    kb, rec = _app_classes(seconds, listener_owner=w)
    st = dict(shown=-1)

    def tick():
        if kb.count != st["shown"]:
            st["shown"] = kb.count
            txt = f"{kb.count} messages, last: {kb.last}, recorded {len(rec.current_notes())} notes"
            w.label.setText(txt)
            say(txt)

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(500)
    QTimer.singleShot(int(seconds * 1000), app.quit)
    app.exec()
    rec.stop()
    kb.close()
    kb.player.stop()
    say(f"case H: NO CRASH ({kb.count} messages)")


def run_i(seconds):
    import importlib
    from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget
    from PySide6.QtCore import QTimer
    _setup_app_settings()
    app = QApplication.instance() or QApplication([])
    fp = importlib.import_module("musikite.gui.freeplayer")

    class FakeApp:
        """What the Free player needs from the main window."""
        def __init__(self):
            self.tabs = QTabWidget()
            self.objects = {}

        def log(self, text):
            say("LOG", text)

        def add_object(self, obj, name):
            self.objects[name] = obj
            return name

    fake = FakeApp()
    win = QMainWindow()
    win.setCentralWidget(fake.tabs)
    win.resize(1000, 600)
    w = fp._widget_class()(fake)
    fake.tabs.addTab(w, "Free player")
    fake.tabs.setCurrentWidget(w)
    win.show()
    st = dict(shown=-1)

    def tick():
        kb = w.kb
        if kb is not None and kb.count != st["shown"]:
            st["shown"] = kb.count
            r = w.rec_
            say(f"{kb.count} messages, last: {kb.last}, timing {kb.timing}"
                + (f", recorded {len(r.current_notes())} notes" if r is not None else ""))

    def press_rec():
        say("pressing Rec (Free player.rec())")
        w.rec()
        say("Rec pressed: PLAY NOW")

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(500)
    QTimer.singleShot(2000, press_rec)
    QTimer.singleShot(int(seconds * 1000), app.quit)
    app.exec()
    say("closing (no Quantize dialog: the take is stopped after the loop)")
    w.closing()
    say("case I: NO CRASH")


def run_jk(case, seconds):
    """J / K: an orphan python-rtmidi input kept alive only by a reference cycle
    (object -> port -> callback -> bound method -> object), as an orphan KeyboardSynth;
    then the cyclic garbage collector frees it."""
    import gc
    import rtmidi
    name = port()

    class Holder:
        def __init__(self, label):
            self.label = label
            self.n = 0
            self.mi = rtmidi.MidiIn()
            ports = self.mi.get_ports()
            self.mi.ignore_types(sysex=True, timing=True, active_sense=True)
            self.mi.open_port(ports.index(name))
            self.mi.set_callback(self.cb)         # cycle: self -> mi -> callback -> self

        def cb(self, event, data=None):
            self.n += 1

    gc.disable()                                  # the collection happens only when asked
    main = Holder("main")
    orphan = Holder("orphan")
    say(f"case {case}: two inputs open on '{name}' (main + orphan): PLAY for {seconds:g} s")
    t_end = time.time() + seconds
    while time.time() < t_end:
        time.sleep(1.0)
        say(f"main {main.n} messages, orphan {orphan.n} messages")
    if case == "K":
        orphan.mi.cancel_callback()
        orphan.mi.close_port()
        orphan.mi.delete()
        say("orphan closed properly (cancel_callback, close_port, delete)")
    o = orphan
    del orphan
    say(f"references to the orphan dropped (refcount now {sys.getrefcount(o) - 1} + cycle)")
    del o
    found = gc.collect()
    say(f"gc.collect(): {found} objects freed. NOW PLAY: "
        + ("expected: crash at the first key" if case == "J" else "expected: no crash"))
    t_end = time.time() + seconds
    while time.time() < t_end:
        time.sleep(1.0)
        say(f"main {main.n} messages")
    main.mi.cancel_callback()
    main.mi.close_port()
    say(f"case {case}: NO CRASH")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "info"
    if what == "info":
        info()
    else:
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
        if what.upper() in ("J", "K"):
            run_jk(what.upper(), secs)
        else:
            {"G": run_g, "H": run_h, "I": run_i}.get(what.upper(), lambda s: run(what, s))(secs)
    _ = threading  # (imported for faulthandler's thread list on some Pythons)
