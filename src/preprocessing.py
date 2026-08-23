"""
Etape 1 : Pretraitement et nettoyage des donnees
- Imputation des valeurs manquantes par la mediane
- Traitement des valeurs aberrantes (outliers) par la methode IQR (ecretage/clipping)
- Division 80/20 stratifiee
- Standardisation (centrage-reduction)

Note methodologique : les statistiques de nettoyage (mediane, bornes IQR, moyenne/
ecart-type) sont calculees UNIQUEMENT sur l'ensemble d'entrainement puis appliquees
telles quelles a l'ensemble de test, afin d'eviter toute fuite d'information
(data leakage) entre les deux ensembles.
"""
import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

DATA_PATH = "data/Enterprise_Network_Traffic_BigData.csv"
OUT_DIR = Path("outputs")
FEATURES = [
    "Duree_Connexion", "Octets_Source_Vers_Dest", "Octets_Dest_Vers_Source",
    "Taux_Paquets_Secondes", "Fenetre_TCP_Moyenne", "Ports_Dest_Distincts",
    "Connexions_Simultanees", "Taux_Erreur_CheckSum", "Frequence_SYN_Flags",
]
TARGET = "Statut_Menace"


def load_data():
    df = pd.read_csv(DATA_PATH)
    df[TARGET] = df[TARGET].astype(str).str.strip().astype(int)
    return df


def iqr_bounds(train_df, columns, k=1.5):
    bounds = {}
    for col in columns:
        q1 = train_df[col].quantile(0.25)
        q3 = train_df[col].quantile(0.75)
        iqr = q3 - q1
        bounds[col] = (q1 - k * iqr, q3 + k * iqr)
    return bounds


def clip_outliers(df, bounds):
    df = df.copy()
    for col, (low, high) in bounds.items():
        df[col] = df[col].clip(lower=low, upper=high)
    return df


def main():
    OUT_DIR.mkdir(exist_ok=True)
    df = load_data()
    X = df[FEATURES]
    y = df[TARGET]

    # 1. Split stratifie 80/20 (AVANT calcul des stats de nettoyage -> pas de fuite)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    # 2. Imputation des valeurs manquantes par la mediane (calculee sur train)
    medians = X_train.median()
    n_missing_train = X_train.isna().sum().sum()
    n_missing_test = X_test.isna().sum().sum()
    X_train = X_train.fillna(medians)
    X_test = X_test.fillna(medians)

    # Sauvegarde des boxplots AVANT ecretage (pour le rapport)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    for ax, col in zip(axes.ravel(), FEATURES):
        ax.boxplot(X_train[col], vert=True)
        ax.set_title(col, fontsize=9)
    fig.suptitle("Distribution des variables (TRAIN) - AVANT ecretage IQR")
    fig.tight_layout()
    fig.savefig("outputs/figures/boxplots_avant_iqr.png", dpi=120)
    plt.close(fig)

    # 3. Traitement des outliers par IQR (bornes calculees sur train)
    bounds = iqr_bounds(X_train, FEATURES, k=1.5)
    n_clipped = {}
    for col, (low, high) in bounds.items():
        n_clipped[col] = int(((X_train[col] < low) | (X_train[col] > high)).sum())

    X_train = clip_outliers(X_train, bounds)
    X_test = clip_outliers(X_test, bounds)

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    for ax, col in zip(axes.ravel(), FEATURES):
        ax.boxplot(X_train[col], vert=True)
        ax.set_title(col, fontsize=9)
    fig.suptitle("Distribution des variables (TRAIN) - APRES ecretage IQR")
    fig.tight_layout()
    fig.savefig("outputs/figures/boxplots_apres_iqr.png", dpi=120)
    plt.close(fig)

    # 4. Standardisation (centrage-reduction), fit sur train uniquement
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train), columns=FEATURES, index=X_train.index
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test), columns=FEATURES, index=X_test.index
    )

    # Sauvegardes
    X_train_scaled.to_csv(OUT_DIR / "X_train.csv", index=False)
    X_test_scaled.to_csv(OUT_DIR / "X_test.csv", index=False)
    y_train.to_csv(OUT_DIR / "y_train.csv", index=False)
    y_test.to_csv(OUT_DIR / "y_test.csv", index=False)
    # Versions non standardisees (utiles pour l'arbre / interpretabilite)
    X_train.to_csv(OUT_DIR / "X_train_raw.csv", index=False)
    X_test.to_csv(OUT_DIR / "X_test_raw.csv", index=False)

    joblib.dump(scaler, OUT_DIR / "models" / "scaler.joblib")
    joblib.dump(medians.to_dict(), OUT_DIR / "models" / "imputation_medians.joblib")
    joblib.dump(bounds, OUT_DIR / "models" / "iqr_bounds.joblib")
    joblib.dump(FEATURES, OUT_DIR / "models" / "feature_names.joblib")

    summary = {
        "n_train": len(X_train), "n_test": len(X_test),
        "missing_values_imputed_train": int(n_missing_train),
        "missing_values_imputed_test": int(n_missing_test),
        "medians_used_for_imputation": medians.round(3).to_dict(),
        "iqr_bounds": {k: [round(v[0], 3), round(v[1], 3)] for k, v in bounds.items()},
        "n_outliers_clipped_per_feature_train": n_clipped,
        "class_distribution_train": y_train.value_counts().sort_index().to_dict(),
        "class_distribution_test": y_test.value_counts().sort_index().to_dict(),
    }
    with open(OUT_DIR / "preprocessing_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print("=" * 70)
    print("PRETRAITEMENT TERMINE")
    print("=" * 70)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")
    print(f"Valeurs manquantes imputees (train/test): {n_missing_train}/{n_missing_test}")
    print("Nombre de valeurs ecretees par variable (train):")
    for k, v in n_clipped.items():
        print(f"  {k}: {v}")
    print("\nFichiers sauvegardes dans outputs/")


if __name__ == "__main__":
    main()
