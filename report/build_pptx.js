const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const OUT = "outputs";
const FIG = path.join(OUT, "figures");
const DEMO = "demo_screenshots";

// ---------------------------------------------------------------- Data
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
const baseline = parseCsv(fs.readFileSync(path.join(OUT, "baseline_results.csv"), "utf8"));
const optimized = parseCsv(fs.readFileSync(path.join(OUT, "optimized_results.csv"), "utf8"));
const comparison = parseCsv(fs.readFileSync(path.join(OUT, "comparison_step3.csv"), "utf8"));
const gridParams = JSON.parse(fs.readFileSync(path.join(OUT, "grid_search_best_params.json"), "utf8"));
const bestInfo = JSON.parse(fs.readFileSync(path.join(OUT, "best_model_info.json"), "utf8"));
const eda = JSON.parse(fs.readFileSync(path.join(OUT, "eda_report.json"), "utf8"));
const selFeat = JSON.parse(fs.readFileSync(path.join(OUT, "selected_features.json"), "utf8"));
function pct(x) { return (parseFloat(x) * 100).toFixed(2) + " %"; }

const classLabels = {
  "0": "Normal", "1": "Scan de Ports", "2": "DDoS", "3": "Infiltration",
};

// ---------------------------------------------------------------- Palette (theme cybersecurite / SOC)
// Meme famille chromatique que l'application Streamlit (coherence deck <-> demo live),
// affinee pour l'impression : teal plus lumineux, ambre plus chaud, navy plus profond.
const NAVY = "0A1628";       // fond dominant, sombre (plus profond qu'avant -> plus de contraste)
const NAVY_LIGHT = "13233F"; // cartes sur fond sombre
const NAVY_MID = "1B355C";
const TEAL = "00E5C7";       // accent principal, plus lumineux sur fond sombre
const RED = "E63946";        // accent alerte / menace
const AMBER = "FFB454";      // accent secondaire (mise en avant / alerte moderee), plus chaud
const WHITE = "FFFFFF";
const TEXT_ONDARK = "F2F5FA";  // texte sur fond sombre : off-white, coherent avec l'app Streamlit
const LIGHT_BG = "F4F7FB";   // fond des slides de contenu
const TEXT_DARK = "10192B";
const TEXT_MUTED = "5B6B82";
const CARD_BORDER = "E3E9F2";

// Systeme typographique : Segoe UI (police systeme Windows/Office, moderne et tres largement
// disponible) pour les titres et le corps de texte, distingues par la graisse ; Consolas (mono,
// egalement standard Windows/Office) reserve aux valeurs chiffrees et donnees techniques, pour
// un rendu "lecture d'instrumentation SOC" qui differencie visuellement donnee et discours.
const FONT_HEAD = "Segoe UI Semibold";
const FONT_BODY = "Segoe UI";
const FONT_MONO = "Consolas";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
const W = 13.333, H = 7.5;

// ---------------------------------------------------------------- Helpers
function footer(slide, n) {
  slide.addText(`${n}`, { x: W - 0.7, y: H - 0.45, w: 0.5, h: 0.3, fontFace: FONT_BODY, fontSize: 10, color: TEXT_MUTED, align: "right" });
  slide.addText("Détection Intelligente des Attaques Réseau — Projet M1 UFRMI", { x: 0.5, y: H - 0.45, w: 7, h: 0.3, fontFace: FONT_BODY, fontSize: 9, color: TEXT_MUTED });
}

function iconCircle(slide, x, y, d, bg, label, labelColor) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color: bg }, line: { type: "none" } });
  slide.addText(label, { x, y, w: d, h: d, align: "center", valign: "middle", fontFace: FONT_MONO, fontSize: d * 24, bold: true, color: labelColor || WHITE });
}

function sectionHeader(slide, num, title, x, y, w) {
  iconCircle(slide, x, y, 0.5, TEAL, num, NAVY);
  slide.addText(title, { x: x + 0.65, y: y - 0.05, w: w - 0.65, h: 0.6, fontFace: FONT_HEAD, fontSize: 22, bold: true, color: TEXT_DARK, valign: "middle" });
}

function darkBg(slide) { slide.background = { color: NAVY }; }
function lightBg(slide) { slide.background = { color: LIGHT_BG }; }

function statCard(slide, x, y, w, h, value, label, accent) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: 0.12, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.18, blur: 6, offset: 2, angle: 90 } });
  slide.addText(value, { x, y: y + 0.15, w, h: h - 0.65, align: "center", valign: "bottom", fontFace: FONT_MONO, fontSize: 28, bold: true, color: accent });
  slide.addText(label, { x: x + 0.1, y: y + h - 0.5, w: w - 0.2, h: 0.4, align: "center", valign: "top", fontFace: FONT_BODY, fontSize: 11, color: TEXT_MUTED, charSpacing: 0.5 });
}

function tableStyled(slide, rows, opts) {
  slide.addTable(rows, opts);
}

// ================================================================== SLIDE 1 - TITRE
{
  const s = pres.addSlide(); darkBg(s);
  s.addShape("rect", { x: 0, y: 0, w: W, h: H, fill: { color: NAVY }, line: { type: "none" } });
  // motif : cercles decoratifs
  s.addShape("ellipse", { x: 10.6, y: -1.4, w: 4.5, h: 4.5, fill: { color: NAVY_MID }, line: { type: "none" } });
  s.addShape("ellipse", { x: -1.8, y: 5.2, w: 3.8, h: 3.8, fill: { color: NAVY_LIGHT }, line: { type: "none" } });

  iconCircle(s, 0.9, 0.75, 0.7, TEAL, "🛡", NAVY);
  s.addText("PROJET MASTER 1 INFORMATIQUE — UFRMI", { x: 0.9, y: 1.65, w: 9, h: 0.4, fontFace: FONT_BODY, fontSize: 14, color: TEAL, charSpacing: 2, bold: true });
  s.addText("Détection Intelligente et Supervision\nen Temps Réel des Attaques Réseau", {
    x: 0.9, y: 2.1, w: 11.9, h: 1.8, fontFace: FONT_HEAD, fontSize: 32, bold: true, color: TEXT_ONDARK, lineSpacing: 38,
  });
  s.addText("Pipeline Machine Learning · API FastAPI · Application de Supervision Streamlit", {
    x: 0.9, y: 4.15, w: 10, h: 0.5, fontFace: FONT_BODY, fontSize: 16, italic: true, color: "CADCFC",
  });

  s.addShape("line", { x: 0.9, y: 5.9, w: 3.2, h: 0, line: { color: TEAL, width: 2 } });
  s.addText([
    { text: "Réalisé par : ", options: { color: "9FB3D1" } },
    { text: "Komoe Edgar Junior\n", options: { color: TEXT_ONDARK, bold: true } },
    { text: "Responsable de l'enseignement : ", options: { color: "9FB3D1" } },
    { text: "Dr ASSOHOUN E Stanislas\n", options: { color: TEXT_ONDARK, bold: true } },
    { text: "ECUE Machine Learning — Public cible : Cybersécurité, Informatique, Science des Données", options: { color: "9FB3D1" } },
  ], { x: 0.9, y: 6.1, w: 10.5, h: 1.2, fontFace: FONT_BODY, fontSize: 13, lineSpacing: 20 });
}

// ================================================================== SLIDE 2 - SOMMAIRE
{
  const s = pres.addSlide(); darkBg(s);
  s.addText("Sommaire", { x: 0.9, y: 0.55, w: 8, h: 0.7, fontFace: FONT_HEAD, fontSize: 30, bold: true, color: TEXT_ONDARK });
  const items = [
    ["01", "Contexte, problématique et jeu de données"],
    ["02", "Méthodologie — pipeline en 5 étapes"],
    ["03", "Prétraitement, modélisation et optimisation"],
    ["04", "Modèle optimal retenu"],
    ["05", "Architecture logicielle — Streamlit & API FastAPI"],
    ["06", "Démonstration du produit final"],
    ["07", "Résultats, limites et conclusion"],
  ];
  const colW = 5.6;
  items.forEach((it, i) => {
    const col = i < 4 ? 0 : 1;
    const row = i < 4 ? i : i - 4;
    const x = 0.9 + col * (colW + 0.6);
    const y = 1.7 + row * 1.15;
    iconCircle(s, x, y, 0.55, NAVY_LIGHT, it[0], TEAL);
    s.addText(it[1], { x: x + 0.75, y: y - 0.05, w: colW - 0.75, h: 0.65, fontFace: FONT_BODY, fontSize: 15, color: TEXT_ONDARK, valign: "middle" });
  });
  footer(s, 2);
}

// ================================================================== SLIDE 3 - CONTEXTE & PROBLEMATIQUE
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "1", "Contexte et problématique", 0.7, 0.55, 8);
  s.addText(
    "Dans les architectures réseau modernes, la multiplication des vecteurs d'attaque (DDoS, scans furtifs, " +
    "exfiltration de données, rebonds d'intrusion) impose l'automatisation de la surveillance à partir des flux " +
    "de trafic collectés par les sondes d'un Centre Opérationnel de Sécurité (SOC).",
    { x: 0.7, y: 1.5, w: 11.9, h: 1.1, fontFace: FONT_BODY, fontSize: 15, color: TEXT_DARK, lineSpacing: 22 }
  );
  s.addShape("roundRect", { x: 0.7, y: 2.75, w: 11.9, h: 2.0, rectRadius: 0.12, fill: { color: NAVY }, line: { type: "none" } });
  s.addText("Problématique", { x: 1.1, y: 2.95, w: 6, h: 0.4, fontFace: FONT_BODY, fontSize: 13, bold: true, color: TEAL, charSpacing: 1 });
  s.addText(
    "Comment concevoir un pipeline de Machine Learning robuste et explicable capable d'analyser un grand volume " +
    "de flux réseau hétérogènes, d'isoler les variables les plus discriminantes, d'optimiser les performances de " +
    "classification multiclasse, et d'être intégré au sein d'une interface graphique interactive pour les " +
    "administrateurs de sécurité ?",
    { x: 1.1, y: 3.35, w: 11.1, h: 1.3, fontFace: FONT_HEAD, fontSize: 16, italic: true, color: TEXT_ONDARK, lineSpacing: 23 }
  );
  const qs = [
    "Impact du prétraitement (imputation, IQR) sur la stabilité des frontières de décision ?",
    "La sélection de variables et l'élagage améliorent-ils la lisibilité des règles de sécurité ?",
    "Quel apport de l'optimisation par GridSearchCV sur les scores de généralisation ?",
    "Comment structurer une application assistant l'opérateur face à une alerte ?",
  ];
  qs.forEach((q, i) => {
    const x = 0.7 + (i % 2) * 6.0;
    const y = 5.0 + Math.floor(i / 2) * 1.0;
    iconCircle(s, x, y, 0.4, TEAL, `Q${i + 1}`, NAVY);
    s.addText(q, { x: x + 0.55, y: y - 0.08, w: 5.4, h: 0.75, fontFace: FONT_BODY, fontSize: 11.5, color: TEXT_DARK, valign: "middle", lineSpacing: 14 });
  });
  footer(s, 3);
}

// ================================================================== SLIDE 4 - JEU DE DONNEES
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "1", "Le jeu de données", 0.7, 0.55, 8);
  s.addText("Enterprise_Network_Traffic_BigData.csv — flux réseau collectés par les sondes d'un SOC", {
    x: 0.7, y: 1.15, w: 11, h: 0.4, fontFace: FONT_BODY, fontSize: 13, italic: true, color: TEXT_MUTED,
  });

  statCard(s, 0.7, 1.75, 2.6, 1.7, eda.shape[0].toLocaleString("fr-FR"), "flux réseau (lignes)", TEAL);
  statCard(s, 3.5, 1.75, 2.6, 1.7, "9", "variables explicatives", TEAL);
  statCard(s, 6.3, 1.75, 2.6, 1.7, "4", "classes de menace", TEAL);
  statCard(s, 9.1, 1.75, 3.3, 1.7, "0", "doublon détecté", TEAL);

  s.addText("Répartition de la variable cible Statut_Menace", { x: 0.7, y: 3.75, w: 6, h: 0.4, fontFace: FONT_BODY, fontSize: 13, bold: true, color: TEXT_DARK });
  const chartData = [{
    name: "Effectif",
    labels: Object.keys(eda.class_distribution).map((k) => classLabels[k]),
    values: Object.values(eda.class_distribution),
  }];
  s.addChart("bar", chartData, {
    x: 0.7, y: 4.2, w: 6.0, h: 2.7,
    barDir: "col", showTitle: false, showLegend: false, showValue: true, dataLabelPosition: "outEnd",
    dataLabelColor: TEXT_DARK, dataLabelFontSize: 10,
    chartColors: [TEAL], catAxisLabelColor: TEXT_MUTED, valAxisLabelColor: TEXT_MUTED,
    catAxisLabelFontSize: 10, valAxisLabelFontSize: 9,
    valGridLine: { color: "E3E9F2", size: 1 }, catGridLine: { style: "none" },
    valAxisHidden: false,
  });

  s.addShape("roundRect", { x: 7.1, y: 3.75, w: 5.3, h: 3.15, rectRadius: 0.1, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1 } });
  s.addText("Déséquilibre représentatif d'un contexte SOC réel", { x: 7.4, y: 3.95, w: 4.8, h: 0.4, fontFace: FONT_BODY, fontSize: 12, bold: true, color: TEXT_DARK });
  const distText = Object.entries(eda.class_distribution_pct).map(([k, v]) => `${classLabels[k]} : ${v}%`).join("     ");
  s.addText(distText, { x: 7.4, y: 4.4, w: 4.8, h: 0.6, fontFace: FONT_BODY, fontSize: 10.5, color: TEXT_MUTED, lineSpacing: 16 });
  s.addText(
    "Ce déséquilibre (75% de trafic normal) justifie la stratification systématique du split et de la validation " +
    "croisée, ainsi que l'usage de métriques macro-moyennées (F1, AUC) plutôt que la seule exactitude.",
    { x: 7.4, y: 5.15, w: 4.8, h: 1.6, fontFace: FONT_BODY, fontSize: 11, color: TEXT_DARK, lineSpacing: 16 }
  );
  footer(s, 4);
}

// ================================================================== SLIDE 5 - PIPELINE GLOBAL
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "2", "Méthodologie — pipeline en 5 étapes", 0.7, 0.55, 10);
  const steps = [
    ["1", "Prétraitement", "Imputation, IQR,\nsplit 80/20, standardisation"],
    ["2", "Modélisation", "5 algorithmes\n(modèle complet)"],
    ["3", "Sélection", "RFE (5 var.) +\nélagage coût-complexité"],
    ["4", "Optimisation", "GridSearchCV\nCV stratifiée 5 plis"],
    ["5", "Déploiement", "App Streamlit +\nAPI FastAPI"],
  ];
  const cardW = 2.25, gap = 0.28, startX = 0.7, y = 2.3, cardH = 2.6;
  steps.forEach((st, i) => {
    const x = startX + i * (cardW + gap);
    s.addShape("roundRect", { x, y, w: cardW, h: cardH, rectRadius: 0.1, fill: { color: i === 4 ? NAVY : WHITE }, line: { color: CARD_BORDER, width: 1 },
      shadow: { type: "outer", color: "3A3A3A", opacity: 0.15, blur: 5, offset: 2, angle: 90 } });
    iconCircle(s, x + cardW / 2 - 0.32, y + 0.25, 0.64, i === 4 ? TEAL : NAVY, st[0], i === 4 ? NAVY : WHITE);
    s.addText(st[1], { x: x + 0.1, y: y + 1.05, w: cardW - 0.2, h: 0.4, align: "center", fontFace: FONT_HEAD, fontSize: 13.5, bold: true, color: i === 4 ? WHITE : TEXT_DARK });
    s.addText(st[2], { x: x + 0.12, y: y + 1.5, w: cardW - 0.24, h: 1.0, align: "center", fontFace: FONT_BODY, fontSize: 10, color: i === 4 ? "CADCFC" : TEXT_MUTED, lineSpacing: 13 });
    if (i < steps.length - 1) {
      s.addText("→", { x: x + cardW, y: y + cardH / 2 - 0.3, w: gap, h: 0.6, align: "center", valign: "middle", fontFace: FONT_BODY, fontSize: 20, bold: true, color: TEAL });
    }
  });
  s.addText(
    "Chaque étape est codée en Python (pandas, scikit-learn, matplotlib, FastAPI, Streamlit) et documentée dans " +
    "le rapport de projet. Les statistiques de nettoyage sont calculées exclusivement sur l'ensemble d'entraînement " +
    "(80%) pour éviter toute fuite d'information vers le test (20%).",
    { x: 0.7, y: 5.35, w: 11.9, h: 1.1, fontFace: FONT_BODY, fontSize: 13, color: TEXT_DARK, lineSpacing: 19 }
  );
  footer(s, 5);
}

// ================================================================== SLIDE 6 - ETAPE 1 PRETRAITEMENT
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "3", "Étape 1 — Prétraitement des données", 0.7, 0.55, 10);
  s.addImage({ path: path.join(FIG, "boxplots_avant_iqr.png"), x: 0.5, y: 1.35, w: 5.9, h: 4.72 });
  s.addImage({ path: path.join(FIG, "boxplots_apres_iqr.png"), x: 6.6, y: 1.35, w: 5.9, h: 4.72 });
  s.addText("AVANT écrêtage IQR", { x: 0.5, y: 6.05, w: 5.9, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 11, italic: true, color: TEXT_MUTED });
  s.addText("APRÈS écrêtage IQR (bornes calculées sur le train)", { x: 6.6, y: 6.05, w: 5.9, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 11, italic: true, color: TEXT_MUTED });
  s.addShape("roundRect", { x: 0.5, y: 6.5, w: 12.0, h: 0.65, rectRadius: 0.08, fill: { color: NAVY }, line: { type: "none" } });
  s.addText("Imputation médiane · Écrêtage IQR (k=1,5) · Split stratifié 80/20 (40 000 / 10 000) · Standardisation (centrage-réduction)", {
    x: 0.7, y: 6.5, w: 11.6, h: 0.65, valign: "middle", fontFace: FONT_BODY, fontSize: 12.5, color: TEXT_ONDARK, bold: true,
  });
  footer(s, 6);
}

// ================================================================== SLIDE 7 - ETAPE 2 BASELINE
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "3", "Étape 2 — Modélisation de base (5 algorithmes)", 0.7, 0.55, 11);
  s.addText("5 algorithmes entraînés sur les 9 variables standardisées (modèle complet) :", {
    x: 0.7, y: 1.25, w: 11, h: 0.4, fontFace: FONT_BODY, fontSize: 13, color: TEXT_MUTED,
  });
  const rows = [
    [
      { text: "Modèle", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY } } },
      { text: "Exactitude", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
      { text: "Précision", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
      { text: "Rappel", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
      { text: "F1-score", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
      { text: "AUC", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
    ],
    ...baseline.map((r) => [
      { text: r["Modele"].replace(/_/g, " "), options: { color: TEXT_DARK, bold: true } },
      { text: pct(r["Exactitude"]), options: { align: "center", color: TEXT_DARK, fontFace: FONT_MONO } },
      { text: pct(r["Precision (macro)"]), options: { align: "center", color: TEXT_DARK, fontFace: FONT_MONO } },
      { text: pct(r["Rappel (macro)"]), options: { align: "center", color: TEXT_DARK, fontFace: FONT_MONO } },
      { text: pct(r["F1-score (macro)"]), options: { align: "center", color: TEXT_DARK, fontFace: FONT_MONO } },
      { text: pct(r["AUC (macro)"]), options: { align: "center", color: TEAL, bold: true, fontFace: FONT_MONO } },
    ]),
  ];
  s.addTable(rows, {
    x: 0.7, y: 1.8, w: 11.9, h: 3.0, fontFace: FONT_BODY, fontSize: 12.5, border: { type: "solid", color: CARD_BORDER, pt: 1 },
    autoPage: false, colW: [3.1, 1.76, 1.76, 1.76, 1.76, 1.76],
  });
  s.addShape("roundRect", { x: 0.7, y: 5.15, w: 11.9, h: 1.5, rectRadius: 0.1, fill: { color: "FFF4E8" }, line: { color: AMBER, width: 1 } });
  s.addText(
    "Tous les modèles dépassent 98% d'exactitude. L'Arbre de Décision non élagué affiche l'AUC la plus faible " +
    "(98,22%) — signe d'un léger surapprentissage motivant l'élagage de l'Étape 3. Le SVM est entraîné sur un " +
    "sous-échantillon stratifié de 8 000 observations pour rester tractable (complexité cubique).",
    { x: 1.0, y: 5.15, w: 11.3, h: 1.5, valign: "middle", fontFace: FONT_BODY, fontSize: 12, color: "7A4A17", lineSpacing: 17 }
  );
  footer(s, 7);
}

// ================================================================== SLIDE 8 - ETAPE 3 RFE
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "3", "Étape 3 — Sélection de variables (RFE)", 0.7, 0.55, 10);
  s.addText(
    "Élimination récursive des variables (estimateur : Régression Logistique) : réduction de 9 à 5 dimensions.",
    { x: 0.7, y: 1.3, w: 11.5, h: 0.5, fontFace: FONT_BODY, fontSize: 14, color: TEXT_DARK }
  );
  const kept = selFeat.selected_features;
  const dropped = ["Duree_Connexion", "Connexions_Simultanees", "Octets_Dest_Vers_Source", "Fenetre_TCP_Moyenne"];
  s.addShape("roundRect", { x: 0.7, y: 2.0, w: 5.8, h: 4.3, rectRadius: 0.1, fill: { color: WHITE }, line: { color: TEAL, width: 1.5 } });
  s.addText("✓  Variables retenues (5)", { x: 1.0, y: 2.2, w: 5.2, h: 0.4, fontFace: FONT_BODY, fontSize: 14, bold: true, color: "0B8A76" });
  kept.forEach((f, i) => {
    s.addText(f.replace(/_/g, " "), { x: 1.2, y: 2.75 + i * 0.62, w: 4.9, h: 0.55, fontFace: FONT_BODY, fontSize: 13, color: TEXT_DARK, bullet: { code: "25B6", color: TEAL } });
  });
  s.addShape("roundRect", { x: 6.8, y: 2.0, w: 5.8, h: 4.3, rectRadius: 0.1, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1 } });
  s.addText("✕  Variables écartées (4)", { x: 7.1, y: 2.2, w: 5.2, h: 0.4, fontFace: FONT_BODY, fontSize: 14, bold: true, color: TEXT_MUTED });
  dropped.forEach((f, i) => {
    s.addText(f.replace(/_/g, " "), { x: 7.3, y: 2.75 + i * 0.62, w: 4.9, h: 0.55, fontFace: FONT_BODY, fontSize: 13, color: TEXT_MUTED, bullet: { code: "25CF", color: CARD_BORDER } });
  });
  footer(s, 8);
}

// ================================================================== SLIDE 9 - ETAPE 3 ELAGAGE + COMPARAISON
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "3", "Étape 3 — Élagage de l'arbre et comparaison", 0.7, 0.55, 11);
  s.addImage({ path: path.join(FIG, "ccp_alpha_curve.png"), x: 0.5, y: 1.25, w: 4.34, h: 3.1 });
  statCard(s, 5.15, 1.25, 3.35, 1.45, "679 → 9", "nœuds (avant → après)", RED);
  statCard(s, 8.65, 1.25, 3.35, 1.45, "30 → 3", "profondeur (avant → après)", RED);
  s.addShape("roundRect", { x: 5.15, y: 2.85, w: 6.85, h: 1.5, rectRadius: 0.1, fill: { color: NAVY }, line: { type: "none" } });
  s.addText(
    "L'élagage par coût-complexité (ccp_alpha ≈ 0,0060, choisi par CV 5 plis) transforme un arbre inexploitable " +
    "en un ensemble de règles lisibles par un analyste — sans perte de performance (AUC 98,22% → 99,89%).",
    { x: 5.45, y: 2.85, w: 6.25, h: 1.5, valign: "middle", fontFace: FONT_BODY, fontSize: 12, color: TEXT_ONDARK, lineSpacing: 16 }
  );
  s.addText("Impact global : le modèle réduit égale ou dépasse le modèle complet pour tous les algorithmes", {
    x: 0.5, y: 4.55, w: 12, h: 0.35, fontFace: FONT_BODY, fontSize: 12.5, bold: true, color: TEXT_DARK,
  });
  const rows = [
    [
      { text: "Modèle", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, fontSize: 11 } },
      { text: "Exact. complet", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center", fontSize: 11 } },
      { text: "Exact. réduit", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center", fontSize: 11 } },
      { text: "AUC complet", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center", fontSize: 11 } },
      { text: "AUC réduit", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center", fontSize: 11 } },
    ],
    ...comparison.map((r) => [
      { text: r["Modele"].replace(/_/g, " "), options: { color: TEXT_DARK, fontSize: 10.5 } },
      { text: pct(r["Exactitude_complet"]), options: { align: "center", color: TEXT_DARK, fontSize: 10.5, fontFace: FONT_MONO } },
      { text: pct(r["Exactitude_reduit"]), options: { align: "center", color: TEXT_DARK, fontSize: 10.5, fontFace: FONT_MONO } },
      { text: pct(r["AUC_complet"]), options: { align: "center", color: TEXT_DARK, fontSize: 10.5, fontFace: FONT_MONO } },
      { text: pct(r["AUC_reduit"]), options: { align: "center", color: TEAL, bold: true, fontSize: 10.5, fontFace: FONT_MONO } },
    ]),
  ];
  s.addTable(rows, { x: 0.5, y: 4.95, w: 12.0, h: 1.95, fontFace: FONT_BODY, border: { type: "solid", color: CARD_BORDER, pt: 1 }, autoPage: false, colW: [3.2, 2.2, 2.2, 2.2, 2.2],
    valign: "middle" });
  footer(s, 9);
}

// ================================================================== SLIDE 10 - ETAPE 4 GRIDSEARCHCV
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "3", "Étape 4 — Optimisation par GridSearchCV", 0.7, 0.55, 11);
  s.addText("Validation croisée stratifiée à 5 plis, grille élargie par algorithme, sur l'espace réduit à 5 variables :", {
    x: 0.7, y: 1.25, w: 11.5, h: 0.4, fontFace: FONT_BODY, fontSize: 12.5, color: TEXT_MUTED,
  });
  const rows = [
    [
      { text: "Modèle", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY } } },
      { text: "Meilleurs hyperparamètres", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY } } },
      { text: "Exactitude test", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
      { text: "AUC test", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
    ],
    ...optimized.map((r) => {
      const key = r["Modele"].replace("_optimise", "");
      const bp = gridParams[key] ? JSON.stringify(gridParams[key].best_params).replace(/[{}"]/g, "").replace(/,/g, ", ") : "";
      const isBest = r["Modele"] === bestInfo.name;
      return [
        { text: r["Modele"].replace(/_/g, " "), options: { color: TEXT_DARK, fontSize: 11.5, bold: isBest } },
        { text: bp, options: { color: TEXT_MUTED, fontSize: 10, fontFace: FONT_MONO } },
        { text: pct(r["Exactitude"]), options: { align: "center", color: isBest ? TEAL : TEXT_DARK, bold: isBest, fontSize: 11.5, fontFace: FONT_MONO } },
        { text: pct(r["AUC (macro)"]), options: { align: "center", color: isBest ? TEAL : TEXT_DARK, bold: isBest, fontSize: 11.5, fontFace: FONT_MONO } },
      ];
    }),
  ];
  s.addTable(rows, { x: 0.7, y: 1.75, w: 11.9, h: 3.3, fontFace: FONT_BODY, border: { type: "solid", color: CARD_BORDER, pt: 1 }, autoPage: false, colW: [2.6, 5.3, 2.0, 2.0] });
  s.addText("★  Ligne en surbrillance = modèle optimal retenu pour la production (Étape 5)", {
    x: 0.7, y: 5.2, w: 11, h: 0.4, fontFace: FONT_BODY, fontSize: 12, italic: true, color: TEAL,
  });
  footer(s, 10);
}

// ================================================================== SLIDE 11 - MODELE OPTIMAL (stat slide, dark)
{
  const s = pres.addSlide(); darkBg(s);
  s.addShape("ellipse", { x: 10.6, y: -1.6, w: 4.5, h: 4.5, fill: { color: NAVY_MID }, line: { type: "none" } });
  s.addText("MODÈLE OPTIMAL RETENU", { x: 0.9, y: 0.7, w: 8, h: 0.4, fontFace: FONT_BODY, fontSize: 14, color: TEAL, bold: true, charSpacing: 2 });
  s.addText(bestInfo.name.replace(/_/g, " "), { x: 0.9, y: 1.1, w: 11, h: 1.0, fontFace: FONT_HEAD, fontSize: 34, bold: true, color: TEXT_ONDARK });
  s.addText("Arbre de Décision élagué (profondeur 5), optimisé par GridSearchCV sur 5 variables réseau", {
    x: 0.9, y: 1.9, w: 11, h: 0.5, fontFace: FONT_BODY, fontSize: 14, italic: true, color: "CADCFC",
  });

  const stats = [
    [pct(bestInfo.accuracy), "Exactitude (test)"],
    [`${(bestInfo.f1_macro * 100).toFixed(2)} %`, "F1-score macro"],
    [`${(bestInfo.auc_macro * 100).toFixed(2)} %`, "AUC macro"],
    ["5 / 9", "Variables utilisées"],
  ];
  stats.forEach((st, i) => {
    const x = 0.9 + i * 2.9;
    s.addShape("roundRect", { x, y: 2.6, w: 2.6, h: 1.5, rectRadius: 0.12, fill: { color: NAVY_LIGHT }, line: { color: NAVY_MID, width: 1 } });
    s.addText(st[0], { x, y: 2.72, w: 2.6, h: 0.85, align: "center", fontFace: FONT_MONO, fontSize: 25, bold: true, color: TEAL });
    s.addText(st[1], { x, y: 3.55, w: 2.6, h: 0.5, align: "center", fontFace: FONT_BODY, fontSize: 11, color: "CADCFC" });
  });

  s.addImage({ path: path.join(FIG, "optimized", "cm_Arbre_Decision_optimise.png"), x: 1.2, y: 4.35, w: 3.06, h: 2.55 });
  s.addImage({ path: path.join(FIG, "optimized", "roc_Arbre_Decision_optimise.png"), x: 5.05, y: 4.35, w: 3.06, h: 2.55 });
  s.addShape("roundRect", { x: 8.5, y: 4.35, w: 3.9, h: 2.55, rectRadius: 0.1, fill: { color: NAVY_LIGHT }, line: { color: NAVY_MID, width: 1 } });
  s.addText(
    "Modèle interprétable (profondeur 5) et hautement performant : combinaison rare et précieuse pour la confiance " +
    "des équipes SOC dans une décision automatisée.",
    { x: 8.8, y: 4.35, w: 3.3, h: 2.55, valign: "middle", fontFace: FONT_BODY, fontSize: 12, italic: true, color: TEXT_ONDARK, lineSpacing: 17 }
  );
  footer(s, 11);
}

// ================================================================== SLIDE 12 - ARCHITECTURE LOGICIELLE
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "4", "Étape 5 — Architecture logicielle du produit final", 0.7, 0.55, 11);
  s.addImage({ path: path.join(FIG, "fastapi_architecture.png"), x: 0.9, y: 1.5, w: 11.5, h: 4.06 });
  s.addShape("roundRect", { x: 0.9, y: 5.75, w: 11.5, h: 1.15, rectRadius: 0.1, fill: { color: NAVY }, line: { type: "none" } });
  s.addText(
    "Deux interfaces distinctes partagent rigoureusement le même pipeline de prétraitement et le même modèle " +
    "optimal : l'application Streamlit (GUI opérateur) et l'API REST FastAPI (intégration programmatique).",
    { x: 1.2, y: 5.75, w: 10.9, h: 1.15, valign: "middle", fontFace: FONT_BODY, fontSize: 13, color: TEXT_ONDARK, lineSpacing: 18 }
  );
  footer(s, 12);
}

// ================================================================== SLIDE 13 - DEMO TABLEAU DE BORD
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "5", "Démonstration — Tableau de bord Streamlit", 0.7, 0.5, 11);
  s.addShape("roundRect", { x: 2.52, y: 1.2, w: 8.3, h: 5.75, rectRadius: 0.06, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1.5 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.2, blur: 8, offset: 3, angle: 90 } });
  s.addImage({ path: path.join(DEMO, "1_tableau_de_bord.png"), x: 2.64, y: 1.3, w: 8.06, h: 8.06 * (1000 / 1440) });
  footer(s, 13);
}

// ================================================================== SLIDE 14 - DEMO IMPORT CSV
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "5", "Démonstration — Import CSV & analyse de logs", 0.7, 0.5, 11);
  const imgW = 5.85, imgH = imgW * (1000 / 1440);
  s.addShape("roundRect", { x: 0.55, y: 1.35, w: imgW + 0.2, h: imgH + 0.2, rectRadius: 0.06, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1.5 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.18, blur: 6, offset: 2, angle: 90 } });
  s.addImage({ path: path.join(DEMO, "2a_import_csv_apercu.png"), x: 0.65, y: 1.45, w: imgW, h: imgH });
  s.addText("1. Chargement du fichier CSV de logs", { x: 0.65, y: 1.45 + imgH + 0.25, w: imgW, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 11.5, italic: true, color: TEXT_MUTED });

  s.addShape("roundRect", { x: 6.9, y: 1.35, w: imgW + 0.2, h: imgH + 0.2, rectRadius: 0.06, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1.5 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.18, blur: 6, offset: 2, angle: 90 } });
  s.addImage({ path: path.join(DEMO, "2b_import_csv_resultats.png"), x: 7.0, y: 1.45, w: imgW, h: imgH });
  s.addText("2. Résultats : 16 menaces détectées sur 50 flux (32%)", { x: 7.0, y: 1.45 + imgH + 0.25, w: imgW, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 11.5, italic: true, color: TEXT_MUTED });
  footer(s, 14);
}

// ================================================================== SLIDE 15 - DEMO PREDICTION UNIQUE + ALERTES
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "5", "Démonstration — Prédiction unique & journal d'alertes", 0.7, 0.5, 11);
  const imgW = 5.85, imgH = imgW * (1000 / 1440);
  s.addShape("roundRect", { x: 0.55, y: 1.35, w: imgW + 0.2, h: imgH + 0.2, rectRadius: 0.06, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1.5 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.18, blur: 6, offset: 2, angle: 90 } });
  s.addImage({ path: path.join(DEMO, "3b_prediction_unique_resultat.png"), x: 0.65, y: 1.45, w: imgW, h: imgH });
  s.addText("Prédiction instantanée + niveau de confiance (%)", { x: 0.65, y: 1.45 + imgH + 0.25, w: imgW, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 11.5, italic: true, color: TEXT_MUTED });

  s.addShape("roundRect", { x: 6.9, y: 1.35, w: imgW + 0.2, h: imgH + 0.2, rectRadius: 0.06, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1.5 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.18, blur: 6, offset: 2, angle: 90 } });
  s.addImage({ path: path.join(DEMO, "5_journal_alertes.png"), x: 7.0, y: 1.45, w: imgW, h: imgH });
  s.addText("Journal d'alertes dynamique, horodaté et exportable", { x: 7.0, y: 1.45 + imgH + 0.25, w: imgW, h: 0.35, align: "center", fontFace: FONT_BODY, fontSize: 11.5, italic: true, color: TEXT_MUTED });
  footer(s, 15);
}

// ================================================================== SLIDE 16 - DEMO SURVEILLANCE EN DIRECT
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "5", "Démonstration — Surveillance en direct", 0.7, 0.5, 11);
  const liveImgW = 6.98, liveImgH = liveImgW * (1000 / 1440);
  const liveCardX = (W - (liveImgW + 0.2)) / 2, liveCardW = liveImgW + 0.2, liveCardY = 1.2, liveCardH = liveImgH + 0.15;
  s.addShape("roundRect", { x: liveCardX, y: liveCardY, w: liveCardW, h: liveCardH, rectRadius: 0.06, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1.5 },
    shadow: { type: "outer", color: "3A3A3A", opacity: 0.2, blur: 8, offset: 3, angle: 90 } });
  s.addImage({ path: path.join(DEMO, "4b_surveillance_en_cours.png"), x: liveCardX + 0.1, y: liveCardY + 0.05, w: liveImgW, h: liveImgH });
  s.addText(
    "Flux réseau échantillonnés dans le jeu de données réel, classés un à un par le modèle en production — compteurs, " +
    "graphique et table se mettent à jour progressivement (sans rechargement de page), avec comparaison à la vérité terrain.",
    { x: liveCardX, y: liveCardY + liveCardH + 0.15, w: liveCardW, h: 0.5, align: "center", fontFace: FONT_BODY, fontSize: 12, italic: true, color: TEXT_MUTED, lineSpacing: 15 }
  );
  footer(s, 16);
}

// ================================================================== SLIDE 17 - API FASTAPI
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "5", "API REST FastAPI — endpoints & validation", 0.7, 0.55, 11);
  const rows = [
    [
      { text: "Méthode", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY }, align: "center" } },
      { text: "Route", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY } } },
      { text: "Description", options: { bold: true, color: TEXT_ONDARK, fill: { color: NAVY } } },
    ],
    [{ text: "GET", options: { align: "center", color: TEAL, bold: true } }, { text: "/health", options: { fontFace: FONT_MONO, color: TEXT_DARK } }, { text: "État de santé du service", options: { color: TEXT_DARK } }],
    [{ text: "GET", options: { align: "center", color: TEAL, bold: true } }, { text: "/model_info", options: { fontFace: FONT_MONO, color: TEXT_DARK } }, { text: "Métadonnées du modèle en production", options: { color: TEXT_DARK } }],
    [{ text: "POST", options: { align: "center", color: AMBER, bold: true } }, { text: "/predict", options: { fontFace: FONT_MONO, color: TEXT_DARK } }, { text: "Prédiction pour un flux réseau unique", options: { color: TEXT_DARK } }],
    [{ text: "POST", options: { align: "center", color: AMBER, bold: true } }, { text: "/predict_batch", options: { fontFace: FONT_MONO, color: TEXT_DARK } }, { text: "Prédiction pour une liste de flux (JSON)", options: { color: TEXT_DARK } }],
    [{ text: "POST", options: { align: "center", color: AMBER, bold: true } }, { text: "/predict_csv", options: { fontFace: FONT_MONO, color: TEXT_DARK } }, { text: "Prédiction pour un fichier CSV uploadé", options: { color: TEXT_DARK } }],
  ];
  s.addTable(rows, { x: 0.7, y: 1.35, w: 5.7, h: 3.4, fontFace: FONT_BODY, fontSize: 11.5, border: { type: "solid", color: CARD_BORDER, pt: 1 }, autoPage: false, colW: [1.1, 2.0, 2.6] });

  s.addShape("roundRect", { x: 6.7, y: 1.35, w: 5.9, h: 3.4, rectRadius: 0.08, fill: { color: NAVY }, line: { type: "none" } });
  s.addText("Exemple — POST /predict", { x: 7.0, y: 1.5, w: 5.3, h: 0.35, fontFace: FONT_BODY, fontSize: 11.5, bold: true, color: TEAL });
  s.addText(
    '{\n  "predicted_class": 1,\n  "predicted_label": "Scan de Ports",\n  "confidence": 100.0,\n  "is_threat": true\n}',
    { x: 7.0, y: 1.9, w: 5.4, h: 1.7, fontFace: FONT_MONO, fontSize: 11.5, color: "9EFCE8", lineSpacing: 15 }
  );
  s.addText("→ validation automatique Pydantic (422 si champ manquant/invalide)\n→ documentation interactive auto-générée : /docs (Swagger UI)", {
    x: 7.0, y: 3.55, w: 5.4, h: 1.1, fontFace: FONT_BODY, fontSize: 11, color: "CADCFC", lineSpacing: 15,
  });

  s.addShape("roundRect", { x: 0.7, y: 5.0, w: 11.9, h: 1.6, rectRadius: 0.1, fill: { color: "E9FBF7" }, line: { color: TEAL, width: 1 } });
  s.addText(
    "✓ Test croisé de cohérence : le fichier sample_logs_demo.csv soumis à l'API (/predict_csv) et à l'application " +
    "Streamlit (onglet Import CSV) renvoie exactement le même résultat — 16 menaces détectées sur 50 flux (32%) — " +
    "confirmant que les deux interfaces partagent rigoureusement le même pipeline et le même modèle.",
    { x: 1.0, y: 5.0, w: 11.3, h: 1.6, valign: "middle", fontFace: FONT_BODY, fontSize: 12.5, color: "0B6B5C", lineSpacing: 17 }
  );
  footer(s, 17);
}

// ================================================================== SLIDE 18 - REPONSES AUX QUESTIONS
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "6", "Synthèse — réponses aux questions de recherche", 0.7, 0.55, 11);
  const answers = [
    ["Q1", "Prétraitement", "Stabilise les frontières de décision (SVM, KNN) mais doit être manié avec prudence : certaines valeurs extrêmes sont le signal même de l'attaque."],
    ["Q2", "Sélection / élagage", "Améliore la lisibilité sans coût en performance — l'arbre passe de 679 à 9 nœuds, restant exploitable par un analyste."],
    ["Q3", "GridSearchCV", "Gain modéré mais garantie méthodologique de généralisation via la CV à 5 plis (évite le sur-ajustement à un seul split)."],
    ["Q4", "Application", "Architecture en 4 modules (dashboard, import, prédiction, alertes) + API FastAPI pour l'intégration programmatique."],
  ];
  answers.forEach((a, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.7 + col * 6.1, y = 1.5 + row * 2.55;
    s.addShape("roundRect", { x, y, w: 5.85, h: 2.3, rectRadius: 0.1, fill: { color: WHITE }, line: { color: CARD_BORDER, width: 1 },
      shadow: { type: "outer", color: "3A3A3A", opacity: 0.15, blur: 5, offset: 2, angle: 90 } });
    iconCircle(s, x + 0.25, y + 0.25, 0.55, NAVY, a[0], TEAL);
    s.addText(a[1], { x: x + 1.0, y: y + 0.28, w: 4.6, h: 0.5, fontFace: FONT_HEAD, fontSize: 14.5, bold: true, color: TEXT_DARK, valign: "middle" });
    s.addText(a[2], { x: x + 0.3, y: y + 0.95, w: 5.25, h: 1.2, fontFace: FONT_BODY, fontSize: 11.5, color: TEXT_MUTED, lineSpacing: 15 });
  });
  footer(s, 18);
}

// ================================================================== SLIDE 19 - LIMITES ET PERSPECTIVES
{
  const s = pres.addSlide(); lightBg(s);
  sectionHeader(s, "6", "Limites et perspectives", 0.7, 0.55, 10);
  const limits = [
    ["Séparabilité très forte", "Exactitude et AUC > 98% pour tous les modèles : dataset probablement en partie synthétique. Un trafic réel serait plus bruité."],
    ["SVM sous-échantillonné", "Entraînement sur 8 000/40 000 lignes pour rester tractable (complexité cubique) — potentiel réel possiblement sous-estimé."],
    ["Déséquilibre des classes", "Traité par stratification et métriques macro uniquement. Le SMOTE ou la pondération des classes pourraient améliorer la classe minoritaire (Infiltration, 4,96%)."],
    ["Traitement par lot (CSV)", "L'intégration à un flux de logs véritablement temps réel (connecteur SIEM, file de messages) reste une extension naturelle."],
  ];
  limits.forEach((l, i) => {
    const y = 1.55 + i * 1.25;
    iconCircle(s, 0.7, y, 0.45, RED, "!", WHITE);
    s.addText(l[0], { x: 1.35, y: y - 0.05, w: 3.2, h: 0.55, fontFace: FONT_BODY, fontSize: 13.5, bold: true, color: TEXT_DARK, valign: "middle" });
    s.addText(l[1], { x: 4.7, y: y - 0.1, w: 7.9, h: 1.0, fontFace: FONT_BODY, fontSize: 12, color: TEXT_MUTED, valign: "middle", lineSpacing: 15 });
  });
  footer(s, 19);
}

// ================================================================== SLIDE 20 - CONCLUSION
{
  const s = pres.addSlide(); darkBg(s);
  s.addShape("ellipse", { x: -1.8, y: -1.8, w: 4.5, h: 4.5, fill: { color: NAVY_MID }, line: { type: "none" } });
  s.addText("Conclusion", { x: 0.9, y: 0.7, w: 8, h: 0.7, fontFace: FONT_HEAD, fontSize: 30, bold: true, color: TEXT_ONDARK });
  s.addText(
    "Ce projet a permis de concevoir un pipeline complet de Machine Learning pour la détection d'intrusion réseau, " +
    "du nettoyage rigoureux des données jusqu'au déploiement d'une application de supervision et d'une API REST " +
    "opérationnelles.",
    { x: 0.9, y: 1.6, w: 11.2, h: 1.0, fontFace: FONT_BODY, fontSize: 15, color: "CADCFC", lineSpacing: 21 }
  );
  const highlights = [
    ["99,04 %", "Exactitude (test)"],
    ["98,72 %", "F1-score macro"],
    ["99,92 %", "AUC macro"],
    ["9 nœuds", "Arbre interprétable"],
  ];
  highlights.forEach((h, i) => {
    const x = 0.9 + i * 2.9;
    s.addShape("roundRect", { x, y: 2.85, w: 2.6, h: 1.7, rectRadius: 0.12, fill: { color: NAVY_LIGHT }, line: { color: NAVY_MID, width: 1 } });
    s.addText(h[0], { x, y: 2.98, w: 2.6, h: 0.85, align: "center", fontFace: FONT_MONO, fontSize: 23, bold: true, color: TEAL });
    s.addText(h[1], { x, y: 3.8, w: 2.6, h: 0.6, align: "center", fontFace: FONT_BODY, fontSize: 11, color: "CADCFC" });
  });
  s.addText(
    "Performance élevée et explicabilité, deux exigences essentielles pour la confiance des équipes de sécurité " +
    "dans un système de détection automatisée — validées par une application Streamlit et une API FastAPI testées " +
    "de bout en bout.",
    { x: 0.9, y: 4.9, w: 11.2, h: 1.0, fontFace: FONT_BODY, fontSize: 14, italic: true, color: TEXT_ONDARK, lineSpacing: 20 }
  );
  s.addShape("line", { x: 0.9, y: 6.1, w: 3.2, h: 0, line: { color: TEAL, width: 2 } });
  s.addText("Merci de votre attention — Questions ?", { x: 0.9, y: 6.3, w: 10, h: 0.6, fontFace: FONT_HEAD, fontSize: 20, bold: true, color: TEXT_ONDARK });
  footer(s, 20);
}

pres.writeFile({ fileName: "report/Presentation_Projet_ML_SOC.pptx" }).then(() => {
  console.log("Deck genere : report/Presentation_Projet_ML_SOC.pptx");
});
