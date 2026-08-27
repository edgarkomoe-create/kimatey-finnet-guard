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
};

const PLAIN_LANGUAGE = {
  "Scan de Ports / Reconnaissance": "une exploration suspecte de votre reseau",
  "Attaque DDoS / Volumetrique": "une tentative de surcharge de votre systeme",
  "Infiltration / Brute-Force / Exfiltration": "une tentative d'intrusion grave",
  "Suspecte": "une transaction mobile money qui ressemble a une fraude",
};
const SEVERITY_COLORS = {
  "Scan de Ports / Reconnaissance": "#f5a524",
  "Attaque DDoS / Volumetrique": "#e74c3c",
  "Infiltration / Brute-Force / Exfiltration": "#8e44ad",
  "Suspecte": "#e74c3c",
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
// Bascule vue simple / technique
// ==========================================================================
document.querySelectorAll(".view-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".view-toggle-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const isSimple = btn.dataset.view === "simple";
    document.getElementById("view-simple").style.display = isSimple ? "block" : "none";
    document.getElementById("view-technique").style.display = isSimple ? "none" : "block";
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
if (urlDomain === "reseau" || urlDomain === "transactions") {
  currentDomain = urlDomain;
  document.getElementById("header-eyebrow").innerHTML = DOMAIN_CONFIG[currentDomain].eyebrow;
  document.querySelector(".domain-toggle").style.display = "none";
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
  } catch (e) {
    document.getElementById("simple-banner").textContent = "Impossible de charger le dashboard (" + API_BASE_URL + ").";
  }
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
      animation: { duration: 900, easing: "easeOutQuart" },
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#9FB3CC" }, grid: { display: false } },
        y: { ticks: { color: "#9FB3CC" }, grid: { color: "rgba(255,255,255,0.05)" }, beginAtZero: true },
      },
    },
  });

  renderTimelineChart(data.day_severity_series);
  renderAlertList(data.alerts);
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
    filteredAlerts = currentDashboardData.alerts.filter((a) => {
      const day = a.Horodatage.slice(0, 10);
      if (startStr && day < startStr) return false;
      if (endStr && day > endStr) return false;
      return true;
    });
  }
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
// Demarrage
// ==========================================================================
if (getToken()) {
  showDashboard();
}
