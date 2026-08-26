"""Schemas Pydantic pour l'API de detection d'intrusion reseau."""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class NetworkFlow(BaseModel):
    """Un flux reseau brut, tel que collecte par une sonde SOC (9 variables)."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "Duree_Connexion": 19867.35,
            "Octets_Source_Vers_Dest": 1717.17,
            "Octets_Dest_Vers_Source": 6886.95,
            "Taux_Paquets_Secondes": 152.1,
            "Fenetre_TCP_Moyenne": 16384,
            "Ports_Dest_Distincts": 121,
            "Connexions_Simultanees": 5,
            "Taux_Erreur_CheckSum": 0.0176,
            "Frequence_SYN_Flags": 0.0577,
        }
    })

    Duree_Connexion: float = Field(..., ge=0, description="Duree totale de la session (ms)")
    Octets_Source_Vers_Dest: float = Field(..., ge=0, description="Octets emis par la source")
    Octets_Dest_Vers_Source: float = Field(..., ge=0, description="Octets recus en retour")
    Taux_Paquets_Secondes: float = Field(..., ge=0, description="Frequence d'emission des paquets/s")
    Fenetre_TCP_Moyenne: float = Field(..., ge=0, description="Taille moyenne de la fenetre TCP")
    Ports_Dest_Distincts: float = Field(..., ge=0, description="Nb de ports distincts cibles (<1s)")
    Connexions_Simultanees: float = Field(..., ge=0, description="Nb de connexions ouvertes en parallele")
    Taux_Erreur_CheckSum: float = Field(..., ge=0, description="Pourcentage de paquets corrompus")
    Frequence_SYN_Flags: float = Field(..., ge=0, description="Proportion de drapeaux SYN actives")


class PredictionResponse(BaseModel):
    predicted_class: int = Field(..., description="Code de la classe predite (0-3)")
    predicted_label: str = Field(..., description="Libelle de la classe predite")
    confidence: float = Field(..., description="Niveau de confiance de la prediction (%)")
    probabilities: Dict[str, float] = Field(..., description="Probabilite (%) pour chacune des 4 classes")
    is_threat: bool = Field(..., description="True si la classe predite n'est pas du trafic normal")


class BatchPredictionRequest(BaseModel):
    flows: List[NetworkFlow]


class BatchPredictionSummary(BaseModel):
    n_flows: int
    n_threats: int
    threat_rate_pct: float
    class_distribution: Dict[str, int]


class BatchPredictionResponse(BaseModel):
    summary: BatchPredictionSummary
    predictions: List[PredictionResponse]


class ModelInfoResponse(BaseModel):
    model_name: str
    accuracy: float
    f1_macro: float
    auc_macro: float
    features_used: List[str]
    all_features: List[str]
    classes: Dict[str, str]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


# ---------------------------------------------------------------- Authentification (Espace Organisation)
class LoginRequest(BaseModel):
    org_id: Optional[str] = Field(None, description="Identifiant d'organisation (requis en mode 'per_org' uniquement)")
    email: Optional[str] = Field(None, description="Email (requis en mode 'self_signup' uniquement)")
    password: str = Field(..., description="Mot de passe (partage, propre a l'organisation, ou de compte selon AUTH_MODE)")


class LoginResponse(BaseModel):
    token: Optional[str] = Field(None, description="Jeton a fournir en 'Authorization: Bearer <token>'")
    auth_mode: str
    message: str


class RegisterRequest(BaseModel):
    """Mode 'self_signup' uniquement : creation d'un compte par email + mot de
    passe (aucun compte a provisionner a la main, contrairement au mode
    'per_org')."""
    email: str = Field(..., min_length=5, max_length=254, description="Adresse email, sert d'identifiant de compte")
    password: str = Field(..., min_length=6, max_length=128, description="Mot de passe (6 caracteres minimum)")

    @field_validator("email")
    @classmethod
    def _email_plausible(cls, v: str) -> str:
        v = v.strip()
        domaine = v.split("@")[-1] if "@" in v else ""
        if v.startswith("@") or v.endswith("@") or "@" not in v or "." not in domaine:
            raise ValueError("Adresse email invalide.")
        return v.lower()


class RegisterResponse(BaseModel):
    token: str = Field(..., description="Jeton a fournir en 'Authorization: Bearer <token>' - le compte cree est deja connecte")
    auth_mode: str
    message: str


# ---------------------------------------------------------------- Compte optionnel (Espace Grand Public)
class PublicProgressIn(BaseModel):
    """Sauvegarde optionnelle de la progression du jeu de vigilance, associee
    au compte connecte (reutilise l'authentification 'self_signup' existante).
    Entierement facultatif : sans compte, la progression reste locale au
    navigateur (localStorage) comme aujourd'hui."""
    state: dict = Field(..., description="Etat serialise du jeu (xp, hearts, badges, categorie, progression par categorie)")


class PublicProgressOut(BaseModel):
    state: Optional[dict] = Field(None, description="Dernier etat sauvegarde pour ce compte, ou null si aucun")
    updated_at: Optional[float] = None


# ---------------------------------------------------------------- Espace Grand Public
class ScenarioOut(BaseModel):
    situation: str
    choices: List[str]
    correct: int
    explanation: str


class ReportStepOut(BaseModel):
    key: str
    question: str
    options: List[str]


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Question de l'utilisateur (texte)")


class AssistantChatResponse(BaseModel):
    reply: str


class TemoignageRequest(BaseModel):
    canal: str = Field(..., description="Canal utilise (SMS, appel, WhatsApp...)")
    demande: str = Field(..., description="Ce qui etait demande")
    reaction: str = Field(..., description="Reaction de la personne")
    detail: Optional[str] = Field(None, description="Recit libre facultatif, anonymise avant stockage")


class TemoignageResponse(BaseModel):
    fiche: str
    total_contributions: int


class TemoignagesCountResponse(BaseModel):
    count: int


class TendancesResponse(BaseModel):
    total: int = Field(..., description="Nombre total de contributions prises en compte")
    par_canal: dict = Field(..., description="Comptage par canal utilise (SMS, appel, WhatsApp...)")
    par_demande: dict = Field(..., description="Comptage par type de demande signalee")


# ---------------------------------------------------------------- Sensibilisation ludique (fusion gamification)
class GameScenarioOut(BaseModel):
    situation: str
    choices: List[str]
    correct: int
    explanation: str
    tip: Optional[str] = None


class GameCategoryOut(BaseModel):
    key: str
    label: str
    emoji: str
    mascot_key: str
    mascot_name: str
    mascot_intro: str
    scenarios: List[GameScenarioOut]


class LevelOut(BaseModel):
    xp_threshold: int
    title: str


class BadgeOut(BaseModel):
    key: str
    emoji: str
    label: str
    xp_required: int
    desc: str


class GameMetaOut(BaseModel):
    xp_per_correct: int
    xp_per_incorrect: int
    max_hearts: int
    levels: List[LevelOut]
    badges: List[BadgeOut]


# ---------------------------------------------------------------- Assistance a l'analyse (Espace Organisation)
# Meme IA (Lieutenant Cyber) que celle du pole Grand Public, ici dans un second role : commenter en langage
# clair un resultat DEJA calcule par le modele (jamais elle qui classifie - voir ORG_ANALYST_SYSTEM_PROMPT).
class ExplainFlowRequest(BaseModel):
    predicted_class: int = Field(..., description="Code de la classe predite par le modele (0-3)")
    predicted_label: str = Field(..., description="Libelle de la classe predite")
    confidence: float = Field(..., description="Niveau de confiance du modele (%)")
    probabilities: Dict[str, float] = Field(default_factory=dict, description="Probabilite (%) par categorie")
    features: Dict[str, float] = Field(default_factory=dict, description="Valeurs des variables techniques du flux")


class ExplainBatchRequest(BaseModel):
    n_flows: int = Field(..., ge=1, description="Nombre de flux analyses dans le lot")
    n_threats: int = Field(..., ge=0, description="Nombre de flux classes comme menace")
    threat_rate_pct: float = Field(..., ge=0, le=100, description="Part du trafic classee comme menace (%)")
    class_distribution: Dict[str, int] = Field(default_factory=dict, description="Nombre de flux par categorie")


class ExplainResponse(BaseModel):
    explanation: str = Field(..., description="Explication en langage clair + recommandation d'action, par Lieutenant Cyber")
