"""Play over MIDI tab (owner, 2026-11-08; logic `playover.PlayOver`, no grade): "Show and
mute" = up to three tracks of the MIDI shown on the staff (written for their instrument)
and silent; Start = one count-in bar, then the cursor moves while the soundfont plays all the
other tracks (tempo map of the MIDI × Tempo %, accompaniment volume, Click). Played to the
end = done (for the session: routines go on to the next item); Stop = nothing.

Practice > Play over MIDI on a selected MIDI / score makes the exercise (in Objects) and
opens it; Generate > Exercises to do > Play over MIDI only makes it; double click on it
(or a routine) opens this tab bound to it."""


def playover_widget(app, obj=None):
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                                   QSpinBox, QCheckBox, QListWidget, QListWidgetItem)
    from PySide6.QtCore import Qt
    from .bar import action_bar, hscroll
    from ..playover import MAX_TRACKS

    class PlayOverWidget(QWidget):
        def __init__(self):
            super().__init__()
            self.app = app
            self.obj = None
            self.sv = None
            self._zoom = 1.0
            self.status = QLabel("")
            self.bar, self.buttons = action_bar(
                [("Start", self.start, "count-in bar, then play the parts shown while the "
                                       "others are heard"),
                 ("Stop", self.stop, "stop (not counted as done)"),
                 None,
                 ("Zoom +", lambda: self.zoom(1.25), "larger staff"),
                 ("Zoom -", lambda: self.zoom(0.8), "smaller staff")], right=self.status)
            lay = QVBoxLayout(self)
            box = QGroupBox("Settings")
            row = QHBoxLayout(box)
            row.addWidget(QLabel(f"Show and mute\n(up to {MAX_TRACKS}):"))   # two lines
            self.tracks = QListWidget()
            self.tracks.setMaximumHeight(90)
            self.tracks.itemChanged.connect(self._tracks_changed)
            row.addWidget(self.tracks)            # as wide as the longest name (_fit_tracks)
            self.tempo = QSpinBox()
            self.tempo.setRange(25, 200)
            self.tempo.setSuffix(" %")
            self.tempo.setToolTip("tempo of the MIDI × this (its tempo changes are followed)")
            self.volume = QSpinBox()
            self.volume.setRange(0, 150)
            self.volume.setSuffix(" %")
            self.volume.setToolTip("volume of the other tracks")
            self.click = QCheckBox("Click")
            acc = QLabel("Accomp.:")                       # short (owner): Click stays in view
            acc.setToolTip("volume of the accompaniment (the tracks not shown)")
            self.bar_a, self.bar_b = QSpinBox(), QSpinBox()      # bars to play (0 = all)
            for sp, tip, word in ((self.bar_a, "first bar to play", "start"),
                                  (self.bar_b, "last bar to play", "end")):
                sp.setRange(0, 9999)
                sp.setSpecialValueText(word)              # 0 = from the start / to the end
                sp.setToolTip(tip)
                sp.editingFinished.connect(self._bars_changed)
            for wdg in (QLabel("Bars:"), self.bar_a, QLabel("to"), self.bar_b,
                        QLabel("Tempo:"), self.tempo, acc, self.volume,
                        self.click):
                row.addWidget(wdg)
            row.addStretch(1)                         # compact: no gaps between the fields
            for wdg in (self.tempo, self.volume):
                wdg.valueChanged.connect(self._settings_changed)
            self.click.toggled.connect(self._settings_changed)
            lay.addWidget(hscroll(box))
            self.staff_box = QVBoxLayout()
            lay.addLayout(self.staff_box, 1)
            self.info = QLabel("Select a MIDI or a score in Objects and choose Practice > "
                               "Play over MIDI")
            self.info.setWordWrap(True)
            self.info.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.info)
            if obj is not None:
                self.bind(obj)

        # ------------------------------------------------------ the exercise
        def bind(self, o):
            self.stop()
            self.obj = o
            self._loading = True
            self.tracks.blockSignals(True)
            self.tracks.clear()
            for i, label in o.readable():
                it = QListWidgetItem(label)
                it.setData(Qt.UserRole, i)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if i in o.tracks else Qt.Unchecked)
                self.tracks.addItem(it)
            self.tracks.blockSignals(False)
            self._fit_tracks()
            self.tempo.setValue(o.tempo_pct)
            self.volume.setValue(o.volume_pct)
            self.click.setChecked(o.click)
            n = o.n_bars()
            for sp in (self.bar_a, self.bar_b):
                sp.setRange(0, n)
            self.bar_a.setValue(o.bar_from or 0)
            self.bar_b.setValue(o.bar_to or 0)
            self._loading = False
            self._show_staff()
            return self

        def _fit_tracks(self):
            """The track list as wide as its longest name (+ check box, frame, scroll bar)."""
            from PySide6.QtWidgets import QStyle
            w = max([self.tracks.sizeHintForColumn(0)] + [0])
            extra = (2 * self.tracks.frameWidth()
                     + self.tracks.style().pixelMetric(QStyle.PM_ScrollBarExtent) + 8)
            self.tracks.setFixedWidth(max(80, w + extra))

        def _checked(self):
            return [self.tracks.item(k).data(Qt.UserRole) for k in range(self.tracks.count())
                    if self.tracks.item(k).checkState() == Qt.Checked]

        def _tracks_changed(self, item):
            if self.obj is None or getattr(self, "_loading", False):
                return
            sel = self._checked()
            if len(sel) > MAX_TRACKS:                   # at most three
                self.tracks.blockSignals(True)
                item.setCheckState(Qt.Unchecked)
                self.tracks.blockSignals(False)
                self.info.setText(f"At most {MAX_TRACKS} tracks can be shown")
                return
            self.stop()
            self.obj.set_tracks(sel)
            self.obj.title = self.obj.make_title()
            self._show_staff()
            self.app.refresh_exercises()

        def _bars_changed(self):
            """Bars to play changed: a new staff (original bar numbers)."""
            if self.obj is None or getattr(self, "_loading", False):
                return
            old = (self.obj.bar_from, self.obj.bar_to)
            a, b = self.obj.set_bars(self.bar_a.value() or None, self.bar_b.value() or None)
            self._loading = True
            self.bar_a.setValue(a or 0)
            self.bar_b.setValue(b or 0)
            self._loading = False
            if (a, b) != old:
                self.stop()
                self.obj.title = self.obj.make_title()
                self._show_staff()
                self.app.refresh_exercises()

        def _settings_changed(self, *_):
            if self.obj is None or getattr(self, "_loading", False):
                return
            self.obj.tempo_pct = self.tempo.value()
            self.obj.volume_pct = self.volume.value()
            self.obj.click = self.click.isChecked()

        def _show_staff(self):
            from PySide6.QtWidgets import QApplication
            from ..staffview import StaffView
            if self.sv is not None:
                self.sv.stop()
                self.sv.win.setParent(None)
                self.sv.win.deleteLater()
                self.sv = None
            if not self.obj.tracks:
                self.info.setText("Choose the tracks to read in Show and mute (1 to "
                                  f"{MAX_TRACKS}): they are shown and silent")
                return None
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                score = self.obj.score()
                self.sv = StaffView(score, title=self.obj.title)
            except Exception as e:
                self.info.setText(f"{type(e).__name__}: {e}")
                self.app.log(f"Play over MIDI: {type(e).__name__}: {e}")
                return None
            finally:
                QApplication.restoreOverrideCursor()
            self.sv.win.setWindowFlags(Qt.Widget)
            self.sv.hide_toolbar()
            self.staff_box.addWidget(self.sv.win)
            if abs(self._zoom - 1.0) > 1e-6:
                self.sv.zoom(self._zoom)
            self.sv.end_q = max(self.sv.end_q, self.obj.end_q())
            self.sv.on_end = self._finished
            self.sv.on_position = lambda beat, bar: self.status.setText(f"Bar {bar}")
            self.sv.set_position(0)                       # the first bar in the status
            self.info.setText(f"{self.obj.title}  (grade n/a: played to the end = done)")
            return self.sv

        def zoom(self, f):
            self._zoom = max(0.2, min(5.0, self._zoom * f))
            if self.sv is not None:
                self.sv.zoom(f)
            return self

        # ------------------------------------------------------ playing
        def start(self):
            if self.obj is None or self.sv is None:
                if self.obj is not None:
                    self.info.setText("Choose the tracks to read first (Show and mute)")
                return None
            self._settings_changed()
            self.sv.midi = self.obj.accompaniment()
            self.sv.tempo_pm = self.sv.midi.pm               # the MIDI's tempo map
            self.sv.q_offset = self.obj.start_q()            # the bars chosen
            self.sv.speed = self.obj.tempo_pct / 100.0
            try:
                self.sv.play(start=0, count_in=1, click=self.obj.click, music=True)
            except Exception as e:
                self.info.setText(f"{type(e).__name__}: {e}")
                self.app.log(f"Play over MIDI: {type(e).__name__}: {e}")
                return None
            self.app.log(f"Play over MIDI: {self.obj.title} at {self.obj.tempo_pct} %")
            return self

        def stop(self):
            if self.sv is not None:
                self.sv.stop()
            return self

        def busy(self):
            """Playing: the routine's ◀ ▶ wait."""
            return self.sv is not None and self.sv.timer.isActive()

        def _finished(self):
            """Played to the end: done for this session (no grade, nothing saved)."""
            from ..tasks import mark_done
            mark_done(self.obj, self.app.user)
            self.app.log(f"Play over MIDI: {self.obj.title} played to the end (done)")
            self.app.attempt_added(self.obj)

        def user_changed(self, name):
            self.stop()

        def closing(self):
            self.stop()

    return PlayOverWidget()


# ---------------------------------------------------------------- tools
def _make(src, tracks=None, tempo=100, bar_from=0, bar_to=0):
    """tracks: track indices (0-based; the Generate check list) or a text "1,2" (1-based)."""
    from ..playover import PlayOver
    if isinstance(tracks, str):
        tracks = [int(x) - 1 for x in tracks.replace(";", ",").split(",") if x.strip().isdigit()]
    po = PlayOver.from_midi(src, list(tracks or []) or None, tempo_pct=int(tempo))
    if bar_from or bar_to:
        po.set_bars(bar_from or None, bar_to or None)
        po.title = po.make_title()
    return po


def _track_choices(src):
    """Generate panel: the tracks of the selected MIDI / score, none ticked (owner: the
    trumpet is an instrument like the others; the user chooses)."""
    from ..playover import PlayOver
    try:
        po = PlayOver.from_midi(src)
    except Exception:
        return []
    return [(i, label, i in po.tracks) for i, label in po.readable()]


def _practice_factory(app):
    """Practice > Play over MIDI: on the selected MIDI / score -> a new exercise in Objects,
    opened; nothing selected -> an empty tab saying what to do."""
    from ..midi import Midi
    from ..score import Score
    sel = app.selected_objects((Midi, Score))
    if sel:
        po = _make(sel[0])
        app.add_object(po, po.title)
        return playover_widget(app, po)
    return playover_widget(app)


def _register():
    from .registry import register, Tool, Param
    from ..midi import Midi
    from ..score import Score
    register(Tool(
        name="play_over", label="Play over MIDI", category="Practice", kind="session",
        factory=_practice_factory, inputs=(Midi, Score),
        help="Read up to three tracks of a MIDI (shown and muted) and play them while the "
             "app plays all the others. No grade."))
    register(Tool(
        name="todo_play_over", label="Play over MIDI", category="Generate", kind="transform",
        submenu="Exercises to do", inputs=(Midi, Score),
        func=lambda src, tracks=None, tempo=100, bar_from=0, bar_to=0:
            _make(src, tracks, tempo, bar_from, bar_to),
        name_fn=lambda s, p: s.title,
        help="A Play over MIDI exercise (the MIDI inside it): the tracks to read are chosen "
             "in its tab; no grade.",
        params=[Param("tracks", "tracks", None, "Show and mute", choices=_track_choices,
                      maximum=3,
                      help="the tracks to read (shown on the staff and silent), up to three; "
                           "the others are played. They can be changed in the tab"),
                Param("bar_from", "int", 0, "From bar", minimum=0, maximum=9999, choices=("start",),
                      help="first bar to play, numbered as in the MIDI (start = from the "
                           "beginning)"),
                Param("bar_to", "int", 0, "To bar", minimum=0, maximum=9999, choices=("end",),
                      help="last bar to play (end = to the end)"),
                Param("tempo", "int", 100, "Tempo %", minimum=25, maximum=200)]))


_register()
