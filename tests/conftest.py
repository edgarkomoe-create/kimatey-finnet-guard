"""Configuration pytest partagee : ajoute la racine du projet au PYTHONPATH."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os
os.chdir(ROOT)  # tous les chemins relatifs (outputs/, data/, ...) supposent ce cwd
