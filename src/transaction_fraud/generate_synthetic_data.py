"""
Generateur de donnees SYNTHETIQUES de transactions mobile money.

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


def generate(n=8000, seed=42, fraud_rate=0.12):
    """Genere n transactions synthetiques. fraud_rate ~ proportion cible de fraude
    (approximative : le bruit ajoute fait varier le taux reel obtenu)."""
    rng = np.random.default_rng(seed)
    n_fraud = int(n * fraud_rate)
    n_legit = n - n_fraud

    def legit_block(n):
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

    def fraud_block(n):
        return pd.DataFrame({
            "Montant": rng.gamma(shape=2.0, scale=25000, size=n).round(0),
            "Ecart_Montant_Habituel": rng.normal(4.5, 1.8, n).clip(0.1, None),
            "Nouveau_Destinataire": rng.binomial(1, 0.85, n),
            "Heure_Transaction": rng.choice(list(range(0, 6)) + list(range(21, 24)), size=n),
            "Frequence_Transactions_24h": rng.poisson(5, n) + 1,
            "Delai_Depuis_Derniere_Min": rng.exponential(20, n).round(1),
            "Nb_Destinataires_Distincts_7j": rng.poisson(6, n) + 1,
            "Changement_Appareil": rng.binomial(1, 0.6, n),
        })

    df_legit = legit_block(n_legit)
    df_legit[TARGET] = 0
    df_fraud = fraud_block(n_fraud)
    df_fraud[TARGET] = 1

    df = pd.concat([df_legit, df_fraud], ignore_index=True)
    # Bruit d'etiquetage (5%) : evite un probleme trop facile / signal parfait,
    # plus realiste qu'un jeu de donnees jouet sans ambiguite.
    flip_mask = rng.random(len(df)) < 0.05
    df.loc[flip_mask, TARGET] = 1 - df.loc[flip_mask, TARGET]

    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate()
    out_path = OUT_DIR / "transactions_synthetiques.csv"
    df.to_csv(out_path, index=False)
    print(f"Genere : {len(df)} transactions synthetiques -> {out_path}")
    print(f"Taux de fraude reel obtenu : {df[TARGET].mean()*100:.1f}%")
