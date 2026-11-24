"""Viewers for objects that are not scores: PDF pages, exercise objects ◆ with their results."""


def pdf_view(path, zoom=1.6):
    """Scrollable widget with the pages of a PDF (rendered with PyMuPDF)."""
    import pymupdf
    from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QLabel
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtCore import Qt
    inner = QWidget()
    lay = QVBoxLayout(inner)
    doc = pymupdf.open(path)
    for page in doc:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        lab = QLabel()
        lab.setPixmap(QPixmap.fromImage(img))
        lab.setAlignment(Qt.AlignHCenter)
        lay.addWidget(lab)
    area = QScrollArea()
    area.setWidget(inner)
    area.setWidgetResizable(True)
    area.setStyleSheet("background: #808080;")
    return area


def task_view(app, task, name=None):
    """View of an exercise object ◆ (owner: the exercise WITH its results): summary of the
    current user, staff of the last attempt (drills: green / red; long tones: cents chart),
    one row per attempt, "Do it" (= double click)."""
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
                                   QPushButton)
    from PySide6.QtGui import QFont
    from ..tasks import attempts
    w = QWidget()
    lay = QVBoxLayout(w)
    user = app.user
    head = QLabel(f"<b>{task.title}</b> – {user or 'no user'}<br>"
                  + task.summary(user).replace("\n", "<br>"))
    f = QFont()
    f.setPointSize(14)
    head.setFont(f)
    lay.addWidget(head)
    ats = attempts(task, user)
    if task.drill:
        _drill_staff(w, lay, task, ats)
    cols = ["time", "grade"] + (["rating", "result"] if task.drill else
                                ["correct", "n_questions", "seconds", "complete"])
    tab = QTableWidget(len(ats), len(cols))
    tab.setHorizontalHeaderLabels(cols)
    for i, a in enumerate(ats):
        for j, c in enumerate(cols):
            v = a.get(c, "")
            tab.setItem(i, j, QTableWidgetItem("" if v is None else str(v)))
    tab.resizeColumnsToContents()
    lay.addWidget(tab)
    b = QPushButton("Do it")
    b.clicked.connect(lambda: app.practise(task, name or task.title,
                                           key=f"open: {name}" if name else None))
    lay.addWidget(b)
    return w


def _drill_staff(w, lay, task, ats):
    """Staff of a drill with the notes of the last attempt green / red (and the cents
    chart of the long tones)."""
    from PySide6.QtCore import Qt
    from ..playcheck import excerpt
    from ..staffview import StaffView
    try:
        dr = task.drill_obj()
        sv = StaffView(excerpt(dr.phrase.to_score(), 0, None), title=dr.title)
        sv.win.setWindowFlags(Qt.Widget)
        sv.hide_toolbar()
        sv.win.statusBar().hide()
        if ats:
            sv.mark({int(k): v for k, v in (ats[-1].get("colors") or {}).items()})
        sv.win.setMinimumHeight(220)
        lay.addWidget(sv.win, 1)
        w._sv = sv
        if ats and ats[-1].get("notes"):
            from .drills_ui import _cents_chart_class
            ch = _cents_chart_class()()
            ch.set_notes(ats[-1]["notes"])
            lay.addWidget(ch)
    except Exception as e:
        from PySide6.QtWidgets import QLabel
        lay.addWidget(QLabel(f"staff: {type(e).__name__}: {e}"))
