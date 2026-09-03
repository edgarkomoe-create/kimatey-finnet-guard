# Extension a d'autres modeles de machine learning - feuille de route

## Contexte

Le projet a prouve, deux fois (detection reseau, fraude transactionnelle), une methodologie
reproductible pour ajouter un nouveau modele de machine learning au systeme. Ce document liste
les extensions envisageables, sans engagement de calendrier - a activer quand une vraie source
de donnees est disponible pour le domaine concerne.

## La recette reproductible (deja validee 2 fois)

1. **Generateur/source de donnees** - reelles si disponibles, sinon synthetiques et clairement
   etiquetees comme telles (jamais presentees comme valides en production sans donnees reelles).
2. **Pipeline d'entrainement** (`src/<domaine>/`) - meme structure que
   `src/preprocessing.py` + `src/baseline_models.py` + `src/grid_search.py` (reseau) ou
   `src/transaction_fraud/train_pipeline.py` (transactions) : split stratifie, standardisation
   apprise uniquement sur le train, comparaison de plusieurs algorithmes, GridSearchCV sur le
   meilleur candidat.
3. **Service de modele** (`api/<domaine>_model_service.py`) - meme pattern que
   `api/model_service.py` / `api/transaction_model_service.py` : chargement des artefacts,
   pretraitement, prediction avec score de confiance.
4. **Endpoints API** - prediction unitaire + lot CSV, meme convention de nommage
   (`/predict_<domaine>`, `/predict_<domaine>_csv`).
5. **Interface Streamlit a deux niveaux** - resume simple (non-technique) + detail technique
   (expander), comme construit pour le module Transactions ce soir.
6. **Reutilisation de l'infrastructure generique deja existante** - systeme de Pass, reglage de
   sensibilite, base d'apprentissage progressive, modele enrichi par organisation : tout ceci est
   deja decouple du domaine reseau/transactions, directement reutilisable pour tout nouveau modele.

## Domaines candidats

### 0. Securite IIoT (EN COURS - le plus avance des candidats)
- **Statut** : travail reel deja engage (notebook `Article_iiot.ipynb`), pas juste envisage.
- **Donnees** : jeu de donnees IIoT reel (Datasense-IIoT-2025), 685 671 echantillons, 94 colonnes
  brutes, 71 variables numeriques exploitables. Cible multi-classe riche (`label3`, ~33 familles
  d'attaques : reconnaissance/scan, usurpation ARP/IP, Mirai (UDP/SYN flood), injection SQL/commande,
  dictionary-ssh, floods varies sur ports 80/1883...) + `benign` a 58,4% (desequilibre raisonnable,
  bien moins extreme que pour les transactions).
- **Travail deja fait** : chargement/fusion de 20 fichiers CSV, EDA, verification des valeurs
  manquantes, reduction de multicolinearite par VIF (Variance Inflation Factor) : 71 -> 41
  predicteurs retenus (VIF < 10.0 pour tous), matrice de correlation residuelle verifiee.
- **Reste a faire** : split train/test stratifie, standardisation (train uniquement - piege de
  fuite de donnees a eviter, voir Partie 3.2 du document technique), comparaison d'algorithmes,
  GridSearchCV, puis toute l'integration applicative (service de modele, endpoints API, module
  Streamlit, entree dans core/schema_router.py, domaine dedie dans core/alert_log.py).
- **Blocage actuel** : le jeu de donnees complet est trop volumineux a transferer tel quel ;
  export d'un echantillon stratifie post-VIF (41 variables, quelques dizaines de milliers de
  lignes) demande pour debloquer l'entrainement reel.

### 1. Classification de texte SMS (arnaque directement depuis le message)
- **Ce qu'il ferait** : predire si un SMS/message est une arnaque a partir de son contenu textuel,
  plutot que de s'appuyer uniquement sur Gemini (voir discussion "Lieutenant Cyber utilise-t-il
  notre modele ML ?" plus tot dans le projet).
- **Donnees disponibles** : les temoignages deja collectes via `/temoignage` (categorises par canal
  et type de demande) constituent un premier socle, mais restent peu nombreux et non exhaustifs
  face a la diversite des formulations d'arnaque.
- **Approche technique** : TF-IDF + modele classique (coherent avec l'approche actuelle), ou
  fine-tuning d'un petit modele de langage si le volume de donnees le justifie.
- **Avantage** : rendrait le volet Grand Public symetrique au volet Organisation (ML + IA
  generative des deux cotes, au lieu de Gemini seul cote Grand Public).

### 2. Detection de reseaux de comptes mules (blanchiment)
- **Ce qu'il ferait** : identifier des groupes de comptes lies entre eux et utilises pour deplacer
  de l'argent frauduleux (analyse de graphe, pas une simple classification ligne par ligne).
- **Donnees necessaires** : historique de transactions avec identifiants de comptes source/destination
  sur une periode significative - beaucoup plus lourd a obtenir qu'une simple transaction isolee.
- **Complexite** : necessite des techniques differentes (analyse de graphe, detection de communautes)
  plutot que la classification supervisee utilisee jusqu'ici - le plus gros ecart methodologique
  de cette liste.

### 3. Fraude cote agent mobile money
- **Ce qu'il ferait** : detecter un agent (point de vente mobile money) qui manipule les transactions
  de ses clients plutot qu'un client fraude par un tiers.
- **Donnees necessaires** : donnees specifiques aux agents (volume, patterns d'activite par agent),
  distinctes des donnees utilisateur final deja envisagees pour le modele transactionnel.

### 4. Priorisation automatique des temoignages citoyens
- **Ce qu'il ferait** : classer automatiquement les temoignages entrants par urgence/gravite, pour
  aider a prioriser quels signalements meritent une attention immediate.
- **Donnees disponibles** : deja en grande partie disponibles (texte des temoignages collectes) -
  le candidat le plus rapide a amorcer parmi cette liste, des qu'un volume suffisant de temoignages
  aura ete collecte.

## Recommandation d'ordre, si/quand on avance

1. **Priorisation des temoignages** (donnees deja en collecte, complexite technique la plus faible)
2. **Classification de texte SMS** (donnees partiellement disponibles, valeur produit elevee)
3. **Fraude agent mobile money** (necessite un partenariat avec un operateur pour les donnees)
4. **Reseaux de comptes mules** (le plus complexe techniquement et en donnees, a envisager en dernier)

Cette liste n'est pas figee - a revisiter des qu'une opportunite de donnees reelles se presente
(partenariat institutionnel, volume suffisant de temoignages collectes, etc.).
