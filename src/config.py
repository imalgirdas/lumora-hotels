"""
Script:   config.py
Purpose:  Folder paths used by every script and notebook.
          Works when you run from the project root or from notebooks/.
"""
from pathlib import Path

# project root = the folder that holds Data/
_here = Path(__file__).resolve().parent.parent
if (_here / "Data").exists():
    BASE = _here
elif (Path.cwd() / "Data").exists():
    BASE = Path.cwd()
else:
    BASE = Path.cwd().parent

RAW_DIR = BASE / "Data"
CLEAN_DIR = BASE / "Data_clean"
OUT_DIR = BASE / "output"
FIG_DIR = OUT_DIR / "figures"
TAB_DIR = OUT_DIR / "tables"
MODEL_DIR = OUT_DIR / "models"
DASH_DIR = OUT_DIR / "dashboard"

TEST_YEAR = 2025          # models train on 2021-2024 and are tested on 2025
RANDOM_STATE = 42


def make_dirs():
    for d in [CLEAN_DIR, FIG_DIR, TAB_DIR, MODEL_DIR, DASH_DIR]:
        d.mkdir(parents=True, exist_ok=True)
