"""Right-hand panel of a transform tool: options (built from Param) and Run.
The input is what is selected in Objects (only the objects the tool accepts)."""


def tool_panel(app, tool):
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QSpinBox, QDoubleSpinBox,
                                   QCheckBox, QLineEdit, QComboBox, QPushButton, QLabel,
                                   QHBoxLayout,
                                   QListWidget, QListWidgetItem, QAbstractItemView)  # noqa: F401
    w = QWidget()
    lay = QVBoxLayout(w)
    title = QLabel(f"<b>{tool.label}</b>")
    lay.addWidget(title)
    if tool.help:
        h = QLabel(tool.help)
        h.setWordWrap(True)
        lay.addWidget(h)
    form = QFormLayout()
    controls = {}
    sel_label = QLabel("")
    sel_label.setWordWrap(True)
    if tool.inputs:
        lay.addWidget(sel_label)

    fillers = []                               # controls filled from the selection
    setters = {}                               # name -> set(value) ('str', 'choice')
    last = {}                                  # name -> value before the change

    def apply(updates):
        """Set the values returned by an action / on_change, without new on_change."""
        for name, v in (updates or {}).items():
            if name in setters:
                c = controls[name][0]
                c.blockSignals(True)
                setters[name](v)
                c.blockSignals(False)
                last[name] = controls[name][1]()

    def changed(p, new):
        old = last.get(p.name)
        last[p.name] = new
        if new == old:
            return
        try:
            apply(p.on_change(old, new, values()))
        except Exception as e:                 # a wrong chord typed: say it, keep the text
            app.log(f"{tool.label}: {e}")

    def refresh_inputs():
        if not tool.inputs:
            return
        for f in fillers:
            f()
        types = tuple(tool.inputs)
        objs = app.selected_objects(types)
        kinds = " / ".join(c.__name__ for c in types)
        if objs:
            names = [n for n in app.selected_names() if any(app.get_object(n) is o for o in objs)]
            more = f" … (+{len(names) - 3})" if len(names) > 3 else ""
            sel_label.setText(f"Input: {len(objs)} selected {kinds} — " +
                              ", ".join(names[:3]) + more)
            sel_label.setStyleSheet("")
        else:
            sel_label.setText(f"Input: select one or more {kinds} objects on the left")
            sel_label.setStyleSheet("color: #c62828")

    for p in tool.params:
        default = p.value()                    # a callable default is read now (e.g. Settings)
        if p.kind == "int":
            c = QSpinBox()
            c.setRange(int(p.minimum if p.minimum is not None else -10 ** 6),
                       int(p.maximum if p.maximum is not None else 10 ** 6))
            c.setValue(int(default))
            if p.choices and isinstance(p.choices, tuple) and len(p.choices) == 1:
                c.setSpecialValueText(str(p.choices[0]))   # text of the minimum ("start")
            get = c.value
        elif p.kind == "float":
            c = QDoubleSpinBox()
            c.setDecimals(2)
            c.setRange(float(p.minimum if p.minimum is not None else -1e6),
                       float(p.maximum if p.maximum is not None else 1e6))
            c.setSingleStep(float(p.step or 0.1))
            c.setValue(float(default))
            get = c.value
        elif p.kind == "bool":
            c = QCheckBox()
            c.setChecked(bool(default))
            get = c.isChecked
        elif p.kind == "choice":
            c = QComboBox()
            c.addItems([str(x) for x in p.choices])
            c.setCurrentText(str(default))
            get = (lambda c=c, p=p: p.choices[c.currentIndex()])
        elif p.kind == "multi":
            c = QListWidget()
            c.setSelectionMode(QAbstractItemView.MultiSelection)
            c.addItems([str(x) for x in p.choices])
            c.setMaximumHeight(min(22 * len(p.choices) + 6, 180))
            for i, x in enumerate(p.choices):
                if default and x in default:
                    c.item(i).setSelected(True)
            get = (lambda c=c: [i.text() for i in c.selectedItems()] or None)
        elif p.kind == "tracks":
            # tracks of the FIRST selected input, as a check list (p.choices(obj) ->
            # [(index, label, checked)], p.maximum = how many at most); value: the indices
            c = QListWidget()
            c.setMaximumHeight(140)

            def fill(c=c, p=p):
                from PySide6.QtCore import Qt as _Qt
                objs = app.selected_objects(tuple(tool.inputs)) if tool.inputs else []
                c.blockSignals(True)
                c.clear()
                for i, label, on in (p.choices(objs[0]) if objs else []):
                    it = QListWidgetItem(label)
                    it.setData(_Qt.UserRole, i)
                    it.setFlags(it.flags() | _Qt.ItemIsUserCheckable)
                    it.setCheckState(_Qt.Checked if on else _Qt.Unchecked)
                    c.addItem(it)
                c.blockSignals(False)

            def checked(c=c):
                from PySide6.QtCore import Qt as _Qt
                return [c.item(k).data(_Qt.UserRole) for k in range(c.count())
                        if c.item(k).checkState() == _Qt.Checked]

            def limit(item, c=c, p=p, checked=checked):
                from PySide6.QtCore import Qt as _Qt
                if p.maximum and len(checked()) > int(p.maximum):
                    c.blockSignals(True)
                    item.setCheckState(_Qt.Unchecked)
                    c.blockSignals(False)

            c.itemChanged.connect(limit)
            fillers.append(fill)
            get = (lambda checked=checked: checked() or None)
        else:
            c = QLineEdit(str(default or ""))
            get = (lambda c=c: c.text().strip())
        if p.help:
            c.setToolTip(p.help)
        controls[p.name] = (c, get)
        if p.kind == "choice":
            setters[p.name] = (lambda v, c=c, p=p: c.setCurrentIndex(
                [str(x) for x in p.choices].index(str(v)) if str(v) in
                [str(x) for x in p.choices] else c.currentIndex()))
        elif p.kind == "str":
            setters[p.name] = (lambda v, c=c: c.setText(str(v)))
        last[p.name] = get()
        if p.on_change and p.kind in ("choice", "str"):
            sig = c.currentIndexChanged if p.kind == "choice" else c.editingFinished
            sig.connect(lambda *a, p=p, get=get: changed(p, get()))
        row = c
        if p.button and p.action:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(c, 1)
            b = QPushButton(p.button)
            b.setToolTip(p.help)
            b.clicked.connect(lambda *a, p=p: apply(p.action(values())))
            h.addWidget(b)
        form.addRow(p.label or p.name, row)
    lay.addLayout(form)

    run = QPushButton("Run")
    lay.addWidget(run)
    lay.addStretch()

    def values():
        return {name: get() for name, (c, get) in controls.items()}

    def do_run():
        return app.run_tool(tool.name, **values())

    run.clicked.connect(do_run)
    w.tool = tool
    w.refresh_inputs = refresh_inputs
    w.values = values
    w.run = do_run
    w.controls = controls
    refresh_inputs()
    return w
