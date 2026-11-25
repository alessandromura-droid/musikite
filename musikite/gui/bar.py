"""
Action bar of the main window: ONE bar at the top of the central area whose
buttons change with the current tab (a score view: Stop, Zoom +, Zoom -, Line/Page; an
exercise: Start/Stop, Again, Zoom +, Zoom -, Click + the pieces of that tab: ◀ ▶ in a
routine, New, bpm, input, Edit…), on one row or more when the width is not enough. Every tab widget that
has actions owns a `bar` widget built with action_bar(); the main window shows
the bar of the current tab.
"""
# BUTTONS AS LARGE AS THEIR TEXT, NEVER MORE; NO EMPTY SPACES BETWEEN THEM (owner,
# 2026-11-25): padding PAD_X / PAD_Y, the flow layout gives every push button the width of
# its text (`button_size`, also buttons made elsewhere, e.g. ◀ ▶ of a routine; the
# platform minimum width — macOS — is not used), BAR_SPACING between the widgets, no
# spacing items (None in action_bar is ignored).
PAD_X, PAD_Y = 8, 4
BAR_SPACING = 3
BAR_MARGIN = 3
BUTTON_FG = "white"
# the SECOND ROW (the piano roll's tools, visible only in Edit): same buttons, the row on a
# very light dark-blue pastel close to grey (owner, 2026-11-25)
EDIT_ROW_BG = "#5b6678"
# the FIRST ROW (every tab's bar: Stop, Zoom…; owner, 2026-11-25): warm taupe, the same
# distance from grey as EDIT_ROW_BG, another hue (not green / red = right / wrong, not the
# yellow / blue of the beats, not the blue of the Edit row); its labels white
MAIN_ROW_BG = "#786a5b"
# BUTTONS TINTED AS THEIR ROW (owner, 2026-11-25): taupe on the first row, Prussian blue on
# the Edit row, darker than the row so that the white text reads well:
# (normal, hover, pressed, checked, disabled background, disabled text)
MAIN_BUTTONS = ("#52473b", "#605446", "#3d342b", "#6e6152", "#6b6054", "#cfc6bb")
EDIT_BUTTONS = ("#33405a", "#3f4d69", "#262f43", "#4c5b78", "#56607a", "#c5ccd8")
BUTTON_BG = MAIN_BUTTONS[0]                 # (compatibility: the first row's buttons)


def button_style(colors, row):
    """Stylesheet of the push buttons of a row ('mainRow' / 'editRow')."""
    bg, hover, pressed, checked, dis_bg, dis_fg = colors
    return (f"#{row} QPushButton {{background: {bg}; color: {BUTTON_FG}; "
            f"border: 1px solid #2a2a2a; border-radius: 4px; padding: {PAD_Y}px {PAD_X}px;"
            f" min-width: 0px;}}"
            f"#{row} QPushButton:hover {{background: {hover};}}"
            f"#{row} QPushButton:pressed {{background: {pressed};}}"
            f"#{row} QPushButton:checked {{background: {checked}; border: 1px solid #e8e8e8;}}"
            f"#{row} QPushButton:disabled {{background: {dis_bg}; color: {dis_fg};}}")


BAR_STYLE = button_style(MAIN_BUTTONS, "mainRow")
EDIT_ROW_STYLE = (f"#editRow {{background: {EDIT_ROW_BG};}}"
                  "#editRow QLabel {color: white;}" + button_style(EDIT_BUTTONS, "editRow"))
MAIN_ROW_STYLE = (f"#mainRow {{background: {MAIN_ROW_BG};}}"
                  "#mainRow QLabel {color: white;}")


def button_size(b):
    """Size of a bar push button: its text + padding + border, never more (QSize); a
    button with a fixed width (e.g. the Click button) keeps it, with the same height;
    None for anything that is not a push button."""
    from PySide6.QtWidgets import QPushButton
    from PySide6.QtCore import QSize
    if not isinstance(b, QPushButton):
        return None
    fm = b.fontMetrics()
    if b.minimumWidth() == b.maximumWidth():
        return QSize(b.minimumWidth(), fm.height() + 2 * PAD_Y + 2)
    w = max(fm.horizontalAdvance(t) for t in (b.text() or " ").split("\n"))
    return QSize(w + 2 * PAD_X + 2 + 2, fm.height() + 2 * PAD_Y + 2)


def flow_layout_class():
    """A layout that puts its widgets in a ROW and goes on in a new row when the width is
    not enough (owner, 2026-11-20: the exercise bar on one or two rows depending on the
    width). Every row is centred vertically; hidden widgets take no room. Also
    insertWidget(i, w) / insertSpacing(i, n) / addSpacing(n), as a QHBoxLayout."""
    from PySide6.QtWidgets import QLayout, QWidgetItem, QWidget
    from PySide6.QtCore import Qt, QRect, QSize, QPoint

    class FlowLayout(QLayout):
        def __init__(self, parent=None, spacing=6):
            super().__init__(parent)
            self._items = []
            self._sp = spacing

        def addItem(self, item):
            self._items.append(item)

        def insertWidget(self, index, w):
            self.addChildWidget(w)
            n = len(self._items)
            i = n + 1 + index if index < 0 else index
            self._items.insert(max(0, min(i, n)), QWidgetItem(w))
            self.invalidate()

        def insertSpacing(self, index, size):
            sp = QWidget()
            sp.setFixedSize(int(size), 1)
            self.insertWidget(index, sp)

        def addSpacing(self, size):
            self.insertSpacing(len(self._items), size)

        def count(self):
            return len(self._items)

        def itemAt(self, i):
            return self._items[i] if 0 <= i < len(self._items) else None

        def takeAt(self, i):
            return self._items.pop(i) if 0 <= i < len(self._items) else None

        def expandingDirections(self):
            return Qt.Orientation(0)

        def hasHeightForWidth(self):
            return True

        def heightForWidth(self, width):
            return self._do(QRect(0, 0, width, 0), True)

        def setGeometry(self, rect):
            super().setGeometry(rect)
            self._do(rect, False)

        def _visible(self):
            return [it for it in self._items if not it.isEmpty()]

        @staticmethod
        def _hint(it):
            """Size of an item: a push button as large as its text (button_size)."""
            s = button_size(it.widget()) if it.widget() is not None else None
            return s if s is not None else it.sizeHint()

        def sizeHint(self):
            m = self.contentsMargins()
            its = self._visible()
            w = sum(self._hint(it).width() for it in its) + self._sp * max(0, len(its) - 1)
            h = max([self._hint(it).height() for it in its] or [0])
            return QSize(w + m.left() + m.right(), h + m.top() + m.bottom())

        def minimumSize(self):
            s = QSize()
            for it in self._visible():
                s = s.expandedTo(self._hint(it) if button_size(it.widget()) is not None
                                 else it.minimumSize())
            m = self.contentsMargins()
            return s + QSize(m.left() + m.right(), m.top() + m.bottom())

        def _do(self, rect, test):
            m = self.contentsMargins()
            r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
            rows, row, x = [], [], 0
            for it in self._visible():
                w = self._hint(it).width()
                if row and x + w > r.width():
                    rows.append(row)
                    row, x = [], 0
                row.append(it)
                x += w + self._sp
            if row:
                rows.append(row)
            y = r.y()
            for row in rows:
                h = max(self._hint(it).height() for it in row)
                if not test:
                    x = r.x()
                    for it in row:
                        sz = self._hint(it)
                        it.setGeometry(QRect(QPoint(x, y + (h - sz.height()) // 2), sz))
                        x += sz.width() + self._sp
                y += h + self._sp
            if rows:
                y -= self._sp
            return y - rect.y() + m.bottom()

    return FlowLayout


def action_bar(items, right=None, edit_row=False):
    """QWidget with buttons darker grey, each as large as its text.
    items: list of (text, callback, tooltip), None (ignored since 2026-11-25: no empty
    spaces between buttons) or a ready widget (e.g. the Click button, `click_button`, a
    spin box, a label); right: widget put at the end (e.g. a clock), right after the
    others. The widgets go on ONE ROW, or on more rows when the width is not enough
    (FlowLayout, owner, 2026-11-20). The row on MAIN_ROW_BG (taupe); edit_row=True: the
    second row of the piano roll (same buttons, the row on EDIT_ROW_BG). Returns
    (bar, {text: button})."""
    from PySide6.QtWidgets import QWidget, QPushButton
    from PySide6.QtCore import Qt
    bar = QWidget()
    bar.setObjectName("editRow" if edit_row else "mainRow")
    bar.setAttribute(Qt.WA_StyledBackground, True)
    bar.setStyleSheet(EDIT_ROW_STYLE if edit_row else BAR_STYLE + MAIN_ROW_STYLE)
    lay = flow_layout_class()(bar, BAR_SPACING)
    lay.setContentsMargins(BAR_MARGIN, BAR_MARGIN, BAR_MARGIN, BAR_MARGIN)
    buttons = {}
    for it in items:
        if it is None:
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
    if right is not None:
        lay.addWidget(right)
    bar.buttons = buttons
    return bar, buttons


def start_stop(button, start, stop, running):
    """ONE BUTTON START / STOP (owner, 2026-11-20: "Start becomes Stop, two buttons are
    almost never needed"): pressed, it calls stop() while running() is true, else start();
    its text follows running() (checked 4 times a second). Returns the button."""
    from PySide6.QtCore import QTimer

    def pressed():
        try:
            busy = bool(running())
        except Exception:
            busy = False
        (stop if busy else start)()
        sync()

    def sync():
        try:
            busy = bool(running())
            button.setText("Stop" if busy else "Start")
        except RuntimeError:                       # the button is gone
            timer.stop()
        except Exception:
            pass

    try:
        button.clicked.disconnect()
    except Exception:
        pass
    button.clicked.connect(lambda checked=False: pressed())
    button.setToolTip("start the exercise; while it runs: stop it")
    timer = QTimer(button)
    timer.setInterval(250)
    timer.timeout.connect(sync)
    timer.start()
    button._start_stop_timer = timer
    return button


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
            # as large as the other bar buttons (same padding PAD_X + border 1), fixed so
            # that "Click 12" does not move the bar
            self.setFixedWidth(fm.horizontalAdvance("Click 12") + 2 * PAD_X + 2 + 4)
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
                bg, fg, hover = MAIN_BUTTONS[0], "white", MAIN_BUTTONS[1]
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
                f"border-radius: 4px; padding: {PAD_Y}px {PAD_X}px;}}"
                f"QPushButton:hover {{background: {hover};}}"
                f"QPushButton:pressed {{background: {MAIN_BUTTONS[2]};}}")
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
            # ShowToParent / HideToParent too (2026-11-20): a box hidden and shown again
            # by code while its tab is not on screen gets no Show event, and its area,
            # once hidden, stayed hidden for ever (Make a variant missing in Read & play)
            if e.type() in (QEvent.Hide, QEvent.Show, QEvent.ShowToParent,
                            QEvent.HideToParent):
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
