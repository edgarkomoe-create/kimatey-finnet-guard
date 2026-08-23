"""
Tests unitaires - API REST FastAPI.
Utilise fastapi.testclient.TestClient (requetes HTTP in-process, sans lancer
de serveur reseau reel) pour valider chaque endpoint : codes de statut,
schemas de reponse, et coherence des predictions avec le pipeline ML.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app

EXEMPLE_FLUX = {
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


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestEndpointsMeta:
    def test_racine_retourne_liste_endpoints(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["service"] == "SOC Threat Detection API"
        for ep in ["/health", "/model_info", "/predict", "/predict_batch", "/predict_csv"]:
            assert ep in body["endpoints"]

    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["model_loaded"] is True

    def test_model_info_coherent_avec_le_pipeline(self, client):
        r = client.get("/model_info")
        assert r.status_code == 200
        body = r.json()
        assert body["model_name"] == "Arbre_Decision_optimise"
        assert 0 <= body["accuracy"] <= 1
        assert 0 <= body["f1_macro"] <= 1
        assert 0 <= body["auc_macro"] <= 1
        assert len(body["features_used"]) == 5
        assert len(body["all_features"]) == 9
        assert len(body["classes"]) == 4


class TestPredictionUnique:
    def test_predict_flux_valide(self, client):
        r = client.post("/predict", json=EXEMPLE_FLUX)
        assert r.status_code == 200
        body = r.json()
        assert body["predicted_class"] in [0, 1, 2, 3]
        assert body["predicted_label"] in [
            "Normal / Legitime",
            "Scan de Ports / Reconnaissance",
            "Attaque DDoS / Volumetrique",
            "Infiltration / Brute-Force / Exfiltration",
        ]
        assert 0 <= body["confidence"] <= 100
        assert len(body["probabilities"]) == 4
        assert abs(sum(body["probabilities"].values()) - 100) < 0.5
        assert body["is_threat"] == (body["predicted_class"] != 0)

    def test_predict_champ_manquant_rejete_422(self, client):
        flux_incomplet = dict(EXEMPLE_FLUX)
        del flux_incomplet["Duree_Connexion"]
        r = client.post("/predict", json=flux_incomplet)
        assert r.status_code == 422

    def test_predict_valeur_negative_rejetee_422(self, client):
        flux_invalide = dict(EXEMPLE_FLUX)
        flux_invalide["Taux_Paquets_Secondes"] = -10.0
        r = client.post("/predict", json=flux_invalide)
        assert r.status_code == 422

    def test_predict_type_invalide_rejete_422(self, client):
        flux_invalide = dict(EXEMPLE_FLUX)
        flux_invalide["Duree_Connexion"] = "pas_un_nombre"
        r = client.post("/predict", json=flux_invalide)
        assert r.status_code == 422


class TestPredictionBatch:
    def test_predict_batch_liste_vide_rejetee_400(self, client):
        r = client.post("/predict_batch", json={"flows": []})
        assert r.status_code == 400

    def test_predict_batch_plusieurs_flux(self, client):
        flux2 = dict(EXEMPLE_FLUX)
        flux2["Taux_Paquets_Secondes"] = 50000.0
        flux2["Ports_Dest_Distincts"] = 900
        r = client.post("/predict_batch", json={"flows": [EXEMPLE_FLUX, flux2]})
        assert r.status_code == 200
        body = r.json()
        assert body["summary"]["n_flows"] == 2
        assert len(body["predictions"]) == 2
        assert body["summary"]["n_threats"] == sum(
            1 for p in body["predictions"] if p["is_threat"]
        )


class TestPredictionCSV:
    def test_predict_csv_fichier_demo_coherent_avec_streamlit(self, client):
        """Le fichier de demo doit produire exactement le meme resultat que celui
        deja observe et verifie manuellement dans l'app Streamlit (16/50 menaces)."""
        with open("outputs/sample_logs_demo.csv", "rb") as f:
            r = client.post(
                "/predict_csv",
                files={"file": ("sample_logs_demo.csv", f, "text/csv")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["summary"]["n_flows"] == 50
        assert body["summary"]["n_threats"] == 16
        assert body["summary"]["threat_rate_pct"] == 32.0
        assert len(body["results"]) == 50
        assert "Menace_Predite" in body["results"][0]
        assert "Confiance_pct" in body["results"][0]

    def test_predict_csv_fichier_non_csv_rejete_400(self, client):
        r = client.post(
            "/predict_csv",
            files={"file": ("notes.txt", b"ceci n'est pas un csv", "text/plain")},
        )
        assert r.status_code == 400

    def test_predict_csv_fichier_vide_rejete_400(self, client):
        r = client.post(
            "/predict_csv",
            files={"file": ("vide.csv", b"", "text/csv")},
        )
        assert r.status_code == 400


class TestCoherenceApiPipeline:
    """Verifie que l'API produit exactement les memes predictions que le
    modele charge directement (pas de divergence de pretraitement)."""

    def test_api_et_modele_direct_predisent_identique(self, client):
        import joblib
        import json as _json

        df_demo = pd.read_csv("outputs/sample_logs_demo.csv")
        r = client.post(
            "/predict_batch",
            json={"flows": df_demo.to_dict(orient="records")},
        )
        assert r.status_code == 200
        api_preds = [p["predicted_class"] for p in r.json()["predictions"]]

        # reproduit le pretraitement (imputation -> IQR -> scaling -> selection)
        # exactement comme api/model_service.py, pour comparaison independante
        medians = joblib.load("outputs/models/imputation_medians.joblib")
        bounds = joblib.load("outputs/models/iqr_bounds.joblib")
        scaler = joblib.load("outputs/models/scaler.joblib")
        feature_names = joblib.load("outputs/models/feature_names.joblib")
        with open("outputs/selected_features.json") as f:
            selected = _json.load(f)["selected_features"]
        model = joblib.load("outputs/models/best_model.joblib")

        df = df_demo.copy()
        for col, med in medians.items():
            df[col] = df[col].fillna(med)
        for col, (low, high) in bounds.items():
            df[col] = df[col].clip(low, high)
        X_scaled = scaler.transform(df[feature_names])
        X_scaled_df = pd.DataFrame(X_scaled, columns=feature_names)
        direct_preds = model.predict(X_scaled_df[selected])

        assert list(api_preds) == list(direct_preds)
