"""
Base d'apprentissage progressive - infrastructure de collecte VALIDEE pour le
reentrainement periodique des modeles (reseau et transactions).

Principe de securite impose (voir discussion produit) : AUCUN apprentissage
automatique en continu sans validation humaine. Un flux/transaction que le
modele vient de classer n'est jamais ajoute tel quel a la base d'entrainement
- un analyste doit d'abord confirmer ou corriger l'etiquette. Sans ce filtre,
le systeme pourrait apprendre de ses propres erreurs et deriver (risque
d'empoisonnement de donnees).

Flux :
  1. Le modele classe un flux/transaction (comme aujourd'hui, inchange)
  2. Un analyste VALIDE (confirme la prediction) ou CORRIGE (donne la vraie
     etiquette) via `add_validated_sample()`
  3. Les echantillons valides s'accumulent dans un lot versionne
     (outputs/learning_db/<domaine>/lot_XXXX.jsonl)
  4. Quand un lot atteint une taille suffisante (ou sur demande explicite),
     `build_retraining_dataset()` fusionne les lots valides en un jeu de
     donnees pret pour un nouveau cycle d'entrainement
  5. Le reentrainement (src/*/train_pipeline.py) reste un acte EXPLICITE,
     jamais declenche automatiquement - un nouveau modele est toujours compare
     a l'ancien avant d'etre mis en production (voir README, discussion
     "collecte continue, reentrainement par cycles")
"""
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LEARNING_DB_DIR = BASE_DIR / "outputs" / "learning_db"


def _domain_dir(domain: str) -> Path:
    """domain: 'reseau' ou 'transactions' (extensible a d'autres domaines plus tard)."""
    d = LEARNING_DB_DIR / domain
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_validated_sample(domain: str, features: dict, true_label, validated_by: str, source: str = "manuel"):
    """Ajoute UN echantillon deja valide par un humain a la base d'apprentissage.

    - domain : 'reseau' ou 'transactions'
    - features : dict des variables (memes noms que le schema du modele concerne)
    - true_label : etiquette confirmee ou corrigee par l'analyste (pas la prediction brute)
    - validated_by : identifiant de l'analyste (email/compte) - tracabilite obligatoire
    - source : d'ou vient l'echantillon (ex. 'analyse_csv', 'flux_unique', 'import_partenaire')
    """
    d = _domain_dir(domain)
    entry = {
        "horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
        "features": features,
        "label": true_label,
        "validated_by": validated_by,
        "source": source,
    }
    # Un seul fichier "lot courant" par domaine, tourne manuellement (voir rotate_batch)
    current_batch = d / "lot_courant.jsonl"
    with open(current_batch, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def batch_size(domain: str) -> int:
    current_batch = _domain_dir(domain) / "lot_courant.jsonl"
    if not current_batch.exists():
        return 0
    with open(current_batch) as f:
        return sum(1 for line in f if line.strip())


def rotate_batch(domain: str) -> str | None:
    """Archive le lot courant sous un nom versionne (horodate), pour en debuter un nouveau.
    A appeler apres un reentrainement reussi, ou quand le lot devient volumineux."""
    d = _domain_dir(domain)
    current_batch = d / "lot_courant.jsonl"
    if not current_batch.exists() or batch_size(domain) == 0:
        return None
    archived_name = f"lot_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    current_batch.rename(d / archived_name)
    return archived_name


def build_retraining_dataset(domain: str):
    """Fusionne TOUS les lots (archives + courant) en un seul jeu de donnees,
    pret a etre charge par un script d'entrainement. Retourne (features_list, labels_list)."""
    d = _domain_dir(domain)
    all_features, all_labels = [], []
    for batch_file in sorted(d.glob("*.jsonl")):
        with open(batch_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                all_features.append(entry["features"])
                all_labels.append(entry["label"])
    return all_features, all_labels


def learning_db_status(domain: str) -> dict:
    """Vue d'ensemble : taille du lot courant, nombre de lots archives, total cumule."""
    d = _domain_dir(domain)
    archived = [f for f in d.glob("lot_2*.jsonl")]
    total_archived = 0
    for f in archived:
        with open(f) as fh:
            total_archived += sum(1 for line in fh if line.strip())
    return {
        "lot_courant": batch_size(domain),
        "lots_archives": len(archived),
        "total_echantillons_archives": total_archived,
        "total_cumule": batch_size(domain) + total_archived,
    }
