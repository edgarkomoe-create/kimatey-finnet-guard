"""Fonctions utilitaires partagees : chargement des donnees, evaluation, graphiques."""
import json
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report, roc_curve, auc, roc_auc_score,
)
from sklearn.preprocessing import label_binarize

OUT_DIR = Path("outputs")
FIG_DIR = OUT_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = {
    0: "Normal",
    1: "Scan de Ports",
    2: "DDoS",
    3: "Infiltration/Brute-Force",
}
CLASSES = [0, 1, 2, 3]


def load_train_test(raw=False):
    suffix = "_raw" if raw else ""
    X_train = pd.read_csv(OUT_DIR / f"X_train{suffix}.csv")
    X_test = pd.read_csv(OUT_DIR / f"X_test{suffix}.csv")
    y_train = pd.read_csv(OUT_DIR / "y_train.csv").squeeze("columns")
    y_test = pd.read_csv(OUT_DIR / "y_test.csv").squeeze("columns")
    return X_train, X_test, y_train, y_test


def evaluate_model(name, model, X_test, y_test, y_pred, y_proba=None, out_subdir="baseline"):
    """Calcule les metriques, sauvegarde matrice de confusion + courbes ROC."""
    sub_dir = FIG_DIR / out_subdir
    sub_dir.mkdir(parents=True, exist_ok=True)

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
    rec = recall_score(y_test, y_pred, average="macro", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
    report = classification_report(y_test, y_pred, target_names=[CLASS_NAMES[c] for c in CLASSES], zero_division=0, output_dict=True)

    # Matrice de confusion
    cm = confusion_matrix(y_test, y_pred, labels=CLASSES)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(CLASSES)))
    ax.set_yticks(range(len(CLASSES)))
    ax.set_xticklabels([CLASS_NAMES[c] for c in CLASSES], rotation=45, ha="right")
    ax.set_yticklabels([CLASS_NAMES[c] for c in CLASSES])
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("Classe predite")
    ax.set_ylabel("Classe reelle")
    ax.set_title(f"Matrice de confusion - {name}")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(sub_dir / f"cm_{name}.png", dpi=120)
    plt.close(fig)

    auc_scores = {}
    macro_auc = None
    if y_proba is not None:
        y_test_bin = label_binarize(y_test, classes=CLASSES)
        fig, ax = plt.subplots(figsize=(6, 5))
        for i, c in enumerate(CLASSES):
            fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_proba[:, i])
            roc_auc = auc(fpr, tpr)
            auc_scores[CLASS_NAMES[c]] = roc_auc
            ax.plot(fpr, tpr, label=f"{CLASS_NAMES[c]} (AUC={roc_auc:.3f})")
        ax.plot([0, 1], [0, 1], "k--", linewidth=0.8)
        ax.set_xlabel("Taux de faux positifs")
        ax.set_ylabel("Taux de vrais positifs")
        ax.set_title(f"Courbes ROC (One-vs-Rest) - {name}")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(sub_dir / f"roc_{name}.png", dpi=120)
        plt.close(fig)
        try:
            macro_auc = roc_auc_score(y_test_bin, y_proba, average="macro", multi_class="ovr")
        except Exception:
            macro_auc = np.mean(list(auc_scores.values()))

    metrics = {
        "model": name,
        "accuracy": round(acc, 4),
        "precision_macro": round(prec, 4),
        "recall_macro": round(rec, 4),
        "f1_macro": round(f1, 4),
        "auc_macro": round(macro_auc, 4) if macro_auc is not None else None,
        "auc_per_class": {k: round(v, 4) for k, v in auc_scores.items()},
        "classification_report": report,
    }
    with open(sub_dir / f"metrics_{name}.json", "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    return metrics


def save_results_table(results, path):
    rows = []
    for r in results:
        rows.append({
            "Modele": r["model"],
            "Exactitude": r["accuracy"],
            "Precision (macro)": r["precision_macro"],
            "Rappel (macro)": r["recall_macro"],
            "F1-score (macro)": r["f1_macro"],
            "AUC (macro)": r["auc_macro"],
        })
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    return df
