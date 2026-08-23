const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, ImageRun, BorderStyle, PageBreak,
  Header, Footer, PageNumber, LevelFormat,
} = require("docx");

const OUT = "outputs";
const FIG = path.join(OUT, "figures");

const { imageSize } = require("image-size");

function img(relPath, width) {
  const full = path.join(FIG, relPath);
  const buf = fs.readFileSync(full);
  let dims;
  try {
    dims = imageSize(buf);
  } catch (e) {
    dims = { width: 800, height: 600 };
  }
  const ratio = dims.height / dims.width;
  return new ImageRun({
    data: buf,
    transformation: { width: width, height: Math.round(width * ratio) },
    type: "png",
  });
}

function h1(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 150 } });
}
function h2(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_2, spacing: { before: 250, after: 120 } });
}
function h3(text) {
  return new Paragraph({ text, heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 } });
}
function p(text, opts = {}) {
  return new Paragraph({
    children: [new TextRun({ text, ...opts })],
    spacing: { after: 160 },
    alignment: AlignmentType.JUSTIFIED,
  });
}
function pRuns(runs, opts = {}) {
  return new Paragraph({ children: runs, spacing: { after: 160 }, alignment: AlignmentType.JUSTIFIED, ...opts });
}
function bold(text) {
  return new TextRun({ text, bold: true });
}
function caption(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, size: 20 })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 240 },
  });
}
function centerImage(relPath, width, captionText) {
  const children = [
    new Paragraph({ children: [img(relPath, width)], alignment: AlignmentType.CENTER, spacing: { after: 60 } }),
  ];
  if (captionText) children.push(caption(captionText));
  return children;
}

function cell(text, opts = {}) {
  return new TableCell({
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { type: ShadingType.CLEAR, fill: "1F4E78" } : undefined,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text), bold: !!opts.header, color: opts.header ? "FFFFFF" : "000000", size: 18 })],
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
      new TableRow({ cantSplit: true, children: headers.map((hd, i) => cell(hd, { header: true, width: colWidths[i] })) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((val, i) => cell(val, { width: colWidths[i], center: true })) })),
    ],
  });
}

// ---------------------------------------------------------------- Data
const baseline = parseCsv(fs.readFileSync(path.join(OUT, "baseline_results.csv"), "utf8"));
const reduced = parseCsv(fs.readFileSync(path.join(OUT, "reduced_results.csv"), "utf8"));
const optimized = parseCsv(fs.readFileSync(path.join(OUT, "optimized_results.csv"), "utf8"));
const comparison = parseCsv(fs.readFileSync(path.join(OUT, "comparison_step3.csv"), "utf8"));
const gridParams = JSON.parse(fs.readFileSync(path.join(OUT, "grid_search_best_params.json"), "utf8"));
const bestInfo = JSON.parse(fs.readFileSync(path.join(OUT, "best_model_info.json"), "utf8"));
const preSummary = JSON.parse(fs.readFileSync(path.join(OUT, "preprocessing_summary.json"), "utf8"));
const eda = JSON.parse(fs.readFileSync(path.join(OUT, "eda_report.json"), "utf8"));
const selFeat = JSON.parse(fs.readFileSync(path.join(OUT, "selected_features.json"), "utf8"));

function parseCsv(text) {
  const lines = text.trim().split("\n");
  const headers = lines[0].split(",");
  return lines.slice(1).map((l) => {
    const vals = l.split(",");
    const obj = {};
    headers.forEach((h, i) => (obj[h] = vals[i]));
    return obj;
  });
}
function pct(x) { return (parseFloat(x) * 100).toFixed(2) + " %"; }

const classLabels = {
  "0": "Normal / Legitime", "1": "Scan de Ports / Reconnaissance",
  "2": "Attaque DDoS / Volumetrique", "3": "Infiltration / Brute-Force / Exfiltration",
};

// ---------------------------------------------------------------- Build sections
const titlePage = [
  new Paragraph({ text: "", spacing: { before: 1200 } }),
  new Paragraph({
    children: [new TextRun({ text: "UFR MATHEMATIQUES ET INFORMATIQUE", bold: true, size: 22 })],
    alignment: AlignmentType.CENTER, spacing: { after: 400 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "MASTER 1 INFORMATIQUE", bold: true, size: 26 })],
    alignment: AlignmentType.CENTER, spacing: { after: 100 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "ECUE : Machine Learning", size: 22 })],
    alignment: AlignmentType.CENTER, spacing: { after: 600 },
  }),
  new Paragraph({
    children: [new TextRun({
      text: "Détection Intelligente et Supervision en Temps Réel des Attaques dans les Réseaux d'Entreprise",
      bold: true, size: 32, color: "1F4E78",
    })],
    alignment: AlignmentType.CENTER, spacing: { after: 300 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Rapport de Projet", italics: true, size: 24 })],
    alignment: AlignmentType.CENTER, spacing: { after: 800 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Réalisé par : Komoe Edgar Junior", size: 22, bold: true })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 100 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Responsable de l'enseignement : Dr ASSOHOUN E Stanislas", size: 22 })],
    alignment: AlignmentType.CENTER, spacing: { after: 100 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Public cible : Étudiants en Master (Cybersécurité, Informatique, Science des Données)", size: 20 })],
    alignment: AlignmentType.CENTER, spacing: { after: 800 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Année académique 2025-2026", size: 20 })],
    alignment: AlignmentType.CENTER, spacing: { before: 1000 },
  }),
  new Paragraph({ children: [new PageBreak()] }),
];

const sommaire = [
  h1("Sommaire"),
  p("1. Introduction et contexte"),
  p("2. Description et exploration du jeu de données"),
  p("3. Problématique et questions de recherche"),
  p("4. Méthodologie"),
  p("5. Étape 1 — Prétraitement et nettoyage des données"),
  p("6. Étape 2 — Modélisation de base (5 algorithmes)"),
  p("7. Étape 3 — Sélection de variables et élagage"),
  p("8. Étape 4 — Optimisation par GridSearchCV"),
  p("9. Étape 5 — Application de supervision (GUI)"),
  p("10. Réponses aux questions de recherche"),
  p("11. Limites et perspectives"),
  p("12. Conclusion"),
  new Paragraph({ children: [new PageBreak()] }),
];

const intro = [
  h1("1. Introduction et contexte"),
  p(
    "Dans les architectures réseaux modernes, la multiplication des vecteurs d'attaque (attaques par déni de service " +
    "distribué — DDoS, scans furtifs, exfiltration de données, rebonds d'intrusion) impose l'automatisation de la " +
    "surveillance à partir des flux de trafic collectés par les sondes d'un Centre Opérationnel de Sécurité (SOC). " +
    "Ce projet propose de concevoir, d'entraîner et de déployer un pipeline complet d'apprentissage automatique " +
    "(Machine Learning) capable de classer automatiquement chaque flux réseau observé selon quatre catégories de " +
    "menace, puis d'intégrer le modèle retenu au sein d'une interface graphique interactive destinée aux " +
    "administrateurs de sécurité."
  ),
  p(
    "Le présent rapport documente l'ensemble de la démarche suivie, de l'exploration du jeu de données brut jusqu'au " +
    "déploiement d'une application de supervision fonctionnelle, en passant par le prétraitement des données, la " +
    "comparaison de cinq algorithmes de classification, la sélection de variables, l'élagage de l'arbre de décision " +
    "et l'optimisation des hyperparamètres par validation croisée."
  ),
];

const dataDesc = [
  h1("2. Description et exploration du jeu de données"),
  p(
    `Le jeu de données Enterprise_Network_Traffic_BigData.csv contient ${eda.shape[0].toLocaleString("fr-FR")} ` +
    `enregistrements (flux réseau), sans doublon, décrits par 9 variables explicatives quantitatives et une ` +
    `variable cible catégorielle Statut_Menace codée sur 4 classes.`
  ),
  h2("2.1 Variables explicatives"),
  p("Les variables se répartissent en deux groupes fonctionnels :"),
  p("Variables temporelles et statistiques de session : Duree_Connexion (durée de la session en millisecondes), " +
    "Octets_Source_Vers_Dest et Octets_Dest_Vers_Source (volumes de données échangés dans chaque sens), " +
    "Taux_Paquets_Secondes (fréquence d'émission des paquets) et Fenetre_TCP_Moyenne (taille moyenne de la fenêtre " +
    "TCP annoncée)."),
  p("Variables comportementales et indicateurs de menace : Ports_Dest_Distincts (nombre de ports uniques ciblés en " +
    "moins d'une seconde, indicateur clé de balayage), Connexions_Simultanees (connexions parallèles ouvertes sur " +
    "l'hôte cible), Taux_Erreur_CheckSum (pourcentage de paquets corrompus) et Frequence_SYN_Flags (proportion de " +
    "drapeaux SYN activés, révélatrice d'attaques SYN Flood)."),
  h2("2.2 Variable cible et déséquilibre des classes"),
  p("La variable Statut_Menace comporte quatre modalités. La distribution observée dans le jeu de données complet " +
    "est fortement déséquilibrée, ce qui est représentatif d'un contexte SOC réel où le trafic légitime domine très " +
    "largement le trafic malveillant :"),
  dataTable(
    ["Classe", "Libellé", "Effectif", "Proportion"],
    Object.entries(eda.class_distribution).map(([k, v]) => [
      k, classLabels[k], v, eda.class_distribution_pct[k] + " %",
    ]),
    [1200, 4200, 1800, 1800]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Ce déséquilibre justifie l'usage systématique d'une stratification (préservation des proportions de classes) " +
    "lors du découpage entraînement/test et de la validation croisée, ainsi que l'emploi de métriques macro-moyennées " +
    "(Précision, Rappel, F1-score) et de l'aire sous la courbe ROC (AUC), moins sensibles au déséquilibre que la " +
    "simple exactitude globale."),
  h2("2.3 Qualité des données"),
  p(`L'exploration initiale révèle un nombre limité de valeurs manquantes, concentrées sur deux variables : ` +
    Object.entries(eda.missing_pct).filter(([k, v]) => v > 0).map(([k, v]) => `${k} (${v} %)`).join(" et ") +
    ". Aucun doublon n'a été détecté. Ces valeurs manquantes sont traitées à l'Étape 1 par imputation médiane."),
];

const problematique = [
  h1("3. Problématique et questions de recherche"),
  p("Problématique : Comment concevoir un pipeline de Machine Learning robuste et explicable capable d'analyser un " +
    "grand volume de flux réseau hétérogènes, d'isoler les variables les plus discriminantes, d'optimiser les " +
    "performances de classification multiclasse, et d'être intégré au sein d'une interface graphique interactive " +
    "pour les administrateurs de sécurité ?", { italics: true }),
  p("Cette problématique se décline en quatre questions de recherche opérationnelles, auxquelles la section 10 du " +
    "présent rapport apporte une réponse argumentée à partir des résultats expérimentaux obtenus :"),
  p("1. Quel est l'impact réel des étapes de prétraitement (imputation des valeurs manquantes et écrêtage des " +
    "valeurs aberrantes par la méthode IQR) sur la stabilité des frontières de décision des algorithmes ?"),
  p("2. Comment la sélection de variables (RFE) et l'élagage par coût-complexité (cp) pour l'arbre de décision " +
    "améliorent-ils la lisibilité des règles de sécurité par rapport au modèle complet ?"),
  p("3. Quel est l'apport quantitatif de l'optimisation des hyperparamètres par recherche sur grille (GridSearchCV, " +
    "validation croisée à 5 plis) sur les scores de généralisation ?"),
  p("4. Comment structurer une application logicielle dotée d'une interface graphique permettant de charger des " +
    "logs en direct et d'assister l'opérateur dans la prise de décision immédiate face à une alerte ?"),
];

const methodo = [
  h1("4. Méthodologie"),
  p("Le pipeline expérimental s'articule autour de cinq étapes successives, chacune codée en Python (bibliothèques " +
    "pandas, scikit-learn, matplotlib et Streamlit) et reproductible via les scripts fournis en annexe du projet " +
    "(dossier src/) :"),
  p("Étape 1 : prétraitement et nettoyage (imputation, traitement des outliers, découpage stratifié, standardisation)."),
  p("Étape 2 : modélisation de référence (baseline) avec cinq algorithmes entraînés sur l'ensemble des 9 variables."),
  p("Étape 3 : sélection de variables par élimination récursive (RFE) et élagage par coût-complexité de l'arbre de décision."),
  p("Étape 4 : optimisation des hyperparamètres par GridSearchCV avec validation croisée stratifiée à 5 plis."),
  p("Étape 5 : intégration du modèle optimal dans une application de supervision interactive développée avec Streamlit."),
  p("Afin de garantir la validité méthodologique des résultats et d'éviter toute fuite d'information (data leakage), " +
    "l'ensemble des statistiques de nettoyage (médianes d'imputation, bornes IQR, moyenne et écart-type de " +
    "standardisation) est calculé exclusivement sur l'ensemble d'entraînement (80 %), puis appliqué tel quel à " +
    "l'ensemble de test (20 %), qui reste ainsi totalement indépendant du processus d'apprentissage."),
];

const etape1 = [
  h1("5. Étape 1 — Prétraitement et nettoyage des données"),
  p(`Après un découpage stratifié en ${preSummary.n_train.toLocaleString("fr-FR")} observations d'entraînement et ` +
    `${preSummary.n_test.toLocaleString("fr-FR")} observations de test (ratio 80/20, proportions de classes ` +
    "préservées dans les deux ensembles), les traitements suivants ont été appliqués :"),
  h2("5.1 Imputation des valeurs manquantes"),
  p(`${preSummary.missing_values_imputed_train} valeurs manquantes ont été imputées dans l'ensemble d'entraînement ` +
    `et ${preSummary.missing_values_imputed_test} dans l'ensemble de test, par la médiane statistique de chaque ` +
    "variable calculée sur l'ensemble d'entraînement. La médiane a été préférée à la moyenne car elle est robuste " +
    "à la présence de valeurs extrêmes, particulièrement fréquentes dans les métriques de trafic réseau (volumes " +
    "d'octets, taux de paquets)."),
  h2("5.2 Traitement des valeurs aberrantes par la méthode IQR"),
  p("Pour chaque variable, les bornes d'écrêtage sont définies par [Q1 − 1,5×IQR ; Q3 + 1,5×IQR], où Q1 et Q3 sont " +
    "les premier et troisième quartiles calculés sur l'ensemble d'entraînement et IQR = Q3 − Q1. Toute valeur en " +
    "dehors de cet intervalle est ramenée (écrêtée) à la borne la plus proche plutôt que supprimée, ce qui préserve " +
    "la taille de l'échantillon. Les figures ci-dessous illustrent l'effet de cet écrêtage sur la distribution des " +
    "variables de l'ensemble d'entraînement."),
  ...centerImage("boxplots_avant_iqr.png", 600, "Figure 1 — Distributions des variables avant écrêtage IQR"),
  ...centerImage("boxplots_apres_iqr.png", 600, "Figure 2 — Distributions des variables après écrêtage IQR"),
  h2("5.3 Découpage et standardisation"),
  p("Le découpage entraînement/test (80 % / 20 %) a été réalisé de façon stratifiée sur la variable cible afin de " +
    "préserver le déséquilibre des classes dans les deux sous-ensembles. Une standardisation (centrage-réduction, " +
    "StandardScaler) a ensuite été appliquée, ajustée sur l'ensemble d'entraînement uniquement puis appliquée aux " +
    "deux ensembles — étape indispensable pour les algorithmes sensibles à l'échelle des variables (Régression " +
    "Logistique, KNN, SVM)."),
];

// ---------------------------------------------------------------- Etape 2
function resultTable(rows) {
  return dataTable(
    ["Modèle", "Exactitude", "Précision", "Rappel", "F1-score", "AUC"],
    rows.map((r) => [
      r["Modele"].replace(/_/g, " "),
      pct(r["Exactitude"]), pct(r["Precision (macro)"]), pct(r["Rappel (macro)"]),
      pct(r["F1-score (macro)"]), pct(r["AUC (macro)"]),
    ]),
    [2400, 1200, 1200, 1200, 1200, 1200]
  );
}

const etape2 = [
  h1("6. Étape 2 — Modélisation de base (Baseline)"),
  p("Cinq algorithmes de classification multiclasse ont été entraînés sur l'ensemble complet des 9 variables " +
    "standardisées : Régression Logistique Multinomiale, K plus proches voisins (KNN, k=5), Naïve Bayes Gaussien, " +
    "Machine à Vecteurs de Support (SVM, noyau RBF) et Arbre de Classification (paramètres par défaut, sans élagage). " +
    "Pour le SVM, dont la complexité d'entraînement croît de façon quasi cubique avec le nombre d'observations, un " +
    "sous-échantillon stratifié de 8 000 flux a été utilisé pour l'apprentissage — l'évaluation restant réalisée sur " +
    "l'intégralité des 10 000 flux de l'ensemble de test, conformément aux bonnes pratiques en contexte Big Data."),
  resultTable(baseline),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Tous les modèles atteignent des performances élevées (exactitude ≥ 98 %), la Régression Logistique et le SVM " +
    "arrivant en tête sur l'exactitude et l'AUC, tandis que l'Arbre de Décision, non élagué, affiche l'AUC macro la " +
    "plus faible (98,22 %) : ce comportement, révélateur d'un léger surapprentissage sur certaines classes " +
    "minoritaires, motive l'élagage réalisé à l'Étape 3."),
  ...centerImage("baseline/cm_Regression_Logistique.png", 380, "Figure 3 — Matrice de confusion, Régression Logistique (modèle complet)"),
  ...centerImage("baseline/roc_Regression_Logistique.png", 380, "Figure 4 — Courbes ROC One-vs-Rest, Régression Logistique (modèle complet)"),
  ...centerImage("baseline/cm_Arbre_Decision.png", 380, "Figure 5 — Matrice de confusion, Arbre de Décision non élagué"),
];

// ---------------------------------------------------------------- Etape 3
const etape3 = [
  h1("7. Étape 3 — Sélection de variables et élagage"),
  h2("7.1 Sélection de variables par élimination récursive (RFE)"),
  p(`Une élimination récursive des variables (Recursive Feature Elimination, estimateur de base : Régression ` +
    `Logistique) a été appliquée afin de réduire l'espace des variables de 9 à ${selFeat.n_selected} dimensions. ` +
    "Les variables retenues sont, par ordre de sélection : " + selFeat.selected_features.join(", ") + "."),
  p("Ce sous-ensemble concentre les indicateurs les plus directement liés aux signatures d'attaque décrites dans le " +
    "contexte du projet : volumétrie de trafic sortant (Octets_Source_Vers_Dest, révélateur d'exfiltration ou de " +
    "flood), fréquence des paquets, diversité des ports ciblés (signature de scan), taux d'erreurs de somme de " +
    "contrôle et proportion de drapeaux SYN (signature de SYN Flood). Les variables écartées (Duree_Connexion, " +
    "Connexions_Simultanees, Octets_Dest_Vers_Source, Fenetre_TCP_Moyenne) apparaissent en revanche moins " +
    "discriminantes une fois l'information des cinq premières variables prise en compte."),
  h2("7.2 Élagage par coût-complexité de l'Arbre de Décision"),
  p("Pour l'Arbre de Décision, la sélection de variables a été remplacée par un élagage par coût-complexité " +
    "(paramètre ccp_alpha), conformément aux consignes du projet. Le chemin d'élagage (cost_complexity_pruning_path) " +
    "a été calculé sur l'ensemble d'entraînement, puis chaque valeur candidate de ccp_alpha a été évaluée par " +
    "validation croisée stratifiée à 5 plis afin de retenir celle qui maximise l'exactitude moyenne."),
  ...centerImage("ccp_alpha_curve.png", 550, "Figure 6 — Exactitude moyenne (CV 5 plis) en fonction de ccp_alpha"),
  p("La valeur optimale retenue (ccp_alpha ≈ 0,0060) réduit l'arbre de 679 nœuds et 30 niveaux de profondeur " +
    "(modèle complet, Étape 2) à seulement 9 nœuds et 3 niveaux de profondeur, tout en améliorant la capacité de " +
    "généralisation du modèle, comme le résume le tableau suivant :"),
];

const etape3b = [
  h2("7.3 Comparaison avec le modèle complet"),
  p("Le tableau ci-dessous compare, pour chaque algorithme, les performances du modèle complet (Étape 2, 9 " +
    "variables) et du modèle réduit / élagué (Étape 3) :"),
  dataTable(
    ["Modèle", "Exact. complet", "Exact. réduit", "AUC complet", "AUC réduit"],
    comparison.map((r) => [
      r["Modele"].replace(/_/g, " "), pct(r["Exactitude_complet"]), pct(r["Exactitude_reduit"]),
      pct(r["AUC_complet"]), pct(r["AUC_reduit"]),
    ]),
    [2600, 1650, 1650, 1650, 1650]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("La réduction du nombre de variables (de 9 à 5) ne dégrade les performances d'aucun modèle — elle les améliore " +
    "même systématiquement pour le KNN (+0,69 point d'exactitude) et surtout pour l'Arbre de Décision, dont l'AUC " +
    "macro progresse de 98,22 % à 99,89 % après élagage. L'élagage réduit également très fortement la complexité " +
    "structurelle de l'arbre, le rendant lisible par un opérateur humain : le nombre de nœuds passe de 679 à 9 et " +
    "la profondeur de 30 à 3 niveaux, tout en conservant une exactitude de 98,71 % sur le jeu de test. Cette " +
    "simplification répond directement à l'exigence d'explicabilité formulée dans la problématique du projet."),
  ...centerImage("reduced/cm_Arbre_Decision_elague.png", 380, "Figure 7 — Matrice de confusion, Arbre de Décision élagué (5 variables, profondeur 3)"),
];

// ---------------------------------------------------------------- Etape 4
const gridRows = Object.entries(gridParams).map(([name, v]) => [
  name.replace(/_/g, " "),
  JSON.stringify(v.best_params).replace(/[{}"]/g, "").replace(/,/g, ", "),
  pct(v.cv_score),
]);

const etape4 = [
  h1("8. Étape 4 — Optimisation par GridSearchCV"),
  p("Chaque algorithme a fait l'objet d'une recherche sur grille (GridSearchCV) couplée à une validation croisée " +
    "stratifiée à 5 plis, menée sur l'espace de variables réduit issu de l'Étape 3 (5 variables). Les grilles " +
    "explorées couvrent les hyperparamètres les plus influents de chaque algorithme : la régularisation C pour la " +
    "Régression Logistique ; le nombre de voisins, la pondération et la métrique de distance pour le KNN ; le " +
    "paramètre de lissage var_smoothing pour Naïve Bayes ; le couple (C, gamma) du noyau RBF pour le SVM ; ainsi " +
    "que la profondeur maximale, le nombre minimal d'observations par feuille et ccp_alpha pour l'Arbre de Décision."),
  dataTable(
    ["Modèle", "Meilleurs hyperparamètres", "Score CV (exactitude)"],
    gridRows,
    [2200, 4600, 1900]
  ),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  p("Résultats sur l'ensemble de test après ré-entraînement avec les hyperparamètres optimaux :"),
  resultTable(optimized),
  new Paragraph({ text: "", spacing: { after: 200 } }),
  pRuns([
    new TextRun("À l'issue de cette optimisation, le modèle "),
    bold(bestInfo.name.replace(/_/g, " ")),
    new TextRun(` est retenu comme modèle optimal pour l'intégration en production, avec une exactitude de test de ` +
      `${(bestInfo.accuracy * 100).toFixed(2)} %, un F1-score macro de ${(bestInfo.f1_macro * 100).toFixed(2)} % et ` +
      `une AUC macro de ${(bestInfo.auc_macro * 100).toFixed(2)} %. Ce choix combine la meilleure exactitude globale, ` +
      "une AUC quasi parfaite et une structure interprétable (profondeur limitée), ce qui en fait un candidat " +
      "particulièrement adapté à un usage opérationnel par des analystes SOC."),
  ]),
  ...centerImage("optimized/cm_Arbre_Decision_optimise.png", 380, "Figure 8 — Matrice de confusion, modèle optimal après GridSearchCV"),
  ...centerImage("optimized/roc_Arbre_Decision_optimise.png", 380, "Figure 9 — Courbes ROC, modèle optimal après GridSearchCV"),
];

// ---------------------------------------------------------------- Etape 5
const etape5 = [
  h1("9. Étape 5 — Application de supervision (GUI)"),
  p("Le modèle optimal a été intégré au sein d'une application Streamlit (app/app.py) organisée en quatre onglets " +
    "reproduisant les fonctionnalités attendues d'un poste de supervision SOC :"),
  h2("9.1 Tableau de bord"),
  p("Affiche les indicateurs de performance du modèle en production (exactitude, F1-score, AUC), la comparaison " +
    "des cinq algorithmes après optimisation, la courbe ROC et la matrice de confusion du modèle retenu, ainsi que " +
    "le tableau comparatif de l'impact de la sélection de variables (Étape 3)."),
  h2("9.2 Import CSV de logs réseau"),
  p("Permet de charger un fichier CSV contenant des flux réseau bruts (les 9 variables du dataset). Le pipeline de " +
    "prétraitement complet (imputation, écrêtage IQR, standardisation, sélection des 5 variables retenues) est " +
    "appliqué automatiquement avant la prédiction. Le résultat affiche le nombre de flux analysés, la répartition " +
    "par catégorie de menace, et permet le téléchargement des résultats annotés."),
  h2("9.3 Prédiction unique"),
  p("Formulaire de saisie manuelle des 9 caractéristiques d'un flux réseau, avec prédiction instantanée de la " +
    "catégorie de menace et affichage du niveau de confiance (probabilité maximale du modèle, en %), ainsi que la " +
    "répartition des probabilités sur les quatre classes."),
  h2("9.4 Journal d'alertes dynamique"),
  p("Historique horodaté de toutes les menaces détectées (catégories 1, 2 et 3), qu'elles proviennent d'un import " +
    "CSV ou d'une saisie manuelle, consultable, exportable au format CSV et réinitialisable par l'opérateur."),
  p("L'application a été testée avec succès en local (serveur Streamlit démarré et interrogé, pipeline de " +
    "prétraitement et de prédiction validé sur un échantillon extrait du dataset original)."),
];

// ---------------------------------------------------------------- Reponses
const reponses = [
  h1("10. Réponses aux questions de recherche"),
  h2("10.1 Impact du prétraitement sur la stabilité des frontières de décision"),
  p("L'imputation médiane et l'écrêtage IQR concernent une proportion modérée mais non négligeable des observations " +
    "(entre 582 et 6 672 valeurs écrêtées selon la variable, sur 40 000 observations d'entraînement, cf. Figures 1 " +
    "et 2). Ce traitement stabilise les frontières de décision des algorithmes sensibles aux valeurs extrêmes — en " +
    "particulier le SVM à noyau RBF et le KNN, dont les métriques de distance sont directement affectées par des " +
    "valeurs aberrantes non traitées — en resserrant la dispersion des variables autour de plages réalistes. Il " +
    "convient toutefois de noter une limite méthodologique importante : certaines valeurs extrêmes (par exemple un " +
    "nombre très élevé de Ports_Dest_Distincts ou une Frequence_SYN_Flags proche de 1) constituent par nature le " +
    "signal discriminant des attaques de type scan ou SYN Flood. L'écrêtage IQR, appliqué uniformément sans " +
    "distinction entre bruit de mesure et signal d'attaque, doit donc être manié avec prudence dans un contexte de " +
    "détection d'intrusion : les résultats obtenus (performances stables voire légèrement améliorées après " +
    "écrêtage) suggèrent ici que l'effet stabilisateur l'emporte sur la perte d'information, mais ce compromis " +
    "mériterait d'être réévalué avec des bornes IQR plus larges (k > 1,5) sur un déploiement réel."),
  h2("10.2 Sélection de variables, élagage et lisibilité des règles de sécurité"),
  p("La sélection RFE et l'élagage par coût-complexité améliorent conjointement la lisibilité des règles produites " +
    "sans coût en performance — au contraire, une légère amélioration est observée pour la plupart des modèles " +
    "(cf. tableau section 7.3). L'effet est particulièrement marqué pour l'Arbre de Décision : la réduction de 679 " +
    "à 9 nœuds (profondeur 30 → 3) transforme un modèle inexploitable visuellement en un ensemble de règles de " +
    "sécurité directement interprétables par un analyste (par exemple : « si Frequence_SYN_Flags dépasse un seuil " +
    "donné et Taux_Erreur_CheckSum est faible, alors probable DDoS »). Cette explicabilité est un atout décisif " +
    "pour l'adoption opérationnelle du modèle en environnement SOC, où la confiance de l'analyste dans la décision " +
    "automatisée conditionne la réactivité face à une alerte."),
  h2("10.3 Apport de l'optimisation par GridSearchCV"),
  p("L'optimisation des hyperparamètres apporte un gain mesurable mais modéré, ce qui est cohérent avec le niveau " +
    "déjà élevé des performances baseline sur ce jeu de données. L'Arbre de Décision optimisé (profondeur maximale " +
    `5, ccp_alpha nul) atteint la meilleure exactitude finale (${pct(optimized.find(r => r.Modele.includes("Arbre")).Exactitude)}) ` +
    "et une AUC macro de 99,92 %, en progression par rapport au modèle élagué de l'Étape 3. La Régression " +
    "Logistique et le SVM bénéficient également d'un léger gain grâce à l'ajustement fin de leur régularisation " +
    "(C=0,1 et C=10/gamma=0,1 respectivement). Le principal apport de GridSearchCV réside ici moins dans le gain " +
    "brut d'exactitude que dans la garantie méthodologique de généralisation : la validation croisée à 5 plis " +
    "assure que les hyperparamètres retenus ne sont pas sur-ajustés à un unique découpage entraînement/test."),
  h2("10.4 Structuration de l'application de supervision"),
  p("L'application développée avec Streamlit (détaillée en section 9) répond à la quatrième question de recherche " +
    "en structurant l'interface autour du cycle de décision d'un analyste SOC : vision globale de la performance du " +
    "système (tableau de bord), traitement en masse de logs historiques ou en flux (import CSV), analyse " +
    "instantanée d'un événement isolé avec quantification de l'incertitude (prédiction unique et niveau de " +
    "confiance), et traçabilité des décisions prises (journal d'alertes). Cette structuration en quatre modules " +
    "distincts, articulés autour d'un unique modèle en production chargé une seule fois au démarrage de " +
    "l'application, garantit à la fois la réactivité de l'outil et la cohérence des prédictions rendues à " +
    "l'opérateur."),
];

const limites = [
  h1("11. Limites et perspectives"),
  p("Plusieurs limites méritent d'être signalées. Premièrement, les performances très élevées obtenues par tous " +
    "les algorithmes (exactitude et AUC systématiquement supérieures à 98 %) suggèrent une séparabilité forte des " +
    "classes dans ce jeu de données, probablement en partie synthétique ; sur un trafic réseau réel, plus bruité, " +
    "des écarts de performance plus marqués entre algorithmes seraient attendus. Deuxièmement, l'entraînement du " +
    "SVM a été réalisé sur un sous-échantillon de 8 000 observations pour des raisons de coût de calcul, ce qui " +
    "peut légèrement sous-estimer son potentiel réel sur l'ensemble des 40 000 observations d'entraînement. " +
    "Troisièmement, le déséquilibre des classes (75 % de trafic normal) n'a été traité que par stratification et " +
    "métriques macro-moyennées ; des techniques de ré-échantillonnage (SMOTE) ou de pondération des classes " +
    "pourraient être explorées pour améliorer davantage la détection de la classe minoritaire (Infiltration, " +
    "4,96 % des observations). Enfin, l'application Streamlit actuelle traite les imports CSV en mode batch ; une " +
    "intégration à un flux de logs véritablement temps réel (connecteur SIEM, file de messages) constituerait une " +
    "extension naturelle du projet."),
];

const conclusion = [
  h1("12. Conclusion"),
  p("Ce projet a permis de concevoir un pipeline complet de Machine Learning pour la détection d'intrusion réseau, " +
    "depuis le nettoyage rigoureux des données brutes jusqu'au déploiement d'une interface de supervision " +
    "opérationnelle. La comparaison systématique de cinq algorithmes, la réduction de dimensionnalité par RFE, " +
    "l'élagage interprétable de l'arbre de décision et l'optimisation par validation croisée ont convergé vers un " +
    "modèle final — un Arbre de Décision élagué à cinq variables — combinant performance élevée (exactitude " +
    `${pct(optimized.find(r => r.Modele.includes("Arbre")).Exactitude)}, AUC macro 99,92 %) et explicabilité, deux ` +
    "exigences essentielles pour la confiance des équipes de sécurité dans un système de détection automatisée. " +
    "L'application Streamlit développée démontre la faisabilité d'une intégration opérationnelle de ce modèle au " +
    "sein d'un poste de travail d'analyste SOC."),
];

// ---------------------------------------------------------------- Document
const doc = new Document({
  sections: [
    {
      properties: { page: { size: { width: 11906, height: 16838 } } }, // A4
      headers: {
        default: new Header({
          children: [new Paragraph({
            children: [new TextRun({ text: "Détection Intelligente des Attaques Réseau — Rapport de Projet M1", size: 16, color: "808080" })],
            alignment: AlignmentType.CENTER,
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            children: [new TextRun({ text: "Page ", size: 16 }), new TextRun({ children: [PageNumber.CURRENT], size: 16 })],
            alignment: AlignmentType.CENTER,
          })],
        }),
      },
      children: [
        ...titlePage,
        ...sommaire,
        ...intro,
        ...dataDesc,
        ...problematique,
        ...methodo,
        ...etape1,
        new Paragraph({ children: [new PageBreak()] }),
        ...etape2,
        new Paragraph({ children: [new PageBreak()] }),
        ...etape3,
        ...etape3b,
        new Paragraph({ children: [new PageBreak()] }),
        ...etape4,
        new Paragraph({ children: [new PageBreak()] }),
        ...etape5,
        new Paragraph({ children: [new PageBreak()] }),
        ...reponses,
        ...limites,
        ...conclusion,
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("report/Rapport_Projet_ML_SOC.docx", buffer);
  console.log("Rapport genere : report/Rapport_Projet_ML_SOC.docx");
});
