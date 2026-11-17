"""
StaffView: window that draws a Score (Qt, PySide6), the Python counterpart of
the MATLAB `pentagramma` / `notes.staff`:

  1. draws the engraved score (Verovio), on one long line ('line', default)
     or wrapped in systems ('page');
  2. moves a cursor along the score in time (play: count-in, metronome
     clicks, optionally the music itself), scrolling to keep it in view;
  3. colours notes (e.g. wrong notes in red after an evaluation).

Works from a script / command line (`view.run()` starts the Qt loop) and
from Jupyter (`show()` switches on the Qt event loop, like `%gui qt`):

    v = StaffView(score).show()
    v.set_position(9.5)                   # cursor at beat 9.5 (quarters from the start)
    v.play(bpm=90, count_in=1, click=True, music=False)   # real time (FluidSynth)
    v.mark_errors([3, 7, 12])             # rows of score.table() in red
    v.mark({5: 'green'}); v.clear_marks()
    v.snapshot('view.jpg')                # JPEG quality 95 by default

Rows are the row numbers of `score.table()` (notes and rests).
"""
import os
import re
import tempfile
import time
import xml.etree.ElementTree as ET

import numpy as np

from .engrave import _unwrap, _flatten_texts

_TR = re.compile(r'translate\(\s*([-\d.eE]+)[\s,]+([-\d.eE]+)')
_LINE = re.compile(r'M\s*([-\d.]+)\s+([-\d.]+)\s+L\s*([-\d.]+)\s+([-\d.]+)')
_SVG = "{http://www.w3.org/2000/svg}"


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _enable_notebook_loop():
    try:
        ip = get_ipython()                          # noqa: F821
    except NameError:
        return False
    if ip.__class__.__name__ == "ZMQInteractiveShell":
        ip.enable_gui("qt")
        return True
    return False


def _classes(el):
    return (el.get("class") or "").split()


# ---------------------------------------------------------------- engraving + geometry
class _Layout:
    """Verovio rendering of the score plus the geometry needed by the view."""

    def __init__(self, score, layout, scale, width):
        import verovio
        fd, xml = tempfile.mkstemp(suffix=".musicxml")
        os.close(fd)
        try:
            score.m21.write("musicxml", fp=xml)
            tk = verovio.toolkit()
            opts = {"scale": scale, "footer": "none", "adjustPageHeight": True}
            if layout == "line":
                opts.update(breaks="none", adjustPageWidth=True, header="none")
            else:
                opts.update(breaks="auto", pageWidth=width, pageHeight=60000, header="auto")
            tk.setOptions(opts)
            if not tk.loadFile(xml):
                raise RuntimeError("Verovio could not read the score")
        finally:
            os.remove(xml)
        self.raw = tk.renderToSVG(1)
        tm = tk.renderToTimemap({"includeRests": True, "includeMeasures": True})
        self.tq = np.array([[e["tstamp"], e["qstamp"]] for e in tm], dtype=float)
        root = ET.fromstring(self.raw)
        self.width_px = float(root.get("width", "0").replace("px", ""))
        self.height_px = float(root.get("height", "0").replace("px", ""))
        inner = next(e for e in root.iter(f"{_SVG}svg") if "definition-scale" in _classes(e))
        vb = [float(v) for v in inner.get("viewBox").split()]
        self.k = self.width_px / vb[2]               # scene pixels per Verovio unit
        self.elems = {}                              # id -> dict(cls, system, staff, x, y)
        self.systems = {}                            # system -> [xmin, xmax, ymin, ymax]
        self.measures = {}                           # id -> dict(system, x0, x1, order)
        self._meas = None                            # measure being walked
        self._nsys = -1
        self._walk(inner, 0.0, 0.0, 0, -1)
        # onset (quarters) of every note/rest
        onset = {}
        for e in tm:
            for i in e.get("on", []) + e.get("restsOn", []):
                onset.setdefault(i, e["qstamp"])
        self.notes = {}                              # (staff, q, pitch|None) -> [ids]
        for i, el in self.elems.items():
            if el["cls"] == "note":
                mv = tk.getMIDIValuesForElement(i)
                q = onset.get(i, self.ms_to_q(mv.get("time", 0)))
                key = (el["staff"], round(float(q), 3), int(mv.get("pitch", -1)))
            else:
                if i not in onset:
                    continue
                key = (el["staff"], round(float(onset[i]), 3), None)
            el["q"] = key[1]
            self.notes.setdefault(key, []).append(i)
        # cursor anchors: one per onset time, at the leftmost note/rest
        anchors = {}
        for el in self.elems.values():
            if "q" in el:
                a = anchors.get(el["q"])
                if a is None or el["x"] < a[0]:
                    anchors[el["q"]] = (el["x"], el["system"])
        self.anchors = sorted((q, x, s) for q, (x, s) in anchors.items())
        # BAR anchors (owner, 2026-11-15, Settings "Cursor": 2 = bars): one per bar at its
        # start (the bar line before it; the first bar of a system: its first note / rest,
        # after clef and key), at the downbeat: the cursor goes at constant speed from one
        # bar line to the next
        meas_q = {}
        for e in tm:
            mo = e.get("measureOn")
            for i in (mo if isinstance(mo, list) else [mo] if mo else []):
                meas_q.setdefault(i, e["qstamp"])
        first_x = {}
        for el in self.elems.values():
            m = el.get("measure")
            if m is not None:
                first_x[m] = min(first_x.get(m, np.inf), el["x"])
        bars, seen = [], set()
        for mid, m in sorted(self.measures.items(), key=lambda kv: kv[1]["order"]):
            if mid not in meas_q or not np.isfinite(m["x0"]):
                continue
            x = m["x0"]
            if m["system"] not in seen:                  # first bar of the system
                x = first_x.get(mid, x) if np.isfinite(first_x.get(mid, np.inf)) else x
                seen.add(m["system"])
            bars.append((float(meas_q[mid]), x, m["system"]))
        self.bar_anchors = sorted(bars)

    def ms_to_q(self, ms):
        if len(self.tq) < 2:
            return 0.0
        return float(np.interp(ms, self.tq[:, 0], self.tq[:, 1]))

    def _walk(self, el, tx, ty, system, staff):
        m = _TR.search(el.get("transform") or "")
        if m and el.tag != f"{_SVG}use":
            tx, ty = tx + float(m.group(1)), ty + float(m.group(2))
        cls = _classes(el)
        if "system" in cls:
            self._nsys += 1
            system = self._nsys
            self.systems[system] = [np.inf, -np.inf, np.inf, -np.inf]
        if "staff" in cls and el.tag == f"{_SVG}g":
            self._staff_lines(el, tx, ty, system)
        if ("note" in cls or "rest" in cls or "mRest" in cls) and el.get("id"):
            use = next(el.iter(f"{_SVG}use"), None)
            mu = _TR.search(use.get("transform") or "") if use is not None else None
            if mu:
                self.elems[el.get("id")] = dict(cls="note" if "note" in cls else "rest",
                                                system=system, staff=staff,
                                                x=(tx + float(mu.group(1))) * self.k,
                                                y=(ty + float(mu.group(2))) * self.k,
                                                measure=self._meas)
            return
        if "measure" in cls:                      # staves of a measure: one per part, in order
            prev = self._meas
            self._meas = el.get("id")
            if self._meas:
                self.measures[self._meas] = dict(system=system, x0=np.inf, x1=-np.inf,
                                                 order=len(self.measures))
            k = 0
            for ch in el:
                if "staff" in _classes(ch):
                    self._walk(ch, tx, ty, system, k)
                    k += 1
                else:
                    self._walk(ch, tx, ty, system, staff)
            self._meas = prev
            return
        for ch in el:
            self._walk(ch, tx, ty, system, staff)

    def _staff_lines(self, g, tx, ty, system):
        b = self.systems.setdefault(system, [np.inf, -np.inf, np.inf, -np.inf])
        for p in g.findall(f"{_SVG}path"):
            m = _LINE.match(p.get("d") or "")
            if m and m.group(2) == m.group(4):
                x1, y, x2 = float(m.group(1)), float(m.group(2)), float(m.group(3))
                b[0] = min(b[0], (tx + x1) * self.k)
                b[1] = max(b[1], (tx + x2) * self.k)
                m = self.measures.get(self._meas)
                if m is not None:                    # staff lines are drawn bar by bar
                    m["x0"] = min(m["x0"], (tx + x1) * self.k)
                    m["x1"] = max(m["x1"], (tx + x2) * self.k)
                b[2] = min(b[2], (ty + y) * self.k)
                b[3] = max(b[3], (ty + y) * self.k)

    def svg(self, colors):
        """SVG ready for QtSvg, with the given element colours {id: colour}."""
        s = self.raw
        for i, c in colors.items():
            s = re.sub(rf'(<g id="{re.escape(i)}" class="(?:note|rest)")',
                       rf'\1 fill="{c}" color="{c}" stroke="{c}"', s, count=1)
        return _flatten_texts(_unwrap(s), note="\u2669")       # "♩ = 120" on screen


CURSOR_MODES = {"notes": "1 = notes (on every note / rest)",
                "bars": "2 = bars (bar line to bar line, constant speed)"}


def cursor_mode():
    """'notes' (default) or 'bars': settings key 'cursor_mode' of the current user."""
    try:
        from .progress import settings
        m = settings().get("cursor_mode", "notes")
    except Exception:
        m = "notes"
    return m if m in CURSOR_MODES else "notes"


# ---------------------------------------------------------------- the view
def _ClickFilter(view):
    """Event filter of the staff viewport: a left click -> StaffView.clicked(scene x, y)."""
    from PySide6.QtCore import QObject, QEvent, Qt

    class F(QObject):
        def eventFilter(self, obj, e):
            if e.type() == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                p = view.view.mapToScene(e.position().toPoint())
                view.clicked(p.x(), p.y())
            return False
    return F()


class StaffView:
    def __init__(self, score, layout="line", scale=40, width=2100, title=None):
        from .score import Score
        from .midi import Midi
        self.midi = None                       # the original MIDI, if built from one
        if isinstance(score, Midi):
            self.midi = score
            score = score.to_score()
        if not isinstance(score, Score):
            raise TypeError("StaffView needs a Score (or a Midi object)")
        self.score = score
        self.layout_mode = layout
        self.scale = scale
        self.width = width
        self.title = title or score.title or "StaffView"
        self.colors = {}                       # table row -> colour
        self.position = 0.0
        self.bpm = None
        self.bpm_default = None                # tempo used by the Play button (None: score tempo)
        self.lead = 0.0                        # count-in duration (s)
        self.tempo_pm = None                   # pretty_midi whose TEMPO MAP the cursor and
        self.speed = 1.0                       # the clicks follow (Play over MIDI), × speed
        self.q_offset = 0.0                    # where beat 0 of the score is in tempo_pm
        self._rows = self._row_keys()
        self.end_q = float(score.m21.highestTime)
        _app()
        self._build_window()
        self._render()

    # ---------------------------------------------------------- rows <-> Verovio ids
    def _row_keys(self):
        """For every row of score.table(): (staff, start, pitch|None)."""
        keys = []
        for ip in range(len(self.score.m21.parts)):
            t = self.score.table(part=ip)
            for r in t.itertuples():
                p = None if r.pitch is None or str(r.pitch) == "<NA>" else int(r.pitch)
                keys.append((ip, round(float(r.start), 3), p))
        return keys

    def _ids_for_row(self, row):
        key = self._rows[row]
        ids = self.lay.notes.get(key)
        if ids is None and key[2] is not None:          # tolerate tiny onset differences
            for (s, q, p), v in self.lay.notes.items():
                if s == key[0] and p == key[2] and abs(q - key[1]) < 0.02:
                    return v
        return ids or []

    # ---------------------------------------------------------- window
    def _build_window(self):
        from PySide6.QtWidgets import (QMainWindow, QGraphicsView, QGraphicsScene, QToolBar,
                                       QLabel)
        from PySide6.QtGui import QAction, QPainter, QColor, QFont
        from PySide6.QtCore import QTimer
        self.win = QMainWindow()
        self.win.setWindowTitle(self.title)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.setBackgroundBrush(QColor("white"))
        self.win.setCentralWidget(self.view)
        tb = self.toolbar = QToolBar()
        self.win.addToolBar(tb)
        for text, fn in self.bar_actions():
            a = QAction(text, self.win)
            a.triggered.connect(fn)
            tb.addAction(a)
        self._bar = None
        self.status = QLabel("")
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)
        self.status.setFont(mono)                  # fixed width: the numbers do not shift the text
        self.win.statusBar().addWidget(self.status)
        self.timer = QTimer()
        self.timer.setInterval(25)
        self.timer.timeout.connect(self._tick)
        self._clicks = _ClickFilter(self)               # click on the staff: cursor + bar
        self.view.viewport().installEventFilter(self._clicks)
        self.on_position = None                          # f(beat, bar) after every move
        self.on_beat = None              # f(n, of) when the beat of the bar changes (Click button)
        self.click_audible = True        # metronome events heard (set_click: also while playing)
        self.win.resize(1200, 360 if self.layout_mode == "line" else 800)
        self.player = None

    def _render(self):
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtSvgWidgets import QGraphicsSvgItem
        from PySide6.QtWidgets import QGraphicsLineItem
        from PySide6.QtGui import QPen, QColor
        from PySide6.QtCore import QByteArray, Qt
        self.lay = _Layout(self.score, self.layout_mode, self.scale, self.width)
        idcol = {}
        for row, c in self.colors.items():
            for i in self._ids_for_row(row):
                idcol[i] = c
        self.scene.clear()
        self.renderer = QSvgRenderer(QByteArray(self.lay.svg(idcol).encode()))
        item = QGraphicsSvgItem()
        item.setSharedRenderer(self.renderer)
        self.scene.addItem(item)
        self.scene.setSceneRect(0, 0, self.lay.width_px, self.lay.height_px)
        pen = QPen(QColor(220, 0, 0))
        pen.setWidthF(2.0)
        pen.setStyle(Qt.DashLine)
        self.cursor = QGraphicsLineItem()
        self.cursor.setPen(pen)
        self.cursor.setZValue(10)
        self.scene.addItem(self.cursor)
        self.set_position(self.position)

    # ---------------------------------------------------------- actions (toolbar / main-window bar)
    def bar_actions(self, play=True):
        """(text, function). play=True (stand-alone window, e.g. `musictools view`): Play =
        listen with the cursor following, Rewind. In the main window (play=False) the
        tab has NO Play: owner's rule, Play is only in the Objects panel (listening),
        the central panel has Start only in exercises (practice)."""
        acts = (("Play", self.listen),) if play else ()
        acts += (("Stop", self.stop),)
        if play:
            acts += (("Rewind", lambda: self.set_position(0)),)
        return acts + (("Zoom +", lambda: self.zoom(1.25)), ("Zoom -", lambda: self.zoom(0.8)),
                       ("Line/Page", self.toggle_layout))

    def listen(self):
        """Play the score (music, no count-in, no clicks) from the cursor position."""
        return self.play(bpm=self.bpm_default, count_in=0, click=False, music=True)

    def hide_toolbar(self):
        """Embedded in another window: its own small toolbar is not shown."""
        self.toolbar.hide()
        return self

    def make_bar(self):
        """Big-button bar for the main window (same actions as the toolbar)."""
        from .gui.bar import action_bar
        if self._bar is None:
            self._bar, _ = action_bar([(t, fn) for t, fn in self.bar_actions(play=False)],
                                      right=self.status)
            self.win.statusBar().hide()           # beat / bar now at the right of the bar
        return self._bar

    def __repr__(self):
        return (f"StaffView('{self.title}', {self.layout_mode}, beat {self.position:.2f}, "
                f"{len(self.colors)} marked)")

    # ---------------------------------------------------------- public API
    def show(self):
        _enable_notebook_loop()
        self.win.show()
        self.win.raise_()
        return self

    def run(self):
        """Show and run the Qt loop until the window is closed (scripts, command line)."""
        self.win.show()
        _app().exec()
        return self

    def close(self):
        self.stop()
        self.win.close()

    def zoom(self, f):
        self.view.scale(f, f)
        self.set_position(self.position)
        return self

    def toggle_layout(self):
        self.layout_mode = "page" if self.layout_mode == "line" else "line"
        self.view.resetTransform()
        self._render()
        return self

    def _anchors(self):
        """Cursor anchors of the mode chosen in Settings > Exercises "Cursor" (owner,
        2026-11-15): 'notes' (default) = on every note / rest when it starts; 'bars' = on
        the bar lines at the downbeats, constant speed inside the bar."""
        if cursor_mode() == "bars" and getattr(self.lay, "bar_anchors", None):
            return self.lay.bar_anchors
        return self.lay.anchors

    def cursor_xy(self, beat):
        """Scene coordinates (x, y_top, y_bottom) of the cursor at a beat."""
        a = self._anchors()
        if not a:
            return 0.0, 0.0, self.lay.height_px
        qs = [v[0] for v in a]
        i = int(np.searchsorted(qs, beat, side="right")) - 1
        if i < 0:
            q, x, s = a[0]
            frac_x = x
        else:
            q, x, s = a[i]
            if i + 1 < len(a):
                q2, x2, s2 = a[i + 1]
                if s2 != s:
                    x2, q2 = self.lay.systems[s][1], q2
            else:
                q2, x2 = self.end_q, self.lay.systems[s][1]
            f = 0.0 if q2 <= q else min(1.0, max(0.0, (beat - q) / (q2 - q)))
            frac_x = x + f * (x2 - x)
        b = self.lay.systems.get(s, [0, 0, 0, self.lay.height_px])
        pad = 0.6 * (b[3] - b[2]) / max(1, len(self.score.m21.parts) * 4) + 10
        return frac_x, b[2] - pad, b[3] + pad

    def set_position(self, beat):
        """Move the cursor to a beat (quarter notes from the start) and scroll to it."""
        self.position = float(beat)
        x, y0, y1 = self.cursor_xy(self.position)
        self.cursor.setLine(x + 4, y0, x + 4, y1)
        vp = self.view.viewport().rect()
        sc = self.view.transform().m11()
        if self.layout_mode == "line":
            # keep the cursor at about one third of the window, as in the MATLAB version
            cx = x + (vp.width() / sc) * (0.5 - 0.33)
            self.view.centerOn(cx, (y0 + y1) / 2)
        else:
            self.view.ensureVisible(x - 50, y0, 100, y1 - y0, 50, 50)
        m = self._measure_at(self.position)
        self.status.setText(f"beat {self.position:7.2f}   bar {m:4d}")
        if callable(self.on_position):
            self.on_position(self.position, m)
        return self

    def _measure_at(self, beat):
        """Number of the bar at a beat: the score's own measure numbers (an excerpt keeps the
        original ones), else counted from the time signature."""
        ms = getattr(self, "_bars", None)
        if ms is None:
            ms = []
            try:
                for m in self.score.m21.parts[0].getElementsByClass("Measure"):
                    ms.append((float(m.offset), int(m.number)))
            except Exception:
                ms = []
            self._bars = ms
        if ms:
            n = ms[0][1]
            for off, num in ms:
                if off <= beat + 1e-6:
                    n = num
                else:
                    break
            return n
        ts = self.score.time_signature().split("/")
        per_bar = float(ts[0]) * 4.0 / float(ts[1])
        return int(beat // per_bar) + 1

    def beat_at(self, x, y):
        """Beat (quarters) under a point of the scene: the system nearest to y, then between
        the cursor anchors of that system."""
        sysb = self.lay.systems
        if not sysb or not self._anchors():
            return 0.0
        s = min(sysb, key=lambda k: 0 if sysb[k][2] - 30 <= y <= sysb[k][3] + 30 else
                min(abs(y - sysb[k][2]), abs(y - sysb[k][3])))
        a = [(q, ax) for q, ax, sy in self._anchors() if sy == s]
        if not a:
            return 0.0
        if x <= a[0][1]:
            return a[0][0]
        for (q1, x1), (q2, x2) in zip(a, a[1:]):
            if x1 <= x <= x2:
                return q1 + (q2 - q1) * (x - x1) / max(1e-6, x2 - x1)
        return a[-1][0]

    def clicked(self, x, y):
        """A click on the staff (not while playing): the cursor goes there and the status
        says the bar (owner, 2026-11-08: "if I click on a bar it must tell me its number")."""
        if self.timer.isActive():
            return None
        beat = self.beat_at(x, y)
        self.set_position(beat)
        return self._measure_at(beat)

    def mark(self, rows, color="red"):
        """Colour rows of score.table(): list of rows, boolean array/Series of the
        table length, or a dict {row: colour}."""
        if isinstance(rows, dict):
            self.colors.update(rows)
        else:
            arr = np.asarray(rows)
            if arr.dtype == bool:
                if len(arr) != len(self._rows):
                    raise ValueError(f"boolean mask must have {len(self._rows)} elements (table rows)")
                rows = np.flatnonzero(arr)
            for r in rows:
                self.colors[int(r)] = color
        self._render()
        return self

    def mark_errors(self, rows):
        return self.mark(rows, "red")

    def clear_marks(self):
        self.colors = {}
        self._render()
        return self

    def snapshot(self, path, quality=95, factor=2.0):
        """Save the whole score with marks and cursor as an image (JPEG quality 95 by default)."""
        from PySide6.QtGui import QImage, QPainter, QColor
        from PySide6.QtCore import QRectF
        r = self.scene.sceneRect()
        img = QImage(int(r.width() * factor), int(r.height() * factor), QImage.Format_RGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        self.scene.render(p, QRectF(0, 0, img.width(), img.height()), r)
        p.end()
        path = os.path.expanduser(path)
        ok = img.save(path, None, quality)
        if not ok:
            raise RuntimeError(f"could not save {path}")
        print(f"written {path}")
        return self

    # ---------------------------------------------------------- play (real time)
    def timeline(self, bpm=None, start=0.0, count_in=1, click=True, music=False):
        """Real-time events for play(): (events, lead seconds, end seconds).
        Times in seconds from the first count-in click."""
        from .realtime import midi_events, click_events
        if self.tempo_pm is not None:
            return self._timeline_map(start, count_in, click, music)
        bpm = float(bpm or self.bpm_default or self.score.tempo() or 90)
        ts = self.score.time_signature().split("/")
        beats_bar, beat_q = int(ts[0]), 4.0 / float(ts[1])
        spq = 60.0 / bpm
        spb = beat_q * spq                                  # seconds per beat of the bar
        lead_beats = count_in * beats_bar if count_in else 0
        lead = lead_beats * spb
        body = max(0.0, self.end_q - start) * spq
        ev = []
        first = int(round(start / beat_q)) - lead_beats     # bar-beat index of the first click
        # the count-in is always heard (owner, 2026-11-17); the clicks after it can be
        # silenced live (Click button: CLICK_PROG events)
        ev += click_events(lead_beats, spb, beats_bar, first_beat=first, prog=0)
        if click:
            ev += click_events(int(np.ceil(body / spb - 1e-9)), spb, beats_bar,
                               first_beat=first + lead_beats, offset=lead)
        if music:
            m = self.midi if self.midi is not None else self.score.to_midi()
            src_bpm = m.tempo() or bpm
            ev += midi_events(m.pm, start=start * 60.0 / src_bpm, scale=src_bpm / bpm,
                              offset=lead)
        return ev, lead, lead + body

    # ---------------------------------------------------------- tempo map (Play over MIDI)
    def _sec(self, q):
        """Seconds of the tempo map at quarter q (before the speed)."""
        pm = self.tempo_pm
        return pm.tick_to_time(int(round((q + self.q_offset) * pm.resolution)))

    def _q(self, sec):
        pm = self.tempo_pm
        return pm.time_to_tick(sec) / float(pm.resolution) - self.q_offset

    def _timeline_map(self, start, count_in, click, music):
        """As timeline() but following the TEMPO MAP of `tempo_pm` (tempo changes of the MIDI)
        at `speed` (1 = the MIDI's tempo): count-in at the starting tempo, a click on every
        beat of the map, the music (self.midi) from `start`."""
        from .realtime import (midi_events, click_events, CLICK_ACCENT, CLICK_BEAT, CLICK_DUR,
                               DRUM_CH, CLICK_PROG)
        sp = max(0.05, float(self.speed))
        ts = self.score.time_signature().split("/")
        beats_bar, beat_q = int(ts[0]), 4.0 / float(ts[1])
        s0 = self._sec(start)
        spb0 = (self._sec(start + beat_q) - s0) / sp
        lead_beats = count_in * beats_bar if count_in else 0
        lead = lead_beats * spb0
        body = max(0.0, self._sec(self.end_q) - s0) / sp
        first = int(round(start / beat_q))
        # count-in always heard (owner, 2026-11-17: Click off = no clicks AFTER the count-in)
        ev = click_events(lead_beats, spb0, beats_bar, first_beat=first - lead_beats, prog=0)
        if click:
            b = 0
            while start + b * beat_q < self.end_q - 1e-6:
                t = lead + (self._sec(start + b * beat_q) - s0) / sp
                key = CLICK_ACCENT if (first + b) % beats_bar == 0 else CLICK_BEAT
                ev += [(t, True, DRUM_CH, key, 110, CLICK_PROG),
                       (t + CLICK_DUR, False, DRUM_CH, key, 0, CLICK_PROG)]
                b += 1
        if music and self.midi is not None:
            ev += midi_events(self.midi.pm, start=s0, scale=1.0 / sp, offset=lead)
        self.bpm = 60.0 / (spb0 / beat_q) if spb0 > 0 else 90.0
        return ev, lead, lead + body

    def play(self, bpm=None, start=None, count_in=1, click=True, music=False, sf2=None,
             sound=True):
        """Move the cursor in time from `start` (beat; default: current position)
        after `count_in` bars of clicks, with metronome clicks (click) and/or the
        score itself (music), synthesized in real time by FluidSynth with the
        soundfont (sf2, default: the one given to Midi.add_sf2). sound=False:
        silent, cursor only. Non-blocking."""
        from .midi import Midi
        from .realtime import get_player
        self.stop()
        start = self.position if start is None else float(start)
        self.bpm = float(bpm or self.bpm_default or self.score.tempo() or 90)
        self._start = start
        ev, self.lead, self._end_t = self.timeline(self.bpm, start, count_in, click, music)
        self.finished = False                  # True when the cursor reached the end
        self.player = None
        self._t0 = time.perf_counter() + 0.05
        if sound:
            sf2 = sf2 or Midi._default_sf2
            if sf2 is None:
                raise RuntimeError("no soundfont: give sf2= or use Midi.add_sf2(path) first")
            self.player = get_player(sf2)
            self.player.play(ev, mute_clicks=not self.click_audible)
        self.timer.start()
        return self

    def set_click(self, on):
        """Metronome clicks heard or silent, also while playing (the Click button)."""
        self.click_audible = bool(on)
        if self.player is not None and hasattr(self.player, "set_clicks_muted"):
            self.player.set_clicks_muted(not self.click_audible)
        return self

    # ---------------------------------------------------------- beat of the bar (Click button)
    def _meter(self):
        """[(offset q, beats in the bar, quarters per beat)] of every bar of the score (its
        time signatures: 6/8 = 6 beats of an eighth, as the clicks)."""
        m = getattr(self, "_meter_cache", None)
        if m is None:
            m = []
            try:
                last = None
                for meas in self.score.m21.parts[0].getElementsByClass("Measure"):
                    ts = meas.timeSignature or meas.getContextByClass("TimeSignature")
                    if ts is not None:
                        last = (int(ts.numerator), 4.0 / float(ts.denominator))
                    if last is None:
                        t = self.score.time_signature().split("/")
                        last = (int(t[0]), 4.0 / float(t[1]))
                    m.append((float(meas.offset), last[0], last[1]))
            except Exception:
                m = []
            self._meter_cache = m
        return m

    def beat_of_bar(self, beat):
        """(n, beats of the bar) at a position in quarters; n = 1 on the downbeat."""
        m = self._meter()
        if not m:
            t = self.score.time_signature().split("/")
            nb, bq = int(t[0]), 4.0 / float(t[1])
            per = nb * bq
            return int((beat % per) / bq + 1e-6) + 1, nb
        cur = m[0]
        for row in m:
            if row[0] <= beat + 1e-6:
                cur = row
            else:
                break
        off, nb, bq = cur
        if beat >= off + nb * bq:                       # after the last bar: go on counting
            beat = off + (beat - off) % (nb * bq)
        return max(1, min(nb, int((beat - off) / bq + 1e-6) + 1)), nb

    def _emit_beat(self, n, of=None):
        key = (n, of)
        if key == getattr(self, "_last_beat", None):
            return
        self._last_beat = key
        f = getattr(self, "on_beat", None)
        if callable(f):
            try:
                f(n, of)
            except Exception:
                pass

    @property
    def play_t0(self):
        """perf_counter instant at which the timeline starts being heard
        (first count-in click); add event times to get when they are heard."""
        if self.player is not None and self.player.t0 is not None:
            return self.player.t0 + self.player.latency
        return getattr(self, "_t0", None)

    def stop(self):
        if getattr(self, "timer", None) is not None:
            self.timer.stop()
        self._emit_beat(None)
        if getattr(self, "player", None) is not None:
            self.player.stop()
        return self

    def _elapsed(self):
        """Seconds of the timeline already heard."""
        if self.player is not None:
            return self.player.elapsed()
        return time.perf_counter() - self._t0

    def _tick(self):
        t = self._elapsed()
        spb = 60.0 / self.bpm
        if t < self.lead:
            self.set_position(self._start)
            self.status.setText(f"count-in {max(0, int(t / spb)) + 1:2d}            ")
            if t < 0:                                  # before the count-in (Listen & repeat:
                self._emit_beat(None)                  # the phrase to repeat)
            else:
                nb = self.beat_of_bar(self._start)[1]  # the count-in bar: beats of the first
                self._emit_beat(min(nb, int(t / (self.lead / nb) + 1e-6) + 1), nb)
            return
        if self.tempo_pm is not None:
            beat = self._q(self._sec(self._start) + (t - self.lead) * self.speed)
        else:
            beat = self._start + (t - self.lead) / spb
        if beat >= self.end_q:
            self.set_position(self.end_q)
            self.stop()
            self.finished = True
            if callable(getattr(self, "on_end", None)):
                self.on_end()
            return
        self.set_position(beat)
        self._emit_beat(*self.beat_of_bar(beat))
