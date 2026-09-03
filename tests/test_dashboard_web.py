"""
Tests structurels - Dashboard SOC web (`web/dashboard.html` + dashboard.js/css).

*** Comble le dernier trou de couverture signale dans le README. ***

Ce module est du HTML/CSS/JS pur (pas de Python), donc hors de portee de
pytest/AppTest - une couverture fonctionnelle complete (clics, rendu visuel)
necessiterait un outil de test navigateur (ex. Playwright), explicitement
hors perimetre ici (voir demo_screenshots/ pour la verification visuelle
manuelle actuelle).

Ce que cette suite verifie SANS navigateur, par analyse statique :
- Validite syntaxique de chaque fichier JS (`node --check`)
- Equilibre des balises HTML et des accolades CSS
- Coherence entre les IDs definis dans le HTML (ou injectes dynamiquement
  par le JS via `innerHTML`) et ceux references par `getElementById()` -
  un ID reference mais jamais defini nulle part est un bug silencieux
  classique (l'element est simplement `null`, aucune erreur explicite)
- Que les 3 canvases de graphiques Chart.js du HTML correspondent exactement
  aux 3 graphiques instancies dans le JS
- Que la configuration de deploiement (`config.js`) est bien la seule source
  d'URLs d'API/app, jamais dupliquee en dur dans dashboard.js
"""
import re
import subprocess
from pathlib import Path

import pytest

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _run_node_check(path: Path):
    result = subprocess.run(
        ["node", "--check", str(path)], capture_output=True, text=True, timeout=15,
    )
    return result.returncode, result.stderr


class TestSyntaxeJavaScript:
    """Un fichier JS syntaxiquement invalide casse silencieusement toute
    interaction de la page pour l'utilisateur - node --check le detecte
    instantanement, sans navigateur."""

    @pytest.mark.parametrize("js_file", sorted(WEB_DIR.glob("*.js")), ids=lambda p: p.name)
    def test_fichier_js_syntaxiquement_valide(self, js_file):
        code, stderr = _run_node_check(js_file)
        assert code == 0, f"{js_file.name} invalide :\n{stderr}"


class TestEquilibreStructurel:
    def test_dashboard_html_balises_equilibrees(self):
        html = (WEB_DIR / "dashboard.html").read_text()
        # Balises auto-fermantes/void HTML courantes a exclure du comptage.
        void_tags = {"meta", "link", "input", "br", "img", "hr"}
        opens = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)(?:\s[^>]*)?(?<!/)>", html)
        closes = re.findall(r"</([a-zA-Z][a-zA-Z0-9]*)>", html)
        opens = [t for t in opens if t.lower() not in void_tags]
        from collections import Counter
        open_counts, close_counts = Counter(t.lower() for t in opens), Counter(t.lower() for t in closes)
        mismatches = {
            tag: (open_counts[tag], close_counts.get(tag, 0))
            for tag in open_counts
            if open_counts[tag] != close_counts.get(tag, 0)
        }
        assert not mismatches, f"Balises non equilibrees : {mismatches}"

    def test_dashboard_css_accolades_equilibrees(self):
        css = (WEB_DIR / "dashboard.css").read_text()
        assert css.count("{") == css.count("}")

    def test_dashboard_js_accolades_et_parentheses_equilibrees(self):
        """Verification grossiere (ne parse pas les chaines/regex contenant
        des accolades) mais suffisante comme garde-fou rapide en complement
        de node --check, qui lui fait deja l'analyse syntaxique complete."""
        js = (WEB_DIR / "dashboard.js").read_text()
        assert js.count("{") == js.count("}")
        assert js.count("(") == js.count(")")


class TestCoherenceIdsHtmlJs:
    """Un getElementById() sur un ID absent du DOM retourne null sans lever
    d'erreur - le bug ne se manifeste souvent qu'au clic, en profondeur.
    On verifie ici que chaque ID reference existe bien quelque part : soit
    statiquement dans le HTML, soit injecte dynamiquement par le JS lui-meme
    (ex. `innerHTML = '<button id="logout-btn">...'` avant de le referencer)."""

    def test_tous_les_ids_references_par_getelementbyid_existent(self):
        html = (WEB_DIR / "dashboard.html").read_text()
        js = (WEB_DIR / "dashboard.js").read_text()

        ids_definis_html = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', html))
        ids_injectes_js = set(re.findall(r'id="([a-zA-Z0-9_-]+)"', js))  # ex. innerHTML dynamique
        ids_disponibles = ids_definis_html | ids_injectes_js

        ids_references = set(re.findall(r'getElementById\(["\']([a-zA-Z0-9_-]+)["\']\)', js))

        manquants = ids_references - ids_disponibles
        assert not manquants, (
            f"IDs references par getElementById() mais introuvables (ni dans le HTML, "
            f"ni injectes dynamiquement par le JS) : {manquants}"
        )

    def test_les_trois_canvases_de_graphiques_correspondent_au_js(self):
        html = (WEB_DIR / "dashboard.html").read_text()
        js = (WEB_DIR / "dashboard.js").read_text()

        canvas_ids_html = set(re.findall(r'<canvas[^>]*id="([a-zA-Z0-9_-]+)"', html))
        chart_ids_js = set(re.findall(r'new Chart\(document\.getElementById\("([a-zA-Z0-9_-]+)"\)', js))

        assert canvas_ids_html == {"chart-status", "chart-severity", "chart-timeline"}
        assert chart_ids_js == canvas_ids_html, (
            "Les canvases Chart.js declares dans le HTML ne correspondent pas "
            "exactement aux graphiques instancies dans le JS."
        )


class TestConfigurationCentralisee:
    """config.js est documente comme LA seule source des URLs de deploiement
    (voir son propre commentaire d'en-tete) - toute URL d'API dupliquee en
    dur ailleurs romprait cette garantie au prochain changement d'environnement."""

    def test_config_js_definit_les_deux_constantes_attendues(self):
        config = (WEB_DIR / "config.js").read_text()
        assert "API_BASE_URL" in config
        assert "ORG_APP_URL" in config
        assert re.search(r'const\s+API_BASE_URL\s*=\s*"https?://', config)
        assert re.search(r'const\s+ORG_APP_URL\s*=\s*"https?://', config)

    def test_dashboard_js_nutilise_pas_durl_dapi_codee_en_dur(self):
        """dashboard.js doit passer par la constante API_BASE_URL de config.js,
        jamais une URL http(s) ecrite en dur qui divergerait silencieusement
        de config.js lors d'un changement de deploiement."""
        js = (WEB_DIR / "dashboard.js").read_text()
        urls_en_dur = re.findall(r'["\'](https?://[^"\']+)["\']', js)
        # Seules des URLs de ressources tierces (polices, CDN) sont tolerees ici,
        # jamais une URL qui ressemble a l'API elle-meme (onrender.com, localhost, /predict...).
        suspectes = [u for u in urls_en_dur if "onrender" in u or "localhost" in u or "127.0.0.1" in u]
        assert not suspectes, f"URL d'API codee en dur trouvee dans dashboard.js : {suspectes}"
        assert js.count("API_BASE_URL") >= 1, "dashboard.js devrait utiliser API_BASE_URL de config.js"


class TestAvertissementsHonnetesPresents:
    """Coherence editoriale : ce module partage la meme discipline
    d'avertissement honnete que le reste du projet (voir README, model
    metadata) - le dashboard ne doit jamais laisser croire a une donnee
    temps reel type capture de paquets (voir clarification 'Real-time
    detection' -> 'on-demand/batch scoring' dans l'historique du projet)."""

    def test_dashboard_ne_revendique_pas_de_capture_de_paquets_en_direct(self):
        html = (WEB_DIR / "dashboard.html").read_text().lower()
        js = (WEB_DIR / "dashboard.js").read_text().lower()
        contenu = html + js
        # Termes qui suggereraient a tort une capture reseau live plutot
        # qu'un scoring a la demande sur des donnees importees/rejouees.
        assert "packet sniffing" not in contenu
        assert "capture de paquets en direct" not in contenu
