"""Graphical front end: a container of tools (see mainwindow.py, registry.py)."""


def gui(show=True):
    """Open the main window. In Jupyter it returns at once (Qt loop switched on);
    the returned App object drives the window from code."""
    from .mainwindow import App
    app = App()
    return app.show() if show else app


def main():
    """Command line: python3 -m musictools gui"""
    from .mainwindow import App
    App().run()
