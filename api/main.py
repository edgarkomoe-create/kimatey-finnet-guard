"""
API REST - Detection Intelligente des Attaques Reseau
Projet Master 1 Informatique - UFRMI

Expose le modele optimal (Arbre de Decision elague + optimise par GridSearchCV,
Etape 4 du projet) via une API FastAPI independante, documentee automatiquement
(OpenAPI / Swagger), utilisable par n'importe quel client (Streamlit, un SIEM,
un script, curl, Postman...).

Lancement :
    uvicorn api.main:app --reload --port 8000

Documentation interactive :
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""
import io
import json
import os
import time
import logging
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    NetworkFlow, PredictionResponse, BatchPredictionRequest,
    BatchPredictionResponse, BatchPredictionSummary, ModelInfoResponse, HealthResponse,
    LoginRequest, LoginResponse, RegisterRequest, RegisterResponse, ScenarioOut, ReportStepOut,
    AssistantChatRequest, AssistantChatResponse, TemoignageRequest, TemoignageResponse,
    TemoignagesCountResponse, GameCategoryOut, GameMetaOut,
    ExplainFlowRequest, ExplainBatchRequest, ExplainResponse,
    PublicProgressIn, PublicProgressOut, TendancesResponse,
    TransactionIn, TransactionPredictionResponse, TransactionBatchSummary,
    PassInfo, ActivePassResponse, SouscrirePassRequest, SensitivityResponse, SetSensitivityRequest,
    EnrichedModelStatus, AlertOut, SocDashboardResponse, ToggleAlertResponse,
    DashboardCommentRequest, DashboardCommentResponse,
)
from api.transaction_model_service import get_transaction_model_service
from core.pass_system import (
    get_catalog, get_active_pass, souscrire as pass_souscrire, check_and_increment_quota,
)
from core.sensitivity import get_threshold, set_threshold, DEFAULT_THRESHOLD
from core.enriched_model import generate_enriched_model, get_enriched_model_status
from core.alert_log import (
    load_org_state, log_alert as record_alert, log_alerts_bulk, toggle_alert_status,
    compute_security_score, mttr_hours, trend_delta_pct, severity_breakdown, day_severity_series,
)
from api.model_service import get_model_service, CLASS_NAMES
from api.auth import (
    require_org_auth, create_token, verify_shared_password, verify_org_credentials,
    register_user, verify_user_credentials, EmailDejaUtilise,
)
from core.kimatey_core import (
    GENAI_AVAILABLE, genai, genai_types, ask_gemini, ASSISTANT_SYSTEM_PROMPT, ANONYMIZE_SYSTEM_PROMPT,
    ORG_ANALYST_SYSTEM_PROMPT, ORG_EXECUTIVE_SYSTEM_PROMPT, SCENARIOS, REPORT_STEPS, GAME_CATEGORIES,
    GAME_MASCOTS, LEVELS, BADGES, XP_PER_CORRECT, XP_PER_INCORRECT, MAX_HEARTS,
)

BASE_DIR = Path(__file__).resolve().parent.parent
TEMOIGNAGES_FILE = BASE_DIR / "outputs" / "temoignages.jsonl"
# Cache du nom de modele Gemini qui fonctionne, partage entre les requetes de ce
# processus (equivalent cote API du st.session_state utilise par Streamlit).
_GEMINI_CACHE: dict = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("soc_api")

app = FastAPI(
    title="SOC Threat Detection API",
    description=(
        "API de detection intelligente des attaques reseau. Expose le modele de "
        "classification multiclasse optimal (Arbre de Decision elague, optimise par "
        "GridSearchCV - Etape 4 du projet M1) issu du pipeline de Machine Learning "
        "documente dans le rapport de projet."
    ),
    version="1.0.0",
    contact={"name": "Projet M1 Informatique - UFRMI - ECUE Machine Learning"},
)

# CORS ouvert : l'API peut etre appelee depuis une app front-end tierce (Streamlit,
# navigateur, etc.) hebergee sur une autre origine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _load_model_on_startup():
    """Charge le modele et le pipeline de pretraitement une seule fois au demarrage
    (fail-fast : l'API refuse de demarrer si les artefacts sont introuvables)."""
    t0 = time.time()
    service = get_model_service()
    logger.info(
        "Modele charge : %s (exactitude=%.4f, %d variables) en %.2fs",
        service.info["name"], service.info["accuracy"], len(service.selected_features),
        time.time() - t0,
    )
    from core import db
    if db.database_configured():
        db.init_schema()
        logger.info("Base de donnees persistante detectee (DATABASE_URL) - schema initialise.")
    else:
        logger.info("Aucune DATABASE_URL configuree - stockage fichier JSON (non persistant sur Render gratuit).")


@app.get("/", tags=["Meta"], summary="Informations generales")
def root():
    return {
        "service": "SOC Threat Detection API",
        "version": "1.0.0",
        "docs": "/docs",
        "auth_mode": os.environ.get("AUTH_MODE", "none"),
        "endpoints_organisation": [
            "/auth/login", "/auth/register", "/model_info", "/predict", "/predict_batch", "/predict_csv",
            "/organisation/explain_flow", "/organisation/explain_batch",
        ],
        "endpoints_grand_public": [
            "/scenarios", "/report_steps", "/assistant/chat", "/temoignage", "/temoignages/count",
            "/game/categories", "/game/meta",
        ],
        "endpoints": ["/health", "/model_info", "/predict", "/predict_batch", "/predict_csv"],
    }


@app.get("/health", response_model=HealthResponse, tags=["Meta"], summary="Etat de sante de l'API")
def health():
    try:
        get_model_service()
        return HealthResponse(status="ok", model_loaded=True)
    except Exception:
        return HealthResponse(status="degraded", model_loaded=False)


@app.get(
    "/model_info", response_model=ModelInfoResponse, tags=["Meta"],
    summary="Metadonnees du modele en production", dependencies=[Depends(require_org_auth)],
)
def model_info():
    service = get_model_service()
    return ModelInfoResponse(
        model_name=service.info["name"],
        accuracy=service.info["accuracy"],
        f1_macro=service.info["f1_macro"],
        auc_macro=service.info["auc_macro"],
        features_used=service.selected_features,
        all_features=service.features,
        classes={str(k): v for k, v in CLASS_NAMES.items()},
    )


@app.post(
    "/predict", response_model=PredictionResponse, tags=["Prediction"],
    summary="Predire la classe de menace d'un flux reseau unique",
    dependencies=[],
)
def predict(flow: NetworkFlow, user=Depends(require_org_auth)):
    service = get_model_service()
    df = pd.DataFrame([flow.model_dump()])
    threshold = get_threshold("reseau", user["org_id"]) if user else DEFAULT_THRESHOLD
    try:
        preds, probas = service.predict_with_threshold(df, threshold=threshold)
    except Exception as exc:
        logger.exception("Erreur de prediction")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return PredictionResponse(**service.format_prediction(preds[0], probas[0]))


@app.post(
    "/predict_batch", response_model=BatchPredictionResponse, tags=["Prediction"],
    summary="Predire la classe de menace pour une liste de flux reseau (JSON)",
    dependencies=[],
)
def predict_batch(request: BatchPredictionRequest, user=Depends(require_org_auth)):
    if not request.flows:
        raise HTTPException(status_code=400, detail="La liste 'flows' ne peut pas etre vide.")
    service = get_model_service()
    df = pd.DataFrame([f.model_dump() for f in request.flows])
    threshold = get_threshold("reseau", user["org_id"]) if user else DEFAULT_THRESHOLD
    preds, probas = service.predict_with_threshold(df, threshold=threshold)
    predictions = [
        PredictionResponse(**service.format_prediction(p, probas[i])) for i, p in enumerate(preds)
    ]
    n_threats = sum(1 for p in predictions if p.is_threat)
    dist = {}
    for p in predictions:
        dist[p.predicted_label] = dist.get(p.predicted_label, 0) + 1
    summary = BatchPredictionSummary(
        n_flows=len(predictions),
        n_threats=n_threats,
        threat_rate_pct=round(n_threats / len(predictions) * 100, 2),
        class_distribution=dist,
    )
    return BatchPredictionResponse(summary=summary, predictions=predictions)


@app.post(
    "/predict_csv", tags=["Prediction"],
    summary="Predire la classe de menace pour un fichier CSV de logs reseau",
    dependencies=[],
)
async def predict_csv(file: UploadFile = File(..., description="CSV contenant les 9 variables reseau"), user=Depends(require_org_auth)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .csv sont acceptes.")
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Fichier CSV illisible : {exc}")
    if df.empty:
        raise HTTPException(status_code=400, detail="Le fichier CSV est vide.")

    service = get_model_service()
    threshold = get_threshold("reseau", user["org_id"]) if user else DEFAULT_THRESHOLD
    try:
        preds, probas = service.predict_with_threshold(df, threshold=threshold)
    except Exception as exc:
        logger.exception("Erreur de prediction batch CSV")
        raise HTTPException(status_code=500, detail=str(exc))

    df_out = df.copy()
    df_out["Menace_Predite"] = [CLASS_NAMES[int(p)] for p in preds]
    df_out["Confiance_pct"] = [round(float(pr.max()) * 100, 2) for pr in probas]
    n_threats = int((preds != 0).sum())

    # Journalise les alertes en un seul lot (voir core/alert_log.py, log_alerts_bulk) -
    # une seule connexion/transaction Postgres au lieu d'une par alerte, essentiel
    # pour la performance sur de gros lots (jusqu'a 500 alertes journalisees).
    entries_to_log = [
        {"source": f"Import CSV (API) - ligne {i+1}", "pred_class": int(p), "confidence": float(probas[i].max()) * 100}
        for i, p in enumerate(preds[:500])
    ]
    log_alerts_bulk(entries_to_log, domaine="reseau")

    return JSONResponse({
        "summary": {
            "n_flows": len(df_out),
            "n_threats": n_threats,
            "threat_rate_pct": round(n_threats / len(df_out) * 100, 2),
        },
        "results": df_out.to_dict(orient="records"),
    })


@app.post(
    "/organisation/explain_flow", response_model=ExplainResponse, tags=["Organisation"],
    summary="Lieutenant Cyber explique un resultat de flux unique deja calcule par le modele",
    dependencies=[Depends(require_org_auth)],
)
def organisation_explain_flow(payload: ExplainFlowRequest):
    client = _get_gemini_client_or_503()
    content = (
        f"Resultat de classification d'un flux reseau unique, deja calcule par le modele de machine "
        f"learning (tu ne classifies pas toi-meme) : classe predite '{payload.predicted_label}' "
        f"(code {payload.predicted_class}), confiance {payload.confidence:.1f}%. "
        f"Probabilites par categorie : {payload.probabilities}. "
        f"Valeurs des variables techniques du flux : {payload.features}."
    )
    explanation = ask_gemini(client, content, system_instruction=ORG_ANALYST_SYSTEM_PROMPT, cache=_GEMINI_CACHE)
    return ExplainResponse(explanation=explanation)


@app.post(
    "/organisation/explain_batch", response_model=ExplainResponse, tags=["Organisation"],
    summary="Lieutenant Cyber resume une analyse par lot deja calculee par le modele",
    dependencies=[Depends(require_org_auth)],
)
def organisation_explain_batch(payload: ExplainBatchRequest):
    client = _get_gemini_client_or_503()
    content = (
        f"Resultat d'une analyse par lot de {payload.n_flows} flux reseau, deja calcule par le modele de "
        f"machine learning (tu ne classifies pas toi-meme) : {payload.n_threats} flux classes comme "
        f"menace ({payload.threat_rate_pct:.1f}% du trafic). Repartition par categorie : "
        f"{payload.class_distribution}."
    )
    explanation = ask_gemini(client, content, system_instruction=ORG_ANALYST_SYSTEM_PROMPT, cache=_GEMINI_CACHE)
    return ExplainResponse(explanation=explanation)


# ==================================================================
# Authentification (Espace Organisation)
# ==================================================================
@app.post(
    "/auth/login", response_model=LoginResponse, tags=["Authentification"],
    summary="Connexion Espace Organisation (selon AUTH_MODE)",
)
def login(payload: LoginRequest):
    mode = os.environ.get("AUTH_MODE", "none")

    if mode == "none":
        return LoginResponse(
            token=None, auth_mode=mode,
            message="Authentification desactivee (AUTH_MODE=none) : aucun jeton n'est necessaire.",
        )

    if mode == "shared_password":
        if not verify_shared_password(payload.password):
            raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
        return LoginResponse(token=create_token("shared"), auth_mode=mode, message="Connexion reussie.")

    if mode == "per_org":
        if not payload.org_id:
            raise HTTPException(status_code=400, detail="org_id requis en mode 'per_org'.")
        if not verify_org_credentials(payload.org_id, payload.password):
            raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")
        return LoginResponse(
            token=create_token(payload.org_id), auth_mode=mode,
            message=f"Connexion reussie pour {payload.org_id}.",
        )

    if mode == "self_signup":
        if not payload.email:
            raise HTTPException(status_code=400, detail="email requis en mode 'self_signup'.")
        if not verify_user_credentials(payload.email, payload.password):
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
        return LoginResponse(
            token=create_token(payload.email.strip().lower()), auth_mode=mode,
            message=f"Connexion reussie pour {payload.email.strip().lower()}.",
        )

    if mode == "firebase":
        raise HTTPException(
            status_code=400,
            detail=(
                "En mode 'firebase', authentifiez-vous cote client avec le SDK Firebase puis "
                "envoyez directement l'ID token obtenu en 'Authorization: Bearer <id_token>' sur "
                "les endpoints proteges. Aucun appel a /auth/login n'est necessaire dans ce mode."
            ),
        )

    raise HTTPException(status_code=500, detail=f"AUTH_MODE inconnu : {mode}")


@app.post(
    "/auth/register", response_model=RegisterResponse, tags=["Authentification"],
    summary="Creer un compte Espace Organisation par email (mode 'self_signup' uniquement)",
)
def register(payload: RegisterRequest):
    """Auto-inscription : aucune organisation a provisionner a la main (contrairement
    au mode 'per_org') - n'importe qui peut creer son propre compte email + mot de
    passe et etre immediatement connecte (jeton retourne directement)."""
    mode = os.environ.get("AUTH_MODE", "none")
    if mode != "self_signup":
        raise HTTPException(
            status_code=400,
            detail=(
                f"La creation de compte par email n'est disponible qu'en mode "
                f"'self_signup' (AUTH_MODE actuel : '{mode}')."
            ),
        )
    try:
        register_user(payload.email, payload.password)
    except EmailDejaUtilise:
        raise HTTPException(status_code=409, detail="Un compte existe deja avec cet email.")
    return RegisterResponse(
        token=create_token(payload.email), auth_mode=mode,
        message="Compte cree avec succes, vous etes connecte.",
    )


# ==================================================================
# Espace Grand Public (assistant conversationnel, sensibilisation, collecte
# participative anonymisee) - ouvert sans authentification, y compris quand
# AUTH_MODE protege par ailleurs l'Espace Organisation : ce pole s'adresse au
# citoyen lambda et ne doit jamais dependre d'un compte.
# ==================================================================
def _get_gemini_client_or_503():
    if not GENAI_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Assistant indisponible : le package 'google-genai' n'est pas installe cote serveur.",
        )
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Assistant indisponible : la variable d'environnement GEMINI_API_KEY n'est pas configuree cote serveur.",
        )
    return genai.Client(api_key=api_key)


@app.get(
    "/scenarios", response_model=list[ScenarioOut], tags=["Grand Public"],
    summary="Scenarios du mini-jeu de vigilance",
)
def scenarios():
    return SCENARIOS


@app.get(
    "/report_steps", response_model=list[ReportStepOut], tags=["Grand Public"],
    summary="Etapes du parcours de collecte participative (echange guide)",
)
def report_steps():
    return REPORT_STEPS


@app.post(
    "/assistant/chat", response_model=AssistantChatResponse, tags=["Grand Public"],
    summary="Poser une question a l'assistant Kimatey (texte)",
)
def assistant_chat(payload: AssistantChatRequest):
    client = _get_gemini_client_or_503()
    reply = ask_gemini(client, payload.message, system_instruction=ASSISTANT_SYSTEM_PROMPT, cache=_GEMINI_CACHE)
    return AssistantChatResponse(reply=reply)


@app.post(
    "/assistant/chat_image", response_model=AssistantChatResponse, tags=["Grand Public"],
    summary="Analyser une capture d'ecran (SMS/message suspect) avec l'assistant Kimatey",
)
async def assistant_chat_image(image: UploadFile = File(..., description="Capture d'ecran du SMS/message suspect (JPEG/PNG)"),
                                message: str = "", account_id: str = "anonyme"):
    # Garde-fou produit : le chat texte de base (/assistant/chat) reste TOUJOURS gratuit et
    # illimite - seule l'analyse d'image (confort additionnel) est soumise au quota du Pass
    # actif. Un compte anonyme (aucun compte optionnel connecte) partage un quota commun
    # "anonyme" cote public - avoir un compte optionnel permet un suivi individuel du quota.
    allowed, quota_info = check_and_increment_quota("public", account_id, "images_mois")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Quota d'analyses d'image atteint pour ce mois ({quota_info['utilise']}/{quota_info['limite']} "
                f"avec le Pass '{quota_info['pass_actuel']}'). Le chat texte reste gratuit et illimite. "
                "Voir /pass/catalogue pour les options."
            ),
        )
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format d'image non supporte. Utilisez JPEG, PNG ou WebP.",
        )
    image_bytes = await image.read()
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image trop volumineuse (8 Mo maximum).",
        )
    client = _get_gemini_client_or_503()
    prompt_text = message.strip() or (
        "Voici une capture d'ecran d'un SMS ou message que j'ai recu. Est-ce une arnaque mobile money ? "
        "Explique pourquoi en langage simple."
    )
    # Contenu multimodal natif Gemini (image + texte) : aucun OCR separe necessaire,
    # le modele lit directement le texte visible dans l'image.
    contents = [
        genai_types.Part.from_bytes(data=image_bytes, mime_type=image.content_type),
        prompt_text,
    ]
    reply = ask_gemini(client, contents, system_instruction=ASSISTANT_SYSTEM_PROMPT, cache=_GEMINI_CACHE)
    return AssistantChatResponse(reply=reply)


@app.get(
    "/game/categories", response_model=list[GameCategoryOut], tags=["Grand Public"],
    summary="Categories du jeu de vigilance",
)
def game_categories():
    return [
        {
            **cat,
            "mascot_name": GAME_MASCOTS[cat["mascot_key"]]["name"],
            "mascot_intro": cat.get("mascot_line") or GAME_MASCOTS[cat["mascot_key"]]["intro"],
        }
        for cat in GAME_CATEGORIES
    ]


@app.get(
    "/game/meta", response_model=GameMetaOut, tags=["Grand Public"],
    summary="Regles du jeu : Points Bouclier par reponse, vies, niveaux, badges",
)
def game_meta():
    return GameMetaOut(
        xp_per_correct=XP_PER_CORRECT,
        xp_per_incorrect=XP_PER_INCORRECT,
        max_hearts=MAX_HEARTS,
        levels=LEVELS,
        badges=BADGES,
    )


def _count_temoignages() -> int:
    if not TEMOIGNAGES_FILE.exists():
        return 0
    with open(TEMOIGNAGES_FILE) as f:
        return sum(1 for line in f if line.strip())


@app.post(
    "/temoignage", response_model=TemoignageResponse, tags=["Grand Public"],
    summary="Contribuer un temoignage anonymise (technique de fraude observee)",
)
def temoignage(payload: TemoignageRequest):
    fiche = f"Canal : {payload.canal} - Demande : {payload.demande} - Reaction : {payload.reaction}."

    if payload.detail and payload.detail.strip() and GENAI_AVAILABLE and os.environ.get("GEMINI_API_KEY"):
        try:
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            synth = ask_gemini(
                client, payload.detail.strip(), system_instruction=ANONYMIZE_SYSTEM_PROMPT, cache=_GEMINI_CACHE,
            )
            fiche = f"{fiche} {synth}"
        except Exception:
            logger.exception("Echec de la synthese IA du temoignage - fiche structuree conservee sans le detail libre.")

    TEMOIGNAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TEMOIGNAGES_FILE, "a") as f:
        f.write(json.dumps({
            "horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
            "fiche": fiche,
            # Champs structures (en plus de la fiche texte) : uniquement utilises pour les
            # comptages agreges du fil de tendances (/temoignages/tendances) - jamais le
            # texte libre individuel, pour preserver l'anonymat.
            "canal": payload.canal,
            "demande": payload.demande,
        }, ensure_ascii=False) + "\n")

    return TemoignageResponse(fiche=fiche, total_contributions=_count_temoignages())


@app.get(
    "/temoignages/count", response_model=TemoignagesCountResponse, tags=["Grand Public"],
    summary="Nombre de contributions enregistrees (pour le compteur ludique)",
)
def temoignages_count():
    return TemoignagesCountResponse(count=_count_temoignages())


@app.get(
    "/temoignages/tendances", response_model=TendancesResponse, tags=["Grand Public"],
    summary="Tendances agregees des techniques de fraude signalees (comptages uniquement, jamais de texte individuel)",
)
def temoignages_tendances():
    """Fil communautaire de tendances : comptages par canal et par type de demande,
    calcules sur l'ensemble des contributions. Ne retourne JAMAIS le texte libre
    (`fiche`/`detail`) d'une contribution individuelle - uniquement des totaux par
    categorie, pour proteger l'anonymat tout en donnant un signal collectif utile
    ("X signalements de faux-employeur cette semaine")."""
    if not TEMOIGNAGES_FILE.exists():
        return TendancesResponse(total=0, par_canal={}, par_demande={})
    canal_counts, demande_counts, total = {}, {}, 0
    with open(TEMOIGNAGES_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            canal = entry.get("canal")
            demande = entry.get("demande")
            if canal:
                canal_counts[canal] = canal_counts.get(canal, 0) + 1
            if demande:
                demande_counts[demande] = demande_counts.get(demande, 0) + 1
    return TendancesResponse(total=total, par_canal=canal_counts, par_demande=demande_counts)


# ==================================================================
# Compte optionnel (Espace Grand Public) : synchronisation de la progression
# ==================================================================
# Reutilise TEL QUEL l'authentification 'self_signup' (POST /auth/register,
# POST /auth/login) deja construite pour l'Espace Organisation : c'est un
# mecanisme generique (email + mot de passe, jeton signe), pas specifique a
# une organisation. Aucune duplication de code d'authentification.
#
# IMPORTANT (coherence avec le positionnement "sans compte, zero donnee
# personnelle" de l'Espace Grand Public) : ce compte reste STRICTEMENT
# OPTIONNEL. Sans compte, tout continue de fonctionner exactement comme avant
# (progression stockee uniquement dans le navigateur, localStorage). Le compte
# ne sert qu'a synchroniser cette meme progression entre plusieurs appareils
# pour qui le souhaite explicitement.
PUBLIC_PROGRESS_FILE = Path(__file__).resolve().parent / "public_progress.json"


def _load_public_progress() -> dict:
    if not PUBLIC_PROGRESS_FILE.exists():
        return {}
    with open(PUBLIC_PROGRESS_FILE) as f:
        return json.load(f)


def _save_public_progress(data: dict) -> None:
    PUBLIC_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PUBLIC_PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.post(
    "/public/progress", response_model=PublicProgressOut, tags=["Grand Public"],
    summary="Sauvegarde la progression du jeu de vigilance pour le compte connecte (optionnel)",
    dependencies=[],
)
def save_public_progress(payload: PublicProgressIn, user=Depends(require_org_auth)):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte requis pour synchroniser la progression (optionnel : sans compte, votre progression reste sauvegardee localement dans ce navigateur).",
        )
    email = user["org_id"]  # en mode self_signup, l'email joue le role d'identifiant de compte
    all_progress = _load_public_progress()
    all_progress[email] = {"state": payload.state, "updated_at": time.time()}
    _save_public_progress(all_progress)
    return PublicProgressOut(state=payload.state, updated_at=all_progress[email]["updated_at"])


@app.get(
    "/public/progress", response_model=PublicProgressOut, tags=["Grand Public"],
    summary="Recupere la derniere progression sauvegardee pour le compte connecte (optionnel)",
)
def get_public_progress(user=Depends(require_org_auth)):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte requis pour recuperer une progression synchronisee.",
        )
    email = user["org_id"]
    entry = _load_public_progress().get(email)
    if not entry:
        return PublicProgressOut(state=None, updated_at=None)
    return PublicProgressOut(state=entry["state"], updated_at=entry["updated_at"])


# ==================================================================
# Fraude transactionnelle (PROTOTYPE - modele entraine sur donnees SYNTHETIQUES)
# ==================================================================
@app.post(
    "/predict_transaction", response_model=TransactionPredictionResponse, tags=["Organisation"],
    summary="[PROTOTYPE] Evalue une transaction mobile money (modele entraine sur donnees synthetiques)",
    dependencies=[Depends(require_org_auth)],
)
def predict_transaction(payload: TransactionIn):
    service = get_transaction_model_service()
    df = pd.DataFrame([payload.model_dump()])
    preds, confs, probas = service.predict(df)
    from api.transaction_model_service import CLASS_NAMES as TX_CLASS_NAMES
    return TransactionPredictionResponse(
        prediction=TX_CLASS_NAMES[int(preds[0])],
        confidence=round(float(confs[0]), 1),
    )


@app.post(
    "/predict_transaction_csv", response_model=TransactionBatchSummary, tags=["Organisation"],
    summary="[PROTOTYPE] Evalue un lot de transactions mobile money via un fichier CSV",
    dependencies=[Depends(require_org_auth)],
)
async def predict_transaction_csv(file: UploadFile = File(..., description="CSV de transactions (colonnes du schema transactionnel)")):
    service = get_transaction_model_service()
    df = pd.read_csv(file.file)
    preds, confs, probas = service.predict(df)
    n_suspect = int((preds != 0).sum())

    from api.transaction_model_service import CLASS_NAMES as TX_CLASS_NAMES
    entries_to_log = [
        {"source": f"Import CSV Transactions (API) - ligne {i+1}", "pred_class": int(p), "confidence": float(confs[i])}
        for i, p in enumerate(preds[:500])
    ]
    log_alerts_bulk(entries_to_log, domaine="transactions", class_names=TX_CLASS_NAMES)

    return TransactionBatchSummary(
        n_total=len(df),
        n_suspectes=n_suspect,
        taux_suspect=round(n_suspect / len(df) * 100, 1) if len(df) > 0 else 0.0,
    )


# ==================================================================
# Systeme de Pass (MODE DEMO - aucun paiement reel encaisse, voir
# docs/ROADMAP_PAIEMENT.md pour l'integration Orange Money/MTN Mobile Money)
# ==================================================================
@app.get(
    "/pass/catalogue", response_model=list[PassInfo], tags=["Meta"],
    summary="Catalogue des Pass disponibles pour un scope donne (organisation ou public)",
)
def pass_catalogue(scope: str):
    if scope not in ("organisation", "public"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope doit etre 'organisation' ou 'public'")
    return get_catalog(scope)


@app.get(
    "/pass/actif", response_model=ActivePassResponse, tags=["Meta"],
    summary="Pass actuellement actif pour un compte (organisation ou public, avec compte optionnel)",
)
def pass_actif(scope: str, account_id: str):
    if scope not in ("organisation", "public"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope doit etre 'organisation' ou 'public'")
    active = get_active_pass(scope, account_id)
    return ActivePassResponse(
        pass_id=active["pass_id"], nom=active["definition"]["nom"], usage=active["usage"],
        quotas=active["definition"]["quotas"], expire_le=active.get("expire_le"),
    )


@app.post(
    "/pass/souscrire", response_model=ActivePassResponse, tags=["Meta"],
    summary="[MODE DEMO] Active un Pass pour un compte - aucun paiement reel n'est encaisse",
)
def pass_souscrire_endpoint(scope: str, account_id: str, payload: SouscrirePassRequest):
    if scope not in ("organisation", "public"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope doit etre 'organisation' ou 'public'")
    try:
        entry = pass_souscrire(scope, account_id, payload.pass_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    active = get_active_pass(scope, account_id)
    return ActivePassResponse(
        pass_id=entry["pass_id"], nom=active["definition"]["nom"], usage=entry["usage"],
        quotas=active["definition"]["quotas"], expire_le=entry.get("expire_le"),
    )


# ==================================================================
# Reglage de sensibilite (seuil de decision, sans reentrainement)
# ==================================================================
@app.get(
    "/sensibilite", response_model=SensitivityResponse, tags=["Organisation"],
    summary="Seuil de sensibilite actuel du compte connecte (domaine 'reseau' ou 'transactions')",
)
def get_sensibilite(domain: str, user=Depends(require_org_auth)):
    if domain not in ("reseau", "transactions"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="domain doit etre 'reseau' ou 'transactions'")
    account_id = user["org_id"] if user else "anonyme"
    threshold = get_threshold(domain, account_id)
    return SensitivityResponse(domain=domain, threshold=threshold, is_default=(threshold == DEFAULT_THRESHOLD))


@app.post(
    "/sensibilite", response_model=SensitivityResponse, tags=["Organisation"],
    summary="Ajuste le seuil de sensibilite du compte connecte (0-1, 0.5 = standard)",
    dependencies=[Depends(require_org_auth)],
)
def set_sensibilite(domain: str, payload: SetSensitivityRequest, user=Depends(require_org_auth)):
    if domain not in ("reseau", "transactions"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="domain doit etre 'reseau' ou 'transactions'")
    account_id = user["org_id"] if user else "anonyme"
    try:
        threshold = set_threshold(domain, account_id, payload.threshold)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return SensitivityResponse(domain=domain, threshold=threshold, is_default=(threshold == DEFAULT_THRESHOLD))


# ==================================================================
# Modele hybride, Niveau 2 : modele enrichi par organisation
# (voir core/enriched_model.py pour le detail de la methodologie et des
# garde-fous - jamais automatique, toujours declenche explicitement)
# ==================================================================
@app.get(
    "/organisation/modele_enrichi", response_model=EnrichedModelStatus, tags=["Organisation"],
    summary="Statut du modele enrichi pour l'organisation connectee (existe ? combien d'echantillons ?)",
    dependencies=[Depends(require_org_auth)],
)
def modele_enrichi_status(user=Depends(require_org_auth)):
    account_id = user["org_id"] if user else "anonyme"
    return get_enriched_model_status(account_id)


@app.post(
    "/organisation/modele_enrichi/generer", response_model=EnrichedModelStatus, tags=["Organisation"],
    summary="Genere (ou regenere) le modele enrichi pour l'organisation connectee, a partir de ses echantillons valides",
    dependencies=[Depends(require_org_auth)],
)
def modele_enrichi_generer(user=Depends(require_org_auth)):
    account_id = user["org_id"] if user else "anonyme"
    try:
        generate_enriched_model(account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return get_enriched_model_status(account_id)


# ==================================================================
# Dashboard SOC (donnees pour une page web animee, en plus de l'onglet
# Streamlit existant - les deux lisent/ecrivent le meme fichier partage,
# voir core/alert_log.py)
# ==================================================================
def _build_soc_dashboard(domaine: str = "reseau") -> SocDashboardResponse:
    state = load_org_state(domaine=domaine)
    alert_log = state.get("alert_log", [])
    n_open = len([a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"])
    n_closed = len(alert_log) - n_open
    treated_rate = round(100 * n_closed / len(alert_log), 1) if alert_log else 0.0
    delta_pct, delta_text = trend_delta_pct(alert_log, days=7)
    return SocDashboardResponse(
        score=compute_security_score(alert_log),
        n_open=n_open,
        n_closed=n_closed,
        treated_rate_pct=treated_rate,
        mttr_hours=mttr_hours(alert_log),
        trend_delta_pct=delta_pct,
        trend_text=delta_text,
        severity_breakdown=severity_breakdown(alert_log),
        day_severity_series=day_severity_series(alert_log, days=14),
        alerts=[
            AlertOut(
                ID=a["ID"], Horodatage=a["Horodatage"], Source=a["Source"], Menace=a["Menace"],
                Confiance=a["Confiance (%)"], Statut=a.get("Statut", "Ouvert"), Fermee_le=a.get("Fermee_le"),
            )
            for a in alert_log[:200]
        ],
    )


@app.get(
    "/organisation/dashboard_soc", response_model=SocDashboardResponse, tags=["Organisation"],
    summary="Etat operationnel complet (score, alertes, tendances) pour le dashboard SOC - Securite Reseau",
    dependencies=[Depends(require_org_auth)],
)
def organisation_dashboard_soc():
    return _build_soc_dashboard(domaine="reseau")


@app.get(
    "/organisation/dashboard_transactions", response_model=SocDashboardResponse, tags=["Organisation"],
    summary="Etat operationnel complet (score, alertes, tendances) pour le dashboard - Fraude Transactionnelle",
    dependencies=[Depends(require_org_auth)],
)
def organisation_dashboard_transactions():
    return _build_soc_dashboard(domaine="transactions")


@app.post(
    "/organisation/dashboard_soc/toggle/{alert_id}", response_model=ToggleAlertResponse, tags=["Organisation"],
    summary="Bascule le statut Ouvert/Ferme d'une alerte (Securite Reseau), retourne le dashboard mis a jour",
    dependencies=[Depends(require_org_auth)],
)
def organisation_dashboard_toggle(alert_id: str):
    found = toggle_alert_status(alert_id, domaine="reseau")
    return ToggleAlertResponse(found=found, dashboard=_build_soc_dashboard(domaine="reseau"))


@app.post(
    "/organisation/dashboard_transactions/toggle/{alert_id}", response_model=ToggleAlertResponse, tags=["Organisation"],
    summary="Bascule le statut Ouvert/Ferme d'une transaction suspecte, retourne le dashboard mis a jour",
    dependencies=[Depends(require_org_auth)],
)
def organisation_dashboard_transactions_toggle(alert_id: str):
    found = toggle_alert_status(alert_id, domaine="transactions")
    return ToggleAlertResponse(found=found, dashboard=_build_soc_dashboard(domaine="transactions"))


@app.post(
    "/organisation/dashboard_soc/commentaire", response_model=DashboardCommentResponse, tags=["Organisation"],
    summary="Genere un commentaire IA (persona decideur ou analyste) sur l'etat actuel du dashboard",
    dependencies=[Depends(require_org_auth)],
)
def organisation_dashboard_commentaire(payload: DashboardCommentRequest):
    if payload.mode not in ("executive", "analyst"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode doit etre 'executive' ou 'analyst'")
    domaine = payload.domaine if payload.domaine in ("reseau", "transactions") else "reseau"
    client = _get_gemini_client_or_503()
    dashboard = _build_soc_dashboard(domaine=domaine)
    prompt_system = ORG_EXECUTIVE_SYSTEM_PROMPT if payload.mode == "executive" else ORG_ANALYST_SYSTEM_PROMPT

    if payload.mode == "executive":
        categories = list({a.Menace for a in dashboard.alerts if a.Statut == "Ouvert"})
        content = (
            f"Score de securite actuel : {dashboard.score}/100. {dashboard.n_open} situation(s) encore "
            f"non traitee(s) sur {dashboard.n_open + dashboard.n_closed} au total. Categories concernees "
            f"par les situations non traitees : {categories if categories else 'aucune'}."
        )
    else:
        content = (
            f"Score de securite : {dashboard.score}/100. Alertes ouvertes : {dashboard.n_open}, "
            f"fermees : {dashboard.n_closed} (taux de traitement {dashboard.treated_rate_pct}%). "
            f"Repartition par gravite : {dashboard.severity_breakdown}. "
            f"MTTR : {dashboard.mttr_hours if dashboard.mttr_hours is not None else 'non disponible'} heures. "
            f"Tendance 7 jours : {dashboard.trend_text}."
        )

    commentaire = ask_gemini(client, content, system_instruction=prompt_system, cache=_GEMINI_CACHE)
    return DashboardCommentResponse(mode=payload.mode, commentaire=commentaire)
