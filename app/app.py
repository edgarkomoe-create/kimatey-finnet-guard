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
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go

BASE_DIR = Path(__file__).resolve().parent.parent
# `streamlit run app/app.py` n'ajoute que le dossier app/ a sys.path (pas la racine
# du projet, contrairement a pytest via tests/conftest.py) : sans cette ligne,
# `from core.kimatey_core import ...` echoue avec ModuleNotFoundError des que
# l'application est lancee depuis un autre repertoire de travail que la racine.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.kimatey_core import (
    GENAI_AVAILABLE, genai, genai_types, ask_gemini,
    ASSISTANT_SYSTEM_PROMPT, ANONYMIZE_SYSTEM_PROMPT, ORG_ANALYST_SYSTEM_PROMPT, ORG_EXECUTIVE_SYSTEM_PROMPT,
    ACADEMIC_INSTRUCTOR_SYSTEM_PROMPT,
    SCENARIOS, REPORT_STEPS,
    GAME_CATEGORIES, GAME_MASCOTS, BADGES, XP_PER_CORRECT, XP_PER_INCORRECT, MAX_HEARTS,
    compute_level, compute_unlocked_badges,
)
# Reutilise directement le module d'authentification de l'API (meme code, meme
# variable AUTH_MODE, meme fichier api/users.json) : pas d'appel HTTP necessaire
# puisque Streamlit et l'API partagent deja le meme processus Python / la meme
# base de code (voir core/kimatey_core.py), donc pas de risque de divergence
# entre "qui peut se connecter sur l'API" et "qui peut se connecter dans l'appli".
from api.auth import register_user, verify_user_credentials, create_token, EmailDejaUtilise
from api.transaction_model_service import get_transaction_model_service
from core.sensitivity import get_threshold, set_threshold
from core.enriched_model import get_enriched_model_status, generate_enriched_model

OUT_DIR = BASE_DIR / "outputs"
MODEL_DIR = OUT_DIR / "models"
OUT_DIR_TX = OUT_DIR / "transaction_fraud"
DATA_DIR = BASE_DIR / "data"

FEATURES = joblib.load(MODEL_DIR / "feature_names.joblib")
MEDIANS = joblib.load(MODEL_DIR / "imputation_medians.joblib")
IQR_BOUNDS = joblib.load(MODEL_DIR / "iqr_bounds.joblib")
SCALER = joblib.load(MODEL_DIR / "scaler.joblib")
BEST_MODEL = joblib.load(MODEL_DIR / "best_model.joblib")

with open(OUT_DIR / "best_model_info.json") as f:
    BEST_MODEL_INFO = json.load(f)
SELECTED_FEATURES = BEST_MODEL_INFO["features_used"]

# ------------------------------------------------------------------------
# Detection adaptative de colonnes enrichies (optionnelles, hors schema ML) :
# horodatage, pays, IP source, departement, appareil. Chaque institution
# nomme ses colonnes differemment - on reconnait plusieurs alias courants
# plutot que d'exiger un nom exact. AUCUNE colonne n'est jamais inventee ou
# imputee : si une dimension est absente du fichier importe, la visualisation
# correspondante indique honnetement "aucune donnee disponible" plutot que de
# fabriquer une valeur. C'est le "Niveau 2 : couche de mapping de colonnes"
# de la feuille de route "faire fonctionner le modele avec le fichier de
# n'importe quelle institution", applique ici a l'enrichissement du dashboard
# (pas aux 9 variables du modele ML, qui restent strictes).
ENRICHMENT_ALIASES = {
    "timestamp": ["Horodatage", "Timestamp", "Date", "DateTime", "Date_Heure"],
    "pays": ["Pays", "Country", "Pays_Source", "Country_Source"],
    "ip": ["IP_Source", "Source_IP", "IP", "Adresse_IP"],
    "departement": ["Departement", "Department", "Service"],
    "appareil": ["Appareil", "Device", "Type_Appareil"],
}


def detect_enrichment_columns(df):
    """Retourne {dimension: nom_de_colonne_reel} pour chaque dimension enrichie
    detectee dans df, en acceptant plusieurs alias courants par dimension."""
    found = {}
    cols_lower = {c.lower(): c for c in df.columns}
    for dim, aliases in ENRICHMENT_ALIASES.items():
        for alias in aliases:
            if alias.lower() in cols_lower:
                found[dim] = cols_lower[alias.lower()]
                break
    return found

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
    st.session_state.view = _query_view if _query_view in ("organisation", "public", "academic") else "landing"
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


def plotly_dark_layout(fig, title=None, height=340):
    """Applique le theme sombre navy/teal a une figure Plotly (equivalent
    interactif de style_dark_fig pour matplotlib) : survol, zoom, panoramique
    fonctionnent nativement, contrairement a une image matplotlib statique."""
    fig.update_layout(
        paper_bgcolor=NAVY_LIGHT, plot_bgcolor=NAVY_LIGHT,
        font=dict(color=TEXT_LIGHT, size=12),
        title=dict(text=title, font=dict(color=TEXT_LIGHT, size=13)) if title else None,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        height=height,
        legend=dict(bgcolor=NAVY_MID, bordercolor=GRID_COLOR, borderwidth=1, font=dict(color=TEXT_LIGHT, size=10)),
        hoverlabel=dict(bgcolor=NAVY_MID, font_color=TEXT_LIGHT, bordercolor=TEAL),
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=TEXT_LIGHT, tickfont=dict(size=10))
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR, color=TEXT_LIGHT, tickfont=dict(size=10))
    return fig


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


# ------------------------------------------------------------------------
# Journal d'alertes et score de securite : logique partagee avec l'API (voir
# core/alert_log.py), pour que Streamlit et une future page web du dashboard
# SOC restent toujours synchronises sur le meme fichier de donnees.
# ------------------------------------------------------------------------
from core.alert_log import (
    load_org_state, save_org_state, log_alert as _log_alert_shared, log_alerts_bulk,
    compute_security_score, record_score_snapshot, mttr_hours, trend_delta_pct, toggle_alert_status,
)


def log_alert(source_label, pred_class, confidence, details="", domaine="reseau", class_names=None):
    _log_alert_shared(source_label, pred_class, confidence, details, domaine=domaine, class_names=class_names)


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
    col1, col2, col3 = st.columns(3)
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
        # L'Espace Grand Public est desormais maintenu uniquement sur la version web
        # independante (Vercel) - plus complete et a jour (lecons visuelles, analyse
        # d'image, fil de tendances, Pass, reconnaissance vocale). Redirection plutot
        # que de maintenir deux versions divergentes de la meme experience.
        st.link_button("Entrer dans l'Espace Grand Public →", "https://kimatey-finnet-guard.vercel.app/public.html",
                        type="primary", use_container_width=True)
    with col3:
        st.markdown(
            '<div class="landing-card"><h3>🎓 Espace Academique</h3>'
            "<p>Cas d'etude pedagogique (machine learning applique a la cybersecurite reseau) : "
            "explications, Professeur Cyber en Q&A, mini-quiz, import de jeu de donnees. Libre "
            "d'acces, aucun compte requis - pour enseignants et etudiants.</p></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Entrer dans l'Espace Academique →", type="primary", use_container_width=True, key="landing_academic"):
            st.session_state.view = "academic"
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

    # ------------------------------------------------------------------------
    # Deux produits distincts sous un meme compte Organisation : la detection
    # reseau (technologie validee) et la fraude transactionnelle (prototype).
    # Design pense pour deux publics : un choix visuel clair pour un decideur
    # non-technique (icone + une phrase), un badge de maturite pour une equipe
    # technique qui veut savoir tout de suite ce qui est valide vs prototype.
    # ------------------------------------------------------------------------
    if "org_module" not in st.session_state:
        st.session_state.org_module = None

    if st.session_state.org_module is None:
        st.markdown("### Que voulez-vous analyser aujourd'hui ?")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                '<div style="background:var(--navy-light,rgba(255,255,255,.04));border:1px solid rgba(0,212,181,.3);'
                'border-radius:14px;padding:1.4rem;">'
                '<div style="font-size:2rem;margin-bottom:.4rem;">🌐</div>'
                '<h4 style="margin:0 0 .4rem 0;">Securite Reseau</h4>'
                '<p style="color:var(--text-muted,#9fb3d1);font-size:.9rem;">Detecte les attaques sur votre '
                'infrastructure (scan, DDoS, infiltration) a partir de vos flux reseau.</p>'
                '<span style="color:#22c55e;font-size:.82rem;font-weight:600;">✅ Technologie validee (99% exactitude)</span>'
                '</div>', unsafe_allow_html=True,
            )
            if st.button("Ouvrir Securite Reseau →", key="choose_reseau", type="primary", use_container_width=True):
                st.session_state.org_module = "reseau"
                st.rerun()
        with c2:
            st.markdown(
                '<div style="background:var(--navy-light,rgba(255,255,255,.04));border:1px solid rgba(245,165,36,.3);'
                'border-radius:14px;padding:1.4rem;">'
                '<div style="font-size:2rem;margin-bottom:.4rem;">💰</div>'
                '<h4 style="margin:0 0 .4rem 0;">Fraude Transactionnelle</h4>'
                '<p style="color:var(--text-muted,#9fb3d1);font-size:.9rem;">Evalue si une transaction mobile '
                'money ressemble a un comportement frauduleux (montant, frequence, destinataire).</p>'
                '<span style="color:#f5a524;font-size:.82rem;font-weight:600;">🧪 Prototype (donnees synthetiques)</span>'
                '</div>', unsafe_allow_html=True,
            )
            if st.button("Ouvrir Fraude Transactionnelle →", key="choose_transactions", use_container_width=True):
                st.session_state.org_module = "transactions"
                st.rerun()
        return

    if st.button("← Changer de module", key="back_module"):
        st.session_state.org_module = None
        st.rerun()

    if st.session_state.org_module == "reseau":
        render_reseau_module()
    else:
        render_transactions_module()


def render_reseau_module():
    tab_simple, tab_dashboard, tab_import, tab_predict, tab_live, tab_alerts, tab_viz = st.tabs(
        ["👔 Resume simple", "📊 Tableau de bord", "📁 Analyser un fichier de logs", "🔎 Verifier un flux unique",
         "🔴 Surveillance en direct", "🚨 Alertes detectees", "📈 Visualisation"]
    )

    # ---------------------------------------------------------------- Tab 0 : Resume simple (non-technique)
    # Destine a un decideur/manager, pas a une equipe technique : jamais de metrique de
    # modele (accuracy/F1/AUC/matrice de confusion), jamais de jargon ML. Uniquement le
    # sens pour l'activite - statut visuel, phrase claire, action recommandee. S'appuie
    # sur les memes donnees deja calculees (etat operationnel, journal d'alertes) que le
    # dashboard professionnel - aucune duplication de calcul, seulement une autre lecture.
    with tab_simple:
        org_state_simple = load_org_state()
        alert_log_simple = org_state_simple.get("alert_log", [])
        score_simple = compute_security_score(alert_log_simple)
        n_open_simple = len([a for a in alert_log_simple if a.get("Statut", "Ouvert") == "Ouvert"])

        PLAIN_LANGUAGE = {
            "Scan de Ports / Reconnaissance": "une exploration suspecte de votre reseau",
            "Attaque DDoS / Volumetrique": "une tentative de surcharge de votre systeme",
            "Infiltration / Brute-Force / Exfiltration": "une tentative d'intrusion grave",
        }

        if score_simple >= 70:
            banner_color, banner_bg = GREEN, "rgba(34,197,94,0.12)"
            banner_text = "🟢 Votre reseau est actuellement bien protege"
        elif score_simple >= 40:
            banner_color, banner_bg = "#f5a524", "rgba(245,165,36,0.12)"
            banner_text = "🟠 Une vigilance accrue est recommandee"
        else:
            banner_color, banner_bg = RED, "rgba(231,76,60,0.12)"
            banner_text = "🔴 Une attention immediate est necessaire"

        st.markdown(
            f'<div style="background:{banner_bg};border-left:5px solid {banner_color};'
            f'border-radius:10px;padding:1.4rem 1.6rem;margin-bottom:1.2rem;">'
            f'<div style="font-size:1.3rem;font-weight:700;color:{banner_color};">{banner_text}</div>'
            f'</div>', unsafe_allow_html=True,
        )

        if not alert_log_simple:
            st.write("Aucune alerte enregistree pour le moment. Le systeme surveille en continu.")
        else:
            open_alerts_simple = [a for a in alert_log_simple if a.get("Statut", "Ouvert") == "Ouvert"]
            if open_alerts_simple:
                categories_presentes = {a["Menace"] for a in open_alerts_simple}
                phrases = [PLAIN_LANGUAGE.get(c, "une activite inhabituelle") for c in categories_presentes]
                st.write(
                    f"**{len(open_alerts_simple)} situation(s)** demande(nt) encore votre attention : "
                    + ", ".join(phrases) + "."
                )
            else:
                st.write("Toutes les alertes recentes ont ete traitees. Rien ne demande votre attention pour l'instant.")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Ce qu'il faut retenir**")
            if n_open_simple > 0:
                st.write(f"- {n_open_simple} situation(s) suspecte(s) sont encore ouvertes et non traitees.")
                st.write("- Il est recommande de transmettre ces cas a votre equipe technique pour verification.")
            else:
                st.write("- Aucune situation ouverte ne necessite d'action de votre part actuellement.")
            st.write(f"- Au total, {len(alert_log_simple)} evenement(s) ont ete detectes et suivis depuis le debut de la surveillance.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(
            "Cette vue simplifiee ne montre aucun detail technique. Votre equipe securite peut consulter "
            "le tableau de bord complet et le journal d'alertes pour l'analyse detaillee."
        )

        # ---- Avis IA optionnel : le resume ci-dessus est instantane (regles fixes,
        # toujours disponible). Ce bouton offre en plus un avis genere par Lieutenant
        # Cyber, plus nuance, pour qui veut une lecture complementaire. ----
        if GENAI_AVAILABLE and get_gemini_key():
            if st.button("🎖️ Demander un avis detaille a Lieutenant Cyber", key="lc_executive_summary"):
                client = genai.Client(api_key=get_gemini_key())
                categories_ouvertes = list({a["Menace"] for a in [x for x in alert_log_simple if x.get("Statut", "Ouvert") == "Ouvert"]}) if alert_log_simple else []
                content = (
                    f"Score de securite actuel : {score_simple}/100. {n_open_simple} situation(s) encore "
                    f"non traitee(s) sur {len(alert_log_simple)} au total. Categories concernees par les "
                    f"situations non traitees : {categories_ouvertes if categories_ouvertes else 'aucune'}."
                )
                with st.spinner("Lieutenant Cyber prepare son avis..."):
                    avis = ask_gemini(client, content, system_instruction=ORG_EXECUTIVE_SYSTEM_PROMPT, cache=st.session_state)
                st.session_state.lc_executive_avis = avis
            if st.session_state.get("lc_executive_avis"):
                with st.chat_message("assistant"):
                    st.write(f"**🎖️ Lieutenant Cyber** : {st.session_state.lc_executive_avis}")

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

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Comparaison de 5 techniques testees**")
            st.markdown('<p class="chart-hint">Plus la barre est haute, plus la technique classe correctement le trafic. '
                         'La technique retenue en production est l\'Arbre de Decision.</p>', unsafe_allow_html=True)
            if (OUT_DIR / "optimized_results.csv").exists():
                df_opt = pd.read_csv(OUT_DIR / "optimized_results.csv")
                st.dataframe(df_opt, use_container_width=True, hide_index=True)
                fig = go.Figure(data=[go.Bar(
                    x=df_opt["Modele"].str.replace("_optimise", ""), y=df_opt["Exactitude"],
                    marker_color=TEAL, text=(df_opt["Exactitude"] * 100).round(2).astype(str) + "%",
                    textposition="outside", textfont=dict(color=TEXT_LIGHT, size=10),
                )])
                fig.update_yaxes(title="Exactitude", range=[0.9, 1.0])
                plotly_dark_layout(fig, height=340)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
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
        st.caption(
            "🎓 Pour une exploration pedagogique approfondie (explications, Professeur Cyber, "
            "quiz, import de jeu de donnees), consultez l'Espace Academique depuis la page d'accueil."
        )

        st.markdown("---")
        st.subheader("🎛️ Personnalisation du modele (modele hybride)")
        st.caption(
            "Deux niveaux de personnalisation, sans jamais toucher au modele partage par les "
            "autres organisations : un reglage immediat (seuil de sensibilite), et un "
            "enrichissement optionnel a partir de vos propres donnees validees."
        )

        account_id = st.session_state.get("auth_email", "anonyme")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Seuil de sensibilite**")
            st.caption("Plus haut = detecte plus (plus de fausses alertes). Plus bas = moins d'alertes "
                       "(risque de rater des menaces subtiles). 0.5 = comportement standard.")
            current_threshold = get_threshold("reseau", account_id)
            new_threshold = st.slider("Seuil", min_value=0.05, max_value=0.95, value=float(current_threshold),
                                       step=0.05, key="sensitivity_slider")
            if st.button("Appliquer ce seuil"):
                set_threshold("reseau", account_id, new_threshold)
                st.success(f"Seuil de sensibilite mis a jour : {new_threshold}")
                st.rerun()

        with c2:
            st.markdown("**Modele enrichi pour votre organisation**")
            enriched_status = get_enriched_model_status(account_id)
            n_avail = enriched_status["n_org_samples_available"]
            n_required = enriched_status["min_required"]
            st.caption(f"Echantillons valides disponibles : {n_avail} / {n_required} requis.")
            st.progress(min(1.0, n_avail / n_required))

            if enriched_status["exists"]:
                st.write(
                    f"Dernier modele enrichi genere le {enriched_status['generated_at'][:10]} : "
                    f"exactitude {enriched_status['accuracy_enriched']*100:.1f}% "
                    f"(reference socle commun : {enriched_status['accuracy_base_reference']*100:.1f}%)"
                )
            if n_avail >= n_required:
                if st.button("🔧 Generer / regenerer mon modele enrichi"):
                    try:
                        generate_enriched_model(account_id)
                        st.success("Modele enrichi genere avec succes.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
            else:
                st.info("Continuez a valider des predictions (base d'apprentissage progressive) pour debloquer cette option.")

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
        st.caption(
            "Astuce : ajoutez des colonnes optionnelles Horodatage / Pays / Departement / Appareil "
            "a votre export pour debloquer automatiquement des vues supplementaires ci-dessous "
            "(chronologie, repartition geographique, filtres) - aucune n'est obligatoire."
        )
        demo_enrichi_path = OUT_DIR / "sample_logs_demo_enrichi.csv"
        if demo_enrichi_path.exists() and uploaded is None:
            if st.button("📎 Charger l'exemple enrichi (donnees synthetiques de demonstration)"):
                st.session_state["_use_demo_enrichi"] = True
                st.rerun()

        if st.session_state.get("_use_demo_enrichi") and uploaded is None:
            df_logs = pd.read_csv(demo_enrichi_path)
            st.info(
                "🧪 Exemple charge avec des colonnes Horodatage/Pays/Departement/Appareil "
                "**synthetiques**, generees uniquement pour illustrer le rendu de ces vues - "
                "ce ne sont pas de vraies donnees de production."
            )
        elif uploaded is not None:
            st.session_state.pop("_use_demo_enrichi", None)
            df_logs = pd.read_csv(uploaded)
        else:
            df_logs = None

        if df_logs is not None:
            st.write(f"**{len(df_logs)} connexions chargees.**")
            st.dataframe(df_logs.head(10), use_container_width=True)

            enrichment = detect_enrichment_columns(df_logs)
            if enrichment:
                st.success("Colonnes enrichies detectees : " + ", ".join(
                    f"{dim} ({col})" for dim, col in enrichment.items()
                ))

            # Filtres pre-analyse (uniquement si les dimensions correspondantes existent)
            df_filtered = df_logs
            filter_cols = st.columns(2)
            if "departement" in enrichment:
                options = sorted(df_logs[enrichment["departement"]].dropna().unique().tolist())
                selected = filter_cols[0].multiselect("Filtrer par departement", options, default=options)
                df_filtered = df_filtered[df_filtered[enrichment["departement"]].isin(selected)]
            if "appareil" in enrichment:
                options = sorted(df_logs[enrichment["appareil"]].dropna().unique().tolist())
                selected = filter_cols[1].multiselect("Filtrer par appareil", options, default=options)
                df_filtered = df_filtered[df_filtered[enrichment["appareil"]].isin(selected)]

            if st.button("Lancer l'analyse des flux", type="primary"):
                preds, confs, probas = predict_with_confidence(df_filtered)
                df_results = df_filtered.copy()
                df_results["Menace_Predite"] = [CLASS_NAMES[p] for p in preds]
                df_results["Confiance (%)"] = confs.round(1)

                n_threats = int((preds != 0).sum())
                rate = n_threats / len(df_filtered) * 100
                dist = pd.Series(preds).map(CLASS_NAMES).value_counts()

                # Resultat persiste en session_state (pas seulement local a ce bloc) : sinon, cliquer sur
                # le bouton "Demander a Lieutenant Cyber" plus bas (ou meme sur "Telecharger") declenche un
                # nouveau run de script ou "Lancer l'analyse des flux" redevient False, et toute cette
                # section disparaitrait - meme categorie de piste que le bug corrige sur la carte de
                # progression du jeu de vigilance (voir plus haut / README).
                st.session_state.last_batch_analysis = {
                    "n_flows": len(df_filtered), "n_threats": n_threats, "rate": rate,
                    "distribution": dist.to_dict(), "df_results": df_results,
                    "enrichment": enrichment,
                }
                st.session_state.pop("lc_batch_explanation", None)

                threat_indices = np.where(preds != 0)[0][:500]
                entries_to_log = [
                    {"source": f"Import CSV - ligne {i+1}", "pred_class": int(preds[i]), "confidence": float(confs[i])}
                    for i in threat_indices
                ]
                log_alerts_bulk(entries_to_log, domaine="reseau")
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
            fig = go.Figure(data=[go.Bar(
                x=dist.index, y=dist.values,
                marker_color=[CLASS_COLORS[c] for c in CLASSES if CLASS_NAMES[c] in dist.index],
            )])
            fig.update_yaxes(title="Nombre de flux")
            plotly_dark_layout(fig, height=320)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # ---- Vues adaptatives : uniquement si les colonnes correspondantes ont ete detectees ----
            enrichment = data.get("enrichment", {})
            threats_only = df_results[df_results["Menace_Predite"] != CLASS_NAMES[0]]

            ec1, ec2 = st.columns(2)
            with ec1:
                st.markdown("**Chronologie des menaces**")
                if "timestamp" in enrichment and len(threats_only) > 0:
                    ts_col = enrichment["timestamp"]
                    try:
                        dates = pd.to_datetime(threats_only[ts_col]).dt.date
                        daily = dates.value_counts().sort_index()
                        fig = go.Figure(data=[go.Scatter(
                            x=daily.index.astype(str), y=daily.values, mode="lines+markers",
                            line=dict(color=TEAL, width=2), marker=dict(size=7, color=TEAL),
                        )])
                        fig.update_yaxes(title="Menaces detectees")
                        plotly_dark_layout(fig, height=320)
                        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                    except (ValueError, TypeError):
                        st.info("Colonne d'horodatage detectee mais format illisible - chronologie indisponible.")
                else:
                    st.info(
                        "Aucune donnee d'horodatage disponible dans ce fichier. Ajoutez une colonne "
                        "Horodatage/Timestamp/Date pour activer cette vue."
                    )
            with ec2:
                st.markdown("**Repartition geographique des menaces**")
                if "pays" in enrichment and len(threats_only) > 0:
                    top_pays = threats_only[enrichment["pays"]].value_counts().head(8)
                    fig = go.Figure(data=[go.Bar(
                        x=top_pays.values[::-1], y=top_pays.index[::-1], orientation="h",
                        marker_color=CLASS_COLORS[2],
                    )])
                    fig.update_xaxes(title="Menaces detectees")
                    plotly_dark_layout(fig, height=320)
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                elif "ip" in enrichment:
                    st.info(
                        "Une colonne IP source est presente, mais la resolution geographique par IP "
                        "(GeoIP) n'est pas encore branchee sur ce prototype - ajoutez directement une "
                        "colonne Pays pour activer cette vue des maintenant."
                    )
                else:
                    st.info(
                        "Aucune donnee geographique disponible dans ce fichier. Ajoutez une colonne "
                        "Pays/Country pour activer cette vue."
                    )

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
            fig = go.Figure(data=[go.Bar(
                x=proba_df["Probabilite (%)"], y=proba_df["Classe"], orientation="h",
                marker_color=[CLASS_COLORS[c] for c in CLASSES],
                text=proba_df["Probabilite (%)"].astype(str) + "%", textposition="outside",
                textfont=dict(color=TEXT_LIGHT, size=10),
            )])
            fig.update_xaxes(title="Probabilite (%)")
            plotly_dark_layout(fig, height=280)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

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
            labels = [CLASS_NAMES[c].split(" / ")[0] for c in CLASSES]
            values = [st.session_state.live_dist.get(c, 0) for c in CLASSES]
            fig = go.Figure(data=[go.Bar(x=labels, y=values, marker_color=[CLASS_COLORS[c] for c in CLASSES])])
            fig.update_yaxes(title="Flux cumules")
            plotly_dark_layout(fig, height=300)
            chart_ph.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                                   key=f"live_chart_{st.session_state.live_stats['n']}")

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
        delta_pct, delta_text = trend_delta_pct(alert_log, days=7)
        trend_level = "neutral" if delta_pct is None else ("threat" if delta_pct > 0 else "good")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.markdown(kpi_card("🛡️", "Score de securite", f"{score}/100", level=score_level,
                              sub="Penalise selon volume et gravite des alertes encore ouvertes"), unsafe_allow_html=True)
        k2.markdown(kpi_card("🚨", "Alertes ouvertes", str(n_open), level=("threat" if n_open > 0 else "good"),
                              sub=f"{n_closed} deja traitees"), unsafe_allow_html=True)
        k3.markdown(kpi_card("✅", "Taux de traitement", f"{treated_rate}%", level="neutral",
                              sub="Part des alertes marquees comme fermees"), unsafe_allow_html=True)
        k4.markdown(kpi_card("⏱️", "Temps moyen de resolution", f"{mttr:.1f} h" if mttr is not None else "N/A",
                              level="neutral", sub="Calcule sur les alertes deja fermees"), unsafe_allow_html=True)
        k5.markdown(kpi_card("📈", "Tendance", delta_text if delta_pct is not None else "N/A",
                              level=trend_level, sub="Volume d'alertes, periode vs periode"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Alertes ouvertes par gravite**")
            open_alerts = [a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"]
            if open_alerts:
                sev_counts = pd.Series([a["Menace"] for a in open_alerts]).value_counts()
                colors_map = {"Scan de Ports / Reconnaissance": CLASS_COLORS[1],
                              "Attaque DDoS / Volumetrique": CLASS_COLORS[2],
                              "Infiltration / Brute-Force / Exfiltration": CLASS_COLORS[3]}
                fig = go.Figure(data=[go.Bar(
                    x=sev_counts.index, y=sev_counts.values,
                    marker_color=[colors_map.get(i, TEAL) for i in sev_counts.index],
                )])
                fig.update_yaxes(title="Nombre d'alertes ouvertes")
                plotly_dark_layout(fig, height=320)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Aucune alerte ouverte actuellement.")
        with c2:
            st.markdown("**Evolution du score de securite**")
            score_hist = org_state.get("score_history", [])
            if len(score_hist) >= 2:
                fig = go.Figure(data=[go.Scatter(
                    x=list(range(len(score_hist))), y=[p["Score"] for p in score_hist],
                    mode="lines+markers", line=dict(color=TEAL, width=2), marker=dict(size=6, color=TEAL),
                    fill="tozeroy", fillcolor="rgba(0,212,181,0.08)",
                )])
                fig.update_yaxes(title="Score /100", range=[0, 100])
                fig.update_xaxes(title="Chargements successifs de cet onglet")
                plotly_dark_layout(fig, height=320)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("L'historique du score se construit au fil des visites de cet onglet.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Alertes par jour et par gravite")
        st.write("Repartition quotidienne des alertes, ventilee par niveau de gravite - filtrable par periode.")

        if alert_log:
            df_alerts_all = pd.DataFrame(alert_log)
            df_alerts_all["Horodatage_dt"] = pd.to_datetime(df_alerts_all["Horodatage"])
            date_min = df_alerts_all["Horodatage_dt"].min().date()
            date_max = df_alerts_all["Horodatage_dt"].max().date()

            date_range = st.date_input(
                "Periode", value=(date_min, date_max), min_value=date_min, max_value=date_max,
                key="alert_date_range",
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range
            else:
                start_date, end_date = date_min, date_max

            mask = (df_alerts_all["Horodatage_dt"].dt.date >= start_date) & (df_alerts_all["Horodatage_dt"].dt.date <= end_date)
            df_filtered_alerts = df_alerts_all[mask]

            if df_filtered_alerts.empty:
                st.info("Aucune alerte sur cette periode.")
            else:
                df_filtered_alerts = df_filtered_alerts.copy()
                df_filtered_alerts["Jour"] = df_filtered_alerts["Horodatage_dt"].dt.date
                pivot = df_filtered_alerts.groupby(["Jour", "Menace"]).size().unstack(fill_value=0)

                colors_map = {"Scan de Ports / Reconnaissance": CLASS_COLORS[1],
                              "Attaque DDoS / Volumetrique": CLASS_COLORS[2],
                              "Infiltration / Brute-Force / Exfiltration": CLASS_COLORS[3]}
                fig = go.Figure()
                for menace in pivot.columns:
                    fig.add_trace(go.Scatter(
                        x=pivot.index.astype(str), y=pivot[menace], mode="lines+markers", name=menace,
                        line=dict(color=colors_map.get(menace, TEAL), width=2), marker=dict(size=6),
                    ))
                fig.update_yaxes(title="Nombre d'alertes")
                plotly_dark_layout(fig, height=380)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Aucune alerte enregistree pour l'instant.")

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

    # ---------------------------------------------------------------- Tab 7 : Visualisation (renvoi vers le web)
    with tab_viz:
        st.markdown("### 📈 Dashboard visuel anime")
        st.write(
            "Retrouvez ce meme tableau de bord (score, alertes, tendances) dans une version web "
            "**interactive et animee** (jauge circulaire, courbes Chart.js) - memes donnees, "
            "presentation plus riche. Connectez-vous avec le meme compte."
        )
        st.link_button("Ouvrir le Dashboard Visuel →", "https://kimatey-finnet-guard.vercel.app/dashboard.html",
                        type="primary", use_container_width=False)
        st.caption(
            "ℹ️ Cette version web anime couvre pour l'instant uniquement la Securite Reseau. "
            "Les modules Fraude Transactionnelle et Espace Academique restent consultables ici, "
            "sur Streamlit uniquement, pour le moment."
        )



# ==================================================================
# Espace Academique (Niveau 1 du systeme hybride) - INDEPENDANT, sans compte
# requis. Sert de cas d'etude pedagogique (machine learning applique a la
# cybersecurite reseau) pour enseignants et etudiants. Deplace hors de
# l'Espace Organisation : un etudiant qui veut reviser n'a pas a creer un
# compte "organisation" pour y acceder.
# ==================================================================
def render_academic_view():
    if st.button("← Retour a l'accueil", key="back_academic"):
        st.session_state.view = "landing"
        st.rerun()

    st.markdown("### 🎓 Espace Academique")
    st.caption(
        "Cas d'etude pedagogique : machine learning applique a la cybersecurite reseau. "
        "Libre d'acces, aucun compte requis - pour enseignants preparant un cours et "
        "etudiants qui revisent."
    )

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
    with st.expander("📖 Que signifient ces 4 indicateurs ? (cliquez pour deplier)"):
        st.markdown(
            "- **Exactitude (accuracy)** : proportion de predictions correctes sur l'ensemble de test. "
            "Attention : sur des classes desequilibrees (ici ~75% de trafic normal), une accuracy elevee "
            "peut masquer un modele qui predit toujours 'Normal' - c'est pourquoi on regarde aussi le F1.\n"
            "- **F1-score macro** : moyenne du F1-score (equilibre precision/rappel) calculee "
            "**separement pour chaque classe puis moyennee** - contrairement a une moyenne ponderee, "
            "chaque classe compte autant, meme la plus rare. C'est le bon choix ici puisque detecter "
            "les 25% de trafic malveillant compte autant que bien classer le trafic normal.\n"
            "- **AUC macro (Area Under Curve)** : mesure la capacite du modele a separer une classe "
            "des autres, quel que soit le seuil de decision choisi. Proche de 100% = tres bonne "
            "separation ; 50% = equivalent a un tirage au sort.\n"
            "- **Variables retenues (RFE)** : Recursive Feature Elimination a permis de reduire de 9 "
            "a 5 variables sans perte de performance - un exemple concret de selection de variables "
            "en reduisant la complexite du modele (plus facile a auditer, moins de risque de sur-apprentissage)."
        )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Comparaison de 5 techniques testees**")
        st.markdown('<p class="chart-hint">Plus la barre est haute, plus la technique classe correctement le trafic. '
                     'La technique retenue en production est l\'Arbre de Decision.</p>', unsafe_allow_html=True)
        if (OUT_DIR / "optimized_results.csv").exists():
            df_opt = pd.read_csv(OUT_DIR / "optimized_results.csv")
            st.dataframe(df_opt, use_container_width=True, hide_index=True)
            fig = go.Figure(data=[go.Bar(
                x=df_opt["Modele"].str.replace("_optimise", ""), y=df_opt["Exactitude"],
                marker_color=TEAL, text=(df_opt["Exactitude"] * 100).round(2).astype(str) + "%",
                textposition="outside", textfont=dict(color=TEXT_LIGHT, size=10),
            )])
            fig.update_yaxes(title="Exactitude", range=[0.9, 1.0])
            plotly_dark_layout(fig, height=340)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            with st.expander("📖 Pourquoi comparer 5 algorithmes plutot que d'en choisir un directement ?"):
                st.markdown(
                    "Chaque famille d'algorithme a des forces differentes : la Regression Logistique est "
                    "rapide et interpretable mais suppose des frontieres lineaires ; KNN capture des motifs "
                    "locaux mais est sensible au bruit ; Naive Bayes suppose l'independance des variables "
                    "(rarement vrai en pratique, mais souvent efficace quand meme) ; SVM gere bien les "
                    "frontieres complexes mais est plus lent a entrainer ; l'Arbre de Decision est "
                    "interpretable (on peut tracer chaque decision) et gere naturellement les interactions "
                    "entre variables. **Comparer plutot que supposer** est une regle de methodologie "
                    "scientifique de base : ici, tous obtiennent des scores tres proches (>98,9%), "
                    "l'Arbre de Decision a ete retenu pour son interpretabilite, pas juste sa performance brute."
                )
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

    st.markdown("---")
    st.subheader("🎓 Professeur Cyber - assistant pedagogique")
    st.caption(
        "Pour un enseignant preparant un cours, ou un etudiant qui revise : posez une question sur "
        "le machine learning, les statistiques ou la methodologie de ce projet, ou testez vos "
        "connaissances avec un mini-quiz."
    )
    mode_academique = st.radio(
        "Mode", ["💬 Poser une question", "📝 Mini-quiz", "🧪 Importer un jeu de donnees (cas d'etude)"],
        horizontal=True, key="academic_mode",
    )

    if mode_academique == "💬 Poser une question":
        if GENAI_AVAILABLE and get_gemini_key():
            question_academique = st.text_input(
                "Votre question", placeholder="Ex : Pourquoi utiliser le F1-score macro plutot que l'accuracy ?",
                key="academic_question_input",
            )
            if st.button("Demander au Professeur Cyber", key="ask_professeur"):
                if question_academique.strip():
                    client = genai.Client(api_key=get_gemini_key())
                    with st.spinner("Le Professeur Cyber reflechit..."):
                        reponse = ask_gemini(client, question_academique, system_instruction=ACADEMIC_INSTRUCTOR_SYSTEM_PROMPT, cache=st.session_state)
                    st.session_state.setdefault("academic_qa_history", []).append((question_academique, reponse))
            for q, r in reversed(st.session_state.get("academic_qa_history", [])[-5:]):
                with st.chat_message("user"):
                    st.write(q)
                with st.chat_message("assistant"):
                    st.write(f"**🎓 Professeur Cyber** : {r}")
        else:
            st.info("Le mode Q&A necessite une cle Gemini configuree (GEMINI_API_KEY).")

    elif mode_academique == "📝 Mini-quiz":
        QUIZ_ML = [
            {"q": "Pourquoi standardiser (scaler) les donnees uniquement sur le jeu d'entrainement ?",
             "options": ["Pour aller plus vite", "Pour eviter une fuite de donnees (data leakage)", "Ce n'est pas necessaire", "Pour reduire le nombre de variables"],
             "correct": 1,
             "explication": "Si on calcule la moyenne/ecart-type sur train+test, des informations du test 'fuient' dans l'entrainement, faussant l'evaluation."},
            {"q": "Sur un jeu de donnees a 75% de classe normale, pourquoi l'accuracy seule peut etre trompeuse ?",
             "options": ["Elle est toujours fausse", "Un modele qui predit toujours 'Normal' aurait deja 75% d'accuracy", "L'accuracy ne se calcule pas sur plusieurs classes", "Elle est plus lente a calculer"],
             "correct": 1,
             "explication": "Avec un fort desequilibre, un modele naïf (toujours la classe majoritaire) obtient une accuracy elevee sans rien detecter - d'ou l'interet du F1-score."},
            {"q": "Que mesure le F1-score macro par rapport au F1-score pondere (weighted) ?",
             "options": ["La meme chose", "Chaque classe compte autant, meme la plus rare", "Seulement la classe majoritaire", "La vitesse du modele"],
             "correct": 1,
             "explication": "Le macro-average moyenne les F1 par classe sans ponderer par leur frequence - important quand detecter la classe rare (menace) compte autant que la classe frequente."},
            {"q": "A quoi sert le GridSearchCV utilise dans ce projet ?",
             "options": ["A collecter plus de donnees", "A tester automatiquement plusieurs combinaisons d'hyperparametres avec validation croisee", "A visualiser les resultats", "A supprimer les valeurs manquantes"],
             "correct": 1,
             "explication": "GridSearchCV essaie systematiquement des combinaisons d'hyperparametres (ex: profondeur de l'arbre) et retient la meilleure selon une validation croisee, evitant un choix arbitraire."},
            {"q": "Pourquoi le modele final a-t-il ete reduit de 9 a 5 variables (RFE) ?",
             "options": ["Pour ameliorer legerement la performance", "Pour simplifier le modele sans perdre en performance, le rendant plus interpretable", "Parce que 4 variables etaient corrompues", "Ce n'etait pas volontaire"],
             "correct": 1,
             "explication": "La selection de variables (RFE) a identifie les 5 variables les plus informatives - un modele plus simple, aussi performant, est plus facile a auditer et moins sujet au sur-apprentissage."},
        ]
        if "quiz_ml_score" not in st.session_state:
            st.session_state.quiz_ml_score = 0
            st.session_state.quiz_ml_index = 0
            st.session_state.quiz_ml_answered = False

        idx_quiz = st.session_state.quiz_ml_index
        if idx_quiz < len(QUIZ_ML):
            question = QUIZ_ML[idx_quiz]
            st.write(f"**Question {idx_quiz + 1}/{len(QUIZ_ML)}** - Score actuel : {st.session_state.quiz_ml_score}/{len(QUIZ_ML)}")
            st.write(question["q"])
            choix = st.radio("Votre reponse", question["options"], key=f"quiz_choice_{idx_quiz}", index=None)
            if not st.session_state.quiz_ml_answered:
                if st.button("Valider", key=f"quiz_validate_{idx_quiz}"):
                    if choix is None:
                        st.warning("Choisissez une reponse avant de valider.")
                    else:
                        st.session_state.quiz_ml_answered = True
                        if question["options"].index(choix) == question["correct"]:
                            st.session_state.quiz_ml_score += 1
                        st.rerun()
            else:
                correct_option = question["options"][question["correct"]]
                if choix == correct_option:
                    st.success(f"✅ Correct ! {question['explication']}")
                else:
                    st.error(f"❌ Pas tout a fait. La bonne reponse etait : *{correct_option}*. {question['explication']}")
                if st.button("Question suivante", key=f"quiz_next_{idx_quiz}"):
                    st.session_state.quiz_ml_index += 1
                    st.session_state.quiz_ml_answered = False
                    st.rerun()
        else:
            st.success(f"🎉 Quiz termine ! Score final : {st.session_state.quiz_ml_score}/{len(QUIZ_ML)}")
            if st.button("Recommencer le quiz"):
                st.session_state.quiz_ml_score = 0
                st.session_state.quiz_ml_index = 0
                st.session_state.quiz_ml_answered = False
                st.rerun()

    else:  # Importer un jeu de donnees (cas d'etude)
        st.caption(
            "Outil generique d'exploration statistique (EDA), decouple du modele de fraude Kimatey : "
            "importez n'importe quel fichier CSV (donnees de cours, jeu de donnees public...) pour "
            "illustrer des concepts de statistique descriptive en cours ou en devoir."
        )
        uploaded_case_study = st.file_uploader("Fichier CSV du cas d'etude", type=["csv"], key="academic_case_study")
        if uploaded_case_study is not None:
            df_case = pd.read_csv(uploaded_case_study)
            st.write(f"**{len(df_case)} lignes, {len(df_case.columns)} colonnes.**")
            st.dataframe(df_case.head(10), use_container_width=True)
            numeric_cols = df_case.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                col_choisie = st.selectbox("Colonne numerique a explorer", numeric_cols, key="case_study_col")
                c1, c2 = st.columns(2)
                c1.markdown(kpi_card("📊", "Moyenne", f"{df_case[col_choisie].mean():.2f}", level="neutral"), unsafe_allow_html=True)
                c2.markdown(kpi_card("📐", "Ecart-type", f"{df_case[col_choisie].std():.2f}", level="neutral"), unsafe_allow_html=True)
                fig = go.Figure(data=[go.Histogram(
                    x=df_case[col_choisie].dropna(), nbinsx=30, marker_color=TEAL,
                )])
                fig.update_xaxes(title=col_choisie)
                fig.update_yaxes(title="Frequence")
                plotly_dark_layout(fig, height=340)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Aucune colonne numerique detectee dans ce fichier.")


# ==================================================================
# Module Fraude Transactionnelle (PROTOTYPE) - design a deux niveaux de
# lecture : un resume en langage simple d'abord (public non-technique), le
# detail technique range dans des expanders (public technique qui veut
# creuser). Meme logique que le module reseau, applique a un second produit.
# ==================================================================
def render_transactions_module():
    st.markdown("### 💰 Fraude Transactionnelle")
    st.caption("🧪 Module prototype - technologie validee, donnees d'entrainement synthetiques.")

    st.info(
        "**En langage simple :** ce module regarde une transaction mobile money (montant, "
        "heure, destinataire) et dit si elle ressemble a un comportement normal ou a une "
        "arnaque - un peu comme un agent qui remarque qu'un client habituel se comporte "
        "soudain differemment."
    )
    with st.expander("🔬 Detail technique (pour une equipe technique)"):
        st.write(
            "Meme methodologie que le modele reseau : arbre de decision optimise par "
            "GridSearchCV, entraine et evalue sur un jeu de test separe (80/20 stratifie). "
            "**Difference importante** : entraine sur des donnees synthetiques generees par "
            "regles (voir `src/transaction_fraud/generate_synthetic_data.py`), pas sur de "
            "vraies transactions - les metriques ci-dessous mesurent la coherence du pipeline, "
            "pas une performance en conditions reelles."
        )

    try:
        tx_service = get_transaction_model_service()
        tx_info = tx_service.info
        k1, k2, k3 = st.columns(3)
        k1.markdown(kpi_card("🎯", "Exactitude (test)", f"{tx_info['accuracy']*100:.1f}%", level="neutral",
                              sub="Mesuree sur donnees synthetiques"), unsafe_allow_html=True)
        k2.markdown(kpi_card("⚖️", "F1-score", f"{tx_info['f1_score']*100:.1f}%", level="neutral"), unsafe_allow_html=True)
        k3.markdown(kpi_card("📈", "AUC", f"{tx_info['auc']*100:.1f}%", level="neutral"), unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Etat operationnel (transactions)")
        tx_org_state = load_org_state(domaine="transactions")
        tx_alert_log = tx_org_state.get("alert_log", [])
        tx_score = compute_security_score(tx_alert_log)
        record_score_snapshot(tx_score, domaine="transactions")
        tx_n_open = len([a for a in tx_alert_log if a.get("Statut", "Ouvert") == "Ouvert"])
        tx_n_closed = len(tx_alert_log) - tx_n_open
        tx_treated_rate = round(100 * tx_n_closed / len(tx_alert_log)) if tx_alert_log else 0
        tx_score_level = "good" if tx_score >= 70 else ("warn" if tx_score >= 40 else "threat")

        tk1, tk2, tk3 = st.columns(3)
        tk1.markdown(kpi_card("🛡️", "Score de securite (transactions)", f"{tx_score}/100", level=tx_score_level,
                               sub="Penalise selon volume et gravite des transactions encore ouvertes"), unsafe_allow_html=True)
        tk2.markdown(kpi_card("🚨", "Transactions suspectes ouvertes", str(tx_n_open),
                               level=("threat" if tx_n_open > 0 else "good"),
                               sub=f"{tx_n_closed} deja traitees"), unsafe_allow_html=True)
        tk3.markdown(kpi_card("✅", "Taux de traitement", f"{tx_treated_rate}%", level="neutral"), unsafe_allow_html=True)

        if tx_alert_log:
            with st.expander("📋 Journal des transactions suspectes"):
                for alert in tx_alert_log[:50]:
                    is_open = alert.get("Statut", "Ouvert") == "Ouvert"
                    icon = "🔴" if is_open else "🟢"
                    cols = st.columns([1, 2, 2, 2, 1, 2])
                    cols[0].markdown(f"{icon} **{alert.get('Statut', 'Ouvert')}**")
                    cols[1].write(alert["Horodatage"])
                    cols[2].write(alert["Source"])
                    cols[3].write(alert["Menace"])
                    cols[4].write(f"{alert['Confiance (%)']}%")
                    btn_label = "Marquer traitee" if is_open else "Rouvrir"
                    if cols[5].button(btn_label, key=f"tx_toggle_{alert['ID']}"):
                        toggle_alert_status(alert["ID"], domaine="transactions")
                        st.rerun()

        st.markdown("---")
        st.subheader("Analyser un fichier de transactions (lot)")
        with st.expander("🔬 Colonnes techniques attendues dans le fichier"):
            st.write("Les colonnes manquantes seront remplacees par la valeur mediane observee a l'entrainement "
                     "(memes limites connues que le modele reseau - voir README).")
            st.code(", ".join(tx_service.features))

        demo_tx_path = OUT_DIR_TX / "transactions_synthetiques.csv"
        if demo_tx_path.exists():
            st.download_button(
                "📎 Telecharger un exemple de fichier synthetique",
                demo_tx_path.read_bytes(), "exemple_transactions_synthetiques.csv", "text/csv",
            )

        uploaded_tx = st.file_uploader("Choisir un fichier CSV de transactions", type=["csv"], key="tx_csv_uploader")
        if uploaded_tx is not None:
            df_tx_batch = pd.read_csv(uploaded_tx)
            st.write(f"**{len(df_tx_batch)} transactions chargees.**")
            st.dataframe(df_tx_batch.head(10), use_container_width=True)

            if st.button("Lancer l'analyse du lot", type="primary", key="tx_batch_analyze"):
                preds, confs, probas = tx_service.predict(df_tx_batch)
                from api.transaction_model_service import CLASS_NAMES as TX_CLASS_NAMES
                df_tx_results = df_tx_batch.copy()
                df_tx_results["Prediction"] = [TX_CLASS_NAMES[p] for p in preds]
                df_tx_results["Confiance (%)"] = confs.round(1)

                n_suspect = int((preds != 0).sum())
                rate_tx = n_suspect / len(df_tx_batch) * 100

                entries_to_log = [
                    {"source": f"Import CSV Transactions - ligne {i+1}", "pred_class": int(p), "confidence": float(confs[i])}
                    for i, p in enumerate(preds[:500])
                ]
                log_alerts_bulk(entries_to_log, domaine="transactions", class_names=TX_CLASS_NAMES)

                st.session_state.last_tx_batch = {
                    "n_total": len(df_tx_batch), "n_suspect": n_suspect, "rate": rate_tx,
                    "df_results": df_tx_results,
                }

        if "last_tx_batch" in st.session_state:
            tx_data = st.session_state.last_tx_batch
            lvl_tx = threat_level(tx_data["rate"])
            colA, colB, colC = st.columns(3)
            colA.markdown(kpi_card("📡", "Transactions verifiees", tx_data["n_total"], level="neutral"), unsafe_allow_html=True)
            colB.markdown(kpi_card("🚨", "Transactions suspectes", tx_data["n_suspect"], level=lvl_tx), unsafe_allow_html=True)
            colC.markdown(kpi_card("📊", "Part suspecte", f"{tx_data['rate']:.1f}%", level=lvl_tx), unsafe_allow_html=True)

            st.markdown("**Detail des transactions (top 200 affiches)**")
            st.dataframe(tx_data["df_results"].head(200), use_container_width=True)
            csv_tx_out = tx_data["df_results"].to_csv(index=False).encode("utf-8")
            st.download_button("Telecharger les resultats (CSV)", csv_tx_out, "resultats_transactions.csv", "text/csv")
            st.caption("⚠️ Rappel : evaluation par un modele prototype sur donnees synthetiques - "
                       "ne pas utiliser pour de vraies decisions.")

        st.markdown("---")
        st.subheader("Evaluer une transaction unique (formulaire)")
        with st.form("transaction_form"):
            c1, c2 = st.columns(2)
            with c1:
                montant = st.number_input("Montant (FCFA)", value=15000.0, min_value=0.0)
                ecart = st.number_input("Ecart vs montant habituel (1.0 = normal)", value=1.1, min_value=0.0)
                nouveau_dest = st.selectbox("Nouveau destinataire ?", ["Non", "Oui"])
                heure = st.slider("Heure de la transaction", 0, 23, 14)
            with c2:
                freq_24h = st.number_input("Transactions dans les dernieres 24h", value=2, min_value=0, step=1)
                delai = st.number_input("Minutes depuis la derniere transaction", value=300.0, min_value=0.0)
                nb_dest_7j = st.number_input("Destinataires distincts (7 derniers jours)", value=2, min_value=0, step=1)
                changement_appareil = st.selectbox("Changement d'appareil ?", ["Non", "Oui"])
            submitted_tx = st.form_submit_button("🔍 Evaluer la transaction", type="primary")

        if submitted_tx:
            df_tx = pd.DataFrame([{
                "Montant": montant, "Ecart_Montant_Habituel": ecart,
                "Nouveau_Destinataire": 1 if nouveau_dest == "Oui" else 0,
                "Heure_Transaction": heure, "Frequence_Transactions_24h": freq_24h,
                "Delai_Depuis_Derniere_Min": delai, "Nb_Destinataires_Distincts_7j": nb_dest_7j,
                "Changement_Appareil": 1 if changement_appareil == "Oui" else 0,
            }])
            preds, confs, _ = tx_service.predict(df_tx)
            from api.transaction_model_service import CLASS_NAMES as TX_CLASS_NAMES
            result_label = TX_CLASS_NAMES[int(preds[0])]
            color = RED if result_label == "Suspecte" else GREEN
            st.markdown(
                f'<div style="padding:1rem;border-radius:10px;background:{color}22;'
                f'border-left:4px solid {color};margin-top:1rem;">'
                f'<b style="color:{color}">{result_label}</b> - confiance {confs[0]:.1f}%'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption("⚠️ Rappel : evaluation par un modele prototype sur donnees synthetiques.")
    except FileNotFoundError:
        st.error(
            "Modele transactionnel non trouve. Executez `python src/transaction_fraud/train_pipeline.py` "
            "pour generer les artefacts."
        )


# ==================================================================
# Vue : Espace Grand Public (2 onglets : Assistant + Sensibilisation)
# ==================================================================
# DEPRECIEE - plus jamais appelee (voir dispatch principal en fin de fichier,
# qui redirige desormais vers la version web independante sur Vercel). Code
# conserve pour reference mais non maintenu ; ne pas modifier ici, modifier
# web/public.html.
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
elif st.session_state.view == "public":
    # L'Espace Grand Public Streamlit est deprecie au profit de la version web
    # independante (Vercel), plus complete et seule maintenue desormais. On ne
    # rend plus jamais l'ancienne implementation, meme via un lien direct
    # ?view=public - redirection systematique vers la version a jour.
    st.markdown('<p class="landing-title">Cet espace a demenage</p>', unsafe_allow_html=True)
    st.write("L'Espace Grand Public est desormais disponible sur notre page web dediee, plus complete.")
    st.link_button("Ouvrir l'Espace Grand Public →", "https://kimatey-finnet-guard.vercel.app/public.html",
                    type="primary", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Retour a l'accueil"):
        st.session_state.view = "landing"
        st.rerun()
elif st.session_state.view == "academic":
    render_academic_view()
else:
    render_landing()

st.markdown("---")
st.caption("Interface developpee avec Streamlit - Realise par Komoe Edgar Junior - Responsable de l'enseignement : Dr ASSOHOUN E Stanislas - Projet ML Master 1 UFRMI")
