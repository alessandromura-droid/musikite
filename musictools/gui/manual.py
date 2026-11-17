"""Help > Manual (owner, 2026-11-17: "the manual must also be read inside the app"): the
Markdown pages of docs/ (the same files shown on GitHub, edited by the owner) in a tab,
rendered by QTextBrowser. Links to other pages open them in the tab; links to a section
("settings.md#audio", GitHub slugs) scroll to its heading; web links open in the browser;
Back / Forward / Contents in the tab's bar.

docs/ is looked up next to the package (project folder) or inside the packaged app
(PyInstaller puts it beside musictools/: scripts/musikite.spec)."""
import os
import re
import sys


def docs_dir():
    """Folder of the manual, or None."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cands = [os.path.join(here, "docs")]
    if getattr(sys, "frozen", False):
        cands.insert(0, os.path.join(sys._MEIPASS, "docs"))
    for d in cands:
        if os.path.isfile(os.path.join(d, "README.md")):
            return d
    return None


def slug(text):
    """GitHub anchor of a heading: 'Read & play and Listen & repeat' ->
    'read--play-and-listen--repeat'."""
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def manual_widget(app, page=None):
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLabel
    from PySide6.QtGui import QDesktopServices, QTextCursor, QTextDocument
    from PySide6.QtCore import QUrl
    from .bar import action_bar

    class ManualWidget(QWidget):
        def __init__(self):
            super().__init__()
            self.root = docs_dir()
            self.where = QLabel("")
            self.bar, self.buttons = action_bar(
                [("◀ Back", self.back, "previous page"),
                 ("Forward ▶", self.forward, "next page"),
                 ("Contents", lambda: self.open("README.md"), "the index of the manual")],
                right=self.where)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.view = QTextBrowser()
            self.view.setOpenLinks(False)                  # every link goes through _link
            self.view.anchorClicked.connect(self._link)
            self.view.historyChanged.connect(self._history)
            lay.addWidget(self.view)
            if self.root is None:
                self.view.setPlainText("The manual (folder docs/) was not found.")
                app.log("Manual: folder docs/ not found")
            else:
                self.open(page or "README.md")

        # ------------------------------------------------------ navigation
        def open(self, target):
            """A page of docs/ ('drills.md', 'settings.md#audio') or an absolute path."""
            if self.root is None:
                return self
            path, _, frag = str(target).partition("#")
            if path and not os.path.isabs(path):
                path = os.path.join(self.root, path)
            if path:
                if not os.path.isfile(path):
                    app.log(f"Manual: page not found: {target}")
                    return self
                self.view.setSource(QUrl.fromLocalFile(path), QTextDocument.MarkdownResource)
                self.where.setText(os.path.relpath(path, self.root))
            if frag:
                self._scroll_to(frag)
            else:
                self.view.verticalScrollBar().setValue(0)
            return self

        def _link(self, url):
            if url.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return
            if not url.path() and url.fragment():           # "#section" in the same page
                self._scroll_to(url.fragment())
                return
            cur = self.view.source().toLocalFile()
            base = os.path.dirname(cur) if cur else self.root
            path = os.path.normpath(os.path.join(base, url.path()))
            if path.lower().endswith(".md"):
                self.open(path + ("#" + url.fragment() if url.fragment() else ""))
            elif os.path.exists(path):                      # e.g. LICENSE: the system viewer
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
            else:
                app.log(f"Manual: link not found: {url.toString()}")

        def _scroll_to(self, frag):
            """Scroll to the heading whose GitHub slug is frag."""
            doc = self.view.document()
            block = doc.begin()
            while block.isValid():
                if block.blockFormat().headingLevel() > 0 and slug(block.text()) == frag:
                    self.view.setTextCursor(QTextCursor(block))
                    top = doc.documentLayout().blockBoundingRect(block).top()
                    self.view.verticalScrollBar().setValue(int(top))
                    return
                block = block.next()

        def back(self):
            self.view.backward()
            self._where()

        def forward(self):
            self.view.forward()
            self._where()

        def _where(self):
            f = self.view.source().toLocalFile()
            if f and self.root:
                self.where.setText(os.path.relpath(f, self.root))

        def _history(self):
            self.buttons["◀ Back"].setEnabled(self.view.isBackwardAvailable())
            self.buttons["Forward ▶"].setEnabled(self.view.isForwardAvailable())

    return ManualWidget()
