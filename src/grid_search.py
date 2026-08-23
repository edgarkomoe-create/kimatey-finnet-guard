"""
Etape 4 : Optimisation des hyperparametres par GridSearchCV
Validation croisee stratifiee a 5 plis, grille elargie par algorithme.
Optimisation menee sur l'espace de variables reduit (issu de l'Etape 3, RFE)
pour capitaliser sur le gain d'interpretabilite/performance observe.
Selection du modele optimal global sur la base de l'exactitude et de l'AUC.
"""
import json
import time
import warnings
warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from utils import load_train_test, evaluate_model, save_results_table, OUT_DIR
from baseline_models import get_svm_subsample

with open(OUT_DIR / "selected_features.json") as f:
    SELECTED_FEATURES = json.load(f)["selected_features"]

CV = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

PARAM_GRIDS = {
    "Regression_Logistique": {
        "estimator": LogisticRegression(solver="lbfgs", max_iter=3000, random_state=42),
        "grid": {"C": [0.01, 0.1, 1, 10, 100]},
    },
    "KNN": {
        "estimator": KNeighborsClassifier(n_jobs=-1),
        "grid": {
            "n_neighbors": [3, 5, 7, 9, 11],
            "weights": ["uniform", "distance"],
            "metric": ["euclidean", "manhattan"],
        },
    },
    "Naive_Bayes_Gaussien": {
        "estimator": GaussianNB(),
        "grid": {"var_smoothing": np.logspace(0, -9, 10)},
    },
    "SVM": {
        "estimator": SVC(kernel="rbf", random_state=42),
        "grid": {"C": [0.1, 1, 10, 100], "gamma": ["scale", 0.01, 0.1, 1]},
    },
    "Arbre_Decision": {
        "estimator": DecisionTreeClassifier(random_state=42),
        "grid": {
            "max_depth": [3, 5, 7, 10, None],
            "ccp_alpha": [0.0, 0.001, 0.005, 0.01],
            "min_samples_leaf": [1, 5, 10],
        },
    },
}


def main():
    X_train, X_test, y_train, y_test = load_train_test(raw=False)
    X_train, X_test = X_train[SELECTED_FEATURES], X_test[SELECTED_FEATURES]
    (OUT_DIR / "models" / "optimized").mkdir(parents=True, exist_ok=True)

    results = []
    best_params_log = {}

    for name, cfg in PARAM_GRIDS.items():
        print(f"\n=== GridSearchCV : {name} ===")
        t0 = time.time()

        if name == "SVM":
            X_fit, y_fit = get_svm_subsample(X_train, y_train, n=8000)
        else:
            X_fit, y_fit = X_train, y_train

        gs = GridSearchCV(
            cfg["estimator"], cfg["grid"], scoring="accuracy",
            cv=CV, n_jobs=-1, refit=True,
        )
        gs.fit(X_fit, y_fit)
        search_time = time.time() - t0
        print(f"  Meilleurs hyperparametres : {gs.best_params_}")
        print(f"  Meilleur score CV (accuracy) : {gs.best_score_:.4f}  (temps: {search_time:.1f}s)")

        best_model = gs.best_estimator_
        # Pour le SVM, re-instancier avec probability=True pour obtenir les scores de confiance
        if name == "SVM":
            best_model = SVC(probability=True, random_state=42, **gs.best_params_)
            best_model.fit(X_fit, y_fit)

        y_pred = best_model.predict(X_test)
        y_proba = best_model.predict_proba(X_test) if hasattr(best_model, "predict_proba") else None
        metrics = evaluate_model(name + "_optimise", best_model, X_test, y_test, y_pred, y_proba, out_subdir="optimized")
        metrics["best_params"] = gs.best_params_
        metrics["cv_best_score_accuracy"] = round(gs.best_score_, 4)
        metrics["search_time_sec"] = round(search_time, 2)
        results.append(metrics)
        best_params_log[name] = {"best_params": gs.best_params_, "cv_score": round(gs.best_score_, 4)}

        joblib.dump(best_model, OUT_DIR / "models" / "optimized" / f"{name}_optimise.joblib")
        print(f"  Test -> Exactitude={metrics['accuracy']}, F1-macro={metrics['f1_macro']}, AUC-macro={metrics['auc_macro']}")

    df = save_results_table(results, OUT_DIR / "optimized_results.csv")
    df["cv_best_score_accuracy"] = [r["cv_best_score_accuracy"] for r in results]
    df.to_csv(OUT_DIR / "optimized_results.csv", index=False)

    print("\n" + "=" * 70)
    print("RESULTATS APRES OPTIMISATION GRIDSEARCHCV")
    print("=" * 70)
    print(df.to_string(index=False))

    with open(OUT_DIR / "grid_search_best_params.json", "w") as f:
        json.dump(best_params_log, f, indent=2, default=str)

    # Selection du modele optimal global (exactitude puis AUC en cas d'egalite)
    best_row = df.sort_values(["Exactitude", "AUC (macro)"], ascending=False).iloc[0]
    best_model_name = best_row["Modele"].replace("_optimise", "")
    print(f"\n>>> MODELE OPTIMAL RETENU POUR LA GUI : {best_row['Modele']} "
          f"(Exactitude={best_row['Exactitude']}, AUC={best_row['AUC (macro)']})")

    best_model_obj = joblib.load(OUT_DIR / "models" / "optimized" / f"{best_row['Modele']}.joblib")
    joblib.dump(best_model_obj, OUT_DIR / "models" / "best_model.joblib")
    with open(OUT_DIR / "best_model_info.json", "w") as f:
        json.dump({
            "name": best_row["Modele"],
            "accuracy": float(best_row["Exactitude"]),
            "f1_macro": float(best_row["F1-score (macro)"]),
            "auc_macro": float(best_row["AUC (macro)"]),
            "features_used": SELECTED_FEATURES,
        }, f, indent=2)


if __name__ == "__main__":
    main()
