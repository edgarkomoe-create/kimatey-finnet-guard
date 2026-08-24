"""
Tests unitaires - Espace Grand Public (assistant, sensibilisation, collecte
participative) et authentification de l'Espace Organisation (api/auth.py).

Utilise fastapi.testclient.TestClient comme tests/test_api.py. AUTH_MODE et
SHARED_ORG_PASSWORD sont manipules via `monkeypatch.setenv`, ce qui est possible
sans redemarrer l'application ni recreer un TestClient : api.auth.require_org_auth
relit ces variables d'environnement a CHAQUE requete (voir docstring du module),
justement pour rester testable ainsi.
"""
import json

import pytest
from fastapi.testclient import TestClient

import api.auth as auth
import api.main as main
from api.main import app

EXEMPLE_TEMOIGNAGE = {
    "canal": "📱 Un SMS",
    "demande": "💰 De l'argent",
    "reaction": "🚫 J'ai ignoré / raccroché",
}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _isolate_temoignages_file(tmp_path, monkeypatch):
    """Redirige le fichier de contributions vers un chemin temporaire pour ne
    jamais ecrire dans le vrai outputs/temoignages.jsonl du projet pendant les
    tests, et pour que chaque test reparte d'un compteur a zero."""
    monkeypatch.setattr(main, "TEMOIGNAGES_FILE", tmp_path / "temoignages.jsonl")


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    """Garantit qu'aucun residu d'AUTH_MODE/SHARED_ORG_PASSWORD d'un test
    precedent ne fuite vers le suivant (monkeypatch restaure l'environnement
    automatiquement a la fin de chaque test, donc ceci est surtout documentaire :
    chaque test qui a besoin d'un mode particulier le fixe explicitement)."""
    monkeypatch.delenv("AUTH_MODE", raising=False)


class TestScenariosEtReportSteps:
    """Contenu du mini-jeu et du parcours de collecte, expose a l'identique de
    ce qu'utilise l'application Streamlit (meme source : core/kimatey_core.py)."""

    def test_scenarios_retourne_3_scenarios_bien_formes(self, client):
        r = client.get("/scenarios")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 3
        for s in body:
            assert set(["situation", "choices", "correct", "explanation"]) <= set(s.keys())
            assert 0 <= s["correct"] < len(s["choices"])

    def test_report_steps_retourne_3_etapes_bien_formees(self, client):
        r = client.get("/report_steps")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 3
        for step in body:
            assert set(["key", "question", "options"]) <= set(step.keys())
            assert len(step["options"]) >= 2


class TestJeuDeVigilanceGamifie:
    """Mecanique de gamification : categories thematiques, mascottes, niveaux et badges -
    exposes a l'identique de ce qu'utilise l'application Streamlit (meme source :
    core/kimatey_core.py)."""

    def test_game_categories_retourne_6_categories_bien_formees(self, client):
        r = client.get("/game/categories")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 6
        cles_attendues = {"mobile_money", "banque", "ingenierie_sociale", "reseaux_sociaux", "aines", "cyber"}
        assert {c["key"] for c in body} == cles_attendues
        for cat in body:
            assert set(["key", "label", "emoji", "mascot_key", "mascot_name", "mascot_intro", "scenarios"]) <= set(cat.keys())
            assert len(cat["scenarios"]) >= 2
            for s in cat["scenarios"]:
                assert set(["situation", "choices", "correct", "explanation"]) <= set(s.keys())
                assert 0 <= s["correct"] < len(s["choices"])

    def test_categorie_mobile_money_reste_les_3_scenarios_historiques(self, client):
        """La categorie mobile_money doit continuer a exposer exactement les memes
        3 scenarios que l'endpoint /scenarios historique (aucune duplication de
        contenu, une seule source de verite dans core/kimatey_core.py)."""
        r_cat = client.get("/game/categories")
        r_legacy = client.get("/scenarios")
        mobile_money = next(c for c in r_cat.json() if c["key"] == "mobile_money")
        situations_cat = [s["situation"] for s in mobile_money["scenarios"]]
        situations_legacy = [s["situation"] for s in r_legacy.json()]
        assert situations_cat == situations_legacy

    def test_toutes_categories_partagent_la_meme_ia_lieutenant_cyber(self, client):
        """Une seule IA originale (Lieutenant Cyber, propre a Kimatey) traverse toutes les
        categories - decision prise apres discussion avec l'utilisateur pour ne pas faire
        reference a une mascotte externe, afin d'eviter tout lien de marque non voulu avec
        ce produit."""
        r = client.get("/game/categories")
        for cat in r.json():
            assert cat["mascot_name"] == "Lieutenant Cyber"
            assert "vivi" not in cat["mascot_intro"].lower()

    def test_game_meta_expose_regles_du_jeu(self, client):
        r = client.get("/game/meta")
        assert r.status_code == 200
        body = r.json()
        assert body["xp_per_correct"] > body["xp_per_incorrect"] > 0
        assert body["max_hearts"] >= 1
        assert len(body["levels"]) >= 2
        assert len(body["badges"]) >= 1
        # Les Points Bouclier n'ont aucune conversion monetaire : verifie qu'aucun
        # champ de type "valeur reelle"/"conversion" n'est expose par l'API.
        assert "valeur_reelle" not in body
        assert "conversion" not in body


class TestAssistantChat:
    def test_sans_cle_gemini_renvoie_503_explicite(self, client, monkeypatch):
        """Sans GEMINI_API_KEY configuree cote serveur, l'endpoint doit refuser
        proprement (503 avec un message clair), jamais planter ni renvoyer 200
        avec un contenu vide."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        r = client.post("/assistant/chat", json={"message": "Bonjour"})
        assert r.status_code == 503
        assert "GEMINI_API_KEY" in r.json()["detail"]

    def test_message_vide_rejete_422(self, client):
        r = client.post("/assistant/chat", json={"message": ""})
        assert r.status_code == 422

    def test_champ_message_manquant_rejete_422(self, client):
        r = client.post("/assistant/chat", json={})
        assert r.status_code == 422


class TestLieutenantCyberExplicationOrganisation:
    """Nouveaux endpoints Organisation (proteges par AUTH_MODE, contrairement au pole
    Grand Public) : Lieutenant Cyber - la meme IA que celle du chat public - commente
    en langage clair un resultat DEJA calcule par le modele (jamais elle qui classifie)."""

    EXEMPLE_FLOW = {
        "predicted_class": 1, "predicted_label": "Scan de Ports", "confidence": 91.2,
        "probabilities": {"Normal": 5.0, "Scan": 91.2, "DDoS": 2.0, "Infiltration": 1.8},
        "features": {"Ports_Dest_Distincts": 800, "Taux_Paquets_Secondes": 120.5},
    }
    EXEMPLE_BATCH = {
        "n_flows": 50, "n_threats": 16, "threat_rate_pct": 32.0,
        "class_distribution": {"Normal": 34, "Scan": 10, "DDoS": 4, "Infiltration": 2},
    }

    def test_explain_flow_sans_cle_gemini_renvoie_503(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        r = client.post("/organisation/explain_flow", json=self.EXEMPLE_FLOW)
        assert r.status_code == 503
        assert "GEMINI_API_KEY" in r.json()["detail"]

    def test_explain_batch_sans_cle_gemini_renvoie_503(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        r = client.post("/organisation/explain_batch", json=self.EXEMPLE_BATCH)
        assert r.status_code == 503
        assert "GEMINI_API_KEY" in r.json()["detail"]

    def test_explain_flow_protege_par_auth_mode(self, client, monkeypatch):
        """Contrairement au pole Grand Public, ces endpoints appartiennent a
        l'Espace Organisation : ils doivent donc etre soumis a AUTH_MODE comme
        /predict, /model_info, etc."""
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        monkeypatch.setenv("SHARED_ORG_PASSWORD", "TestPassword123")
        r = client.post("/organisation/explain_flow", json=self.EXEMPLE_FLOW)
        assert r.status_code == 401

    def test_explain_batch_protege_par_auth_mode(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        monkeypatch.setenv("SHARED_ORG_PASSWORD", "TestPassword123")
        r = client.post("/organisation/explain_batch", json=self.EXEMPLE_BATCH)
        assert r.status_code == 401

    def test_explain_flow_champs_manquants_rejete_422(self, client):
        r = client.post("/organisation/explain_flow", json={})
        assert r.status_code == 422

    def test_explain_batch_champs_manquants_rejete_422(self, client):
        r = client.post("/organisation/explain_batch", json={})
        assert r.status_code == 422


class TestTemoignage:
    def test_temoignage_structure_sans_detail(self, client):
        r = client.post("/temoignage", json=EXEMPLE_TEMOIGNAGE)
        assert r.status_code == 200
        body = r.json()
        assert "SMS" in body["fiche"]
        assert "argent" in body["fiche"]
        assert body["total_contributions"] == 1

    def test_temoignage_compteur_incremente_a_chaque_contribution(self, client):
        client.post("/temoignage", json=EXEMPLE_TEMOIGNAGE)
        r = client.post("/temoignage", json=EXEMPLE_TEMOIGNAGE)
        assert r.json()["total_contributions"] == 2
        r_count = client.get("/temoignages/count")
        assert r_count.json()["count"] == 2

    def test_temoignage_avec_detail_sans_cle_gemini_reste_utilisable(self, client, monkeypatch):
        """Sans cle Gemini, la synthese IA du recit libre est simplement ignoree
        (pas d'exception) : la fiche structuree (canal/demande/reaction) est
        quand meme enregistree - comportement volontairement tolerant, documente
        dans le rapport de projet."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        payload = dict(EXEMPLE_TEMOIGNAGE, detail="Un detail quelconque raconte librement.")
        r = client.post("/temoignage", json=payload)
        assert r.status_code == 200
        assert "SMS" in r.json()["fiche"]

    def test_champ_obligatoire_manquant_rejete_422(self, client):
        payload = dict(EXEMPLE_TEMOIGNAGE)
        del payload["canal"]
        r = client.post("/temoignage", json=payload)
        assert r.status_code == 422


class TestAuthModeNone:
    """Comportement par defaut (historique) : aucune authentification."""

    def test_model_info_accessible_sans_en_tete(self, client):
        r = client.get("/model_info")
        assert r.status_code == 200

    def test_login_en_mode_none_ne_reclame_aucun_jeton(self, client):
        r = client.post("/auth/login", json={"password": "peu importe"})
        assert r.status_code == 200
        body = r.json()
        assert body["token"] is None
        assert body["auth_mode"] == "none"


class TestAuthModeSharedPassword:
    def test_endpoint_organisation_refuse_sans_en_tete(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        r = client.get("/model_info")
        assert r.status_code == 401

    def test_login_mauvais_mot_de_passe_rejete(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        monkeypatch.setenv("SHARED_ORG_PASSWORD", "secret123")
        r = client.post("/auth/login", json={"password": "faux"})
        assert r.status_code == 401

    def test_login_puis_acces_avec_jeton_fonctionne(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        monkeypatch.setenv("SHARED_ORG_PASSWORD", "secret123")
        r = client.post("/auth/login", json={"password": "secret123"})
        assert r.status_code == 200
        token = r.json()["token"]
        assert token
        r2 = client.get("/model_info", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200

    def test_jeton_invalide_rejete(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        r = client.get("/model_info", headers={"Authorization": "Bearer un.jeton.invente"})
        assert r.status_code == 401


class TestAuthModePerOrg:
    @pytest.fixture()
    def orgs_de_test(self, tmp_path, monkeypatch):
        """Isole les tests d'un vrai fichier orgs.json : cree un fichier
        temporaire avec une seule organisation de test dont on connait le mot
        de passe en clair."""
        salt = "sel_de_test"
        password = "MotDePasseDeTest!"
        org = {
            "org_id": "org_test",
            "org_name": "Organisation de test",
            "salt": salt,
            "password_hash": auth.hash_password(password, salt),
        }
        orgs_file = tmp_path / "orgs_test.json"
        orgs_file.write_text(json.dumps([org]))
        monkeypatch.setattr(auth, "ORGS_FILE", orgs_file)
        return {"org_id": "org_test", "password": password}

    def test_login_org_id_manquant_rejete_400(self, client, monkeypatch, orgs_de_test):
        monkeypatch.setenv("AUTH_MODE", "per_org")
        r = client.post("/auth/login", json={"password": orgs_de_test["password"]})
        assert r.status_code == 400

    def test_login_mauvais_mot_de_passe_rejete_401(self, client, monkeypatch, orgs_de_test):
        monkeypatch.setenv("AUTH_MODE", "per_org")
        r = client.post("/auth/login", json={"org_id": orgs_de_test["org_id"], "password": "faux"})
        assert r.status_code == 401

    def test_login_organisation_inconnue_rejetee_401(self, client, monkeypatch, orgs_de_test):
        monkeypatch.setenv("AUTH_MODE", "per_org")
        r = client.post("/auth/login", json={"org_id": "inconnu", "password": orgs_de_test["password"]})
        assert r.status_code == 401

    def test_login_puis_acces_avec_jeton_fonctionne(self, client, monkeypatch, orgs_de_test):
        monkeypatch.setenv("AUTH_MODE", "per_org")
        r = client.post("/auth/login", json={"org_id": orgs_de_test["org_id"], "password": orgs_de_test["password"]})
        assert r.status_code == 200
        token = r.json()["token"]
        r2 = client.get("/model_info", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200


class TestAuthModeSelfSignup:
    """Auto-inscription par email + mot de passe (api/users.json) : rend le MVP
    reellement "connectable" (creer un compte puis se connecter) sans dependre
    d'un vrai projet Firebase externe."""

    @pytest.fixture(autouse=True)
    def _isolate_users_file(self, tmp_path, monkeypatch):
        """Isole chaque test d'un vrai fichier users.json (fichier temporaire
        vide a chaque test, jamais le vrai fichier livre avec le projet)."""
        monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "users_test.json")

    def test_creation_de_compte_hors_mode_self_signup_rejetee_400(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "shared_password")
        r = client.post("/auth/register", json={"email": "test@exemple.com", "password": "motdepasse"})
        assert r.status_code == 400

    def test_creation_de_compte_email_invalide_rejetee_422(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        r = client.post("/auth/register", json={"email": "pas-un-email", "password": "motdepasse"})
        assert r.status_code == 422

    def test_creation_de_compte_mot_de_passe_trop_court_rejete_422(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        r = client.post("/auth/register", json={"email": "test@exemple.com", "password": "123"})
        assert r.status_code == 422

    def test_creation_de_compte_puis_connexion_fonctionnent(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        r = client.post("/auth/register", json={"email": "Nouvel.Utilisateur@Exemple.com", "password": "motdepasse123"})
        assert r.status_code == 200
        token_inscription = r.json()["token"]
        assert token_inscription
        # Le compte cree est deja connecte (jeton d'inscription utilisable immediatement).
        r_acces = client.get("/model_info", headers={"Authorization": f"Bearer {token_inscription}"})
        assert r_acces.status_code == 200
        # Et on peut aussi se reconnecter plus tard avec le meme email (insensible a la casse) + mot de passe.
        r_login = client.post(
            "/auth/login",
            json={"email": "nouvel.utilisateur@exemple.com", "password": "motdepasse123"},
        )
        assert r_login.status_code == 200
        token_connexion = r_login.json()["token"]
        r_acces2 = client.get("/model_info", headers={"Authorization": f"Bearer {token_connexion}"})
        assert r_acces2.status_code == 200

    def test_creation_de_compte_email_deja_utilise_rejetee_409(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        client.post("/auth/register", json={"email": "double@exemple.com", "password": "motdepasse123"})
        r = client.post("/auth/register", json={"email": "double@exemple.com", "password": "autremdp123"})
        assert r.status_code == 409

    def test_connexion_email_inconnu_rejetee_401(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        r = client.post("/auth/login", json={"email": "inconnu@exemple.com", "password": "peu importe"})
        assert r.status_code == 401

    def test_connexion_sans_email_rejetee_400(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        r = client.post("/auth/login", json={"password": "peu importe"})
        assert r.status_code == 400

    def test_connexion_mauvais_mot_de_passe_rejetee_401(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        client.post("/auth/register", json={"email": "test2@exemple.com", "password": "motdepasse123"})
        r = client.post("/auth/login", json={"email": "test2@exemple.com", "password": "faux"})
        assert r.status_code == 401


class TestAuthModeFirebase:
    """Mode non operationnel dans cet environnement de demonstration (pas de
    package firebase-admin ni de vrai projet Firebase) : on verifie que
    l'echec est explicite (501), jamais une fausse reussite silencieuse."""

    def test_login_oriente_vers_le_flux_cote_client(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "firebase")
        r = client.post("/auth/login", json={"password": "peu importe"})
        assert r.status_code == 400
        assert "Firebase" in r.json()["detail"] or "SDK" in r.json()["detail"]

    def test_acces_sans_projet_firebase_configure_rejete_501(self, client, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "firebase")
        r = client.get("/model_info", headers={"Authorization": "Bearer un_id_token_firebase_quelconque"})
        assert r.status_code == 501
        assert "firebase-admin" in r.json()["detail"] or "Firebase" in r.json()["detail"]
