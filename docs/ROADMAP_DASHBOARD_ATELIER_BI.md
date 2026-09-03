# Dashboard web vers un atelier BI visuel - feuille de route progressive

## Point de depart (livre ce soir)

`web/dashboard.html` est deja un vrai outil de restitution BI (jauge, graphiques Chart.js
interactifs, filtres de date, commentaire IA) sur 3 domaines. On y ajoute ce soir un premier
element vers "l'atelier visuel" : un **logigramme du pipeline** (SVG anime, donnees reelles par
domaine) montrant comment chaque modele a ete construit (Donnees -> Pretraitement -> Comparaison
d'algorithmes -> Modele retenu -> Evaluation).

## Pourquoi une approche progressive, pas un atelier no-code complet d'un coup

Un vrai atelier no-code (glisser-deposer des blocs connectes, executer un pipeline visuellement)
est un projet d'ingenierie de plusieurs mois - bibliotheque de canvas interactif, moteur
d'execution de noeuds, persistance de workflows. Le construire d'un coup serait la meme survente
qu'on a evitee toute la soiree sur d'autres sujets (voir le refus explicite d'un "modele qui
s'adapte a n'importe quel jeu de donnees" plus tot dans le projet). La bonne approche : livrer des
etapes reelles et utilisables, dans l'ordre de la valeur/faisabilite.

## Etapes deja franchies

1. ✅ **Dashboard de restitution** (score, alertes, graphiques interactifs, 3 domaines)
2. ✅ **Logigramme du pipeline** (SVG, donnees reelles, par domaine) - livre ce soir
3. ✅ **Atelier de modelisation low-code** (Espace Academique, Streamlit) - menus deroulants pour
   choisir cible/algorithme/predicteurs, entrainement reel sur les donnees importees par
   l'utilisateur, jamais sur les modeles de production. Livre ce soir, mais **pas encore sur
   `dashboard.html`** - vit aujourd'hui uniquement dans Streamlit (voir etape 5 ci-dessous).

## Prochaines etapes envisageables (par ordre de complexite croissante)

### 4. Logigramme interactif (pas juste illustratif)
Rendre le logigramme deja livre cliquable : cliquer sur une etape ("Comparaison d'algorithmes")
affiche le detail (tableau comparatif complet, comme celui deja construit dans l'Espace
Academique) directement sur `dashboard.html`, sans changer de page.

### 5. Porter l'atelier de modelisation low-code sur le web
L'atelier construit ce soir vit dans Streamlit (Espace Academique). Le porter sur
`dashboard.html` demanderait un nouvel endpoint API (`POST /academique/entrainer_atelier`)
acceptant un fichier + des parametres (cible, algorithme, predicteurs), executant l'entrainement
cote serveur, et renvoyant les metriques - plus complexe qu'un simple appel de lecture, car il
s'agit d'une vraie charge de calcul a gerer (limite de taille de fichier, timeout, mise en file
d'attente si plusieurs utilisateurs simultanes).

### 6. Comparaison visuelle multi-configurations
Une fois l'etape 5 faite : permettre de lancer 2-3 configurations en parallele (ex. "Arbre de
Decision" vs "Foret Aleatoire" sur les memes donnees) et afficher les resultats cote a cote -
premiere brique d'un vrai outil de comparaison, sans encore etre un canvas de noeuds.

### 7. (Vision long terme, pas engagee) Canvas visuel de blocs connectes
La version complete evoquee initialement (glisser-deposer, connecter des blocs Donnees ->
Pretraitement -> Modele -> Evaluation visuellement) - necessiterait une bibliotheque dediee (ex.
React Flow), une refonte du frontend (`dashboard.html` est aujourd'hui du HTML/JS simple, pas un
framework avec gestion d'etat), et un moteur d'execution capable d'enchainer des etapes
configurees visuellement. A n'envisager que si les etapes 4-6 confirment une vraie demande/usage
pour cette complexite supplementaire.

## Principe de securite a respecter a chaque etape (rappel)

Toute execution initiee depuis un espace libre d'acces (Grand Public, Academique) doit rester
strictement isolee des modeles de production utilises par l'Espace Organisation - jamais
d'ecriture, jamais de remplacement automatique d'un modele reel. Voir aussi
`docs/ROADMAP_ATELIER_EXPERIMENTATION_ACADEMIQUE.md` pour le meme principe applique a un contexte
voisin (experimentation sur les pipelines internes plutot que sur des donnees importees par
l'utilisateur).
