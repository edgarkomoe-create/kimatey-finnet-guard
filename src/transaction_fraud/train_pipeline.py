"""
Pipeline d'entrainement - module fraude transactionnelle (PROTOTYPE, donnees
synthetiques - voir generate_synthetic_data.py pour l'avertissement complet).

Reprend la meme methodologie que le pipeline reseau (src/preprocessing.py +
src/baseline_models.py + src/grid_search.py) : split stratifie 80/20,
standardisation apprise uniquement sur le train, comparaison de plusieurs
algorithmes, puis GridSearchCV sur le meilleur candidat.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from generate_synthetic_data import FEATURES, TARGET, generate

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "transaction_fraud"
MODEL_DIR = OUT_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def run():
    df = generate()
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Standardisation apprise uniquement sur le train (meme discipline que le pipeline reseau)
    scaler = StandardScaler()
    X_train_s = pd.DataFrame(scaler.fit_transform(X_train), columns=FEATURES)
    X_test_s = pd.DataFrame(scaler.transform(X_test), columns=FEATURES)

    # ---- Etape 1 : comparaison de plusieurs algorithmes (baseline) ----
    candidates = {
        "Regression_Logistique": LogisticRegression(max_iter=1000, random_state=42),
        "Arbre_Decision": DecisionTreeClassifier(random_state=42, max_depth=6),
        "Foret_Aleatoire": RandomForestClassifier(n_estimators=100, random_state=42, max_depth=8),
    }
    results = []
    for name, model in candidates.items():
        model.fit(X_train_s, y_train)
        preds = model.predict(X_test_s)
        proba = model.predict_proba(X_test_s)[:, 1]
        results.append({
            "Modele": name,
            "Exactitude": round(accuracy_score(y_test, preds), 4),
            "F1_Score": round(f1_score(y_test, preds), 4),
            "AUC": round(roc_auc_score(y_test, proba), 4),
        })
    df_results = pd.DataFrame(results).sort_values("F1_Score", ascending=False)
    df_results.to_csv(OUT_DIR / "comparaison_algorithmes.csv", index=False)
    print("Comparaison des algorithmes :\n", df_results.to_string(index=False))

    # ---- Etape 2 : GridSearchCV sur le meilleur candidat (Arbre de Decision, coherent
    # avec le choix du modele reseau - meme famille d'algorithme, facile a auditer) ----
    param_grid = {
        "max_depth": [4, 6, 8, 10],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
    }
    grid = GridSearchCV(
        DecisionTreeClassifier(random_state=42), param_grid, cv=5, scoring="f1", n_jobs=-1
    )
    grid.fit(X_train_s, y_train)
    best_model = grid.best_estimator_

    preds = best_model.predict(X_test_s)
    proba = best_model.predict_proba(X_test_s)[:, 1]
    final_metrics = {
        "name": "Arbre_Decision_optimise_transactions",
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "f1_score": round(f1_score(y_test, preds), 4),
        "auc": round(roc_auc_score(y_test, proba), 4),
        "best_params": grid.best_params_,
        "features_used": FEATURES,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "donnees": "SYNTHETIQUES - voir generate_synthetic_data.py, non entraine sur de vraies transactions",
    }
    print("\nModele final (optimise) :", json.dumps(final_metrics, indent=2, ensure_ascii=False))

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
