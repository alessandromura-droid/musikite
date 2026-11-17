"""History tab: results of an exercise for a user (per session and per item)."""


def history_widget(progress, user, exercise, title, label=str):
    """Results per session (chart, as MATLAB mylog) and accuracy per item (table);
    label(asked) -> text of an item."""
    import datetime as dt
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel
    from PySide6.QtCharts import (QChart, QChartView, QLineSeries, QScatterSeries, QDateTimeAxis,
                                  QValueAxis)
    from PySide6.QtCore import QDateTime, Qt
    from PySide6.QtGui import QPainter

    w = QWidget()
    lay = QVBoxLayout(w)
    ses = progress.sessions(user, exercise)
    if ses.empty:
        lay.addWidget(QLabel(f"No results yet for {user}"))
        return w
    chart = QChart()
    chart.setTitle(f"{user}: {title}, % correct per session")
    line, dots = QLineSeries(), QScatterSeries()
    dots.setMarkerSize(9)
    times = []
    for r in ses.itertuples():
        t = dt.datetime.fromisoformat(r.session)
        ms = QDateTime(t.year, t.month, t.day, t.hour, t.minute, t.second).toMSecsSinceEpoch()
        times.append(ms)
        line.append(ms, r.percent)
        dots.append(ms, r.percent)
    ax = QDateTimeAxis()
    ax.setFormat("dd MMM yy")
    day = 86400000
    ax.setRange(QDateTime.fromMSecsSinceEpoch(min(times) - day),
                QDateTime.fromMSecsSinceEpoch(max(times) + day))
    ay = QValueAxis()
    ay.setRange(0, 100)
    ay.setLabelFormat("%d")
    chart.addAxis(ax, Qt.AlignBottom)
    chart.addAxis(ay, Qt.AlignLeft)
    for series in (line, dots):
        chart.addSeries(series)
        series.attachAxis(ax)
        series.attachAxis(ay)
    chart.legend().hide()
    view = QChartView(chart)
    view.setRenderHint(QPainter.Antialiasing)
    view.setMinimumHeight(300)
    lay.addWidget(view)

    items = progress.by_item(user, exercise)
    tab = QTableWidget(len(items), 4)
    tab.setHorizontalHeaderLabels(["Item", "Answers", "Correct", "%"])
    for i, r in enumerate(items.itertuples()):
        for j, v in enumerate((label(r.asked), r.answers, r.correct,
                               r.percent)):
            tab.setItem(i, j, QTableWidgetItem(str(v)))
    tab.resizeColumnsToContents()
    lay.addWidget(QLabel("Accuracy per item (all sessions)"))
    lay.addWidget(tab)
    last = ses.iloc[-1]
    lay.addWidget(QLabel(f"Sessions: {len(ses)}   last: {last.session}  "
                         f"{int(last.correct)}/{int(last.answers)} ({last.percent:.0f}%)"))
    return w
