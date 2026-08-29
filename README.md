# Kimatey FinNet Guard — Plateforme Hybride de Cybersécurité et Protection Financière

Projet Master 1 Informatique — UFRMI — ECUE Machine Learning
Réalisé par : Komoe Edgar Junior
Responsable de l'enseignement : Dr ASSOHOUN E Stanislas

Solution destinée à sécuriser l'infrastructure réseau des fintechs, agrégateurs mobile money,
institutions de microfinance et administrations publiques, et à sensibiliser directement les
citoyens contre les arnaques mobile money.

**Trois espaces indépendants**, chacun avec son propre public et son propre niveau d'accès :

| Espace | Public | Accès | Hébergement |
|---|---|---|---|
| 🏢 Organisation | Équipes IT/sécurité, fintechs, opérateurs mobile money | Compte requis | Streamlit Cloud |
| 👥 Grand Public | Citoyens | Libre | Vercel (page web indépendante) |
| 🎓 Académique | Enseignants, étudiants | Libre, aucun compte | Streamlit Cloud |

**Deux modèles de machine learning**, même méthodologie, deux domaines :
- **Sécurité Réseau** (validé) : Arbre de décision, 99,04 % d'exactitude, entraîné sur 50 000 flux réels
- **Fraude Transactionnelle** (prototype) : même pipeline, entraîné sur données synthétiques clairement étiquetées

**Persistance** : comptes utilisateurs et journal d'alertes sur PostgreSQL (Neon), avec repli
automatique sur fichiers JSON si aucune base n'est configurée (voir section dédiée ci-dessous).

## Calibration du générateur de données synthétiques (Fraude Transactionnelle) sur des statistiques réelles BCEAO

Le module Fraude Transactionnelle reste un prototype entraîné sur des données **100% synthétiques**
(aucune vraie transaction, aucune fraude réelle constatée) - ce statut ne change pas tant qu'un
partenariat avec un opérateur mobile money réel n'aura pas fourni de données anonymisées.

Ce qui a changé : `src/transaction_fraud/generate_synthetic_data.py` (v3) calibre désormais les
**montants** et la **typologie de fraude** sur des statistiques publiques réelles de la BCEAO
(Banque Centrale des États de l'Afrique de l'Ouest), plutôt que sur des valeurs choisies sans
référence :

- **Montant moyen des transactions légitimes** : centré sur ~20 000 FCFA, ancré sur le montant
  moyen réel d'un transfert de personne à personne en zone UEMOA/Côte d'Ivoire (18 220-22 692 FCFA
  selon le [Rapport annuel BCEAO sur les services financiers numériques dans l'UEMOA - 2024](https://www.bceao.int/sites/default/files/2026-03/Rapport%20annuel%20sur%20les%20services%20financiers%20num%C3%A9riques%20dans%20l'UEMOA%20-%202024.pdf))
- **Sous-type de fraude "bypass cash in"** (remplace l'ancien "structuring" générique) : calibré
  sur un pattern de fraude réellement documenté par la BCEAO - le fractionnement des dépôts
  clients par des distributeurs/agents en plusieurs petites transactions successives, pour
  toucher davantage de commissions (barèmes dégressifs par palier). Voir le
  [Rapport annuel BCEAO 2021](https://www.bceao.int/sites/default/files/2023-02/Rapport%20annuel%20sur%20les%20services%20financiers%20num%C3%A9riques%20dans%20l'UEMOA%20%C3%A0%20fin%202021.pdf),
  qui documente ce pattern (Graphique n°5 : Fraudes, incidents et gestion des réclamations
  clients).

**Ce qui reste une hypothèse non vérifiée**, honnêtement signalé : le **taux de fraude** (5% par
défaut) et les deux autres sous-types (compte compromis, vélocité/mules) n'ont pas pu être ancrés
sur des chiffres BCEAO publiquement disponibles - les rapports annuels mentionnent la fraude
comme risque croissant mais publient les statistiques chiffrées sous forme de graphique (image
dans le PDF), non extractibles automatiquement. Cette calibration améliore le réalisme des
*montants* et de la *typologie*, pas la validité du *taux de fraude* lui-même.

## Structure du projet

```
kimatey_finnet_guard/
├── data/                          Jeu de données (CSV, 50 000 flux reseau)
├── src/                           Scripts Python - pipeline ML reseau (Etapes 1 a 4)
│   ├── eda.py                     Analyse exploratoire
│   ├── preprocessing.py           Etape 1 : nettoyage, IQR, split, standardisation
│   ├── utils.py                   Fonctions communes (evaluation, graphiques)
│   ├── baseline_models.py         Etape 2 : 5 algorithmes (modele complet)
│   ├── feature_selection.py       Etape 3 : RFE + elagage cout-complexite
│   ├── grid_search.py             Etape 4 : GridSearchCV (5 plis)
│   ├── regen_dashboard_figures.py Regenere les ROC/matrice de confusion en version sombre
│   └── transaction_fraud/         Pipeline ML transactions (donnees synthetiques)
│       ├── generate_synthetic_data.py
│       └── train_pipeline.py
├── core/                          Logique partagee entre Streamlit ET l'API (source de verite unique)
│   ├── kimatey_core.py            Prompts systeme Gemini (4 personas), ask_gemini(), jeu de vigilance
│   ├── alert_log.py                Journal d'alertes + score de securite, multi-domaine (reseau/transactions),
│   │                                Postgres si DATABASE_URL configuree, sinon repli fichier JSON
│   ├── db.py                      Connexion PostgreSQL generique (Neon/Supabase/Render Postgres)
│   ├── pass_system.py             Catalogue de Pass (quotas Organisation/Grand Public, mode demo)
│   ├── sensitivity.py             Reglage de seuil de decision par compte
│   └── enriched_model.py          Generation de modele enrichi par organisation (Niveau 2 hybride)
├── app/
│   └── app.py                     Interface Streamlit : page d'accueil (3 espaces) + Organisation
│                                   (2 modules : Reseau, Transactions) + Academique
├── .streamlit/
│   └── config.toml                Theme visuel (dark, primaryColor teal, background navy)
├── web/                           Pages web independantes (hors Streamlit), deployees sur Vercel
│   ├── index.html                 Page d'accueil : branding + 3 cartes (Organisation/Public/Academique)
│   ├── public.html                Espace Grand Public complet (chat + voix + image + jeu + Pass)
│   ├── dashboard.html             Dashboard SOC web anime (BI/restitution) - jauge, Chart.js, IA
│   ├── config.js                  API_BASE_URL et ORG_APP_URL - a changer pour deployer ailleurs
│   ├── style.css / landing.css / dashboard.css   Themes navy/teal partages
│   ├── dashboard.js               Logique du dashboard web (fetch API, graphiques, filtres)
│   └── i18n.js                    Traductions FR/EN (page d'accueil + Grand Public)
├── api/                           API REST FastAPI (backend independant, source de verite unique)
│   ├── main.py                    Tous les endpoints (Organisation, Grand Public, dashboard SOC)
│   ├── auth.py                    5 modes d'authentification, comptes utilisateurs sur Postgres/JSON
│   ├── orgs.json                  Comptes de demonstration pour le mode 'per_org'
│   ├── users.json                 Repli JSON pour les comptes self_signup (vide si Postgres configure)
│   ├── schemas.py                 Schemas Pydantic (validation des requetes/reponses)
│   ├── model_service.py           Modele reseau : chargement + pipeline de pretraitement (cache)
│   └── transaction_model_service.py   Modele transactions : chargement + pretraitement (cache)
├── outputs/                       Resultats generes (CSV, JSON, modeles .joblib, figures) +
│                                   organisation_state[_transactions].json (repli JSON, non versionne) +
│                                   transaction_fraud/ (donnees synthetiques + modele)
├── docs/                          Feuilles de route honnetes (non construit, mais documente)
│   ├── ROADMAP_SMS_USSD.md
│   ├── ROADMAP_PAIEMENT.md
│   └── ROADMAP_MODELES_ADDITIONNELS.md
├── tests/                         Suite de tests automatises (pytest) - couvre le pipeline ML reseau,
│                                   l'API historique et l'authentification. NE COUVRE PAS ENCORE :
│                                   le module Transactions, la persistance Postgres, l'Espace Academique,
│                                   ni le dashboard SOC web (aucun test ecrit pour ces ajouts recents).
└── report/                        Rapport de projet, document API, PowerPoint, rapport de tests
```


## Exécution du pipeline complet

```bash
pip install -r requirements.txt

cd kimatey_finnet_guard
python3 src/eda.py
python3 src/preprocessing.py
python3 src/baseline_models.py
python3 src/feature_selection.py
python3 src/grid_search.py
```

Chaque script écrit ses résultats (métriques, figures, modèles) dans `outputs/`.

## Lancer l'application de supervision (GUI)

```bash
streamlit run app/app.py
```

L'application se lance dans le navigateur (par défaut http://localhost:8501), avec un thème
visuel sombre navy/teal cohérent avec le PowerPoint de soutenance.

Elle démarre sur une **page d'accueil** (bandeau "Kimatey FinNet Guard" + choix de l'espace) qui
oriente vers trois espaces distincts :

### 🏢 Espace Organisation (compte requis)

Dès la connexion, un **écran de sélection** propose deux produits distincts, chacun avec son propre
badge de maturité :
- **🌐 Sécurité Réseau** (✅ validé, 99,04 % d'exactitude)
- **💰 Fraude Transactionnelle** (🧪 prototype, données synthétiques)

Chaque module a ses propres onglets, sur un même schéma :
- **👔 Résumé simple** : vue non-technique (jauge de score visuelle, pastilles de gravité en icônes,
  langage courant, aucune métrique de modèle),
- **⚙️ Réglages** (module Réseau) : personnalisation - seuil de sensibilité, modèle enrichi par
  organisation (Niveau 2 hybride, à partir de 20 échantillons validés),
- **📁 Analyser un fichier de logs / de transactions** : import CSV en lot,
- **🔎 Vérifier un flux unique** (module Réseau) : formulaire de prédiction ponctuelle,
- **🔴 Surveillance en direct** (module Réseau) : simulation d'un flux continu échantillonné dans le
  jeu de données réel, à des fins de démonstration (ce n'est pas une capture réseau live),
- **🚨 Alertes détectées** : score de sécurité, statut ouvert/fermé, gravité, tendance 7 jours,
  filtres, journal complet - alimenté par les imports/vérifications précédents,
- **📈 Visualisation** : lien vers le dashboard SOC web animé (voir section dédiée ci-dessous),
  scopé strictement au domaine du module courant.

**Lieutenant Cyber** peut expliquer un résultat en langage clair, avec un persona dédié selon le
contexte (analyste technique ou décideur sans jargon) - voir section « Lieutenant Cyber » ci-dessous.

### 👥 Espace Grand Public (libre d'accès)

Ne vit plus dans Streamlit : le bouton redirige vers la page web indépendante (voir section
« Page d'accueil web + Espace Grand Public indépendants » ci-dessous), seule désormais maintenue.

### 🎓 Espace Académique (libre d'accès, aucun compte requis)

Cas d'étude pédagogique (machine learning appliqué à la cybersécurité réseau), pour enseignants et
étudiants - volontairement indépendant de l'Espace Organisation (un étudiant n'a pas à créer un
compte "organisation" pour réviser) :
- métriques de confiance du modèle (accuracy, F1 macro, AUC macro) avec explications dépliables,
- comparaison des 5 algorithmes testés, courbes ROC, matrice de confusion,
- **Professeur Cyber** : Q&A libre avec un persona pédagogique dédié, connaît le contexte précis
  du projet,
- mini-quiz (5 questions fixes) sur les concepts clés (fuite de données, F1 macro, GridSearchCV, RFE),
- import de jeu de données personnalisé : outil générique d'EDA (moyenne, écart-type, histogramme),
  découplé du modèle Kimatey - pour illustrer des concepts de statistique en cours ou en devoir.

Cette page d'accueil + trois espaces au sein de Streamlit/web reste utile pour une démo rapide.
L'Espace Organisation continue de vivre dans Streamlit (outil interne), avec deep-links directs
(`?view=organisation`, `?view=academic`).

## Persistance des données (PostgreSQL / Neon)

Par défaut, les comptes utilisateurs et le journal d'alertes vivent sur fichiers JSON locaux -
**non persistants** sur la plupart des hébergeurs gratuits (le disque est réinitialisé à chaque
redéploiement). Pour une vraie persistance, configurez la variable d'environnement `DATABASE_URL`
(compatible Neon, Supabase, Render Postgres, ou toute base PostgreSQL) :

```bash
export DATABASE_URL="postgresql://user:password@host/dbname?sslmode=require"
```

Dès que cette variable est définie, `core/db.py` et `core/alert_log.py` basculent automatiquement
sur PostgreSQL (schéma créé automatiquement au démarrage) - **sans variable définie, aucune
régression** : repli transparent sur le comportement fichier JSON existant. Les deux tables créées :
`users` (comptes) et `alerts` / `score_history` (journal, avec colonne `domaine` pour isoler
Sécurité Réseau et Fraude Transactionnelle l'un de l'autre).

**Important** : cette variable doit être configurée séparément sur **chaque** environnement
d'exécution (Render pour l'API, Streamlit Cloud dans ses "Secrets") - ce sont deux processus
indépendants, chacun avec son propre jeu de variables d'environnement.

## Dashboard SOC web animé (`web/dashboard.html`)

Une page web indépendante (Vercel), pensée comme un vrai outil de **restitution façon BI**
(Power BI-like) : elle ne fait qu'afficher des données déjà collectées, avec des graphiques
interactifs (Chart.js - survol, animations fluides), contrairement à Streamlit qui reste l'outil
**opérationnel** (import, vérification, simulation).

- Connexion avec le même compte que l'Espace Organisation,
- **scopée strictement par domaine** via un paramètre d'URL (`?domaine=reseau` ou
  `?domaine=transactions`) - quand l'utilisateur arrive depuis un module précis, aucune visibilité
  sur l'autre domaine (sélecteur masqué). Sans paramètre (accès direct), un sélecteur reste
  disponible en repli,
- jauge de score circulaire animée, donut de statut, barres de gravité, courbes chronologiques
  multi-jours, filtre de date, journal cliquable (marquer traité/rouvrir),
- commentaire IA à la demande (Lieutenant Cyber, persona décideur ou analyste selon la vue).

Consomme directement les endpoints `/organisation/dashboard_soc` et
`/organisation/dashboard_transactions` de l'API (voir liste complète des endpoints ci-dessous).

## Jeu de vigilance gamifié

Le mini-jeu de sensibilisation repose sur des mécaniques de gamification classiques — niveaux/XP,
une monnaie de progression, un système de vies, des mascottes par catégorie, des catégories
thématiques et des badges — adaptées spécifiquement au domaine de la fraude mobile money :

- **6 catégories thématiques** : 📱 Mobile Money (les 3 scénarios historiques, inchangés),
  🏦 Banque & Épargne,
  📞 Ingénierie Sociale, 💬 Réseaux Sociaux, 🧓 Protection des Aînés, 🔐 Cyber & Mots de Passe —
  chacune avec 2 à 3 scénarios réels, un retour immédiat coloré (succès/erreur) et une **astuce**
  (`tip`) actionnable en plus de l'explication.
- **Niveaux & Points Bouclier 🛡️** : chaque réponse rapporte des Points Bouclier (15 si correcte, 5
  si incorrecte — pour avoir essayé), qui font progresser à travers 5 niveaux (Recrue Vigilante →
  Vigie Mobile Money → Gardien Cyber → Gardien d'Élite → Légende de la Vigilance). **Décision de
  design assumée** : les Points Bouclier n'ont ici *aucune*
  conversion en argent ni en récompense réelle. Dans une
  application qui lutte contre la fraude financière, imiter une monnaie qui se convertit en valeur
  réelle aurait envoyé le mauvais signal — c'est uniquement un indicateur de progression et de
  vigilance.
- **Vies ❤️** : 3 vies, perdues sur une mauvaise réponse, rechargeables à tout moment (simplification
  assumée par rapport à un vrai minuteur de régénération — voir feuille de route).
- **Une mascotte, propre à Kimatey** : **Lieutenant Cyber**, une création originale (pas un personnage
  emprunté à un autre produit), anime les 6 catégories — une identité unique plutôt que plusieurs
  mascottes différentes.
  Voir section « Lieutenant Cyber » ci-dessous : c'est la même IA que l'assistant conversationnel et que
  la nouvelle assistance à l'analyse de l'Espace Organisation - une identité unique plutôt que plusieurs
  entités disjointes.
- **Sélecteur d'âge** (Ado 13-17 ans / Adulte 18+), léger : adapte simplement le ton d'une astuce
  affichée par la mascotte (aucun contenu masqué), inspiré du filtrage par âge de VIE.
- **Badges** débloqués à des paliers de Points Bouclier (Premier Bouclier, As du Mobile Money, Gardien
  Multi-Catégories, Légende Cyber), affichés verrouillés/déverrouillés dans un panneau dédié — en
  remplacement d'une boutique à achats (hors scope, voir feuille de route).

**Asymétrie de persistance assumée entre les deux surfaces** :
- Côté **Streamlit** (`app/app.py`), la progression reste en `st.session_state` : valable pour la
  session de démonstration uniquement, comme le reste de l'Espace Grand Public dans Streamlit.
- Côté **page web indépendante** (`web/public.html`), la progression est enregistrée dans le
  `localStorage` du navigateur (`kimatey_game_state_v1`) : elle survit à une fermeture/réouverture de
  la page, sans nécessiter de compte — une vraie amélioration permise par le fait que cette surface
  tourne dans un vrai navigateur. Un vrai système de comptes persistants côté serveur (pour un
  classement/tournoi hebdomadaire à la VIE, par exemple) reste une piste de feuille de route.

Contenu et règles exposés par l'API (mêmes données consommées par Streamlit et par `web/public.html`,
une seule source de vérité dans `core/kimatey_core.py`) :
- `GET /game/categories` : les 6 catégories avec leurs scénarios, mascottes et astuces.
- `GET /game/meta` : Points Bouclier par réponse, nombre de vies, niveaux, badges.
- `GET /scenarios` reste inchangé (3 scénarios Mobile Money historiques), pour ne rien casser côté
  clients existants.

## Lieutenant Cyber : une seule IA, quatre personas selon l'audience

Objectif explicite : que la même IA rende « l'analyse des données, le rendu des tableaux de bord et
l'assistance des différents types d'utilisateurs plus fluides et simples », plutôt que d'avoir des
expériences disjointes. **Lieutenant Cyber** est cette identité unique, avec quatre rôles/prompts
système dédiés (`core/kimatey_core.py`) :

- **`ASSISTANT_SYSTEM_PROMPT`** (Grand Public) : l'assistant conversationnel/vocal et la mascotte du
  jeu de vigilance.
- **`ORG_ANALYST_SYSTEM_PROMPT`** (Organisation, technique) : explique un résultat (flux unique ou lot)
  en langage clair avec une recommandation d'action, pour une équipe technique.
- **`ORG_EXECUTIVE_SYSTEM_PROMPT`** (Organisation, décideur) : même rôle, mais interdiction stricte de
  tout jargon technique - pour un manager/décideur non-technique (Résumé simple, dashboard web).
- **`ACADEMIC_INSTRUCTOR_SYSTEM_PROMPT`** ("Professeur Cyber", Espace Académique) : explique les
  concepts de ML/statistiques/méthodologie avec le contexte précis du projet, pour enseignants et
  étudiants.

**Grounding strict, délibéré** : dans tous les rôles Organisation/Académique, Lieutenant Cyber ne
classifie jamais elle-même le trafic (le modèle de machine learning entraîné reste seul responsable
de la classification) et chaque system prompt lui interdit explicitement d'inventer un signal, une
menace ou une donnée qui ne lui a pas été fournie dans le contexte de l'appel.

Exposé côté API (protégé par `AUTH_MODE`) : `POST /organisation/explain_flow`,
`POST /organisation/explain_batch`, `POST /organisation/dashboard_soc/commentaire` (paramètre `mode`
= `executive` ou `analyst`, `domaine` = `reseau` ou `transactions`). Sans clé Gemini configurée côté
serveur, ces endpoints répondent `503` explicitement, jamais un contenu vide ni un crash.

## Lancer l'API REST (FastAPI)

```bash
uvicorn api.main:app --reload --port 8000
```

Documentation interactive : http://localhost:8000/docs (Swagger UI). Voir le document
`report/Configuration_API_FastAPI.docx` pour le détail des endpoints historiques (predict*), et les
sections ci-dessous pour les endpoints Grand Public et l'authentification, ajoutés depuis.

L'API expose plusieurs familles d'endpoints (voir `/docs` pour la liste exhaustive à jour) :
- **Organisation - Réseau** (`/model_info`, `/predict`, `/predict_batch`, `/predict_csv`,
  `/organisation/explain_flow`, `/organisation/explain_batch`, `/organisation/dashboard_soc`,
  `/organisation/dashboard_soc/toggle/{alert_id}`, `/sensibilite`, `/organisation/modele_enrichi`) :
  protégés selon `AUTH_MODE` (voir "Authentification" ci-dessous).
- **Organisation - Transactions** (`/predict_transaction`, `/predict_transaction_csv`,
  `/organisation/dashboard_transactions`, `/organisation/dashboard_transactions/toggle/{alert_id}`) :
  même protection, journal et score isolés du domaine Réseau (colonne `domaine` en base).
- **Organisation - commun** (`/organisation/dashboard_soc/commentaire`) : commentaire IA, paramétré
  par `mode` (executive/analyst) et `domaine` (reseau/transactions).
- **Grand Public** (`/scenarios`, `/report_steps`, `/assistant/chat`, `/assistant/chat_image`,
  `/temoignage`, `/temoignages/count`, `/temoignages/tendances`, `/game/categories`, `/game/meta`,
  `/pass/catalogue`, `/pass/actif`, `/pass/souscrire`, `/public/progress`) : toujours ouverts, sans
  authentification, quel que soit `AUTH_MODE`.

## Authentification de l'Espace Organisation (API + Streamlit)

Cinq modes réels, choisis via la variable d'environnement `AUTH_MODE` (par défaut `none`, donc aucun
changement de comportement si vous ne définissez rien) :

| `AUTH_MODE`         | Usage                                                              | Configuration |
|----------------------|---------------------------------------------------------------------|---------------|
| `none` (défaut)      | Aucune authentification (comportement historique)                   | rien à faire |
| `shared_password`    | Un seul mot de passe protège tout l'Espace Organisation              | `SHARED_ORG_PASSWORD` |
| `per_org`            | Chaque organisation a son identifiant + mot de passe (comptes pré-provisionnés) | `api/orgs.json` (2 comptes de démo fournis) |
| `self_signup`        | Auto-inscription par email + mot de passe, sans compte à provisionner à la main ni service externe | `api/users.json` (créé automatiquement) |
| `firebase`           | Point d'extension Firebase Authentication (voir note ci-dessous)     | `GOOGLE_APPLICATION_CREDENTIALS` + `firebase-admin` |

`self_signup` est le mode recommandé pour une démo où l'on veut qu'un visiteur puisse réellement "se
connecter ou créer un compte" de bout en bout, sans dépendre d'un vrai projet Firebase externe (voir
note sur `firebase` ci-dessous) ni provisionner de compte à la main comme en mode `per_org`. Ce mode est
branché à la fois côté API (`POST /auth/register` puis `POST /auth/login`) **et** côté application
Streamlit : quand `AUTH_MODE=self_signup`, l'Espace Organisation affiche un écran de connexion / création
de compte avant les 5 onglets techniques - Streamlit réutilise directement `api/auth.py` (même code, même
fichier `api/users.json`), sans appel HTTP, donc les deux surfaces restent cohérentes.

```bash
export AUTH_MODE=self_signup
streamlit run app/app.py
# -> "Espace Organisation" affiche un ecran "Se connecter" / "Creer un compte" (email + mot de passe,
#    6 caracteres minimum) avant les onglets techniques. Le compte cree est immediatement connecte.

# Equivalent cote API (utile pour un client externe / un SIEM) :
uvicorn api.main:app --port 8000
curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" \
     -d '{"email": "moi@exemple.com", "password": "motdepasse123"}'
# -> {"token": "...", "auth_mode": "self_signup", "message": "Compte cree avec succes, vous etes connecte."}
curl http://localhost:8000/model_info -H "Authorization: Bearer <token>"
```

Mots de passe stockés hashés-salés (SHA-256), jamais en clair. Volontairement minimaliste pour une
démo/projet M1 : pas de vérification d'email, pas de récupération de mot de passe oublié - à ajouter
avant tout usage en production réelle.

Exemple avec `shared_password` :

```bash
export AUTH_MODE=shared_password
export SHARED_ORG_PASSWORD=change-moi
uvicorn api.main:app --port 8000

# Connexion
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
     -d '{"password": "change-moi"}'
# -> {"token": "...", "auth_mode": "shared_password", "message": "Connexion reussie."}

# Utilisation du jeton sur un endpoint Organisation
curl http://localhost:8000/model_info -H "Authorization: Bearer <token>"
```

Exemple avec `per_org` (comptes de démonstration dans `api/orgs.json`, mots de passe en clair fournis
uniquement dans cette documentation - à changer avant tout usage réel) :

```bash
export AUTH_MODE=per_org
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
     -d '{"org_id": "kimatey_demo_bank", "password": "ChangeMoi123!"}'
```

**Mode `firebase`** : point d'extension honnête, pas une intégration réelle dans cet environnement de
démonstration - il n'y a ni le package `firebase-admin` installé, ni un vrai projet Firebase (fichier de
compte de service) à y brancher. Tant que ces deux prérequis ne sont pas fournis, l'API répond
explicitement `501 Not Implemented` plutôt que de simuler une connexion réussie. Pour l'activer
réellement : créer un projet Firebase, activer Firebase Authentication, télécharger un fichier de compte
de service, `pip install firebase-admin`, définir `GOOGLE_APPLICATION_CREDENTIALS=/chemin/vers/le/fichier.json`
et `AUTH_MODE=firebase` - le client (page web ou appli mobile) s'authentifie alors directement auprès de
Firebase avec le SDK officiel, puis envoie son "ID token" en `Authorization: Bearer <id_token>` à l'API.

## Page d'accueil web + Espace Grand Public indépendants (hors Streamlit)

C'est la séparation réelle en deux surfaces techniques distinctes évoquée plus haut : une petite page web
statique (HTML/CSS/JS, sans framework, sans étape de build) sert de page d'accueil et d'Espace Grand Public
complet, en consommant directement l'API FastAPI.

```bash
# Terminal 1 : l'API (obligatoire, sert /assistant/chat, /scenarios, /report_steps, /temoignage...)
uvicorn api.main:app --port 8000

# Terminal 2 : la page web statique
python3 -m http.server 8080 --directory web

# Terminal 3 (optionnel, pour le lien "Espace Organisation") : Streamlit
streamlit run app/app.py
```

Ouvrir http://localhost:8080/index.html : trois cartes - "Espace Organisation" mène directement à
`http://localhost:8501/?view=organisation` (Streamlit) ; "Espace Grand Public" mène à `public.html`
(assistant conversationnel, voix, image, jeu de vigilance gamifié, système de Pass) ; "Espace
Académique" mène à `http://localhost:8501/?view=academic` (Streamlit, aucun compte requis).

Les deux seules valeurs à changer pour déployer ailleurs qu'en local sont dans `web/config.js`
(`API_BASE_URL` et `ORG_APP_URL`).

## Résultat principal

Modèle optimal retenu : **Arbre de Décision élagué et optimisé** (5 variables, profondeur 5)
- Exactitude (test) : 99,04 %
- F1-score macro : 98,72 %
- AUC macro : 99,92 %

## Garde-fou de version scikit-learn

`requirements.txt` épingle `scikit-learn` à une version exacte (`==`), contrairement au reste des
dépendances (`>=`) : les objets scikit-learn sérialisés via joblib/pickle ne sont pas garantis
stables entre versions mineures - un écart peut se charger sans erreur mais produire des
prédictions subtilement différentes de celles validées à l'entraînement. Chaque pipeline
d'entraînement (`src/grid_search.py`, `src/transaction_fraud/train_pipeline.py`) enregistre
désormais la version scikit-learn utilisée dans les métadonnées du modèle
(`sklearn_version` dans `best_model_info*.json`) ; `core/model_version_check.py` la compare à la
version installée à chaque démarrage de service (`api/model_service.py`,
`api/transaction_model_service.py`) et journalise un avertissement clair (sans bloquer le
démarrage) en cas d'écart - utile en particulier si l'environnement de déploiement (Render,
Streamlit Cloud) réinstalle une version différente de celle utilisée localement.

## Migration du paramètre Streamlit `width`

Les 36 usages de `use_container_width=True/False` dans `app/app.py` ont été remplacés par
`width="stretch"`/`width="content"` : `use_container_width` est déprécié par Streamlit depuis fin
2025 (date de retrait déjà passée au moment de cette migration) - découvert via un warning émis
pendant l'exécution des tests Streamlit de l'Espace Académique, corrigé avant que Streamlit Cloud
ne mette à jour vers une version où l'ancien paramètre ne fonctionnerait plus du tout.

## Exécuter la suite de tests

```bash
pip install pytest httpx --break-system-packages
cd kimatey_finnet_guard
python3 -m pytest tests/ -v
```

109 tests (pipeline ML réseau, API - Organisation historique, Grand Public, jeu de vigilance gamifié,
assistance à l'analyse Lieutenant Cyber, 5 modes d'authentification dont l'auto-inscription self_signup,
application Streamlit dont l'écran de connexion/création de compte, écran de sélection de module de
l'Espace Organisation et de l'Espace Académique, redirection de l'Espace Grand Public vers la version
web, Mini-quiz ML, module Fraude Transactionnelle) + 33 tests de persistance PostgreSQL/JSON + 8 tests
API de fraude transactionnelle + 11 tests structurels du dashboard SOC web = **175 tests, 1 skip
attendu**, s'exécutent en moins de 30 secondes au total.

`tests/test_streamlit_app.py` a été resynchronisé avec deux restructurations de l'interface qui
l'avaient rendu obsolète sans mise à jour immédiate (19 tests étaient en échec avant correction,
voir le journal Git pour le détail) : l'entrée dans l'Espace Organisation passe désormais par un
écran de choix entre 2 produits avant les onglets techniques (7 onglets pour le module réseau,
au lieu de 5), et l'Espace Grand Public Streamlit est déprécié - la carte d'accueil pointe
désormais vers la version web indépendante (Vercel) via un lien externe plutôt qu'un onglet interne.

**Les 3 trous de couverture précédemment signalés sont désormais comblés :**

- **Module Fraude Transactionnelle** : navigation Streamlit (`TestModuleFraudeTransactionnelle`
  dans `test_streamlit_app.py`) + endpoints API (`tests/test_api_transactions.py`, 8 tests -
  prédiction unique, lot CSV, validation des bornes, isolation du journal d'alertes par domaine)
- **Espace Académique** : `TestEspaceAcademique` + `TestMiniQuizAcademique` dans
  `test_streamlit_app.py` - accès sans authentification, KPIs du modèle, les 3 modes (Q&A,
  quiz, EDA), logique de score du quiz (bonne/mauvaise réponse)
- **Dashboard SOC web** (`web/dashboard.html`) : `tests/test_dashboard_web.py` (11 tests) -
  analyse statique sans navigateur (validité syntaxique JS via `node --check`, équilibre des
  balises HTML/accolades CSS, cohérence des IDs référencés par `getElementById()` vs définis
  dans le HTML ou injectés dynamiquement, correspondance canvases Chart.js ↔ graphiques
  instanciés, absence d'URL d'API codée en dur hors de `config.js`). Une couverture
  fonctionnelle complète (clics, rendu visuel réel) resterait hors de portée de pytest et
  nécessiterait un outil navigateur (ex. Playwright) - non implémenté ici.

Le jeu de vigilance gamifié et l'assistant Lieutenant Cyber conversationnel, désormais implémentés
en HTML/JS pur sur la version web (Vercel) plutôt qu'en Streamlit, restent hors de portée de cette
suite pytest/AppTest pour la même raison (nécessiteraient Playwright).

**Persistance PostgreSQL (`core/db.py`, `core/alert_log.py`)** : couverte par
`tests/test_persistence_postgresql.py` (33 tests) - connexion mockée (aucune base réelle requise
pour l'essentiel de la suite), isolation stricte entre domaines réseau/transactions, repli JSON,
et toute la logique métier pure (score de sécurité, MTTR, tendance, répartition de gravité). Un
test d'intégration optionnel contre une vraie base existe (`TestIntegrationReelleOptionnelle`,
ignoré par défaut, activable via `TEST_DATABASE_URL`).

Le détail de la stratégie de test et des résultats se trouve dans
`report/Rapport_de_Tests.docx`.

## Rapport

Le rapport complet (12 sections : contexte, EDA, méthodologie, résultats des 5 étapes,
réponses aux 4 questions de recherche, limites, conclusion) se trouve dans
`report/Rapport_Projet_ML_SOC.docx`.
