"""
MidiView: the tab of a Midi object in the main window. It opens on the STAFF
(StaffView) and the button "Edit" (owner, 2026-11-25; was "Piano roll") switches to the
piano roll (PianoRollView), where the MIDI is edited as a recording of the Free player
(hand, pencil, eraser, Quantize…, undo) plus the editor tools (Bars…, Double…,
Resample…, Quantize from playing). The edits go into the Midi object itself (Objects >
Save writes them; Play plays them); back on "Staff" the staff is engraved again.

EDITING A COPY (2026-11-25, exercises ♩ and Play over MIDI ♬: an edited exercise is
ANOTHER exercise): `MidiView(midi, title, app, edit=True, end_q=…, on_save=fn)` opens on
the piano roll of a temporary Midi; the bar has "Save as new" = on_save(midi, length_q)
(the caller makes the new object); closing the tab with edits not saved asks first.

Same interface as StaffView for the main window: win, make_bar(), set_position(),
listen(), stop(), timer, obj_name.
"""


class MidiView:
    def __init__(self, midi, title, app=None, edit=False, end_q=None, on_save=None):
        from PySide6.QtWidgets import QWidget, QStackedLayout, QLabel
        from PySide6.QtGui import QFont
        self.midi = midi
        self.title = title
        self.app = app
        self.obj_name = None
        self.mode = "staff"
        self.staff = None
        self.roll = None
        self._staff_old = True                  # the staff must be engraved (again)
        self.win = QWidget()
        self.stack = QStackedLayout(self.win)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel("")
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)
        self.status.setFont(mono)
        self._bar = None
        self._on_end = None                     # end of the music (loop of Play, 2026-11-18)
        self._loop = False                      # Play in a loop (A B…B C), 2026-11-18
        self._on_double_click = None            # double click on a bar (2026-11-23)
        self.end_q = end_q                      # length of an exercise (its empty bars)
        self.on_save = on_save                  # editing a copy: "Save as new"
        self.unsaved = False
        if edit:
            self._show_roll()
        else:
            self._show_staff()

    # ---------------------------------------------------------- views
    def _embed(self, view):
        from PySide6.QtCore import Qt
        view.win.setWindowFlags(Qt.Widget)
        view.hide_toolbar()
        view.win.statusBar().hide()
        view.status = self.status               # beat / bar written in the tab bar
        self.stack.addWidget(view.win)
        return view

    def _show_staff(self):
        from ..staffview import StaffView
        if self.staff is None or self._staff_old:
            if self.staff is not None:
                self.staff.stop()
                self.stack.removeWidget(self.staff.win)
                self.staff.win.deleteLater()
            self.staff = self._embed(StaffView(self.midi, title=self.title))
            self.staff.on_end = self._on_end
            self.staff.loop = self._loop
            self.staff.on_double_click = self._on_double_click
            self._staff_old = False
        self.stack.setCurrentWidget(self.staff.win)
        self.mode = "staff"

    def _show_roll(self):
        from ..pianorollview import PianoRollView
        if self.roll is None:
            self.roll = self._embed(PianoRollView(self.midi, title=self.title,
                                                  on_change=self._edited, tools=True,
                                                  end_q=self.end_q))
            self.roll.on_end = self._on_end
            self.roll.loop = self._loop
            self.roll.on_double_click = self._on_double_click
        self.stack.setCurrentWidget(self.roll.win)
        self.roll.set_position(self.roll.position)
        self.mode = "roll"

    def _edited(self, roll):
        self._staff_old = True
        self.unsaved = True
        if self.app is not None and self.obj_name:
            self.app.log(f"{self.obj_name}: edited in the piano roll ({roll.n_notes()} notes)")

    @property
    def view(self):
        return self.roll if self.mode == "roll" else self.staff

    def toggle(self):
        """Staff <-> Piano roll."""
        self.stop()
        try:
            if self.mode == "staff":
                self._show_roll()
            else:
                self._show_staff()
        except Exception as e:
            if self.app is not None:
                self.app.log(f"{self.title}: {type(e).__name__}: {e}")
        self._update_bar()
        return self

    def edit(self):
        """The piano roll (Edit MIDI / right click > Edit)."""
        if self.mode != "roll":
            self.toggle()
        return self

    def _update_bar(self):
        if self._bar is not None:
            b = self._bar.buttons
            b["Edit"].setText("Staff" if self.mode == "roll" else "Edit")
            b["Line/Page"].setEnabled(self.mode == "staff")

    def save_new(self):
        """Save as new: on_save(midi, length_q) of the caller (a new object); the tab
        stays (more edits = another Save as new)."""
        if self.on_save is None:
            return None
        length = self.roll.roll.length_q() if self.roll is not None else self.end_q
        try:
            res = self.on_save(self.midi, length)
        except Exception as e:
            if self.app is not None:
                self.app.log(f"{self.title}: cannot save: {type(e).__name__}: {e}")
            return None
        self.unsaved = False
        return res

    def space_bar(self):
        """SPACE BAR in the "Edit: <name>" tab (owner, 2026-11-25): start / stop the sound
        of the copy being edited (from the bar clicked after one count-in bar, else from
        the cursor; as listen()). True = used."""
        v = self.view
        try:
            if v.timer.isActive():
                self.stop()
            else:
                self.listen()
        except Exception as e:
            if self.app is not None:
                self.app.log(f"{self.title}: {type(e).__name__}: {e}")
        return True

    def closing(self):
        """The tab is closed: a copy with edits not saved -> ask (Save as new / discard)."""
        self.stop()
        if self.on_save is None or not self.unsaved:
            return
        from PySide6.QtWidgets import QMessageBox
        a = QMessageBox.question(self.win.window(), "Edited",
                                 f"Save the edits of '{self.title}' as a new object?",
                                 QMessageBox.Save | QMessageBox.Discard, QMessageBox.Save)
        if a == QMessageBox.Save:
            self.save_new()

    # ---------------------------------------------------------- StaffView interface
    def make_bar(self):
        from .bar import action_bar
        if self._bar is None:
            self._bar, _ = action_bar(
                [("Stop", self.stop, "stop the sound"),
                 ("Zoom +", lambda: self.view.zoom(1.25)),
                 ("Zoom -", lambda: self.view.zoom(0.8)),
                 ("Line/Page", lambda: self.staff.toggle_layout(), "staff on one line / in pages"),
                 None,
                 ("Edit", self.toggle, "edit the MIDI in the piano roll; again: back to "
                                       "the staff")]
                + ([("Save as new", self.save_new, "the edited copy becomes a NEW object in "
                                                   "Objects (the original stays as it is)")]
                   if self.on_save is not None else []),
                right=self.status)
            self._update_bar()
        return self._bar

    def set_position(self, beat):
        self.view.set_position(beat)
        return self

    def listen(self, start=None, count_in=None):
        return self.view.listen(start, count_in)

    @property
    def from_q(self):
        """The bar clicked in the view shown (None: never): Play begins there."""
        return self.view.from_q

    @property
    def on_double_click(self):
        return self._on_double_click

    @on_double_click.setter
    def on_double_click(self, fn):
        """Double click on a bar (staff, or bar numbers of the piano roll): fn(q)."""
        self._on_double_click = fn
        for v in (self.staff, self.roll):
            if v is not None:
                v.on_double_click = fn

    def stop(self):
        for v in (self.staff, self.roll):
            if v is not None:
                v.stop()
        return self

    @property
    def on_end(self):
        return self._on_end

    @on_end.setter
    def on_end(self, fn):
        """Called when the music reaches its end (Play in Objects: the loop); given to the
        staff AND the piano roll, which play by themselves."""
        self._on_end = fn
        for v in (self.staff, self.roll):
            if v is not None:
                v.on_end = fn

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, on):
        """Play in a loop: given to the staff and the piano roll."""
        self._loop = bool(on)
        for v in (self.staff, self.roll):
            if v is not None:
                v.loop = self._loop

    @property
    def timer(self):
        return self.view.timer

    @property
    def position(self):
        return self.view.position
