// ==========================================================================
// Etat
// ==========================================================================
const DASH_TOKEN_KEY = "kimatey_dash_token";
const DASH_EMAIL_KEY = "kimatey_dash_email";
let severityChart = null;
let timelineChart = null;
let statusChart = null;
let currentDomain = "reseau"; // 'reseau' ou 'transactions'
let currentDashboardData = null; // derniere reponse API, pour filtrage de date cote client

// ==========================================================================
// Donnees reelles du pipeline pour chaque domaine (issues des artefacts
// d'entrainement - outputs/best_model_info*.json) - pas de valeurs inventees.
// ==========================================================================
const PIPELINE_DATA = {
  reseau: {
    sousTitre: "Arbre de Decision optimise - entraine sur 50 000 flux reseau reels",
    etapes: [
      { titre: "Donnees", valeur: "50 000", sous: "flux reseau reels" },
      { titre: "Pretraitement", valeur: "9 → 5", sous: "variables (RFE + IQR)" },
      { titre: "Comparaison", valeur: "5 algos", sous: "validation croisee 5 plis" },
      { titre: "Modele retenu", valeur: "Arbre de Decision", sous: "GridSearchCV" },
      { titre: "Evaluation", valeur: "F1 98.72%", sous: "Accuracy 99.04% / AUC 99.92%" },
    ],
  },
  transactions: {
    sousTitre: "Gradient Boosting - entraine sur 8 000 transactions synthetiques calibrees BCEAO",
    etapes: [
      { titre: "Donnees", valeur: "8 000", sous: "transactions synthetiques" },
      { titre: "Pretraitement", valeur: "8 var.", sous: "standardisation train-only" },
      { titre: "Comparaison", valeur: "4 algos", sous: "AUC-PR (classes desequilibrees)" },
      { titre: "Modele retenu", valeur: "Gradient Boosting", sous: "GridSearchCV" },
      { titre: "Evaluation", valeur: "F1 72.63%", sous: "AUC 81.94% / Accuracy 96.53%" },
    ],
  },
  iot: {
    sousTitre: "Foret Aleatoire - entraine sur 148 850 flux IIoT reels (attaques + benin)",
    etapes: [
      { titre: "Donnees", valeur: "148 850", sous: "flux IIoT reels" },
      { titre: "Pretraitement", valeur: "71 → 30", sous: "variables (VIF + norm. duree)" },
      { titre: "Comparaison", valeur: "4 algos", sous: "F1 macro, class_weight" },
      { titre: "Modele retenu", valeur: "Foret Aleatoire", sous: "class_weight=balanced" },
      { titre: "Evaluation", valeur: "F1 95.62%", sous: "119 080 train / 29 770 test" },
    ],
  },
};

function renderPipelineDiagram(domaine) {
  const config = PIPELINE_DATA[domaine];
  if (!config) return;
  document.getElementById("pipeline-subtitle").textContent = config.sousTitre;

  const largeurNoeud = 152, hauteurNoeud = 92, ecart = 26;
  const largeurTotale = config.etapes.length * largeurNoeud + (config.etapes.length - 1) * ecart;
  const hauteurSvg = 130;

  let svg = `<svg viewBox="0 0 ${largeurTotale} ${hauteurSvg}" style="width:100%;height:auto;max-width:900px;display:block;margin:0 auto;">`;

  config.etapes.forEach((etape, i) => {
    const x = i * (largeurNoeud + ecart);
    const y = 15;
    const estDernier = i === config.etapes.length - 1;
    const classeBoite = estDernier ? "pipeline-node-box highlight" : "pipeline-node-box";

    svg += `
      <rect x="${x}" y="${y}" width="${largeurNoeud}" height="${hauteurNoeud}" rx="10" class="${classeBoite}"/>
      <text x="${x + largeurNoeud / 2}" y="${y + 22}" text-anchor="middle" class="pipeline-node-title">${etape.titre}</text>
      <text x="${x + largeurNoeud / 2}" y="${y + 48}" text-anchor="middle" class="pipeline-node-value">${etape.valeur}</text>
      <text x="${x + largeurNoeud / 2}" y="${y + 68}" text-anchor="middle" class="pipeline-node-sub">${etape.sous}</text>
    `;

    if (!estDernier) {
      const xFleche = x + largeurNoeud;
      const yMilieu = y + hauteurNoeud / 2;
      svg += `
        <line x1="${xFleche}" y1="${yMilieu}" x2="${xFleche + ecart - 8}" y2="${yMilieu}" class="pipeline-arrow"/>
        <polygon points="${xFleche + ecart - 8},${yMilieu - 5} ${xFleche + ecart + 2},${yMilieu} ${xFleche + ecart - 8},${yMilieu + 5}" class="pipeline-arrow-head"/>
      `;
    }
  });

  svg += "</svg>";
  document.getElementById("pipeline-svg-container").innerHTML = svg;
}

const DOMAIN_CONFIG = {
  reseau: {
    endpoint: "/organisation/dashboard_soc",
    toggleEndpoint: "/organisation/dashboard_soc/toggle/",
    eyebrow: "Securite Reseau &middot; Espace Organisation",
    bannerGood: "🟢 Votre reseau est actuellement bien protege",
  },
  transactions: {
    endpoint: "/organisation/dashboard_transactions",
    toggleEndpoint: "/organisation/dashboard_transactions/toggle/",
    eyebrow: "Fraude Transactionnelle &middot; Espace Organisation (Prototype)",
    bannerGood: "🟢 Aucune transaction suspecte en attente",
  },
  iot: {
    endpoint: "/organisation/dashboard_iot",
    toggleEndpoint: "/organisation/dashboard_iot/toggle/",
    eyebrow: "Securite IIoT &middot; Espace Organisation",
    bannerGood: "🟢 Aucune menace IIoT en attente",
  },
};

const PLAIN_LANGUAGE = {
  "Scan de Ports / Reconnaissance": "une exploration suspecte de votre reseau",
  "Attaque DDoS / Volumetrique": "une tentative de surcharge de votre systeme",
  "Infiltration / Brute-Force / Exfiltration": "une tentative d'intrusion grave",
  "Suspecte": "une transaction mobile money qui ressemble a une fraude",
  "recon": "une exploration suspecte de vos objets connectes",
  "dos": "une tentative de saturation d'un appareil",
  "ddos": "une tentative de saturation distribuee",
  "mitm": "une tentative d'interception de vos communications",
  "malware": "un logiciel malveillant detecte sur le reseau",
  "web": "une attaque applicative (injection...)",
  "bruteforce": "une tentative de force brute sur des identifiants",
};
const SEVERITY_COLORS = {
  "Scan de Ports / Reconnaissance": "#f5a524",
  "Attaque DDoS / Volumetrique": "#e74c3c",
  "Infiltration / Brute-Force / Exfiltration": "#8e44ad",
  "Suspecte": "#e74c3c",
  "recon": "#f5a524",
  "dos": "#e67e22",
  "ddos": "#e74c3c",
  "mitm": "#8e44ad",
  "malware": "#c0392b",
  "web": "#3498db",
  "bruteforce": "#d35400",
};

function getToken() { return localStorage.getItem(DASH_TOKEN_KEY); }
function setSession(token, email) {
  localStorage.setItem(DASH_TOKEN_KEY, token);
  localStorage.setItem(DASH_EMAIL_KEY, email);
}
function clearSession() {
  localStorage.removeItem(DASH_TOKEN_KEY);
  localStorage.removeItem(DASH_EMAIL_KEY);
}

// ==========================================================================
// Ecran de connexion
// ==========================================================================
document.querySelectorAll(".login-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".login-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const isLogin = tab.dataset.tab === "login";
    document.getElementById("login-panel").style.display = isLogin ? "block" : "none";
    document.getElementById("register-panel").style.display = isLogin ? "none" : "block";
    document.getElementById("login-error").textContent = "";
  });
});

async function authRequest(mode, email, password) {
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";
  if (!email || !password) { errorEl.textContent = "Email et mot de passe requis."; return; }
  try {
    const r = await fetch(API_BASE_URL + "/auth/" + mode, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const body = await r.json();
    if (!r.ok) { errorEl.textContent = body.detail || "Une erreur est survenue."; return; }
    setSession(body.token, email);
    showDashboard();
    demarrerAutoRefresh();
  } catch (e) {
    errorEl.textContent = "Impossible de contacter le serveur (" + API_BASE_URL + ").";
  }
}

document.getElementById("login-submit").addEventListener("click", () => {
  authRequest("login", document.getElementById("login-email").value.trim(), document.getElementById("login-password").value);
});
document.getElementById("register-submit").addEventListener("click", () => {
  authRequest("register", document.getElementById("register-email").value.trim(), document.getElementById("register-password").value);
});

// ==========================================================================
// Bascule vue simple / technique / globale
// ==========================================================================
document.querySelectorAll(".view-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".view-toggle-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const vue = btn.dataset.view;
    document.getElementById("view-simple").style.display = vue === "simple" ? "block" : "none";
    document.getElementById("view-technique").style.display = vue === "technique" ? "block" : "none";
    document.getElementById("view-globale").style.display = vue === "globale" ? "block" : "none";
    if (vue === "globale") chargerVueGlobale();
  });
});

// ==========================================================================
// Bascule domaine : Securite Reseau / Fraude Transactionnelle
// ==========================================================================
document.querySelectorAll(".domain-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".domain-toggle-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentDomain = btn.dataset.domain;
    document.getElementById("header-eyebrow").innerHTML = DOMAIN_CONFIG[currentDomain].eyebrow;
    if (getToken()) loadDashboardData();
  });
});

// ==========================================================================
// Contexte de domaine impose par l'URL (?domaine=reseau ou ?domaine=transactions).
// Quand l'utilisateur arrive depuis un espace precis (lien "Visualisation" dans
// l'Espace Reseau ou l'Espace Transactions de Streamlit), le dashboard reste
// STRICTEMENT scope a ce domaine - aucune visibilite sur l'autre, coherent
// avec le principe "deux produits distincts" de l'Espace Organisation. Le
// selecteur ne reste visible qu'en cas d'acces direct (pas de contexte fourni).
const urlParams = new URLSearchParams(window.location.search);
const urlDomain = urlParams.get("domaine");
if (urlDomain === "reseau" || urlDomain === "transactions" || urlDomain === "iot") {
  currentDomain = urlDomain;
  document.getElementById("header-eyebrow").innerHTML = DOMAIN_CONFIG[currentDomain].eyebrow;
  document.querySelector(".domain-toggle").style.display = "none";
} else {
  // Acces direct (pas de contexte de domaine impose) : la Vision Globale multi-domaines
  // devient pertinente - elle reste masquee en cas de verrouillage strict, coherent avec
  // le principe d'isolation des domaines etabli plus tot.
  document.getElementById("btn-vue-globale").style.display = "inline-block";
}

// ==========================================================================
// Chargement + rendu du dashboard
// ==========================================================================
async function showDashboard() {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("dashboard-screen").style.display = "block";
  const email = localStorage.getItem(DASH_EMAIL_KEY);
  document.getElementById("nav-actions").innerHTML =
    '<span style="color:var(--text-muted);font-size:.85rem;margin-right:.8rem;">' + email + '</span>' +
    '<button class="btn secondary" id="logout-btn">Se deconnecter</button>';
  document.getElementById("logout-btn").addEventListener("click", () => {
    clearSession();
    location.reload();
  });
  await loadDashboardData();
}

async function loadDashboardData() {
  try {
    const r = await fetch(API_BASE_URL + DOMAIN_CONFIG[currentDomain].endpoint, {
      headers: { Authorization: "Bearer " + getToken() },
    });
    if (r.status === 401) { clearSession(); location.reload(); return; }
    const data = await r.json();
    renderSimpleView(data);
    renderTechnicalView(data);
    updateLastRefreshedLabel();
  } catch (e) {
    document.getElementById("simple-banner").textContent = "Impossible de charger le dashboard (" + API_BASE_URL + ").";
  }
}

function updateLastRefreshedLabel() {
  const el = document.getElementById("last-updated");
  if (!el) return;
  const maintenant = new Date();
  el.textContent = "Mis a jour a " + maintenant.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function renderSimpleView(data) {
  const banner = document.getElementById("simple-banner");
  let color, bg, text;
  if (data.score >= 70) { color = "#22c55e"; bg = "rgba(34,197,94,0.12)"; text = DOMAIN_CONFIG[currentDomain].bannerGood; }
  else if (data.score >= 40) { color = "#f5a524"; bg = "rgba(245,165,36,0.12)"; text = "🟠 Une vigilance accrue est recommandee"; }
  else { color = "#e74c3c"; bg = "rgba(231,76,60,0.12)"; text = "🔴 Une attention immediate est necessaire"; }
  banner.style.borderLeftColor = color;
  banner.style.background = bg;
  banner.style.color = color;
  banner.textContent = text;

  const summary = document.getElementById("simple-summary");
  if (data.n_open === 0) {
    summary.innerHTML = "<p>Aucune situation ouverte ne necessite votre attention actuellement.</p>";
    return;
  }
  const categories = [...new Set(data.alerts.filter((a) => a.Statut === "Ouvert").map((a) => a.Menace))];
  const phrases = categories.map((c) => PLAIN_LANGUAGE[c] || "une activite inhabituelle");
  summary.innerHTML =
    "<p><b>" + data.n_open + " situation(s)</b> demande(nt) encore votre attention : " + phrases.join(", ") + ".</p>" +
    "<p>Au total, " + (data.n_open + data.n_closed) + " evenement(s) ont ete detectes et suivis.</p>";
}

function renderTechnicalView(data) {
  currentDashboardData = data; // conserve pour le filtrage de date cote client (voir applyDateFilter)
  renderPipelineDiagram(currentDomain);

  // ---- Jauge de score animee ----
  const circumference = 327; // 2 * PI * 52
  const offset = circumference - (data.score / 100) * circumference;
  const gaugeColor = data.score >= 70 ? "#22c55e" : (data.score >= 40 ? "#f5a524" : "#e74c3c");
  const fill = document.getElementById("gauge-fill");
  fill.style.stroke = gaugeColor;
  requestAnimationFrame(() => { fill.style.strokeDashoffset = offset; });
  document.getElementById("score-value").textContent = data.score;

  document.getElementById("kpi-open").textContent = data.n_open;
  document.getElementById("kpi-closed-sub").textContent = data.n_closed + " deja traitees";
  document.getElementById("kpi-treated").textContent = data.treated_rate_pct + "%";
  document.getElementById("kpi-mttr").textContent = data.mttr_hours !== null ? data.mttr_hours.toFixed(1) + " h" : "N/A";
  document.getElementById("kpi-trend").textContent = data.trend_delta_pct !== null ? data.trend_text : "N/A";

  // ---- Graphique statut (donut Ouvert/Ferme) ----
  if (statusChart) statusChart.destroy();
  statusChart = new Chart(document.getElementById("chart-status"), {
    type: "doughnut",
    data: {
      labels: ["Ouvertes", "Fermees"],
      datasets: [{ data: [data.n_open, data.n_closed], backgroundColor: ["#e74c3c", "#22c55e"], borderColor: "#132C53", borderWidth: 3 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 900, easing: "easeOutQuart" },
      plugins: { legend: { position: "bottom", labels: { color: "#9FB3CC", font: { size: 11 } } } },
    },
  });

  // ---- Graphique gravite (barres) ----
  const sevLabels = Object.keys(data.severity_breakdown);
  const sevValues = Object.values(data.severity_breakdown);
  if (severityChart) severityChart.destroy();
  severityChart = new Chart(document.getElementById("chart-severity"), {
    type: "bar",
    data: {
      labels: sevLabels.map((l) => l.split(" / ")[0]),
      datasets: [{ data: sevValues, backgroundColor: sevLabels.map((l) => SEVERITY_COLORS[l] || "#00D4B5"), borderRadius: 6 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 900, easing: "easeOutQuart" },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#9FB3CC" }, grid: { display: false } },
        y: { ticks: { color: "#9FB3CC" }, grid: { color: "rgba(255,255,255,0.05)" }, beginAtZero: true },
      },
    },
  });

  renderTimelineChart(data.day_severity_series);
  applyDateFilter(); // applique les filtres deja actifs (date + gravite) plutot que tout reafficher
}

// ---- Graphique chronologie multi-gravite (courbes), extrait en fonction separee
// pour pouvoir le re-dessiner uniquement (donnees filtrees par date) sans tout
// re-fetcher depuis l'API. ----
function renderTimelineChart(daySeveritySeries) {
  const days = Object.keys(daySeveritySeries);
  const allMenaces = [...new Set(days.flatMap((d) => Object.keys(daySeveritySeries[d])))];
  const datasets = allMenaces.map((menace) => ({
    label: menace.split(" / ")[0],
    data: days.map((d) => daySeveritySeries[d][menace] || 0),
    borderColor: SEVERITY_COLORS[menace] || "#00D4B5",
    backgroundColor: "transparent",
    tension: 0.35,
    pointRadius: 3,
  }));
  if (timelineChart) timelineChart.destroy();
  timelineChart = new Chart(document.getElementById("chart-timeline"), {
    type: "line",
    data: { labels: days, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 1000, easing: "easeOutQuart" },
      plugins: { legend: { labels: { color: "#9FB3CC", font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: "#9FB3CC" }, grid: { display: false } },
        y: { ticks: { color: "#9FB3CC" }, grid: { color: "rgba(255,255,255,0.05)" }, beginAtZero: true },
      },
    },
  });
}

// ---- Journal des alertes, extrait en fonction separee pour etre reutilisable ----
function renderAlertList(alerts) {
  const listEl = document.getElementById("alert-list");
  if (alerts.length === 0) {
    listEl.innerHTML = '<p style="color:var(--text-muted)">Aucune alerte enregistree.</p>';
    return;
  }
  listEl.innerHTML = alerts.slice(0, 50).map((a) => `
    <div class="alert-row">
      <span class="alert-status-dot ${a.Statut === "Ouvert" ? "open" : "closed"}"></span>
      <span class="alert-menace">${a.Menace}</span>
      <span class="alert-date">${a.Horodatage}</span>
      <button class="alert-toggle-btn" data-id="${a.ID}">${a.Statut === "Ouvert" ? "Marquer traitee" : "Rouvrir"}</button>
    </div>
  `).join("");
  listEl.querySelectorAll(".alert-toggle-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        const r = await fetch(API_BASE_URL + DOMAIN_CONFIG[currentDomain].toggleEndpoint + btn.dataset.id, {
          method: "POST",
          headers: { Authorization: "Bearer " + getToken() },
        });
        const body = await r.json();
        renderSimpleView(body.dashboard);
        renderTechnicalView(body.dashboard);
      } catch (e) {
        btn.disabled = false;
      }
    });
  });
}

// ==========================================================================
// Filtre de date (chronologie + journal) - filtrage cote client sur les
// donnees deja recuperees (day_severity_series couvre 14 jours cote serveur ;
// le journal complet est deja dans currentDashboardData.alerts).
// ==========================================================================
function applyDateFilter() {
  if (!currentDashboardData) return;
  const startStr = document.getElementById("filter-date-start").value;
  const endStr = document.getElementById("filter-date-end").value;

  let filteredSeries = currentDashboardData.day_severity_series;
  if (startStr || endStr) {
    filteredSeries = {};
    for (const [day, counts] of Object.entries(currentDashboardData.day_severity_series)) {
      if (startStr && day < startStr) continue;
      if (endStr && day > endStr) continue;
      filteredSeries[day] = counts;
    }
  }
  renderTimelineChart(filteredSeries);

  let filteredAlerts = currentDashboardData.alerts;
  if (startStr || endStr) {
    filteredAlerts = filteredAlerts.filter((a) => {
      const day = a.Horodatage.slice(0, 10);
      if (startStr && day < startStr) return false;
      if (endStr && day > endStr) return false;
      return true;
    });
  }

  const niveauxCoches = Array.from(document.querySelectorAll(".severity-checkbox:checked")).map((cb) => cb.value);
  filteredAlerts = filteredAlerts.filter((a) => niveauxCoches.includes(deduireNiveauGravite(a.Menace)));

  renderAlertList(filteredAlerts);
}

document.getElementById("filter-date-start").addEventListener("change", applyDateFilter);
document.getElementById("filter-date-end").addEventListener("change", applyDateFilter);
document.getElementById("filter-date-reset").addEventListener("click", () => {
  document.getElementById("filter-date-start").value = "";
  document.getElementById("filter-date-end").value = "";
  applyDateFilter();
});

// ==========================================================================
// Commentaire IA (Lieutenant Cyber) - persona executif ou analyste, meme
// endpoint /organisation/dashboard_soc/commentaire selon le mode.
// ==========================================================================
async function requestComment(mode, buttonEl, targetEl) {
  buttonEl.disabled = true;
  const originalText = buttonEl.textContent;
  buttonEl.textContent = "Reflexion en cours...";
  try {
    const r = await fetch(API_BASE_URL + "/organisation/dashboard_soc/commentaire", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + getToken() },
      body: JSON.stringify({ mode, domaine: currentDomain }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      targetEl.textContent = body.detail || "Une erreur est survenue.";
    } else {
      const body = await r.json();
      targetEl.textContent = "🎖️ " + body.commentaire;
    }
    targetEl.classList.add("visible");
  } catch (e) {
    targetEl.textContent = "Impossible de contacter le serveur.";
    targetEl.classList.add("visible");
  }
  buttonEl.disabled = false;
  buttonEl.textContent = originalText;
}

document.getElementById("btn-comment-executive").addEventListener("click", (e) => {
  requestComment("executive", e.target, document.getElementById("comment-executive"));
});
document.getElementById("btn-comment-analyst").addEventListener("click", (e) => {
  requestComment("analyst", e.target, document.getElementById("comment-technique"));
});

// ==========================================================================
// Rafraichissement : bouton manuel + auto-refresh periodique (60s). Se met
// en pause quand l'onglet n'est pas visible (economise des appels API
// inutiles), reprend au retour sur l'onglet.
// ==========================================================================
document.getElementById("btn-refresh").addEventListener("click", () => {
  if (getToken()) loadDashboardData();
});

let autoRefreshInterval = null;

function demarrerAutoRefresh() {
  if (autoRefreshInterval) return;
  autoRefreshInterval = setInterval(() => {
    if (getToken() && document.visibilityState === "visible") loadDashboardData();
  }, 60000); // 60 secondes
}

function arreterAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
    autoRefreshInterval = null;
  }
}

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && getToken()) {
    loadDashboardData(); // rafraichit immediatement au retour sur l'onglet
  }
});

// ==========================================================================
// Demarrage
// ==========================================================================
// Vue Globale : recupere les 3 domaines en parallele, affiche les scores
// cote a cote. Lecture seule - aucune action possible depuis cette vue.
// ==========================================================================
async function chargerVueGlobale() {
  const domaines = ["reseau", "transactions", "iot"];
  await Promise.all(domaines.map(async (d) => {
    const scoreEl = document.getElementById("globale-score-" + d);
    const subEl = document.getElementById("globale-sub-" + d);
    try {
      const r = await fetch(API_BASE_URL + DOMAIN_CONFIG[d].endpoint, {
        headers: { Authorization: "Bearer " + getToken() },
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const data = await r.json();
      const couleur = data.score >= 70 ? "#22c55e" : (data.score >= 40 ? "#f5a524" : "#e74c3c");
      scoreEl.textContent = data.score + "/100";
      scoreEl.style.color = couleur;
      subEl.textContent = data.n_open + " alerte(s) ouverte(s) - " + data.treated_rate_pct + "% traite";
    } catch (e) {
      scoreEl.textContent = "N/A";
      subEl.textContent = "Indisponible";
    }
  }));
}

// ==========================================================================
// Filtre de gravite (journal des alertes) : deduit un niveau (Critique/
// Elevee/Moyenne) a partir de la categorie de menace, coherent avec les
// couleurs SEVERITY_COLORS deja utilisees pour les graphiques.
// ==========================================================================
function deduireNiveauGravite(menace) {
  const critiques = ["Infiltration / Brute-Force / Exfiltration", "mitm", "malware"];
  const elevees = ["Attaque DDoS / Volumetrique", "ddos", "dos"];
  if (critiques.includes(menace)) return "Critique";
  if (elevees.includes(menace)) return "Elevee";
  return "Moyenne";
}

document.querySelectorAll(".severity-checkbox").forEach((cb) => {
  cb.addEventListener("change", applyDateFilter); // reutilise le meme pipeline de filtrage/rendu
});

// ==========================================================================
// Demarrage
// ==========================================================================
if (getToken()) {
  showDashboard();
  demarrerAutoRefresh();
}
