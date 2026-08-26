"""
Reglage de sensibilite par compte - personnalisation LEGERE (sans reentrainement)
du seuil de decision, applicable immediatement sur le modele existant.

Principe : au lieu de toujours choisir la classe la plus probable (argmax brut),
chaque organisation peut ajuster le seuil de confiance minimum requis pour
classer un flux/transaction comme "normal/legitime". Plus ce seuil est haut,
plus le systeme est sensible (il faut etre TRES sur qu'un flux est normal pour
ne pas le signaler - detecte plus, mais plus de fausses alertes). Plus il est
bas, moins le systeme est sensible (ne signale que les cas tres confiants -
moins de fausses alertes, mais risque de rater des menaces subtiles).

Valeur par defaut (0.5) : comportement equivalent a l'argmax standard.
"""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SENSITIVITY_FILE = BASE_DIR / "outputs" / "sensitivity_settings.json"

DEFAULT_THRESHOLD = 0.5


def _load() -> dict:
    if SENSITIVITY_FILE.exists():
        with open(SENSITIVITY_FILE) as f:
            return json.load(f)
    return {}


def _save(state: dict) -> None:
    SENSITIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SENSITIVITY_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_threshold(domain: str, account_id: str) -> float:
    """domain: 'reseau' ou 'transactions'."""
    state = _load()
    return state.get(f"{domain}:{account_id}", DEFAULT_THRESHOLD)


def set_threshold(domain: str, account_id: str, threshold: float) -> float:
    if not (0.0 < threshold < 1.0):
        raise ValueError("Le seuil doit etre strictement entre 0 et 1.")
    state = _load()
    state[f"{domain}:{account_id}"] = threshold
    _save(state)
    return threshold
