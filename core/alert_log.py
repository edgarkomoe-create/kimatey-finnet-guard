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
ORG_STATE_FILE = BASE_DIR / "outputs" / "organisation_state.json"

CLASS_NAMES = {0: "Normal / Legitime", 1: "Scan de Ports / Reconnaissance",
               2: "Attaque DDoS / Volumetrique", 3: "Infiltration / Brute-Force / Exfiltration"}
SEVERITY_WEIGHT = {1: 1, 2: 2, 3: 3}  # 1=scan (faible), 2=DDoS (eleve), 3=infiltration (critique)


def _load_org_state_pg() -> dict:
    db.init_schema()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, horodatage, source, menace, confiance, details, statut, fermee_le "
                "FROM alerts ORDER BY seq DESC"
            )
            alert_log = [
                {
                    "ID": row[0], "Horodatage": row[1], "Source": row[2], "Menace": row[3],
                    "Confiance (%)": row[4], "Details": row[5] or "", "Statut": row[6], "Fermee_le": row[7],
                }
                for row in cur.fetchall()
            ]
            cur.execute("SELECT horodatage, score FROM score_history ORDER BY seq ASC")
            score_history = [{"Horodatage": row[0], "Score": row[1]} for row in cur.fetchall()]
    return {"alert_log": alert_log, "score_history": score_history}


def _save_org_state_pg(state: dict) -> None:
    """Remplacement complet (delete + reinsert) - simple et correct a l'echelle
    d'une demo (quelques centaines d'alertes au plus), evite une logique de
    diff plus complexe."""
    db.init_schema()
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM alerts")
            for entry in reversed(state.get("alert_log", [])):  # reversed : le plus ancien insere en premier
                cur.execute(
                    "INSERT INTO alerts (id, horodatage, source, menace, confiance, details, statut, fermee_le) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (entry["ID"], entry["Horodatage"], entry.get("Source"), entry.get("Menace"),
                     entry.get("Confiance (%)"), entry.get("Details", ""), entry.get("Statut", "Ouvert"),
                     entry.get("Fermee_le")),
                )
            cur.execute("DELETE FROM score_history")
            for entry in state.get("score_history", []):
                cur.execute(
                    "INSERT INTO score_history (horodatage, score) VALUES (%s, %s)",
                    (entry["Horodatage"], entry["Score"]),
                )


def load_org_state() -> dict:
    if db.database_configured():
        return _load_org_state_pg()
    if ORG_STATE_FILE.exists():
        with open(ORG_STATE_FILE) as f:
            return json.load(f)
    return {"alert_log": [], "score_history": []}


def save_org_state(state: dict) -> None:
    if db.database_configured():
        _save_org_state_pg(state)
        return
    ORG_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ORG_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def log_alert(source_label: str, pred_class: int, confidence: float, details: str = "") -> None:
    if pred_class == 0:
        return
    entry_id = str(uuid.uuid4())[:8]
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alerts (id, horodatage, source, menace, confiance, details, statut, fermee_le) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (entry_id, horodatage, source_label, CLASS_NAMES[pred_class], round(confidence, 1),
                     details, "Ouvert", None),
                )
        return
    state = load_org_state()
    state.setdefault("alert_log", []).insert(0, {
        "ID": entry_id, "Horodatage": horodatage, "Source": source_label,
        "Menace": CLASS_NAMES[pred_class], "Confiance (%)": round(confidence, 1),
        "Details": details, "Statut": "Ouvert", "Fermee_le": None,
    })
    save_org_state(state)


def toggle_alert_status(alert_id: str) -> bool:
    """Bascule Ouvert <-> Ferme pour une alerte precise. Retourne True si trouvee."""
    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT statut FROM alerts WHERE id = %s", (alert_id,))
                row = cur.fetchone()
                if not row:
                    return False
                is_open = row[0] == "Ouvert"
                new_statut = "Ferme" if is_open else "Ouvert"
                new_fermee_le = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_open else None
                cur.execute(
                    "UPDATE alerts SET statut = %s, fermee_le = %s WHERE id = %s",
                    (new_statut, new_fermee_le, alert_id),
                )
        return True

    state = load_org_state()
    found = False
    for a in state.get("alert_log", []):
        if a["ID"] == alert_id:
            is_open = a.get("Statut", "Ouvert") == "Ouvert"
            a["Statut"] = "Ferme" if is_open else "Ouvert"
            a["Fermee_le"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_open else None
            found = True
    if found:
        save_org_state(state)
    return found


def compute_security_score(alert_log: list) -> int:
    """Score composite /100 : penalise le trafic recent selon sa gravite ponderee.
    100 = aucune menace ouverte recemment ; descend selon le volume et la gravite
    des alertes encore ouvertes (une alerte fermee ne penalise plus le score)."""
    open_alerts = [a for a in alert_log if a.get("Statut", "Ouvert") == "Ouvert"]
    if not open_alerts:
        return 100
    weight_map = {"Scan de Ports / Reconnaissance": 1, "Attaque DDoS / Volumetrique": 2,
                  "Infiltration / Brute-Force / Exfiltration": 3}
    total_weight = sum(weight_map.get(a["Menace"], 1) for a in open_alerts)
    avg_severity = total_weight / len(open_alerts)  # 1 a 3
    volume_penalty = min(40, len(open_alerts) * 0.5)
    severity_penalty = (avg_severity / 3) * 60
    return max(0, round(100 - volume_penalty - severity_penalty))


def record_score_snapshot(score: int) -> dict:
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db.database_configured():
        db.init_schema()
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO score_history (horodatage, score) VALUES (%s, %s)", (horodatage, score))
                # Garde uniquement les 50 derniers points (coherent avec le comportement JSON)
                cur.execute("""
                    DELETE FROM score_history WHERE seq NOT IN (
                        SELECT seq FROM score_history ORDER BY seq DESC LIMIT 50
                    )
                """)
        return load_org_state()

    state = load_org_state()
    state.setdefault("score_history", []).append({"Horodatage": horodatage, "Score": score})
    state["score_history"] = state["score_history"][-50:]
    save_org_state(state)
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
