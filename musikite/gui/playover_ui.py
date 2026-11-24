"""Play over MIDI tab (owner, 2026-11-08; logic `playover.PlayOver`, no grade): "Show and
mute" = up to three tracks of the MIDI shown on the staff (written for their instrument)
and silent; Start = one count-in bar, then the cursor moves while the soundfont plays all the
other tracks (tempo map of the MIDI × Tempo %, accompaniment volume, Click). Played to the
end = done (for the session: routines go on to the next item); Stop = nothing.

Practice > Play over MIDI on a selected MIDI / score makes the exercise (in Objects) and
opens it; Generate > Exercises to do > Play over MIDI only makes it; double click on it
(or a routine) opens this tab bound to it.

EMPTY TAB (owner, 2026-11-17: opened from the menu with nothing selected it was a dead
end): a MIDI, a PDF or a score is DRAGGED into it (from Objects > Material or from the
Finder) or chosen with OPEN… (native dialog; the touch alternative of the drag, Android
tablets); a file is opened as an object, a PDF is read to MIDI first (Convert > PDF → MIDI),
then the exercise is made (Objects) and the tab is bound to it. A bound tab takes no drop
and has no Open….
CLICK BUTTON (owner, 2026-11-17): the "Click" box is replaced by the Click button of the
bar (bar.click_button): beat of the bar while playing, press = clicks off / on at once.
START FROM A BAR (owner, 2026-11-23): a click on a bar = Start begins there (after the
count-in bar); a double click = it starts from there at once. Played to the end counts as
done only when it started from the first bar.
SHOW POSITIONS (owner, 2026-11-23): box in the bar, as in Read & play: the valves / slide
positions under the notes of every part shown that has fingerings (`PlayOver.score(
positions=True)`); saved per user and per instrument beside the user (the same setting
as Read & play); shown only when a part shown has fingerings.
PLAY-ALONG GRADED (owner, 2026-11-24): box "Grade" (+ "Graded" = which of the tracks shown,
when more than one): Start = one take recorded from the microphone and graded as Read &
play (`PlayOver.play_along`: the accompaniment rendered into the take at one constant
tempo, from the first bar of the bars to play); the notes of the graded part green / red,
the grade shown and written in the practice diary (kind 'play_along'). ONLY WITH
HEADPHONES: a warning when the audio output is the loudspeakers.
SPACE BAR (owner, 2026-11-23) = the Start / Stop button (`space_bar`, called by the main
window's key filter when this tab is in front)."""

FILE_TYPES = (".mid", ".midi", ".pdf", ".musicxml", ".xml", ".mxl")


def playover_widget(app, obj=None):
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
                                   QSpinBox, QCheckBox, QListWidget, QListWidgetItem)
    from PySide6.QtCore import Qt
    from .bar import action_bar, hscroll, click_button
    from ..playover import MAX_TRACKS

    class PlayOverWidget(QWidget):
        def __init__(self):
            super().__init__()
            self.app = app
            self.obj = None
            self.sv = None
            self._take = None                        # a graded take going on
            self._take_timer = None
            self._zoom = 1.0
            self.status = QLabel("")
            self.click_btn = click_button(True, self._click_toggled)
            from PySide6.QtWidgets import QCheckBox
            from .play_reading import _show_positions
            self.pos_box = QCheckBox("Show positions")
            self.pos_box.setChecked(_show_positions())
            self.pos_box.setToolTip("the valves or the slide positions under the notes of "
                                    "the parts shown")
            self.pos_box.toggled.connect(self._positions_toggled)
            self.pos_box.setVisible(False)
            self._pos_ok = False                 # a part shown has fingerings
            # ONE BAR (owner, 2026-11-20): Start / Stop in one button
            self.bar, self.buttons = action_bar(
                [("Start", self.start, "count-in bar, then play the parts shown while the "
                                       "others are heard; while it plays: stop (not "
                                       "counted as done)"),
                 ("Open…", self.open_file, "choose a MIDI, a PDF or a score (or drag one "
                                           "into this tab)"),
                 ("Zoom +", lambda: self.zoom(1.25), "larger staff"),
                 ("Zoom -", lambda: self.zoom(0.8), "smaller staff"),
                 self.pos_box, self.click_btn], right=self.status)
            from .bar import start_stop
            start_stop(self.buttons["Start"], self.start, self.stop, self.busy)
            self.setAcceptDrops(True)
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
            acc = QLabel("Accomp.:")                       # short (owner): Click stays in view
            acc.setToolTip("volume of the accompaniment (the tracks not shown)")
            self.bar_a, self.bar_b = QSpinBox(), QSpinBox()      # bars to play (0 = all)
            for sp, tip, word in ((self.bar_a, "first bar to play", "start"),
                                  (self.bar_b, "last bar to play", "end")):
                sp.setRange(0, 9999)
                sp.setSpecialValueText(word)              # 0 = from the start / to the end
                sp.setToolTip(tip)
                sp.editingFinished.connect(self._bars_changed)
            from PySide6.QtWidgets import QComboBox
            self.grade_box = QCheckBox("Grade")
            self.grade_box.setToolTip("play-along graded: the part you play is recorded and "
                                      "graded (HEADPHONES needed: the microphone must not "
                                      "hear the band)")
            self.grade_box.toggled.connect(self._grade_toggled)
            self.graded_combo = QComboBox()
            self.graded_combo.setToolTip("the track graded")
            self.graded_combo.currentIndexChanged.connect(self._graded_changed)
            for wdg in (QLabel("Bars:"), self.bar_a, QLabel("to"), self.bar_b,
                        QLabel("Tempo:"), self.tempo, acc, self.volume, self.grade_box,
                        self.graded_combo):
                row.addWidget(wdg)
            row.addStretch(1)                         # compact: no gaps between the fields
            for wdg in (self.tempo, self.volume):
                wdg.valueChanged.connect(self._settings_changed)
            lay.addWidget(hscroll(box))
            self.staff_box = QVBoxLayout()
            lay.addLayout(self.staff_box, 1)
            self.box = box
            self.info = QLabel("Drag a MIDI, a PDF or a score here (from Objects or from the "
                               "Finder), or press Open…")
            self.info.setWordWrap(True)
            self.info.setAlignment(Qt.AlignCenter)
            lay.addWidget(self.info)
            if obj is not None:
                self.bind(obj)
            else:
                self.box.setEnabled(False)               # nothing to set until a MIDI comes

        # ------------------------------------------------------ an empty tab: drag / Open…
        def _paths(self, md):
            return [u.toLocalFile() for u in md.urls()
                    if u.toLocalFile().lower().endswith(FILE_TYPES)] if md.hasUrls() else []

        def _drop_ok(self, e):
            if self.obj is not None:                     # bound: no drop
                return False
            if e.source() is getattr(app, "mat_list", None):
                return True
            return bool(self._paths(e.mimeData()))

        def dragEnterEvent(self, e):
            if self._drop_ok(e):
                e.acceptProposedAction()
            else:
                e.ignore()

        def dragMoveEvent(self, e):
            if self._drop_ok(e):
                e.acceptProposedAction()
            else:
                e.ignore()

        def dropEvent(self, e):
            if not self._drop_ok(e):
                return e.ignore()
            e.acceptProposedAction()
            if e.source() is getattr(app, "mat_list", None):
                from ..midi import Midi
                from ..score import Score
                from ..pdf import Pdf
                objs = app.selected_objects((Midi, Score, Pdf))
                if not objs:
                    self.info.setText("Drag a MIDI, a PDF or a score")
                    return None
                return self.use(objs[0], more=len(objs) - 1)
            paths = self._paths(e.mimeData())
            return self.use_file(paths[0], more=len(paths) - 1)

        def open_file(self):
            """Open…: the native dialog (the touch alternative of the drag)."""
            from PySide6.QtWidgets import QFileDialog
            from ..progress import folder
            if self.obj is not None:
                return None
            path, _ = QFileDialog.getOpenFileName(
                app.win, "Play over MIDI: open", folder("midi"),
                "MIDI, PDF, MusicXML (*.mid *.midi *.pdf *.musicxml *.xml *.mxl)")
            if not path:
                return None                              # cancelled: nothing changes
            return self.use_file(path)

        def use_file(self, path, more=0):
            """A file: opened as an object (Objects > Material), then used."""
            name = app.open_file(path)
            if isinstance(name, list):
                name = name[0] if name else None
            o = app.get_object(name) if name else None
            if o is None:
                self.info.setText(f"Cannot open {path} (see Log)")
                return None
            return self.use(o, more)

        def use(self, src, more=0):
            """A MIDI / score / PDF: a new Play over MIDI exercise (Objects), bound here. A PDF
            is read to MIDI first (Convert > PDF → MIDI, the MIDI goes into Objects too)."""
            from PySide6.QtWidgets import QApplication
            from ..pdf import Pdf
            from ..midi import Midi
            from ..score import Score
            if more:
                app.log(f"Play over MIDI: only the first of {more + 1} is used")
            if isinstance(src, Pdf):
                self.info.setText("Reading the PDF…")
                self.info.repaint()
                name = app.run_tool("pdf2midi", src)
                if isinstance(name, list):
                    name = name[0] if name else None
                src = app.get_object(name) if name else None
                if src is None:
                    self.info.setText("The PDF could not be read as MIDI (see the Log: View > "
                                      "Log)")
                    return None
            if not isinstance(src, (Midi, Score)):
                self.info.setText("Drag a MIDI, a PDF or a score")
                return None
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                po = _make(src)
            except Exception as e:
                self.info.setText(f"{type(e).__name__}: {e}")
                app.log(f"Play over MIDI: {type(e).__name__}: {e}")
                return None
            finally:
                QApplication.restoreOverrideCursor()
            app.add_object(po, po.title, preview=False)   # this tab shows it
            app.refresh_exercises()
            return self.bind(po)

        # ------------------------------------------------------ the exercise
        def bind(self, o):
            self.stop()
            self.obj = o
            self.box.setEnabled(True)
            self.buttons["Open…"].hide()                  # bound: no other MIDI here
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
            self.click_btn.set_on(o.click)
            n = o.n_bars()
            for sp in (self.bar_a, self.bar_b):
                sp.setRange(0, n)
            self.bar_a.setValue(o.bar_from or 0)
            self.bar_b.setValue(o.bar_to or 0)
            self.grade_box.setChecked(bool(getattr(o, "grade", False)))
            self._loading = False
            self._fill_graded()
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
            self._fill_graded()
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
            self.obj.click = self.click_btn.on

        def _click_toggled(self, on):
            """Click button: the clicks off / on at once (also while playing), kept in the
            exercise."""
            if self.obj is not None:
                self.obj.click = bool(on)
            if self.sv is not None:
                self.sv.set_click(on)
            if getattr(self, "_take", None) is not None:    # a graded take: its stream
                self._take["pc"].set_click(on)

        def _show_staff(self):
            from PySide6.QtWidgets import QApplication
            from ..staffview import StaffView
            if self.sv is not None:
                self.sv.stop()
                self.sv.win.setParent(None)
                self.sv.win.deleteLater()
                self.sv = None
            self._positions_visible()
            if not self.obj.tracks:
                self.info.setText("Choose the tracks to read in Show and mute (1 to "
                                  f"{MAX_TRACKS}): they are shown and silent")
                return None
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                score = self.obj.score(positions=self._positions())
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
            self.sv.on_beat = self.click_btn.show_beat    # the beat on the Click button
            self.sv.on_double_click = lambda q: self.start()   # from that bar (2026-11-23)
            self.sv.set_position(0)                       # the first bar in the status
            self.info.setText(f"{self.obj.title}  (grade n/a: played to the end = done)")
            return self.sv

        # ------------------------------------------------------ play-along graded
        def _fill_graded(self):
            """The tracks shown in the "Graded" list (visible with Grade and 2+ tracks)."""
            self.graded_combo.blockSignals(True)
            self.graded_combo.clear()
            if self.obj is not None:
                labels = dict(self.obj.readable())
                for t in self.obj.tracks:
                    self.graded_combo.addItem(labels.get(t, str(t + 1)), t)
                g = self.obj.graded()
                if g is not None:
                    self.graded_combo.setCurrentIndex(max(0, self.graded_combo.findData(g)))
            self.graded_combo.blockSignals(False)
            self.graded_combo.setVisible(self.grade_box.isChecked()
                                         and self.graded_combo.count() > 1)

        def _grade_toggled(self, on):
            if self.obj is not None and not getattr(self, "_loading", False):
                self.obj.grade = bool(on)
            self._fill_graded()
            if on:
                self._headphones_warning()

        def _graded_changed(self, i):
            if self.obj is not None and i >= 0:
                self.obj.graded_track = self.graded_combo.itemData(i)

        def _headphones_warning(self):
            """PLAY-ALONG NEEDS HEADPHONES (owner, 2026-11-24)."""
            from ..realtime import output_is_speakers, audio_config
            spk, name = output_is_speakers(audio_config().get("device") or None)
            if spk:
                msg = (f"WARNING: the sound goes to the loudspeakers ({name}): the graded "
                       "play-along works only with HEADPHONES (the microphone must not hear "
                       "the band)")
                self.info.setText(msg)
                self.app.log(f"Play over MIDI: {msg}")
                return True
            return False

        def _start_graded(self):
            """One graded take: count-in bar, the accompaniment in the same audio stream as
            the microphone, the cursor on the stream clock; graded at the end."""
            from PySide6.QtCore import QTimer
            from .play_reading import _StreamClock
            from ..realtime import audio_config
            warned = self._headphones_warning()
            try:
                d = self.obj.play_along(user=self.app.user, click=bool(self.obj.click))
            except Exception as e:
                self.info.setText(f"{type(e).__name__}: {e}")
                self.app.log(f"Play over MIDI: {type(e).__name__}: {e}")
                return None
            self._take = d
            self._from_start = True                      # always from the first bar
            pc = d["pc"]
            if self.sv.from_q:
                self.app.log("Play over MIDI: a graded take starts from the first bar of the "
                             "bars to play (Bars from / to choose a passage)")
            self.sv.from_q = None
            self.sv.clear_marks()
            self.sv.tempo_pm = None                      # constant tempo in a graded take
            self.sv.midi = None
            cfg = audio_config()
            pc.start(input_device=cfg.get("input_device") or None,
                     output_device=cfg.get("device") or None)
            self.sv.play(bpm=pc.bpm, start=0, count_in=1, click=False, sound=False)
            self.sv.player = _StreamClock(pc)
            if self._take_timer is None:
                self._take_timer = QTimer(self)
                self._take_timer.setSingleShot(True)
                self._take_timer.timeout.connect(self._end_graded)
            self._take_timer.start(int(pc.duration * 1000) + 300)
            if not warned:
                self.info.setText(f"{self.obj.title}: graded take at {pc.bpm:.0f} bpm"
                                  + (" (tempo changes not followed)" if d["tempo_changes"]
                                     else ""))
            self.app.log(f"Play over MIDI: graded take of track {d['track'] + 1}, "
                         f"{pc.bpm:.0f} bpm")
            return self

        def _end_graded(self):
            d, self._take = self._take, None
            if d is None:
                return
            pc = d["pc"]
            self.sv.stop()
            try:
                pc.wait(timeout=1.0)
                r = pc.evaluate(source="microphone")
            except Exception as e:
                self.info.setText(f"{type(e).__name__}: {e}")
                self.app.log(f"Play over MIDI: grading: {type(e).__name__}: {e}")
                return
            off = sum(1 for k in self.sv._rows if k[0] < d["part"])   # rows of the parts above
            self.sv.mark({off + row: ("green" if ok else "red")
                          for row, ok in r["correct_rows"].items()})
            self.sv.set_position(0)
            self.info.setText(f"{r['rating']}   {r['grade']:.1f}/10   ({r['ok']}/{r['nn']} "
                              f"notes)   —   {self.obj.title}")
            self.app.log(f"Play over MIDI: graded {r['grade']:.1f} ({r['ok']}/{r['nn']})")
            try:
                from ..diary import get, SOUND_FACTOR
                get(self.app.user).record("play_along", self.obj.diary_key(), r["grade"],
                                          SOUND_FACTOR * float(pc.duration or 0.0),
                                          self.obj.title)
            except Exception as e:
                self.app.log(f"Play over MIDI: diary: {type(e).__name__}: {e}")

        # ------------------------------------------------------ show positions
        def _positions(self):
            return self._pos_ok and self.pos_box.isChecked()

        def _positions_visible(self):
            """The box only when a part shown has fingerings; its state = the setting of
            the instrument beside the user."""
            from .play_reading import _show_positions
            ok = self.obj is not None and self.obj.has_positions()
            self.pos_box.blockSignals(True)
            self.pos_box.setChecked(_show_positions())
            self.pos_box.blockSignals(False)
            self._pos_ok = bool(ok)
            self.pos_box.setVisible(ok)

        def _positions_toggled(self, on):
            """Saved per user and instrument; the staff drawn again at once (not while
            playing: from the next Start)."""
            from .play_reading import _set_show_positions
            try:
                _set_show_positions(bool(on))
            except Exception:
                pass
            if self.obj is not None and not self.busy():
                self._show_staff()

        def instrument_changed(self, key):
            """Another instrument beside the user: its own Show positions state."""
            was = self._positions()
            self._positions_visible()
            if self.obj is not None and self._positions() != was and not self.busy():
                self._show_staff()

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
            if self.obj.grade:                              # play-along graded (2026-11-24)
                return self._start_graded()
            self.sv.midi = self.obj.accompaniment()
            self.sv.tempo_pm = self.sv.midi.pm               # the MIDI's tempo map
            self.sv.q_offset = self.obj.start_q()            # the bars chosen
            self.sv.speed = self.obj.tempo_pct / 100.0
            self.sv.click_audible = bool(self.obj.click)    # Click button: switched live
            start = self.sv.from_q or 0.0                   # the bar clicked (2026-11-23)
            self._from_start = start <= 1e-9
            try:
                self.sv.play(start=start, count_in=1, click=True, music=True)
            except Exception as e:
                self.info.setText(f"{type(e).__name__}: {e}")
                self.app.log(f"Play over MIDI: {type(e).__name__}: {e}")
                return None
            self.app.log(f"Play over MIDI: {self.obj.title} at {self.obj.tempo_pct} %")
            return self

        def stop(self):
            if getattr(self, "_take_timer", None) is not None:
                self._take_timer.stop()
            d = getattr(self, "_take", None)
            if d is not None:                              # a graded take: not graded
                self._take = None
                try:
                    d["pc"].stop()
                except Exception:
                    pass
            if self.sv is not None:
                self.sv.stop()
            return self

        def space_bar(self):
            """SPACE BAR = the Start / Stop button (owner, 2026-11-23)."""
            if self.busy():
                self.stop()
            else:
                self.start()
            return True

        def busy(self):
            """Playing: the routine's ◀ ▶ wait."""
            return (self.sv is not None and self.sv.timer.isActive()) or \
                getattr(self, "_take", None) is not None

        def _finished(self):
            """Played to the end: done for this session (no grade, nothing saved)."""
            from ..tasks import mark_done
            if not getattr(self, "_from_start", True):
                self.app.log(f"Play over MIDI: {self.obj.title} played from a bar to the end "
                             "(not counted as done)")
                return
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
    opened; nothing selected -> an empty tab that takes a dragged MIDI / PDF / score or
    Open…"""
    from ..midi import Midi
    from ..score import Score
    sel = app.selected_objects((Midi, Score))
    if sel:
        po = _make(sel[0])
        app.add_object(po, po.title, preview=False)   # its tab opens
        return playover_widget(app, po)
    return playover_widget(app)


def _practice_open(app):
    """Practice > Play over MIDI (bug fixed 2026-11-23: with the tab of a piece already
    open, choosing it on ANOTHER MIDI brought back the previous piece — open_tool only
    brought the old tab to the front). A MIDI / score selected -> a NEW exercise in
    Objects and ITS OWN tab (as a double click on it: app.practise); nothing selected ->
    the empty tab if one is open and still empty, else a new empty one."""
    from ..midi import Midi
    from ..score import Score
    sel = app.selected_objects((Midi, Score))
    if sel:
        po = _make(sel[0])
        name = app.add_object(po, po.title, preview=False) or po.title
        return app.practise(po, name, key=f"open: {name}")
    w = app.tool_widgets.get("play_over")
    if w is None or app.tabs.indexOf(w) < 0 or getattr(w, "obj", None) is not None:
        w = playover_widget(app)
        app.tool_widgets["play_over"] = w
        app.add_tab(w, "Play over MIDI")
    app.tabs.setCurrentWidget(w)
    return w


def _register():
    from .registry import register, Tool, Param
    from ..midi import Midi
    from ..score import Score
    register(Tool(
        name="play_over", label="Play over MIDI", category="Practice", kind="session",
        factory=_practice_factory, opener=_practice_open, inputs=(Midi, Score),
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
