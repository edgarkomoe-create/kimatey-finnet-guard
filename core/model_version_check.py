"""
Verification de compatibilite de version scikit-learn au chargement d'un
modele serialise (.joblib). Partage entre api/model_service.py (reseau) et
api/transaction_model_service.py (fraude), pour eviter un import croise
entre les deux services API et garder ce controle en un seul endroit.

Pourquoi ce controle existe : requirements.txt epingle scikit-learn a une
version exacte (==) plutot qu'un minimum (>=), precisement parce que les
objets scikit-learn serialises via joblib/pickle ne sont pas garantis
stables entre versions mineures - un ecart peut charger sans erreur mais
produire des predictions subtilement differentes de celles validees a
l'entrainement. Ce module detecte l'ecart et avertit clairement (log +
warning Python) au lieu de le laisser passer silencieusement, sans pour
autant bloquer le demarrage (un ecart mineur reste souvent sans consequence
reelle - on avertit, on ne devine pas a la place de la personne qui exploite
le service).
"""
import logging
import warnings

import sklearn

logger = logging.getLogger(__name__)


def check_sklearn_version(info: dict, model_label: str) -> None:
    """info : le dict de metadonnees charge depuis best_model_info*.json.
    model_label : nom lisible du modele, pour un message d'avertissement clair
    (ex. "Modele reseau", "Modele fraude transactionnelle")."""
    trained_version = info.get("sklearn_version")
    if not trained_version:
        logger.warning(
            "%s : version scikit-learn d'entrainement non enregistree dans les "
            "metadonnees (modele entraine avant l'ajout de ce controle). "
            "Impossible de verifier la compatibilite.", model_label,
        )
        return
    if trained_version != sklearn.__version__:
        message = (
            f"{model_label} : version scikit-learn installee ({sklearn.__version__}) "
            f"differente de celle utilisee a l'entrainement ({trained_version}). "
            "Un ecart de version peut charger le modele sans erreur mais produire "
            "des predictions subtilement differentes de celles validees. "
            "Reentrainer avec la version installee, ou aligner requirements.txt "
            f"sur scikit-learn=={trained_version}."
        )
        logger.warning(message)
        warnings.warn(message, RuntimeWarning, stacklevel=2)
