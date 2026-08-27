"""
Journal d'alertes et score de securite - logique partagee entre l'application
Streamlit (Espace Organisation) et l'API FastAPI (pour une future page web
animee du dashboard SOC). Les deux surfaces lisent/ecrivent le MEME fichier
(outputs/organisation_state.json), donc restent toujours synchronisees -
aucune duplication de donnees.

Meme limite connue que le reste du projet (voir README) : sur le plan
gratuit Render, ce fichier n'est pas persistant a travers les redeploiements
tant que la migration vers PostgreSQL (core/db.py) ne couvre pas aussi cette
donnee (voir roadmap).
"""
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from core import db

BASE_DIR = Path(__file__).resolve().parent.parent

CLASS_NAMES = {0: "Normal / Legitime", 1: "Scan de Ports / Reconnaissance",
               2: "Attaque DDoS / Volumetrique", 3: "Infiltration / Brute-Force / Exfiltration"}
TRANSACTION_CLASS_NAMES = {0: "Legitime", 1: "Suspecte"}
SEVERITY_WEIGHT = {1: 1, 2: 2, 3: 3}  # 1=scan (faible), 2=DDoS (eleve), 3=infiltration (critique)


def _state_file(domaine: str) -> Path:
    suffix = "" if domaine == "reseau" else f"_{domaine}"
    return BASE_DIR / "outputs" / f"organisation_state{suffix}.json"


def _load_org_state_pg(domaine: str) -> dict:
    db.init_schema()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, horodatage, source, menace, confiance, details, statut, fermee_le "
                "FROM alerts WHERE domaine = %s ORDER BY seq DESC", (domaine,)
            )
            alert_log = [
                {
                    "ID": row[0], "Horodatage": row[1], "Source": row[2], "Menace": row[3],
                    "Confiance (%)": row[4], "Details": row[5] or "", "Statut": row[6], "Fermee_le": row[7],
                }
                for row in cur.fetchall()
            ]
            cur.execute("SELECT horodatage, score FROM score_history WHERE domaine = %s ORDER BY seq ASC", (domaine,))
            score_history = [{"Horodatage": row[0], "Score": row[1]} for row in cur.fetchall()]
    return {"alert_log": alert_log, "score_history": score_history}


def _save_org_state_pg(state: dict, domaine: str) -> None:
    """Remplacement complet (delete + reinsert), limite au domaine concerne -
    simple et correct a l'echelle d'une demo, evite une logique de diff plus
    complexe. N'affecte jamais les alertes d'un autre domaine."""
    db.init_schema()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM alerts WHERE domaine = %s", (domaine,))
            for entry in reversed(state.get("alert_log", [])):  # reversed : le plus ancien insere en premier
                cur.execute(
                    "INSERT INTO alerts (id, domaine, horodatage, source, menace, confiance, details, statut, fermee_le) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (entry["ID"], domaine, entry["Horodatage"], entry.get("Source"), entry.get("Menace"),
                     entry.get("Confiance (%)"), entry.get("Details", ""), entry.get("Statut", "Ouvert"),
                     entry.get("Fermee_le")),
                )
            cur.execute("DELETE FROM score_history WHERE domaine = %s", (domaine,))
            for entry in state.get("score_history", []):
                cur.execute(
                    "INSERT INTO score_history (domaine, horodatage, score) VALUES (%s, %s, %s)",
                    (domaine, entry["Horodatage"], entry["Score"]),
                )


def load_org_state(domaine: str = "reseau") -> dict:
    if db.database_configured():
        return _load_org_state_pg(domaine)
    state_file = _state_file(domaine)
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"alert_log": [], "score_history": []}


def save_org_state(state: dict, domaine: str = "reseau") -> None:
    if db.database_configured():
        _save_org_state_pg(state, domaine)
        return
    state_file = _state_file(domaine)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def log_alert(source_label: str, pred_class: int, confidence: float, details: str = "",
              domaine: str = "reseau", class_names: dict = None) -> None:
    """domaine : 'reseau' (par defaut, 4 classes) ou 'transactions' (2 classes,
    voir TRANSACTION_CLASS_NAMES). class_names permet de surcharger le mapping
    si besoin d'un futur domaine supplementaire, sans toucher a cette fonction.

    ATTENTION PERFORMANCE : pour journaliser plusieurs alertes d'un coup (import
    CSV en lot), preferer log_alerts_bulk() ci-dessous - cette fonction ouvre
    une connexion Postgres separee a CHAQUE appel, ce qui devient tres lent
    (des centaines d'allers-retours reseau sequentiels) si appelee en boucle."""
    if pred_class == 0:
        return
    names = class_names or (TRANSACTION_CLASS_NAMES if domaine == "transactions" else CLASS_NAMES)
    entry_id = str(uuid.uuid4())[:8]
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alerts (id, domaine, horodatage, source, menace, confiance, details, statut, fermee_le) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (entry_id, domaine, horodatage, source_label, names[pred_class], round(confidence, 1),
                     details, "Ouvert", None),
                )
        return
    state = load_org_state(domaine)
    state.setdefault("alert_log", []).insert(0, {
        "ID": entry_id, "Horodatage": horodatage, "Source": source_label,
        "Menace": names[pred_class], "Confiance (%)": round(confidence, 1),
        "Details": details, "Statut": "Ouvert", "Fermee_le": None,
    })
    save_org_state(state, domaine)


def log_alerts_bulk(entries: list, domaine: str = "reseau", class_names: dict = None) -> int:
    """Journalise PLUSIEURS alertes en une seule connexion/transaction Postgres
    (au lieu d'une connexion par alerte comme le ferait un appel repete a
    log_alert) - essentiel pour la performance d'un import CSV en lot, ou
    des centaines de menaces peuvent etre detectees d'un coup.

    entries : liste de dicts {"source": str, "pred_class": int, "confidence": float,
    "details": str (optionnel)}. Les entrees avec pred_class=0 (normal/legitime)
    sont ignorees, comme pour log_alert(). Retourne le nombre d'alertes inserees."""
    names = class_names or (TRANSACTION_CLASS_NAMES if domaine == "transactions" else CLASS_NAMES)
    to_insert = [e for e in entries if e["pred_class"] != 0]
    if not to_insert:
        return 0
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # executemany : une seule connexion/transaction pour tout le lot,
                # au lieu d'une connexion par alerte - le vrai gain de performance.
                cur.executemany(
                    "INSERT INTO alerts (id, domaine, horodatage, source, menace, confiance, details, statut, fermee_le) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        (str(uuid.uuid4())[:8], domaine, horodatage, e["source"], names[e["pred_class"]],
                         round(e["confidence"], 1), e.get("details", ""), "Ouvert", None)
                        for e in to_insert
                    ],
                )
        return len(to_insert)

    # Repli JSON : une seule lecture/ecriture pour tout le lot (au lieu d'une
    # lecture/ecriture par alerte).
    state = load_org_state(domaine)
    new_entries = [
        {
            "ID": str(uuid.uuid4())[:8], "Horodatage": horodatage, "Source": e["source"],
            "Menace": names[e["pred_class"]], "Confiance (%)": round(e["confidence"], 1),
            "Details": e.get("details", ""), "Statut": "Ouvert", "Fermee_le": None,
        }
        for e in to_insert
    ]
    state.setdefault("alert_log", [])[:0] = new_entries  # insertion en tete, ordre du lot preserve
    save_org_state(state, domaine)
    return len(to_insert)


def toggle_alert_status(alert_id: str, domaine: str = "reseau") -> bool:
    """Bascule Ouvert <-> Ferme pour une alerte precise. Retourne True si trouvee."""
    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT statut FROM alerts WHERE id = %s AND domaine = %s", (alert_id, domaine))
                row = cur.fetchone()
                if not row:
                    return False
                is_open = row[0] == "Ouvert"
                new_statut = "Ferme" if is_open else "Ouvert"
                new_fermee_le = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_open else None
                cur.execute(
                    "UPDATE alerts SET statut = %s, fermee_le = %s WHERE id = %s AND domaine = %s",
                    (new_statut, new_fermee_le, alert_id, domaine),
                )
        return True

    state = load_org_state(domaine)
    found = False
    for a in state.get("alert_log", []):
        if a["ID"] == alert_id:
            is_open = a.get("Statut", "Ouvert") == "Ouvert"
            a["Statut"] = "Ferme" if is_open else "Ouvert"
            a["Fermee_le"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_open else None
            found = True
    if found:
        save_org_state(state, domaine)
    return found


def compute_security_score(alert_log: list) -> int:
    """Score composite /100 : penalise le trafic recent selon sa gravite ponderee.
    100 = aucune menace ouverte recemment ; descend selon le volume et la gravite
    des alertes encore ouvertes (une alerte fermee ne penalise plus le score).
    Fonctionne pour les deux domaines : pour les transactions (2 classes), tout
    poids inconnu retombe sur 1 (severite uniforme, coherent avec un modele
    binaire Legitime/Suspecte sans sous-categories de gravite)."""
    open_alerts = [a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"]
    if not open_alerts:
        return 100
    weight_map = {"Scan de Ports / Reconnaissance": 1, "Attaque DDoS / Volumetrique": 2,
                  "Infiltration / Brute-Force / Exfiltration": 3, "Suspecte": 2}
    total_weight = sum(weight_map.get(a["Menace"], 1) for a in open_alerts)
    avg_severity = total_weight / len(open_alerts)  # 1 a 3
    volume_penalty = min(40, len(open_alerts) * 0.5)
    severity_penalty = (avg_severity / 3) * 60
    return max(0, round(100 - volume_penalty - severity_penalty))


def record_score_snapshot(score: int, domaine: str = "reseau") -> dict:
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO score_history (domaine, horodatage, score) VALUES (%s, %s, %s)",
                    (domaine, horodatage, score),
                )
                # Garde uniquement les 50 derniers points par domaine (coherent avec le comportement JSON)
                cur.execute("""
                    DELETE FROM score_history WHERE domaine = %s AND seq NOT IN (
                        SELECT seq FROM score_history WHERE domaine = %s ORDER BY seq DESC LIMIT 50
                    )
                """, (domaine, domaine))
        return load_org_state(domaine)

    state = load_org_state(domaine)
    state.setdefault("score_history", []).append({"Horodatage": horodatage, "Score": score})
    state["score_history"] = state["score_history"][-50:]
    save_org_state(state, domaine)
    return state


def mttr_hours(alert_log: list):
    """Temps moyen de resolution, en heures, calcule sur les alertes fermees."""
    durations = []
    for a in alert_log:
        if a.get("Statut") == "Ferme" and a.get("Fermee_le"):
            try:
                t0 = datetime.strptime(a["Horodatage"], "%Y-%m-%d %H:%M:%S")
                t1 = datetime.strptime(a["Fermee_le"], "%Y-%m-%d %H:%M:%S")
                durations.append((t1 - t0).total_seconds() / 3600)
            except (ValueError, KeyError):
                continue
    if not durations:
        return None
    return sum(durations) / len(durations)


def trend_delta_pct(alert_log: list, days: int = 7):
    """Compare le nombre d'alertes de la fenetre en cours (derniers `days` jours)
    a la fenetre precedente de meme duree. Retourne (delta_pct, texte) ou
    (None, texte_explicatif) si pas assez d'historique pour comparer honnetement."""
    if not alert_log:
        return None, "Pas encore assez de donnees pour une tendance."
    try:
        horodatages = [datetime.strptime(a["Horodatage"], "%Y-%m-%d %H:%M:%S") for a in alert_log]
    except (ValueError, KeyError):
        return None, "Pas encore assez de donnees pour une tendance."
    now = max(horodatages)
    window_current = sum(1 for h in horodatages if now - timedelta(days=days) <= h <= now)
    window_previous = sum(1 for h in horodatages if now - timedelta(days=2 * days) <= h < now - timedelta(days=days))
    oldest = min(horodatages)
    if oldest > now - timedelta(days=2 * days):
        return None, f"Historique < {2*days} j - tendance pas encore fiable."
    if window_previous == 0:
        return None, "Pas d'activite sur la periode precedente pour comparer."
    delta = (window_current - window_previous) / window_previous * 100
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
    return delta, f"{arrow} {abs(delta):.1f}% vs les {days} j precedents"


def severity_breakdown(alert_log: list) -> dict:
    """Comptage des alertes OUVERTES par categorie de gravite."""
    open_alerts = [a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"]
    counts = {}
    for a in open_alerts:
        counts[a["Menace"]] = counts.get(a["Menace"], 0) + 1
    return counts


def day_severity_series(alert_log: list, days: int = 7) -> dict:
    """Serie temporelle {jour: {menace: count}} sur les `days` derniers jours,
    pour le graphique multi-courbes 'Alertes par jour et par gravite'."""
    try:
        entries = [
            (datetime.strptime(a["Horodatage"], "%Y-%m-%d %H:%M:%S").date(), a["Menace"])
            for a in alert_log
        ]
    except (ValueError, KeyError):
        return {}
    if not entries:
        return {}
    now = max(d for d, _ in entries)
    cutoff = now - timedelta(days=days)
    series = {}
    for d, menace in entries:
        if d >= cutoff:
            series.setdefault(str(d), {}).setdefault(menace, 0)
            series[str(d)][menace] += 1
    return dict(sorted(series.items()))
