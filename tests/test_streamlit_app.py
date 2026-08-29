"""
Tests de fumee (smoke tests) - Interface Streamlit (Etape 5).
Utilise streamlit.testing.v1.AppTest pour executer l'application sans navigateur.

*** Mis a jour (voir git log) pour suivre 2 restructurations qui avaient casse
19 de ces tests sans que la suite ne soit mise a jour en meme temps : ***

1. L'Espace Organisation ne mene plus directement a des onglets techniques.
   Il affiche d'abord un ecran de selection a 2 produits ("Securite Reseau"
   valide vs "Fraude Transactionnelle" prototype) - il faut donc un clic
   supplementaire (voir `_choisir_module_reseau`) avant d'atteindre les 7
   onglets du module reseau (le nombre est aussi passe de 5 a 7 : Reglages
   et Visualisation ont ete ajoutes, Tableau de bord a ete retire au profit
   de l'Espace Academique).
2. L'Espace Grand Public Streamlit est desormais deprecie : la carte
   "Espace Grand Public" de la page d'accueil est un st.link_button externe
   vers la version web independante (Vercel, plus complete - lecons
   visuelles, reconnaissance vocale, Pass), pas un st.button qui changerait
   de vue. La route interne `?view=public` existe toujours mais n'affiche
   plus qu'un message "Cet espace a demenage" avec un lien vers Vercel - le
   jeu de vigilance gamifie qui vivait ici n'est plus rendu par Streamlit du
   tout. Les tests qui verifiaient ce jeu (TestJeuDeVigilanceGamifie) testaient
   donc du code mort (`render_public_view()`, jamais appele par le dispatch
   principal) ; ils ont ete remplaces par des tests du redirect, seul
   comportement reellement atteignable depuis Streamlit aujourd'hui. Le jeu
   de vigilance lui-meme (desormais en HTML/JS pur sur Vercel) resterait a
   couvrir par un outil web (Playwright), hors perimetre de cette suite
   pytest/AppTest.

Chaque test utilise donc une instance fraiche de AppTest (fixture a portee
"function") pour eviter toute pollution d'etat entre tests lies a la
navigation (st.session_state.view). Des fonctions utilitaires simulent le
clic sur les boutons d'entree/retour de la page d'accueil.

Limite connue : AppTest ne simule pas les interactions st.file_uploader
(voir issue streamlit/streamlit). La couverture de l'onglet "Import CSV" est
donc assuree separement par des captures d'ecran Playwright (demo_screenshots/)
documentees dans le rapport de tests, et par les tests d'equivalence
API <-> pipeline direct (tests/test_api.py::TestCoherenceApiPipeline) qui
valident le meme code de pretraitement/prediction.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import api.auth as auth

APP_PATH = Path(__file__).resolve().parent.parent / "app" / "app.py"


def _set_text_input(app_test, key, value):
    """Renseigne un st.text_input (ou st.text_input(type='password')) identifie
    par sa `key`, sans faire rejouer l'application (comme AppTest.set_value
    pour les autres widgets) : le rerun se fait via le clic du bouton de
    soumission du formulaire, comme dans un vrai parcours utilisateur."""
    widget = next(w for w in app_test.text_input if w.key == key)
    widget.set_value(value)
    return widget


@pytest.fixture()
def at():
    """Instance fraiche de l'application pour chaque test (portee 'function') :
    la navigation entre la page d'accueil et les deux espaces modifie
    st.session_state.view, donc partager une instance entre tests (portee
    'module') ferait fuiter la navigation d'un test a l'autre."""
    a = AppTest.from_file(str(APP_PATH))
    a.run(timeout=60)
    return a


def _click_button_containing(app_test, substring):
    """Clique sur le premier bouton dont le libelle contient `substring`,
    puis rejoue l'application. Echoue explicitement si aucun bouton ne
    correspond, plutot que de laisser un IndexError peu clair."""
    boutons = [b for b in app_test.get("button") if substring in (b.label or "")]
    assert boutons, f"Aucun bouton contenant '{substring}' trouve"
    boutons[0].click().run(timeout=60)
    return app_test


def _goto_organisation(app_test):
    """Clique sur la carte d'entree de l'Espace Organisation. Selon le mode
    d'authentification, on atterrit soit sur l'ecran de connexion
    (AUTH_MODE=self_signup), soit directement sur l'ecran de selection de
    module (2 produits) - jamais sur des onglets techniques immediatement."""
    return _click_button_containing(app_test, "Espace Organisation")


def _choisir_module_reseau(app_test):
    """Depuis l'ecran de selection a 2 produits de l'Espace Organisation,
    choisit le module Securite Reseau (celui teste par cette suite - le
    module Fraude Transactionnelle n'a pas encore de couverture pytest
    dediee, voir README)."""
    return _click_button_containing(app_test, "Ouvrir Securite Reseau")


def _goto_reseau(app_test):
    """Raccourci pour les tests qui veulent directement les onglets du module
    reseau, en franchissant les deux etapes (Espace Organisation -> Securite
    Reseau)."""
    _goto_organisation(app_test)
    return _choisir_module_reseau(app_test)


class TestPageAccueil:
    def test_application_demarre_sans_exception(self, at):
        assert not at.exception, f"Exception au demarrage : {at.exception}"

    def test_titre_present(self, at):
        """Le titre est rendu via une banniere HTML personnalisee (st.markdown),
        et non st.title. Le bandeau est affiche sur toutes les vues, y compris
        la page d'accueil."""
        html_blocks = " ".join(m.value for m in at.markdown)
        assert "Kimatey FinNet Guard" in html_blocks
        assert "Detection Intelligente" in html_blocks or "SOC" in html_blocks

    def test_page_accueil_affiche_les_deux_espaces_et_aucun_onglet(self, at):
        """Au premier chargement, l'application doit presenter la page
        d'accueil (bouton d'entree Organisation + lien externe vers l'Espace
        Grand Public sur Vercel) et ne doit afficher aucun onglet technique
        tant qu'aucun espace n'a ete choisi.

        L'Espace Grand Public est un st.link_button (redirection externe vers
        la version web independante), pas un st.button - il n'apparait donc
        pas dans at.get("button") mais dans at.get("link_button")."""
        boutons = [b.label or "" for b in at.get("button")]
        liens = [lb.label or "" for lb in at.get("link_button")]
        assert any("Espace Organisation" in b for b in boutons)
        assert any("Espace Grand Public" in l for l in liens)
        assert len(at.tabs) == 0


class TestEspaceOrganisation:
    def test_ecran_de_selection_du_module_affiche_avant_tout_onglet(self, at):
        """Depuis la restructuration en 2 produits, l'entree dans l'Espace
        Organisation affiche d'abord un ecran de choix (Securite Reseau /
        Fraude Transactionnelle), jamais des onglets directement."""
        _goto_organisation(at)
        assert not at.exception
        assert len(at.tabs) == 0
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Ouvrir Securite Reseau" in b for b in boutons)
        assert any("Ouvrir Fraude Transactionnelle" in b for b in boutons)

    def test_sept_onglets_presents_dans_le_module_reseau(self, at):
        _goto_reseau(at)
        assert len(at.tabs) == 7

    def test_metriques_resume_simple_affichees(self, at):
        """Le premier onglet du module reseau ("Resume simple") doit afficher
        au moins 4 cartes KPI (score de securite, alertes ouvertes, taux de
        traitement, tendance...). Ces cartes sont des blocs HTML personnalises
        (classe CSS kpi-card), pas des st.metric."""
        _goto_reseau(at)
        html_blocks = " ".join(m.value for m in at.markdown)
        assert html_blocks.count("kpi-value") >= 4

    def test_bouton_retour_accueil_fonctionne(self, at):
        _goto_reseau(at)
        assert len(at.tabs) == 7
        _click_button_containing(at, "Retour a l'accueil")
        assert len(at.tabs) == 0
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Espace Organisation" in b for b in boutons)

    def test_bouton_changer_de_module_revient_a_lecran_de_selection(self, at):
        """Nouveau parcours propre a la restructuration : depuis un module,
        on peut revenir a l'ecran de choix sans repasser par la page
        d'accueil (donc sans perdre la session authentifiee)."""
        _goto_reseau(at)
        _click_button_containing(at, "Changer de module")
        assert not at.exception
        assert len(at.tabs) == 0
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Ouvrir Securite Reseau" in b for b in boutons)


class TestConnexionEspaceOrganisationSelfSignup:
    """Ecran de connexion / creation de compte (email + mot de passe),
    affiche uniquement quand AUTH_MODE=self_signup, en reutilisant directement
    api/auth.py (meme module, meme fichier api/users.json, que l'API
    FastAPI - voir app/app.py). Isole de tout vrai fichier users.json via un
    chemin temporaire par test."""

    @pytest.fixture(autouse=True)
    def _mode_self_signup_isole(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "self_signup")
        monkeypatch.setattr(auth, "USERS_FILE", tmp_path / "users_test.json")

    def test_espace_organisation_demande_une_connexion_avant_les_onglets(self, at):
        """Tant qu'aucun compte n'est authentifie, on ne voit que les 2 onglets
        de l'ecran de connexion (Se connecter / Creer un compte) - jamais les
        5 onglets techniques de l'Espace Organisation."""
        _goto_organisation(at)
        assert not at.exception
        assert len(at.tabs) == 2
        assert not any("Tableau de bord" in (t.label or "") for t in at.tabs)
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Se connecter" in b for b in boutons)
        assert any("Creer mon compte" in b for b in boutons)

    def test_creation_de_compte_donne_acces_immediat_a_lecran_de_selection_de_module(self, at):
        """Apres creation de compte, l'utilisateur atterrit sur l'ecran de
        selection a 2 produits (pas directement sur des onglets techniques -
        voir TestEspaceOrganisation pour ce parcours plus loin)."""
        _goto_organisation(at)
        _set_text_input(at, "register_email", "etudiant@ufrmi.edu")
        _set_text_input(at, "register_password", "motdepasse123")
        _click_button_containing(at, "Creer mon compte")
        assert not at.exception
        assert len(at.tabs) == 0
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Ouvrir Securite Reseau" in b for b in boutons)
        caption_texts = " ".join(c.value for c in at.caption)
        assert "etudiant@ufrmi.edu" in caption_texts

    def test_creation_de_compte_puis_choix_du_module_reseau_donne_acces_aux_onglets(self, at):
        _goto_organisation(at)
        _set_text_input(at, "register_email", "etudiant1b@ufrmi.edu")
        _set_text_input(at, "register_password", "motdepasse123")
        _click_button_containing(at, "Creer mon compte")
        _choisir_module_reseau(at)
        assert not at.exception
        assert len(at.tabs) == 7

    def test_connexion_avec_le_compte_juste_cree_fonctionne_apres_deconnexion(self, at):
        _goto_organisation(at)
        _set_text_input(at, "register_email", "etudiant2@ufrmi.edu")
        _set_text_input(at, "register_password", "motdepasse123")
        _click_button_containing(at, "Creer mon compte")
        _click_button_containing(at, "Se deconnecter")
        assert len(at.tabs) == 2  # de retour sur l'ecran de connexion, pas les onglets techniques
        _set_text_input(at, "login_email", "etudiant2@ufrmi.edu")
        _set_text_input(at, "login_password", "motdepasse123")
        _click_button_containing(at, "Se connecter")
        assert not at.exception
        assert len(at.tabs) == 0  # ecran de selection de module, pas encore les onglets
        _choisir_module_reseau(at)
        assert len(at.tabs) == 7
        assert any("Resume simple" in (t.label or "") for t in at.tabs)

    def test_mauvais_mot_de_passe_refuse_laccess(self, at):
        _goto_organisation(at)
        _set_text_input(at, "register_email", "etudiant3@ufrmi.edu")
        _set_text_input(at, "register_password", "motdepasse123")
        _click_button_containing(at, "Creer mon compte")
        _click_button_containing(at, "Se deconnecter")
        _set_text_input(at, "login_email", "etudiant3@ufrmi.edu")
        _set_text_input(at, "login_password", "faux")
        _click_button_containing(at, "Se connecter")
        assert not at.exception
        assert len(at.tabs) == 2
        boutons = [b.label or "" for b in at.get("button")]
        assert not any("Ouvrir Securite Reseau" in b for b in boutons)


class TestFormulairePredictionUnique:
    def test_formulaire_contient_9_champs_numeriques(self, at):
        _goto_reseau(at)
        assert len(at.number_input) == 9

    def test_soumission_formulaire_valeurs_par_defaut_ne_leve_pas_dexception(self, at):
        """Soumettre le formulaire avec les valeurs par defaut (medianes
        d'entrainement) doit produire un resultat sans erreur."""
        _goto_reseau(at)
        submit_buttons = [b for b in at.get("button") if "Analyser" in (b.label or "")]
        assert len(submit_buttons) >= 1
        submit_buttons[0].click().run(timeout=60)
        assert not at.exception, f"Exception a la soumission : {at.exception}"

    def test_soumission_formulaire_affiche_un_resultat(self, at):
        _goto_reseau(at)
        submit_buttons = [b for b in at.get("button") if "Analyser" in (b.label or "")]
        submit_buttons[0].click().run(timeout=60)
        markdown_texts = " ".join(m.value for m in at.markdown)
        assert "Resultat de l'analyse" in markdown_texts or "Niveau de confiance" in markdown_texts

    def test_soumission_formulaire_propose_explication_lieutenant_cyber(self, at):
        """Nouvelle fonctionnalite : Lieutenant Cyber (meme IA que l'Espace Grand
        Public) peut expliquer un resultat de prediction en langage clair. Sans cle
        Gemini configuree dans cet environnement de test, seule l'invite (caption)
        doit apparaitre - jamais une exception."""
        _goto_reseau(at)
        submit_buttons = [b for b in at.get("button") if "Analyser" in (b.label or "")]
        submit_buttons[0].click().run(timeout=60)
        assert not at.exception
        caption_texts = " ".join(c.value for c in at.caption)
        assert "Lieutenant Cyber" in caption_texts


class TestOngletSurveillanceEnDirect:
    """Onglet ajoute pour simuler une supervision en temps reel (echantillonnage
    aleatoire du jeu de donnees reel + prediction + mise a jour progressive de
    l'affichage). Ce test verifie que les controles sont bien presents ; il ne
    declenche pas la simulation elle-meme (boucle avec time.sleep) pour garder
    la suite de tests rapide - la simulation est verifiee visuellement (QA
    Playwright, voir demo_screenshots/)."""

    def test_bouton_demarrer_et_sliders_presents(self, at):
        _goto_reseau(at)
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Demarrer" in b or "marrer" in b for b in boutons)
        assert any("einitialiser" in b for b in boutons)
        assert len(at.slider) >= 2

    def test_pas_dexception_avant_lancement_simulation(self, at):
        _goto_reseau(at)
        assert not at.exception


class TestEspaceGrandPublic:
    """L'Espace Grand Public Streamlit est deprecie au profit de la version web
    independante (Vercel, seule maintenue desormais - lecons visuelles,
    reconnaissance vocale, Pass, fil de tendances). Ces tests verifient donc
    le redirect, seul comportement que Streamlit rend encore reellement pour
    cet espace - pas le contenu de l'ancien module (jeu de vigilance,
    Lieutenant Cyber conversationnel), qui n'est plus jamais rendu par
    `render_public_view()` (code mort, jamais appele par le dispatch
    principal). La couverture du jeu de vigilance et de l'assistant tels
    qu'ils existent reellement aujourd'hui (HTML/JS sur Vercel) releverait
    d'un outil web (Playwright), hors perimetre de cette suite pytest/AppTest -
    voir demo_screenshots/ pour la verification visuelle manuelle actuelle."""

    def test_carte_accueil_pointe_vers_la_version_web(self, at):
        liens = [lb for lb in at.get("link_button") if "Espace Grand Public" in (lb.label or "")]
        assert liens, "Aucun lien 'Espace Grand Public' trouve sur la page d'accueil"
        assert "vercel.app/public.html" in liens[0].url

    def test_route_interne_view_public_affiche_un_message_de_redirection(self):
        """Le lien direct ?view=public (ancien signet, lien externe historique)
        ne doit plus jamais afficher l'ancienne interface a onglets - seulement
        un message clair et un lien vers la version a jour."""
        a = AppTest.from_file(str(APP_PATH))
        a.query_params["view"] = "public"
        a.run(timeout=60)
        assert not a.exception
        assert len(a.tabs) == 0
        markdown_texts = " ".join(m.value for m in a.markdown)
        assert "demenage" in markdown_texts.lower()
        liens = [lb for lb in a.get("link_button") if "Espace Grand Public" in (lb.label or "")]
        assert liens and "vercel.app/public.html" in liens[0].url

    def test_route_interne_view_public_bouton_retour_fonctionne(self):
        a = AppTest.from_file(str(APP_PATH))
        a.query_params["view"] = "public"
        a.run(timeout=60)
        boutons = [b for b in a.get("button") if "Retour a l'accueil" in (b.label or "")]
        assert boutons
        boutons[0].click().run(timeout=60)
        assert not a.exception
        boutons_accueil = [b.label or "" for b in a.get("button")]
        assert any("Espace Organisation" in b for b in boutons_accueil)
