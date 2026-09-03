"""
Generateur de donnees SYNTHETIQUES de transactions mobile money (v3, calibree
sur des statistiques reelles BCEAO).

*** IMPORTANT - A LIRE AVANT TOUTE UTILISATION ***
Ce script ne lit AUCUNE vraie transaction et ne produit AUCUNE verite terrain
reelle (le label Fraude reste une regle de generation, pas une fraude
constatee). Objectif : demontrer qu'un pipeline de type "Kimatey" peut
s'appliquer a un second domaine (transactions, pas seulement flux reseau),
PAS pretendre detecter de la vraie fraude en production.

Tant qu'aucune vraie donnee de transaction (avec verite terrain fournie par
un operateur/institution partenaire) n'est disponible, le modele issu de ce
pipeline reste un prototype methodologique, a ne jamais presenter comme
valide sur des transactions reelles.

Changements v3 (vs v2) - calibration sur donnees reelles BCEAO :
Jusqu'ici, les montants et le taux de fraude etaient des ordres de grandeur
choisis a la main, sans ancrage local. La BCEAO (Banque Centrale des Etats
de l'Afrique de l'Ouest) publie chaque annee un rapport public et gratuit
sur les services financiers numeriques dans l'UEMOA, avec de vraies
statistiques agregees. Sources utilisees ici :

  - Rapport annuel UEMOA 2024 (bceao.int/fr/publications/rapport-annuel-
    sur-les-services-financiers-numeriques-dans-luemoa-2024) :
      * Valeur moyenne d'une transaction (Union) : 13 160 FCFA en 2024
      * Valeur moyenne d'une transaction en Cote d'Ivoire : 22 692 FCFA
      * Montant moyen d'un transfert de personne a personne (Union) :
        18 220 FCFA en 2024 (21 668 FCFA en 2021)
  - Rapport annuel UEMOA 2021 (bceao.int, PDF "...luemoa-a-fin-2021.pdf") :
    confirme un pattern de fraude specifiquement documente dans l'UEMOA,
    le "Bypass cash in" - fractionnement des depots clients par les
    distributeurs/agents en plusieurs petites transactions successives,
    pour toucher davantage de commissions (les baremes de commission sont
    souvent degressifs par palier). Le rapport 2021 mentionne aussi un
    "Graphique n°5 : Fraudes, incidents et gestion des reclamations
    clients" (donnees chiffrees non extractibles ici, presentees sous
    forme d'image dans le PDF).

Ce que cette calibration change concretement :
- Les montants des transactions LEGITIMES sont desormais centres sur la
  vraie moyenne d'un transfert P2P en Cote d'Ivoire (~18-22k FCFA), au lieu
  d'une valeur choisie sans reference (~16k FCFA, qui etait proche par
  coincidence mais non justifiee).
- Le sous-type de fraude "structuring" est renomme "bypass_cash_in" et
  recalibre pour refleter le VRAI pattern documente (rafale de petites
  transactions vers le meme destinataire, montants sous les paliers de
  commission usuels) plutot qu'un "montant juste sous un seuil unique"
  invente sans base documentaire.
- Le TAUX de fraude (5%) et les DEUX AUTRES sous-types (compte compromis,
  velocite/mules) restent des hypotheses non verifiees localement, faute
  de statistiques UEMOA publiquement chiffrees sur ce point precis - c'est
  la limite honnete qui subsiste meme apres cette calibration.
"""
import numpy as np
import pandas as pd
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "transaction_fraud"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Ancrage reel (BCEAO, rapport annuel UEMOA 2024, transfert P2P Cote d'Ivoire) :
# utilise pour calibrer la moyenne des montants de transactions legitimes.
MONTANT_MOYEN_REEL_P2P_CI_FCFA = 20_000  # entre 18 220 (Union) et 22 692 (CI, transaction moyenne tous types)

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
    # gamma(shape=2, scale) a pour moyenne 2*scale : scale choisi pour que la
    # moyenne corresponde au montant moyen reel d'un transfert P2P (BCEAO 2024).
    return pd.DataFrame({
        "Montant": rng.gamma(shape=2.0, scale=MONTANT_MOYEN_REEL_P2P_CI_FCFA / 2, size=n).round(0),
        "Ecart_Montant_Habituel": rng.normal(1.0, 0.25, n).clip(0.1, None),
        "Nouveau_Destinataire": rng.binomial(1, 0.15, n),
        "Heure_Transaction": rng.normal(14, 4, n).clip(0, 23).round(0),
        "Frequence_Transactions_24h": rng.poisson(1.5, n),
        "Delai_Depuis_Derniere_Min": rng.exponential(400, n).round(1),
        "Nb_Destinataires_Distincts_7j": rng.poisson(2, n),
        "Changement_Appareil": rng.binomial(1, 0.05, n),
    })


def _fraud_compte_compromis(n, rng):
    # Montant exprime comme multiple du montant moyen reel (~20k FCFA), pas
    # une valeur absolue arbitraire : un compte compromis est caracterise par
    # un ecart au comportement HABITUEL, pas par un seuil absolu universel.
    return pd.DataFrame({
        "Montant": rng.gamma(shape=2.2, scale=1.5 * MONTANT_MOYEN_REEL_P2P_CI_FCFA, size=n).round(0),
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
        "Montant": rng.gamma(shape=1.8, scale=0.75 * MONTANT_MOYEN_REEL_P2P_CI_FCFA, size=n).round(0),
        "Ecart_Montant_Habituel": rng.normal(1.8, 1.1, n).clip(0.1, None),
        "Nouveau_Destinataire": rng.binomial(1, 0.55, n),
        "Heure_Transaction": rng.integers(0, 24, size=n),
        "Frequence_Transactions_24h": rng.poisson(13, n) + 2,
        "Delai_Depuis_Derniere_Min": rng.exponential(7, n).round(1),
        "Nb_Destinataires_Distincts_7j": rng.poisson(10, n) + 2,
        "Changement_Appareil": rng.binomial(1, 0.15, n),
    })


def _fraud_bypass_cash_in(n, rng):
    """"Bypass cash in" (documente BCEAO, rapport UEMOA 2021) : un distributeur
    fractionne le depot d'un client en plusieurs transactions successives, sous
    les paliers habituels de commission, pour toucher davantage de commissions
    au total. Signature : rafale de PETITES transactions vers le MEME
    destinataire (le compte du client, pas de nouveaux destinataires), en tres
    peu de temps - a l'oppose du "velocite/mules" qui vise plusieurs
    destinataires distincts."""
    montant = rng.normal(0.4 * MONTANT_MOYEN_REEL_P2P_CI_FCFA, 0.08 * MONTANT_MOYEN_REEL_P2P_CI_FCFA, n)
    montant = montant.clip(1000, None)
    return pd.DataFrame({
        "Montant": montant.round(0),
        "Ecart_Montant_Habituel": rng.normal(0.4, 0.2, n).clip(0.05, None),  # montants plus PETITS qu'habituel
        "Nouveau_Destinataire": rng.binomial(1, 0.05, n),  # meme destinataire (le client lui-meme)
        "Heure_Transaction": rng.normal(11, 3, n).clip(6, 20).round(0),  # heures ouvrees, agent en activite
        "Frequence_Transactions_24h": rng.poisson(9, n) + 3,  # rafale caracteristique du fractionnement
        "Delai_Depuis_Derniere_Min": rng.exponential(4, n).round(1),  # tres rapproche
        "Nb_Destinataires_Distincts_7j": rng.poisson(1.5, n),  # PAS de nouveaux destinataires, contrairement aux mules
        "Changement_Appareil": rng.binomial(1, 0.1, n),
    })


def generate(n=15000, seed=42, fraud_rate=0.05):
    """Genere n transactions synthetiques. fraud_rate ~ proportion cible de fraude
    (approximative : le bruit ajoute fait varier le taux reel obtenu ; ce taux
    reste une hypothese non verifiee localement, voir docstring du module).
    La fraude est repartie entre 3 sous-types (compte compromis, velocite/mules,
    bypass cash in) pour eviter un signal trop uniforme."""
    rng = np.random.default_rng(seed)
    n_fraud = max(30, int(n * fraud_rate))
    n_legit = n - n_fraud

    n_compromis = n_fraud // 3
    n_velocite = n_fraud // 3
    n_bypass = n_fraud - n_compromis - n_velocite

    df_legit = _legit_block(n_legit, rng)
    df_legit[TARGET] = 0

    df_fraud = pd.concat([
        _fraud_compte_compromis(n_compromis, rng),
        _fraud_velocite_mules(n_velocite, rng),
        _fraud_bypass_cash_in(n_bypass, rng),
    ], ignore_index=True)
    df_fraud[TARGET] = 1

    df = pd.concat([df_legit, df_fraud], ignore_index=True)
    # Bruit d'etiquetage (3%) : evite un probleme trop facile / signal parfait,
    # plus realiste qu'un jeu de donnees jouet sans ambiguite.
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
