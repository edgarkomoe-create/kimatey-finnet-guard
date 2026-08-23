"""
Tests de fumee (smoke tests) - Interface Streamlit (Etape 5).
Utilise streamlit.testing.v1.AppTest pour executer l'application sans navigateur.

Depuis la refonte "Kimatey FinNet Guard", l'application n'est plus un seul
bandeau plat de 7 onglets : elle demarre sur une page d'accueil (0 onglet)
qui oriente vers deux espaces distincts, chacun avec ses propres onglets :
- Espace Organisation (5 onglets techniques) : Tableau de bord, Import CSV,
  Prediction unique, Surveillance en direct, Alertes.
- Espace Grand Public (2 onglets) : Lieutenant Cyber (assistant conversationnel/vocal,
  Gemini), Sensibilisation (jeu de vigilance gamifie + collecte participative anonymisee).

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
    return _click_button_containing(app_test, "Espace Organisation")


def _goto_public(app_test):
    return _click_button_containing(app_test, "Espace Grand Public")


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
        d'accueil (deux boutons d'entree) et ne doit afficher aucun onglet
        technique tant qu'aucun espace n'a ete choisi."""
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Espace Organisation" in b for b in boutons)
        assert any("Espace Grand Public" in b for b in boutons)
        assert len(at.tabs) == 0


class TestEspaceOrganisation:
    def test_cinq_onglets_presents(self, at):
        _goto_organisation(at)
        assert len(at.tabs) == 5

    def test_metriques_tableau_de_bord_affichees(self, at):
        """Le tableau de bord (1er onglet de l'Espace Organisation) doit
        afficher au moins les 4 cartes KPI cle du modele (exactitude, F1,
        AUC, nb variables). Ces cartes sont des blocs HTML personnalises
        (classe CSS kpi-card), pas des st.metric."""
        _goto_organisation(at)
        html_blocks = " ".join(m.value for m in at.markdown)
        assert html_blocks.count("kpi-value") >= 4

    def test_bouton_retour_accueil_fonctionne(self, at):
        _goto_organisation(at)
        assert len(at.tabs) == 5
        _click_button_containing(at, "Retour a l'accueil")
        assert len(at.tabs) == 0
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Espace Organisation" in b for b in boutons)


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

    def test_creation_de_compte_donne_acces_immediat_a_lespace_organisation(self, at):
        _goto_organisation(at)
        _set_text_input(at, "register_email", "etudiant@ufrmi.edu")
        _set_text_input(at, "register_password", "motdepasse123")
        _click_button_containing(at, "Creer mon compte")
        assert not at.exception
        assert len(at.tabs) == 5
        caption_texts = " ".join(c.value for c in at.caption)
        assert "etudiant@ufrmi.edu" in caption_texts

    def test_connexion_avec_le_compte_juste_cree_fonctionne_apres_deconnexion(self, at):
        _goto_organisation(at)
        _set_text_input(at, "register_email", "etudiant2@ufrmi.edu")
        _set_text_input(at, "register_password", "motdepasse123")
        _click_button_containing(at, "Creer mon compte")
        _click_button_containing(at, "Se deconnecter")
        assert len(at.tabs) == 2  # de retour sur l'ecran de connexion, pas les 5 onglets techniques
        _set_text_input(at, "login_email", "etudiant2@ufrmi.edu")
        _set_text_input(at, "login_password", "motdepasse123")
        _click_button_containing(at, "Se connecter")
        assert not at.exception
        assert len(at.tabs) == 5
        assert any("Tableau de bord" in (t.label or "") for t in at.tabs)

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
        assert not any("Tableau de bord" in (t.label or "") for t in at.tabs)


class TestFormulairePredictionUnique:
    def test_formulaire_contient_9_champs_numeriques(self, at):
        _goto_organisation(at)
        assert len(at.number_input) == 9

    def test_soumission_formulaire_valeurs_par_defaut_ne_leve_pas_dexception(self, at):
        """Soumettre le formulaire avec les valeurs par defaut (medianes
        d'entrainement) doit produire un resultat sans erreur."""
        _goto_organisation(at)
        submit_buttons = [b for b in at.get("button") if "Analyser" in (b.label or "")]
        assert len(submit_buttons) >= 1
        submit_buttons[0].click().run(timeout=60)
        assert not at.exception, f"Exception a la soumission : {at.exception}"

    def test_soumission_formulaire_affiche_un_resultat(self, at):
        _goto_organisation(at)
        submit_buttons = [b for b in at.get("button") if "Analyser" in (b.label or "")]
        submit_buttons[0].click().run(timeout=60)
        markdown_texts = " ".join(m.value for m in at.markdown)
        assert "Resultat de l'analyse" in markdown_texts or "Niveau de confiance" in markdown_texts

    def test_soumission_formulaire_propose_explication_lieutenant_cyber(self, at):
        """Nouvelle fonctionnalite : Lieutenant Cyber (meme IA que l'Espace Grand
        Public) peut expliquer un resultat de prediction en langage clair. Sans cle
        Gemini configuree dans cet environnement de test, seule l'invite (caption)
        doit apparaitre - jamais une exception."""
        _goto_organisation(at)
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
        _goto_organisation(at)
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Demarrer" in b or "marrer" in b for b in boutons)
        assert any("einitialiser" in b for b in boutons)
        assert len(at.slider) >= 2

    def test_pas_dexception_avant_lancement_simulation(self, at):
        _goto_organisation(at)
        assert not at.exception


class TestEspaceGrandPublic:
    def test_deux_onglets_presents(self, at):
        _goto_public(at)
        assert len(at.tabs) == 2

    def test_assistant_et_sensibilisation_presents(self, at):
        """Verifie la presence du contenu des deux onglets grand public sans
        dependre d'une cle API Gemini valide : l'onglet Lieutenant Cyber doit au
        moins afficher son sous-titre, et l'onglet Sensibilisation doit
        afficher le jeu de vigilance (situation + choix sous forme de bouton radio)."""
        _goto_public(at)
        assert not at.exception
        subheader_texts = " ".join(s.value for s in at.subheader)
        assert "Lieutenant Cyber" in subheader_texts
        assert len(at.radio) >= 1
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Valider ma reponse" in b for b in boutons)

    def test_bouton_retour_accueil_fonctionne(self, at):
        _goto_public(at)
        assert len(at.tabs) == 2
        _click_button_containing(at, "Retour a l'accueil")
        assert len(at.tabs) == 0
        boutons = [b.label or "" for b in at.get("button")]
        assert any("Espace Grand Public" in b for b in boutons)


class TestJeuDeVigilanceGamifie:
    """Fusion avec le modele de gamification de l'Espace Jeux VIE (VIE Water Care) :
    categories thematiques + mascottes, niveau/Points Bouclier, vies, badges."""

    def test_six_categories_thematiques_presentes(self, at):
        _goto_public(at)
        cat_radio = next(r for r in at.radio if "categorie" in (r.label or "").lower())
        assert len(cat_radio.options) == 6
        assert any("Cyber" in opt for opt in cat_radio.options)
        assert any("Mobile Money" in opt for opt in cat_radio.options)

    def test_carte_de_progression_affichee(self, at):
        _goto_public(at)
        assert not at.exception
        markdown_html = " ".join(m.value for m in at.markdown)
        assert "Niveau" in markdown_html
        assert "Points Bouclier" in markdown_html
        assert "Vies" in markdown_html
        assert "Badges" in markdown_html

    def test_categorie_cyber_affiche_lieutenant_cyber_sans_reference_a_vivi(self, at):
        """Decision produit : une IA originale (Lieutenant Cyber, propre a Kimatey) anime
        toutes les categories, y compris Cyber & Mots de Passe - sans faire apparaitre ViVi
        (mascotte de VIE Water Care), pour ne pas creer de lien de marque non voulu."""
        _goto_public(at)
        cat_radio = next(r for r in at.radio if "categorie" in (r.label or "").lower())
        cyber_option = next(opt for opt in cat_radio.options if "Cyber" in opt)
        cat_radio.set_value(cyber_option).run(timeout=60)
        assert not at.exception
        markdown_html = " ".join(m.value for m in at.markdown)
        assert "Lieutenant Cyber" in markdown_html
        assert "ViVi" not in markdown_html

    def test_repondre_correctement_ajoute_des_points_bouclier(self, at):
        _goto_public(at)
        quiz_radio = next(r for r in at.radio if r.label == "Que faites-vous ?")
        # La 2e option est toujours la bonne reponse dans les scenarios de ce jeu.
        quiz_radio.set_value(quiz_radio.options[1]).run(timeout=60)
        _click_button_containing(at, "Valider ma reponse")
        assert not at.exception
        markdown_html = " ".join(m.value for m in at.markdown)
        assert "15 Points Bouclier" in markdown_html
        badges_expander_titles = [e.label for e in at.get("expander")]
        assert any("🏅 Mes badges" in t for t in badges_expander_titles)

    def test_repondre_incorrectement_retire_une_vie(self, at):
        _goto_public(at)
        quiz_radio = next(r for r in at.radio if r.label == "Que faites-vous ?")
        quiz_radio.set_value(quiz_radio.options[0]).run(timeout=60)  # Toujours la mauvaise reponse
        _click_button_containing(at, "Valider ma reponse")
        assert not at.exception
        markdown_html = " ".join(m.value for m in at.markdown)
        assert "🖤" in markdown_html
