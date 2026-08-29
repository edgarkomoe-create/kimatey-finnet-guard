"""
Generateur de donnees SYNTHETIQUES de transactions mobile money (v2).

*** IMPORTANT - A LIRE AVANT TOUTE UTILISATION ***
Ce script ne lit AUCUNE vraie transaction. Il fabrique des donnees fictives
selon des regles de generation deliberement construites pour ressembler a de
la fraude transactionnelle plausible (montant inhabituel, nouveau destinataire,
heure atypique, frequence elevee...), avec du bruit ajoute pour eviter un
signal trop parfait. Objectif : demontrer qu'un pipeline de type "Kimatey"
peut s'appliquer a un second domaine (transactions, pas seulement flux
reseau), PAS pretendre detecter de la vraie fraude en production.

Tant qu'aucune vraie donnee de transaction (avec verite terrain fournie par
un operateur/institution partenaire) n'est disponible, le modele issu de ce
pipeline reste un prototype methodologique, a ne jamais presenter comme
valide sur des transactions reelles.

Changements v2 (vs la premiere version) :
- Taux de fraude par defaut abaisse de 12% a 5% : plus proche des ordres de
  grandeur observes en detection de fraude reelle (ex. IEEE-CIS ~3.5%,
  PaySim <1%). 12% etait artificiellement facile a apprendre.
- La fraude n'est plus un bloc homogene mais 3 sous-types distincts, pour
  eviter qu'un seul pattern trivial ne domine l'apprentissage :
    1. Compte compromis   : nouvel appareil + nouveau destinataire + montant eleve
    2. Velocite / mules    : rafale de transactions, nombreux destinataires distincts
    3. Structuring         : montants juste sous un seuil rond, heures calmes
- Volume par defaut augmente (8000 -> 15000) pour une meilleure stabilite
  statistique de la validation croisee dans train_pipeline.py.
"""
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "transaction_fraud"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURES = [
    "Montant",
    "Ecart_Montant_Habituel",       # ratio vs montant moyen historique de l'utilisateur
    "Nouveau_Destinataire",         # 1 si jamais envoye a ce destinataire avant, 0 sinon
    "Heure_Transaction",            # 0-23
    "Frequence_Transactions_24h",   # nombre de transactions dans les dernieres 24h
    "Delai_Depuis_Derniere_Min",    # minutes depuis la transaction precedente
    "Nb_Destinataires_Distincts_7j",
    "Changement_Appareil",          # 1 si appareil different de l'habituel, 0 sinon
]
TARGET = "Fraude"


def _legit_block(n, rng):
    return pd.DataFrame({
        "Montant": rng.gamma(shape=2.0, scale=8000, size=n).round(0),
        "Ecart_Montant_Habituel": rng.normal(1.0, 0.25, n).clip(0.1, None),
        "Nouveau_Destinataire": rng.binomial(1, 0.15, n),
        "Heure_Transaction": rng.normal(14, 4, n).clip(0, 23).round(0),
        "Frequence_Transactions_24h": rng.poisson(1.5, n),
        "Delai_Depuis_Derniere_Min": rng.exponential(400, n).round(1),
        "Nb_Destinataires_Distincts_7j": rng.poisson(2, n),
        "Changement_Appareil": rng.binomial(1, 0.05, n),
    })


def _fraud_compte_compromis(n, rng):
    return pd.DataFrame({
        "Montant": rng.gamma(shape=2.2, scale=30000, size=n).round(0),
        "Ecart_Montant_Habituel": rng.normal(4.8, 1.6, n).clip(0.1, None),
        "Nouveau_Destinataire": rng.binomial(1, 0.88, n),
        "Heure_Transaction": rng.choice(list(range(0, 6)) + list(range(22, 24)), size=n),
        "Frequence_Transactions_24h": rng.poisson(2.5, n),
        "Delai_Depuis_Derniere_Min": rng.exponential(25, n).round(1),
        "Nb_Destinataires_Distincts_7j": rng.poisson(2.5, n) + 1,
        "Changement_Appareil": rng.binomial(1, 0.8, n),
    })


def _fraud_velocite_mules(n, rng):
    return pd.DataFrame({
        "Montant": rng.gamma(shape=1.8, scale=15000, size=n).round(0),
        "Ecart_Montant_Habituel": rng.normal(1.8, 1.1, n).clip(0.1, None),
        "Nouveau_Destinataire": rng.binomial(1, 0.55, n),
        "Heure_Transaction": rng.integers(0, 24, size=n),
        "Frequence_Transactions_24h": rng.poisson(13, n) + 2,
        "Delai_Depuis_Derniere_Min": rng.exponential(7, n).round(1),
        "Nb_Destinataires_Distincts_7j": rng.poisson(10, n) + 2,
        "Changement_Appareil": rng.binomial(1, 0.15, n),
    })


def _fraud_structuring(n, rng):
    montant = rng.normal(95_000, 6_000, n).clip(50_000, 99_500)
    return pd.DataFrame({
        "Montant": montant.round(0),
        "Ecart_Montant_Habituel": rng.normal(0.9, 0.6, n).clip(0.1, None),
        "Nouveau_Destinataire": rng.binomial(1, 0.3, n),
        "Heure_Transaction": rng.choice(list(range(1, 5)), size=n),
        "Frequence_Transactions_24h": rng.poisson(4, n),
        "Delai_Depuis_Derniere_Min": rng.exponential(40, n).round(1),
        "Nb_Destinataires_Distincts_7j": rng.poisson(4, n),
        "Changement_Appareil": rng.binomial(1, 0.2, n),
    })


def generate(n=15000, seed=42, fraud_rate=0.05):
    """Genere n transactions synthetiques. fraud_rate ~ proportion cible de fraude
    (approximative : le bruit ajoute fait varier le taux reel obtenu). La
    fraude est repartie entre 3 sous-types (compte compromis, velocite/mules,
    structuring) pour eviter un signal trop uniforme."""
    rng = np.random.default_rng(seed)
    n_fraud = max(30, int(n * fraud_rate))
    n_legit = n - n_fraud

    n_compromis = n_fraud // 3
    n_velocite = n_fraud // 3
    n_structuring = n_fraud - n_compromis - n_velocite

    df_legit = _legit_block(n_legit, rng)
    df_legit[TARGET] = 0

    df_fraud = pd.concat([
        _fraud_compte_compromis(n_compromis, rng),
        _fraud_velocite_mules(n_velocite, rng),
        _fraud_structuring(n_structuring, rng),
    ], ignore_index=True)
    df_fraud[TARGET] = 1

    df = pd.concat([df_legit, df_fraud], ignore_index=True)
    # Bruit d'etiquetage (3%) : evite un probleme trop facile / signal parfait,
    # plus realiste qu'un jeu de donnees jouet sans ambiguite. Abaisse vs v1
    # (5%) car le chevauchement entre sous-types de fraude et cas legitimes
    # apporte deja de l'ambiguite naturelle.
    flip_mask = rng.random(len(df)) < 0.03
    df.loc[flip_mask, TARGET] = 1 - df.loc[flip_mask, TARGET]

    # Bornes realistes
    df["Montant"] = df["Montant"].clip(lower=100)
    df["Frequence_Transactions_24h"] = df["Frequence_Transactions_24h"].clip(lower=0)
    df["Nb_Destinataires_Distincts_7j"] = df["Nb_Destinataires_Distincts_7j"].clip(lower=0)
    df["Delai_Depuis_Derniere_Min"] = df["Delai_Depuis_Derniere_Min"].clip(lower=0.1)
    df["Heure_Transaction"] = df["Heure_Transaction"].astype(int) % 24

    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate()
    out_path = OUT_DIR / "transactions_synthetiques.csv"
    df.to_csv(out_path, index=False)
    print(f"Genere : {len(df)} transactions synthetiques -> {out_path}")
    print(f"Taux de fraude reel obtenu : {df[TARGET].mean()*100:.1f}%")
