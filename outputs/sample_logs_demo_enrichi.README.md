# sample_logs_demo_enrichi.csv - donnees SYNTHETIQUES

Ce fichier n'est PAS un export reel de logs reseau. Les 9 colonnes techniques
(Duree_Connexion, Octets_..., etc.) sont les vraies valeurs de `sample_logs_demo.csv`
(deja utilise pour les predictions du modele). Les colonnes ajoutees -
**Horodatage, Pays, Departement, Appareil** - sont entierement **generees
artificiellement** (script rapide, seed=7) uniquement pour demontrer le rendu
des vues adaptatives du dashboard (chronologie des menaces, repartition
geographique, filtres departement/appareil) tant qu'aucune vraie institution
n'a encore fourni de fichier avec ces colonnes.

A ne jamais presenter comme des donnees de production reelles.
