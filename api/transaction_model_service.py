"""
Service de chargement du modele de fraude transactionnelle (PROTOTYPE).

*** Entraine sur des donnees SYNTHETIQUES *** (voir
src/transaction_fraud/generate_synthetic_data.py pour l'avertissement complet).
A ne jamais presenter comme valide sur de vraies transactions tant qu'un
reentrainement sur des donnees reelles n'a pas ete effectue.

Suit exactement le meme pattern que api/model_service.py (le modele reseau),
pour la coherence architecturale, mais reste un service independant : les
deux modeles ne partagent ni schema d'entree ni logique metier.
"""
import json
from pathlib import Path
from functools import lru_cache

import joblib
import pandas as pd

from core.model_version_check import check_sklearn_version

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "outputs" / "transaction_fraud"
MODEL_DIR = OUT_DIR / "models"

CLASS_NAMES = {0: "Legitime", 1: "Suspecte"}


class TransactionModelService:
    def __init__(self):
        self.features = joblib.load(MODEL_DIR / "feature_names_transactions.joblib")
        self.medians = joblib.load(MODEL_DIR / "imputation_medians_transactions.joblib")
        self.scaler = joblib.load(MODEL_DIR / "scaler_transactions.joblib")
        self.model = joblib.load(MODEL_DIR / "best_model_transactions.joblib")
        with open(OUT_DIR / "best_model_info_transactions.json") as f:
            self.info = json.load(f)
        check_sklearn_version(self.info, "Modele fraude transactionnelle")

    def preprocess(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df = df_raw.copy()
        for col in self.features:
            if col not in df.columns:
                df[col] = self.medians[col]
        df = df[self.features]
        return pd.DataFrame(self.scaler.transform(df), columns=self.features)

    def predict(self, df_raw: pd.DataFrame):
        X = self.preprocess(df_raw)
        preds = self.model.predict(X)
        probas = self.model.predict_proba(X)
        confidences = probas.max(axis=1) * 100
        return preds, confidences, probas

    def predict_with_threshold(self, df_raw: pd.DataFrame, threshold: float = 0.5):
        """threshold = probabilite minimale de fraude (classe 1) requise pour
        classer une transaction comme suspecte. threshold=0.5 reproduit le
        comportement standard de predict()."""
        X = self.preprocess(df_raw)
        probas = self.model.predict_proba(X)
        p_fraude = probas[:, 1]
        preds = (p_fraude >= threshold).astype(int)
        confidences = probas.max(axis=1) * 100
        return preds, confidences, probas


@lru_cache(maxsize=1)
def get_transaction_model_service() -> TransactionModelService:
    return TransactionModelService()
