"""
Regenere les figures ROC / matrice de confusion du modele optimal en version
'sombre' (theme navy/teal), utilisees par le tableau de bord Streamlit.
Ne touche PAS aux figures originales (roc_<name>.png, cm_<name>.png), deja
utilisees par le rapport Word et le PowerPoint de soutenance : ce script cree
de nouveaux fichiers (roc_dashboard_dark.png, cm_dashboard_dark.png).
"""
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import confusion_matrix, roc_curve, auc
from sklearn.preprocessing import label_binarize

OUT_DIR = Path("outputs")
MODEL_DIR = OUT_DIR / "models"
FIG_DIR = OUT_DIR / "figures" / "optimized"

NAVY_LIGHT = "#132C53"
NAVY_MID = "#1D3A66"
TEAL = "#00D4B5"
GRID_COLOR = "#2A4A73"
TEXT_LIGHT = "#F5F7FA"

CLASS_NAMES = {0: "Normal", 1: "Scan de Ports", 2: "DDoS", 3: "Infiltration/Brute-Force"}
CLASSES = [0, 1, 2, 3]
CLASS_COLORS = {0: "#2ecc71", 1: "#f39c12", 2: "#e74c3c", 3: "#8e44ad"}


def style_dark(fig, ax):
    fig.patch.set_facecolor(NAVY_LIGHT)
    ax.set_facecolor(NAVY_LIGHT)
    ax.tick_params(colors=TEXT_LIGHT, labelsize=8)
    ax.xaxis.label.set_color(TEXT_LIGHT)
    ax.yaxis.label.set_color(TEXT_LIGHT)
    ax.title.set_color(TEXT_LIGHT)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)


def main():
    with open(OUT_DIR / "best_model_info.json") as f:
        info = json.load(f)
    features = info["features_used"]
    model = joblib.load(MODEL_DIR / "best_model.joblib")

    X_test = pd.read_csv(OUT_DIR / "X_test.csv")[features]
    y_test = pd.read_csv(OUT_DIR / "y_test.csv").squeeze("columns")

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)

    # --- Matrice de confusion (theme sombre) ---
    cm = confusion_matrix(y_test, y_pred, labels=CLASSES)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="viridis")
    ax.set_xticks(range(len(CLASSES)))
    ax.set_yticks(range(len(CLASSES)))
    ax.set_xticklabels([CLASS_NAMES[c] for c in CLASSES], rotation=45, ha="right")
    ax.set_yticklabels([CLASS_NAMES[c] for c in CLASSES])
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, cm[i, j], ha="center", va="center",
                     color="white" if cm[i, j] < cm.max() / 1.6 else "black", fontsize=9)
    ax.set_xlabel("Classe predite")
    ax.set_ylabel("Classe reelle")
    ax.set_title(f"Matrice de confusion - {info['name']}")
    cbar = fig.colorbar(im, ax=ax)
    cbar.ax.yaxis.set_tick_params(color=TEXT_LIGHT)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=TEXT_LIGHT)
    style_dark(fig, ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "cm_dashboard_dark.png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)

    # --- Courbes ROC One-vs-Rest (theme sombre) ---
    y_test_bin = label_binarize(y_test, classes=CLASSES)
    fig, ax = plt.subplots(figsize=(6, 5))
    for i, c in enumerate(CLASSES):
        fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_proba[:, i])
        roc_auc = auc(fpr, tpr)
        ax.plot(fpr, tpr, label=f"{CLASS_NAMES[c]} (AUC={roc_auc:.3f})", color=CLASS_COLORS[c], linewidth=2)
    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=0.9, color=GRID_COLOR)
    ax.set_xlabel("Taux de faux positifs")
    ax.set_ylabel("Taux de vrais positifs")
    ax.set_title(f"Courbes ROC (One-vs-Rest) - {info['name']}")
    legend = ax.legend(fontsize=8, facecolor=NAVY_MID, edgecolor=GRID_COLOR)
    for text in legend.get_texts():
        text.set_color(TEXT_LIGHT)
    style_dark(fig, ax)
    ax.grid(color=GRID_COLOR, linewidth=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "roc_dashboard_dark.png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)

    print("Figures sombres generees :")
    print(" -", FIG_DIR / "cm_dashboard_dark.png")
    print(" -", FIG_DIR / "roc_dashboard_dark.png")


if __name__ == "__main__":
    main()
