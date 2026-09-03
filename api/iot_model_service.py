"""
Service de chargement et de prediction - modele Securite IIoT.

Reutilise exactement les memes artefacts (scaler, modele, liste de variables)
que ceux produits par src/iot_security/train_pipeline.py, pour garantir des
predictions strictement identiques entre l'API et tout futur module Streamlit
- meme principe que api/model_service.py (reseau) et
api/transaction_model_service.py (transactions).

Point specifique a ce domaine : le modele a ete entraine sur des variables de
type "compteur par seconde" (ex. network_fragmented-packets_par_sec), obtenues
en divisant le compteur brut par la duree reelle de capture (timestamp_end -
timestamp_start) - voir la note methodologique dans best_model_info_iot.json
pour le contexte complet (biais de duree de capture systematique entre benin
et attaques dans le jeu de donnees source, corrige avant entrainement). Ce
service applique la MEME transformation a l'inference, a partir des colonnes
brutes + timestamp_start/timestamp_end fournies en entree.
"""
import json
from pathlib import Path
from functools import lru_cache

import joblib
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs" / "iot_security"
MODEL_DIR = OUT_DIR / "models"

CLASS_NAMES = {
    "benign": "Trafic normal",
    "recon": "Reconnaissance / Scan",
    "dos": "Attaque DoS (source unique)",
    "ddos": "Attaque DDoS (distribuee)",
    "mitm": "Interception (Man-in-the-Middle)",
    "malware": "Malware (ex. Mirai)",
    "web": "Attaque applicative Web (injection...)",
    "bruteforce": "Force brute (identifiants)",
}


class IotModelService:
    """Encapsule le modele Securite IIoT optimal et son pretraitement (singleton)."""

    def __init__(self):
        self.model = joblib.load(MODEL_DIR / "best_model_iot.joblib")
        self.scaler = joblib.load(MODEL_DIR / "scaler_iot.joblib")
        self.features = joblib.load(MODEL_DIR / "feature_names_iot.joblib")
        with open(OUT_DIR / "best_model_info_iot.json") as f:
            self.info = json.load(f)

        # Colonnes brutes necessaires pour reconstruire chaque variable "_par_sec"
        self.colonnes_taux = [f for f in self.features if f.endswith("_par_sec")]
        self.colonnes_brutes_necessaires = [c[:-len("_par_sec")] for c in self.colonnes_taux]
        self.colonnes_statistiques = [f for f in self.features if not f.endswith("_par_sec")]

    def preprocess(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Reconstruit les variables '_par_sec' a partir des compteurs bruts et de
        la duree de capture (timestamp_start/timestamp_end), puis assemble les 30
        variables du modele dans le bon ordre avant standardisation."""
        df = df_raw.copy()

        if "timestamp_start" in df.columns and "timestamp_end" in df.columns:
            ts_start = pd.to_datetime(df["timestamp_start"], format="ISO8601", errors="coerce")
            ts_end = pd.to_datetime(df["timestamp_end"], format="ISO8601", errors="coerce")
            duree_sec = (ts_end - ts_start).dt.total_seconds()
            duree_sec = duree_sec.where(duree_sec > 0, 1.0)  # repli a 1s si duree absente/invalide
        else:
            duree_sec = pd.Series(1.0, index=df.index)  # hypothese neutre si colonnes absentes

        for col_taux, col_brute in zip(self.colonnes_taux, self.colonnes_brutes_necessaires):
            if col_brute in df.columns:
                df[col_taux] = df[col_brute] / duree_sec
            else:
                df[col_taux] = 0.0  # valeur neutre si le compteur brut est absent du fichier importe

        for col in self.colonnes_statistiques:
            if col not in df.columns:
                df[col] = 0.0

        X = df[self.features].fillna(0.0)
        X_scaled = pd.DataFrame(self.scaler.transform(X), columns=self.features, index=X.index)
        return X_scaled

    def predict(self, df_raw: pd.DataFrame):
        X = self.preprocess(df_raw)
        preds = self.model.predict(X)
        probas = self.model.predict_proba(X)
        confidences = probas.max(axis=1) * 100
        return preds, confidences, probas

    def format_prediction(self, pred_label: str, confidence: float) -> dict:
        return {
            "classe_predite": pred_label,
            "libelle": CLASS_NAMES.get(pred_label, pred_label),
            "confiance_pct": round(float(confidence), 1),
            "est_menace": pred_label != "benign",
        }


@lru_cache(maxsize=1)
def get_iot_model_service() -> IotModelService:
    return IotModelService()
