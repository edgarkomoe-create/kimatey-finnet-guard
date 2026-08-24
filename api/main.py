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
    PublicProgressIn, PublicProgressOut,
)
from api.model_service import get_model_service, CLASS_NAMES
from api.auth import (
    require_org_auth, create_token, verify_shared_password, verify_org_credentials,
    register_user, verify_user_credentials, EmailDejaUtilise,
)
from core.kimatey_core import (
    GENAI_AVAILABLE, genai, ask_gemini, ASSISTANT_SYSTEM_PROMPT, ANONYMIZE_SYSTEM_PROMPT,
    ORG_ANALYST_SYSTEM_PROMPT, SCENARIOS, REPORT_STEPS, GAME_CATEGORIES, GAME_MASCOTS, LEVELS, BADGES,
    XP_PER_CORRECT, XP_PER_INCORRECT, MAX_HEARTS,
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
    dependencies=[Depends(require_org_auth)],
)
def predict(flow: NetworkFlow):
    service = get_model_service()
    df = pd.DataFrame([flow.model_dump()])
    try:
        preds, probas = service.predict(df)
    except Exception as exc:
        logger.exception("Erreur de prediction")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return PredictionResponse(**service.format_prediction(preds[0], probas[0]))


@app.post(
    "/predict_batch", response_model=BatchPredictionResponse, tags=["Prediction"],
    summary="Predire la classe de menace pour une liste de flux reseau (JSON)",
    dependencies=[Depends(require_org_auth)],
)
def predict_batch(request: BatchPredictionRequest):
    if not request.flows:
        raise HTTPException(status_code=400, detail="La liste 'flows' ne peut pas etre vide.")
    service = get_model_service()
    df = pd.DataFrame([f.model_dump() for f in request.flows])
    preds, probas = service.predict(df)
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
    dependencies=[Depends(require_org_auth)],
)
async def predict_csv(file: UploadFile = File(..., description="CSV contenant les 9 variables reseau")):
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
    try:
        preds, probas = service.predict(df)
    except Exception as exc:
        logger.exception("Erreur de prediction batch CSV")
        raise HTTPException(status_code=500, detail=str(exc))

    df_out = df.copy()
    df_out["Menace_Predite"] = [CLASS_NAMES[int(p)] for p in preds]
    df_out["Confiance_pct"] = [round(float(pr.max()) * 100, 2) for pr in probas]
    n_threats = int((preds != 0).sum())

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


@app.get(
    "/game/categories", response_model=list[GameCategoryOut], tags=["Grand Public"],
    summary="Categories du jeu de vigilance (fusion avec le modele de gamification VIE Water Care)",
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
        }, ensure_ascii=False) + "\n")

    return TemoignageResponse(fiche=fiche, total_contributions=_count_temoignages())


@app.get(
    "/temoignages/count", response_model=TemoignagesCountResponse, tags=["Grand Public"],
    summary="Nombre de contributions enregistrees (pour le compteur ludique)",
)
def temoignages_count():
    return TemoignagesCountResponse(count=_count_temoignages())


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
