"""
Tests unitaires - Etape 1 : Pretraitement et nettoyage des donnees.
Valide l'absence de valeurs manquantes residuelles, l'absence de fuite de donnees
(data leakage) entre train et test, la stratification du split, et la standardisation.
"""
import json
import joblib
import numpy as np
import pandas as pd
import pytest

FEATURES = [
    "Duree_Connexion", "Octets_Source_Vers_Dest", "Octets_Dest_Vers_Source",
    "Taux_Paquets_Secondes", "Fenetre_TCP_Moyenne", "Ports_Dest_Distincts",
    "Connexions_Simultanees", "Taux_Erreur_CheckSum", "Frequence_SYN_Flags",
]


@pytest.fixture(scope="module")
def data():
    return {
        "X_train": pd.read_csv("outputs/X_train.csv"),
        "X_test": pd.read_csv("outputs/X_test.csv"),
        "y_train": pd.read_csv("outputs/y_train.csv").squeeze("columns"),
        "y_test": pd.read_csv("outputs/y_test.csv").squeeze("columns"),
        "X_train_raw": pd.read_csv("outputs/X_train_raw.csv"),
        "X_test_raw": pd.read_csv("outputs/X_test_raw.csv"),
    }


@pytest.fixture(scope="module")
def raw_dataset():
    df = pd.read_csv("data/Enterprise_Network_Traffic_BigData.csv")
    df["Statut_Menace"] = df["Statut_Menace"].astype(str).str.strip().astype(int)
    return df


class TestJeuDeDonnees:
    def test_dataset_brut_50000_lignes(self, raw_dataset):
        assert raw_dataset.shape[0] == 50000

    def test_dataset_brut_9_variables_plus_cible(self, raw_dataset):
        assert raw_dataset.shape[1] == 10

    def test_pas_de_doublons(self, raw_dataset):
        assert raw_dataset.duplicated().sum() == 0

    def test_cible_a_4_classes(self, raw_dataset):
        assert set(raw_dataset["Statut_Menace"].unique()) == {0, 1, 2, 3}


class TestImputation:
    def test_aucune_valeur_manquante_apres_imputation_train(self, data):
        assert data["X_train"].isna().sum().sum() == 0

    def test_aucune_valeur_manquante_apres_imputation_test(self, data):
        assert data["X_test"].isna().sum().sum() == 0

    def test_medianes_sauvegardees_pour_toutes_les_variables(self):
        medians = joblib.load("outputs/models/imputation_medians.joblib")
        assert set(medians.keys()) == set(FEATURES)
        assert all(np.isfinite(v) for v in medians.values())


class TestEcretageIQR:
    def test_bornes_iqr_sauvegardees_pour_toutes_les_variables(self):
        bounds = joblib.load("outputs/models/iqr_bounds.joblib")
        assert set(bounds.keys()) == set(FEATURES)
        for low, high in bounds.values():
            assert low <= high

    def test_valeurs_train_dans_les_bornes_iqr(self, data):
        bounds = joblib.load("outputs/models/iqr_bounds.joblib")
        for col, (low, high) in bounds.items():
            assert data["X_train_raw"][col].min() >= low - 1e-6
            assert data["X_train_raw"][col].max() <= high + 1e-6

    def test_valeurs_test_dans_les_bornes_iqr(self, data):
        """Le test doit aussi etre ecrete avec les bornes du TRAIN (pas de fuite)."""
        bounds = joblib.load("outputs/models/iqr_bounds.joblib")
        for col, (low, high) in bounds.items():
            assert data["X_test_raw"][col].min() >= low - 1e-6
            assert data["X_test_raw"][col].max() <= high + 1e-6


class TestSplitStratifie:
    def test_proportion_80_20(self, data):
        n_train, n_test = len(data["X_train"]), len(data["X_test"])
        total = n_train + n_test
        assert total == 50000
        assert abs(n_train / total - 0.8) < 0.01

    def test_stratification_preserve_les_proportions_de_classes(self, data):
        """Les proportions de chaque classe doivent etre quasi identiques entre
        train et test (tolerance 1 point de pourcentage)."""
        train_props = data["y_train"].value_counts(normalize=True).sort_index()
        test_props = data["y_test"].value_counts(normalize=True).sort_index()
        for c in [0, 1, 2, 3]:
            assert abs(train_props[c] - test_props[c]) < 0.01

    def test_aucun_chevauchement_dimensions(self, data):
        assert data["X_train"].shape[1] == data["X_test"].shape[1] == len(FEATURES)


class TestStandardisation:
    def test_scaler_sauvegarde_et_coherent(self):
        scaler = joblib.load("outputs/models/scaler.joblib")
        assert len(scaler.mean_) == len(FEATURES)
        assert len(scaler.scale_) == len(FEATURES)

    def test_train_standardise_moyenne_nulle(self, data):
        means = data["X_train"][FEATURES].mean()
        assert (means.abs() < 0.05).all(), f"Moyennes hors tolerance: {means.to_dict()}"

    def test_train_standardise_ecart_type_unitaire(self, data):
        stds = data["X_train"][FEATURES].std()
        assert ((stds - 1.0).abs() < 0.05).all(), f"Ecarts-types hors tolerance: {stds.to_dict()}"

    def test_scaler_ajuste_uniquement_sur_train_no_leakage(self, data):
        """Le test ne doit PAS avoir une moyenne/ecart-type parfaits de 0/1
        (signe qu'il n'a pas ete utilise pour calculer le scaler)."""
        means_test = data["X_test"][FEATURES].mean()
        # sur le test, la moyenne ne doit pas etre exactement 0 partout
        assert not (means_test.abs() < 1e-9).all()
