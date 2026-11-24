"""
Practice > Free player: play the MIDI keyboard with the soundfont, with an
instrument chosen from the General MIDI list or "From keyboard" (the channel and
the program changes sent by the keyboard are used), and RECORD it.

Recording (logic in recorder.Recorder, no Qt): Rec starts a take with the instrument
chosen (one count-in bar, always heard, then the clicks; the CLICK BUTTON of the bar —
owner, 2026-11-17 — shows the beat of the bar in colour and switches the clicks off / on,
also during the take); Stop ends it.
Every take is a part with its own instrument: record the trumpet, change the
instrument, Rec again and the first take plays back while you add the second
(overdub). The metronome and the parts already recorded are played by FluidSynth's
own sequencer (sample-accurate, not a Python thread), the note times come from the
MIDI driver (python-rtmidi), and nothing is drawn while recording (drawing blocked
Python and spoiled the timing). At Stop the recording is shown as a PIANO ROLL
(pianorollview.PianoRollView, Ableton style) and the Quantize… dialog opens on the
new take (grid 1/4 … 1/32, triplets, mixed grids, strength, note ends; Cancel = keep
it as played). In the piano roll the takes are edited (hand, pencil, eraser, undo,
Quantize… again); the edits are what the next take plays back. Save makes it a
Midi object in Objects (Convert > MIDI → Score for the notation); Clear starts again.
Tempo and time signature are those of the first take.

The MIDI input (Settings > Audio: MIDI input) is open only while this tab is in
front, so that an exercise with the keyboard in another tab does not receive the
same notes; leaving the tab stops a recording and every sounding note. Logic in
midiin.KeyboardSynth (no Qt).

From code:  w = app.open_tool('free_player'); w.set_instrument(56); w.rec(); …; w.rec(); w.save()
"""
from . import registry

LIVE_CHANNEL = 15                 # synth channel of the keyboard (playback uses 1-14)
TIME_SIGNATURES = ("4/4", "3/4", "2/4", "6/8", "2/2")


def _widget_class():
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                                   QSpinBox, QCheckBox)
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    from .bar import action_bar, click_button
    from .. import midiin as mi
    from ..recorder import Recorder

    class FreePlayerWidget(QWidget):
        def __init__(self, app):
            super().__init__()
            self.app = app
            self.kb = None
            self._connecting = False          # connect_port() running (no re-entry)
            from ..diary import Activity
            self.activity = Activity()          # time really played (practice diary)
            self._ticks = 0
            self.rec_ = None
            self.status = QLabel("")
            mono = QFont("Menlo")
            mono.setStyleHint(QFont.Monospace)
            self.status.setFont(mono)
            self.click_btn = click_button(True, self._click_toggled)
            self.bar, self.bar_buttons = action_bar(
                [("Rec", self.rec, "start / stop recording a take with the instrument chosen "
                                   "(the takes already recorded play back)"),
                 ("Clear", self.clear, "forget the recording"),
                 ("Save", self.save, "the recording (as edited) becomes a Midi object in "
                                     "Objects"),
                 None,
                 ("All notes off", self.panic, "stop every sounding note (and the pedal)"),
                 ("Reconnect", self.reconnect, "open the MIDI input again (keyboard plugged "
                                               "in now, or another port in Settings > Audio)"),
                 None,
                 self.click_btn],
                right=self.status)
            self.rec_btn = self.bar_buttons["Rec"]
            lay = QVBoxLayout(self)
            row = QHBoxLayout()
            # INPUT and INSTRUMENT are two things (owner, 2026-11-17): where the notes come
            # from (a MIDI keyboard, the computer keyboard) and the sound they get
            self.input_box = QComboBox()
            self.input_box.setToolTip("where the notes come from: a MIDI keyboard or the "
                                      "computer keyboard (default: Settings > Audio > MIDI "
                                      "input)")
            self._fill_inputs()
            self.input_box.currentIndexChanged.connect(lambda *_: self._input_changed())
            row.addWidget(QLabel("Input:"))
            row.addWidget(self.input_box)
            row.addSpacing(16)
            self.instrument = QComboBox()
            self.instrument.addItem("From keyboard (channel and program sent by the keyboard)")
            self.instrument.addItems([f"{i + 1} – {n}" for i, n in enumerate(mi.GM_NAMES)])
            self.instrument.currentIndexChanged.connect(self._instrument_changed)
            self.bpm = QSpinBox()
            self.bpm.setRange(30, 240)
            self.bpm.setValue(90)
            self.ts = QComboBox()
            self.ts.addItems(TIME_SIGNATURES)
            self.instrument.setToolTip("the sound of the notes (General MIDI), or the "
                                       "keyboard's own channel and program changes")
            for wdg in (QLabel("Instrument:"), self.instrument):
                row.addWidget(wdg)
            row.addSpacing(16)
            for wdg in (QLabel("bpm:"), self.bpm, QLabel("Time:"), self.ts):
                row.addWidget(wdg)
            row.setStretch(1, 1)
            lay.addLayout(row)
            big = QFont()
            big.setPointSize(16)
            self.last = QLabel("Play the keyboard")
            self.last.setFont(big)
            self.last.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.last)
            self.roll_box = QVBoxLayout()
            lay.addLayout(self.roll_box, 1)
            self.rv = None
            self.info = QLabel("")
            self.info.setWordWrap(True)
            self.info.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.info)
            self.timer = QTimer(self)
            self.timer.setInterval(100)
            self.timer.timeout.connect(self._update)
            self.beat_timer = QTimer(self)           # the beat on the Click button (recording)
            self.beat_timer.setInterval(20)
            self.beat_timer.timeout.connect(self._beat)
            self._shown = -1
            self.bpm.valueChanged.connect(lambda *_: self._empty_roll())
            self.ts.currentIndexChanged.connect(lambda *_: self._empty_roll())
            self._show_roll()
            app.tabs.currentChanged.connect(self._tab_changed)
            QTimer.singleShot(0, self._tab_changed)

        # ------------------------------------------------------ input
        def _fill_inputs(self):
            """The MIDI inputs connected + Computer keyboard; the current choice kept, else
            the one of the settings."""
            from ..realtime import audio_config
            cur = self.input_box.currentText() or audio_config().get("midi_input") or ""
            names = mi.input_names()
            self.input_box.blockSignals(True)
            self.input_box.clear()
            self.input_box.addItems(names)
            i = self.input_box.findText(cur)
            if i < 0:
                real = [n for n in names if n != mi.COMPUTER_KEYBOARD]
                i = self.input_box.findText(real[0] if real else mi.COMPUTER_KEYBOARD)
            self.input_box.setCurrentIndex(max(0, i))
            self.input_box.blockSignals(False)

        def _input_changed(self):
            if self.app.tabs.currentWidget() is self or self.kb is not None:
                self.reconnect()

        # ------------------------------------------------------ instrument
        def program(self):
            i = self.instrument.currentIndex()
            return None if i <= 0 else i - 1

        def set_instrument(self, program=None):
            """GM program 0-127, None = from the keyboard."""
            self.instrument.setCurrentIndex(0 if program is None else int(program) + 1)
            return self

        def _instrument_changed(self, *_):
            if self.rv is not None:
                self.rv.new_program = self.program() or 0      # notes drawn with no take yet
            if self.kb is not None:
                self.kb.set_program(self.program())
            self.app.log(f"free player: instrument {self.instrument.currentText()}")

        # ------------------------------------------------------ port
        def _tab_changed(self, *_):
            if self.app.tabs.currentWidget() is self:
                self.connect_port()
            else:
                self.disconnect_port()

        def connect_port(self):
            """Open the keyboard ONCE. Starting FluidSynth / CoreAudio inside open() lets
            macOS run the event loop, so the Qt timer of the tab could call this again
            before self.kb was set: a second KeyboardSynth was opened and the first one
            dropped with its port open -> crash at Rec (see midiin module doc)."""
            if self.kb is not None or self._connecting:
                return self
            self._connecting = True
            kb = None
            try:
                name = mi.port_name(self.input_box.currentText() or None)
                if name is None:
                    raise RuntimeError("no MIDI keyboard connected: plug it in, then Reconnect")
                kb = mi.KeyboardSynth(program=self.program(), channel=LIVE_CHANNEL,
                                      listener=self._on_message)
                self.kb = kb
                kb.open(name)
                self.status.setText(f"{name}  ·  latency {self.kb.latency_ms} ms ")
                self.info.setStyleSheet("color: gray")
                self.info.setText("Rec: record a take with the instrument chosen; Rec again "
                                  "with another instrument adds a part (the first plays back).")
                if name == mi.COMPUTER_KEYBOARD:
                    self.info.setText("Computer keyboard: a w s e d f t g y h u j k o l p ò = "
                                      "C … E (an octave and a half), z / x octave, c / v "
                                      "velocity. Rec: record a take with the instrument chosen.")
                self.app.log(f"free player: '{name}' open, latency {self.kb.latency_ms} ms")
                self.timer.start()
            except Exception as e:
                if kb is not None:
                    kb.close()                        # never left open
                self.kb = None
                self.status.setText("not connected ")
                self.info.setStyleSheet("color: red")
                self.info.setText(str(e))
                self.app.log(f"free player: {e}")
            finally:
                self._connecting = False
            return self

        def disconnect_port(self):
            if self.rec_ is not None and self.rec_.recording:
                self._stop_take()
            self.timer.stop()
            self._flush_time()
            if self.kb is not None:
                self.kb.close()                   # all notes off
                self.kb = None
                self.status.setText("paused (tab not in front) ")
            return self

        def reconnect(self):
            self.disconnect_port()
            self._fill_inputs()                       # a keyboard plugged in meanwhile
            return self.connect_port()

        def panic(self):
            if self.kb is not None:
                self.kb.all_off()

        def _on_message(self, msg, t):
            """MIDI thread: notes into the take being recorded (perf_counter time)."""
            if msg.type in ("note_on", "note_off"):
                self.activity.hit(t)                    # study time: only while playing
            r = self.rec_
            if r is None or not r.recording:
                return
            if msg.type == "note_on" and msg.velocity > 0:
                r.note_on(msg.note, msg.velocity, t)
            elif msg.type in ("note_on", "note_off"):
                r.note_off(msg.note, t)

        def _flush_time(self):
            """Practice diary: twice the time really played (owner's rule)."""
            try:
                from ..diary import get, SOUND_FACTOR
                s = self.activity.take()
                if s > 0:
                    get(self.app.user).add_time("free_player", SOUND_FACTOR * s)
            except Exception as e:
                self.app.log(f"free player: diary: {type(e).__name__}: {e}")

        def _update(self):
            self._ticks += 1
            if self._ticks % 600 == 0:                     # every minute
                self._flush_time()
            if self.kb is not None and self.kb.count != self._shown:
                self._shown = self.kb.count
                self.last.setText(self.kb.last)
            r = self.rec_
            if r is not None and r.recording:
                q = r.now_q()
                if q < 0:
                    self.status.setText(f"● count-in {int(q / r.beat_q) + r.ts[0] + 1}   ")
                else:
                    self.status.setText(f"● REC  bar {int(q // r.bar_q) + 1:3d}  "
                                        f"beat {int((q % r.bar_q) // r.beat_q) + 1}   ")

        def _beat(self):
            """Beat of the bar (count-in included) on the Click button, from the recorder's
            clock (the time HEARD); only a button repaint, nothing else is drawn."""
            r = self.rec_
            if r is None or not r.recording:
                self.click_btn.show_beat(None)
                return
            q = r.now_q()
            if q < 0:
                n = int((q + r.bar_q) / r.beat_q + 1e-6) + 1
            else:
                n = int((q % r.bar_q) / r.beat_q + 1e-6) + 1
            self.click_btn.show_beat(max(1, min(r.ts[0], n)))

        def _click_toggled(self, on):
            """Click button: the clicks of the take off / on at once (the count-in is always
            heard)."""
            if self.rec_ is not None and self.rec_.recording and self.kb is not None \
                    and self.kb.player is not None:
                self.kb.player.set_clicks_muted(not on)
            self.app.log(f"free player: click {'on' if on else 'off'}")

        # ------------------------------------------------------ recording
        def rec(self):
            """Rec / Stop (the same button)."""
            if self.rec_ is not None and self.rec_.recording:
                return self._stop_take()
            if self.kb is None:
                self.connect_port()
            if self.kb is None:
                return None
            try:
                player = self.kb._player()
            except Exception as e:
                self._say(f"no sound: {e}")
                return None
            num, den = (int(x) for x in self.ts.currentText().split("/"))
            if self.rec_ is None or not self.rec_.parts:
                self.rec_ = Recorder(bpm=self.bpm.value(), ts=(num, den))
            r = self.rec_
            events, lead = r.take_events(live_channel=LIVE_CHANNEL)
            # clicks timed by FluidSynth, not Python; silenced by the Click button
            player.play_sequenced(events, mute_clicks=not self.click_btn.on)
            self.kb.set_program(self.program())          # play() reset the channels
            prog = self.program() if self.program() is not None else 0
            from ..realtime import audio_config
            offset = float(audio_config().get("record_offset_ms") or 0) / 1000.0
            # t = 0 of the music: when its first beat is HEARD (+ the measured offset)
            r.start(prog, t_zero=player.t0 + player.latency + lead + offset)
            for w in (self.bpm, self.ts):                  # tempo/metre of the first take
                w.setEnabled(False)
            self.rec_btn.setText("Stop")
            self.beat_timer.start()
            if self.rv is not None:
                self.rv.win.setEnabled(False)            # no editing while recording
            # nothing drawn while recording: it would block Python and delay the notes
            # (the piano roll is redrawn at Stop); a bar/beat counter instead
            self.app.log(f"free player: recording take {len(r.parts) + 1} "
                         f"({self.instrument.currentText()}), {r.bpm:g} bpm, "
                         f"{r.ts[0]}/{r.ts[1]}, click {'on' if self.click_btn.on else 'off'}, "
                         f"clicks by {player.info.get('scheduler', '?')}, "
                         f"note times from {getattr(self.kb, 'timing', '?')}")
            self._say("● recording… (Stop when finished)", error=False)
            return self

        def _stop_take(self):
            r = self.rec_
            part = r.stop()
            self.beat_timer.stop()
            self.click_btn.show_beat(None)
            if self.kb is not None and self.kb.player is not None:
                self.kb.player.stop()
                self.kb.set_program(self.program())
            self.rec_btn.setText("Rec")
            n = len(part["notes"]) if part else 0
            self.app.log(f"free player: take ended, {n} notes"
                         + ("" if part else " (nothing played: take dropped)"))
            self._say(f"{len(r.parts)} parts recorded — edit them in the piano roll, Rec adds "
                      "another, Save keeps it" if r.parts else "nothing recorded",
                      error=not r.parts)
            if not r.parts:
                for w in (self.bpm, self.ts):
                    w.setEnabled(True)
            self._show_roll()
            if part is not None and self.rv is not None:
                from PySide6.QtCore import QTimer as _T
                k = len(r.parts) - 1                       # the new take
                _T.singleShot(0, lambda: self.rv.quantize_dialog(track=k))
            return self

        def clear(self):
            if self.rec_ is not None and self.rec_.recording:
                self._stop_take()
            self.rec_ = None
            for w in (self.bpm, self.ts):
                w.setEnabled(True)
            self._show_roll()
            self._say("recording cleared", error=False)
            return self

        def save(self):
            """The recording (with the edits of the piano roll) becomes a Midi object;
            returns its name."""
            import datetime
            if self.rec_ is not None and self.rec_.recording:
                self._stop_take()
            if self.rec_ is None or not self.rec_.parts:
                self._say("nothing to save: record a take first")
                return None
            title = "Recording " + datetime.datetime.now().strftime("%Y-%m-%d %H.%M")
            try:
                midi = self.rec_.to_midi()
                midi.title = title
            except Exception as e:
                self._say(f"cannot make the MIDI: {type(e).__name__}: {e}")
                return None
            name = self.app.add_object(midi, title)
            self._say(f"saved as '{name}' (Objects)", error=False)
            return name

        def _show_roll(self):
            """Piano roll of the recording (empty bars before the first take)."""
            from PySide6.QtCore import Qt as _Qt
            from ..pianoroll import Roll
            from ..pianorollview import PianoRollView
            r = self.rec_
            num, den = (int(x) for x in self.ts.currentText().split("/"))
            roll = (Roll.from_parts(r.parts, r.bpm, r.ts, "Recording") if r is not None
                    else Roll([], self.bpm.value(), (num, den), "Recording"))
            try:
                if self.rv is None:
                    self.rv = PianoRollView(roll, title="Recording", on_change=self._edited)
                    self.rv.new_program = self.program() or 0
                    self.rv.win.setWindowFlags(_Qt.Widget)
                    self.rv.hide_toolbar()
                    self.roll_box.addWidget(self.rv.win)
                else:
                    self.rv.set_roll(roll)
                self.rv.win.setEnabled(True)
                if r is not None and r.parts:
                    self.rv.set_track(len(r.parts) - 1)
            except Exception as e:
                self.app.log(f"free player: piano roll: {type(e).__name__}: {e}")

        def _empty_roll(self):
            """Tempo / time signature changed before the first take: new empty grid."""
            if self.rec_ is None or not self.rec_.parts:
                self._show_roll()

        def _edited(self, roll):
            """Edits in the piano roll: they are the parts played back by the next take."""
            if self.rec_ is None:
                self.rec_ = Recorder(bpm=roll.bpm, ts=roll.ts)
            self.rec_.parts = roll.to_parts()
            if self.rec_.parts:
                for w in (self.bpm, self.ts):
                    w.setEnabled(False)

        def _say(self, text, error=True):
            self.info.setStyleSheet("color: red" if error else "")
            self.info.setText(text)
            self.app.log(f"free player: {text}")

        def busy(self):
            """Recording a take: a click in Objects does not show its Preview (owner,
            2026-11-20: the Preview tab would take the front and stop the recording)."""
            return self.rec_ is not None and bool(getattr(self.rec_, "recording", False))

        def closing(self):
            try:
                self.app.tabs.currentChanged.disconnect(self._tab_changed)
            except Exception:
                pass
            if self.rv is not None:
                self.rv.stop()
            self.disconnect_port()

    return FreePlayerWidget


registry.register(registry.Tool(
    name="free_player", label="Free player (MIDI keyboard)", category="Practice", kind="session",
    factory=lambda app: _widget_class()(app),
    help="Play the MIDI keyboard with the soundfont (a General MIDI instrument of your choice, "
         "or the one chosen on the keyboard) and record it: every take is a part with its "
         "instrument, shown as a piano roll to quantize and edit; Save makes it a Midi."))
