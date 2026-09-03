# Espace Academique comme atelier d'experimentation - feuille de route

## Idee

Faire evoluer l'Espace Academique d'un espace purement pedagogique (explications, quiz,
Professeur Cyber, import de jeu de donnees generique decouple du modele Kimatey) vers un
**atelier d'experimentation** ou enseignants et etudiants pourraient tester des variantes
methodologiques sur les vrais pipelines du projet (strategies de gestion du desequilibre,
hyperparametres, selection de variables...) et obtenir de vraies metriques comparatives.

## Principe de securite non negociable

**L'Espace Academique est libre d'acces, sans compte requis.** Aucune experimentation menee
depuis cet espace ne doit jamais pouvoir modifier, remplacer, ou degrader un modele reellement
utilise en production par les organisations (Espace Organisation). Sans cette garantie, l'atelier
serait une faille d'integrite majeure - n'importe qui pourrait empoisonner ou degrader
volontairement (ou accidentellement) un modele servi a de vraies organisations.

## Architecture proposee (a construire quand on y reviendra)

```
Espace Academique (libre, sans compte)
        |
        v
[ Atelier d'experimentation ]
   - Opere sur une COPIE du pipeline d'entrainement, jamais le modele de production
   - Expose les parametres deja rendus "ajustables" dans le harnais de chaque pipeline
     (ex: STRATEGIE_DESEQUILIBRE dans src/iot_security/train_pipeline.py - deja construit
     pour permettre exactement ce type d'experimentation)
   - Genere de vraies metriques comparatives (F1 macro, matrice de confusion...) sur le
     jeu de donnees d'entrainement existant, pas sur des donnees inventees
        |
        v
   Resultat = un RAPPORT COMPARATIF affiche a l'utilisateur, jamais un deploiement automatique
        |
        v
[ Revue humaine (administrateur du projet) ]
   -> decision manuelle d'integrer ou non une amelioration constatee au vrai pipeline
      de production, via le processus normal (modification du code, tests, deploiement)
```

## Pourquoi c'est maintenant faisable techniquement (contrairement a avant)

Le concept de "harnais ajustable" introduit pour le pipeline IIoT
(`src/iot_security/train_pipeline.py`, parametre `STRATEGIE_DESEQUILIBRE`) est exactement le
mecanisme qui rendrait cet atelier possible : les parametres experimentables (strategie de
desequilibre, choix d'algorithme, hyperparametres) sont deja isoles dans le code plutot que
codes en dur, ce qui permet de les exposer a une interface utilisateur sans reecrire le pipeline
a chaque nouvelle experimentation.

## Ce qu'un premier prototype pourrait couvrir (scope minimal, a discuter le moment venu)

1. Selection d'un pipeline existant (Reseau, Transactions, ou IIoT une fois stable)
2. Selection d'une strategie parmi celles deja definies dans le harnais du pipeline choisi
3. Execution (potentiellement longue - a gerer avec une file d'attente ou une limite de taille
   d'echantillon pour rester utilisable dans une session web)
4. Affichage du rapport comparatif (metriques avant/apres, par rapport a la configuration
   actuellement en production)
5. Aucune action d'ecriture automatique - uniquement de la lecture/calcul en lecture seule sur
   une copie des donnees d'entrainement

## Statut

Idee documentee, non construite. A reprendre une fois le pipeline IIoT stabilise avec de
vraies donnees (voir la section IIoT de `docs/ROADMAP_MODELES_ADDITIONNELS.md`), pour eviter
de complexifier un pipeline encore en cours de validation.
