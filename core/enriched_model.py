"""
Niveau 2 du modele hybride : generation d'un modele ENRICHI par organisation,
combinant le socle commun (donnees d'entrainement de base) et les echantillons
propres a cette organisation, deja valides par un humain (voir core/learning_db.py).

Principe de securite (coherent avec le reste du projet) :
- Jamais automatique : declenche explicitement par l'organisation (bouton /
  endpoint dedie), jamais en arriere-plan.
- Minimum d'echantillons valides requis avant de proposer la generation
  (evite un modele enrichi sur 2-3 exemples, non representatif).
- Le modele enrichi est un fichier SEPARE, stocke par organisation - il ne
  remplace jamais le modele de base partage, et n'affecte aucune autre
  organisation.
- Toujours accompagne de ses propres metriques (mesurees sur le meme jeu de
  test que le modele de base), pour que l'organisation puisse juger si
  l'enrichissement a reellement aide avant de l'utiliser.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GridSearchCV
from sklearn.tree import DecisionTreeClassifier

from core.learning_db import build_retraining_dataset

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs"
MODEL_DIR = OUT_DIR / "models"
ORG_MODEL_DIR = MODEL_DIR / "org_models"

MIN_SAMPLES_REQUIRED = 20  # seuil minimal d'echantillons valides avant de proposer l'enrichissement
ORG_SAMPLE_WEIGHT = 5      # poids relatif des echantillons de l'organisation vs le socle commun


def _account_dir(account_id: str) -> Path:
    # Nom de fichier sûr : remplace les caracteres non alphanumeriques de l'email
    safe_id = "".join(c if c.isalnum() or c in "._-" else "_" for c in account_id)
    d = ORG_MODEL_DIR / safe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def count_org_validated_samples(account_id: str) -> int:
    all_features, all_labels = build_retraining_dataset("reseau")
    # build_retraining_dataset ne filtre pas par compte a ce stade (voir learning_db.py) -
    # filtrage par validated_by fait ici en relisant les lots bruts pour la tracabilite.
    from core.learning_db import LEARNING_DB_DIR
    d = LEARNING_DB_DIR / "reseau"
    if not d.exists():
        return 0
    count = 0
    for batch_file in d.glob("*.jsonl"):
        with open(batch_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("validated_by") == account_id:
                    count += 1
    return count


def _load_org_samples(account_id: str):
    from core.learning_db import LEARNING_DB_DIR
    d = LEARNING_DB_DIR / "reseau"
    features, labels = [], []
    if not d.exists():
        return features, labels
    for batch_file in d.glob("*.jsonl"):
        with open(batch_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("validated_by") == account_id:
                    features.append(entry["features"])
                    labels.append(entry["label"])
    return features, labels


def generate_enriched_model(account_id: str):
    """Genere et sauvegarde un modele enrichi pour ce compte. Leve ValueError
    si le nombre d'echantillons valides est insuffisant."""
    n_samples = count_org_validated_samples(account_id)
    if n_samples < MIN_SAMPLES_REQUIRED:
        raise ValueError(
            f"Pas assez d'echantillons valides ({n_samples}/{MIN_SAMPLES_REQUIRED} requis) "
            "pour generer un modele enrichi. Continuez a valider des predictions."
        )

    base_features = joblib.load(MODEL_DIR / "feature_names.joblib")
    base_selected = json.load(open(OUT_DIR / "best_model_info.json"))["features_used"]
    scaler = joblib.load(MODEL_DIR / "scaler.joblib")
    iqr_bounds = joblib.load(MODEL_DIR / "iqr_bounds.joblib")
    medians = joblib.load(MODEL_DIR / "imputation_medians.joblib")

    X_train_base = pd.read_csv(OUT_DIR / "X_train_raw.csv")
    y_train_base = pd.read_csv(OUT_DIR / "y_train.csv").iloc[:, 0]

    org_feats, org_labels = _load_org_samples(account_id)
    X_org = pd.DataFrame(org_feats)
    for col in base_features:
        if col not in X_org.columns:
            X_org[col] = medians[col]
    X_org = X_org[base_features]
    y_org = pd.Series(org_labels)

    # Preprocessing identique au pipeline de base (mêmes bornes IQR + scaler déjà appris,
    # jamais reappris ici - coherence garantie avec le modele de base)
    def preprocess(df):
        df = df.copy()
        for col in base_features:
            df[col] = df[col].fillna(medians[col])
            low, high = iqr_bounds[col]
            df[col] = df[col].clip(lower=low, upper=high)
        return pd.DataFrame(scaler.transform(df[base_features]), columns=base_features)[base_selected]

    X_train_s = preprocess(X_train_base)
    X_org_s = preprocess(X_org)

    X_combined = pd.concat([X_train_s, X_org_s], ignore_index=True)
    y_combined = pd.concat([y_train_base, y_org], ignore_index=True)
    # Poids : echantillons de l'organisation comptent plus lourd (signal specifique
    # a son contexte reseau), sans pour autant ecraser le socle commun.
    sample_weight = np.concatenate([
        np.ones(len(X_train_s)), np.full(len(X_org_s), ORG_SAMPLE_WEIGHT),
    ])

    param_grid = {"max_depth": [4, 6, 8, 10], "min_samples_leaf": [1, 2, 4]}
    grid = GridSearchCV(DecisionTreeClassifier(random_state=42), param_grid, cv=3, scoring="f1_macro", n_jobs=-1)
    grid.fit(X_combined, y_combined, sample_weight=sample_weight)
    enriched_model = grid.best_estimator_

    # Evaluation sur le MEME jeu de test que le modele de base (jamais vu a l'entrainement,
    # ni du socle ni de l'organisation) pour une comparaison honnete.
    X_test_base = pd.read_csv(OUT_DIR / "X_test_raw.csv")
    y_test_base = pd.read_csv(OUT_DIR / "y_test.csv").iloc[:, 0]
    X_test_s = preprocess(X_test_base)
    base_model = joblib.load(MODEL_DIR / "best_model.joblib")

    preds_enriched = enriched_model.predict(X_test_s)
    preds_base = base_model.predict(X_test_s[base_selected]) if set(base_selected) <= set(X_test_s.columns) else base_model.predict(X_test_s)

    metrics = {
        "n_org_samples_used": n_samples,
        "accuracy_enriched": round(accuracy_score(y_test_base, preds_enriched), 4),
        "f1_macro_enriched": round(f1_score(y_test_base, preds_enriched, average="macro"), 4),
        "accuracy_base_reference": round(accuracy_score(y_test_base, preds_base), 4),
        "f1_macro_base_reference": round(f1_score(y_test_base, preds_base, average="macro"), 4),
        "generated_at": pd.Timestamp.now().isoformat(),
    }

    d = _account_dir(account_id)
    joblib.dump(enriched_model, d / "model_enrichi.joblib")
    with open(d / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    return metrics


def get_enriched_model_status(account_id: str) -> dict:
    d = _account_dir(account_id)
    metrics_path = d / "metrics.json"
    n_samples = count_org_validated_samples(account_id)
    if not metrics_path.exists():
        return {"exists": False, "n_org_samples_available": n_samples, "min_required": MIN_SAMPLES_REQUIRED}
    with open(metrics_path) as f:
        metrics = json.load(f)
    return {"exists": True, "n_org_samples_available": n_samples, "min_required": MIN_SAMPLES_REQUIRED, **metrics}
