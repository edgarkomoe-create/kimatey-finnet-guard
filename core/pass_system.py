"""
Systeme de "Pass" optionnels (inspire des forfaits Orange/MTN Cote d'Ivoire) -
paliers payants facultatifs, en plus de l'usage de base.

*** MODE DEMO *** L'achat d'un Pass ici n'encaisse AUCUN argent reel : aucun
compte marchand Orange Money/MTN Mobile Money n'est branche (voir
docs/ROADMAP_PAIEMENT.md pour ce que ca demanderait reellement). Un Pass
"achete" via /pass/souscrire est active immediatement, sans transaction
financiere - utile pour demontrer le systeme de quotas/fonctionnalites, pas
pour un vrai usage commercial en l'etat.

Principe de garde-fou (decision produit explicite) : cote Grand Public, la
verification de base contre les arnaques (chat texte avec Lieutenant Cyber)
reste TOUJOURS gratuite et illimitee, quel que soit le Pass actif ou son
absence - seuls des conforts additionnels (volume d'analyse d'image, sync
multi-appareils, rapports) sont limites par Pass. La mission de protection
citoyenne ne doit jamais dependre d'un paiement.
"""
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PASS_STATE_FILE = BASE_DIR / "outputs" / "pass_subscriptions.json"

PASS_CATALOG = {
    "organisation": [
        {
            "id": "org_decouverte", "nom": "Pass Decouverte", "prix_fcfa": 0, "duree_jours": None,
            "quotas": {"analyses_csv_mois": 3, "predictions_unitaires_jour": 20},
            "fonctionnalites": [],
            "description": "Pour tester la plateforme. Toujours gratuit.",
        },
        {
            "id": "org_pro", "nom": "Pass Pro", "prix_fcfa": 15000, "duree_jours": 30,
            "quotas": {"analyses_csv_mois": 50, "predictions_unitaires_jour": 500},
            "fonctionnalites": ["module_transactions", "export_avance"],
            "description": "Pour une equipe securite active au quotidien.",
        },
        {
            "id": "org_entreprise", "nom": "Pass Entreprise", "prix_fcfa": 75000, "duree_jours": 30,
            "quotas": {"analyses_csv_mois": None, "predictions_unitaires_jour": None},
            "fonctionnalites": ["module_transactions", "export_avance", "historique_illimite", "support_prioritaire"],
            "description": "Usage illimite, support prioritaire.",
        },
    ],
    "public": [
        {
            "id": "pub_gratuit", "nom": "Gratuit", "prix_fcfa": 0, "duree_jours": None,
            "quotas": {"images_mois": 5},
            "fonctionnalites": [],
            "description": "Verification de base illimitee. Toujours gratuit.",
        },
        {
            "id": "pub_famille", "nom": "Pass Famille", "prix_fcfa": 1000, "duree_jours": 30,
            "quotas": {"images_mois": 100},
            "fonctionnalites": ["sync_multi_appareils", "rapport_mensuel"],
            "description": "Pour proteger toute la famille, sur plusieurs appareils.",
        },
    ],
}


def get_catalog(scope: str) -> list[dict]:
    return PASS_CATALOG.get(scope, [])


def get_pass_definition(scope: str, pass_id: str) -> dict | None:
    for p in get_catalog(scope):
        if p["id"] == pass_id:
            return p
    return None


def _load_state() -> dict:
    if PASS_STATE_FILE.exists():
        with open(PASS_STATE_FILE) as f:
            return json.load(f)
    return {}


def _save_state(state: dict) -> None:
    PASS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PASS_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def souscrire(scope: str, account_id: str, pass_id: str) -> dict:
    """Active un Pass pour un compte (MODE DEMO - aucun paiement reel).
    account_id : email (reutilise l'identite existante, organisation ou compte
    public optionnel)."""
    definition = get_pass_definition(scope, pass_id)
    if definition is None:
        raise ValueError(f"Pass inconnu : {pass_id}")

    state = _load_state()
    key = f"{scope}:{account_id}"
    now = time.time()
    expires_at = now + definition["duree_jours"] * 86400 if definition["duree_jours"] else None

    state[key] = {
        "pass_id": pass_id, "scope": scope, "souscrit_le": now, "expire_le": expires_at,
        "usage": {k: 0 for k in definition["quotas"]},
        "mode_demo": True,  # rappel explicite : pas de vrai paiement
    }
    _save_state(state)
    return state[key]


def get_active_pass(scope: str, account_id: str) -> dict:
    """Retourne le Pass actif (definition + usage), ou le Pass gratuit par defaut
    si aucune souscription active/non expiree."""
    state = _load_state()
    key = f"{scope}:{account_id}"
    entry = state.get(key)
    free_pass_id = "org_decouverte" if scope == "organisation" else "pub_gratuit"

    if entry is None:
        definition = get_pass_definition(scope, free_pass_id)
        return {"pass_id": free_pass_id, "definition": definition, "usage": {k: 0 for k in definition["quotas"]}, "expire_le": None}

    if entry.get("expire_le") and entry["expire_le"] < time.time():
        # Pass expire : retombe sur le Pass gratuit, mais garde la trace de l'historique
        definition = get_pass_definition(scope, free_pass_id)
        return {"pass_id": free_pass_id, "definition": definition, "usage": {k: 0 for k in definition["quotas"]}, "expire_le": None, "pass_precedent_expire": entry["pass_id"]}

    definition = get_pass_definition(scope, entry["pass_id"])
    return {"pass_id": entry["pass_id"], "definition": definition, "usage": entry["usage"], "expire_le": entry.get("expire_le")}


def check_and_increment_quota(scope: str, account_id: str, quota_key: str) -> tuple[bool, dict]:
    """Verifie si l'action est autorisee par le quota du Pass actif, et
    l'incremente si oui. Retourne (autorise: bool, info: dict).
    quota_key absent du Pass actif (ex. fonctionnalite non liee a un quota) ->
    toujours autorise (pas de quota = pas de limite sur cette dimension)."""
    active = get_active_pass(scope, account_id)
    definition = active["definition"]
    limit = definition["quotas"].get(quota_key)
    if limit is None:
        return True, {"illimite": True}

    state = _load_state()
    key = f"{scope}:{account_id}"
    current_usage = state.get(key, {}).get("usage", {}).get(quota_key, 0)

    if current_usage >= limit:
        return False, {"quota_atteint": True, "limite": limit, "utilise": current_usage, "pass_actuel": active["pass_id"]}

    # Increment (initialise l'entree si le compte tourne encore sur le Pass gratuit implicite)
    if key not in state:
        state[key] = {
            "pass_id": active["pass_id"], "scope": scope, "souscrit_le": time.time(),
            "expire_le": None, "usage": {k: 0 for k in definition["quotas"]}, "mode_demo": True,
        }
    state[key]["usage"][quota_key] = state[key]["usage"].get(quota_key, 0) + 1
    _save_state(state)
    return True, {"utilise": current_usage + 1, "limite": limit}


def has_feature(scope: str, account_id: str, feature_key: str) -> bool:
    active = get_active_pass(scope, account_id)
    return feature_key in active["definition"].get("fonctionnalites", [])
