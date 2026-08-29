"""
Tests de la couche de persistance PostgreSQL (core/db.py + core/alert_log.py).

*** Comble un trou de couverture signale honnetement dans le README depuis la
migration Neon : cette couche n'avait jusqu'ici AUCUN test automatise. ***

Approche : aucune vraie base de donnees n'est necessaire pour la majorite de
ces tests - core/db.py expose un seul point d'entree (`get_connection()`)
que l'on remplace par un faux objet (`_FakeConnection`/`_FakeCursor`) qui
enregistre les requetes SQL executees et leurs parametres. Cela permet de
verifier la LOGIQUE (quelle requete part avec quels parametres, isolation
entre domaines, comportement de repli JSON) sans dependre d'une base externe,
d'un reseau, ou d'identifiants - donc rapide, deterministe, executable en CI.

Un test d'integration reel (contre une vraie base) est delibere hors
perimetre ici : il necessiterait une base Neon dediee aux tests et des
identifiants secrets, ce qui n'a pas sa place dans une suite pytest locale.
Voir la classe TestIntegrationReelleOptionnelle en bas de fichier pour le
point d'ancrage si une base de test devient disponible (skip automatique
sinon).
"""
import os

import pytest

from core import db, alert_log


# ======================================================================
# Doubles de test pour simuler une connexion psycopg sans base reelle
# ======================================================================
class _FakeCursor:
    """Enregistre chaque requete executee (SQL + parametres) et retourne des
    lignes pre-configurees pour fetchone()/fetchall(), a la maniere d'un
    faux cursor psycopg minimal."""

    def __init__(self, fetchall_result=None, fetchone_result=None):
        self.executed = []  # liste de (sql, params)
        self.executemany_calls = []  # liste de (sql, liste_de_params)
        self._fetchall_result = fetchall_result or []
        self._fetchone_result = fetchone_result

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, seq_of_params):
        self.executemany_calls.append((sql, list(seq_of_params)))

    def fetchall(self):
        return self._fetchall_result

    def fetchone(self):
        return self._fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConnection:
    """Un seul cursor partage (recupere via .cursor()), pour pouvoir inspecter
    apres coup toutes les requetes executees pendant le `with get_connection()`."""

    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _patch_connection(monkeypatch, cursor):
    """Remplace core.db.get_connection() par un context manager qui fournit
    une _FakeConnection enveloppant `cursor`, et force database_configured()
    a True (comme si DATABASE_URL etait definie)."""
    from contextlib import contextmanager

    fake_conn = _FakeConnection(cursor)

    @contextmanager
    def _fake_get_connection():
        yield fake_conn

    monkeypatch.setattr(db, "get_connection", _fake_get_connection)
    monkeypatch.setattr(db, "database_configured", lambda: True)
    monkeypatch.setattr(db, "init_schema", lambda: None)  # deja teste separement
    return fake_conn


# ======================================================================
# core/db.py - configuration et garde-fous
# ======================================================================
class TestDatabaseConfigured:
    def test_non_configuree_sans_database_url(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert db.database_configured() is False

    def test_configuree_quand_database_url_et_psycopg_presents(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")
        monkeypatch.setattr(db, "PSYCOPG_AVAILABLE", True)
        assert db.database_configured() is True

    def test_non_configuree_si_psycopg_absent_meme_avec_url(self, monkeypatch):
        """Garde-fou : si le pilote psycopg n'est pas installe, on ne doit
        jamais pretendre que la base est utilisable meme si DATABASE_URL
        traine dans l'environnement."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")
        monkeypatch.setattr(db, "PSYCOPG_AVAILABLE", False)
        assert db.database_configured() is False

    def test_get_connection_leve_runtimeerror_si_non_configuree(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError):
            with db.get_connection():
                pass


class TestInitSchema:
    def test_init_schema_noop_si_non_configuree(self, monkeypatch):
        """Ne doit jamais tenter de se connecter si aucune base n'est
        configuree - sinon un simple `python -m pytest` sans DATABASE_URL
        planterait au lieu de basculer sur le repli JSON."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        called = {"connected": False}

        def _should_not_be_called():
            called["connected"] = True
            raise AssertionError("get_connection() ne doit pas etre appelee")

        monkeypatch.setattr(db, "get_connection", _should_not_be_called)
        db.init_schema()
        assert called["connected"] is False

    def test_init_schema_cree_les_tables_et_la_colonne_de_migration(self, monkeypatch):
        cursor = _FakeCursor()
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")
        monkeypatch.setattr(db, "PSYCOPG_AVAILABLE", True)
        from contextlib import contextmanager

        fake_conn = _FakeConnection(cursor)

        @contextmanager
        def _fake_get_connection():
            yield fake_conn

        monkeypatch.setattr(db, "get_connection", _fake_get_connection)

        db.init_schema()

        all_sql = " ".join(sql for sql, _ in cursor.executed)
        assert "CREATE TABLE IF NOT EXISTS users" in all_sql
        assert "CREATE TABLE IF NOT EXISTS alerts" in all_sql
        assert "CREATE TABLE IF NOT EXISTS score_history" in all_sql
        # Migration douce pour les bases creees avant l'ajout du domaine :
        # doit etre presente pour 'alerts' ET 'score_history'.
        assert all_sql.count("ADD COLUMN IF NOT EXISTS domaine") == 2


# ======================================================================
# core/alert_log.py - chemin PostgreSQL (mocke)
# ======================================================================
class TestChargementEtSauvegardeEtatPg:
    def test_load_org_state_pg_mappe_correctement_les_colonnes(self, monkeypatch):
        alert_rows = [("abc123", "2026-08-01 10:00:00", "Import CSV", "Attaque DDoS / Volumetrique",
                        97.5, "", "Ouvert", None)]
        score_rows = [("2026-08-01 10:00:00", 82)]

        class _TwoQueryCursor(_FakeCursor):
            def execute(self, sql, params=None):
                super().execute(sql, params)
                if "FROM alerts" in sql:
                    self._fetchall_result = alert_rows
                elif "FROM score_history" in sql:
                    self._fetchall_result = score_rows

        cursor = _TwoQueryCursor()
        _patch_connection(monkeypatch, cursor)

        state = alert_log.load_org_state(domaine="reseau")

        assert state["alert_log"] == [{
            "ID": "abc123", "Horodatage": "2026-08-01 10:00:00", "Source": "Import CSV",
            "Menace": "Attaque DDoS / Volumetrique", "Confiance (%)": 97.5, "Details": "",
            "Statut": "Ouvert", "Fermee_le": None,
        }]
        assert state["score_history"] == [{"Horodatage": "2026-08-01 10:00:00", "Score": 82}]
        # Les deux requetes doivent filtrer explicitement sur le domaine demande.
        domaines_filtres = [params[0] for sql, params in cursor.executed if params]
        assert all(d == "reseau" for d in domaines_filtres)

    def test_save_org_state_pg_isole_le_domaine_transactions_du_domaine_reseau(self, monkeypatch):
        """Garde-fou le plus important de cette couche : sauvegarder l'etat
        du domaine 'transactions' ne doit JAMAIS emettre une requete liee au
        domaine 'reseau' (et reciproquement) - les deux produits doivent
        rester strictement etanches."""
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)

        state = {
            "alert_log": [{"ID": "tx1", "Horodatage": "2026-08-01 10:00:00", "Source": "S",
                            "Menace": "Suspecte", "Confiance (%)": 88.0, "Details": "", "Statut": "Ouvert",
                            "Fermee_le": None}],
            "score_history": [{"Horodatage": "2026-08-01 10:00:00", "Score": 90}],
        }
        alert_log.save_org_state(state, domaine="transactions")

        domaines_touches = {
            params[0] for sql, params in cursor.executed
            if params and ("domaine = %s" in sql or "VALUES (%s, %s" in sql)
        }
        # 'INSERT INTO alerts' a domaine en 2e position, pas en 1re - on verifie
        # plus precisement via les DELETE (domaine en 1re position, sans ambiguite).
        deletes = [params[0] for sql, params in cursor.executed if sql.startswith("DELETE")]
        assert deletes == ["transactions", "transactions"]
        assert "reseau" not in deletes

    def test_save_org_state_pg_reinjecte_les_alertes_dans_lordre_chronologique(self, monkeypatch):
        """alert_log est stocke le plus recent en tete (voir log_alert qui fait
        .insert(0, ...)) ; a la sauvegarde, l'INSERT doit re-inserer dans
        l'ordre chronologique (le plus ancien d'abord), pas dans l'ordre
        d'affichage - sinon `seq` (auto-increment) ne refleterait plus l'ordre
        temporel reel apres un reload."""
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)

        state = {
            "alert_log": [
                {"ID": "recent", "Horodatage": "2026-08-02 10:00:00", "Source": "S", "Menace": "Suspecte",
                 "Confiance (%)": 80.0, "Details": "", "Statut": "Ouvert", "Fermee_le": None},
                {"ID": "ancien", "Horodatage": "2026-08-01 10:00:00", "Source": "S", "Menace": "Suspecte",
                 "Confiance (%)": 80.0, "Details": "", "Statut": "Ouvert", "Fermee_le": None},
            ],
            "score_history": [],
        }
        alert_log.save_org_state(state, domaine="transactions")

        inserts = [params for sql, params in cursor.executed if sql.startswith("INSERT INTO alerts")]
        assert [p[0] for p in inserts] == ["ancien", "recent"]


class TestLogAlertPg:
    def test_pred_class_zero_ninsere_rien(self, monkeypatch):
        cursor = _FakeCursor()
        conn = _patch_connection(monkeypatch, cursor)
        alert_log.log_alert("Source X", pred_class=0, confidence=99.0, domaine="reseau")
        assert cursor.executed == []

    def test_pred_class_non_zero_insere_une_ligne_avec_le_bon_domaine(self, monkeypatch):
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)
        alert_log.log_alert("Import CSV - ligne 3", pred_class=2, confidence=91.234, domaine="reseau")
        assert len(cursor.executed) == 1
        sql, params = cursor.executed[0]
        assert sql.startswith("INSERT INTO alerts")
        assert params[1] == "reseau"  # domaine
        assert params[4] == "Attaque DDoS / Volumetrique"  # menace mappee depuis CLASS_NAMES
        assert params[5] == 91.2  # confiance arrondie a 1 decimale
        assert params[7] == "Ouvert"

    def test_domaine_transactions_utilise_le_mapping_a_deux_classes(self, monkeypatch):
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)
        alert_log.log_alert("CSV Transactions - ligne 1", pred_class=1, confidence=75.0, domaine="transactions")
        _, params = cursor.executed[0]
        assert params[4] == "Suspecte"


class TestLogAlertsBulkPg:
    def test_liste_vide_ne_touche_pas_a_la_base(self, monkeypatch):
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)
        n = alert_log.log_alerts_bulk([], domaine="reseau")
        assert n == 0
        assert cursor.executemany_calls == []

    def test_filtre_les_entrees_normales_et_utilise_executemany_une_seule_fois(self, monkeypatch):
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)
        entries = [
            {"source": "ligne 1", "pred_class": 0, "confidence": 99.0},  # normal, ignoree
            {"source": "ligne 2", "pred_class": 1, "confidence": 88.4},
            {"source": "ligne 3", "pred_class": 3, "confidence": 70.0},
        ]
        n = alert_log.log_alerts_bulk(entries, domaine="reseau")
        assert n == 2
        assert len(cursor.executemany_calls) == 1  # une seule transaction pour tout le lot
        _, rows = cursor.executemany_calls[0]
        assert len(rows) == 2


class TestToggleAlertStatusPg:
    def test_alerte_introuvable_retourne_false(self, monkeypatch):
        cursor = _FakeCursor(fetchone_result=None)
        _patch_connection(monkeypatch, cursor)
        assert alert_log.toggle_alert_status("inconnue", domaine="reseau") is False
        updates = [sql for sql, _ in cursor.executed if sql.startswith("UPDATE")]
        assert updates == []

    def test_alerte_ouverte_devient_fermee_avec_horodatage(self, monkeypatch):
        cursor = _FakeCursor(fetchone_result=("Ouvert",))
        _patch_connection(monkeypatch, cursor)
        assert alert_log.toggle_alert_status("abc123", domaine="reseau") is True
        update_sql, update_params = next((s, p) for s, p in cursor.executed if s.startswith("UPDATE"))
        assert update_params[0] == "Ferme"
        assert update_params[1] is not None  # Fermee_le renseignee

    def test_alerte_fermee_est_reouverte_sans_horodatage_de_fermeture(self, monkeypatch):
        cursor = _FakeCursor(fetchone_result=("Ferme",))
        _patch_connection(monkeypatch, cursor)
        assert alert_log.toggle_alert_status("abc123", domaine="reseau") is True
        _, update_params = next((s, p) for s, p in cursor.executed if s.startswith("UPDATE"))
        assert update_params[0] == "Ouvert"
        assert update_params[1] is None


class TestRecordScoreSnapshotPg:
    def test_insere_le_score_et_purge_au_dela_de_50_points(self, monkeypatch):
        cursor = _FakeCursor()
        _patch_connection(monkeypatch, cursor)
        monkeypatch.setattr(alert_log, "load_org_state", lambda domaine: {"alert_log": [], "score_history": []})
        alert_log.record_score_snapshot(77, domaine="reseau")
        sqls = [sql for sql, _ in cursor.executed]
        assert any(s.startswith("INSERT INTO score_history") for s in sqls)
        assert any("DELETE FROM score_history" in s and "LIMIT 50" in s for s in sqls)


# ======================================================================
# core/alert_log.py - chemin de repli JSON (sans base configuree)
# ======================================================================
class TestReplifichierJson:
    @pytest.fixture(autouse=True)
    def _sans_base_et_dossier_isole(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setattr(alert_log, "BASE_DIR", tmp_path)

    def test_etat_par_defaut_quand_aucun_fichier_nexiste(self):
        state = alert_log.load_org_state(domaine="reseau")
        assert state == {"alert_log": [], "score_history": []}

    def test_sauvegarde_puis_chargement_repique_les_memes_donnees(self):
        state = {"alert_log": [{"ID": "x1", "Statut": "Ouvert"}], "score_history": [{"Score": 55}]}
        alert_log.save_org_state(state, domaine="reseau")
        reloaded = alert_log.load_org_state(domaine="reseau")
        assert reloaded == state

    def test_domaines_reseau_et_transactions_sont_isoles_sur_deux_fichiers_distincts(self, tmp_path):
        alert_log.save_org_state({"alert_log": [{"ID": "reseau1"}], "score_history": []}, domaine="reseau")
        alert_log.save_org_state({"alert_log": [{"ID": "tx1"}], "score_history": []}, domaine="transactions")

        assert (tmp_path / "outputs" / "organisation_state.json").exists()
        assert (tmp_path / "outputs" / "organisation_state_transactions.json").exists()

        reseau_state = alert_log.load_org_state(domaine="reseau")
        tx_state = alert_log.load_org_state(domaine="transactions")
        assert reseau_state["alert_log"][0]["ID"] == "reseau1"
        assert tx_state["alert_log"][0]["ID"] == "tx1"

    def test_log_alert_json_insere_en_tete_de_liste(self):
        alert_log.log_alert("Premiere", pred_class=1, confidence=90.0, domaine="reseau")
        alert_log.log_alert("Seconde", pred_class=2, confidence=80.0, domaine="reseau")
        state = alert_log.load_org_state(domaine="reseau")
        assert [a["Source"] for a in state["alert_log"]] == ["Seconde", "Premiere"]

    def test_toggle_alert_status_json_bascule_ouvert_ferme(self):
        alert_log.log_alert("Une alerte", pred_class=1, confidence=90.0, domaine="reseau")
        alert_id = alert_log.load_org_state(domaine="reseau")["alert_log"][0]["ID"]
        assert alert_log.toggle_alert_status(alert_id, domaine="reseau") is True
        state = alert_log.load_org_state(domaine="reseau")
        assert state["alert_log"][0]["Statut"] == "Ferme"
        assert state["alert_log"][0]["Fermee_le"] is not None


# ======================================================================
# core/alert_log.py - logique metier pure (aucune I/O, aucune base)
# ======================================================================
class TestComputeSecurityScore:
    def test_aucune_alerte_ouverte_donne_100(self):
        assert alert_log.compute_security_score([]) == 100
        alertes = [{"Statut": "Ferme", "Menace": "Infiltration / Brute-Force / Exfiltration"}]
        assert alert_log.compute_security_score(alertes) == 100

    def test_alertes_fermees_ne_penalisent_jamais_le_score(self):
        ouvertes_seules = [{"Statut": "Ouvert", "Menace": "Scan de Ports / Reconnaissance"}]
        avec_fermees = ouvertes_seules + [
            {"Statut": "Ferme", "Menace": "Infiltration / Brute-Force / Exfiltration"} for _ in range(20)
        ]
        assert alert_log.compute_security_score(ouvertes_seules) == alert_log.compute_security_score(avec_fermees)

    def test_score_plus_bas_pour_infiltration_que_pour_scan(self):
        scan = [{"Statut": "Ouvert", "Menace": "Scan de Ports / Reconnaissance"}]
        infiltration = [{"Statut": "Ouvert", "Menace": "Infiltration / Brute-Force / Exfiltration"}]
        assert alert_log.compute_security_score(infiltration) < alert_log.compute_security_score(scan)

    def test_score_ne_descend_jamais_sous_zero(self):
        beaucoup = [{"Statut": "Ouvert", "Menace": "Infiltration / Brute-Force / Exfiltration"} for _ in range(500)]
        assert alert_log.compute_security_score(beaucoup) >= 0


class TestMttrHours:
    def test_aucune_alerte_fermee_retourne_none(self):
        assert alert_log.mttr_hours([{"Statut": "Ouvert"}]) is None

    def test_calcule_la_moyenne_en_heures(self):
        alertes = [
            {"Statut": "Ferme", "Horodatage": "2026-08-01 10:00:00", "Fermee_le": "2026-08-01 12:00:00"},  # 2h
            {"Statut": "Ferme", "Horodatage": "2026-08-01 10:00:00", "Fermee_le": "2026-08-01 14:00:00"},  # 4h
        ]
        assert alert_log.mttr_hours(alertes) == pytest.approx(3.0)

    def test_horodatage_malforme_est_ignore_sans_exception(self):
        alertes = [{"Statut": "Ferme", "Horodatage": "pas une date", "Fermee_le": "2026-08-01 12:00:00"}]
        assert alert_log.mttr_hours(alertes) is None


class TestSeverityBreakdown:
    def test_compte_uniquement_les_alertes_ouvertes_par_menace(self):
        alertes = [
            {"Statut": "Ouvert", "Menace": "Scan de Ports / Reconnaissance"},
            {"Statut": "Ouvert", "Menace": "Scan de Ports / Reconnaissance"},
            {"Statut": "Ferme", "Menace": "Scan de Ports / Reconnaissance"},
            {"Statut": "Ouvert", "Menace": "Attaque DDoS / Volumetrique"},
        ]
        assert alert_log.severity_breakdown(alertes) == {
            "Scan de Ports / Reconnaissance": 2,
            "Attaque DDoS / Volumetrique": 1,
        }


class TestTrendDeltaPct:
    def test_liste_vide_retourne_none_avec_message(self):
        delta, texte = alert_log.trend_delta_pct([])
        assert delta is None
        assert "Pas encore assez" in texte

    def test_historique_trop_court_retourne_none(self):
        alertes = [{"Horodatage": "2026-08-25 10:00:00"}, {"Horodatage": "2026-08-26 10:00:00"}]
        delta, texte = alert_log.trend_delta_pct(alertes, days=7)
        assert delta is None


# ======================================================================
# Test d'integration reel (optionnel) - contre une vraie base PostgreSQL
# ======================================================================
@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL non definie - fournir une base Postgres de test "
           "(ex. projet Neon dedie aux tests) pour activer cette verification "
           "de bout en bout du SQL reel. Ignore en local/CI par defaut.",
)
class TestIntegrationReelleOptionnelle:
    """Verifie le SQL reel (contraintes, migration, executemany) contre une
    vraie base - jamais execute par defaut, pour ne pas faire echouer la
    suite quand personne n'a provisionne de base de test. Pour l'activer :
    export TEST_DATABASE_URL="postgresql://...", en pointant vers une base
    dediee aux tests (jamais la base de production)."""

    @pytest.fixture(autouse=True)
    def _base_de_test(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
        monkeypatch.setattr(db, "PSYCOPG_AVAILABLE", True)
        db.init_schema()

    def test_cycle_complet_sauvegarde_puis_lecture(self):
        domaine = "test_integration_reseau"
        state = {
            "alert_log": [{"ID": "int1", "Horodatage": "2026-08-01 10:00:00", "Source": "Test",
                            "Menace": "Scan de Ports / Reconnaissance", "Confiance (%)": 91.0,
                            "Details": "", "Statut": "Ouvert", "Fermee_le": None}],
            "score_history": [{"Horodatage": "2026-08-01 10:00:00", "Score": 80}],
        }
        alert_log.save_org_state(state, domaine=domaine)
        reloaded = alert_log.load_org_state(domaine=domaine)
        assert reloaded["alert_log"][0]["ID"] == "int1"
        # Nettoyage : ne pas laisser de donnees de test dans la base.
        alert_log.save_org_state({"alert_log": [], "score_history": []}, domaine=domaine)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
