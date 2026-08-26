"""
Etape 5 : Application Kimatey FinNet Guard - Detection Intelligente des Attaques Reseau
Interface Streamlit integrant le modele optimal (Etape 4).

Page d'accueil orientant vers deux espaces distincts :
- Espace Organisation : tableau de bord technique (fintechs, agregateurs mobile money,
  institutions de microfinance, administrations publiques).
- Espace Grand Public : assistant conversationnel/vocal + sensibilisation ludique,
  pour les citoyens.

Lancer avec : streamlit run app/app.py
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent
# `streamlit run app/app.py` n'ajoute que le dossier app/ a sys.path (pas la racine
# du projet, contrairement a pytest via tests/conftest.py) : sans cette ligne,
# `from core.kimatey_core import ...` echoue avec ModuleNotFoundError des que
# l'application est lancee depuis un autre repertoire de travail que la racine.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.kimatey_core import (
    GENAI_AVAILABLE, genai, genai_types, ask_gemini,
    ASSISTANT_SYSTEM_PROMPT, ANONYMIZE_SYSTEM_PROMPT, ORG_ANALYST_SYSTEM_PROMPT, SCENARIOS, REPORT_STEPS,
    GAME_CATEGORIES, GAME_MASCOTS, BADGES, XP_PER_CORRECT, XP_PER_INCORRECT, MAX_HEARTS,
    compute_level, compute_unlocked_badges,
)
# Reutilise directement le module d'authentification de l'API (meme code, meme
# variable AUTH_MODE, meme fichier api/users.json) : pas d'appel HTTP necessaire
# puisque Streamlit et l'API partagent deja le meme processus Python / la meme
# base de code (voir core/kimatey_core.py), donc pas de risque de divergence
# entre "qui peut se connecter sur l'API" et "qui peut se connecter dans l'appli".
from api.auth import register_user, verify_user_credentials, create_token, EmailDejaUtilise

OUT_DIR = BASE_DIR / "outputs"
MODEL_DIR = OUT_DIR / "models"
DATA_DIR = BASE_DIR / "data"

FEATURES = joblib.load(MODEL_DIR / "feature_names.joblib")
MEDIANS = joblib.load(MODEL_DIR / "imputation_medians.joblib")
IQR_BOUNDS = joblib.load(MODEL_DIR / "iqr_bounds.joblib")
SCALER = joblib.load(MODEL_DIR / "scaler.joblib")
BEST_MODEL = joblib.load(MODEL_DIR / "best_model.joblib")

with open(OUT_DIR / "best_model_info.json") as f:
    BEST_MODEL_INFO = json.load(f)
SELECTED_FEATURES = BEST_MODEL_INFO["features_used"]

CLASS_NAMES = {0: "Normal / Legitime", 1: "Scan de Ports / Reconnaissance",
               2: "Attaque DDoS / Volumetrique", 3: "Infiltration / Brute-Force / Exfiltration"}
CLASS_ICONS = {0: "🟢", 1: "🟠", 2: "🔴", 3: "🟣"}
CLASS_COLORS = {0: "#2ecc71", 1: "#f39c12", 2: "#e74c3c", 3: "#8e44ad"}
CLASSES = [0, 1, 2, 3]

# Formulation en langage clair pour un public non technique : titre court, phrase
# d'explication concrete, et niveau de gravite (utilise pour le code couleur).
CLASS_PLAIN = {
    0: {"title": "Trafic normal", "level": "good",
        "desc": "Ce flux ressemble au trafic habituel du reseau : rien d'anormal detecte."},
    1: {"title": "Scan de ports", "level": "warn",
        "desc": "Quelqu'un teste plusieurs ports de vos systemes : un signe classique de reconnaissance avant une attaque."},
    2: {"title": "Attaque DDoS", "level": "threat",
        "desc": "Un afflux massif de trafic destine a surcharger vos systemes et a les rendre indisponibles."},
    3: {"title": "Infiltration / Vol de donnees", "level": "threat",
        "desc": "Un comportement typique d'une tentative d'intrusion ou d'exfiltration de donnees sensibles."},
}

FEATURE_LABELS = {
    "Duree_Connexion": "Duree de connexion (ms)",
    "Octets_Source_Vers_Dest": "Octets Source -> Dest",
    "Octets_Dest_Vers_Source": "Octets Dest -> Source",
    "Taux_Paquets_Secondes": "Taux de paquets/s",
    "Fenetre_TCP_Moyenne": "Fenetre TCP moyenne",
    "Ports_Dest_Distincts": "Ports dest. distincts (<1s)",
    "Connexions_Simultanees": "Connexions simultanees",
    "Taux_Erreur_CheckSum": "Taux erreur CheckSum",
    "Frequence_SYN_Flags": "Frequence drapeaux SYN",
}

# ---------------------------------------------------------------- Palette (coherente avec le PPTX de soutenance)
NAVY = "#0B1F3A"
NAVY_LIGHT = "#132C53"
NAVY_MID = "#1D3A66"
TEAL = "#00D4B5"
GRID_COLOR = "#2A4A73"
TEXT_LIGHT = "#F5F7FA"
TEXT_MUTED = "#9FB3CC"
# Code couleur semantique (lisible sans connaissance technique : vert = OK, ambre = a
# surveiller, rouge = danger). Reutilise partout ou une carte resume un niveau de risque.
GREEN = "#22c55e"
AMBER = "#f5a524"
RED = "#e74c3c"
LEVEL_COLORS = {"good": GREEN, "warn": AMBER, "threat": RED, "neutral": TEAL}
LEVEL_ICONS = {"good": "✅", "warn": "⚠️", "threat": "🚨", "neutral": "ℹ️"}

st.set_page_config(page_title="Kimatey FinNet Guard", layout="wide", page_icon="🛡️")

if "view" not in st.session_state:
    # Permet a une page web externe (voir web/index.html) de lier directement vers un
    # espace precis (ex: ?view=organisation) plutot que de forcer un double clic (arrivee
    # sur la page d'accueil Streamlit, puis clic vers l'espace deja choisi cote web).
    _query_view = st.query_params.get("view")
    st.session_state.view = _query_view if _query_view in ("organisation", "public") else "landing"
if "live_dist" not in st.session_state:
    st.session_state.live_dist = {}
if "live_rows" not in st.session_state:
    st.session_state.live_rows = []
if "live_stats" not in st.session_state:
    st.session_state.live_stats = {"n": 0, "threats": 0, "correct": 0}

# ---------------------------------------------------------------- CSS custom (theme navy / teal)
st.markdown(f"""
<style>
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
.block-container {{ padding-top: 1.6rem; }}

.soc-header {{
  background: linear-gradient(135deg, {NAVY_MID} 0%, {NAVY} 100%);
  border: 1px solid rgba(0,212,181,0.35);
  border-radius: 14px;
  padding: 1.5rem 1.9rem;
  margin-bottom: 1.3rem;
}}
.soc-header-top {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap; }}
.soc-header-title {{ display:flex; align-items:center; gap:1rem; }}
.soc-header h1 {{ margin:0; font-size:1.75rem; color:{TEXT_LIGHT}; }}
.soc-header p {{ margin:.35rem 0 0 0; color:{TEXT_MUTED}; font-size:.95rem; max-width:44rem; }}
.soc-subtext {{ margin:.9rem 0 0 0; color:{TEXT_MUTED}; font-size:.72rem; opacity:.85; }}
.soc-badge-row {{ display:flex; gap:.55rem; flex-wrap:wrap; margin-top:1rem; }}
.soc-chip {{
  background: rgba(0,212,181,0.12); border:1px solid rgba(0,212,181,0.4);
  color: {TEAL}; padding:.28rem .75rem; border-radius:999px; font-size:.78rem; font-weight:600;
}}

/* --- Indicateur permanent "surveillance active", visible sur tous les onglets --- */
.live-status-pill {{
  display:flex; align-items:center; gap:.5rem; background:rgba(34,197,94,0.12);
  border:1px solid rgba(34,197,94,0.4); color:{GREEN}; padding:.4rem .9rem;
  border-radius:999px; font-size:.8rem; font-weight:700; white-space:nowrap;
}}
.live-dot {{
  height:9px; width:9px; background:{GREEN}; border-radius:50%; display:inline-block;
  animation: pulse 1.4s infinite;
}}
.live-dot.red {{ background:{RED}; }}
@keyframes pulse {{ 0% {{opacity:1;}} 50% {{opacity:.25;}} 100% {{opacity:1;}} }}

/* --- Radar : anneaux concentriques qui se propagent depuis le bouclier, en boucle --- */
.radar-wrap {{ position:relative; width:56px; height:56px; display:flex; align-items:center; justify-content:center; flex:none; }}
.radar-ring {{
  position:absolute; border-radius:50%; border:2px solid {TEAL};
  width:16px; height:16px; opacity:0; animation: radar-pulse 2.6s ease-out infinite;
}}
.radar-ring.r2 {{ animation-delay: .9s; }}
.radar-ring.r3 {{ animation-delay: 1.8s; }}
@keyframes radar-pulse {{
  0% {{ width:14px; height:14px; opacity:.7; }}
  100% {{ width:58px; height:58px; opacity:0; }}
}}
.radar-core {{ position:relative; z-index:2; font-size:1.55rem; }}

.kpi-card {{
  background: {NAVY_LIGHT}; border:1px solid rgba(255,255,255,0.07);
  border-left: 4px solid {TEAL}; border-radius:10px; padding:.95rem 1.1rem; height:100%;
  box-shadow: 0 2px 8px rgba(0,0,0,0.18);
}}
.kpi-good {{ border-left-color:{GREEN}; }}
.kpi-warn {{ border-left-color:{AMBER}; }}
.kpi-threat {{ border-left-color:{RED}; }}
.kpi-neutral {{ border-left-color:{TEAL}; }}
.kpi-icon {{ font-size:1.25rem; }}
.kpi-label {{ color:{TEXT_LIGHT}; font-size:.86rem; font-weight:600; margin-top:.25rem; }}
.kpi-value {{ color:{TEXT_LIGHT}; font-size:1.65rem; font-weight:700; margin-top:.1rem; }}
.kpi-sub {{ color:{TEXT_MUTED}; font-size:.68rem; margin-top:.35rem; }}

/* --- Bandeau de resultat en langage clair (prediction unique / import CSV) --- */
.plain-result {{ padding:18px 20px; border-radius:10px; background:{NAVY_LIGHT}; margin-top:.4rem; }}
.plain-result h4 {{ margin:0; font-size:1.15rem; }}
.plain-result p {{ margin:.4rem 0 0 0; color:{TEXT_LIGHT}; font-size:.92rem; line-height:1.5; }}
.plain-result .tech {{ margin-top:.6rem; color:{TEXT_MUTED}; font-size:.72rem; }}

.chart-hint {{ color:{TEXT_MUTED}; font-size:.82rem; margin:.1rem 0 .6rem 0; }}
.section-title {{ color:{TEXT_LIGHT}; font-weight:700; margin-bottom:.4rem; }}

/* --- Page d'accueil : deux cartes "espace" --- */
.landing-card {{
  background: {NAVY_LIGHT}; border:1px solid rgba(255,255,255,0.08); border-radius:14px;
  padding:1.6rem 1.4rem; height:100%; box-shadow: 0 2px 10px rgba(0,0,0,0.2);
}}
.landing-card h3 {{ color:{TEXT_LIGHT}; margin-top:0; }}
.landing-card p {{ color:{TEXT_MUTED}; font-size:.92rem; line-height:1.5; }}
.landing-title {{ text-align:center; color:{TEXT_LIGHT}; font-size:1.35rem; font-weight:700; margin:.5rem 0 1.4rem 0; }}
</style>
""", unsafe_allow_html=True)


def kpi_card(icon, label, value, level="neutral", sub=None):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return (f'<div class="kpi-card kpi-{level}"><div class="kpi-icon">{icon}</div>'
            f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{sub_html}</div>')


def threat_level(rate_pct):
    """Traduit un taux de menace (%) en niveau semantique good/warn/threat."""
    if rate_pct <= 0:
        return "good"
    if rate_pct <= 20:
        return "warn"
    return "threat"


def plain_result_box(pred_class, confidence):
    info = CLASS_PLAIN[pred_class]
    color = LEVEL_COLORS[info["level"]]
    icon = LEVEL_ICONS[info["level"]]
    return (
        f'<div class="plain-result" style="border-left:6px solid {color}">'
        f'<h4 style="color:{color}">{icon} {info["title"]}</h4>'
        f'<p>{info["desc"]}</p>'
        f'<p>Confiance du systeme : <b>{confidence:.0f}%</b></p>'
        f'<div class="tech">Niveau de confiance : {confidence:.1f}% &middot; '
        f'Categorie technique : {CLASS_ICONS[pred_class]} {CLASS_NAMES[pred_class]}</div>'
        f'</div>'
    )


def style_dark_fig(fig, ax):
    """Applique le theme sombre navy/teal a une figure matplotlib."""
    fig.patch.set_facecolor(NAVY_LIGHT)
    ax.set_facecolor(NAVY_LIGHT)
    ax.tick_params(colors=TEXT_LIGHT, labelsize=8)
    ax.xaxis.label.set_color(TEXT_LIGHT)
    ax.yaxis.label.set_color(TEXT_LIGHT)
    ax.title.set_color(TEXT_LIGHT)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.grid(color=GRID_COLOR, linewidth=0.5, alpha=0.6)
    legend = ax.get_legend()
    if legend is not None:
        legend.get_frame().set_facecolor(NAVY_MID)
        legend.get_frame().set_edgecolor(GRID_COLOR)
        for text in legend.get_texts():
            text.set_color(TEXT_LIGHT)


def preprocess_raw_df(df_raw):
    """Applique le pipeline de nettoyage (imputation, IQR, standardisation) a un
    DataFrame brut contenant les 9 variables reseau, et renvoie les 5 variables
    retenues (RFE), pretes pour le modele optimal."""
    df = df_raw.copy()
    for col in FEATURES:
        if col not in df.columns:
            df[col] = MEDIANS[col]
        df[col] = df[col].fillna(MEDIANS[col])
        low, high = IQR_BOUNDS[col]
        df[col] = df[col].clip(lower=low, upper=high)
    df_scaled = pd.DataFrame(SCALER.transform(df[FEATURES]), columns=FEATURES, index=df.index)
    return df_scaled[SELECTED_FEATURES]


def predict_with_confidence(df_raw):
    X = preprocess_raw_df(df_raw)
    preds = BEST_MODEL.predict(X)
    probas = BEST_MODEL.predict_proba(X)
    confidences = probas.max(axis=1) * 100
    return preds, confidences, probas


def log_alert(source_label, pred_class, confidence, details=""):
    if pred_class != 0:
        state = load_org_state()
        state["alert_log"].insert(0, {
            "ID": str(uuid.uuid4())[:8],
            "Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Source": source_label,
            "Menace": CLASS_NAMES[pred_class],
            "Confiance (%)": round(confidence, 1),
            "Details": details,
            "Statut": "Ouvert",
            "Fermee_le": None,
        })
        save_org_state(state)


# ------------------------------------------------------------------------
# Persistance disque de l'etat operationnel (journal d'alertes + historique
# de score). Remplace le st.session_state precedent, ephemere par session :
# stocke sur le disque du serveur Streamlit, donc partage entre sessions et
# survit a une fermeture de page (limite connue : sur Streamlit Community
# Cloud gratuit, le disque peut etre reinitialise lors d'un redeploiement -
# suffisant pour cette demo, mais une vraie base de donnees serait requise
# pour une mise en production).
# ------------------------------------------------------------------------
ORG_STATE_FILE = Path(__file__).resolve().parent / "organisation_state.json"

SEVERITY_WEIGHT = {1: 1, 2: 2, 3: 3}  # 1=scan (faible), 2=DDoS (eleve), 3=infiltration (critique)


def load_org_state():
    if ORG_STATE_FILE.exists():
        with open(ORG_STATE_FILE) as f:
            return json.load(f)
    return {"alert_log": [], "score_history": []}


def save_org_state(state):
    with open(ORG_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def compute_security_score(alert_log):
    """Score composite /100 : penalise le trafic recent selon sa gravite ponderee.
    100 = aucune menace ouverte recemment ; descend selon le volume et la gravite
    des alertes encore ouvertes (une alerte fermee ne penalise plus le score)."""
    open_alerts = [a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"]
    if not open_alerts:
        return 100
    weight_map = {"Scan de Ports / Reconnaissance": 1, "Attaque DDoS / Volumetrique": 2,
                  "Infiltration / Brute-Force / Exfiltration": 3}
    total_weight = sum(weight_map.get(a["Menace"], 1) for a in open_alerts)
    avg_severity = total_weight / len(open_alerts)  # 1 a 3
    volume_penalty = min(40, len(open_alerts) * 0.5)  # plus d'alertes ouvertes = score plus bas, plafonne
    severity_penalty = (avg_severity / 3) * 60  # jusqu'a 60 points selon la gravite moyenne
    score = max(0, round(100 - volume_penalty - severity_penalty))
    return score


def record_score_snapshot(score):
    state = load_org_state()
    state.setdefault("score_history", []).append(
        {"Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Score": score}
    )
    state["score_history"] = state["score_history"][-50:]  # garde les 50 derniers points
    save_org_state(state)
    return state


def mttr_hours(alert_log):
    """Temps moyen de resolution, en heures, calcule sur les alertes fermees."""
    durations = []
    for a in alert_log:
        if a.get("Statut") == "Ferme" and a.get("Fermee_le"):
            try:
                t0 = datetime.strptime(a["Horodatage"], "%Y-%m-%d %H:%M:%S")
                t1 = datetime.strptime(a["Fermee_le"], "%Y-%m-%d %H:%M:%S")
                durations.append((t1 - t0).total_seconds() / 3600)
            except (ValueError, KeyError):
                continue
    if not durations:
        return None
    return sum(durations) / len(durations)


@st.cache_data(show_spinner=False)
def load_live_pool(n=3000, seed=42):
    """Echantillon mis en cache du jeu de donnees reel (avec verite terrain),
    utilise pour alimenter la simulation de surveillance en direct."""
    df = pd.read_csv(DATA_DIR / "Enterprise_Network_Traffic_BigData.csv")
    return df.sample(n=min(n, len(df)), random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------- Assistant conversationnel (Kimatey FinNet Guard)
# GEMINI_MODEL_CANDIDATES, ASSISTANT_SYSTEM_PROMPT, ask_gemini(), ANONYMIZE_SYSTEM_PROMPT,
# SCENARIOS et REPORT_STEPS vivent maintenant dans core/kimatey_core.py (importe en haut de
# ce fichier), pour etre partages a l'identique avec l'API FastAPI (api/main.py), qui expose
# desormais les memes contenus/comportement aux clients web du pole Grand Public.


def get_gemini_key():
    """Cle API Gemini : d'abord la variable d'environnement GEMINI_API_KEY (recommande),
    sinon une saisie manuelle temporaire faite dans l'interface (non sauvegardee sur disque)."""
    return os.environ.get("GEMINI_API_KEY") or st.session_state.get("gemini_api_key_manual", "")


# ---------------------------------------------------------------- Lieutenant Cyber - assistance a l'analyse
# (Espace Organisation). Meme IA que celle de l'Espace Grand Public (voir ORG_ANALYST_SYSTEM_PROMPT dans
# core/kimatey_core.py pour le grounding strict impose : elle commente un resultat DEJA calcule par le
# modele, elle ne classifie jamais elle-meme, et elle ne doit rien inventer au-dela des donnees fournies).
def render_lieutenant_cyber_explain_batch(n_flows, n_threats, rate, dist):
    if not GENAI_AVAILABLE or not get_gemini_key():
        st.caption(
            "🎖️ Lieutenant Cyber peut aussi resumer cette analyse en langage clair et recommander une "
            "action, des qu'une cle Gemini est configuree (variable d'environnement GEMINI_API_KEY)."
        )
        return
    if st.button("🎖️ Demander a Lieutenant Cyber un resume de cette analyse", key="lc_explain_batch"):
        client = genai.Client(api_key=get_gemini_key())
        content = (
            f"Resultat d'une analyse par lot de {n_flows} flux reseau, deja calcule par le modele de "
            f"machine learning (tu ne classifies pas toi-meme) : {n_threats} flux classes comme menace "
            f"({rate:.1f}% du trafic). Repartition par categorie : {dist.to_dict()}."
        )
        with st.spinner("Lieutenant Cyber analyse le resultat..."):
            explanation = ask_gemini(client, content, system_instruction=ORG_ANALYST_SYSTEM_PROMPT, cache=st.session_state)
        st.session_state.lc_batch_explanation = explanation
    if st.session_state.get("lc_batch_explanation"):
        with st.chat_message("assistant"):
            st.write(f"**🎖️ Lieutenant Cyber** : {st.session_state.lc_batch_explanation}")


def render_lieutenant_cyber_explain_flow(pred_class, confidence, probas_row, values):
    if not GENAI_AVAILABLE or not get_gemini_key():
        st.caption(
            "🎖️ Lieutenant Cyber peut aussi expliquer ce resultat en langage clair et recommander une "
            "action, des qu'une cle Gemini est configuree (variable d'environnement GEMINI_API_KEY)."
        )
        return
    if st.button("🎖️ Demander a Lieutenant Cyber d'expliquer ce resultat", key="lc_explain_single"):
        client = genai.Client(api_key=get_gemini_key())
        probabilities = {CLASS_NAMES[c]: round(float(probas_row[c]) * 100, 2) for c in CLASSES}
        content = (
            f"Resultat de classification d'un flux reseau unique, deja calcule par le modele de machine "
            f"learning (tu ne classifies pas toi-meme) : classe predite '{CLASS_NAMES[pred_class]}' "
            f"(code {pred_class}), confiance {confidence:.1f}%. Probabilites par categorie : "
            f"{probabilities}. Valeurs des variables techniques du flux : {values}."
        )
        with st.spinner("Lieutenant Cyber analyse le resultat..."):
            explanation = ask_gemini(client, content, system_instruction=ORG_ANALYST_SYSTEM_PROMPT, cache=st.session_state)
        st.session_state.lc_single_explanation = explanation
    if st.session_state.get("lc_single_explanation"):
        with st.chat_message("assistant"):
            st.write(f"**🎖️ Lieutenant Cyber** : {st.session_state.lc_single_explanation}")


# ---------------------------------------------------------------- Header (affiche sur toutes les vues)
st.markdown(f"""
<div class="soc-header">
  <div class="soc-header-top">
    <div class="soc-header-title">
      <div class="radar-wrap">
        <span class="radar-ring r1"></span>
        <span class="radar-ring r2"></span>
        <span class="radar-ring r3"></span>
        <span class="radar-core">🛡️</span>
      </div>
      <div>
        <h1>🛡️ Kimatey FinNet Guard</h1>
        <p>Securise l'infrastructure reseau des fintechs, agregateurs mobile money, institutions de
        microfinance et administrations publiques - et sensibilise directement les citoyens contre les
        arnaques mobile money.</p>
      </div>
    </div>
    <div class="live-status-pill"><span class="live-dot"></span>Surveillance active</div>
  </div>
  <div class="soc-badge-row">
    <span class="soc-chip">✅ Fiable a {BEST_MODEL_INFO['accuracy']*100:.0f}%</span>
    <span class="soc-chip">🧠 Equilibre de detection {BEST_MODEL_INFO['f1_macro']*100:.0f}%</span>
    <span class="soc-chip">🔎 Distingue les menaces a {BEST_MODEL_INFO['auc_macro']*100:.0f}%</span>
    <span class="soc-chip">🧬 {len(SELECTED_FEATURES)}/{len(FEATURES)} signaux surveilles</span>
  </div>
  <p class="soc-subtext">Moteur technique : Detection Intelligente des Attaques Reseau ({BEST_MODEL_INFO['name'].replace('_', ' ')}) &middot;
  Pipeline ML : pretraitement → modelisation → selection de variables → optimisation GridSearchCV &middot;
  Exactitude {BEST_MODEL_INFO['accuracy']*100:.2f}% / F1 macro {BEST_MODEL_INFO['f1_macro']*100:.2f}% / AUC macro {BEST_MODEL_INFO['auc_macro']*100:.2f}%</p>
</div>
""", unsafe_allow_html=True)


# ==================================================================
# Vue : Page d'accueil
# ==================================================================
def render_landing():
    st.markdown('<p class="landing-title">Bienvenue - choisissez votre espace</p>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div class="landing-card"><h3>🏢 Espace Organisation</h3>'
            "<p>Tableau de bord technique : detection en temps reel, analyse de logs, surveillance "
            "en direct, journal d'alertes. Pour les equipes IT/securite des fintechs, operateurs "
            "mobile money, institutions financieres et administrations.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Entrer dans l'Espace Organisation →", type="primary", use_container_width=True, key="landing_org"):
            st.session_state.view = "organisation"
            st.rerun()
    with col2:
        st.markdown(
            '<div class="landing-card"><h3>👥 Espace Grand Public</h3>'
            "<p>Discutez avec Lieutenant Cyber, testez vos reflexes face aux arnaques mobile money, "
            "et aidez a en reperer de nouvelles - sans jamais partager d'information personnelle.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Entrer dans l'Espace Grand Public →", type="primary", use_container_width=True, key="landing_pub"):
            st.session_state.view = "public"
            st.rerun()


def render_organisation_login_gate():
    """Ecran de connexion / creation de compte, affiche uniquement quand
    AUTH_MODE=self_signup et que la session n'a pas encore de compte
    authentifie. Reutilise directement api/auth.py (voir import en tete de
    fichier) : aucun appel HTTP, meme code et meme fichier api/users.json que
    l'API FastAPI, donc les deux surfaces restent parfaitement coherentes."""
    st.markdown('<p class="landing-title">🔐 Connexion Espace Organisation</p>', unsafe_allow_html=True)
    st.caption(
        "Compte local a cette demonstration : aucun email n'est envoye ni verifie, "
        "un identifiant + mot de passe suffisent pour creer un compte et tester l'Espace Organisation."
    )
    tab_login, tab_register = st.tabs(["Se connecter", "Creer un compte"])

    with tab_login:
        with st.form("form_login_org"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Mot de passe", type="password", key="login_password")
            submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
        if submitted:
            if not email or not password:
                st.error("Email et mot de passe requis.")
            elif verify_user_credentials(email, password):
                email_norm = email.strip().lower()
                st.session_state.auth_email = email_norm
                st.session_state.auth_token = create_token(email_norm)
                st.rerun()
            else:
                st.error("Email ou mot de passe incorrect.")

    with tab_register:
        with st.form("form_register_org"):
            new_email = st.text_input("Email", key="register_email")
            new_password = st.text_input("Mot de passe (6 caracteres min.)", type="password", key="register_password")
            submitted_r = st.form_submit_button("Creer mon compte", type="primary", use_container_width=True)
        if submitted_r:
            if not new_email or "@" not in new_email or "." not in new_email.split("@")[-1]:
                st.error("Adresse email invalide.")
            elif len(new_password) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caracteres.")
            else:
                try:
                    register_user(new_email, new_password)
                except EmailDejaUtilise:
                    st.error("Un compte existe deja avec cet email - connectez-vous plutot.")
                else:
                    email_norm = new_email.strip().lower()
                    st.session_state.auth_email = email_norm
                    st.session_state.auth_token = create_token(email_norm)
                    st.success("Compte cree, vous etes connecte !")
                    st.rerun()


# ==================================================================
# Vue : Espace Organisation (5 onglets techniques)
# ==================================================================
def render_organisation_view():
    if st.button("← Retour a l'accueil", key="back_org"):
        st.session_state.view = "landing"
        st.rerun()

    if os.environ.get("AUTH_MODE") == "self_signup" and "auth_email" not in st.session_state:
        render_organisation_login_gate()
        return

    if os.environ.get("AUTH_MODE") == "self_signup":
        col_user, col_logout = st.columns([5, 1])
        # Email entre backticks (police code) plutot qu'en gras : Streamlit/markdown
        # transforme automatiquement un email brut en lien mailto: cliquable (souligne
        # bleu), ce qui ressemble a tort a un lien externe dans l'interface.
        col_user.caption(f"🔐 Connecte en tant que `{st.session_state.auth_email}`")
        if col_logout.button("Se deconnecter", key="logout_org"):
            del st.session_state["auth_email"]
            del st.session_state["auth_token"]
            st.rerun()

    tab_dashboard, tab_import, tab_predict, tab_live, tab_alerts = st.tabs(
        ["📊 Tableau de bord", "📁 Analyser un fichier de logs", "🔎 Verifier un flux unique",
         "🔴 Surveillance en direct", "🚨 Alertes detectees"]
    )

    # ---------------------------------------------------------------- Tab 1 : Dashboard
    with tab_dashboard:
        st.markdown('<p class="section-title">Le systeme est-il fiable ? (mesure sur des donnees de test jamais vues a l\'entrainement)</p>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(kpi_card("🎯", "Reponses correctes", "99 sur 100", level="good",
                              sub=f"Exactitude (accuracy) : {BEST_MODEL_INFO['accuracy']*100:.2f}%"), unsafe_allow_html=True)
        k2.markdown(kpi_card("⚖️", "Equilibre entre les 4 types de trafic", f"{BEST_MODEL_INFO['f1_macro']*100:.1f}%", level="good",
                              sub=f"F1-score macro : {BEST_MODEL_INFO['f1_macro']*100:.2f}%"), unsafe_allow_html=True)
        k3.markdown(kpi_card("📈", "Capacite a distinguer une vraie menace", f"{BEST_MODEL_INFO['auc_macro']*100:.1f}%", level="good",
                              sub=f"AUC macro : {BEST_MODEL_INFO['auc_macro']*100:.2f}%"), unsafe_allow_html=True)
        k4.markdown(kpi_card("🧬", "Signaux surveilles en permanence", f"{len(SELECTED_FEATURES)} / {len(FEATURES)}", level="neutral",
                              sub="Variables retenues apres selection (RFE)"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Comparaison de 5 techniques testees**")
            st.markdown('<p class="chart-hint">Plus la barre est haute, plus la technique classe correctement le trafic. '
                         'La technique retenue en production est l\'Arbre de Decision.</p>', unsafe_allow_html=True)
            if (OUT_DIR / "optimized_results.csv").exists():
                df_opt = pd.read_csv(OUT_DIR / "optimized_results.csv")
                st.dataframe(df_opt, use_container_width=True, hide_index=True)
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.bar(df_opt["Modele"].str.replace("_optimise", ""), df_opt["Exactitude"], color=TEAL)
                ax.set_ylabel("Exactitude")
                ax.set_ylim(0.9, 1.0)
                plt.xticks(rotation=30, ha="right", fontsize=8)
                style_dark_fig(fig, ax)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
        with c2:
            st.markdown("**Le systeme sait-il bien reconnaitre chaque type de menace ?**")
            st.markdown('<p class="chart-hint">Plus une courbe se rapproche du coin superieur gauche, mieux le systeme '
                         'distingue ce type de menace du trafic normal.</p>', unsafe_allow_html=True)
            roc_dark = OUT_DIR / "figures" / "optimized" / "roc_dashboard_dark.png"
            roc_path = roc_dark if roc_dark.exists() else OUT_DIR / "figures" / "optimized" / f"roc_{BEST_MODEL_INFO['name']}.png"
            if roc_path.exists():
                st.image(str(roc_path))
            cm_dark = OUT_DIR / "figures" / "optimized" / "cm_dashboard_dark.png"
            cm_path = cm_dark if cm_dark.exists() else OUT_DIR / "figures" / "optimized" / f"cm_{BEST_MODEL_INFO['name']}.png"
            if cm_path.exists():
                st.markdown("**Detail des erreurs, ligne par ligne**")
                st.image(str(cm_path))

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Moins de signaux surveilles, meme fiabilite**")
        st.markdown('<p class="chart-hint">En ne gardant que 5 signaux cles sur les 9 collectes, le systeme reste '
                     'aussi fiable, tout en etant plus simple a auditer pour un analyste.</p>', unsafe_allow_html=True)
        if (OUT_DIR / "comparison_step3.csv").exists():
            st.dataframe(pd.read_csv(OUT_DIR / "comparison_step3.csv"), use_container_width=True, hide_index=True)

    # ---------------------------------------------------------------- Tab 2 : Import CSV
    with tab_import:
        st.subheader("Analyser un fichier de logs reseau")
        st.write(
            "Chargez un extrait de vos journaux reseau (export de vos sondes) pour que le systeme "
            "les analyse tous d'un coup et vous dise lesquels sont suspects."
        )
        with st.expander("Colonnes techniques attendues dans le fichier"):
            st.write("Les colonnes manquantes seront remplacees par la valeur mediane observee a l'entrainement.")
            st.code(", ".join(FEATURES))

        uploaded = st.file_uploader("Choisir un fichier CSV", type=["csv"])
        if uploaded is not None:
            df_logs = pd.read_csv(uploaded)
            st.write(f"**{len(df_logs)} connexions chargees.**")
            st.dataframe(df_logs.head(10), use_container_width=True)

            if st.button("Lancer l'analyse des flux", type="primary"):
                preds, confs, probas = predict_with_confidence(df_logs)
                df_results = df_logs.copy()
                df_results["Menace_Predite"] = [CLASS_NAMES[p] for p in preds]
                df_results["Confiance (%)"] = confs.round(1)

                n_threats = int((preds != 0).sum())
                rate = n_threats / len(df_logs) * 100
                dist = pd.Series(preds).map(CLASS_NAMES).value_counts()

                # Resultat persiste en session_state (pas seulement local a ce bloc) : sinon, cliquer sur
                # le bouton "Demander a Lieutenant Cyber" plus bas (ou meme sur "Telecharger") declenche un
                # nouveau run de script ou "Lancer l'analyse des flux" redevient False, et toute cette
                # section disparaitrait - meme categorie de piste que le bug corrige sur la carte de
                # progression du jeu de vigilance (voir plus haut / README).
                st.session_state.last_batch_analysis = {
                    "n_flows": len(df_logs), "n_threats": n_threats, "rate": rate,
                    "distribution": dist.to_dict(), "df_results": df_results,
                }
                st.session_state.pop("lc_batch_explanation", None)

                for i in np.where(preds != 0)[0][:500]:
                    log_alert(f"Import CSV - ligne {i+1}", int(preds[i]), confs[i])
                if n_threats > 0:
                    st.warning(f"{n_threats} alerte(s) ajoutee(s) au journal d'alertes.")

        if "last_batch_analysis" in st.session_state:
            data = st.session_state.last_batch_analysis
            n_flows, n_threats, rate = data["n_flows"], data["n_threats"], data["rate"]
            dist = pd.Series(data["distribution"])
            df_results = data["df_results"]
            lvl = threat_level(rate)

            colA, colB, colC = st.columns(3)
            colA.markdown(kpi_card("📡", "Connexions verifiees", n_flows, level="neutral"), unsafe_allow_html=True)
            colB.markdown(kpi_card("🚨", "Connexions suspectes", n_threats, level=lvl), unsafe_allow_html=True)
            colC.markdown(kpi_card("📊", "Part du trafic suspect", f"{rate:.1f}%", level=lvl), unsafe_allow_html=True)

            summary_color = LEVEL_COLORS[lvl]
            summary_icon = LEVEL_ICONS[lvl]
            st.markdown(
                f'<p style="color:{summary_color};font-weight:600;margin-top:.6rem">{summary_icon} '
                f'Sur {n_flows} connexions verifiees, {n_threats} presentent un comportement suspect '
                f'({rate:.1f}% du trafic analyse).</p>',
                unsafe_allow_html=True,
            )

            st.markdown("<br>", unsafe_allow_html=True)
            fig, ax = plt.subplots(figsize=(6, 3.5))
            ax.bar(dist.index, dist.values, color=[CLASS_COLORS[c] for c in CLASSES if CLASS_NAMES[c] in dist.index])
            plt.xticks(rotation=15, ha="right", fontsize=8)
            ax.set_ylabel("Nombre de flux")
            style_dark_fig(fig, ax)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

            st.markdown("**Detail des flux (top 200 affiches)**")
            st.dataframe(df_results.head(200), use_container_width=True)

            csv_out = df_results.to_csv(index=False).encode("utf-8")
            st.download_button("Telecharger les resultats (CSV)", csv_out, "resultats_analyse.csv", "text/csv")

            st.markdown("---")
            render_lieutenant_cyber_explain_batch(n_flows, n_threats, rate, dist)

    # ---------------------------------------------------------------- Tab 3 : Prediction unique
    with tab_predict:
        st.subheader("Verifier un flux reseau unique")
        st.write(
            "Entrez les caracteristiques techniques d'une connexion reseau (ou laissez les valeurs "
            "par defaut) pour savoir si elle ressemble a du trafic normal ou a une attaque."
        )

        defaults = MEDIANS
        with st.form("single_flow_form"):
            cols = st.columns(3)
            values = {}
            for i, feat in enumerate(FEATURES):
                with cols[i % 3]:
                    values[feat] = st.number_input(
                        FEATURE_LABELS.get(feat, feat),
                        value=float(round(defaults[feat], 4)),
                        format="%.4f",
                    )
            submitted = st.form_submit_button("🔍 Analyser le flux", type="primary")

        if submitted:
            df_single = pd.DataFrame([values])
            preds, confs, probas = predict_with_confidence(df_single)
            # Persiste en session_state (voir remarque equivalente dans l'onglet Import CSV plus haut) :
            # sans cela, cliquer sur "Demander a Lieutenant Cyber" plus bas ferait disparaitre tout ce
            # bloc au rerun suivant, puisque `submitted` ne redevient vrai que sur un nouveau clic du
            # formulaire.
            st.session_state.last_single_prediction = {
                "pred_class": int(preds[0]), "confidence": float(confs[0]),
                "probas": probas[0].tolist(), "values": values,
            }
            st.session_state.pop("lc_single_explanation", None)
            log_alert("Saisie manuelle", int(preds[0]), float(confs[0]),
                       details=", ".join(f"{k}={v}" for k, v in values.items()))

        if "last_single_prediction" in st.session_state:
            data = st.session_state.last_single_prediction
            pred_class, confidence, probas_row, values_used = (
                data["pred_class"], data["confidence"], data["probas"], data["values"],
            )

            st.markdown("### Resultat de l'analyse")
            st.markdown(plain_result_box(pred_class, confidence), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Repartition des probabilites par categorie**")
            st.markdown('<p class="chart-hint">A quel point le systeme est-il sur de son verdict, pour chacune des 4 categories possibles ?</p>', unsafe_allow_html=True)
            proba_df = pd.DataFrame({
                "Classe": [CLASS_NAMES[c] for c in CLASSES],
                "Probabilite (%)": [round(probas_row[c] * 100, 2) for c in CLASSES],
            })
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.barh(proba_df["Classe"], proba_df["Probabilite (%)"], color=[CLASS_COLORS[c] for c in CLASSES])
            ax.set_xlabel("Probabilite (%)")
            style_dark_fig(fig, ax)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)

            if pred_class != 0:
                st.warning("⚠️ Menace detectee - alerte ajoutee au journal.")
            else:
                st.success("✅ Trafic classe comme legitime.")

            st.markdown("---")
            render_lieutenant_cyber_explain_flow(pred_class, confidence, probas_row, values_used)

    # ---------------------------------------------------------------- Tab 4 : Surveillance en direct
    with tab_live:
        st.subheader("🔴 Surveillance en direct (simulation)")
        st.write(
            "Simule un flux continu de connexions reseau soumises au systeme en production, "
            "echantillonnees aleatoirement dans le jeu de donnees reel (verite terrain connue), "
            "pour visualiser la supervision en conditions proches du temps reel. Il ne s'agit pas "
            "d'une capture reseau en direct, mais d'un rejeu realiste de donnees existantes."
        )

        pool = load_live_pool()

        c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
        n_flux = c1.slider("Nombre de flux a simuler", min_value=5, max_value=100, value=25, step=5)
        vitesse = c2.slider("Intervalle entre flux (s)", min_value=0.1, max_value=1.5, value=0.4, step=0.1)
        lancer = c3.button("▶ Demarrer", type="primary", use_container_width=True)
        reinit = c4.button("↺ Reinitialiser", use_container_width=True)

        if reinit:
            st.session_state.live_dist = {}
            st.session_state.live_rows = []
            st.session_state.live_stats = {"n": 0, "threats": 0, "correct": 0}
            st.rerun()

        kpi_ph = st.empty()
        status_ph = st.empty()
        chart_col, table_col = st.columns([1, 1.5])
        chart_ph = chart_col.empty()
        table_ph = table_col.empty()

        def render_kpis():
            s = st.session_state.live_stats
            rate = (s["threats"] / s["n"] * 100) if s["n"] else 0.0
            acc = (s["correct"] / s["n"] * 100) if s["n"] else 0.0
            lvl = threat_level(rate) if s["n"] else "neutral"
            with kpi_ph.container():
                a, b, cc, d = st.columns(4)
                a.markdown(kpi_card("📡", "Connexions verifiees", s["n"], level="neutral"), unsafe_allow_html=True)
                b.markdown(kpi_card("🚨", "Alertes levees", s["threats"], level=lvl), unsafe_allow_html=True)
                cc.markdown(kpi_card("📈", "Part suspecte", f"{rate:.1f}%", level=lvl), unsafe_allow_html=True)
                d.markdown(kpi_card("✅", "Fiabilite observee", f"{acc:.1f}%", level="good" if acc >= 90 or s["n"] == 0 else "warn",
                                     sub="Prediction comparee a la verite terrain"), unsafe_allow_html=True)

        def render_chart():
            fig, ax = plt.subplots(figsize=(5, 3.3))
            labels = [CLASS_NAMES[c].split(" / ")[0] for c in CLASSES]
            values = [st.session_state.live_dist.get(c, 0) for c in CLASSES]
            ax.bar(labels, values, color=[CLASS_COLORS[c] for c in CLASSES])
            ax.set_ylabel("Flux cumules")
            plt.xticks(rotation=15, ha="right", fontsize=7)
            style_dark_fig(fig, ax)
            fig.tight_layout()
            chart_ph.pyplot(fig)
            plt.close(fig)

        def render_table():
            rows = st.session_state.live_rows
            if rows:
                table_ph.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=360)
            else:
                table_ph.info("En attente du demarrage de la simulation...")

        render_kpis()
        render_chart()
        render_table()

        if lancer:
            for i in range(n_flux):
                row = pool.sample(1).iloc[0]
                true_label = int(row["Statut_Menace"])
                df_single = pd.DataFrame([row[FEATURES].to_dict()])
                preds, confs, probas = predict_with_confidence(df_single)
                pred_class = int(preds[0])
                confidence = float(confs[0])

                s = st.session_state.live_stats
                s["n"] += 1
                if pred_class != 0:
                    s["threats"] += 1
                if pred_class == true_label:
                    s["correct"] += 1
                st.session_state.live_dist[pred_class] = st.session_state.live_dist.get(pred_class, 0) + 1

                st.session_state.live_rows.insert(0, {
                    "Heure": datetime.now().strftime("%H:%M:%S"),
                    "Prediction": f"{CLASS_ICONS[pred_class]} {CLASS_NAMES[pred_class]}",
                    "Confiance (%)": round(confidence, 1),
                    "Verite terrain": f"{CLASS_ICONS[true_label]} {CLASS_NAMES[true_label]}",
                    "Statut": "✅ Correct" if pred_class == true_label else "❌ Ecart",
                })
                st.session_state.live_rows = st.session_state.live_rows[:12]

                log_alert(f"Surveillance en direct - flux #{s['n']}", pred_class, confidence)

                status_ph.markdown(
                    f'<span class="live-dot red"></span><span style="color:{TEXT_LIGHT}">'
                    f'Simulation en cours... ({i + 1}/{n_flux})</span>',
                    unsafe_allow_html=True,
                )
                render_kpis()
                render_chart()
                render_table()
                time.sleep(vitesse)
            status_ph.success(f"Simulation terminee : {n_flux} flux analyses.")
        elif st.session_state.live_stats["n"] == 0:
            status_ph.info("Cliquez sur *Demarrer* pour lancer la simulation de surveillance en direct.")

    # ---------------------------------------------------------------- Tab 5 : Journal d'alertes
    with tab_alerts:
        org_state = load_org_state()
        alert_log = org_state.get("alert_log", [])
        score = compute_security_score(alert_log)
        record_score_snapshot(score)
        org_state = load_org_state()  # relit apres l'ajout du nouveau point d'historique

        st.subheader("Etat operationnel")
        n_open = len([a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"])
        n_closed = len(alert_log) - n_open
        treated_rate = round(100 * n_closed / len(alert_log)) if alert_log else 0
        mttr = mttr_hours(alert_log)
        score_level = "good" if score >= 70 else ("warn" if score >= 40 else "threat")

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(kpi_card("🛡️", "Score de securite", f"{score}/100", level=score_level,
                              sub="Penalise selon volume et gravite des alertes encore ouvertes"), unsafe_allow_html=True)
        k2.markdown(kpi_card("🚨", "Alertes ouvertes", str(n_open), level=("threat" if n_open > 0 else "good"),
                              sub=f"{n_closed} deja traitees"), unsafe_allow_html=True)
        k3.markdown(kpi_card("✅", "Taux de traitement", f"{treated_rate}%", level="neutral",
                              sub="Part des alertes marquees comme fermees"), unsafe_allow_html=True)
        k4.markdown(kpi_card("⏱️", "Temps moyen de resolution", f"{mttr:.1f} h" if mttr is not None else "N/A",
                              level="neutral", sub="Calcule sur les alertes deja fermees"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Alertes ouvertes par gravite**")
            open_alerts = [a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"]
            if open_alerts:
                sev_counts = pd.Series([a["Menace"] for a in open_alerts]).value_counts()
                fig, ax = plt.subplots(figsize=(6, 3.5))
                colors_map = {"Scan de Ports / Reconnaissance": CLASS_COLORS[1],
                              "Attaque DDoS / Volumetrique": CLASS_COLORS[2],
                              "Infiltration / Brute-Force / Exfiltration": CLASS_COLORS[3]}
                ax.bar(sev_counts.index, sev_counts.values,
                       color=[colors_map.get(i, TEAL) for i in sev_counts.index])
                ax.set_ylabel("Nombre d'alertes ouvertes")
                plt.xticks(rotation=20, ha="right", fontsize=8)
                style_dark_fig(fig, ax)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
            else:
                st.info("Aucune alerte ouverte actuellement.")
        with c2:
            st.markdown("**Evolution du score de securite**")
            score_hist = org_state.get("score_history", [])
            if len(score_hist) >= 2:
                fig, ax = plt.subplots(figsize=(6, 3.5))
                ax.plot(range(len(score_hist)), [p["Score"] for p in score_hist], color=TEAL, marker="o", markersize=3)
                ax.set_ylim(0, 100)
                ax.set_ylabel("Score /100")
                ax.set_xlabel("Chargements successifs de cet onglet")
                style_dark_fig(fig, ax)
                fig.tight_layout()
                st.pyplot(fig)
                plt.close(fig)
            else:
                st.info("L'historique du score se construit au fil des visites de cet onglet.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Journal des alertes")
        st.write("Chaque connexion jugee suspecte par le systeme apparait ici, la plus recente en premier. "
                 "Marquez une alerte comme traitee une fois l'investigation terminee.")
        if len(alert_log) == 0:
            st.info("Aucune alerte enregistree pour l'instant. Analysez des flux dans les onglets precedents.")
        else:
            for alert in alert_log[:100]:
                is_open = alert.get("Statut", "Ouvert") == "Ouvert"
                icon = "🔴" if is_open else "🟢"
                cols = st.columns([1, 2, 2, 2, 1, 2])
                cols[0].markdown(f"{icon} **{alert.get('Statut', 'Ouvert')}**")
                cols[1].write(alert["Horodatage"])
                cols[2].write(alert["Source"])
                cols[3].write(alert["Menace"])
                cols[4].write(f"{alert['Confiance (%)']}%")
                btn_label = "Marquer traitee" if is_open else "Rouvrir"
                if cols[5].button(btn_label, key=f"toggle_{alert['ID']}"):
                    for a in org_state["alert_log"]:
                        if a["ID"] == alert["ID"]:
                            a["Statut"] = "Ferme" if is_open else "Ouvert"
                            a["Fermee_le"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_open else None
                    save_org_state(org_state)
                    st.rerun()

            df_alerts = pd.DataFrame(alert_log)
            csv_alerts = df_alerts.to_csv(index=False).encode("utf-8")
            c1, c2 = st.columns(2)
            c1.download_button("Telecharger le journal (CSV)", csv_alerts, "journal_alertes.csv", "text/csv")
            if c2.button("Vider le journal"):
                save_org_state({"alert_log": [], "score_history": org_state.get("score_history", [])})
                st.rerun()


# ==================================================================
# Vue : Espace Grand Public (2 onglets : Assistant + Sensibilisation)
# ==================================================================
def render_public_view():
    if st.button("← Retour a l'accueil", key="back_pub"):
        st.session_state.view = "landing"
        st.rerun()

    tab_assistant, tab_awareness = st.tabs(["🎖️ Lieutenant Cyber", "🎮 Sensibilisation"])

    # ---------------------------------------------------------------- Tab : Assistant conversationnel/vocal
    with tab_assistant:
        st.subheader("🎖️ Lieutenant Cyber - l'IA de Kimatey FinNet Guard")
        st.write(
            "Posez une question en langage courant sur une alerte, une menace, ou un message suspect "
            "recu par mobile money - a l'ecrit ou a l'oral. Cet assistant explique et sensibilise ; "
            "il ne remplace pas la detection automatique du tableau de bord."
        )

        if not GENAI_AVAILABLE:
            st.error(
                "Le module 'google-genai' n'est pas installe. Lancez : "
                "pip install google-genai"
            )
        else:
            api_key = get_gemini_key()
            if not api_key:
                st.info(
                    "Aucune cle API Gemini detectee. Pour un usage normal, definissez la variable "
                    "d'environnement GEMINI_API_KEY avant de lancer Streamlit. Pour un test rapide "
                    "en local uniquement, vous pouvez la coller ci-dessous (elle n'est pas sauvegardee "
                    "sur disque et disparait a la fermeture de l'application)."
                )
                manual_key = st.text_input(
                    "Cle API Gemini (test local uniquement)", type="password", key="gemini_key_input_field"
                )
                if manual_key:
                    st.session_state["gemini_api_key_manual"] = manual_key
                    st.rerun()
            else:
                client = genai.Client(api_key=api_key)

                if "chat_messages" not in st.session_state:
                    st.session_state.chat_messages = []

                for msg in st.session_state.chat_messages:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])

                audio_value = None
                if hasattr(st, "audio_input"):
                    audio_value = st.audio_input("🎤 Ou posez votre question a l'oral")
                else:
                    st.caption(
                        "Astuce : mettez a jour Streamlit (pip install -U streamlit) pour activer "
                        "la question posee a l'oral (st.audio_input)."
                    )

                user_text = st.chat_input("Ecrivez votre question ici...")

                new_question = None
                request_contents = None
                if user_text:
                    new_question = user_text
                    request_contents = user_text
                elif audio_value is not None and audio_value != st.session_state.get("_last_audio_processed"):
                    st.session_state["_last_audio_processed"] = audio_value
                    new_question = "(question posee a l'oral)"
                    audio_part = genai_types.Part.from_bytes(data=audio_value.getvalue(), mime_type="audio/wav")
                    request_contents = [
                        "Voici une question posee a l'oral par l'utilisateur : transcris-la mentalement "
                        "puis reponds-y directement, dans la meme langue que l'audio.",
                        audio_part,
                    ]

                if new_question:
                    st.session_state.chat_messages.append({"role": "user", "content": new_question})
                    with st.chat_message("user"):
                        st.write(new_question)

                    with st.spinner("Lieutenant Cyber reflechit..."):
                        answer = ask_gemini(client, request_contents, cache=st.session_state)

                    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                    with st.chat_message("assistant"):
                        st.write(answer)

                    # Lecture a voix haute cote navigateur (synthese vocale, gratuite, sans cle API).
                    safe_answer = (
                        answer.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
                    )
                    st.components.v1.html(
                        f"""<script>
                        try {{
                            const utter = new SpeechSynthesisUtterance("{safe_answer}");
                            utter.lang = "fr-FR";
                            window.speechSynthesis.cancel();
                            window.speechSynthesis.speak(utter);
                        }} catch (e) {{ console.warn("Synthese vocale indisponible :", e); }}
                        </script>""",
                        height=0,
                    )

                if st.session_state.chat_messages and st.button("Effacer la conversation"):
                    st.session_state.chat_messages = []
                    st.rerun()

    # ---------------------------------------------------------------- Tab : Sensibilisation ludique + collecte
    with tab_awareness:
        st.subheader("🎮 Sensibilisation ludique & vigilance collective")
        st.write(
            "Deux facons de participer : tester vos reflexes face a des situations reelles, "
            "et aider a reperer de nouvelles techniques d'arnaque - sans jamais partager d'information "
            "personnelle."
        )

        st.markdown("### 🧠 Jeu de vigilance : sauriez-vous reperer le piege ?")
        st.caption(
            "Mecanique de gamification - niveaux, Points Bouclier, vies, mascottes et categories "
            "thematiques - adaptee a la fraude mobile money. **Difference assumee "
            "et volontaire : les Points Bouclier n'ont ici aucune valeur monetaire ni conversion en argent "
            "reel.** Dans une application qui lutte contre la fraude financiere, une fausse 'monnaie' qui se "
            "convertit en valeur reelle aurait envoye le mauvais signal - c'est un indicateur de progression "
            "et de vigilance, point. Progression valable pour cette session de demonstration : pas encore "
            "de compte persistant (voir feuille de route)."
        )

        # ---- Etat de jeu (session-only : voir remarque ci-dessus) ----------------------------------
        if "game_xp" not in st.session_state:
            st.session_state.game_xp = 0
        if "game_hearts" not in st.session_state:
            st.session_state.game_hearts = MAX_HEARTS
        if "game_category" not in st.session_state:
            st.session_state.game_category = GAME_CATEGORIES[0]["key"]
        if "game_quiz_index" not in st.session_state:
            st.session_state.game_quiz_index = {}
        if "game_badges_seen" not in st.session_state:
            st.session_state.game_badges_seen = set()

        categories_by_key = {c["key"]: c for c in GAME_CATEGORIES}

        # Placeholder reserve ici pour la carte de progression (Niveau / Points Bouclier / Vies /
        # Badges), mais REMPLI plus bas, une fois que la reponse au scenario de ce run (le cas
        # echeant) a ete traitee. Streamlit execute le script de haut en bas en un seul passage : si
        # on calculait cette carte ici, elle afficherait encore l'ancienne valeur de game_xp au moment
        # meme ou l'utilisateur voit le message "Bien joue, +15 Points Bouclier" plus bas - donc un
        # decalage d'un tour visible et deroutant. st.empty() garde la position visuelle en haut tout
        # en recevant son contenu final calcule apres les mutations d'etat de ce meme run, sans avoir
        # besoin d'un st.rerun() qui effacerait le message de feedback.
        header_placeholder = st.empty()

        # ---- Selection de categorie (tabs thematiques) ---------------------
        cat_labels = [f"{c['emoji']} {c['label']}" for c in GAME_CATEGORIES]
        cat_keys = [c["key"] for c in GAME_CATEGORIES]
        current_cat_idx = cat_keys.index(st.session_state.game_category) if st.session_state.game_category in cat_keys else 0
        chosen_label = st.radio("Choisissez une categorie :", cat_labels, index=current_cat_idx,
                                 horizontal=True, key="game_category_radio")
        st.session_state.game_category = cat_keys[cat_labels.index(chosen_label)]
        cat = categories_by_key[st.session_state.game_category]
        mascot = GAME_MASCOTS[cat["mascot_key"]]

        age_band = st.selectbox(
            "Votre tranche d'age (adapte simplement le ton de la mascotte)",
            ["🧒 Ado (13-17 ans)", "🧑 Adulte (18 ans et plus)"], index=1, key="game_age_band",
        )

        with st.chat_message("assistant"):
            st.write(f"**{mascot['name']}** : {mascot['intro']}")
            if age_band.startswith("🧒"):
                st.caption("Astuce pour les ados : si un adulte vous pousse a agir vite ou a garder un "
                           "secret pour de l'argent, parlez-en toujours a un parent ou une personne de "
                           "confiance avant.")

        scenarios = cat["scenarios"]
        idx = st.session_state.game_quiz_index.get(cat["key"], 0) % len(scenarios)
        scenario = scenarios[idx]
        st.info(scenario["situation"])

        if st.session_state.game_hearts <= 0:
            st.warning("🛡️ Plus de vies pour l'instant sur cette session.")
            if st.button("🔁 Recharger mes vies", use_container_width=True):
                st.session_state.game_hearts = MAX_HEARTS
                st.rerun()
        else:
            choice = st.radio("Que faites-vous ?", scenario["choices"], index=None,
                               key=f"quiz_choice_{cat['key']}_{idx}")

            colq1, colq2 = st.columns([1, 1])
            valider = colq1.button("Valider ma reponse", type="primary", disabled=choice is None,
                                    use_container_width=True)
            suivant = colq2.button("Scenario suivant ➡️", use_container_width=True)

            if valider:
                if scenario["choices"].index(choice) == scenario["correct"]:
                    st.session_state.game_xp += XP_PER_CORRECT
                    st.success(f"✅ Bien joue ! +{XP_PER_CORRECT} 🛡️ Points Bouclier. {scenario['explanation']}")
                else:
                    st.session_state.game_hearts = max(0, st.session_state.game_hearts - 1)
                    st.session_state.game_xp += XP_PER_INCORRECT
                    st.error(f"⚠️ Pas tout a fait (-1 ❤️, +{XP_PER_INCORRECT} 🛡️ quand meme, pour avoir "
                             f"essaye). {scenario['explanation']}")
                if scenario.get("tip"):
                    st.info(f"💡 {scenario['tip']}")

                newly_unlocked = [b for b in compute_unlocked_badges(st.session_state.game_xp)
                                   if b["key"] not in st.session_state.game_badges_seen]
                for b in newly_unlocked:
                    st.session_state.game_badges_seen.add(b["key"])
                    st.success(f"🎉 Nouveau badge debloque : {b['emoji']} {b['label']} - {b['desc']}")

            if suivant:
                st.session_state.game_quiz_index[cat["key"]] = idx + 1
                st.rerun()

        with st.expander(f"🏅 Mes badges ({len(compute_unlocked_badges(st.session_state.game_xp))}/{len(BADGES)})"):
            unlocked_keys = {b["key"] for b in compute_unlocked_badges(st.session_state.game_xp)}
            for b in BADGES:
                if b["key"] in unlocked_keys:
                    st.markdown(f"✅ {b['emoji']} **{b['label']}** - {b['desc']}")
                else:
                    st.markdown(f"🔒 {b['emoji']} {b['label']} *(a {b['xp_required']} Points Bouclier)* - {b['desc']}")

        # ---- Rendu final de la carte de progression, dans le placeholder cree plus haut -------------
        level_info = compute_level(st.session_state.game_xp)
        with header_placeholder.container():
            card_cols = st.columns([2, 1, 1])
            with card_cols[0]:
                next_txt = (f" (prochain niveau a {level_info['next_threshold']} 🛡️)"
                            if level_info["next_threshold"] else " - niveau maximal !")
                st.markdown(
                    kpi_card("🛡️", "Niveau", f"{level_info['title']}",
                             sub=f"{st.session_state.game_xp} Points Bouclier{next_txt}", level="good"),
                    unsafe_allow_html=True,
                )
            with card_cols[1]:
                hearts_display = "❤️ " * st.session_state.game_hearts + "🖤 " * (MAX_HEARTS - st.session_state.game_hearts)
                st.markdown(kpi_card("💗", "Vies", hearts_display.strip() or "Aucune",
                                      level="good" if st.session_state.game_hearts > 0 else "threat"),
                            unsafe_allow_html=True)
            with card_cols[2]:
                unlocked_now = compute_unlocked_badges(st.session_state.game_xp)
                st.markdown(kpi_card("🏅", "Badges", f"{len(unlocked_now)} / {len(BADGES)}", level="good"),
                            unsafe_allow_html=True)
            st.progress(level_info["progress_ratio"])

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🤝 Racontez a Lieutenant Cyber ce qui vous est arrive")
        st.write(
            "Pas de formulaire a remplir : discutez-en avec Lieutenant Cyber, comme vous le feriez avec un ami. "
            "Aucune information personnelle n'est demandee - seule la technique utilisee par l'escroc nous "
            "interesse, pour enrichir a terme nos modeles de detection."
        )

        if not GENAI_AVAILABLE:
            st.warning(
                "Le module 'google-genai' n'est pas installe : la synthese automatique du temoignage n'est "
                "pas disponible, mais l'echange ci-dessous reste utilisable et votre contribution est enregistree."
            )

        if "community_reports" not in st.session_state:
            st.session_state.community_reports = []
        if "report_step" not in st.session_state:
            st.session_state.report_step = 0
        if "report_answers" not in st.session_state:
            st.session_state.report_answers = {}
        if "report_done" not in st.session_state:
            st.session_state.report_done = False
        if "report_celebrated" not in st.session_state:
            st.session_state.report_celebrated = False

        # REPORT_STEPS est importe depuis core.kimatey_core (partage avec l'API).

        with st.chat_message("assistant"):
            st.write("👋 Racontez-moi ce qui s'est passé, comme si vous en parliez à un ami - je ne vous "
                      "demanderai jamais votre nom, votre numéro ou un montant précis.")

        for step in REPORT_STEPS[: min(st.session_state.report_step, len(REPORT_STEPS))]:
            with st.chat_message("assistant"):
                st.write(step["question"])
            with st.chat_message("user"):
                st.write(st.session_state.report_answers.get(step["key"], ""))

        if st.session_state.report_step < len(REPORT_STEPS) and not st.session_state.report_done:
            current = REPORT_STEPS[st.session_state.report_step]
            with st.chat_message("assistant"):
                st.write(current["question"])
            cols = st.columns(len(current["options"]))
            for i, opt in enumerate(current["options"]):
                if cols[i].button(opt, key=f"report_opt_{st.session_state.report_step}_{i}", use_container_width=True):
                    st.session_state.report_answers[current["key"]] = opt
                    st.session_state.report_step += 1
                    st.rerun()

        elif not st.session_state.report_done:
            with st.chat_message("assistant"):
                st.write(
                    "Merci ! Un dernier detail a ajouter, a l'ecrit ou a l'oral ? C'est facultatif - et toujours "
                    "sans nom, numero ni montant."
                )
            recit = st.text_input("Votre message (facultatif)", key="report_recit_text", label_visibility="collapsed",
                                   placeholder="Ecrivez ici si vous voulez ajouter un detail...")
            audio_report = None
            if hasattr(st, "audio_input"):
                audio_report = st.audio_input("🎙️ Ou racontez a l'oral (facultatif)")
            colf1, colf2 = st.columns(2)
            envoyer = colf1.button("Envoyer ma contribution 🎉", type="primary", use_container_width=True)
            passer = colf2.button("Terminer sans detail", use_container_width=True)

            if envoyer or passer:
                canal = st.session_state.report_answers.get("canal", "non precise")
                demande = st.session_state.report_answers.get("demande", "non precise")
                reaction = st.session_state.report_answers.get("reaction", "non precise")
                fiche = f"Canal : {canal} - Demande : {demande} - Reaction : {reaction}."
                api_key = get_gemini_key()
                if envoyer and GENAI_AVAILABLE and api_key and (recit.strip() or audio_report is not None):
                    client = genai.Client(api_key=api_key)
                    contents = []
                    if recit.strip():
                        contents.append(recit.strip())
                    if audio_report is not None:
                        contents.append(genai_types.Part.from_bytes(data=audio_report.getvalue(), mime_type="audio/wav"))
                    with st.spinner("Lieutenant Cyber met tout ça en forme..."):
                        synth = ask_gemini(client, contents, system_instruction=ANONYMIZE_SYSTEM_PROMPT, cache=st.session_state)
                    fiche = f"{fiche} {synth}"

                st.session_state.community_reports.insert(0, {
                    "Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Fiche anonymisee": fiche,
                })
                st.session_state.report_done = True
                st.rerun()

        else:
            with st.chat_message("assistant"):
                st.write(
                    "🎉 Merci beaucoup ! Vous êtes la "
                    f"{len(st.session_state.community_reports)}e personne à nous aider aujourd'hui à mieux "
                    "repérer ce genre de piège."
                )
            if not st.session_state.report_celebrated:
                st.balloons()
                st.session_state.report_celebrated = True
            if st.button("Partager une autre experience"):
                st.session_state.report_step = 0
                st.session_state.report_answers = {}
                st.session_state.report_done = False
                st.session_state.report_celebrated = False
                st.rerun()

        if st.session_state.community_reports:
            with st.expander(f"📋 Fiches collectees dans cette session ({len(st.session_state.community_reports)})"):
                st.caption(
                    "Stockage local a cette session de demonstration uniquement - pas encore relie a une base "
                    "de donnees persistante ni a un pipeline de reentrainement du modele."
                )
                st.dataframe(pd.DataFrame(st.session_state.community_reports), use_container_width=True, hide_index=True)


# ==================================================================
# Dispatch principal
# ==================================================================
if st.session_state.view == "landing":
    render_landing()
elif st.session_state.view == "organisation":
    render_organisation_view()
else:
    render_public_view()

st.markdown("---")
st.caption("Interface developpee avec Streamlit - Realise par Komoe Edgar Junior - Responsable de l'enseignement : Dr ASSOHOUN E Stanislas - Projet ML Master 1 UFRMI")
