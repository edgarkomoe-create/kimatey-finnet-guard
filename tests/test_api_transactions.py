"""
Tests unitaires - endpoints API de fraude transactionnelle (PROTOTYPE).

*** Comble un trou de couverture signale dans le README : ces endpoints
(predict_transaction, predict_transaction_csv) n'avaient jusqu'ici aucun
test automatise, contrairement a leurs equivalents reseau (voir test_api.py). ***

Meme approche que test_api.py : fastapi.testclient.TestClient, pas de serveur
reseau reel. AUTH_MODE n'est pas definie dans cet environnement de test, donc
require_org_auth() retourne None sans exiger de jeton (voir api/auth.py) -
coherent avec test_api.py qui suit le meme principe pour les endpoints reseau.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app

# Transaction clairement legitime (voir src/transaction_fraud/generate_synthetic_data.py
# pour la logique de generation - ce jeu de valeurs correspond au profil "legitime").
TRANSACTION_LEGITIME = {
    "Montant": 15000.0,
    "Ecart_Montant_Habituel": 0.1,
    "Nouveau_Destinataire": 0,
    "Heure_Transaction": 14,
    "Frequence_Transactions_24h": 2,
    "Delai_Depuis_Derniere_Min": 200.0,
    "Nb_Destinataires_Distincts_7j": 2,
    "Changement_Appareil": 0,
}

# Profil "compte compromis" (voir generate_synthetic_data.py, sous-type de fraude 1) :
# montant eleve, nouveau destinataire, heure atypique, nouvel appareil.
TRANSACTION_SUSPECTE = {
    "Montant": 250000.0,
    "Ecart_Montant_Habituel": 4.5,
    "Nouveau_Destinataire": 1,
    "Heure_Transaction": 3,
    "Frequence_Transactions_24h": 1,
    "Delai_Depuis_Derniere_Min": 10.0,
    "Nb_Destinataires_Distincts_7j": 1,
    "Changement_Appareil": 1,
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestPredictTransactionUnique:
    def test_transaction_legitime_retourne_200_avec_avertissement_prototype(self, client):
        r = client.post("/predict_transaction", json=TRANSACTION_LEGITIME)
        assert r.status_code == 200
        body = r.json()
        assert body["prediction"] in ("Legitime", "Suspecte")
        assert 0 <= body["confidence"] <= 100
        assert body["is_prototype"] is True
        assert "SYNTHETIQUES" in body["avertissement"]

    def test_transaction_manifestement_suspecte_est_detectee(self, client):
        """Le profil 'compte compromis' (montant eleve, nouveau destinataire,
        heure atypique, nouvel appareil) doit etre reconnu comme suspect -
        c'est le pattern le plus net du generateur synthetique."""
        r = client.post("/predict_transaction", json=TRANSACTION_SUSPECTE)
        assert r.status_code == 200
        assert r.json()["prediction"] == "Suspecte"

    def test_champ_manquant_rejete_422(self, client):
        payload = dict(TRANSACTION_LEGITIME)
        del payload["Montant"]
        r = client.post("/predict_transaction", json=payload)
        assert r.status_code == 422

    def test_nouveau_destinataire_hors_bornes_rejete_422(self, client):
        """Nouveau_Destinataire doit etre 0 ou 1 (voir Field(ge=0, le=1) dans
        api/schemas.py) - une valeur type '2' doit etre rejetee, pas silencieusement
        acceptee comme vraie."""
        payload = dict(TRANSACTION_LEGITIME)
        payload["Nouveau_Destinataire"] = 2
        r = client.post("/predict_transaction", json=payload)
        assert r.status_code == 422

    def test_heure_hors_bornes_rejetee_422(self, client):
        payload = dict(TRANSACTION_LEGITIME)
        payload["Heure_Transaction"] = 24
        r = client.post("/predict_transaction", json=payload)
        assert r.status_code == 422


class TestPredictTransactionCsv:
    def test_lot_de_transactions_traite_et_resume_correctement(self, client, tmp_path):
        df = pd.DataFrame([TRANSACTION_LEGITIME, TRANSACTION_SUSPECTE, TRANSACTION_LEGITIME])
        csv_path = tmp_path / "transactions_test.csv"
        df.to_csv(csv_path, index=False)

        with open(csv_path, "rb") as f:
            r = client.post(
                "/predict_transaction_csv",
                files={"file": ("transactions_test.csv", f, "text/csv")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["n_total"] == 3
        assert 0 <= body["n_suspectes"] <= 3
        assert body["taux_suspect"] == pytest.approx(body["n_suspectes"] / 3 * 100, abs=0.1)
        assert body["is_prototype"] is True

    def test_lot_journalise_les_alertes_avec_le_domaine_transactions(self, client, tmp_path, monkeypatch):
        """Les transactions suspectes importees en lot doivent atterrir dans le
        journal du domaine 'transactions', jamais dans celui de 'reseau' -
        meme garde-fou d'isolation que teste plus en detail dans
        tests/test_persistence_postgresql.py, ici verifie de bout en bout via l'API."""
        from core import alert_log
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr(alert_log, "BASE_DIR", tmp_path)

        df = pd.DataFrame([TRANSACTION_SUSPECTE])
        csv_path = tmp_path / "une_transaction.csv"
        df.to_csv(csv_path, index=False)
        with open(csv_path, "rb") as f:
            client.post(
                "/predict_transaction_csv",
                files={"file": ("une_transaction.csv", f, "text/csv")},
            )

        reseau_state = alert_log.load_org_state(domaine="reseau")
        tx_state = alert_log.load_org_state(domaine="transactions")
        assert reseau_state["alert_log"] == []
        assert len(tx_state["alert_log"]) >= 1
        assert tx_state["alert_log"][0]["Menace"] == "Suspecte"


class TestCoherenceServiceTransactionnel:
    """Verifie que le service utilise par l'API est bien le meme objet que
    celui documente/utilise par Streamlit (meme pattern que
    TestCoherenceApiPipeline dans test_api.py pour le modele reseau)."""

    def test_le_modele_charge_correspond_aux_metadonnees_declarees(self):
        from api.transaction_model_service import get_transaction_model_service
        service = get_transaction_model_service()
        assert service.info["donnees"].startswith("SYNTHETIQUES")
        assert set(service.features) == {
            "Montant", "Ecart_Montant_Habituel", "Nouveau_Destinataire", "Heure_Transaction",
            "Frequence_Transactions_24h", "Delai_Depuis_Derniere_Min",
            "Nb_Destinataires_Distincts_7j", "Changement_Appareil",
        }
