"""
Action bar of the main window: ONE bar at the top of the central area whose
buttons change with the current tab (a score view: Play, Stop, Rewind, Zoom +,
Zoom -, Line/Page; an exercise: Start, Stop, Repeat, ...). Every tab widget that
has actions owns a `bar` widget built with action_bar(); the main window shows
the bar of the current tab.
"""
BAR_STYLE = ("QPushButton {background: #4a4a4a; color: white; border: 1px solid #333; "
             "border-radius: 4px; padding: 4px 14px;}"
             "QPushButton:hover {background: #5a5a5a;}"
             "QPushButton:pressed {background: #333;}"
             "QPushButton:disabled {background: #6e6e6e; color: #bbbbbb;}")


def action_bar(items, right=None):
    """QWidget with buttons as those of the Objects panel (same size), darker grey.
    items: list of (text, callback, tooltip), None (spacing) or a ready widget (e.g. the
    Click button, `click_button`); right: widget put at the right end (e.g. a clock).
    Returns (bar, {text: button})."""
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
    bar = QWidget()
    bar.setStyleSheet(BAR_STYLE)
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(4, 4, 4, 4)
    lay.setSpacing(6)
    buttons = {}
    for it in items:
        if it is None:
            lay.addSpacing(24)
            continue
        if not isinstance(it, (tuple, list)):          # a widget made by the caller
            lay.addWidget(it)
            continue
        text, fn, tip = (tuple(it) + ("",))[:3]
        b = QPushButton(text)
        if tip:
            b.setToolTip(tip)
        b.clicked.connect(lambda checked=False, fn=fn: fn())
        lay.addWidget(b)
        buttons[text] = b
    lay.addStretch(1)
    if right is not None:
        lay.addWidget(right)
    bar.buttons = buttons
    return bar, buttons


# CLICK BUTTON (owner, 2026-11-17): a visual metronome and the switch of the audio click in
# one button of the exercise bars, after Zoom + / Zoom -. While a take runs it shows
# "Click N" (N = the beat of the bar, also in the count-in) and its background changes
# colour at every click: the first beat of the bar RED, the others yellow, green, blue,
# then yellow again (any metre: 3/4 red-yellow-green, 6/8 counted in eighths as its
# clicks). Pressing it switches the audio click off / on, also during a take (the
# visual count goes on); off = the text struck through. It replaces the "Click" boxes.
BEAT_COLOURS = ("#c62828", "#f9a825", "#2e7d32", "#1565c0")   # beat 1, then 2, 3, 4, 2, 3…
_BEAT_TEXT = {"#f9a825": "black"}


def beat_colour(n):
    """Background of beat n (1 = the first of the bar)."""
    if n <= 1:
        return BEAT_COLOURS[0]
    return BEAT_COLOURS[1 + (n - 2) % (len(BEAT_COLOURS) - 1)]


def click_button(on=True, toggled=None):
    """The Click button (see BEAT_COLOURS): `on` = audio click heard; toggled(on) is
    called when it is pressed. Methods: set_on(on) (no call of toggled), show_beat(n)
    (n None = idle), `on`."""
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtCore import Qt

    class ClickButton(QPushButton):
        def __init__(self):
            super().__init__("Click")
            self.on = bool(on)
            self._beat = None
            self.toggled_fn = toggled
            self.setFocusPolicy(Qt.NoFocus)          # the space bar stays for the exercise
            fm = self.fontMetrics()
            # as large as the other bar buttons (same padding 14 + border 1), fixed so that
            # "Click 12" does not move the bar
            self.setFixedWidth(fm.horizontalAdvance("Click 12") + 2 * 14 + 2 + 4)
            self.clicked.connect(self._pressed)
            self._paint()

        def _pressed(self):
            self.on = not self.on
            self._paint()
            if callable(self.toggled_fn):
                self.toggled_fn(self.on)

        def set_on(self, value):
            self.on = bool(value)
            self._paint()
            return self

        def show_beat(self, n, of=None):
            n = None if n is None else int(n)
            if n == self._beat:
                return self
            self._beat = n
            self._paint()
            return self

        def _paint(self):
            n = self._beat
            if n is None:
                bg, fg, hover = "#4a4a4a", "white", "#5a5a5a"
                self.setText("Click")
            else:
                bg = beat_colour(n)
                fg = _BEAT_TEXT.get(bg, "white")
                hover = bg
                self.setText(f"Click {n}")
            if not self.on:
                fg = "#9a9a9a" if n is None else fg
            f = self.font()
            f.setStrikeOut(not self.on)
            self.setFont(f)
            self.setStyleSheet(
                f"QPushButton {{background: {bg}; color: {fg}; border: 1px solid #333; "
                f"border-radius: 4px; padding: 4px 14px;}}"
                f"QPushButton:hover {{background: {hover};}}"
                f"QPushButton:pressed {{background: #333;}}")
            self.setToolTip("audio click ON: press to switch it off (the count goes on)"
                            if self.on else
                            "audio click OFF: press to switch it on")

    return ClickButton()


def hscroll(w):
    """A settings box that NEVER makes its tab wider than the window (owner, 2026-11-08:
    with the Tools panel open the end of the staff was cut): the box in its own horizontal
    scroll area, as high as the box, no minimum width; it follows the box when the box is
    hidden / shown. Returns the area (add it to the layout instead of the box)."""
    from PySide6.QtWidgets import QScrollArea, QFrame, QSizePolicy
    from PySide6.QtCore import Qt, QSize, QEvent, QObject

    class HScroll(QScrollArea):
        def __init__(self):
            super().__init__()
            self.setWidget(w)
            self.setWidgetResizable(True)
            self.setFrameShape(QFrame.NoFrame)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.watch = Watch(self)
            w.installEventFilter(self.watch)
            self.setVisible(not w.isHidden())

        def _h(self):
            h = w.sizeHint().height()
            if w.minimumSizeHint().width() > self.viewport().width():
                h += self.horizontalScrollBar().sizeHint().height()
            return h

        def sizeHint(self):
            return QSize(w.sizeHint().width(), self._h())

        def minimumSizeHint(self):
            return QSize(40, self._h())

        def resizeEvent(self, e):
            super().resizeEvent(e)
            if self.height() != self._h():
                self.updateGeometry()

    class Watch(QObject):
        def eventFilter(self, obj, e):
            area = self.parent()
            if e.type() in (QEvent.Hide, QEvent.Show):
                if area.isHidden() != w.isHidden():
                    area.setVisible(not w.isHidden())
                area.updateGeometry()
            elif e.type() == QEvent.LayoutRequest:
                area.updateGeometry()
            return False

    return HScroll()


def tabs_class():
    """The tabs of the main window (a real QTabWidget: the look of the system, current
    tab highlighted). Every page is the tool / view widget with its action bar
    (widget.bar) on top: changing tab changes the available buttons. Same API as
    QTabWidget for the original widgets (the wrapper pages stay hidden).

    CLOSE ALL (owner's rule): as soon as there is more than one tab, a last tab "Close all"
    is added; clicking it closes every tab (`on_close_all()`, the main window's
    close_all: each tab is closed as with its own close button). It is not counted by
    count(), never becomes the current tab by itself and has no close button.

    THE WINDOW NEVER RESIZES ITSELF (owner, 2026-11-08): every page is inside a scroll area,
    so content wider / taller than the space gets scroll bars instead of enlarging the main
    window (which also kept the panel dividers from moving); the action bar may be cut."""
    from PySide6.QtWidgets import (QTabWidget, QWidget, QVBoxLayout, QTabBar, QScrollArea,
                                   QFrame, QSizePolicy)
    from PySide6.QtCore import QTimer

    class Tabs(QTabWidget):
        def __init__(self):
            super().__init__()
            self._page = {}                            # widget -> wrapper page
            self._close_page = None                    # the "Close all" tab (or None)
            self._prev = 0                             # last real current tab
            self.on_close_all = None
            self.tabBar().tabBarClicked.connect(self._clicked)
            self.tabBar().setAcceptDrops(True)         # a drag held over a tab opens it
            self.tabBar().setChangeCurrentOnDrag(True)  # (e.g. an exercise to a routine)
            self.currentChanged.connect(self._guard)

        # ---------------------------------------------- "Close all"
        def _ci(self):
            p = self._close_page
            return QTabWidget.indexOf(self, p) if p is not None else -1

        def count(self):
            n = QTabWidget.count(self)
            return n - 1 if self._ci() >= 0 else n

        def _update_close(self):
            n, ci = self.count(), self._ci()
            if n > 1 and ci < 0:
                page = self._close_page = QWidget()
                i = QTabWidget.addTab(self, page, "Close all")
                self.setTabToolTip(i, "close all the open tabs")
                for side in (QTabBar.LeftSide, QTabBar.RightSide):
                    self.tabBar().setTabButton(i, side, None)
            elif n <= 1 and ci >= 0:
                page, self._close_page = self._close_page, None
                QTabWidget.removeTab(self, ci)
                page.deleteLater()

        def _clicked(self, i):
            if i >= 0 and i == self._ci():
                QTimer.singleShot(0, self._close_all)

        def _close_all(self):
            if self.on_close_all is not None:
                self.on_close_all()
            else:
                while self.count():
                    self.removeTab(self.count() - 1)

        def _guard(self, i):
            """The "Close all" tab never stays current (clicked or reached by closing)."""
            if i >= 0 and i == self._ci():
                if self.count():
                    self.setCurrentIndex(max(0, min(self._prev, self.count() - 1)))
            elif i >= 0:
                self._prev = i

        def _wrap(self, w):
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)
            bar = getattr(w, "bar", None)
            if bar is not None:
                _no_min_width(bar)
                lay.addWidget(bar)
            area = QScrollArea()                       # never enlarges the window
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            area.setWidget(w)
            lay.addWidget(area, 1)
            page.inner = w
            page.area = area
            self._page[w] = page
            return page

        def addTab(self, w, title):
            i = super().insertTab(self.count(), self._wrap(w), title)   # before "Close all"
            self._update_close()
            return i

        def _inner(self, page):
            return getattr(page, "inner", page) if page is not None else None

        def widget(self, i):
            return self._inner(super().widget(i))

        def currentWidget(self):
            return self._inner(super().currentWidget())

        def indexOf(self, w):
            page = self._page.get(w)
            return super().indexOf(page) if page is not None else -1

        def setCurrentWidget(self, w):
            i = self.indexOf(w)
            if i >= 0:
                self.setCurrentIndex(i)

        def removeTab(self, i):
            page = super().widget(i)
            super().removeTab(i)
            w = getattr(page, "inner", None)
            if w is not None:
                self._page.pop(w, None)
            self._update_close()

        def set_bar(self, widget, bar):
            """Replace the action bar of a page (a view now showing another object)."""
            page = self._page.get(widget)
            old = getattr(widget, "bar", None)
            widget.bar = bar
            if page is None:
                return
            lay = page.layout()
            if old is not None and old is not bar:
                lay.removeWidget(old)
                old.setParent(None)
            if bar is not None and lay.indexOf(bar) < 0:
                _no_min_width(bar)
                lay.insertWidget(0, bar)

        def _show_bar(self):                          # compatibility (bars live in the pages)
            pass

    def _no_min_width(bar):
        """An action bar never imposes its width on the window (buttons may be cut)."""
        sp = bar.sizePolicy()
        sp.setHorizontalPolicy(QSizePolicy.Ignored)
        bar.setSizePolicy(sp)
        bar.setMinimumWidth(0)

    return Tabs
