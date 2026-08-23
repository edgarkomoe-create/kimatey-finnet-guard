"""
Etape 3 : Selection de variables / Elagage
- RFE (Recursive Feature Elimination) pour selectionner les variables les plus
  predictives, appliquee aux 4 modeles "boite noire/lineaire"
  (Regression Logistique, KNN, Naive Bayes, SVM).
- Elagage par cout-complexite (ccp_alpha) pour l'Arbre de Decision, choisi par
  validation croisee.
Comparaison des performances (metriques + AUC) avec le modele complet (Etape 2).
"""
import json
import time
import warnings
warnings.filterwarnings("ignore")

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.feature_selection import RFE
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

from utils import load_train_test, evaluate_model, save_results_table, OUT_DIR, FIG_DIR
from baseline_models import get_svm_subsample, SVM_TRAIN_SIZE

N_FEATURES_TO_SELECT = 5


def run_rfe_selection(X_train, y_train):
    """RFE avec Regression Logistique comme estimateur de base (rapide, stable)."""
    estimator = LogisticRegression(solver="lbfgs", max_iter=2000, random_state=42)
    rfe = RFE(estimator, n_features_to_select=N_FEATURES_TO_SELECT)
    rfe.fit(X_train, y_train)
    ranking = pd.Series(rfe.ranking_, index=X_train.columns).sort_values()
    selected = X_train.columns[rfe.support_].tolist()
    return selected, ranking


def run_tree_pruning(X_train, y_train, X_test, y_test):
    """Elagage par cout-complexite (ccp_alpha) choisi par validation croisee (5 plis)."""
    base_tree = DecisionTreeClassifier(random_state=42)
    path = base_tree.cost_complexity_pruning_path(X_train, y_train)
    ccp_alphas = path.ccp_alphas
    # sous-echantillonner les alphas pour limiter le nombre de CV (garder ~40 valeurs)
    if len(ccp_alphas) > 40:
        idx = np.linspace(0, len(ccp_alphas) - 1, 40).astype(int)
        ccp_alphas = ccp_alphas[idx]

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    mean_scores = []
    for alpha in ccp_alphas:
        clf = DecisionTreeClassifier(random_state=42, ccp_alpha=alpha)
        scores = cross_val_score(clf, X_train, y_train, cv=skf, scoring="accuracy", n_jobs=-1)
        mean_scores.append(scores.mean())

    best_idx = int(np.argmax(mean_scores))
    best_alpha = ccp_alphas[best_idx]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(ccp_alphas, mean_scores, marker="o", markersize=3)
    ax.axvline(best_alpha, color="red", linestyle="--", label=f"alpha optimal={best_alpha:.5f}")
    ax.set_xlabel("ccp_alpha")
    ax.set_ylabel("Exactitude moyenne (CV 5 plis)")
    ax.set_title("Elagage par cout-complexite - Arbre de Decision")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ccp_alpha_curve.png", dpi=120)
    plt.close(fig)

    pruned_tree = DecisionTreeClassifier(random_state=42, ccp_alpha=best_alpha)
    pruned_tree.fit(X_train, y_train)

    full_tree = DecisionTreeClassifier(random_state=42)
    full_tree.fit(X_train, y_train)

    info = {
        "best_ccp_alpha": float(best_alpha),
        "n_nodes_full_tree": int(full_tree.tree_.node_count),
        "depth_full_tree": int(full_tree.get_depth()),
        "n_nodes_pruned_tree": int(pruned_tree.tree_.node_count),
        "depth_pruned_tree": int(pruned_tree.get_depth()),
    }
    return pruned_tree, info


def main():
    X_train, X_test, y_train, y_test = load_train_test(raw=False)
    (OUT_DIR / "models" / "reduced").mkdir(parents=True, exist_ok=True)

    # ---- RFE : selection de variables ----
    print("=== Selection de variables (RFE) ===")
    selected_features, ranking = run_rfe_selection(X_train, y_train)
    print(f"Variables retenues ({N_FEATURES_TO_SELECT}/{len(X_train.columns)}) : {selected_features}")
    print("\nClassement complet des variables (1 = retenue) :")
    print(ranking.to_string())
    ranking.to_csv(OUT_DIR / "rfe_ranking.csv", header=["rang"])

    X_train_sel = X_train[selected_features]
    X_test_sel = X_test[selected_features]

    models = {
        "Regression_Logistique_reduit": LogisticRegression(solver="lbfgs", max_iter=2000, random_state=42),
        "KNN_reduit": KNeighborsClassifier(n_neighbors=5, n_jobs=-1),
        "Naive_Bayes_Gaussien_reduit": GaussianNB(),
        "SVM_reduit": SVC(kernel="rbf", probability=True, random_state=42),
    }

    results = []
    for name, model in models.items():
        print(f"\n--- Entrainement (variables reduites) : {name} ---")
        t0 = time.time()
        if "SVM" in name:
            X_fit, y_fit = get_svm_subsample(X_train_sel, y_train)
            model.fit(X_fit, y_fit)
        else:
            model.fit(X_train_sel, y_train)
        fit_time = time.time() - t0
        y_pred = model.predict(X_test_sel)
        y_proba = model.predict_proba(X_test_sel) if hasattr(model, "predict_proba") else None
        metrics = evaluate_model(name, model, X_test_sel, y_test, y_pred, y_proba, out_subdir="reduced")
        metrics["fit_time_sec"] = round(fit_time, 2)
        results.append(metrics)
        joblib.dump(model, OUT_DIR / "models" / "reduced" / f"{name}.joblib")
        print(f"  Exactitude={metrics['accuracy']}, F1-macro={metrics['f1_macro']}, AUC-macro={metrics['auc_macro']}")

    # ---- Elagage cout-complexite pour l'arbre ----
    print("\n=== Elagage par cout-complexite (Arbre de Decision) ===")
    pruned_tree, tree_info = run_tree_pruning(X_train, y_train, X_test, y_test)
    y_pred = pruned_tree.predict(X_test)
    y_proba = pruned_tree.predict_proba(X_test)
    tree_metrics = evaluate_model("Arbre_Decision_elague", pruned_tree, X_test, y_test, y_pred, y_proba, out_subdir="reduced")
    tree_metrics.update(tree_info)
    results.append(tree_metrics)
    joblib.dump(pruned_tree, OUT_DIR / "models" / "reduced" / "Arbre_Decision_elague.joblib")
    print(json.dumps(tree_info, indent=2))
    print(f"Exactitude arbre elague={tree_metrics['accuracy']}, F1-macro={tree_metrics['f1_macro']}")

    df = save_results_table(results, OUT_DIR / "reduced_results.csv")
    print("\n" + "=" * 70)
    print("RESULTATS APRES SELECTION DE VARIABLES / ELAGAGE")
    print("=" * 70)
    print(df.to_string(index=False))

    # ---- Comparaison baseline vs reduit ----
    baseline_df = pd.read_csv(OUT_DIR / "baseline_results.csv")
    comparison_rows = []
    pairs = [
        ("Regression_Logistique", "Regression_Logistique_reduit"),
        ("KNN", "KNN_reduit"),
        ("Naive_Bayes_Gaussien", "Naive_Bayes_Gaussien_reduit"),
        ("SVM", "SVM_reduit"),
        ("Arbre_Decision", "Arbre_Decision_elague"),
    ]
    for base_name, red_name in pairs:
        b = baseline_df[baseline_df["Modele"] == base_name].iloc[0]
        r = df[df["Modele"] == red_name].iloc[0]
        comparison_rows.append({
            "Modele": base_name,
            "Exactitude_complet": b["Exactitude"], "Exactitude_reduit": r["Exactitude"],
            "F1_complet": b["F1-score (macro)"], "F1_reduit": r["F1-score (macro)"],
            "AUC_complet": b["AUC (macro)"], "AUC_reduit": r["AUC (macro)"],
        })
    comp_df = pd.DataFrame(comparison_rows)
    comp_df.to_csv(OUT_DIR / "comparison_step3.csv", index=False)
    print("\nComparaison modele complet (9 var.) vs reduit/elague :")
    print(comp_df.to_string(index=False))

    with open(OUT_DIR / "selected_features.json", "w") as f:
        json.dump({"selected_features": selected_features, "n_selected": N_FEATURES_TO_SELECT}, f, indent=2)


if __name__ == "__main__":
    main()
