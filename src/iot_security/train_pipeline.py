"""
Pipeline d'entrainement - module Securite IIoT (4e domaine Kimatey FinNet Guard).

Donnees : jeu de donnees IIoT reel (Datasense-IIoT-2025), 685 671 echantillons,
41 variables numeriques (retenues apres reduction de multicolinearite par VIF -
voir le notebook source Article_iiot.ipynb pour le detail de cette etape prealable,
menee en amont de ce script). Cible : label2 (8 categories : benign, recon, dos,
ddos, mitm, malware, web, bruteforce - ratio de desequilibre 66:1, gerable sans
sur-echantillonnage synthetique).

"Harnais ajustable et adaptatif" : la strategie de gestion du desequilibre de
classes n'est PAS figee dans le code - c'est un parametre du pipeline
(STRATEGIE_DESEQUILIBRE ci-dessous), au meme titre que le seuil de sensibilite
(core/sensitivity.py) est ajustable par compte pour le modele reseau. Objectif :
pouvoir comparer objectivement plusieurs strategies (poids de classes, aucune
correction, sur-echantillonnage futur) sans reecrire le pipeline a chaque fois -
et documenter honnetement dans l'article laquelle a ete retenue et pourquoi,
sur la base de resultats reels plutot que d'un choix a priori.

Reprend la meme methodologie que les pipelines Reseau et Transactions : split
stratifie 80/20, standardisation apprise uniquement sur le train, comparaison
de plusieurs algorithmes evalues par validation croisee stratifiee sur F1 macro
(jamais l'accuracy seule - trompeuse ici aussi, ~58% de trafic benin), puis
GridSearchCV sur le meilleur candidat.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "iot_security"
MODEL_DIR = OUT_DIR / "models"
TARGET = "label2"

# ==========================================================================
# LE HARNAIS AJUSTABLE : la strategie de gestion du desequilibre se choisit
# ici, sans toucher au reste du pipeline. Options actuellement supportees :
#   - "class_weight" : ponderation inversement proportionnelle a la frequence
#     de chaque classe (defaut - suffisant pour un ratio 66:1, pas de risque
#     de sur-apprentissage sur des donnees synthetiques).
#   - "aucune" : aucune correction - sert de reference pour mesurer l'apport
#     reel de la ponderation (comparaison honnete, pas suppose).
# D'autres strategies (ex: SMOTE) pourront s'ajouter ici plus tard SI et
# seulement si les resultats reels avec class_weight montrent un besoin non
# couvert sur certaines classes - jamais ajoutees par anticipation.
# ==========================================================================
STRATEGIE_DESEQUILIBRE = "class_weight"


def get_class_weight_param(strategie: str):
    """Traduit la strategie choisie en parametre scikit-learn - un seul
    endroit a modifier pour changer la strategie de tout le pipeline."""
    if strategie == "class_weight":
        return "balanced"
    elif strategie == "aucune":
        return None
    else:
        raise ValueError(f"Strategie de desequilibre inconnue : {strategie!r}")


def load_data(chemin_csv: str) -> pd.DataFrame:
    """Charge l'echantillon exporte depuis le notebook source (voir
    Article_iiot.ipynb : export post-VIF, stratifie sur label2)."""
    df = pd.read_csv(chemin_csv)
    if TARGET not in df.columns:
        raise ValueError(f"Colonne cible '{TARGET}' absente du fichier. Colonnes trouvees : {list(df.columns)}")
    return df


def preprocess(df: pd.DataFrame):
    """Split stratifie + standardisation apprise UNIQUEMENT sur le train -
    meme discipline anti-fuite de donnees que les pipelines Reseau et
    Transactions (voir Partie 3.2 du document technique Kimatey)."""
    features = [c for c in df.columns if c != TARGET]
    X = df[features]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=features, index=X_train.index)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=features, index=X_test.index)

    return X_train_scaled, X_test_scaled, y_train, y_test, scaler, features


def comparer_algorithmes(X_train, y_train, strategie: str, cv=5):
    """Compare plusieurs familles d'algorithmes par validation croisee
    stratifiee sur F1 macro (jamais l'accuracy seule - ~58% de benin rendrait
    un modele naif trompeusement performant). Chaque candidat recoit la
    strategie de desequilibre choisie via get_class_weight_param()."""
    class_weight = get_class_weight_param(strategie)
    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)

    candidats = {
        "Regression_Logistique": LogisticRegression(
            class_weight=class_weight, max_iter=1000, random_state=42,
        ),
        "Arbre_Decision": DecisionTreeClassifier(
            class_weight=class_weight, random_state=42,
        ),
        "Foret_Aleatoire": RandomForestClassifier(
            class_weight=class_weight, n_estimators=100, random_state=42, n_jobs=-1,
        ),
        "Gradient_Boosting": HistGradientBoostingClassifier(
            class_weight=class_weight, random_state=42,
        ),
    }

    resultats = []
    for nom, modele in candidats.items():
        scores = cross_val_score(modele, X_train, y_train, cv=skf, scoring="f1_macro", n_jobs=-1)
        resultats.append({"Modele": nom, "F1_macro_CV_moyenne": scores.mean(), "F1_macro_CV_ecart_type": scores.std()})
        print(f"{nom} ({strategie}) : F1 macro CV = {scores.mean():.4f} (+/- {scores.std():.4f})")

    return pd.DataFrame(resultats).sort_values("F1_macro_CV_moyenne", ascending=False)


GRILLES_HYPERPARAMETRES = {
    "Regression_Logistique": {"estimator": LogisticRegression, "grid": {"C": [0.1, 1.0, 10.0]}},
    "Arbre_Decision": {"estimator": DecisionTreeClassifier, "grid": {"max_depth": [5, 10, 15, None]}},
    "Foret_Aleatoire": {"estimator": RandomForestClassifier, "grid": {"n_estimators": [100], "max_depth": [15, None]}},
    "Gradient_Boosting": {"estimator": HistGradientBoostingClassifier, "grid": {"max_depth": [None, 10, 20], "learning_rate": [0.05, 0.1, 0.2]}},
}


def optimiser_meilleur_modele(nom_modele: str, X_train, y_train, strategie: str, cv=5):
    """GridSearchCV sur le candidat reellement vainqueur de la comparaison
    (pas un choix par defaut) - meme principe que le pipeline Reseau."""
    class_weight = get_class_weight_param(strategie)
    config = GRILLES_HYPERPARAMETRES[nom_modele]
    estimateur_kwargs = {"random_state": 42}
    if nom_modele != "Foret_Aleatoire" or True:
        estimateur_kwargs["class_weight"] = class_weight

    skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)

    gs = GridSearchCV(
        config["estimator"](**estimateur_kwargs), config["grid"],
        scoring="f1_macro", cv=skf, n_jobs=-1, refit=True,
    )
    gs.fit(X_train, y_train)
    print(f"Meilleurs hyperparametres : {gs.best_params_}")
    print(f"Meilleur score CV (F1 macro) : {gs.best_score_:.4f}")
    return gs.best_estimator_, gs.best_params_, gs.best_score_


def entrainer(chemin_csv: str, strategie: str = STRATEGIE_DESEQUILIBRE):
    """Point d'entree complet du pipeline - execute toutes les etapes et
    sauvegarde les artefacts, comme les pipelines Reseau et Transactions."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== Chargement des donnees ({chemin_csv}) ===")
    df = load_data(chemin_csv)
    print(f"{df.shape[0]} lignes, {df.shape[1]} colonnes.")
    print(f"\nDistribution de la cible ({TARGET}) :")
    print(df[TARGET].value_counts())

    print(f"\n=== Pretraitement (split stratifie 80/20 + standardisation train-only) ===")
    X_train, X_test, y_train, y_test, scaler, features = preprocess(df)

    print(f"\n=== Comparaison d'algorithmes (strategie de desequilibre : {strategie}) ===")
    comparaison = comparer_algorithmes(X_train, y_train, strategie)
    print(comparaison)

    meilleur_nom = comparaison.iloc[0]["Modele"]
    print(f"\n=== Optimisation du meilleur candidat : {meilleur_nom} ===")
    meilleur_modele, meilleurs_params, meilleur_score_cv = optimiser_meilleur_modele(
        meilleur_nom, X_train, y_train, strategie,
    )

    print(f"\n=== Evaluation finale sur le jeu de test (jamais vu pendant l'entrainement) ===")
    y_pred = meilleur_modele.predict(X_test)
    rapport = classification_report(y_test, y_pred, output_dict=True)
    print(classification_report(y_test, y_pred))
    f1_macro_test = f1_score(y_test, y_pred, average="macro")
    print(f"F1 macro (test) : {f1_macro_test:.4f}")

    # Sauvegarde des artefacts - memes conventions que Reseau/Transactions
    joblib.dump(meilleur_modele, MODEL_DIR / "best_model_iot.joblib")
    joblib.dump(scaler, MODEL_DIR / "scaler_iot.joblib")
    joblib.dump(features, MODEL_DIR / "feature_names_iot.joblib")

    info = {
        "name": meilleur_nom,
        "strategie_desequilibre": strategie,
        "f1_macro_cv": meilleur_score_cv,
        "f1_macro_test": f1_macro_test,
        "best_params": {k: str(v) for k, v in meilleurs_params.items()},
        "features_used": features,
        "target": TARGET,
        "classes": sorted(df[TARGET].unique().tolist()),
        "classification_report": rapport,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "sklearn_version": sklearn.__version__,
    }
    with open(OUT_DIR / "best_model_info_iot.json", "w") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    comparaison.to_csv(OUT_DIR / "comparaison_algorithmes_iot.csv", index=False)

    print(f"\n=== Termine. Artefacts sauvegardes dans {MODEL_DIR} ===")
    return meilleur_modele, info


if __name__ == "__main__":
    import sys
    chemin = sys.argv[1] if len(sys.argv) > 1 else "iot_echantillon_41var_100k_label2.csv"
    entrainer(chemin)
