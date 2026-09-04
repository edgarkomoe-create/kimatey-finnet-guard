"""
Regenere la matrice de confusion du modele Securite IIoT (Foret Aleatoire),
sur le vrai jeu de test (meme split que l'entrainement, random_state=42).

Necessite le fichier source des donnees d'entrainement completes (voir
docs/ROADMAP_MODELES_ADDITIONNELS.md, section 0) - non embarque dans le depot
(trop volumineux). A executer manuellement si besoin de regenerer la figure,
en pointant vers une copie locale du fichier fusionne et corrige (voir
train_pipeline.py pour le format exact attendu).

Usage : python src/iot_security/regen_confusion_matrix.py <chemin_donnees_completes.csv>
"""
import sys
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.iot_security.train_pipeline import load_data, preprocess, OUT_DIR, MODEL_DIR

NAVY_LIGHT = "#132C53"
TEXT_LIGHT = "#F5F7FA"
GRID_COLOR = "#2A4A7A"


def regenerer(chemin_donnees_completes: str):
    df = load_data(chemin_donnees_completes)
    X_train, X_test, y_train, y_test, scaler, features = preprocess(df)

    modele = joblib.load(MODEL_DIR / "best_model_iot.joblib")
    features_modele = joblib.load(MODEL_DIR / "feature_names_iot.joblib")
    assert features == features_modele, "Incoherence des variables - verifier le fichier source fourni."

    y_pred = modele.predict(X_test)
    classes = sorted(y_test.unique())
    cm = confusion_matrix(y_test, y_pred, labels=classes)
    cm_normalized = cm.astype("float") / cm.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=(9, 7.5))
    fig.patch.set_facecolor(NAVY_LIGHT)
    ax.set_facecolor(NAVY_LIGHT)

    im = ax.imshow(cm_normalized, cmap="YlGnBu", vmin=0, vmax=1)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.yaxis.set_tick_params(color=TEXT_LIGHT)
    plt.setp(plt.getp(cbar.ax, "yticklabels"), color=TEXT_LIGHT)
    cbar.set_label("Proportion (par ligne)", color=TEXT_LIGHT)

    ax.set_xticks(range(len(classes)))
    ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(classes, rotation=45, ha="right", color=TEXT_LIGHT, fontsize=10)
    ax.set_yticklabels(classes, color=TEXT_LIGHT, fontsize=10)
    ax.set_xlabel("Classe predite", color=TEXT_LIGHT, fontsize=11)
    ax.set_ylabel("Classe reelle", color=TEXT_LIGHT, fontsize=11)
    ax.set_title(
        "Matrice de confusion - Modele Securite IIoT (Foret Aleatoire)\n"
        f"Jeu de test reel, {len(y_test)} echantillons",
        color=TEXT_LIGHT, fontsize=12, pad=15,
    )

    for i in range(len(classes)):
        for j in range(len(classes)):
            valeur = cm[i, j]
            if valeur > 0:
                couleur_texte = "white" if cm_normalized[i, j] > 0.5 else TEXT_LIGHT
                ax.text(j, i, str(valeur), ha="center", va="center", color=couleur_texte, fontsize=8.5)

    ax.spines[:].set_color(GRID_COLOR)
    plt.tight_layout()
    sortie = OUT_DIR / "confusion_matrix_iot.png"
    plt.savefig(sortie, dpi=150, facecolor=NAVY_LIGHT, bbox_inches="tight")
    print(f"Matrice de confusion sauvegardee : {sortie}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python src/iot_security/regen_confusion_matrix.py <chemin_donnees_completes.csv>")
        sys.exit(1)
    regenerer(sys.argv[1])
