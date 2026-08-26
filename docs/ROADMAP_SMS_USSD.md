# Acces SMS / USSD - feuille de route (non implemente)

## Pourquoi ce n'est pas deja fait ce soir

Contrairement aux fonctionnalites web (chat, jeu, certificat), un acces SMS/USSD reel
necessite une **relation contractuelle avec un operateur ou un agregateur telecom**,
pas seulement du code. Impossible a fabriquer sans compte reel : ce document sert de
plan pret a executer des que ce compte existe.

## Ce qu'il faut, concretement

1. **Un compte chez un agregateur SMS/USSD**, par exemple :
   - Africa's Talking (couverture Afrique de l'Ouest, SMS + USSD + Voice, le plus utilise
     pour des projets comme celui-ci)
   - Orange Developer API / MTN Developer API (acces direct operateur, plus long a obtenir)
   - Twilio (SMS uniquement, pas de USSD, couverture Cote d'Ivoire a verifier)
2. **Un numero court ou un code USSD dedie** (ex. *123#), loue aupres de l'agregateur -
   generalement payant (frais d'installation + cout par message/session).
3. **Une verification d'identite entreprise** (KYB) - la plupart des agregateurs exigent
   un enregistrement de societe pour les codes USSD/numeros courts.

## Architecture prevue (des que le compte existe)

```
Utilisateur (telephone, meme sans smartphone)
        |
        | SMS ou session USSD
        v
Agregateur (ex. Africa's Talking) --webhook HTTP-->  Nouvel endpoint API
                                                       POST /channels/sms/inbound
                                                       POST /channels/ussd/session
                                                              |
                                                              v
                                                    Meme logique que /assistant/chat
                                                    (ASSISTANT_SYSTEM_PROMPT, ask_gemini)
                                                    mais reponse adaptee au format SMS
                                                    (rendu en texte pur, tres court,
                                                    pas de markdown/emoji lourd)
```

## Contraintes techniques a anticiper

- **Longueur des reponses** : un SMS fait 160 caracteres (ou se decoupe en plusieurs
  segments factures separement) - le prompt systeme de Lieutenant Cyber devra avoir une
  variante "reponse ultra-courte" pour ce canal, sans perdre l'essentiel.
- **Pas de vocal, pas d'image** : USSD/SMS = texte pur uniquement, donc l'analyse d'image
  (OCR/Gemini vision) et la reconnaissance vocale ne s'appliquent qu'au canal web.
- **Cout par message** : contrairement au web (gratuit une fois hebergee), chaque
  SMS envoye a un cout reel facture par l'agregateur - a integrer dans le futur modele
  economique/subventionne du produit.
- **Session USSD avec etat** : une session USSD est courte (quelques secondes, menu par
  menu) - il faudrait re-adapter le jeu de vigilance en menus numerotes simples
  (1. Vrai  2. Faux) plutot que la version web actuelle.

## Ce que je peux faire des que vous avez un compte agregateur

Cote code, l'ajout est en realite assez contenu une fois le compte disponible : un
nouvel endpoint API qui recoit le webhook entrant, reutilise `ask_gemini()` avec un
prompt adapte, et repond au format attendu par l'agregateur (XML pour la plupart des
USSD, JSON/POST simple pour SMS). Prevenez-moi des que vous avez les identifiants et
on le branche.
