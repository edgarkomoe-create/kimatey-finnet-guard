"""
Authentification de l'Espace Organisation (API Kimatey FinNet Guard).

Cinq modes reels sont geres via la variable d'environnement AUTH_MODE, relue
a CHAQUE requete (jamais mise en cache a l'import du module) : cela permet de
changer de mode - y compris pendant les tests automatises via monkeypatch -
sans avoir a redemarrer le processus uvicorn.

- "none" (par defaut)
    Aucune authentification : comportement historique de l'API, conserve pour
    ne pas casser les demos/tests existants qui appellent /predict directement.

- "shared_password"
    Un seul mot de passe partage (variable d'environnement SHARED_ORG_PASSWORD)
    protege tout l'Espace Organisation. Le plus simple a mettre en place pour
    une demonstration ou un premier pilote a une seule organisation.

- "per_org"
    Chaque organisation cliente a son propre identifiant (org_id) et mot de
    passe, verifies contre api/orgs.json (comptes pre-provisionnes a la main).
    Les mots de passe n'y sont jamais stockes en clair (hash sale, SHA-256).

- "self_signup"
    Auto-inscription par email + mot de passe (api/users.json), sans compte a
    provisionner a la main ni service externe : n'importe qui peut creer son
    propre compte (POST /auth/register) puis se connecter (POST /auth/login).
    C'est ce mode qui rend le MVP "connectable" de bout en bout sans dependre
    d'un projet Firebase reel. Les mots de passe sont stockes hashes-sales
    (SHA-256), jamais en clair. Volontairement minimaliste pour une demo/M1 :
    pas de verification d'email, pas de recuperation de mot de passe oublie.

- "firebase"
    Point d'extension pour Firebase Authentication : le client (page web ou
    appli mobile) s'authentifie directement aupres de Firebase avec le SDK
    officiel, puis envoie son "ID token" Firebase en Authorization: Bearer a
    l'API, qui le verifie cote serveur via le package `firebase-admin`. Ce mode
    n'est PAS operationnel dans cet environnement de demonstration : il n'y a
    ni le package installe, ni un vrai projet Firebase (fichier de compte de
    service) a y brancher. Plutot que de simuler une reussite, la fonction
    correspondante leve une erreur explicite (501) tant que ces deux
    prerequis ne sont pas fournis - voir le README pour la procedure de
    connexion a un vrai projet Firebase.

Le jeton emis a la connexion (modes shared_password/per_org/self_signup) est
un jeton "maison" signe en HMAC-SHA256 (pas de dependance externe type JWT) :
{org_id, exp} encode en base64, signe avec API_AUTH_SECRET (variable
d'environnement - une valeur par defaut est fournie pour la demonstration,
a changer obligatoirement en production). En mode "self_signup", l'email de
l'utilisateur joue le role d'org_id dans ce jeton.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException, status

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ORGS_FILE = BASE_DIR / "api" / "orgs.json"
DEFAULT_USERS_FILE = BASE_DIR / "api" / "users.json"
TOKEN_TTL_SECONDS = 8 * 3600  # 8h, une journee de travail type pour une equipe IT/securite

# Variable de module (et non constante figee) : permet aux tests de rediriger
# vers un fichier temporaire via monkeypatch.setattr(auth, "ORGS_FILE", tmp_path)
# sans toucher au vrai fichier de demonstration livre avec le projet.
ORGS_FILE = DEFAULT_ORGS_FILE

# Meme principe pour le mode "self_signup" : monkeypatch.setattr(auth, "USERS_FILE", tmp_path)
# dans les tests isole des vrais comptes crees en demo.
USERS_FILE = DEFAULT_USERS_FILE


class EmailDejaUtilise(ValueError):
    """Mode 'self_signup' : un compte existe deja avec cet email."""


def _secret() -> bytes:
    return os.environ.get("API_AUTH_SECRET", "kimatey-finnet-guard-demo-secret-a-changer-en-prod").encode()


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(org_id: str) -> str:
    """Emet un jeton signe, valable TOKEN_TTL_SECONDS, identifiant `org_id`."""
    payload = json.dumps({"org_id": org_id, "exp": time.time() + TOKEN_TTL_SECONDS}).encode()
    signature = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return f"{_b64encode(payload)}.{_b64encode(signature)}"


def _verify_token(token: str) -> dict:
    try:
        payload_b64, signature_b64 = token.split(".")
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton malforme.")
    expected = hmac.new(_secret(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton invalide.")
    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton illisible.")
    if data.get("exp", 0) < time.time():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jeton expire, reconnectez-vous.")
    return data


def _load_orgs() -> list:
    if not ORGS_FILE.exists():
        return []
    with open(ORGS_FILE) as f:
        return json.load(f)


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_org_credentials(org_id: str, password: str) -> bool:
    """Mode 'per_org' : verifie (org_id, password) contre api/orgs.json."""
    for org in _load_orgs():
        if org.get("org_id") == org_id:
            return hmac.compare_digest(hash_password(password, org["salt"]), org["password_hash"])
    return False


def verify_shared_password(password: str) -> bool:
    """Mode 'shared_password' : compare au mot de passe unique defini par
    SHARED_ORG_PASSWORD (valeur de demonstration par defaut si absente)."""
    expected = os.environ.get("SHARED_ORG_PASSWORD", "kimatey-demo")
    return hmac.compare_digest(password, expected)


def _load_users() -> list:
    if not USERS_FILE.exists():
        return []
    with open(USERS_FILE) as f:
        return json.load(f)


def _save_users(users: list) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def register_user(email: str, password: str) -> None:
    """Mode 'self_signup' : cree un compte email + mot de passe dans
    api/users.json (mot de passe hashe-sale, jamais stocke en clair).
    Leve EmailDejaUtilise si un compte existe deja avec cet email
    (comparaison insensible a la casse : Jean@X.com == jean@x.com)."""
    email_normalise = email.strip().lower()
    users = _load_users()
    if any(u.get("email") == email_normalise for u in users):
        raise EmailDejaUtilise(f"Un compte existe deja avec l'email '{email_normalise}'.")
    salt = os.urandom(16).hex()
    users.append({
        "email": email_normalise,
        "salt": salt,
        "password_hash": hash_password(password, salt),
        "created_at": time.time(),
    })
    _save_users(users)


def verify_user_credentials(email: str, password: str) -> bool:
    """Mode 'self_signup' : verifie (email, password) contre api/users.json."""
    email_normalise = (email or "").strip().lower()
    for user in _load_users():
        if user.get("email") == email_normalise:
            return hmac.compare_digest(hash_password(password, user["salt"]), user["password_hash"])
    return False


def verify_firebase_id_token(id_token: str) -> dict:
    """Mode 'firebase' : verification cote serveur d'un ID token Firebase.
    Necessite le package `firebase-admin` ET un vrai projet Firebase (variable
    d'environnement GOOGLE_APPLICATION_CREDENTIALS pointant vers un fichier de
    compte de service). Ni l'un ni l'autre n'est disponible dans cet
    environnement de demonstration : leve une erreur 501 explicite plutot que
    de simuler une reussite."""
    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth, credentials
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Mode 'firebase' active mais le package 'firebase-admin' n'est pas installe "
                "cote serveur (pip install firebase-admin)."
            ),
        )
    if not firebase_admin._apps:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=(
                    "Mode 'firebase' active mais aucun projet Firebase n'est configure "
                    "(definissez GOOGLE_APPLICATION_CREDENTIALS vers votre fichier de compte "
                    "de service). Voir README, section Authentification."
                ),
            )
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"ID token Firebase invalide : {exc}")


def require_org_auth(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Dependance FastAPI protegeant les endpoints reserves a l'Espace
    Organisation (predict*, model_info). AUTH_MODE est relu a chaque appel."""
    mode = os.environ.get("AUTH_MODE", "none")
    if mode == "none":
        return None
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise : en-tete 'Authorization: Bearer <jeton>' manquant.",
        )
    token = authorization.split(" ", 1)[1].strip()
    if mode == "firebase":
        return verify_firebase_id_token(token)
    if mode in ("shared_password", "per_org", "self_signup"):
        return _verify_token(token)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"AUTH_MODE inconnu : {mode}")
