"""
Tests unitaires - Etapes 2 a 4 : modeles baseline, selection de variables (RFE +
elagage), et optimisation par GridSearchCV.
Valide la coherence des metriques produites, le chargement du modele final,
et la coherence des variables selectionnees avec le modele retenu.
"""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

ALGOS_BASELINE = [
    "Regression_Logistique", "KNN", "Naive_Bayes_Gaussien", "SVM", "Arbre_Decision",
]
METRIC_COLS = [
    "Exactitude", "Precision (macro)", "Rappel (macro)", "F1-score (macro)", "AUC (macro)",
]


def _assert_metrics_in_range(df):
    for col in METRIC_COLS:
        assert col in df.columns, f"Colonne manquante : {col}"
        assert (df[col] >= 0).all() and (df[col] <= 1).all(), (
            f"Valeurs hors intervalle [0,1] dans {col} : {df[col].tolist()}"
        )


class TestEtape2Baseline:
    @pytest.fixture(scope="module")
    def results(self):
        return pd.read_csv("outputs/baseline_results.csv")

    def test_cinq_algorithmes_presents(self, results):
        assert set(results["Modele"]) == set(ALGOS_BASELINE)

    def test_metriques_dans_intervalle_valide(self, results):
        _assert_metrics_in_range(results)

    def test_tous_les_modeles_baseline_sauvegardes(self):
        for algo in ALGOS_BASELINE:
            m = joblib.load(f"outputs/models/baseline/{algo}.joblib")
            assert hasattr(m, "predict")

    def test_exactitude_superieure_au_hasard(self, results):
        """Avec 4 classes desequilibrees (classe majoritaire ~75%), un modele
        utile doit largement depasser un classifieur trivial (~0.75)."""
        assert (results["Exactitude"] > 0.9).all()


class TestEtape3SelectionVariables:
    @pytest.fixture(scope="module")
    def selected(self):
        with open("outputs/selected_features.json") as f:
            return json.load(f)

    @pytest.fixture(scope="module")
    def reduced_results(self):
        return pd.read_csv("outputs/reduced_results.csv")

    @pytest.fixture(scope="module")
    def comparison(self):
        return pd.read_csv("outputs/comparison_step3.csv")

    def test_cinq_variables_selectionnees_par_rfe(self, selected):
        assert selected["n_selected"] == 5
        assert len(selected["selected_features"]) == 5

    def test_variables_selectionnees_font_partie_des_9_variables_initiales(self, selected):
        toutes = {
            "Duree_Connexion", "Octets_Source_Vers_Dest", "Octets_Dest_Vers_Source",
            "Taux_Paquets_Secondes", "Fenetre_TCP_Moyenne", "Ports_Dest_Distincts",
            "Connexions_Simultanees", "Taux_Erreur_CheckSum", "Frequence_SYN_Flags",
        }
        assert set(selected["selected_features"]).issubset(toutes)

    def test_metriques_reduites_dans_intervalle_valide(self, reduced_results):
        _assert_metrics_in_range(reduced_results)

    def test_performance_preservee_apres_reduction(self, results_comparaison=None):
        """La reduction a 5 variables ne doit pas degrader excessivement la
        performance par rapport au modele complet (perte d'exactitude < 2 points)."""
        baseline = pd.read_csv("outputs/baseline_results.csv").set_index("Modele")
        reduced = pd.read_csv("outputs/reduced_results.csv")
        mapping = {
            "Regression_Logistique_reduit": "Regression_Logistique",
            "KNN_reduit": "KNN",
            "Naive_Bayes_Gaussien_reduit": "Naive_Bayes_Gaussien",
            "SVM_reduit": "SVM",
            "Arbre_Decision_elague": "Arbre_Decision",
        }
        for _, row in reduced.iterrows():
            full_name = mapping[row["Modele"]]
            full_acc = baseline.loc[full_name, "Exactitude"]
            assert full_acc - row["Exactitude"] < 0.02, (
                f"{row['Modele']} perd trop de performance vs {full_name}"
            )

    def test_arbre_elague_moins_complexe_que_arbre_complet(self):
        """L'elagage cout-complexite doit reduire significativement la taille
        de l'arbre (moins de noeuds, profondeur moindre)."""
        full_tree = joblib.load("outputs/models/baseline/Arbre_Decision.joblib")
        pruned_tree = joblib.load("outputs/models/reduced/Arbre_Decision_elague.joblib")
        assert pruned_tree.tree_.node_count < full_tree.tree_.node_count
        assert pruned_tree.get_depth() < full_tree.get_depth()


class TestEtape4Optimisation:
    @pytest.fixture(scope="module")
    def optimized_results(self):
        return pd.read_csv("outputs/optimized_results.csv")

    @pytest.fixture(scope="module")
    def best_info(self):
        with open("outputs/best_model_info.json") as f:
            return json.load(f)

    def test_metriques_optimisees_dans_intervalle_valide(self, optimized_results):
        _assert_metrics_in_range(optimized_results)

    def test_cv_best_score_present_et_valide(self, optimized_results):
        assert "cv_best_score_accuracy" in optimized_results.columns
        assert (optimized_results["cv_best_score_accuracy"] >= 0).all()
        assert (optimized_results["cv_best_score_accuracy"] <= 1).all()

    def test_modele_champion_est_larbre_de_decision_optimise(self, optimized_results, best_info):
        idx_best = optimized_results["Exactitude"].idxmax()
        assert optimized_results.loc[idx_best, "Modele"] == best_info["name"]

    def test_grid_search_ne_degrade_pas_la_performance(self, optimized_results):
        """GridSearchCV doit maintenir ou ameliorer la performance par rapport
        aux modeles reduits (elagage/RFE) pour chaque algorithme."""
        reduced = pd.read_csv("outputs/reduced_results.csv")
        mapping = {
            "Regression_Logistique_optimise": "Regression_Logistique_reduit",
            "KNN_optimise": "KNN_reduit",
            "Naive_Bayes_Gaussien_optimise": "Naive_Bayes_Gaussien_reduit",
            "SVM_optimise": "SVM_reduit",
            "Arbre_Decision_optimise": "Arbre_Decision_elague",
        }
        reduced_idx = reduced.set_index("Modele")
        for _, row in optimized_results.iterrows():
            reduit_name = mapping[row["Modele"]]
            acc_reduit = reduced_idx.loc[reduit_name, "Exactitude"]
            assert row["Exactitude"] >= acc_reduit - 0.01, (
                f"{row['Modele']} degrade par rapport a {reduit_name}"
            )


class TestModeleFinal:
    @pytest.fixture(scope="module")
    def best_model(self):
        return joblib.load("outputs/models/best_model.joblib")

    @pytest.fixture(scope="module")
    def selected_features(self):
        with open("outputs/selected_features.json") as f:
            return json.load(f)["selected_features"]

    def test_modele_final_se_charge_correctement(self, best_model):
        assert hasattr(best_model, "predict")
        assert hasattr(best_model, "predict_proba")

    def test_modele_final_attend_5_variables(self, best_model, selected_features):
        assert best_model.n_features_in_ == len(selected_features) == 5

    def test_modele_final_connait_les_4_classes(self, best_model):
        assert list(best_model.classes_) == [0, 1, 2, 3]

    def test_modele_final_predit_sur_un_echantillon_reel(self, best_model, selected_features):
        """Le modele doit produire une prediction valide sur un vrai flux du
        jeu de test (variables selectionnees, deja standardisees)."""
        X_test = pd.read_csv("outputs/X_test.csv")
        assert set(selected_features).issubset(X_test.columns)
        sample = X_test[selected_features].iloc[:10]
        preds = best_model.predict(sample)
        probas = best_model.predict_proba(sample)
        assert preds.shape == (10,)
        assert set(preds).issubset({0, 1, 2, 3})
        assert probas.shape == (10, 4)
        assert np.allclose(probas.sum(axis=1), 1.0, atol=1e-6)

    def test_modele_final_coherent_avec_le_test_set_complet(self, best_model, selected_features, ):
        """L'exactitude recalculee directement doit correspondre a celle
        enregistree dans best_model_info.json (a 0.5 point pres)."""
        X_test = pd.read_csv("outputs/X_test.csv")
        y_test = pd.read_csv("outputs/y_test.csv").squeeze("columns")
        with open("outputs/best_model_info.json") as f:
            info = json.load(f)
        preds = best_model.predict(X_test[selected_features])
        acc = (preds == y_test).mean()
        assert abs(acc - info["accuracy"]) < 0.005
