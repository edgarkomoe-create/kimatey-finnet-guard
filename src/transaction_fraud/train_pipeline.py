"""
Pipeline d'entrainement - module fraude transactionnelle (PROTOTYPE, donnees
synthetiques - voir generate_synthetic_data.py pour l'avertissement complet).

Reprend la meme methodologie que le pipeline reseau (src/preprocessing.py +
src/baseline_models.py + src/grid_search.py) : split stratifie 80/20,
standardisation apprise uniquement sur le train, comparaison de plusieurs
algorithmes, puis GridSearchCV sur le meilleur candidat.

Changements v2 (vs la premiere version) :
- Les classes sont desormais fortement desequilibrees (~5% de fraude, voir
  generate_synthetic_data.py) : l'accuracy seule serait trompeuse. La
  selection du meilleur modele repose donc sur l'AUC-PR (average_precision),
  la metrique de reference en detection de fraude, evaluee par validation
  croisee stratifiee (5 folds) plutot que sur un seul split.
- class_weight="balanced" (ou equivalent) applique a tous les candidats
  pour compenser le desequilibre, au lieu de laisser les modeles ignorer
  la classe minoritaire.
- Un 4e candidat, HistGradientBoostingClassifier (scikit-learn natif, pas
  de nouvelle dependance), s'ajoute a la comparaison Regression Logistique /
  Arbre de Decision / Foret Aleatoire.
- Le GridSearchCV final s'applique desormais au candidat reellement
  vainqueur de la comparaison (plus seulement a l'Arbre de Decision par
  defaut), avec une grille d'hyperparametres adaptee a sa famille.
- Les artefacts sauvegardes (noms de fichiers, cles JSON) restent
  identiques a la version precedente pour ne rien casser cote API/Streamlit ;
  des metriques supplementaires (precision, recall, pr_auc) sont ajoutees
  au JSON sans retirer les cles existantes (accuracy, f1_score, auc).
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, f1_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from generate_synthetic_data import FEATURES, TARGET, generate

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "transaction_fraud"
MODEL_DIR = OUT_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Grilles d'hyperparametres pour l'etape 2 (GridSearchCV), une par famille
# de modele susceptible de gagner l'etape 1.
PARAM_GRIDS = {
    "Arbre_Decision": (
        DecisionTreeClassifier(random_state=42, class_weight="balanced"),
        {"max_depth": [4, 6, 8, 10], "min_samples_split": [2, 5, 10], "min_samples_leaf": [1, 2, 4]},
    ),
    "Foret_Aleatoire": (
        RandomForestClassifier(random_state=42, class_weight="balanced_subsample", n_jobs=-1),
        {"n_estimators": [150, 300], "max_depth": [8, 12, None], "min_samples_leaf": [1, 5, 10]},
    ),
    "Gradient_Boosting": (
        HistGradientBoostingClassifier(random_state=42, class_weight="balanced"),
        {"max_depth": [4, 6, None], "learning_rate": [0.05, 0.1], "max_iter": [150, 300]},
    ),
    "Regression_Logistique": (
        LogisticRegression(max_iter=2000, random_state=42, class_weight="balanced"),
        {"C": [0.1, 1.0, 10.0]},
    ),
}


def run():
    df = generate()
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)} lignes ({int(y_train.sum())} fraudes) | "
          f"Test: {len(X_test)} lignes ({int(y_test.sum())} fraudes)")

    # Standardisation apprise uniquement sur le train (meme discipline que le pipeline reseau)
    scaler = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train), columns=FEATURES)
    X_test_s = pd.DataFrame(scaler.transform(X_test), columns=FEATURES)

    # ---- Etape 1 : comparaison de plusieurs algorithmes par validation croisee ----
    # Metrique = AUC-PR (average_precision), adaptee au desequilibre de classes -
    # contrairement a l'accuracy, qui resterait haute meme pour un modele inutile.
    candidates = {name: model for name, (model, _) in PARAM_GRIDS.items()}
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    results = []
    for name, model in candidates.items():
        cv_scores = cross_val_score(model, X_train_s, y_train, cv=cv, scoring="average_precision", n_jobs=-1)
        model.fit(X_train_s, y_train)
        preds = model.predict(X_test_s)
        proba = model.predict_proba(X_test_s)[:, 1]
        results.append({
            "Modele": name,
            "AUC_PR_CV_moyenne": round(cv_scores.mean(), 4),
            "AUC_PR_CV_ecart_type": round(cv_scores.std(), 4),
            "Exactitude": round(accuracy_score(y_test, preds), 4),
            "F1_Score": round(f1_score(y_test, preds), 4),
            "AUC": round(roc_auc_score(y_test, proba), 4),
        })
    df_results = pd.DataFrame(results).sort_values("AUC_PR_CV_moyenne", ascending=False)
    df_results.to_csv(OUT_DIR / "comparaison_algorithmes.csv", index=False)
    print("\nComparaison des algorithmes (validation croisee, 5 folds, AUC-PR) :\n",
          df_results.to_string(index=False))

    best_name = df_results.iloc[0]["Modele"]
    print(f"\nMeilleur candidat (validation croisee) : {best_name}")

    # ---- Etape 2 : GridSearchCV sur le candidat reellement vainqueur ----
    base_model, param_grid = PARAM_GRIDS[best_name]
    grid = GridSearchCV(base_model, param_grid, cv=5, scoring="average_precision", n_jobs=-1)
    grid.fit(X_train_s, y_train)
    best_model = grid.best_estimator_

    preds = best_model.predict(X_test_s)
    proba = best_model.predict_proba(X_test_s)[:, 1]
    final_metrics = {
        "sklearn_version": sklearn.__version__,
        "name": f"{best_name}_optimise_transactions",
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "f1_score": round(f1_score(y_test, preds), 4),
        "auc": round(roc_auc_score(y_test, proba), 4),
        "precision": round(precision_score(y_test, preds, zero_division=0), 4),
        "recall": round(recall_score(y_test, preds, zero_division=0), 4),
        "pr_auc": round(average_precision_score(y_test, proba), 4),
        "best_params": {k: (v if not isinstance(v, (np.integer, np.floating)) else v.item())
                         for k, v in grid.best_params_.items()},
        "features_used": FEATURES,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "fraud_rate_train": round(float(y_train.mean()), 4),
        "algorithmes_compares": df_results.to_dict(orient="records"),
        "donnees": "SYNTHETIQUES - voir generate_synthetic_data.py, non entraine sur de vraies transactions",
    }
    print("\nModele final (optimise) :", json.dumps(
        {k: v for k, v in final_metrics.items() if k != "algorithmes_compares"},
        indent=2, ensure_ascii=False,
    ))

    # ---- Sauvegarde des artefacts (meme pattern que le modele reseau) ----
    joblib.dump(best_model, MODEL_DIR / "best_model_transactions.joblib")
    joblib.dump(scaler, MODEL_DIR / "scaler_transactions.joblib")
    joblib.dump(FEATURES, MODEL_DIR / "feature_names_transactions.joblib")
    joblib.dump(X_train.median().to_dict(), MODEL_DIR / "imputation_medians_transactions.joblib")
    with open(OUT_DIR / "best_model_info_transactions.json", "w") as f:
        json.dump(final_metrics, f, indent=2, ensure_ascii=False)

    print(f"\nArtefacts sauvegardes dans {MODEL_DIR}")


if __name__ == "__main__":
    run()
