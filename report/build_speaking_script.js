const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  BorderStyle, ShadingType, LevelFormat,
} = require("docx");

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 150 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 260, after: 110 } });
}
function h3(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_3, spacing: { before: 180, after: 80 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, ...opts })],
    spacing: { after: 160 },
    alignment: AlignmentType.JUSTIFIED,
  });
}
function pRuns(runs, opts = {}) {
  return new Paragraph({ children: runs, spacing: { after: 160 }, alignment: AlignmentType.JUSTIFIED, ...opts });
}
function bold(text) { return new TextRun({ text, bold: true, size: 22 }); }

// Bloc "a dire" - encadre visuellement (bordure gauche + fond leger) pour reperer vite le texte a prononcer
function saySay(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, size: 22, color: "10192B" })],
    spacing: { before: 60, after: 200 },
    alignment: AlignmentType.JUSTIFIED,
    indent: { left: 280 },
    border: {
      left: { style: BorderStyle.SINGLE, size: 18, color: "00A98F", space: 8 },
    },
    shading: { type: ShadingType.CLEAR, fill: "EAF7F4" },
  });
}
function label(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 18, color: "5B6B82", allCaps: true, characterSpacing: 12 })],
    spacing: { before: 100, after: 40 },
  });
}
function timing(text) {
  return new Paragraph({
    children: [new TextRun({ text: `⏱ ${text}`, italics: true, size: 18, color: "5B6B82" })],
    spacing: { after: 40 },
  });
}
function hr() {
  return new Paragraph({
    text: "",
    spacing: { before: 100, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "E3E9F2", space: 1 } },
  });
}
function bullets(items) {
  return items.map((t) => new Paragraph({
    children: [new TextRun({ text: t, size: 22 })],
    numbering: { reference: "bullet-list", level: 0 },
    spacing: { after: 90 },
  }));
}
function qa(q, a) {
  return [
    new Paragraph({ children: [new TextRun({ text: "Q — ", bold: true, size: 22, color: "00A98F" }), new TextRun({ text: q, bold: true, size: 22 })], spacing: { before: 160, after: 60 } }),
    new Paragraph({ children: [new TextRun({ text: "R — ", bold: true, size: 22, color: "5B6B82" }), new TextRun({ text: a, size: 22 })], spacing: { after: 60 }, alignment: AlignmentType.JUSTIFIED }),
  ];
}

// ------------------------------------------------------------------
// Chaque slide du PowerPoint (20 au total) recoit : ce qui est affiche,
// ce qu'on peut dire a voix haute, et un minutage indicatif.
// ------------------------------------------------------------------
const slides = [
  {
    n: 1, title: "Titre",
    ecran: "Titre du projet, sous-titre (pipeline ML, API, application de supervision), nom de l'enseignant responsable.",
    duree: "30 s",
    dire:
      "Bonjour, je vais vous présenter mon projet de Machine Learning intitulé Détection Intelligente et Supervision en " +
      "Temps Réel des Attaques Réseau. L'objectif est de construire un pipeline complet, depuis le nettoyage d'un jeu " +
      "de données de trafic réseau jusqu'au déploiement d'une application de supervision et d'une API, en passant par " +
      "la modélisation, la sélection de variables et l'optimisation des hyperparamètres.",
  },
  {
    n: 2, title: "Sommaire",
    ecran: "7 points : contexte/données, méthodologie, prétraitement/modélisation/optimisation, modèle optimal, architecture logicielle, démonstration, résultats/limites/conclusion.",
    duree: "20 s",
    dire:
      "Je vais suivre ce plan en sept temps : je commence par le contexte et les données, puis la méthodologie en cinq " +
      "étapes, le détail de chaque étape, le modèle retenu, l'architecture logicielle, une démonstration en direct, et " +
      "je terminerai par les résultats, les limites et la conclusion.",
  },
  {
    n: 3, title: "Contexte et problématique",
    ecran: "Paragraphe de contexte (multiplication des vecteurs d'attaque, nécessité d'automatiser la surveillance), encadré problématique, 4 questions de recherche Q1-Q4.",
    duree: "60-90 s",
    dire:
      "Dans un centre opérationnel de sécurité, les sondes réseau génèrent un volume de trafic bien trop important " +
      "pour être analysé manuellement flux par flux. La problématique que je me suis posée est donc : comment " +
      "concevoir un pipeline de Machine Learning à la fois robuste, explicable et intégrable dans une interface " +
      "opérateur, pour classer automatiquement chaque flux réseau selon son niveau de menace ? " +
      "J'ai décliné cette problématique en quatre questions de recherche que je vais traiter tout au long de cette " +
      "présentation : l'impact du prétraitement sur la stabilité des modèles, l'apport de la sélection de variables et " +
      "de l'élagage sur la lisibilité, l'apport réel de l'optimisation par GridSearchCV, et enfin comment structurer " +
      "une application utile pour un administrateur de sécurité.",
    cle: "Ne pas lire l'encadré mot à mot : le reformuler avec ses propres mots montre qu'on l'a vraiment compris, pas seulement recopié.",
  },
  {
    n: 4, title: "Le jeu de données",
    ecran: "4 cartes chiffrées (50 000 flux, 9 variables, 4 classes, 0 doublon), graphique de répartition des classes, encadré sur le déséquilibre.",
    duree: "60 s",
    dire:
      "Le jeu de données comporte 50 000 flux réseau décrits par 9 variables explicatives — durée de connexion, " +
      "octets échangés dans les deux sens, taux de paquets par seconde, nombre de ports distincts contactés, etc. — " +
      "et une variable cible à 4 classes : trafic normal, scan de ports, attaque DDoS, et infiltration ou exfiltration. " +
      "On observe un déséquilibre marqué, avec environ 75% de trafic normal contre moins de 5% pour la classe " +
      "infiltration. C'est représentatif d'un contexte SOC réel — les attaques sont rares par nature — mais cela " +
      "m'a obligé à systématiquement stratifier mes découpages train/test et à privilégier des métriques " +
      "macro-moyennées, comme le F1-score macro, plutôt que la seule exactitude qui serait trompeuse ici.",
    cle: "Si le jury demande pourquoi macro et pas micro : parce que l'exactitude seule serait dominée par la classe majoritaire (75% de Normal) et masquerait une mauvaise détection de la classe minoritaire.",
  },
  {
    n: 5, title: "Méthodologie — pipeline en 5 étapes",
    ecran: "Schéma des 5 étapes : prétraitement, modélisation de base, sélection de variables, optimisation, application.",
    duree: "30 s",
    dire:
      "Le pipeline se déroule en cinq étapes séquentielles : d'abord le prétraitement des données, ensuite une phase " +
      "de modélisation de base avec cinq algorithmes différents sur l'ensemble des variables, puis une étape de " +
      "sélection de variables et d'élagage pour simplifier les modèles, une phase d'optimisation par GridSearchCV " +
      "sur le meilleur candidat, et enfin le déploiement dans une application et une API.",
  },
  {
    n: 6, title: "Étape 1 — Prétraitement des données",
    ecran: "Boxplots avant/après traitement des valeurs extrêmes (IQR).",
    duree: "60-75 s",
    dire:
      "Pour le prétraitement, j'ai d'abord imputé les valeurs manquantes par la médiane. Ensuite, j'ai traité les " +
      "valeurs extrêmes par la méthode de l'écart interquartile, avec un facteur k de 1,5 — un choix classique en " +
      "statistique descriptive. Un point méthodologique important : j'ai calculé les statistiques de l'IQR " +
      "uniquement sur l'ensemble d'entraînement, jamais sur le test, pour éviter toute fuite de données. Le split " +
      "train/test est fait à 80/20 de façon stratifiée, pour préserver la même proportion de chaque classe des deux " +
      "côtés. Enfin, j'ai standardisé les variables, ce qui est indispensable pour des algorithmes sensibles à " +
      "l'échelle comme le SVM ou le KNN.",
    cle: "\"Fit sur train uniquement\" est LE point que le jury teste presque toujours en ML — le dire explicitement et sans qu'on le demande est un signal fort.",
  },
  {
    n: 7, title: "Étape 2 — Modélisation de base (5 algorithmes)",
    ecran: "Tableau des 5 modèles (Régression Logistique, KNN, Naive Bayes, SVM, Arbre de Décision) avec exactitude/précision/rappel/F1/AUC sur les 9 variables complètes.",
    duree: "60-75 s",
    dire:
      "J'ai entraîné cinq familles d'algorithmes sur les neuf variables complètes : Régression Logistique, KNN, " +
      "Naive Bayes Gaussien, SVM et Arbre de Décision. Tous obtiennent une exactitude supérieure à 98%, ce qui " +
      "montre que le problème est globalement bien séparable. Deux points à noter : le SVM a été entraîné sur un " +
      "sous-échantillon de 8 000 lignes plutôt que les 40 000 d'entraînement, parce que sa complexité est cubique en " +
      "nombre d'observations et qu'il devenait impraticable sur l'ensemble complet. Et l'Arbre de Décision, bien " +
      "qu'ayant une bonne exactitude, a l'AUC la plus faible du groupe — 98,22% — parce que sans contrainte de " +
      "profondeur il sur-apprend fortement : il atteint 679 nœuds et une profondeur de 30, ce qui le rend illisible " +
      "et fragile en généralisation. C'est précisément ce que je corrige à l'étape suivante.",
  },
  {
    n: 8, title: "Étape 3 — Sélection de variables (RFE)",
    ecran: "Résultat de la RFE (Recursive Feature Elimination) : les 5 variables retenues sur 9.",
    duree: "45-60 s",
    dire:
      "Pour simplifier les modèles sans perdre en performance, j'ai appliqué une élimination récursive de variables, " +
      "la RFE, qui retire itérativement la variable la moins importante. Cinq variables se sont dégagées comme les " +
      "plus discriminantes : les octets échangés de la source vers la destination, le taux de paquets par seconde, " +
      "le nombre de ports de destination distincts, le taux d'erreur de checksum, et la fréquence des drapeaux SYN. " +
      "Ce sont des variables qui ont un sens direct pour un analyste sécurité : un grand nombre de ports distincts " +
      "évoque un scan, une fréquence de SYN élevée évoque un flood SYN typique d'un DDoS.",
  },
  {
    n: 9, title: "Étape 3 — Élagage de l'arbre et comparaison",
    ecran: "Tableau comparatif modèle complet (9 var.) vs réduit (5 var.) pour les 5 algorithmes ; focus sur l'élagage de l'arbre (679→9 nœuds, profondeur 30→3, AUC 98,22%→99,89%).",
    duree: "60-75 s",
    dire:
      "Le résultat le plus marquant de cette étape concerne l'Arbre de Décision : en combinant la réduction à cinq " +
      "variables avec un élagage par coût-complexité, il passe de 679 nœuds et une profondeur de 30, à seulement 9 " +
      "nœuds et une profondeur de 3 — et paradoxalement, son AUC macro s'améliore, passant de 98,22% à 99,89%. C'est " +
      "un exemple concret où réduire la complexité améliore la généralisation plutôt que de la dégrader : l'arbre " +
      "complet apprenait du bruit, l'arbre élagué apprend le signal. Pour les autres algorithmes, la réduction à " +
      "cinq variables maintient des performances quasiment identiques au modèle à neuf variables, ce qui confirme " +
      "que les quatre variables écartées apportaient peu d'information supplémentaire.",
    cle: "C'est la réponse directe à la question de recherche Q2 (sélection/élagage) — bien la relier explicitement si le jury pose la question.",
  },
  {
    n: 10, title: "Étape 4 — Optimisation par GridSearchCV",
    ecran: "Grille d'hyperparamètres testée pour l'Arbre de Décision, validation croisée stratifiée à 5 plis, meilleurs hyperparamètres trouvés.",
    duree: "60 s",
    dire:
      "J'ai ensuite optimisé les hyperparamètres de l'arbre de décision élagué par recherche en grille, avec une " +
      "validation croisée stratifiée à 5 plis. J'ai testé différentes valeurs de profondeur maximale, de nombre " +
      "minimal d'échantillons par feuille, et de coefficient d'élagage ccp_alpha. La configuration retenue est une " +
      "profondeur maximale de 5, un minimum d'un échantillon par feuille, et un ccp_alpha nul — c'est-à-dire que " +
      "l'élagage effectué manuellement à l'étape précédente s'est révélé déjà proche de l'optimum trouvé " +
      "automatiquement par la recherche en grille. L'intérêt de cette étape n'est pas tant le gain de performance, " +
      "qui reste modéré, que la garantie méthodologique : la validation croisée à 5 plis évite de sur-ajuster les " +
      "hyperparamètres à un seul découpage train/test.",
  },
  {
    n: 11, title: "Modèle optimal retenu",
    ecran: "Grande carte statistique sombre : Arbre de Décision optimisé, 99,04% exactitude, 98,72% F1-macro, 99,92% AUC macro, 5 variables, 9 nœuds.",
    duree: "45 s",
    dire:
      "Le modèle final retenu pour la production est donc cet Arbre de Décision élagué et optimisé, entraîné sur " +
      "cinq variables. Il atteint 99,04% d'exactitude sur l'ensemble de test, un F1-score macro de 98,72%, et une " +
      "AUC macro de 99,92%. Je l'ai préféré à la Régression Logistique — qui a des scores très proches — pour une " +
      "raison d'explicabilité : avec seulement 9 nœuds, un arbre de décision peut être lu et audité directement par " +
      "un analyste sécurité, alors qu'une régression logistique ou un SVM restent des boîtes plus difficiles à " +
      "justifier devant un incident réel.",
    cle: "Argument clé si le jury demande \"pourquoi pas la régression logistique qui a un score quasi identique ?\" : l'explicabilité en contexte SOC.",
  },
  {
    n: 12, title: "Architecture logicielle du produit final",
    ecran: "Schéma : Clients (curl, Postman, Streamlit, SIEM) → API FastAPI (Uvicorn :8000) → ModelService (prétraitement + predict) → Artefacts entraînés (modèle, scaler, médiane, IQR, cache).",
    duree: "60 s",
    dire:
      "Pour rendre ce modèle utilisable, j'ai construit deux interfaces qui partagent rigoureusement le même code de " +
      "prétraitement et le même modèle entraîné, chargé une seule fois en mémoire grâce à un cache : une application " +
      "Streamlit pour un opérateur humain, et une API REST FastAPI pour une intégration programmatique — par exemple " +
      "depuis un SIEM ou un script d'automatisation. Toutes les requêtes de l'API passent par une validation " +
      "Pydantic stricte avant d'atteindre le modèle, ce qui évite qu'un flux mal formé fasse planter le service.",
    cle: "Le point important à faire ressortir : \"même pipeline, même modèle\" pour les deux interfaces — pas deux implémentations divergentes qui pourraient donner des résultats différents.",
  },
  {
    n: 13, title: "Démonstration — Tableau de bord Streamlit",
    ecran: "Capture (ou démo live) : bannière, cartes KPI, tableau de comparaison des algorithmes, courbes ROC.",
    duree: "30-45 s (+ démo live si le temps le permet)",
    dire:
      "Voici le tableau de bord principal de l'application. On y retrouve les indicateurs clés du modèle en " +
      "production — exactitude, F1, AUC, nombre de variables retenues — ainsi que le tableau de comparaison des " +
      "cinq algorithmes optimisés et les courbes ROC one-vs-rest du modèle final. C'est l'écran d'accueil qui donne " +
      "à un responsable sécurité une vue d'ensemble immédiate de la fiabilité du système.",
  },
  {
    n: 14, title: "Démonstration — Import CSV & analyse de logs",
    ecran: "Import d'un fichier CSV de logs, aperçu du tableau chargé, résultats agrégés (flux analysés, menaces détectées, taux de menace).",
    duree: "30-45 s",
    dire:
      "Cet onglet permet d'importer un fichier CSV de logs réseau — par exemple un export de sonde — et de le faire " +
      "analyser en une fois par le modèle. Sur ce fichier de démonstration de 50 flux, le modèle détecte 16 flux " +
      "suspects, soit un taux de menace de 32%. C'est le même résultat, au flux près, que celui obtenu en soumettant " +
      "ce fichier directement à l'API — preuve que les deux interfaces sont bien cohérentes entre elles.",
  },
  {
    n: 15, title: "Démonstration — Prédiction unique & journal d'alertes",
    ecran: "Formulaire de saisie manuelle des 9 caractéristiques d'un flux, résultat avec niveau de confiance ; journal d'alertes horodaté et exportable.",
    duree: "30-45 s",
    dire:
      "Pour analyser un flux unique, par exemple lors d'une investigation manuelle, l'opérateur peut saisir " +
      "directement les caractéristiques du flux et obtenir instantanément la classe prédite avec son niveau de " +
      "confiance. Chaque analyse, qu'elle vienne du CSV, du formulaire, ou de la surveillance en direct, alimente " +
      "automatiquement un journal d'alertes horodaté, consultable et exportable en CSV.",
  },
  {
    n: 16, title: "Démonstration — Surveillance en direct",
    ecran: "Simulation d'un flux continu de connexions échantillonnées dans le vrai jeu de données, avec mise à jour progressive des compteurs, du graphique et de la table (vérité terrain connue).",
    duree: "45-60 s (démo live recommandée si possible)",
    dire:
      "Le dernier onglet simule une supervision en conditions proches du temps réel : le modèle analyse un à un des " +
      "flux échantillonnés aléatoirement dans le vrai jeu de données, dont je connais la vérité terrain, et " +
      "l'affichage — compteurs, graphique de répartition, table des derniers flux — se met à jour progressivement, " +
      "sans recharger la page. On peut ainsi comparer en direct la prédiction du modèle à la réalité et constater sa " +
      "précision. J'insiste sur le mot simulation : ce n'est pas un flux réseau réellement capturé en direct, mais " +
      "un rejeu réaliste du jeu de données existant — la vraie intégration temps réel à une sonde réseau ou un SIEM " +
      "est identifiée comme une perspective d'évolution, pas encore réalisée dans ce projet.",
    cle: "Honnêteté importante : bien préciser \"simulation\", ne jamais laisser penser que c'est branché sur un flux réseau réel — le jury apprécie la rigueur plus que l'effet.",
  },
  {
    n: 17, title: "API REST FastAPI — endpoints & validation",
    ecran: "Tableau des endpoints (GET /health, /model_info ; POST /predict, /predict_batch, /predict_csv), exemple de réponse JSON, encadré sur le test croisé de cohérence.",
    duree: "45-60 s",
    dire:
      "Côté API, cinq endpoints sont exposés : deux endpoints de santé et de métadonnées, et trois endpoints de " +
      "prédiction — pour un flux unique, une liste de flux en JSON, ou un fichier CSV entier. Chaque requête est " +
      "validée automatiquement par Pydantic — un champ manquant ou invalide renvoie une erreur 422 explicite plutôt " +
      "qu'un plantage. La documentation Swagger est générée automatiquement sur /docs. J'ai vérifié la cohérence " +
      "entre l'API et l'application Streamlit avec un test croisé strict : le même fichier de logs soumis aux deux " +
      "interfaces renvoie exactement le même résultat, flux par flux.",
  },
  {
    n: 18, title: "Synthèse — réponses aux questions de recherche",
    ecran: "4 cartes Q1-Q4 avec une réponse synthétique à chaque question de recherche posée en introduction.",
    duree: "60-75 s",
    dire:
      "Je reviens maintenant sur les quatre questions posées en introduction. Sur le prétraitement : il stabilise " +
      "les frontières de décision, en particulier pour le SVM et le KNN qui sont sensibles à l'échelle, mais il faut " +
      "le manier avec prudence, car certaines valeurs extrêmes sont en réalité le signal même de l'attaque, pas du " +
      "bruit à éliminer. Sur la sélection de variables et l'élagage : ils améliorent nettement la lisibilité du " +
      "modèle sans coût en performance, l'arbre passant de 679 à 9 nœuds. Sur GridSearchCV : le gain de performance " +
      "brut est modéré, mais l'apport méthodologique — la garantie de généralisation via la validation croisée — est " +
      "réel. Et sur l'application : j'ai structuré une architecture en quatre modules fonctionnels côté Streamlit, " +
      "complétée par une API FastAPI pour l'intégration programmatique.",
  },
  {
    n: 19, title: "Limites et perspectives",
    ecran: "4 limites identifiées : séparabilité très forte (dataset probablement en partie synthétique), SVM sous-échantillonné, déséquilibre des classes, traitement par lot plutôt que flux temps réel.",
    duree: "60-75 s",
    dire:
      "Je conclus par un regard critique sur mon propre travail. Premièrement, les scores obtenus — au-delà de 98% " +
      "pour tous les modèles — sont probablement optimistes : cela suggère que le jeu de données est en partie " +
      "synthétique et plus séparable qu'un trafic réel, qui serait plus bruité. Deuxièmement, le SVM a été entraîné " +
      "sur un sous-échantillon de 8 000 lignes pour rester calculable, ce qui peut sous-estimer son potentiel réel. " +
      "Troisièmement, le déséquilibre des classes a été traité par stratification et métriques macro, mais des " +
      "techniques comme le SMOTE ou une pondération explicite des classes pourraient encore améliorer la détection " +
      "de la classe minoritaire, l'infiltration, qui ne représente que 4,96% des flux. Enfin, le système actuel " +
      "traite des lots de données — fichiers CSV ou formulaires — et non un flux réseau réellement continu : " +
      "l'intégration à un connecteur SIEM ou une file de messages type Kafka serait l'extension naturelle pour un " +
      "vrai déploiement en production.",
    cle: "Assumer ces limites soi-même, avant que le jury ne les soulève, est le signal le plus fort de maîtrise du sujet.",
  },
  {
    n: 20, title: "Conclusion",
    ecran: "Résumé du projet, 4 chiffres clés (99,04% exactitude, 98,72% F1-macro, 99,92% AUC macro, 9 nœuds), phrase de clôture, \"Merci de votre attention — Questions ?\"",
    duree: "30-45 s",
    dire:
      "Pour conclure, ce projet m'a permis de construire un pipeline de Machine Learning complet et cohérent de bout " +
      "en bout : du nettoyage rigoureux des données jusqu'au déploiement d'une application de supervision et d'une " +
      "API opérationnelles, en passant par une démarche de sélection de variables et d'optimisation justifiée à " +
      "chaque étape. Le modèle retenu combine une performance élevée — 99,04% d'exactitude, 99,92% d'AUC macro — et " +
      "une explicabilité forte avec seulement 9 nœuds, ce qui répond aux deux exigences essentielles pour la " +
      "confiance d'une équipe de sécurité dans un système de détection automatisée. Je vous remercie de votre " +
      "attention et je suis prêt à répondre à vos questions.",
  },
];

const qaPairs = [
  ["Pourquoi avoir choisi l'Arbre de Décision plutôt que la Régression Logistique, qui a un score presque identique (98,99% vs 99,04%) ?",
    "Les deux modèles ont des performances très proches, mais l'arbre élagué à 9 nœuds est directement lisible par un analyste sécurité : chaque décision de classification peut être expliquée par une suite de seuils sur des variables concrètes (nombre de ports, taux de SYN...). En contexte SOC, l'explicabilité d'une alerte est aussi importante que sa précision, ce qui a fait pencher le choix vers l'arbre."],
  ["Le split train/test a-t-il été fait avant ou après le traitement des valeurs extrêmes (IQR) ?",
    "Avant. Le split stratifié 80/20 est fait en premier, puis les bornes de l'IQR (Q1, Q3) sont calculées uniquement sur l'ensemble d'entraînement et appliquées ensuite au test. C'est une précaution volontaire contre la fuite de données : si on calculait les bornes sur l'ensemble complet, des informations du test influenceraient indirectement l'entraînement."],
  ["Pourquoi le SVM a-t-il été entraîné sur un sous-échantillon et pas sur l'ensemble complet ?",
    "Parce que la complexité d'entraînement du SVM avec noyau croît de façon cubique avec le nombre d'observations. Sur 40 000 lignes d'entraînement, le temps de calcul devenait impraticable dans le cadre du projet. J'ai donc utilisé un sous-échantillon de 8 000 lignes, ce qui reste une limite assumée et documentée : le potentiel réel du SVM sur l'ensemble complet est probablement sous-estimé."],
  ["Comment expliquez-vous que l'AUC de l'arbre passe de 98,22% à 99,89% après l'élagage, alors qu'on retire de la complexité au modèle ?",
    "L'arbre complet, avec 679 nœuds et une profondeur de 30, sur-apprend le bruit spécifique à l'ensemble d'entraînement plutôt que le vrai signal. En élaguant par coût-complexité et en réduisant à 5 variables pertinentes, on force le modèle à ne garder que les règles de décision qui généralisent, ce qui améliore mécaniquement sa performance sur le test. C'est un exemple concret du compromis biais-variance : moins de variance, meilleure généralisation."],
  ["Le F1-score macro et l'AUC macro, c'est quoi la différence, et pourquoi les utiliser plutôt que l'exactitude seule ?",
    "L'exactitude globale peut être trompeuse sur un jeu déséquilibré : un modèle qui prédit toujours 'Normal' aurait déjà 75% d'exactitude sans détecter aucune attaque. Le F1-score macro moyenne le F1 de chaque classe avec le même poids, quelle que soit sa fréquence, ce qui pénalise fortement un modèle qui ignorerait la classe minoritaire Infiltration. L'AUC macro fait la même chose pour la capacité de discrimination du modèle, classe par classe."],
  ["Qu'est-ce que le GridSearchCV a réellement apporté, si les hyperparamètres trouvés sont proches de ceux choisis manuellement à l'étape d'élagage ?",
    "Le gain de performance brut est effectivement modéré, mais l'apport n'est pas la performance en elle-même : c'est la garantie méthodologique. La validation croisée stratifiée à 5 plis teste chaque combinaison d'hyperparamètres sur 5 découpages différents des données, ce qui évite de choisir des hyperparamètres qui ne marcheraient bien que sur un seul split par chance. Le fait que le résultat automatique confirme le choix manuel est en soi une validation de la démarche d'élagage."],
  ["L'onglet 'Surveillance en direct' analyse-t-il un vrai flux réseau en temps réel ?",
    "Non, et c'est important de le préciser : c'est une simulation. Elle échantillonne aléatoirement des flux du jeu de données réel, dont je connais la vérité terrain, et les fait passer un par un dans le modèle en production avec une mise à jour progressive de l'affichage — sans rechargement de page. Cela permet de visualiser le comportement du système en conditions proches du temps réel, mais l'intégration à un flux réseau réellement capturé en direct, via une sonde ou un connecteur SIEM, reste une perspective non implémentée dans ce projet."],
  ["Comment garantissez-vous que l'application Streamlit et l'API FastAPI donnent le même résultat pour un même flux ?",
    "Les deux interfaces appellent exactement le même code de prétraitement et chargent le même modèle entraîné, via un module partagé (model_service). Ce n'est pas une garantie seulement théorique : j'ai écrit un test automatisé qui soumet le même fichier de 50 flux à l'API et à l'application, et vérifie que les prédictions sont identiques ligne par ligne. Ce test fait partie de ma suite de 57 tests automatisés et passe avec succès."],
  ["Quelle est la principale limite de ce projet si vous deviez en choisir une seule ?",
    "La séparabilité très forte du jeu de données. Tous les modèles dépassent 98% d'exactitude et d'AUC dès l'étape de base, ce qui est un signal que les données sont probablement en partie synthétiques ou moins bruitées qu'un trafic réseau réel. Sur un trafic de production réel, plus bruité et avec des attaques plus subtiles, je m'attendrais à des performances plus modestes, et ce serait le premier terrain de validation à mener avant tout déploiement en conditions réelles."],
];

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullet-list",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 260 } } } }],
    }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
    children: [
      new Paragraph({ text: "Script de Soutenance", heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER, spacing: { before: 600, after: 120 } }),
      new Paragraph({
        children: [new TextRun({ text: "Guide de présentation orale — Détection Intelligente et Supervision en Temps Réel des Attaques Réseau", italics: true, size: 24, color: "5B6B82" })],
        alignment: AlignmentType.CENTER, spacing: { after: 60 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "Projet Master 1 Informatique — UFRMI · ECUE Machine Learning · Réalisé par Komoe Edgar Junior · Responsable de l'enseignement : Dr ASSOHOUN E Stanislas", size: 20, color: "5B6B82" })],
        alignment: AlignmentType.CENTER, spacing: { after: 400 },
      }),

      h1("Comment utiliser ce document"),
      p(
        "Ce script accompagne, slide par slide, le PowerPoint de soutenance (20 diapositives). Il n'est pas fait pour " +
        "être lu mot à mot devant le jury — l'objectif est de se l'approprier, de le répéter à voix haute plusieurs " +
        "fois, puis de ne garder en mémoire que les idées clés et l'enchaînement logique. Chaque section indique : " +
        "ce qui est affiché à l'écran, un texte proposé (encadré en vert, à reformuler avec ses propres mots), une " +
        "durée indicative, et parfois un point clé à ne pas oublier."
      ),
      p(
        "Durée totale visée : environ 12 à 16 minutes de présentation (hors questions), ce qui correspond à un " +
        "format de soutenance M1 classique. Si le temps est serré, les slides 13 à 17 (démonstration) peuvent être " +
        "raccourcies en montrant l'application en direct plutôt qu'en commentant chaque capture longuement — " +
        "l'application qui tourne réellement devant le jury est plus convaincante qu'une description."
      ),
      p(
        "Conseils généraux : parler au jury, pas à l'écran ; ne pas lire les diapositives (le jury sait déjà lire) ; " +
        "ralentir sur les chiffres et les termes techniques ; assumer soi-même les limites du projet avant qu'on ne " +
        "les pointe — cela renforce la crédibilité plutôt que de l'affaiblir."
      ),

      h1("Script détaillé, diapositive par diapositive"),
      ...slides.flatMap((s) => [
        h2(`Slide ${s.n} — ${s.title}`),
        label("À l'écran"),
        p(s.ecran, { size: 20, color: "5B6B82" }),
        label("Minutage indicatif"),
        timing(s.duree),
        label("Ce qu'on peut dire"),
        saySay(s.dire),
        ...(s.cle ? [label("Point clé"), p(`💡 ${s.cle}`, { size: 20, italics: true, color: "10192B" })] : []),
        hr(),
      ]),

      h1("Questions probables du jury et éléments de réponse"),
      p(
        "Ces questions correspondent aux points de vigilance classiques d'un jury de Machine Learning : fuite de " +
        "données, choix de métriques, justification des choix de modèle, et limites du travail. Les réponses " +
        "proposées reprennent des éléments déjà présents dans le rapport et le PowerPoint — l'idée est de pouvoir " +
        "les retrouver vite sous le stress de l'oral, pas d'apprendre un texte nouveau."
      ),
      ...qaPairs.flatMap(([q, a]) => qa(q, a)),

      h1("Dernier point avant d'entrer en salle"),
      p(
        "Si une question sort du script ci-dessus et que la réponse n'est pas connue avec certitude, il vaut mieux " +
        "dire honnêtement \"je n'ai pas testé ce cas précis, mais voici comment je l'aborderais\" plutôt que " +
        "d'improviser un chiffre inventé. Un jury valorise davantage la rigueur et la conscience des limites de son " +
        "propre travail qu'une réponse assurée mais fausse."
      ),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("report/Script_Soutenance.docx", buf);
  console.log("Script de soutenance genere : report/Script_Soutenance.docx");
});
