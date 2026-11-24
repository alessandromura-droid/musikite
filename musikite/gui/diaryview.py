"""
Analyse > Practice diary: the results day by day (data: diary.Diary, no Qt there).

Charts (one at a time, "Chart"):
  Calendar   one cell per day (columns = weeks, Monday on top), colour chosen in
             "Colour": time studied, mean grade, or mean grade of one exercise type;
             today outlined; current and longest streak in the bar
  Candles    "stock exchange" chart of the grades of one exercise type (or all):
             one candle per day with practice: open = first attempt, close = last,
             high = best, low = worst (green: closed higher than it opened); dot =
             mean grade of the day (best of each exercise)
  Trend      mean grade of the day (dots), min–max band, moving mean over 7 days (line)
  Weekly     minutes per week, stacked by exercise type
Click on a day (calendar, candles, trend) = its summary on the right: minutes,
exercises with the grade of the day (best attempt) and number of attempts, mean per
type; frozen days are marked so.
"""
import datetime as _dt

from . import registry

KIND_COLORS = {"intervals": "#7b1fa2", "interval_reading": "#1565c0",
               "play_reading": "#ef6c00", "listen_repeat": "#2e7d32",
               "long_tones": "#00838f", "scales": "#c62828", "lip_slurs": "#6d4c41",
               "rhythm": "#f9a825", "free_player": "#607d8b", "chords": "#ad1457",
               "flashcards": "#3949ab", "chord_arpeggios": "#558b2f",
               "improvisation": "#9e9d24", "play_along": "#00695c",
               "scale_ear": "#d84315", "scale_degrees": "#0277bd", "cadences": "#8e24aa"}
EMPTY = "#ebedf0"


def _grade_color(g):
    """0 red -> 5 yellow -> 10 green."""
    from PySide6.QtGui import QColor
    g = max(0.0, min(10.0, float(g)))
    if g < 5:
        f = g / 5.0
        return QColor(int(215 + (240 - 215) * f), int(48 + (200 - 48) * f), int(39 + (40 - 39) * f))
    f = (g - 5) / 5.0
    return QColor(int(240 + (39 - 240) * f), int(200 + (160 - 200) * f), int(40 + (70 - 40) * f))


def _time_color(minutes, top):
    from PySide6.QtGui import QColor
    f = max(0.0, min(1.0, minutes / max(1.0, top)))
    a, b = (227, 242, 253), (13, 71, 161)
    return QColor(*(int(a[i] + (b[i] - a[i]) * (0.15 + 0.85 * f)) for i in range(3)))


def _widget_class():
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                                   QTextBrowser, QSplitter, QToolTip)
    from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPolygonF
    from PySide6.QtCore import Qt, QRectF, QPointF
    from .bar import action_bar
    from .. import diary as dy

    class Canvas(QWidget):
        def __init__(self, owner):
            super().__init__()
            self.o = owner
            self.setMouseTracking(True)
            self.setMinimumSize(420, 260)
            self.hits = []                   # (QRectF, day) of the last paint

        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.fillRect(self.rect(), QColor("white"))
            self.hits = []
            try:
                getattr(self, "_paint_" + self.o.chart())(p)
            except Exception as ex:                   # never a broken tab
                p.setPen(QColor("red"))
                p.drawText(20, 30, f"{type(ex).__name__}: {ex}")
            p.end()

        def _empty(self, p, text="Nothing practised yet"):
            p.setPen(QColor("#777"))
            p.drawText(self.rect(), Qt.AlignCenter, text)

        # -------------------------------------------------- calendar
        def _paint_calendar(self, p):
            metric, kind = self.o.colour()
            vals = self.o.d.calendar(metric, kind)
            today = _dt.date.fromisoformat(dy.day_of())
            first = min([_dt.date.fromisoformat(d) for d in vals] + [today])
            start = max(first, today - _dt.timedelta(weeks=52))
            start -= _dt.timedelta(days=start.weekday())                   # a Monday
            weeks = (today - start).days // 7 + 1
            W, H = self.width(), self.height()
            left, top = 34, 26
            cell = max(6.0, min(24.0, (W - left - 10) / weeks, (H - top - 60) / 7))
            gap = max(1.0, cell * 0.12)
            p.setFont(QFont("", 9))
            p.setPen(QColor("#555"))
            for r, lab in ((0, "Mon"), (2, "Wed"), (4, "Fri"), (6, "Sun")):
                p.drawText(QRectF(0, top + r * cell, left - 4, cell),
                           Qt.AlignRight | Qt.AlignVCenter, lab)
            top_v = max([60.0] + list(vals.values())) if metric == "time" else 10.0
            month = None
            for w in range(weeks):
                for r in range(7):
                    d = start + _dt.timedelta(days=7 * w + r)
                    if d > today:
                        break
                    x, y = left + w * cell, top + r * cell
                    rect = QRectF(x, y, cell - gap, cell - gap)
                    v = vals.get(d.isoformat())
                    if v is None:
                        c = QColor(EMPTY)
                    else:
                        c = _time_color(v, top_v) if metric == "time" else _grade_color(v)
                    p.fillRect(rect, c)
                    if d == today or d.isoformat() == self.o.selected:
                        p.setPen(QPen(QColor("#ff9f1a" if d.isoformat() == self.o.selected
                                             else "#222"), 2))
                        p.drawRect(rect)
                    self.hits.append((rect, d.isoformat()))
                    if r == 0 and d.month != month:
                        month = d.month
                        p.setPen(QColor("#555"))
                        p.drawText(QPointF(x, top - 8), d.strftime("%b"))
            # legend
            y = top + 7 * cell + 18
            p.setPen(QColor("#555"))
            p.drawText(QPointF(left, y + 10), "less" if metric == "time" else "0")
            for k in range(10):
                f = k / 9.0
                c = _time_color(f * top_v, top_v) if metric == "time" else _grade_color(10 * f)
                p.fillRect(QRectF(left + 34 + k * 14, y, 12, 12), c)
            p.drawText(QPointF(left + 34 + 10 * 14 + 6, y + 10),
                       f"{top_v:.0f} min" if metric == "time" else "10")
            label = self.o.colour_box.currentText()
            lx = left + 34 + 10 * 14 + 70
            if lx + p.fontMetrics().horizontalAdvance(label) > self.width() - 8:
                p.drawText(QPointF(left, y + 28), label)      # no room: on the next line
            else:
                p.drawText(QPointF(lx, y + 10), label)

        # -------------------------------------------------- candles
        def _frame(self, p, n, y0=0.0, y1=10.0, ylab="grade", top=30):
            W, H = self.width(), self.height()
            L, R, T, B = 44, 12, top, 34
            pw, ph = W - L - R, H - T - B
            p.setPen(QColor("#ddd"))
            for g in range(int(y0), int(y1) + 1, 2 if y1 - y0 <= 10 else max(1, int((y1 - y0) / 5))):
                y = T + ph * (1 - (g - y0) / (y1 - y0))
                p.drawLine(QPointF(L, y), QPointF(W - R, y))
                p.setPen(QColor("#555"))
                p.drawText(QRectF(0, y - 8, L - 6, 16), Qt.AlignRight | Qt.AlignVCenter, f"{g:g}")
                p.setPen(QColor("#ddd"))
            p.setPen(QColor("#555"))
            p.drawText(QPointF(4, 14), ylab)
            return L, T, pw, ph

        def _xlabels(self, p, days, L, T, pw, ph, xs):
            p.setPen(QColor("#555"))
            step = max(1, len(days) // 8)
            for i in range(0, len(days), step):
                p.drawText(QRectF(xs[i] - 40, T + ph + 4, 80, 16), Qt.AlignCenter, days[i][5:])

        def _paint_candles(self, p):
            rows = self.o.d.candles(self.o.kind())
            if not rows:
                return self._empty(p, "No grades for this exercise type yet")
            L, T, pw, ph = self._frame(p, len(rows))
            n = len(rows)
            step = pw / max(1, n)
            bw = max(3.0, min(18.0, step * 0.6))

            def yv(g):
                return T + ph * (1 - g / 10.0)
            p.setPen(QPen(QColor("#999"), 1, Qt.DashLine))
            p.drawLine(QPointF(L, yv(6)), QPointF(L + pw, yv(6)))       # 'fair' line
            xs = []
            for i, (d, o, hi, lo, c, m) in enumerate(rows):
                x = L + step * (i + 0.5)
                xs.append(x)
                up = c >= o
                col = QColor("#2e7d32" if up else "#c62828")
                p.setPen(QPen(col, 1.4))
                p.drawLine(QPointF(x, yv(hi)), QPointF(x, yv(lo)))
                top, bot = yv(max(o, c)), yv(min(o, c))
                body = QRectF(x - bw / 2, top, bw, max(1.5, bot - top))
                p.fillRect(body, col if not up else QColor("#a5d6a7"))
                p.drawRect(body)
                if m is not None:
                    p.setBrush(QColor("#222"))
                    p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(x, yv(m)), 2.5, 2.5)
                    p.setBrush(Qt.NoBrush)
                if d == self.o.selected:
                    p.setPen(QPen(QColor("#ff9f1a"), 2))
                    p.drawRect(QRectF(x - step / 2, T, step, ph))
                self.hits.append((QRectF(x - step / 2, T, step, ph), d))
            self._xlabels(p, [r[0] for r in rows], L, T, pw, ph, xs)

        # -------------------------------------------------- trend
        def _paint_trend(self, p):
            rows = self.o.d.trend(self.o.kind())
            if not rows:
                return self._empty(p, "No grades for this exercise type yet")
            L, T, pw, ph = self._frame(p, len(rows))
            d0 = _dt.date.fromisoformat(rows[0][0])
            span = max(1, (_dt.date.fromisoformat(rows[-1][0]) - d0).days)

            def xv(d):
                return L + 10 + (pw - 20) * (_dt.date.fromisoformat(d) - d0).days / span

            def yv(g):
                return T + ph * (1 - g / 10.0)
            band = QPolygonF([QPointF(xv(r[0]), yv(r[3])) for r in rows]
                             + [QPointF(xv(r[0]), yv(r[2])) for r in reversed(rows)])
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(21, 101, 192, 40))
            p.drawPolygon(band)
            p.setBrush(QColor("#1565c0"))
            xs = []
            for d, m, lo, hi, avg in rows:
                xs.append(xv(d))
                p.drawEllipse(QPointF(xv(d), yv(m)), 3, 3)
                self.hits.append((QRectF(xv(d) - 6, T, 12, ph), d))
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#e65100"), 2.4))
            for a, b in zip(rows, rows[1:]):
                p.drawLine(QPointF(xv(a[0]), yv(a[4])), QPointF(xv(b[0]), yv(b[4])))
            if self.o.selected in [r[0] for r in rows]:
                p.setPen(QPen(QColor("#ff9f1a"), 1.5, Qt.DashLine))
                x = xv(self.o.selected)
                p.drawLine(QPointF(x, T), QPointF(x, T + ph))
            self._xlabels(p, [r[0] for r in rows], L, T, pw, ph, xs)
            p.setPen(QColor("#555"))
            p.drawText(QPointF(L + 60, 14), "dots: mean of the day   band: min–max   "
                                            "line: mean over 7 days")

        # -------------------------------------------------- weekly
        def _paint_weekly(self, p):
            wk = self.o.d.weekly()
            if not wk:
                return self._empty(p)
            weeks = list(wk)[-26:]
            top = max(30.0, max(sum(wk[w].values()) for w in weeks))
            # LEGEND THAT FITS (owner, 2026-11-13: part of it went out of the window): only the
            # exercise types in the weeks shown, on as many rows as the width needs; the chart
            # starts below it
            fm = p.fontMetrics()
            kinds = [k for k in dy.KINDS if any(wk[w].get(k, 0.0) > 0 for w in weeks)]
            W, x, rows, place = self.width(), 44.0, 0, []
            for k in kinds:
                iw = 14 + fm.horizontalAdvance(dy.KIND_LABELS[k]) + 12
                if place and x + iw > W - 12:
                    rows, x = rows + 1, 44.0
                place.append((k, x, rows))
                x += iw
            nrows = rows + 1 if place else 0
            L, T, pw, ph = self._frame(p, len(weeks), 0.0, top, "minutes",
                                       top=max(30, 22 + 16 * nrows + 8))
            step = pw / len(weeks)
            bw = max(4.0, step * 0.7)
            xs = []
            for i, w in enumerate(weeks):
                x = L + step * (i + 0.5)
                xs.append(x)
                y = T + ph
                for k in dy.KINDS:
                    v = wk[w].get(k, 0.0)
                    if v <= 0:
                        continue
                    h = ph * v / top
                    p.fillRect(QRectF(x - bw / 2, y - h, bw, h), QColor(KIND_COLORS[k]))
                    y -= h
            self._xlabels(p, weeks, L, T, pw, ph, xs)
            for k, x0, r in place:
                y0 = 22 + 16 * r
                p.fillRect(QRectF(x0, y0, 10, 10), QColor(KIND_COLORS[k]))
                p.setPen(QColor("#333"))
                p.drawText(QPointF(x0 + 14, y0 + 9), dy.KIND_LABELS[k])

        # -------------------------------------------------- mouse
        def _day_at(self, pos):
            for r, d in self.hits:
                if r.contains(pos):
                    return d
            return None

        def mouseMoveEvent(self, e):
            pos = e.position() if hasattr(e, "position") else e.pos()
            d = self._day_at(pos)
            if d is None:
                QToolTip.hideText()
                return
            QToolTip.showText(e.globalPosition().toPoint() if hasattr(e, "globalPosition")
                              else e.globalPos(), self.o.tooltip(d), self)

        def mousePressEvent(self, e):
            pos = e.position() if hasattr(e, "position") else e.pos()
            d = self._day_at(pos)
            if d is not None:
                self.o.select_day(d)

    class DiaryWidget(QWidget):
        def __init__(self, app):
            super().__init__()
            self.app = app
            self.d = dy.get(app.user)
            self.selected = dy.day_of()
            # FILTER BY INSTRUMENT (owner, 2026-11-18): all, or one of the user's instruments
            # (attempts made before then have no instrument: only in "All instruments")
            from .. import instruments as ins
            self.ins_box = QComboBox()
            self.ins_box.addItem("All instruments", None)
            for k in ins.user_instruments():
                self.ins_box.addItem(ins.label(k), ins.played(k))
            self.streak = QLabel("")
            self.bar, _ = action_bar([("Refresh", self.refresh, "read the diary again"),
                                      ("Today", lambda: self.select_day(dy.day_of()),
                                       "summary of today")], right=self.streak)
            lay = QVBoxLayout(self)
            row = QHBoxLayout()
            self.chart_box = QComboBox()
            self.chart_box.addItems(["Calendar", "Candles", "Trend", "Weekly time"])
            self.colour_box = QComboBox()
            self.colour_box.addItem("Time studied", ("time", None))
            self.colour_box.addItem("Mean grade", ("grade", None))
            for k in dy.GRADED:
                self.colour_box.addItem(f"Mean grade: {dy.KIND_LABELS[k]}", ("grade", k))
            self.kind_box = QComboBox()
            self.kind_box.addItem("All exercises", None)
            for k in dy.GRADED:
                self.kind_box.addItem(dy.KIND_LABELS[k], k)
            self.colour_lbl, self.kind_lbl = QLabel("Colour:"), QLabel("Exercise:")
            row0 = QHBoxLayout()                       # two rows: the content fits the space
            for w in (QLabel("Instrument:"), self.ins_box, QLabel("Chart:"), self.chart_box):
                row0.addWidget(w)
            row0.addStretch(1)
            lay.addLayout(row0)
            for w in (self.colour_lbl, self.colour_box, self.kind_lbl, self.kind_box):
                row.addWidget(w)
            row.addStretch(1)
            lay.addLayout(row)
            split = QSplitter(Qt.Horizontal)
            self.canvas = Canvas(self)
            self.detail = QTextBrowser()
            self.detail.setMinimumWidth(260)
            split.addWidget(self.canvas)
            split.addWidget(self.detail)
            split.setStretchFactor(0, 3)
            split.setStretchFactor(1, 1)
            lay.addWidget(split, 1)
            for b in (self.chart_box, self.colour_box, self.kind_box):
                b.currentIndexChanged.connect(self._changed)
            self.ins_box.currentIndexChanged.connect(lambda *_: self.refresh())
            self._changed()
            self.refresh()

        # ---------------------------------------------- state
        def chart(self):
            return ("calendar", "candles", "trend", "weekly")[self.chart_box.currentIndex()]

        def colour(self):
            return self.colour_box.currentData()

        def kind(self):
            return self.kind_box.currentData()

        def set_chart(self, name):
            self.chart_box.setCurrentIndex(("calendar", "candles", "trend", "weekly").index(name))
            return self

        def _changed(self, *_):
            c = self.chart()
            for w in (self.colour_lbl, self.colour_box):
                w.setVisible(c == "calendar")
            for w in (self.kind_lbl, self.kind_box):
                w.setVisible(c in ("candles", "trend"))
            self.canvas.update()

        def refresh(self):
            self.d = dy.get(self.app.user).view(self.ins_box.currentData())
            self.d.freeze()
            cur, best = self.d.streak()
            today = self.d.day()
            self.streak.setText(f"today {today['minutes']:.0f} min   streak {cur} days "
                                f"(longest {best})  ")
            self.select_day(self.selected)
            return self

        def select_day(self, day):
            self.selected = day
            self.detail.setHtml(self.day_html(day))
            self.canvas.update()
            return self

        # ---------------------------------------------- text
        def tooltip(self, day):
            s = self.d.day(day)
            mean = "–" if s["mean"] is None else f"{s['mean']:.1f}"
            return f"{day}: {s['minutes']:.0f} min, {s['n']} exercises, mean {mean}"

        def day_html(self, day):
            s = self.d.day(day)
            when = _dt.date.fromisoformat(day).strftime("%A %d %B %Y")
            state = "frozen" if s.get("frozen") else "today (still open)" \
                if day == dy.day_of() else "not frozen yet"
            h = [f"<h3>{when}</h3><p><i>{state}</i></p>",
                 f"<p><b>{s['minutes']:.0f} min</b> of study, <b>{s['n']}</b> exercises"
                 + ("" if s["mean"] is None else f", mean grade <b>{s['mean']:.1f}</b>")
                 + "</p>"]
            if s["by_kind"]:
                h.append("<table cellspacing=4><tr><th align=left>Type</th><th>n</th>"
                         "<th>mean</th><th>min</th></tr>")
                for k, b in s["by_kind"].items():
                    m = "–" if b["mean"] is None else f"{b['mean']:.1f}"
                    h.append(f"<tr><td><font color='{KIND_COLORS.get(k, '#333')}'>■</font> "
                             f"{dy.KIND_LABELS.get(k, k)}</td><td align=center>{b['n']}</td>"
                             f"<td align=center>{m}</td><td align=center>{b['minutes']:.0f}</td></tr>")
                h.append("</table>")
            if s["exercises"]:
                h.append("<p><b>Exercises</b> (grade of the day = best attempt)</p><ul>")
                for x in s["exercises"]:
                    more = f" ({x['attempts']} attempts, first {x['first']:.1f})" \
                        if x["attempts"] > 1 else ""
                    h.append(f"<li><font color='{KIND_COLORS.get(x['kind'], '#333')}'>■</font> "
                             f"{x['title'] or x['key']}: <b>{x['best']:.1f}</b>{more}</li>")
                h.append("</ul>")
            if not s["by_kind"]:
                h.append("<p>Nothing practised on this day.</p>")
            return "".join(h)

    return DiaryWidget


registry.register(registry.Tool(
    name="practice_diary", label="Practice diary (results day by day)", category="Analyse",
    kind="session", factory=lambda app: _widget_class()(app),
    help="Calendar of the days of practice (colour: time, mean grade, grade of one exercise "
         "type), candles and trend of the grades, minutes per week; click a day for its "
         "summary. Days are frozen at 04:00."))
