# Kimatey FinNet Guard — Détection Intelligente et Supervision en Temps Réel des Attaques Réseau

Projet Master 1 Informatique — UFRMI — ECUE Machine Learning
Réalisé par : Komoe Edgar Junior
Responsable de l'enseignement : Dr ASSOHOUN E Stanislas

Solution destinée à sécuriser l'infrastructure réseau des fintechs, agrégateurs mobile money,
institutions de microfinance et administrations publiques, et à sensibiliser directement les
citoyens contre les arnaques mobile money.

## Structure du projet

```
kimatey_finnet_guard/
├── data/                          Jeu de données (CSV, 50 000 flux)
├── src/                           Scripts Python (Étapes 1 à 4)
│   ├── eda.py                     Analyse exploratoire
│   ├── preprocessing.py           Étape 1 : nettoyage, IQR, split, standardisation
│   ├── utils.py                   Fonctions communes (évaluation, graphiques)
│   ├── baseline_models.py         Étape 2 : 5 algorithmes (modèle complet)
│   ├── feature_selection.py       Étape 3 : RFE + élagage coût-complexité
│   ├── grid_search.py             Étape 4 : GridSearchCV (5 plis)
│   └── regen_dashboard_figures.py Régénère les ROC/matrice de confusion en version sombre (dashboard)
├── core/
│   └── kimatey_core.py            Contenu partage entre Streamlit et l'API : prompts systeme Gemini,
│                                   ask_gemini(), jeu de vigilance gamifie (categories/mascottes/
│                                   niveaux/badges), etapes du parcours de collecte
├── app/
│   └── app.py                     Étape 5 : interface Streamlit "Kimatey FinNet Guard" (thème navy/teal),
│                                   page d'accueil + deux espaces (Organisation : 5 onglets ;
│                                   Grand Public : 2 onglets). Deep-link : ?view=organisation / ?view=public
├── .streamlit/
│   └── config.toml                Thème visuel (dark, primaryColor teal, background navy)
├── web/                           Page d'accueil web + Espace Grand Public independants (hors Streamlit)
│   ├── index.html                 Page d'accueil : branding + 2 cartes (lien direct vers l'API/Streamlit)
│   ├── public.html                Espace Grand Public : assistant (chat + lecture vocale), mini-jeu,
│   │                               parcours de collecte participative - tout via l'API FastAPI
│   ├── config.js                  Les 2 seules valeurs a changer pour deployer (API_BASE_URL, ORG_APP_URL)
│   └── style.css                  Theme navy/teal partage avec l'application Streamlit
├── api/                           API REST FastAPI (backend indépendant, source de verite unique)
│   ├── main.py                    Endpoints Organisation (proteges selon AUTH_MODE) + Grand Public (ouverts)
│   ├── auth.py                    5 modes d'authentification (dont l'auto-inscription self_signup) + point d'extension Firebase
│   ├── orgs.json                  Comptes de demonstration pour le mode 'per_org' (mots de passe hashes)
│   ├── users.json                 Comptes crees par auto-inscription en mode 'self_signup' (mots de passe hashes, vide au depart)
│   ├── schemas.py                 Schémas Pydantic (validation des requêtes/réponses)
│   └── model_service.py           Chargement du modèle + pipeline de prétraitement (cache)
├── outputs/                       Résultats générés (CSV, JSON, modèles .joblib, figures) +
│                                   temoignages.jsonl (contributions Grand Public, cree a l'usage)
├── demo_screenshots/              Captures d'écran : page d'accueil (Streamlit et web), Espace
│                                   Organisation (5 onglets), Espace Grand Public (Streamlit et web)
├── tests/                         Suite de tests automatisés (pytest)
│   ├── conftest.py                 Configuration partagée (PYTHONPATH, répertoire de travail)
│   ├── test_preprocessing.py       Étape 1 : prétraitement, no-leakage (17 tests)
│   ├── test_models.py              Étapes 2-4 : modèles baseline/réduits/optimisés (18 tests)
│   ├── test_api.py                 API FastAPI : endpoints Organisation, validations, cohérence (13 tests)
│   ├── test_api_public_et_auth.py  API : Espace Grand Public + 5 modes d'authentification (39 tests)
│   └── test_streamlit_app.py       Application Streamlit : smoke tests (AppTest, 24 tests,
│                                   navigation page d'accueil -> Organisation / Grand Public)
└── report/
    ├── build_report.js            Générateur du rapport Word (projet)
    ├── Rapport_Projet_ML_SOC.docx Rapport de projet complet
    ├── build_fastapi_doc.js       Générateur du document de configuration FastAPI
    ├── Configuration_API_FastAPI.docx  Document de configuration et mise en œuvre de l'API
    ├── build_pptx.js              Générateur du PowerPoint de soutenance
    ├── Presentation_Projet_ML_SOC.pptx PowerPoint de soutenance (19 slides)
    ├── build_test_report.js       Générateur du rapport de tests
    └── Rapport_de_Tests.docx      Rapport de tests détaillé (stratégie + 55 résultats réels)
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
oriente vers deux espaces distincts, chacun accessible par un bouton dédié et refermable via un
bouton "← Retour à l'accueil" :

### 🏢 Espace Organisation (5 onglets)

Destiné aux équipes IT/sécurité des fintechs, opérateurs mobile money, institutions financières
et administrations :
- un tableau de bord de performance du modèle optimal (cartes KPI, comparaison des algorithmes, ROC, matrice de confusion),
- l'import d'un fichier CSV de logs réseau (un exemple est fourni : `outputs/sample_logs_demo.csv`),
- un formulaire de prédiction d'un flux réseau unique avec niveau de confiance,
- une **surveillance en direct** : simulation d'un flux continu de connexions échantillonnées dans le
  jeu de données réel, avec mise à jour progressive (compteurs, graphique, table des derniers flux,
  comparaison à la vérité terrain) pour visualiser la supervision en conditions proches du temps réel,
- un journal d'alertes dynamique, alimenté par les trois onglets précédents,
- **Lieutenant Cyber** peut aussi expliquer un résultat (flux unique ou lot importé) en langage clair et
  recommander une action, à la demande (bouton dédié après chaque analyse) — voir section « Lieutenant
  Cyber » ci-dessous pour le détail.

### 👥 Espace Grand Public (2 onglets)

Destiné directement aux citoyens, sans jargon technique :
- **Lieutenant Cyber**, l'IA conversationnelle et vocale de Kimatey FinNet Guard (API Gemini), qui
  explique les alertes en langage clair et aide à évaluer si un SMS/message reçu ressemble à une
  arnaque mobile money. Nécessite une clé API Gemini gratuite (https://aistudio.google.com/apikey),
  définie dans la variable d'environnement `GEMINI_API_KEY` avant de lancer Streamlit
  (`export GEMINI_API_KEY=votre_cle`). Sans clé, l'onglet reste utilisable pour saisir une clé de test,
  sans bloquer le reste de l'application,
- un onglet **Sensibilisation**, désormais un **jeu de vigilance gamifié** (voir section dédiée
  ci-dessous), et
  un **échange animé façon chat** avec l'assistant (et non un formulaire) qui pose une question à la
  fois avec des réponses rapides en boutons, pour aider à repérer de nouvelles techniques de fraude
  sans jamais demander d'information personnelle. Un dernier détail facultatif (texte ou audio) est
  automatiquement résumé par Gemini en une fiche anonymisée (technique utilisée uniquement, jamais de
  nom/numéro/montant), avec un remerciement animé (ballons) à la fin de l'échange. Les fiches ne sont
  conservées que dans la session de démonstration (pas encore reliées à une base de données
  persistante ni à un pipeline de réentraînement du modèle).

Cette page d'accueil + deux espaces au sein de Streamlit reste utile pour une démo rapide en local
(tout dans un seul processus). L'architecture cible réellement séparée existe désormais en parallèle :
voir "Page d'accueil web + Espace Grand Public independants" ci-dessous. L'Espace Organisation continue
de vivre dans Streamlit (outil interne), mais accepte maintenant un lien direct `?view=organisation`
pour y entrer sans repasser par sa propre page d'accueil.

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

## Lieutenant Cyber : une seule IA pour les deux univers

Objectif explicite : que la même IA rende « l'analyse des données, le rendu des tableaux de bord et
l'assistance des deux types d'utilisateurs plus fluides et simples », plutôt que d'avoir un chatbot
texte (Grand Public), une mascotte de quiz, et un tableau de bord purement statique (Organisation)
comme trois expériences disjointes. **Lieutenant Cyber** est cette identité unique, avec deux rôles :

- **Rôle Grand Public (inchangé dans sa mécanique, renommé)** : l'assistant conversationnel/vocal
  (onglet « 🎖️ Lieutenant Cyber ») et la mascotte du jeu de vigilance, dans les 6 catégories.
- **Rôle Organisation (nouveau)** : dans l'Espace Organisation, après une prédiction (flux unique ou
  lot importé), un bouton « 🎖️ Demander à Lieutenant Cyber d'expliquer ce résultat » envoie le résultat
  déjà calculé par le modèle (classe prédite, confiance, probabilités, valeurs des variables ou
  résumé du lot) à Gemini avec un system prompt dédié (`ORG_ANALYST_SYSTEM_PROMPT`), qui répond en
  langage clair avec une recommandation d'action concrète.

**Grounding strict, delibéré** : dans ce rôle, Lieutenant Cyber ne classifie jamais elle-même le
trafic (le modèle de machine learning entraîné reste seul responsable de la classification) et le
system prompt lui interdit explicitement d'inventer un signal, une menace ou une donnée qui ne lui a
pas été fournie dans le contexte de l'appel - un risque d'hallucination serait plus grave ici que pour
un simple chat de sensibilisation, puisque ce rôle s'adresse à des équipes qui prennent des décisions
de sécurité sur la base de cette explication.

Exposé aussi côté API (protégé par `AUTH_MODE`, comme `/predict` et consorts) pour un client externe :
`POST /organisation/explain_flow` (résultat d'un flux unique) et `POST /organisation/explain_batch`
(résumé d'un lot). Sans clé Gemini configurée côté serveur, les deux répondent `503` explicitement,
jamais un contenu vide ni un crash.

## Lancer l'API REST (FastAPI)

```bash
uvicorn api.main:app --reload --port 8000
```

Documentation interactive : http://localhost:8000/docs (Swagger UI). Voir le document
`report/Configuration_API_FastAPI.docx` pour le détail des endpoints historiques (predict*), et les
sections ci-dessous pour les endpoints Grand Public et l'authentification, ajoutés depuis.

L'API expose deux familles d'endpoints :
- **Organisation** (`/model_info`, `/predict`, `/predict_batch`, `/predict_csv`,
  `/organisation/explain_flow`, `/organisation/explain_batch`) : protégés selon `AUTH_MODE` (voir
  "Authentification" ci-dessous). Par défaut (`AUTH_MODE=none`), ouverts comme avant.
- **Grand Public** (`/scenarios`, `/report_steps`, `/assistant/chat`, `/temoignage`,
  `/temoignages/count`, `/game/categories`, `/game/meta`) : toujours ouverts, sans authentification,
  quel que soit `AUTH_MODE` - ce pôle s'adresse au citoyen lambda et ne doit jamais dépendre d'un compte.

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

Ouvrir http://localhost:8080/index.html : la carte "Espace Grand Public" mène à `public.html` (assistant
conversationnel avec lecture vocale automatique des réponses, mini-jeu de vigilance, parcours de collecte
participative anonymisée par des boutons de réponse rapide) ; la carte "Espace Organisation" mène
directement à `http://localhost:8501/?view=organisation` (Streamlit, sans double clic).

Les deux seules valeurs à changer pour déployer ailleurs qu'en local sont dans `web/config.js`
(`API_BASE_URL` et `ORG_APP_URL`).

Limite assumée : contrairement à l'Espace Grand Public de Streamlit, cette page web ne propose pas
(encore) la saisie vocale des questions (uniquement la lecture à voix haute des réponses) - ajouter
l'enregistrement audio navigateur (MediaRecorder) et un endpoint API dédié reste une piste de roadmap.

## Résultat principal

Modèle optimal retenu : **Arbre de Décision élagué et optimisé** (5 variables, profondeur 5)
- Exactitude (test) : 99,04 %
- F1-score macro : 98,72 %
- AUC macro : 99,92 %

## Exécuter la suite de tests

```bash
pip install pytest httpx --break-system-packages
cd kimatey_finnet_guard
python3 -m pytest tests/ -v
```

111 tests (pipeline ML, API - Organisation, Grand Public, jeu de vigilance gamifié, assistance à
l'analyse Lieutenant Cyber, 5 modes d'authentification dont l'auto-inscription self_signup -,
application Streamlit dont l'écran de connexion/création de compte) s'exécutent en moins de 25 secondes.
Le détail de la stratégie de test et des résultats se trouve dans
`report/Rapport_de_Tests.docx`.

## Rapport

Le rapport complet (12 sections : contexte, EDA, méthodologie, résultats des 5 étapes,
réponses aux 4 questions de recherche, limites, conclusion) se trouve dans
`report/Rapport_Projet_ML_SOC.docx`.
