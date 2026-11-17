#!/usr/bin/env python3
"""scoreread.py: the PDF reader now lives in the musictools package
(musictools/scoreread.py; font in musictools/data/TrumpetFing.ttf). This file only
keeps the old command working, with the same options:

    python3 scoreread.py score.pdf [--fontsize 12] [--font Arial.ttf] [--space 12]
                                   [--color k] [--no_repetition true]
    python3 scoreread.py score.pdf --midi [--instrument NAME] [--force]

Warnings log: ~/.musikite/scoreread.log (option --log to change it).
The module is loaded directly from its file, without importing the whole package.
"""
import importlib.util
import os
import sys

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musictools", "scoreread.py")
if not os.path.isfile(_PATH):
    sys.exit(f"missing {_PATH}: copy the whole musictools folder")
_spec = importlib.util.spec_from_file_location("scoreread", _PATH)
_engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_engine)

if __name__ == "__main__":
    _engine.main()
