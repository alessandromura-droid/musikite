"""
MidiView: the tab of a Midi object in the main window. It opens on the STAFF
(StaffView) and the button "Piano roll" switches to the piano roll (PianoRollView),
where the MIDI is edited exactly as a recording of the Free player (hand, pencil,
eraser, Quantize…, undo). The edits go into the Midi object itself (Objects > Save
writes them; Play plays them); back on "Staff" the staff is engraved again.

Same interface as StaffView for the main window: win, make_bar(), set_position(),
listen(), stop(), timer, obj_name.
"""


class MidiView:
    def __init__(self, midi, title, app=None):
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
            self._staff_old = False
        self.stack.setCurrentWidget(self.staff.win)
        self.mode = "staff"

    def _show_roll(self):
        from ..pianorollview import PianoRollView
        if self.roll is None:
            self.roll = self._embed(PianoRollView(self.midi, title=self.title,
                                                  on_change=self._edited))
        self.stack.setCurrentWidget(self.roll.win)
        self.roll.set_position(self.roll.position)
        self.mode = "roll"

    def _edited(self, roll):
        self._staff_old = True
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
        if self._bar is not None:
            b = self._bar.buttons
            b["Piano roll"].setText("Staff" if self.mode == "roll" else "Piano roll")
            b["Line/Page"].setEnabled(self.mode == "staff")
        return self

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
                 ("Piano roll", self.toggle, "switch between staff and piano roll (where the "
                                             "MIDI is edited)")],
                right=self.status)
        return self._bar

    def set_position(self, beat):
        self.view.set_position(beat)
        return self

    def listen(self):
        return self.view.listen()

    def stop(self):
        for v in (self.staff, self.roll):
            if v is not None:
                v.stop()
        return self

    @property
    def timer(self):
        return self.view.timer

    @property
    def position(self):
        return self.view.position
