const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, PageBreak, Header, Footer, PageNumber,
} = require("docx");

function h1(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 150 } }); }
function h2(text) { return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 250, after: 120 } }); }
function p(text, opts = {}) {
  return new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 160 }, alignment: AlignmentType.JUSTIFIED });
}
function bullet(text) {
  return new Paragraph({ children: [new TextRun({ text })], bullet: { level: 0 }, spacing: { after: 100 } });
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
function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { type: ShadingType.CLEAR, fill: "1F4E78" } : (opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill } : undefined),
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
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((val, i) => cell(val, { width: colWidths[i], center: i !== 0, fill: r._fill })) })),
    ],
  });
}

// ---------------------------------------------------------------------------
// Donnees reelles issues de l'execution de la suite pytest (tests/) le
// 21/08/2026 - voir junit_report.xml et pytest_full_output.txt (logs bruts).
// ---------------------------------------------------------------------------

const titlePage = [
  new Paragraph({ text: "", spacing: { before: 1200 } }),
  new Paragraph({ children: [new TextRun({ text: "UFR MATHEMATIQUES ET INFORMATIQUE", bold: true, size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 400 } }),
  new Paragraph({ children: [new TextRun({ text: "MASTER 1 INFORMATIQUE", bold: true, size: 26 })], alignment: AlignmentType.CENTER, spacing: { after: 100 } }),
  new Paragraph({ children: [new TextRun({ text: "ECUE : Machine Learning", size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 600 } }),
  new Paragraph({
    children: [new TextRun({ text: "Rapport de Tests\nDétection Intelligente et Supervision en Temps Réel\ndes Attaques dans les Réseaux d'Entreprise", bold: true, size: 30, color: "1F4E78" })],
    alignment: AlignmentType.CENTER, spacing: { after: 300 },
  }),
  new Paragraph({ children: [new TextRun({ text: "Document technique complémentaire au rapport de projet et au document de configuration de l'API", italics: true, size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 800 } }),
  new Paragraph({ children: [new TextRun({ text: "Réalisé par : Komoe Edgar Junior", size: 22, bold: true })], alignment: AlignmentType.CENTER, spacing: { after: 100 } }),
  new Paragraph({ children: [new TextRun({ text: "Responsable de l'enseignement : Dr ASSOHOUN E Stanislas", size: 22 })], alignment: AlignmentType.CENTER, spacing: { after: 800 } }),
  new Paragraph({ children: [new TextRun({ text: "Année académique 2025-2026", size: 20 })], alignment: AlignmentType.CENTER, spacing: { before: 1000 } }),
  new Paragraph({ children: [new PageBreak()] }),
];

const intro = [
  h1("1. Objectif et périmètre"),
  p("Ce document présente la stratégie de test appliquée au projet et les résultats obtenus lors de son " +
    "exécution réelle. L'objectif est de démontrer, avec des preuves reproductibles, que les trois " +
    "composants livrés — le pipeline de Machine Learning (Étapes 1 à 4), l'application de supervision " +
    "Streamlit (Étape 5) et l'API REST FastAPI — fonctionnent correctement, individuellement et ensemble, " +
    "et qu'ils ne présentent pas les défauts méthodologiques classiques (fuite de données, incohérence " +
    "entre interfaces, mauvaise gestion des cas d'erreur)."),
  p("Contrairement à un rapport de test purement narratif, l'ensemble des résultats présentés ici provient " +
    "d'une suite de tests automatisés (pytest) réellement écrite et exécutée sur l'environnement du projet, " +
    "complétée par les vérifications fonctionnelles manuelles déjà réalisées (captures d'écran de " +
    "l'application, requêtes curl sur l'API). Aucun résultat n'est estimé ou supposé : chaque chiffre cité " +
    "provient d'une exécution effective, horodatée, dont le journal brut est conservé (junit_report.xml)."),
];

const strategie = [
  h1("2. Stratégie et méthodologie de test"),
  p("La stratégie de test suit une approche pyramidale classique, adaptée à un projet de Machine Learning : " +
    "des tests unitaires rapides sur les artefacts et transformations de données (prétraitement, modèles), " +
    "des tests d'intégration sur l'API REST (cycle requête/réponse complet), et des tests de fumée (smoke " +
    "tests) sur l'interface graphique Streamlit. Un test transversal de cohérence inter-composants complète " +
    "le dispositif : il vérifie que l'API et l'application Streamlit, bien qu'implémentées indépendamment, " +
    "produisent des prédictions strictement identiques sur les mêmes données."),
  dataTable(
    ["Composant testé", "Fichier de test", "Nb. tests", "Outillage"],
    [
      ["Étape 1 — Prétraitement (imputation, IQR, split, standardisation)", "tests/test_preprocessing.py", "17", "pytest"],
      ["Étapes 2 à 4 — Modèles baseline, RFE/élagage, GridSearchCV", "tests/test_models.py", "18", "pytest"],
      ["API REST FastAPI (endpoints, validations, cohérence)", "tests/test_api.py", "13", "pytest + fastapi.testclient"],
      ["Application Streamlit (démarrage, onglets, formulaire)", "tests/test_streamlit_app.py", "7", "pytest + streamlit.testing.v1.AppTest"],
    ],
    [4600, 2700, 1200, 1700]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Chaque test unitaire est indépendant et déterministe : les artefacts (jeux de données prétraités, " +
    "modèles sérialisés .joblib, métriques .csv/.json) sont chargés depuis le dossier outputs/, généré une " +
    "fois par l'exécution du pipeline complet (src/eda.py à src/grid_search.py), puis relus et vérifiés par " +
    "les tests — sans jamais ré-entraîner de modèle pendant la suite de tests elle-même, ce qui garantit une " +
    "exécution rapide (quelques secondes) et reproductible."),
];

const env = [
  h1("3. Environnement d'exécution"),
  dataTable(
    ["Composant", "Version"],
    [
      ["Python", "3.11.15"],
      ["pytest", "9.1.1"],
      ["scikit-learn", "1.8.0"],
      ["pandas", "3.0.2"],
      ["numpy", "2.4.4"],
      ["streamlit", "1.61.1"],
      ["fastapi", "0.141.1"],
      ["pydantic", "2.13.3"],
    ],
    [3800, 3600]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("La suite complète est lancée avec la commande pytest tests/ -v depuis la racine du projet. Un fichier " +
    "tests/conftest.py partagé positionne le répertoire de travail sur la racine du projet avant chaque " +
    "session de test, afin que les chemins relatifs utilisés dans le code de production (outputs/, data/) " +
    "restent valides quel que soit le répertoire depuis lequel pytest est invoqué."),
];

const T = (n, ok) => [n, ok ? "PASS" : "FAIL"];

const resultatsGlobaux = [
  h1("4. Résultats globaux"),
  p("La suite complète (55 tests) a été exécutée le 21/08/2026 à 10:12 UTC. Résultat : 55 tests réussis, " +
    "0 échec, 0 erreur, 0 test ignoré, en 4,77 secondes."),
  dataTable(
    ["Fichier de test", "Tests exécutés", "Réussis", "Échoués", "Durée"],
    [
      ["tests/test_preprocessing.py", "17", "17", "0", "≈ 10,9 s (1ʳᵉ exécution isolée)"],
      ["tests/test_models.py", "18", "18", "0", "≈ 1,6 s"],
      ["tests/test_api.py", "13", "13", "0", "≈ 2,3 s"],
      ["tests/test_streamlit_app.py", "7", "7", "0", "≈ 5,0 s"],
      ["Suite complète (tests/)", "55", "55", "0", "4,77 s"],
    ],
    [3200, 1600, 1300, 1300, 2000]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Remarque sur la durée : la première exécution isolée de test_preprocessing.py (≈ 11 s) inclut le " +
    "chargement initial de pandas/numpy et du fichier CSV brut de 50 000 lignes ; lorsque la suite est " +
    "exécutée en une seule session (pytest tests/), ce coût est amorti et la durée totale tombe à 4,77 " +
    "secondes pour l'ensemble des 55 tests."),
];

const detailPreproc = [
  h1("5. Détail des tests — Étape 1 : Prétraitement (17 tests)"),
  p("Ces tests visent en priorité à démontrer l'absence de fuite de données (data leakage), point " +
    "méthodologique central du projet : le split train/test doit précéder tout calcul statistique " +
    "(médianes d'imputation, bornes IQR, moyenne/écart-type de standardisation), et ces statistiques, " +
    "calculées uniquement sur le train, doivent ensuite être appliquées telles quelles au test."),
  dataTable(
    ["Classe de test", "Vérifie", "Résultat"],
    [
      ["TestJeuDeDonnees (4 tests)", "50 000 lignes, 9 variables + cible, absence de doublons, 4 classes présentes (0 à 3)", "PASS"],
      ["TestImputation (3 tests)", "Aucune valeur manquante résiduelle après imputation (train et test), médianes sauvegardées pour les 9 variables", "PASS"],
      ["TestEcretageIQR (3 tests)", "Bornes IQR sauvegardées et cohérentes (borne basse ≤ borne haute), valeurs train ET test dans les bornes calculées sur le train", "PASS"],
      ["TestSplitStratifie (3 tests)", "Proportion 80/20 respectée, proportions de classes préservées entre train et test (tolérance 1 point), pas de désalignement de dimensions", "PASS"],
      ["TestStandardisation (4 tests)", "Moyenne ≈ 0 et écart-type ≈ 1 sur le train (tolérance 0,05) ; le test N'A PAS une moyenne exactement nulle, preuve que le scaler n'a pas été ajusté dessus", "PASS"],
    ],
    [2600, 4800, 1000]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Le dernier test (test_scaler_ajuste_uniquement_sur_train_no_leakage) mérite une attention particulière : " +
    "il vérifie une propriété négative — que la moyenne des variables standardisées sur le jeu de test N'EST " +
    "PAS parfaitement nulle. Si elle l'était, cela indiquerait que le scaler a été ajusté (fit) sur " +
    "l'ensemble des données avant le split, une erreur de fuite de données fréquente dans les projets de " +
    "Machine Learning. Ce test PASSE, confirmant l'absence de cette fuite."),
];

const detailModels = [
  h1("6. Détail des tests — Étapes 2 à 4 : Modèles (18 tests)"),
  dataTable(
    ["Classe de test", "Vérifie", "Résultat"],
    [
      ["TestEtape2Baseline (4 tests)", "5 algorithmes présents, métriques dans [0,1], modèles baseline chargeables, exactitude > 90% pour tous", "PASS"],
      ["TestEtape3SelectionVariables (5 tests)", "5 variables sélectionnées par RFE, sous-ensemble des 9 variables initiales, métriques réduites valides, perte d'exactitude < 2 points vs modèle complet, arbre élagué strictement moins complexe que l'arbre complet (nœuds et profondeur)", "PASS"],
      ["TestEtape4Optimisation (4 tests)", "Métriques optimisées valides, score de validation croisée présent et cohérent, modèle champion = Arbre_Decision_optimise, GridSearchCV ne dégrade aucun algorithme par rapport à l'étape 3", "PASS"],
      ["TestModeleFinal (5 tests)", "Chargement du modèle final, 5 variables attendues, 4 classes connues, prédiction valide sur un échantillon réel (probabilités sommant à 100%), exactitude recalculée cohérente avec best_model_info.json (écart < 0,5 point)", "PASS"],
    ],
    [2900, 5000, 1000]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Le test test_arbre_elague_moins_complexe_que_arbre_complet compare directement les deux objets " +
    "scikit-learn sérialisés (Arbre_Decision.joblib et Arbre_Decision_elague.joblib) et confirme " +
    "programmatiquement la réduction de complexité déjà documentée dans le rapport de projet (679 nœuds / " +
    "profondeur 30 pour l'arbre complet, contre 9 nœuds / profondeur 3 pour l'arbre élagué)."),
];

const detailApi = [
  h1("7. Détail des tests — API REST FastAPI (13 tests)"),
  p("Ces tests utilisent fastapi.testclient.TestClient, qui exécute l'application FastAPI en mémoire (sans " +
    "socket réseau réel) tout en respectant fidèlement le cycle de vie complet de l'application (y compris " +
    "l'événement de démarrage qui charge le modèle) et la pile de validation Pydantic."),
  dataTable(
    ["Classe de test", "Vérifie", "Résultat"],
    [
      ["TestEndpointsMeta (3 tests)", "GET /, /health et /model_info répondent 200 avec les métadonnées attendues (5 variables, 9 variables totales, 4 classes)", "PASS"],
      ["TestPredictionUnique (4 tests)", "POST /predict : flux valide → 200 avec probabilités sommant à 100% ; champ manquant → 422 ; valeur négative → 422 ; type invalide → 422", "PASS"],
      ["TestPredictionBatch (2 tests)", "POST /predict_batch : liste vide → 400 ; plusieurs flux → 200 avec résumé cohérent", "PASS"],
      ["TestPredictionCSV (3 tests)", "POST /predict_csv : fichier de démonstration (50 flux) → 16 menaces détectées (32%) ; fichier non-CSV → 400 ; fichier vide → 400", "PASS"],
      ["TestCoherenceApiPipeline (1 test)", "Les prédictions renvoyées par l'API sur les 50 flux de démonstration sont IDENTIQUES, ligne par ligne, à celles obtenues en appliquant directement le pipeline de prétraitement et le modèle en dehors de l'API", "PASS"],
    ],
    [2900, 5100, 900]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Le test de cohérence (TestCoherenceApiPipeline) est le plus significatif du point de vue architecture : " +
    "il reproduit indépendamment, dans le code de test, les quatre étapes du pipeline (imputation, écrêtage " +
    "IQR, standardisation, sélection des 5 variables) à partir des artefacts .joblib, puis compare les " +
    "prédictions obtenues à celles renvoyées par l'API. L'égalité stricte confirme qu'il n'existe aucune " +
    "divergence d'implémentation entre api/model_service.py et le pipeline documenté — un risque réel " +
    "lorsque deux interfaces (Streamlit et API) sont censées partager la même logique métier."),
  p("Note technique : l'exécution de la suite produit deux avertissements (DeprecationWarning) signalant " +
    "que le décorateur @app.on_event(\"startup\") est déprécié par FastAPI au profit des « lifespan event " +
    "handlers ». Il ne s'agit pas d'un échec de test ni d'un dysfonctionnement — le code fonctionne " +
    "correctement avec la version actuelle de FastAPI (0.141.1) — mais d'une piste d'amélioration mineure " +
    "identifiée à cette occasion, à corriger avant une éventuelle montée de version majeure de FastAPI."),
];

const detailStreamlit = [
  h1("8. Détail des tests — Application Streamlit (7 tests)"),
  p("Ces tests utilisent streamlit.testing.v1.AppTest, qui exécute le script app/app.py dans un " +
    "environnement Streamlit simulé (sans navigateur ni serveur), et inspecte l'arbre des éléments produits " +
    "(titres, métriques, onglets, champs de formulaire) comme le ferait un utilisateur."),
  dataTable(
    ["Classe de test", "Vérifie", "Résultat"],
    [
      ["TestChargementApplication (4 tests)", "L'application démarre sans exception, le titre est présent, les 4 onglets existent, le tableau de bord affiche au moins 4 métriques dont des pourcentages", "PASS"],
      ["TestFormulairePredictionUnique (3 tests)", "Le formulaire de prédiction unique contient bien les 9 champs numériques attendus ; sa soumission avec les valeurs par défaut (médianes) s'exécute sans exception ; un résultat de prédiction est effectivement affiché", "PASS"],
    ],
    [3300, 4700, 900]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Limite connue et documentée : à la date de rédaction, AppTest ne permet pas de simuler l'interaction " +
    "avec un composant st.file_uploader (limitation de l'outil de test officiel de Streamlit lui-même, non " +
    "du projet). L'onglet « Import CSV » n'est donc pas couvert par un test AppTest dédié. Cette lacune est " +
    "comblée de deux façons complémentaires : (1) des captures d'écran Playwright, prises lors d'une session " +
    "réelle du navigateur, démontrent le fonctionnement effectif de l'import CSV, de l'aperçu des données et " +
    "de l'affichage des résultats (voir demo_screenshots/2a_import_csv_apercu.png et " +
    "2b_import_csv_resultats.png) ; (2) le test test_predict_csv_fichier_demo_coherent_avec_streamlit de " +
    "tests/test_api.py exécute exactement la même logique de prétraitement et de prédiction sur le même " +
    "fichier via l'API, produisant le résultat identique (16 menaces sur 50 flux) déjà observé " +
    "manuellement dans Streamlit — apportant une preuve fonctionnelle indirecte mais rigoureuse de la " +
    "correction de cet onglet."),
];

const anomalie = [
  h1("9. Anomalie détectée et corrigée pendant la phase de test et de relecture"),
  p("La démarche de test et de relecture croisée du projet a permis d'identifier une erreur de " +
    "transcription dans les documents déjà livrés (rapport de projet et présentation PowerPoint), " +
    "indépendamment de la suite pytest : la valeur de l'AUC macro du modèle après élagage de l'arbre de " +
    "décision (Étape 3) y était indiquée à tort comme passant de 98,22 % à 98,89 %, alors que la valeur " +
    "réelle, extraite directement du fichier outputs/comparison_step3.csv (colonne AUC_reduit, ligne " +
    "Arbre_Decision), est 99,89 %."),
  dataTable(
    ["Source", "Valeur indiquée avant correction", "Valeur réelle (comparison_step3.csv)"],
    [["Rapport de projet + PowerPoint", "98,22 % → 98,89 %", "98,22 % → 99,89 %"]],
    [3400, 3000, 2600]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Cette anomalie a été corrigée dans les deux documents concernés (report/build_report.js et " +
    "report/build_pptx.js), qui ont été régénérés puis revérifiés (inspection directe du XML interne des " +
    "fichiers .docx et .pptx pour confirmer la présence de la valeur correcte et l'absence de l'ancienne " +
    "valeur). Ce cas est documenté ici à titre de traçabilité et illustre l'utilité d'une phase de test et " +
    "de relecture dédiée, même sur un projet dont le code source produit des résultats corrects : l'erreur " +
    "se trouvait uniquement dans la transcription manuelle des chiffres vers les documents de restitution, " +
    "pas dans le pipeline de calcul lui-même."),
];

const couverture = [
  h1("10. Synthèse de couverture et limites des tests"),
  p("Le tableau suivant récapitule ce que la suite de tests couvre effectivement, et ce qui reste hors de " +
    "son périmètre (limites assumées, avec la justification du choix)."),
  dataTable(
    ["Élément", "Couvert par un test automatisé ?", "Détail"],
    [
      ["Absence de fuite de données (split, imputation, standardisation)", "Oui", "tests/test_preprocessing.py"],
      ["Cohérence et plausibilité des métriques (5 algorithmes, 3 étapes)", "Oui", "tests/test_models.py"],
      ["Réduction de complexité de l'arbre par élagage", "Oui", "tests/test_models.py"],
      ["Non-régression de GridSearchCV vs étape précédente", "Oui", "tests/test_models.py"],
      ["Chargement et prédiction du modèle final", "Oui", "tests/test_models.py"],
      ["Endpoints API (succès et cas d'erreur 400/422)", "Oui", "tests/test_api.py"],
      ["Cohérence stricte API ↔ pipeline direct", "Oui", "tests/test_api.py"],
      ["Démarrage et structure de l'application Streamlit", "Oui", "tests/test_streamlit_app.py"],
      ["Soumission du formulaire de prédiction unique", "Oui", "tests/test_streamlit_app.py"],
      ["Interaction avec le composant d'upload CSV (Streamlit)", "Non (limite d'AppTest)", "Couvert indirectement : captures Playwright + test API équivalent"],
      ["Performance / charge (temps de réponse sous forte volumétrie)", "Non", "Hors périmètre du projet académique ; piste d'amélioration"],
      ["Sécurité (authentification, CORS restreint, injection)", "Non", "Documenté comme limite dans Configuration_API_FastAPI.docx, section 7"],
      ["Déséquilibre des classes (impact du sous-échantillonnage SVM)", "Partiel", "Vérifié via métriques macro (test_exactitude_superieure_au_hasard) ; SMOTE non implémenté (limite documentée)"],
    ],
    [3800, 2200, 3000]
  ),
];

const conclusion = [
  h1("11. Conclusion"),
  p("La suite de tests automatisés, comptant 55 tests répartis sur les quatre composants du projet, " +
    "s'exécute intégralement avec succès (55 réussis, 0 échec) en moins de 5 secondes. Elle démontre de " +
    "façon reproductible l'absence de fuite de données dans le pipeline de prétraitement, la validité et la " +
    "cohérence progressive des métriques à travers les étapes de sélection de variables et d'optimisation, " +
    "le bon fonctionnement de l'API REST y compris sur ses cas d'erreur, la cohérence stricte entre l'API et " +
    "l'application Streamlit, et le démarrage correct de l'interface graphique."),
  p("Cette démarche de test a également permis de détecter et corriger une erreur réelle de transcription " +
    "dans les documents de restitution (section 9), illustrant la valeur d'une phase de test et de relecture " +
    "systématique, y compris sur un projet dont l'implémentation technique est correcte. Les limites " +
    "assumées de la suite de tests (absence de test automatisé de charge, de sécurité, et de l'upload CSV " +
    "via AppTest) sont explicitement documentées en section 10 plutôt que passées sous silence, conformément " +
    "à une démarche de qualité rigoureuse."),
];

const doc = new Document({
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 } } },
    headers: { default: new Header({ children: [new Paragraph({ children: [new TextRun({ text: "Rapport de Tests — Détection Intelligente des Attaques Réseau", size: 16, color: "808080" })], alignment: AlignmentType.CENTER })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ children: [new TextRun({ text: "Page ", size: 16 }), new TextRun({ children: [PageNumber.CURRENT], size: 16 })], alignment: AlignmentType.CENTER })] }) },
    children: [
      ...titlePage, ...intro, ...strategie,
      new Paragraph({ children: [new PageBreak()] }),
      ...env, ...resultatsGlobaux,
      new Paragraph({ children: [new PageBreak()] }),
      ...detailPreproc,
      new Paragraph({ children: [new PageBreak()] }),
      ...detailModels,
      new Paragraph({ children: [new PageBreak()] }),
      ...detailApi,
      new Paragraph({ children: [new PageBreak()] }),
      ...detailStreamlit,
      new Paragraph({ children: [new PageBreak()] }),
      ...anomalie, ...couverture,
      new Paragraph({ children: [new PageBreak()] }),
      ...conclusion,
    ],
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("report/Rapport_de_Tests.docx", buffer);
  console.log("Document genere : report/Rapport_de_Tests.docx");
});
