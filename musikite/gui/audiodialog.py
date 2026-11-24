"""Settings > Audio…: output driver, device, buffer, sample rate, gain, Test (note + clicks);
input device (microphone for Read & play) with a live level meter; MIDI input (keyboard)
with Test MIDI (the notes received are shown and sound with the soundfont) and the
"Keyboard sound" option (exercises with the keyboard: the keys also sound)."""
from .. import realtime
from ..audio import BUFFERS, RATES


def audio_dialog(app):
    """Settings window opened on the Audio page."""
    from .settingsdialog import settings_dialog
    return settings_dialog(app, page="Audio")


def audio_page(app):
    """The Audio page of the Settings window (a QWidget with save(), stop())."""
    from PySide6.QtWidgets import (QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
                                   QPushButton, QHBoxLayout, QLabel, QVBoxLayout, QProgressBar,
                                   QWidget, QCheckBox)
    from PySide6.QtCore import Qt, QTimer

    cfg = realtime.audio_config()
    d = QWidget()
    lay = QVBoxLayout(d)
    form = QFormLayout()
    driver = QComboBox()
    driver.addItems(["(default)"] + list(realtime.DRIVERS))
    driver.setCurrentText(cfg["driver"] or "(default)")
    device = QComboBox()
    device.setEditable(True)                   # a name not listed can be typed
    device.addItems(["(default)"] + realtime.output_devices())
    device.setCurrentText(cfg["device"] or "(default)")
    period = QComboBox()
    period.addItems([str(b) for b in BUFFERS])
    period.setCurrentText(str(cfg["period_size"]))
    periods = QSpinBox()
    periods.setRange(2, 16)
    periods.setValue(int(cfg["periods"]))
    rate = QComboBox()
    rate.addItems([str(r) for r in RATES])
    rate.setCurrentText(str(cfg["sample_rate"]))
    gain = QDoubleSpinBox()
    gain.setRange(0.05, 2.0)
    gain.setSingleStep(0.05)
    gain.setValue(float(cfg["gain"]))
    latency = QLabel()
    offset = QSpinBox()
    offset.setRange(-500, 500)
    offset.setSuffix(" ms")
    offset.setValue(int(cfg.get("record_offset_ms") or 0))
    offset.setToolTip("recordings from the keyboard (Free player): if the notes come out late "
                      "compared with the click, raise this value (extra delay of the audio "
                      "output beyond the buffer)")
    indev = QComboBox()
    indev.setEditable(True)
    indev.addItems(["(default)"] + realtime.input_devices())
    indev.setCurrentText(cfg.get("input_device") or "(default)")
    from .. import midiin as mi
    midiin = QComboBox()

    def fill_midi():
        cur = midiin.currentText() or cfg.get("midi_input") or "(first connected)"
        midiin.blockSignals(True)
        midiin.clear()
        midiin.addItems(["(first connected)"] + mi.input_names())
        midiin.setCurrentText(cur)
        midiin.blockSignals(False)
    fill_midi()
    midiin.setCurrentText(cfg.get("midi_input") or "(first connected)")
    thru = QCheckBox("the keys also sound with the soundfont during the exercises "
                     "(off: the keyboard has its own sound)")
    thru.setChecked(bool(cfg.get("midi_thru", True)))
    for label, w in (("Driver", driver), ("Output device", device), ("Buffer (samples)", period),
                     ("Periods", periods), ("Sample rate (Hz)", rate), ("Gain", gain),
                     ("Buffer latency", latency), ("Recording offset", offset),
                     ("Input device (microphone)", indev)):
        form.addRow(label, w)
    # live level of the microphone (as macOS Sound settings)
    meter_box = QWidget()
    mh = QHBoxLayout(meter_box)
    mh.setContentsMargins(0, 0, 0, 0)
    meter = QProgressBar()
    meter.setRange(0, 60)                      # -60 .. 0 dBFS
    meter.setTextVisible(False)
    meter.setFixedHeight(14)
    meter.setStyleSheet("QProgressBar {border: 1px solid #999; border-radius: 3px; background: #eee;}"
                        "QProgressBar::chunk {background: #43a047;}")
    meter_db = QLabel("")
    from PySide6.QtGui import QFont
    mono = QFont("Menlo")
    mono.setStyleHint(QFont.Monospace)
    meter_db.setFont(mono)
    meter_db.setMinimumWidth(110)
    mic_btn = QPushButton("Test microphone")
    mic_btn.setCheckable(True)
    mic_btn.setToolTip("start / stop the level meter of the input device")
    mh.addWidget(mic_btn)
    mh.addWidget(meter, 1)
    mh.addWidget(meter_db)
    form.addRow("Input level", meter_box)
    mic_hint = QLabel("")
    mic_hint.setWordWrap(True)
    form.addRow("", mic_hint)
    # MIDI keyboard: port, test (notes shown and played), sound in the exercises
    midi_row = QWidget()
    mr = QHBoxLayout(midi_row)
    mr.setContentsMargins(0, 0, 0, 0)
    midi_btn = QPushButton("Test MIDI")
    midi_btn.setCheckable(True)
    midi_btn.setToolTip("open the MIDI input: play the keyboard, the notes are shown and sound")
    mr.addWidget(midiin, 1)
    mr.addWidget(midi_btn)
    form.addRow("MIDI input (keyboard)", midi_row)
    midi_show = QLabel("")
    midi_show.setFont(mono)
    midi_show.setWordWrap(True)
    form.addRow("", midi_show)
    form.addRow("Keyboard sound", thru)
    lay.addLayout(form)
    status = QLabel("")
    status.setWordWrap(True)
    status.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay.addWidget(status)

    def values():
        return dict(driver=None if driver.currentText() == "(default)" else driver.currentText(),
                    device=None if device.currentText() in ("", "(default)") else device.currentText(),
                    period_size=int(period.currentText()), periods=periods.value(),
                    sample_rate=int(rate.currentText()), gain=gain.value(),
                    input_device=None if indev.currentText() in ("", "(default)")
                    else indev.currentText(),
                    midi_input=None if midiin.currentText() in ("", "(first connected)")
                    else midiin.currentText(),
                    midi_thru=thru.isChecked(),
                    record_offset_ms=offset.value())

    def show_latency(*_):
        v = values()
        latency.setText(f"{1000.0 * v['period_size'] * v['periods'] / v['sample_rate']:.1f} ms")

    for w in (period, rate):
        w.currentTextChanged.connect(show_latency)
    periods.valueChanged.connect(show_latency)
    show_latency()

    def save():
        realtime.set_audio_config(**values())
        app.log(f"audio settings saved: {values()}")

    def test():
        save()
        status.setStyleSheet("")
        status.setText("testing…")
        status.repaint()
        try:
            info = realtime.test()
            msg = (f"OK: driver {info['driver']}, device {info['device'] or 'default'}, "
                   f"buffer {info['period_size']} x {info['periods']}, latency {info['latency_ms']} ms")
            if info["error"]:
                msg += f"  [{info['error']}]"
            status.setStyleSheet("color: green")
        except Exception as e:
            msg = f"Audio did not start: {e}"
            status.setStyleSheet("color: red")
        status.setText(msg)
        app.log(msg)

    mic = realtime.InputMeter()
    mic_timer = QTimer(d)
    mic_timer.setInterval(50)
    state = {"shown": -60.0, "ticks": 0}

    def stop_meter():
        mic_timer.stop()
        mic.stop()
        meter.setValue(0)
        meter_db.setText("")
        mic_hint.setText("")
        mic_btn.setChecked(False)
        mic_btn.setText("Test microphone")

    def toggle_meter(on):
        if on:
            mic_btn.setText("Stop test")
            start_meter()
        else:
            stop_meter()

    def restart_meter(*_):
        if mic_btn.isChecked():
            start_meter()

    def start_meter(*_):
        dev = None if indev.currentText() in ("", "(default)") else indev.currentText()
        mic.start(dev)
        state.update(shown=-60.0, ticks=0)
        if mic.error:
            mic_hint.setStyleSheet("color: red")
            mic_hint.setText(f"Input did not start: {mic.error}")
        else:
            mic_hint.setStyleSheet("color: gray")
            mic_hint.setText(f"'{mic.device}': play or speak, the bar must move")
        mic_timer.start()

    def update_meter():
        db = mic.level()
        state["shown"] = max(db, state["shown"] - 1.5)          # smooth fall
        meter.setValue(int(max(0, min(60, state["shown"] + 60))))
        meter_db.setText(f"{state['shown']:6.1f} dBFS" if state["shown"] > -59.5 else "  -inf dBFS")
        state["ticks"] += 1
        if state["ticks"] == 80 and mic.error is None and mic.max_peak < 1e-4:   # 4 s of silence
            mic_hint.setStyleSheet("color: red")
            mic_hint.setText("Silence from the microphone: check the permission (macOS: System "
                             "Settings > Privacy & Security > Microphone, for Terminal/Python) "
                             "or choose another input device.")

    mic_timer.timeout.connect(update_meter)
    mic_btn.toggled.connect(toggle_meter)
    indev.currentTextChanged.connect(restart_meter)

    # ------------------------------------------------ Test MIDI
    kb = {"synth": None, "ticks": 0}
    midi_timer = QTimer(d)
    midi_timer.setInterval(100)
    seen = []

    def midi_listen(msg, t):
        seen.append(mi.describe(msg))

    def stop_midi():
        midi_timer.stop()
        if kb["synth"] is not None:
            kb["synth"].close()
            kb["synth"] = None
        midi_btn.setChecked(False)
        midi_btn.setText("Test MIDI")

    def start_midi():
        fill_midi()                               # a keyboard plugged in after opening
        seen.clear()
        kb["ticks"] = 0
        want = None if midiin.currentText() in ("", "(first connected)") else midiin.currentText()
        try:
            name = mi.port_name(want)
            if name is None:
                raise RuntimeError("no MIDI keyboard connected: plug it in (USB) and press "
                                   "Test MIDI again")
            try:
                k = mi.KeyboardSynth(program=mi.FROM_KEYBOARD, listener=midi_listen).open(name)
                sound = f"sound: soundfont, latency {k.latency_ms} ms"
            except Exception as e:                # no soundfont / audio: show the notes only
                k = mi.KeyboardSynth(sound=False, listener=midi_listen).open(name)
                sound = f"no sound ({e})"
            kb["synth"] = k
            midi_show.setStyleSheet("color: gray")
            midi_show.setText(f"'{name}' open ({sound}): play some keys…")
            app.log(f"MIDI test: '{name}' open, {sound}")
            midi_timer.start()
        except Exception as e:
            midi_show.setStyleSheet("color: red")
            midi_show.setText(str(e))
            app.log(f"MIDI test: {e}")
            midi_btn.setChecked(False)

    def toggle_midi(on):
        if on:
            midi_btn.setText("Stop test")
            start_midi()
        else:
            stop_midi()

    def update_midi():
        kb["ticks"] += 1
        k = kb["synth"]
        if k is None:
            return
        if seen:
            midi_show.setStyleSheet("color: green")
            midi_show.setText(f"OK, {k.count} messages — last: " + " | ".join(seen[-3:]))
        elif kb["ticks"] == 40:                   # 4 s without messages
            midi_show.setStyleSheet("color: red")
            midi_show.setText(f"Nothing received from '{k.name}': check the cable / USB, that "
                              "the keyboard sends on its MIDI/USB output (local control), or "
                              "choose another port.")

    midi_timer.timeout.connect(update_midi)
    midi_btn.toggled.connect(toggle_midi)
    midiin.currentTextChanged.connect(lambda *_: (start_midi() if midi_btn.isChecked() else None))

    def stop_all():
        stop_meter()
        stop_midi()
    d.stop = stop_all
    d.test_midi = lambda on=True: midi_btn.setChecked(on)
    d.midi_status = lambda: midi_show.text()

    def test_input():
        save()
        status.setStyleSheet("")
        status.setText("recording 2 s from the microphone: play or speak…")
        status.repaint()
        try:
            r = realtime.test_input(values()["input_device"])
            if r["silent"]:
                msg = (f"Input '{r['device']}': SILENCE (peak {r['peak_db']} dBFS). Check the "
                       "microphone permission (macOS: System Settings > Privacy & Security > "
                       "Microphone, for Terminal/Python) or choose another input device.")
                status.setStyleSheet("color: red")
            else:
                msg = (f"Input '{r['device']}' OK: peak {r['peak_db']} dBFS, "
                       f"rms {r['rms_db']} dBFS ({r['samplerate']} Hz)")
                status.setStyleSheet("color: green")
        except Exception as e:
            msg = f"Input did not start: {type(e).__name__}: {e}"
            status.setStyleSheet("color: red")
        status.setText(msg)
        app.log(msg)

    row = QHBoxLayout()
    for text, fn in (("Test sound", test),):
        b = QPushButton(text)
        b.clicked.connect(fn)
        row.addWidget(b)
    row.addStretch()
    lay.addLayout(row)
    lay.addStretch()
    d.test, d.test_input, d.save, d.values = test, test_input, save, values   # drivable from code
    d.meter = mic
    return d
