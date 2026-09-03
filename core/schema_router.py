"""
Registre centralise des schemas de donnees connus par le systeme, et detection
automatique du schema d'un fichier importe.

Pourquoi ce module existe : avant sa creation, chaque module (Reseau, Transactions)
verifiait sa propre compatibilite de schema independamment, avec sa logique dupliquee.
Ce n'est PAS un modele "universel" qui s'adapterait a n'importe quel format (un tel
systeme releve de la recherche avancee - transfert d'apprentissage, modeles de
fondation pour donnees tabulaires - hors de portee de ce projet). C'est un ROUTEUR :
il compare un fichier importe aux schemas EXPLICITEMENT enregistres ici (chacun
associe a son propre modele deja entraine), et identifie automatiquement le bon
domaine - ou signale clairement qu'aucun schema connu ne correspond, plutot que de
laisser un module tenter une analyse denuee de sens sur des donnees qu'il ne
comprend pas.

Ajouter un nouveau domaine (ex: IoT, une fois un modele dedie entraine) se fait en
ajoutant une seule entree ci-dessous - aucune duplication de logique de detection.
"""

SCHEMAS = {
    "reseau": {
        "label": "Securite Reseau",
        "description": "Flux reseau agreges (duree de connexion, volume de donnees, "
                        "taux de paquets, ports sollicites...)",
        "features": [
            "Duree_Connexion", "Octets_Source_Vers_Dest", "Octets_Dest_Vers_Source",
            "Taux_Paquets_Secondes", "Fenetre_TCP_Moyenne", "Ports_Dest_Distincts",
            "Connexions_Simultanees", "Taux_Erreur_CheckSum", "Frequence_SYN_Flags",
        ],
        "modele_disponible": True,
    },
    "transactions": {
        "label": "Fraude Transactionnelle",
        "description": "Transactions mobile money (montant, frequence, destinataire, "
                        "changement d'appareil...)",
        "features": [
            "Montant", "Ecart_Montant_Habituel", "Nouveau_Destinataire", "Heure_Transaction",
            "Frequence_Transactions_24h", "Delai_Depuis_Derniere_Min",
            "Nb_Destinataires_Distincts_7j", "Changement_Appareil",
        ],
        "modele_disponible": True,
    },
    # "iot": {
    #     "label": "Securite IIoT Industrielle",
    #     "description": "Flux IIoT (Datasense-IIoT-2025) - 41 variables retenues apres reduction
    #                      VIF (multicolinearite), cible multi-classe (~33 familles d'attaques :
    #                      recon/scan, usurpation ARP/IP, Mirai, injection, floods varies + benign).
    #                      Travail en cours - voir docs/ROADMAP_MODELES_ADDITIONNELS.md, section 0.
    #                      A activer une fois le pipeline d'entrainement complet (src/iot_security/)
    #                      et les artefacts (.joblib) disponibles.",
    #     "features": [...],  # les 41 variables post-VIF, a lister une fois l'export recu
    #     "modele_disponible": False,
    # },
}


def detect_schema(df_columns, seuil_minimal=0.5):
    """Compare les colonnes d'un fichier importe a chaque schema enregistre, et
    retourne le meilleur candidat.

    Retourne un dict :
    {
        "meilleur_schema": nom du schema le plus proche (ou None si aucun n'atteint le seuil),
        "taux_couverture": taux de correspondance du meilleur schema (0.0 a 1.0),
        "colonnes_manquantes": colonnes du meilleur schema absentes du fichier,
        "tous_les_scores": {nom_schema: taux_couverture} pour tous les schemas enregistres,
    }

    seuil_minimal : en-dessous de ce taux de couverture, meilleur_schema reste None
    (mieux vaut ne pas deviner que de proposer un schema tres peu probable).
    """
    df_columns_set = set(df_columns)
    scores = {}
    for nom_schema, config in SCHEMAS.items():
        features = config["features"]
        trouvees = [f for f in features if f in df_columns_set]
        scores[nom_schema] = len(trouvees) / len(features)

    meilleur_schema = max(scores, key=scores.get)
    if scores[meilleur_schema] < seuil_minimal:
        meilleur_schema = None

    colonnes_manquantes = []
    if meilleur_schema:
        colonnes_manquantes = [f for f in SCHEMAS[meilleur_schema]["features"] if f not in df_columns_set]

    return {
        "meilleur_schema": meilleur_schema,
        "taux_couverture": scores[meilleur_schema] if meilleur_schema else max(scores.values()),
        "colonnes_manquantes": colonnes_manquantes,
        "tous_les_scores": scores,
    }
