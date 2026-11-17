"""musictools: Alessandro's music tools as one modular package."""
from .check import require, check, prepare_fluidsynth
require()            # stops here with what to install if required packages are missing
prepare_fluidsynth() # lets pyfluidsynth find a FluidSynth library outside the default path
from . import theory    # music theory engine (pure Python)
from .midi import Midi, makeduet, midiplay, merge
from .pdf import Pdf
from .score import Score
from .notes import Notes
from .staffview import StaffView
from .eartraining import IntervalQuiz
from .reading import IntervalReadingQuiz
from .progress import Progress, folder, set_folder, set_current_user
from .workspace import save_workspace, load_workspace
from .playcheck import PlayCheck, PlayQuiz
from .report import ScoreReport
from .transcribe import audio_notes
from .phrase import Phrase, ExerciseSet, exercises_from_midi
from .gui import gui
from .audio import audio_settings, audio_test, audio_panel, audio_devices

__all__ = ["check", "theory", "Midi", "Pdf", "Score", "Notes", "StaffView", "IntervalQuiz", "IntervalReadingQuiz", "PlayCheck", "PlayQuiz", "ScoreReport", "audio_notes", "Phrase", "ExerciseSet", "exercises_from_midi", "Progress", "folder", "set_folder", "set_current_user", "save_workspace", "load_workspace", "gui", "audio_settings", "audio_test", "audio_panel", "audio_devices", "makeduet", "midiplay", "merge"]
