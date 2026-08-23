"""
Etape 2 : Modelisation de base (Baseline - Modele complet)
5 algorithmes : Regression Logistique Multinomiale, KNN, Naive Bayes Gaussien,
SVM, Arbre de Classification.
"""
import time
import json
import warnings
warnings.filterwarnings("ignore")

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split

from utils import load_train_test, evaluate_model, save_results_table, OUT_DIR

# Le SVM (kernel RBF, probability=True) a une complexite proche de O(n^2 - n^3).
# Sur 40 000 echantillons l'entrainement complet est intraitable en temps raisonnable ;
# on utilise donc un sous-echantillon stratifie de la base d'entrainement pour le SVM
# uniquement (pratique standard en contexte Big Data), l'evaluation restant faite
# sur l'integralite du jeu de test (10 000 echantillons).
SVM_TRAIN_SIZE = 8000


def get_svm_subsample(X_train, y_train, n=SVM_TRAIN_SIZE, seed=42):
    if len(X_train) <= n:
        return X_train, y_train
    X_sub, _, y_sub, _ = train_test_split(
        X_train, y_train, train_size=n, stratify=y_train, random_state=seed
    )
    return X_sub, y_sub


def main():
    X_train, X_test, y_train, y_test = load_train_test(raw=False)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")

    models = {
        "Regression_Logistique": LogisticRegression(
            solver="lbfgs", max_iter=2000, random_state=42
        ),
        "KNN": KNeighborsClassifier(n_neighbors=5, n_jobs=-1),
        "Naive_Bayes_Gaussien": GaussianNB(),
        "SVM": SVC(kernel="rbf", probability=True, random_state=42),
        "Arbre_Decision": DecisionTreeClassifier(random_state=42),
    }

    results = []
    timings = {}
    (OUT_DIR / "models" / "baseline").mkdir(parents=True, exist_ok=True)

    for name, model in models.items():
        print(f"\n--- Entrainement : {name} ---")
        t0 = time.time()
        if name == "SVM":
            X_fit, y_fit = get_svm_subsample(X_train, y_train)
            print(f"  (sous-echantillon SVM: {len(X_fit)} lignes)")
            model.fit(X_fit, y_fit)
        else:
            model.fit(X_train, y_train)
        fit_time = time.time() - t0

        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None

        metrics = evaluate_model(name, model, X_test, y_test, y_pred, y_proba, out_subdir="baseline")
        metrics["fit_time_sec"] = round(fit_time, 2)
        results.append(metrics)
        timings[name] = round(fit_time, 2)

        joblib.dump(model, OUT_DIR / "models" / "baseline" / f"{name}.joblib")
        print(f"  Exactitude={metrics['accuracy']}, F1-macro={metrics['f1_macro']}, "
              f"AUC-macro={metrics['auc_macro']}, temps={fit_time:.1f}s")

    df = save_results_table(results, OUT_DIR / "baseline_results.csv")
    print("\n" + "=" * 70)
    print("RESULTATS BASELINE (5 algorithmes - modele complet)")
    print("=" * 70)
    print(df.to_string(index=False))

    with open(OUT_DIR / "baseline_timings.json", "w") as f:
        json.dump(timings, f, indent=2)


if __name__ == "__main__":
    main()
