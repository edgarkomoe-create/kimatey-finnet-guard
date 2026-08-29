"""
Service de chargement du modele et du pipeline de pretraitement.
Reutilise exactement les memes artefacts (scaler, medianes, bornes IQR, modele
optimal issu de GridSearchCV) que ceux produits par les scripts src/ et utilises
par l'application Streamlit (app/app.py), afin de garantir des predictions
strictement identiques entre les deux interfaces.
"""
import json
from pathlib import Path
from functools import lru_cache

import joblib
import pandas as pd

from core.model_version_check import check_sklearn_version

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs"
MODEL_DIR = OUT_DIR / "models"

CLASS_NAMES = {
    0: "Normal / Legitime",
    1: "Scan de Ports / Reconnaissance",
    2: "Attaque DDoS / Volumetrique",
    3: "Infiltration / Brute-Force / Exfiltration",
}


class ModelService:
    """Encapsule le modele optimal et le pipeline de pretraitement (singleton)."""

    def __init__(self):
        self.features = joblib.load(MODEL_DIR / "feature_names.joblib")
        self.medians = joblib.load(MODEL_DIR / "imputation_medians.joblib")
        self.iqr_bounds = joblib.load(MODEL_DIR / "iqr_bounds.joblib")
        self.scaler = joblib.load(MODEL_DIR / "scaler.joblib")
        self.model = joblib.load(MODEL_DIR / "best_model.joblib")
        with open(OUT_DIR / "best_model_info.json") as f:
            self.info = json.load(f)
        self.selected_features = self.info["features_used"]
        check_sklearn_version(self.info, "Modele reseau")

    def preprocess(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Imputation mediane -> ecretage IQR -> standardisation -> selection RFE."""
        df = df_raw.copy()
        for col in self.features:
            if col not in df.columns:
                df[col] = self.medians[col]
            df[col] = df[col].fillna(self.medians[col])
            low, high = self.iqr_bounds[col]
            df[col] = df[col].clip(lower=low, upper=high)
        df_scaled = pd.DataFrame(
            self.scaler.transform(df[self.features]), columns=self.features, index=df.index
        )
        return df_scaled[self.selected_features]

    def predict(self, df_raw: pd.DataFrame):
        X = self.preprocess(df_raw)
        preds = self.model.predict(X)
        probas = self.model.predict_proba(X)
        return preds, probas

    def predict_with_threshold(self, df_raw: pd.DataFrame, threshold: float = 0.5):
        """Applique un seuil de sensibilite personnalise au lieu de l'argmax brut
        (voir core/sensitivity.py). threshold = confiance minimale requise en
        P(Normal) pour classer un flux comme normal ; en-dessous, le flux est
        classe selon la classe de menace la plus probable parmi les 3 restantes.
        threshold=0.5 reproduit le comportement standard de predict()."""
        X = self.preprocess(df_raw)
        probas = self.model.predict_proba(X)
        p_normal = probas[:, 0]
        # Classe de menace la plus probable parmi les colonnes 1,2,3 (jamais 0)
        threat_argmax = probas[:, 1:].argmax(axis=1) + 1
        preds = pd.Series(0, index=range(len(probas)))
        preds[p_normal < threshold] = threat_argmax[p_normal < threshold]
        return preds.to_numpy(), probas

    def format_prediction(self, pred_class: int, proba_row) -> dict:
        confidence = float(proba_row.max() * 100)
        probabilities = {
            CLASS_NAMES[c]: round(float(proba_row[i]) * 100, 2)
            for i, c in enumerate(sorted(CLASS_NAMES.keys()))
        }
        return {
            "predicted_class": int(pred_class),
            "predicted_label": CLASS_NAMES[int(pred_class)],
            "confidence": round(confidence, 2),
            "probabilities": probabilities,
            "is_threat": int(pred_class) != 0,
        }


@lru_cache(maxsize=1)
def get_model_service() -> "ModelService":
    """Charge le modele une seule fois (mise en cache) au premier appel."""
    return ModelService()
