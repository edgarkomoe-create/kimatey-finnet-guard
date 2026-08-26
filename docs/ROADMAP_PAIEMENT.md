# Integration paiement reel (Orange Money / MTN Mobile Money) - feuille de route

## Etat actuel

Le systeme de Pass (`core/pass_system.py`) gere deja toute la logique de
paliers, quotas et fonctionnalites debloquees - **mais aucun paiement reel
n'est encaisse**. Souscrire a un Pass aujourd'hui l'active immediatement,
gratuitement, en mode demonstration uniquement (champ `mode_demo: true`
explicite dans chaque enregistrement).

## Ce qu'il faut, concretement, pour un vrai encaissement

1. **Un compte marchand** chez un agregateur de paiement mobile money, par exemple :
   - CinetPay, PayDunya, ou Paystack (agregateurs multi-operateurs, couvrent
     Orange Money + MTN Mobile Money + Wave en Cote d'Ivoire via une seule
     integration)
   - Ou une integration directe API Orange Money / API MTN MoMo (plus lourd,
     un contrat par operateur)
2. **Un enregistrement entreprise (KYB)** aupres de l'agregateur - la plupart
   exigent un registre de commerce.
3. **Une politique de remboursement/litige** definie avant tout encaissement reel.

## Architecture prevue (des que le compte agregateur existe)

```
Utilisateur clique "Souscrire au Pass Famille"
        |
        v
Frontend redirige vers la page de paiement de l'agregateur (CinetPay etc.)
        |
        | webhook de confirmation apres paiement reussi
        v
Nouvel endpoint API : POST /pass/webhook_paiement
        |
        v
core.pass_system.souscrire(...) - appele SEULEMENT apres confirmation reelle
du paiement (jamais avant, contrairement au mode demo actuel qui active
immediatement sans verification)
```

## Ce qui change dans le code existant

- `core/pass_system.souscrire()` reste la meme fonction - elle n'a pas besoin
  d'etre reecrite, juste appelee au bon moment (apres webhook de paiement
  confirme, plutot que directement depuis le clic utilisateur).
- Le champ `mode_demo` dans chaque enregistrement passera a `false` pour les
  vraies souscriptions payees, permettant de distinguer les deux dans les
  journaux/rapports.
- Ajouter une table/fichier de suivi des transactions de paiement (montant,
  reference agregateur, statut) - separee du systeme de Pass lui-meme.

## Prevenez-moi des que vous avez un compte agregateur

L'ajout du webhook et du flux de paiement reel est un chantier contenu une
fois le compte disponible - la logique metier (quotas, fonctionnalites) est
deja prete et testee cote code.
