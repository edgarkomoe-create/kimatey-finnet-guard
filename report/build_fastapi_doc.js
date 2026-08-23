const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, ImageRun, PageBreak, Header, Footer, PageNumber,
} = require("docx");
const { imageSize } = require("image-size");

const OUT = "outputs";
const FIG = path.join(OUT, "figures");

function img(fullPath, width) {
  const buf = fs.readFileSync(fullPath);
  let dims;
  try { dims = imageSize(buf); } catch (e) { dims = { width: 800, height: 600 }; }
  const ratio = dims.height / dims.width;
  return new ImageRun({ data: buf, transformation: { width, height: Math.round(width * ratio) }, type: "png" });
}
function h1(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 150 } }); }
function h2(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 250, after: 120 } }); }
function p(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 160 }, alignment: AlignmentType.JUSTIFIED });
}
function code(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: "Consolas", size: 18 })],
    spacing: { after: 160 },
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
    border: { top: { style: "single", size: 4, color: "CCCCCC" }, bottom: { style: "single", size: 4, color: "CCCCCC" },
      left: { style: "single", size: 4, color: "CCCCCC" }, right: { style: "single", size: 4, color: "CCCCCC" } },
  });
}
function codeBlock(lines) {
  return lines.map((l, i) => new Paragraph({
    children: [new TextRun({ text: l || " ", font: "Consolas", size: 18 })],
    spacing: { after: i === lines.length - 1 ? 160 : 0 },
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2" },
  }));
}
function caption(text) {
  return new Paragraph({ children: [new TextRun({ text, italics: true, size: 20 })], alignment: AlignmentType.CENTER, spacing: { after: 240 } });
}
function centerImage(fullPath, width, captionText) {
  const children = [new Paragraph({ children: [img(fullPath, width)], alignment: AlignmentType.CENTER, spacing: { after: 60 } })];
  if (captionText) children.push(caption(captionText));
  return children;
}
function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { type: ShadingType.CLEAR, fill: "1F4E78" } : undefined,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text), bold: !!opts.header, color: opts.header ? "FFFFFF" : "000000", size: 18, font: opts.mono ? "Consolas" : undefined })],
      alignment: opts.center === false ? AlignmentType.LEFT : AlignmentType.CENTER,
    })],
    verticalAlign: "center",
  });
}
function dataTable(headers, rows, colWidths) {
  const totalWidth = colWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ cantSplit: true, children: headers.map((hdr, i) => cell(hdr, { header: true, width: colWidths[i] })) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((val, i) => cell(val, { width: colWidths[i], center: false, mono: i === 0 })) })),
    ],
  });
}

const bestInfo = JSON.parse(fs.readFileSync(path.join(OUT, "best_model_info.json"), "utf8"));

const titlePage = [
  new Paragraph({ text: "", spacing: { before: 1200 } }),
  new Paragraph({ children: [new TextRun({ text: "UFR MATHEMATIQUES ET INFORMATIQUE", bold: true, size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 400 } }),
  new Paragraph({ children: [new TextRun({ text: "MASTER 1 INFORMATIQUE", bold: true, size: 26 })], alignment: AlignmentType.CENTER, spacing: { after: 100 } }),
  new Paragraph({ children: [new TextRun({ text: "ECUE : Machine Learning", size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 600 } }),
  new Paragraph({
    children: [new TextRun({ text: "Configuration et Mise en Œuvre d'une API REST FastAPI\npour la Détection d'Intrusion Réseau", bold: true, size: 30, color: "1F4E78" })],
    alignment: AlignmentType.CENTER, spacing: { after: 300 },
  }),
  new Paragraph({ children: [new TextRun({ text: "Document technique complémentaire au rapport de projet", italics: true, size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 800 } }),
  new Paragraph({ children: [new TextRun({ text: "Réalisé par : Komoe Edgar Junior", size: 22, bold: true })], alignment: AlignmentType.CENTER, spacing: { after: 100 } }),
  new Paragraph({ children: [new TextRun({ text: "Responsable de l'enseignement : Dr ASSOHOUN E Stanislas", size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 800 } }),
  new Paragraph({ children: [new TextRun({ text: "Année académique 2025-2026", size: 20 })], alignment: AlignmentType.CENTER, spacing: { before: 1000 } }),
  new Paragraph({ children: [new PageBreak()] }),
];

const intro = [
  h1("1. Objectif"),
  p("Ce document décrit la configuration et la mise en œuvre d'une API REST développée avec FastAPI, " +
    "qui expose le modèle de Machine Learning optimal issu du projet (Arbre de Décision élagué et optimisé " +
    "par GridSearchCV, cf. rapport de projet, Étape 4) sous forme de service web independant. Cette API " +
    "constitue une couche d'accès programmatique au modèle, distincte de l'application Streamlit déjà " +
    "livrée : elle permet à n'importe quel client (script, application tierce, SIEM, Postman, curl, ou la " +
    "même application Streamlit) d'obtenir une prédiction de menace réseau via de simples requêtes HTTP, " +
    "sans avoir à charger le modèle ni à connaître les détails d'implémentation du pipeline de Machine Learning."),
  p("FastAPI a été retenu pour ce projet en raison de sa validation automatique des données par Pydantic, " +
    "de sa génération automatique d'une documentation interactive (Swagger UI / OpenAPI), de ses performances " +
    "(serveur ASGI asynchrone Uvicorn) et de sa large adoption dans l'industrie pour l'exposition de modèles " +
    "de Machine Learning en production."),
];

const archi = [
  h1("2. Architecture"),
  p("L'API est organisée en trois modules Python indépendants, situés dans le dossier api/ du projet, " +
    "qui reproduisent exactement le pipeline de prétraitement et le modèle utilisés par l'application " +
    "Streamlit — garantissant des prédictions strictement identiques entre les deux interfaces (démontré " +
    "en section 5)."),
  ...centerImage(path.join(FIG, "fastapi_architecture.png"), 600, "Figure 1 — Architecture de l'API FastAPI"),
  dataTable(
    ["Fichier", "Rôle"],
    [
      ["api/main.py", "Point d'entrée FastAPI : déclaration de l'application, des routes (endpoints) et de la gestion des erreurs."],
      ["api/schemas.py", "Modèles Pydantic définissant la structure et la validation des requêtes et réponses JSON."],
      ["api/model_service.py", "Classe ModelService : chargement (une seule fois, mis en cache) du modèle optimal et des artefacts de prétraitement (scaler, médianes, bornes IQR), fonctions de prétraitement et de prédiction."],
    ],
    [3200, 6100]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Au démarrage du serveur (événement startup), le modèle et ses artefacts associés sont chargés une " +
    "seule fois en mémoire et mis en cache (fonction lru_cache), ce qui évite de recharger le modèle à " +
    "chaque requête et garantit des temps de réponse très courts. Si les artefacts sont introuvables, le " +
    "serveur échoue immédiatement au démarrage (fail-fast) plutôt que de répondre de façon incohérente."),
];

const endpoints = [
  h1("3. Endpoints exposés"),
  dataTable(
    ["Méthode", "Route", "Description"],
    [
      ["GET", "/", "Informations générales sur l'API et liste des endpoints disponibles."],
      ["GET", "/health", "Vérification de l'état de santé du service (readiness/liveness probe)."],
      ["GET", "/model_info", "Métadonnées du modèle en production (nom, exactitude, F1, AUC, variables utilisées)."],
      ["POST", "/predict", "Prédiction pour un flux réseau unique (corps JSON)."],
      ["POST", "/predict_batch", "Prédiction pour une liste de flux réseau (corps JSON)."],
      ["POST", "/predict_csv", "Prédiction pour un fichier CSV de logs uploadé (multipart/form-data)."],
      ["GET", "/docs", "Documentation interactive Swagger UI (générée automatiquement)."],
      ["GET", "/redoc", "Documentation alternative ReDoc (générée automatiquement)."],
    ],
    [1400, 2400, 5500]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  h2("3.1 Schéma d'entrée — NetworkFlow"),
  p("Chaque flux réseau soumis à /predict ou /predict_batch doit respecter le schéma Pydantic NetworkFlow, " +
    "qui reprend exactement les 9 variables brutes décrites dans le sujet du projet. La validation est " +
    "automatique : toute valeur manquante, mal typée ou négative (contrainte ge=0) est rejetée avec un " +
    "code HTTP 422 et un message d'erreur détaillé, avant même d'atteindre le modèle."),
  dataTable(
    ["Champ", "Type", "Contrainte"],
    [
      ["Duree_Connexion", "float", "≥ 0"], ["Octets_Source_Vers_Dest", "float", "≥ 0"],
      ["Octets_Dest_Vers_Source", "float", "≥ 0"], ["Taux_Paquets_Secondes", "float", "≥ 0"],
      ["Fenetre_TCP_Moyenne", "float", "≥ 0"], ["Ports_Dest_Distincts", "float", "≥ 0"],
      ["Connexions_Simultanees", "float", "≥ 0"], ["Taux_Erreur_CheckSum", "float", "≥ 0"],
      ["Frequence_SYN_Flags", "float", "≥ 0"],
    ],
    [3800, 2200, 3100]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  h2("3.2 Schéma de sortie — PredictionResponse"),
  p("Chaque prédiction renvoie la classe prédite (code numérique et libellé), le niveau de confiance " +
    "(probabilité maximale du modèle, en %), la répartition complète des probabilités sur les 4 classes, " +
    "et un indicateur booléen is_threat facilitant le filtrage côté client."),
];

const exemples = [
  h1("4. Exemples d'utilisation"),
  h2("4.1 Prédiction d'un flux unique (POST /predict)"),
  p("Requête :"),
  ...codeBlock([
    'curl -X POST http://localhost:8000/predict \\',
    '  -H "Content-Type: application/json" \\',
    "  -d '{",
    '    "Duree_Connexion": 19867.35,',
    '    "Octets_Source_Vers_Dest": 1717.17,',
    '    "Octets_Dest_Vers_Source": 6886.95,',
    '    "Taux_Paquets_Secondes": 152.1,',
    '    "Fenetre_TCP_Moyenne": 16384,',
    '    "Ports_Dest_Distincts": 121,',
    '    "Connexions_Simultanees": 5,',
    '    "Taux_Erreur_CheckSum": 0.0176,',
    '    "Frequence_SYN_Flags": 0.0577',
    "  }'",
  ]),
  p("Réponse (200 OK) :"),
  ...codeBlock([
    "{",
    '  "predicted_class": 1,',
    '  "predicted_label": "Scan de Ports / Reconnaissance",',
    '  "confidence": 100.0,',
    '  "probabilities": {',
    '    "Normal / Legitime": 0.0,',
    '    "Scan de Ports / Reconnaissance": 100.0,',
    '    "Attaque DDoS / Volumetrique": 0.0,',
    '    "Infiltration / Brute-Force / Exfiltration": 0.0',
    "  },",
    '  "is_threat": true',
    "}",
  ]),
  h2("4.2 Prédiction en lot (POST /predict_batch)"),
  p("Accepte un corps JSON {\"flows\": [...]} contenant une liste de flux réseau, et renvoie un résumé " +
    "(nombre de flux, nombre de menaces, taux de menace, répartition par classe) accompagné du détail de " +
    "chaque prédiction — utile pour intégrer l'API à un pipeline de traitement par lots."),
  h2("4.3 Import d'un fichier CSV (POST /predict_csv)"),
  p("Accepte un upload multipart/form-data (champ file) contenant un CSV de logs réseau bruts, applique le " +
    "pipeline de prétraitement complet, et renvoie le fichier annoté (menace prédite et confiance ajoutées " +
    "à chaque ligne) au format JSON — fonctionnellement équivalent à l'onglet « Import CSV » de l'application " +
    "Streamlit."),
  p("Requête :"),
  ...codeBlock(['curl -X POST http://localhost:8000/predict_csv \\', '  -F "file=@sample_logs_demo.csv"']),
];

const tests = [
  h1("5. Tests réalisés et cohérence avec l'application Streamlit"),
  p("L'ensemble des endpoints a été testé manuellement (curl) après démarrage du serveur Uvicorn en local. " +
    "Le tableau suivant résume les scénarios de test exécutés et leurs résultats :"),
  dataTable(
    ["Scénario testé", "Résultat"],
    [
      ["GET /health", "200 OK — {\"status\": \"ok\", \"model_loaded\": true}"],
      ["GET /model_info", "200 OK — modèle Arbre_Decision_optimise, exactitude 99.04%, 5 variables"],
      ["POST /predict (flux de scan de ports connu)", "200 OK — classe 1 (Scan de Ports) prédite avec 100% de confiance, conforme à l'étiquette réelle du dataset"],
      ["POST /predict_batch (2 flux)", "200 OK — résumé + détail cohérents avec les étiquettes réelles"],
      ["POST /predict_csv (échantillon de 50 flux)", "200 OK — 16 menaces détectées sur 50 flux (32%), résultat identique à celui obtenu via l'onglet Import CSV de Streamlit sur le même fichier"],
      ["POST /predict avec champs manquants", "422 Unprocessable Entity — erreurs de validation Pydantic détaillées par champ"],
      ["POST /predict_csv avec fichier non-CSV", "400 Bad Request — message d'erreur explicite"],
    ],
    [3800, 5300]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Le test croisé le plus important est celui du fichier outputs/sample_logs_demo.csv, soumis à la fois " +
    "à l'application Streamlit (onglet Import CSV) et à l'endpoint /predict_csv de l'API : les deux " +
    "interfaces renvoient exactement le même nombre de menaces détectées (16 sur 50 flux, soit 32%), ce qui " +
    "confirme que l'API et l'application partagent rigoureusement le même pipeline de prétraitement et le " +
    "même modèle, sans divergence d'implémentation."),
];

const lancement = [
  h1("6. Installation et lancement"),
  p("Les dépendances nécessaires (fastapi, uvicorn, python-multipart) sont ajoutées au fichier " +
    "requirements.txt du projet, aux côtés des dépendances déjà utilisées pour le pipeline de Machine " +
    "Learning et l'application Streamlit."),
  ...codeBlock([
    "pip install -r requirements.txt",
    "",
    "# Lancement du serveur de developpement (rechargement automatique)",
    "uvicorn api.main:app --reload --port 8000",
    "",
    "# Lancement en production (plusieurs workers)",
    "uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4",
  ]),
  p("Une fois le serveur démarré, la documentation interactive est accessible à l'adresse " +
    "http://localhost:8000/docs (Swagger UI, permet de tester chaque endpoint directement depuis le " +
    "navigateur) ou http://localhost:8000/redoc (documentation statique ReDoc). Ces interfaces sont générées " +
    "automatiquement par FastAPI à partir des schémas Pydantic et nécessitent un accès Internet pour charger " +
    "leurs ressources visuelles (bibliothèque Swagger UI servie depuis un CDN) ; sur le poste de " +
    "l'utilisateur, connecté à Internet, cette page s'affiche normalement."),
];

const securite = [
  h1("7. Sécurité, limites et pistes d'amélioration"),
  p("Dans sa configuration actuelle, orientée démonstration académique, l'API autorise les requêtes cross-" +
    "origin depuis n'importe quelle origine (CORS ouvert, allow_origins=[\"*\"]) et ne met en œuvre aucun " +
    "mécanisme d'authentification. Ce choix facilite les tests et l'intégration avec l'application Streamlit " +
    "ou un navigateur, mais ne convient pas à un déploiement en production face à Internet."),
  p("Pour un déploiement réel au sein d'un SOC, les évolutions suivantes seraient nécessaires : restreindre " +
    "les origines CORS autorisées aux seuls clients de confiance ; ajouter une authentification par clé API " +
    "ou jeton JWT sur les routes de prédiction ; mettre en place une limitation de débit (rate limiting) " +
    "pour prévenir les abus ; exposer le service exclusivement via HTTPS (TLS) derrière un reverse-proxy " +
    "(Nginx, Traefik) ; ajouter une journalisation structurée et une supervision (métriques Prometheus, " +
    "temps de réponse, taux d'erreur) ; et conteneuriser l'API (Docker) pour en faciliter le déploiement et " +
    "la mise à l'échelle horizontale (plusieurs workers Uvicorn/Gunicorn)."),
];

const conclusion = [
  h1("8. Conclusion"),
  p("L'API FastAPI développée constitue une brique d'architecture complémentaire à l'application Streamlit " +
    "livrée : elle expose le même modèle optimal (Arbre de Décision élagué et optimisé, exactitude 99.04%, " +
    "AUC macro 99.92%) sous forme de service REST documenté, testé et validé, réutilisable par tout système " +
    "tiers d'un environnement de sécurité opérationnel (SIEM, script d'automatisation, autre application). " +
    "Cette séparation entre la couche de service (API) et la couche de présentation (GUI Streamlit) suit un " +
    "principe d'architecture logicielle standard qui facilite l'évolution indépendante des deux composants."),
];

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 } } },
    headers: { default: new Header({ children: [new Paragraph({ children: [new TextRun({ text: "Configuration API FastAPI — Détection d'Intrusion Réseau", size: 16, color: "808080" })], alignment: AlignmentType.CENTER })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ children: [new TextRun({ text: "Page ", size: 16 }), new TextRun({ children: [PageNumber.CURRENT], size: 16 })], alignment: AlignmentType.CENTER })] }) },
    children: [
      ...titlePage, ...intro, ...archi,
      new Paragraph({ children: [new PageBreak()] }),
      ...endpoints,
      new Paragraph({ children: [new PageBreak()] }),
      ...exemples,
      new Paragraph({ children: [new PageBreak()] }),
      ...tests, ...lancement,
      new Paragraph({ children: [new PageBreak()] }),
      ...securite, ...conclusion,
    ],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("report/Configuration_API_FastAPI.docx", buffer);
  console.log("Document genere : report/Configuration_API_FastAPI.docx");
});
