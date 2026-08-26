"""
Contenu partage entre l'application Streamlit (app/app.py, Espace Grand Public)
et l'API FastAPI (api/main.py, endpoints publics), pour eviter toute duplication
et garantir que les deux surfaces exposent exactement le meme assistant, le
meme mini-jeu de vigilance et le meme parcours de collecte participative.

Utilise le SDK "google-genai" (le SDK "google-generativeai" est deprecie par
Google - verifie explicitement dans cet environnement en 2026).
"""
import time

try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    genai_types = None
    GENAI_AVAILABLE = False


# ---------------------------------------------------------------- Assistant conversationnel
# Liste de modeles candidats, essayes dans l'ordre : les noms de modeles Gemini
# evoluent avec le temps, donc on ne bloque pas sur un seul nom. Le premier qui
# repond avec succes est mis en cache (voir parametre `cache` de ask_gemini) pour
# les appels suivants.
# Si tous echouent, verifiez la liste a jour sur https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL_CANDIDATES = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

ASSISTANT_SYSTEM_PROMPT = """Tu es Lieutenant Cyber, l'IA de Kimatey FinNet Guard, un systeme qui protege
l'infrastructure reseau des fintechs, agregateurs d'agents mobile money, institutions de microfinance et
administrations publiques en Afrique de l'Ouest, et qui aide aussi les particuliers a se proteger des arnaques
liees au mobile money. Tu es une creation originale de Kimatey Enterprise (pas un personnage emprunte a un
autre produit) : si on te demande qui tu es, presente-toi comme Lieutenant Cyber, l'IA de Kimatey FinNet Guard.

Regles a suivre strictement :
- Reponds toujours en francais simple et concret, sans jargon technique inutile (sauf si on te pose une
  question clairement technique, auquel cas tu peux etre plus precis).
- Si on te decrit une alerte de securite (scan de ports, attaque DDoS, infiltration/vol de donnees), explique
  ce que ca signifie concretement et propose une action recommandee claire.
- Si on te decrit un SMS, un appel ou un message recu (par exemple lie a un compte mobile money), aide a
  evaluer s'il presente des signes d'arnaque (fausse promotion, demande de code confidentiel, lien suspect,
  urgence artificielle, usurpation d'un operateur) et explique pourquoi simplement.
- Ne demande JAMAIS a l'utilisateur de te communiquer un code PIN, un mot de passe, un numero de carte ou tout
  identifiant sensible - rappelle au contraire qu'il ne faut jamais les partager, meme avec un assistant.
- Sois honnete sur tes limites : tu es un assistant conversationnel qui explique et sensibilise, pas un
  systeme de detection automatique en direct (cette partie est assuree par le modele de machine learning du
  tableau de bord).
- Reste bref (quelques phrases), concret et bienveillant."""


# ---------------------------------------------------------------- Assistance a l'analyse (Espace Organisation)
# Meme IA (Lieutenant Cyber), un second role : commenter en langage clair un resultat DEJA calcule par le
# modele de machine learning (jamais elle qui classifie). Grounding strict impose explicitement dans le
# system prompt : elle ne doit jamais inventer un signal ou une menace qui ne lui a pas ete fournie - un
# risque d'hallucination serait plus grave ici que pour un simple chat de sensibilisation, puisque ce role
# s'adresse a des equipes qui prennent des decisions de securite sur la base de cette explication.
ORG_ANALYST_SYSTEM_PROMPT = """Tu es Lieutenant Cyber, la meme IA de Kimatey FinNet Guard que celle qui
dialogue avec le grand public, mais ici dans un second role : aider les equipes IT/securite de l'Espace
Organisation a lire les resultats du tableau de bord.

Contexte impose a chaque appel : on te fournit un resultat DEJA calcule par le modele de machine learning
de Kimatey FinNet Guard (une classe predite, un niveau de confiance, et selon le cas les probabilites par
categorie et/ou les valeurs des variables techniques du flux, ou un resume d'une analyse par lot). Ce n'est
JAMAIS toi qui classifies le trafic - cette tache appartient exclusivement au modele entraine.

Regles strictes :
- Explique le resultat fourni en francais clair, pour une equipe technique mais sans jargon superflu.
- Termine par une recommandation d'action concrete et proportionnee (surveiller, investiguer plus en detail,
  bloquer/isoler, ou confirmer qu'aucune action n'est necessaire si le trafic est classe normal).
- Ne mentionne JAMAIS un signal, une menace, une donnee ou un evenement qui ne t'a pas ete fourni
  explicitement dans le contexte de cet appel - si une information manque pour recommander une action
  precise, dis-le plutot que de deviner ou d'inventer.
- Reste bref (3 a 5 phrases), concret et actionnable."""


ORG_EXECUTIVE_SYSTEM_PROMPT = """Tu es Lieutenant Cyber, la meme IA de Kimatey FinNet Guard, ici dans un
troisieme role : donner un avis a un decideur ou manager NON TECHNIQUE (pas une equipe IT/securite),
a partir d'un resultat DEJA calcule par le systeme (jamais toi qui classifies).

Regles strictes, plus exigeantes que pour une equipe technique :
- INTERDICTION ABSOLUE de jargon technique : jamais les mots "modele", "flux", "classe", "algorithme",
  "IA", "machine learning", "score", "pourcentage technique", ni aucun nom de categorie technique
  (ex. jamais "Infiltration/Brute-Force/Exfiltration" - dis plutot "une tentative d'intrusion grave").
- Parle comme a un dirigeant d'entreprise qui n'a aucune formation informatique : langage des affaires,
  consequences concretes ("risque pour vos operations", "action a prendre"), jamais de detail technique.
- Maximum 3 phrases courtes. Une premiere phrase sur la situation globale, une deuxieme sur ce que ca
  signifie concretement, une troisieme sur l'action recommandee (ou la confirmation que tout va bien).
- Ne mentionne jamais une information qui ne t'a pas ete fournie explicitement dans cet appel."""


ACADEMIC_INSTRUCTOR_SYSTEM_PROMPT = """Tu es "Professeur Cyber", une variante pedagogique de l'IA de
Kimatey FinNet Guard, dediee au dashboard academique. Ton public : des etudiants qui etudient pour un
devoir/examen, ou des enseignants qui preparent un cours, sur le machine learning applique a la
cybersecurite reseau (ce projet precis sert d'etude de cas).

Contexte pedagogique du projet (a utiliser comme reference si pertinent) :
- Probleme : classification multi-classe (4 classes : Normal, Scan de Ports, Attaque DDoS, Infiltration)
  sur des flux reseau, a partir de 9 variables numeriques.
- Pipeline : EDA -> pretraitement (IQR, standardisation apprise sur le train uniquement) -> comparaison de
  5 algorithmes (Regression Logistique, KNN, Naive Bayes, SVM, Arbre de Decision) -> selection de variables
  (RFE, 9 -> 5) -> optimisation d'hyperparametres (GridSearchCV, validation croisee 5 plis).
- Modele retenu : Arbre de Decision elague, 99,04% d'exactitude, 98,72% F1-score macro, 99,92% AUC macro.
- Deséquilibre des classes : ~75% trafic normal, ~25% reparti sur les 3 classes de menace.

Regles :
- Explique les concepts (ML, statistiques, methodologie, cybersecurite) de facon pedagogique et precise,
  avec des exemples concrets tires de CE projet quand c'est pertinent, sans jamais inventer un chiffre
  ou un resultat qui ne t'a pas ete donne.
- Adapte le niveau : si la question est basique, explique simplement d'abord puis approfondis si demande.
  Si la question est pointue (ex: "pourquoi macro-average plutot que weighted"), reponds au niveau attendu.
- Toujours pedagogique, jamais condescendant. Style d'un bon enseignant, pas d'un manuel aride.
- Si on te demande de generer une question de quiz ou un exercice, tu peux le faire - mais precise
  toujours la reponse correcte et pourquoi les autres options sont fausses.
- Reste concis par defaut (une reponse de cours, pas un chapitre entier) sauf si on te demande explicitement
  d'approfondir."""


def ask_gemini(client, contents, system_instruction=ASSISTANT_SYSTEM_PROMPT, cache=None):
    """Envoie une question (texte ou audio) a Gemini via le client, en essayant
    plusieurs noms de modele si besoin. Renvoie toujours du texte, y compris un
    message d'erreur lisible en cas d'echec, plutot que de lever une exception
    qui casserait la page/l'appel API. Le system_instruction est parametrable
    pour reutiliser cette fonction avec un autre role (ex : anonymisation d'un
    temoignage). `cache` est un objet dict-like (st.session_state cote
    Streamlit, un simple dict cote API) utilise pour retenir le premier modele
    qui a fonctionne, afin d'eviter de retester tous les candidats a chaque
    appel."""
    cache = {} if cache is None else cache
    cached = cache.get("gemini_model_name")
    candidates = [cached] + [c for c in GEMINI_MODEL_CANDIDATES if c != cached] if cached else GEMINI_MODEL_CANDIDATES
    config = genai_types.GenerateContentConfig(system_instruction=system_instruction)
    last_err = None
    for name in candidates:
        try:
            response = client.models.generate_content(model=name, contents=contents, config=config)
            cache["gemini_model_name"] = name
            return response.text
        except Exception as e:
            last_err = e
            continue
    return ("Je n'arrive pas a contacter l'assistant pour le moment "
            f"(verifiez votre cle API et votre connexion). Detail technique : {last_err}")


# ---------------------------------------------------------------- Sensibilisation ludique + collecte participative
ANONYMIZE_SYSTEM_PROMPT = """Tu transformes le temoignage d'une personne ayant vecu ou observe une tentative
d'arnaque (mobile money ou autre) en une fiche technique courte et totalement depersonnalisee, utile pour
reperer de nouvelles techniques de fraude.

Regles strictes, a respecter meme si le texte d'origine contient ces informations :
- Ne jamais inclure de nom, numero de telephone, numero de compte, montant precis, localisation precise,
  ou tout autre element qui permettrait d'identifier la personne. Si le texte en contient, ignore-les.
- Decris uniquement la mecanique de l'arnaque : canal utilise (SMS, appel, WhatsApp, en personne...),
  pretexte invoque, ce qui etait demande, et le signal d'alerte a retenir pour la reconnaitre a l'avenir.
- Reponds en 2 a 3 phrases maximum, en francais simple.
- Ne t'adresse jamais a la personne directement (pas de "vous") : ecris a la troisieme personne, comme une
  fiche de synthese anonyme (ex : "Un message pretendant venir de l'operateur demande de composer un code
  pour 'debloquer' un compte - signal d'alerte : aucun operateur ne demande jamais ce code.")."""

SCENARIOS = [
    {
        "situation": "Vous recevez un SMS : « Felicitations ! Vous avez gagne 500 000 FCFA. "
                     "Composez #144*1# pour reclamer votre gain avant minuit. »",
        "choices": ["Je compose le code tout de suite, avant de perdre le gain", "Je verifie autrement, ou j'ignore le message"],
        "correct": 1,
        "explanation": "Aucune promotion legitime ne cree une urgence artificielle (« avant minuit ») "
                       "ni ne demande de composer un code USSD inconnu. C'est une technique classique pour "
                       "vous faire agir sans reflechir.",
        "tip": "Astuce : aucune promotion legitime ne demande de composer un code USSD pour « debloquer » "
               "un gain. En cas de doute, contactez le service client via le numero officiel de votre operateur.",
    },
    {
        "situation": "Un appel : « Bonjour, je suis agent de votre operateur mobile money. Votre compte "
                     "va etre bloque, donnez-moi votre code secret pour le confirmer. »",
        "choices": ["Je donne le code pour eviter le blocage", "Je raccroche et j'appelle le numero officiel "
                    "du service client moi-meme"],
        "correct": 1,
        "explanation": "Un operateur ne demande JAMAIS votre code secret par telephone. C'est toujours "
                       "vous qui devez rappeler un numero officiel connu, jamais repondre a l'appel entrant.",
        "tip": "Astuce : votre code secret mobile money ne doit jamais quitter votre tete - ni par "
               "telephone, ni par SMS, ni en personne, meme face a quelqu'un qui se dit « agent officiel ».",
    },
    {
        "situation": "Sur WhatsApp, un « ami » vous ecrit d'un nouveau numero : « Je suis bloque, "
                     "envoie-moi vite 10 000 FCFA par mobile money, je te rembourse demain. »",
        "choices": ["J'envoie l'argent tout de suite, c'est urgent", "Je verifie en appelant mon ami sur son "
                    "ancien numero avant tout"],
        "correct": 1,
        "explanation": "Le detournement de compte WhatsApp (ou l'usurpation via un nouveau numero) est tres "
                       "frequent. Toujours verifier par un autre canal avant d'envoyer de l'argent a un "
                       "contact qui semble urgent et inhabituel.",
        "tip": "Astuce : en cas de demande d'argent urgente et inhabituelle, appelez toujours la personne "
               "sur son numero connu avant d'envoyer quoi que ce soit.",
    },
]

REPORT_STEPS = [
    {"key": "canal", "question": "👋 Pour commencer : ça s'est passé comment ? Par quel canal ?",
     "options": ["📱 Un SMS", "☎️ Un appel", "💬 WhatsApp", "🧑 En personne", "🔀 Autre chose"]},
    {"key": "demande", "question": "D'accord, merci. Et qu'est-ce qu'on vous demandait exactement ?",
     "options": ["🔑 Un code confidentiel", "💰 De l'argent", "🔗 De cliquer sur un lien",
                 "🪪 Des infos personnelles", "🔀 Autre chose"]},
    {"key": "reaction", "question": "Je vois. Et vous, sur le moment, qu'avez-vous fait ?",
     "options": ["😬 J'ai suivi la demande", "🚫 J'ai ignoré / raccroché", "🔍 J'ai vérifié autrement avant d'agir"]},
]


# ---------------------------------------------------------------- Sensibilisation ludique (mecanique de
# gamification : niveaux, points de progression, vies, mascottes, categories thematiques, badges). Adapte
# au domaine fraude/mobile money, avec une difference assumee et volontaire : ici, la "monnaie" du jeu
# (Points Bouclier) n'a AUCUNE conversion en argent ni en recompense reelle - dans une application qui lutte
# contre la fraude financiere, imiter une monnaie qui se convertit en
# valeur reelle aurait envoye le mauvais signal. C'est un indicateur de progression et de vigilance, point.
XP_PER_CORRECT = 15
XP_PER_INCORRECT = 5
MAX_HEARTS = 3

# Paliers de niveau (seuil de Points Bouclier cumules -> titre). Le dernier palier atteint definit le niveau
# courant ; compute_level() renvoie aussi le seuil du niveau suivant pour afficher une barre de progression.
LEVELS = [
    {"xp_threshold": 0, "title": "🌱 Recrue Vigilante"},
    {"xp_threshold": 50, "title": "🔍 Vigie Mobile Money"},
    {"xp_threshold": 120, "title": "🛡️ Gardien Cyber"},
    {"xp_threshold": 220, "title": "🏅 Gardien d'Elite"},
    {"xp_threshold": 350, "title": "👑 Legende de la Vigilance"},
]

BADGES = [
    {"key": "premier_bouclier", "emoji": "🛡️", "label": "Premier Bouclier",
     "xp_required": 15, "desc": "Premiere reponse validee dans le jeu de vigilance."},
    {"key": "as_mobile_money", "emoji": "📱", "label": "As du Mobile Money",
     "xp_required": 60, "desc": "Bonne progression sur les pieges lies au mobile money."},
    {"key": "gardien_multi", "emoji": "🧭", "label": "Gardien Multi-Categories",
     "xp_required": 150, "desc": "Progression solide sur plusieurs types d'arnaques differents."},
    {"key": "legende_cyber", "emoji": "👑", "label": "Legende Cyber",
     "xp_required": 350, "desc": "Niveau maximal atteint - un vrai reflexe de vigilance !"},
]


def compute_level(xp):
    """Renvoie le niveau courant pour un total de Points Bouclier donne :
    {"title": str, "xp_threshold": int, "next_threshold": int|None, "progress_ratio": float}.
    progress_ratio est la fraction (0-1) parcourue vers le niveau suivant (1.0 si niveau max atteint)."""
    current = LEVELS[0]
    next_level = None
    for i, lvl in enumerate(LEVELS):
        if xp >= lvl["xp_threshold"]:
            current = lvl
            next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
        else:
            break
    if next_level is None:
        ratio = 1.0
    else:
        span = next_level["xp_threshold"] - current["xp_threshold"]
        ratio = min(1.0, (xp - current["xp_threshold"]) / span) if span > 0 else 1.0
    return {
        "title": current["title"],
        "xp_threshold": current["xp_threshold"],
        "next_threshold": next_level["xp_threshold"] if next_level else None,
        "progress_ratio": ratio,
    }


def compute_unlocked_badges(xp):
    """Renvoie la liste des badges (parmi BADGES) debloques pour ce total de Points Bouclier."""
    return [b for b in BADGES if xp >= b["xp_required"]]


# Mascotte : Lieutenant Cyber est l'IA propre a Kimatey FinNet Guard - une creation originale, pas un
# personnage emprunte a un autre produit du portefeuille. Meme IA que l'assistant conversationnel
# (ASSISTANT_SYSTEM_PROMPT) : une seule identite qui traverse le jeu de vigilance, le chat Grand Public,
# et l'assistance a l'analyse cote Espace Organisation (voir ORG_ANALYST_SYSTEM_PROMPT plus haut) - c'est
# ce qui rend "l'analyse des donnees, le rendu des tableaux de bord et l'assistance des deux types
# d'utilisateurs plus fluides et simples" (objectif explicite de l'utilisateur), plutot que d'avoir un
# chatbot texte, une mascotte de quiz et un assistant technique qui seraient 3 entites disjointes.
# Seule la ligne d'accueil (mascot_line) change selon la categorie, pour rester rattachee au theme.
GAME_MASCOTS = {
    "lieutenant_cyber": {
        "name": "Lieutenant Cyber",
        "intro": "🎖️ Lieutenant Cyber au rapport ! Je suis l'IA de Kimatey FinNet Guard, ici pour "
                 "t'aider a reperer les pieges avant qu'ils ne te coutent cher.",
    },
}

GAME_CATEGORIES = [
    {
        "key": "mobile_money",
        "label": "Mobile Money",
        "emoji": "📱",
        "mascot_key": "lieutenant_cyber",
        "mascot_line": "🎖️ Lieutenant Cyber au rapport ! Aujourd'hui, on inspecte les pieges du mobile "
                       "money - pret(e) a tester tes reflexes ?",
        "lecon": [
            {"icone": "📵", "texte": "Personne d'officiel ne vous demande votre code secret."},
            {"icone": "⏳", "texte": "L'urgence est une arme des arnaqueurs. Prenez toujours le temps de verifier."},
            {"icone": "📞", "texte": "Un doute ? Rappelez vous-meme le numero officiel, jamais celui recu par SMS."},
            {"icone": "🚫💸", "texte": "Jamais d'argent envoye a un inconnu, meme s'il dit etre urgent ou important."},
        ],
        "scenarios": SCENARIOS,
    },
    {
        "key": "banque",
        "label": "Banque & Epargne",
        "emoji": "🏦",
        "mascot_key": "lieutenant_cyber",
        "mascot_line": "🎖️ Lieutenant Cyber : les arnaques bancaires sont parmi les plus sophistiquees. "
                       "Restons vigilants ensemble.",
        "lecon": [
            {"icone": "🏦❌", "texte": "Votre banque ne bloque jamais un compte par simple SMS avec un lien."},
            {"icone": "🔗🚫", "texte": "Ne cliquez jamais sur un lien recu par SMS ou email pour votre banque."},
            {"icone": "🎁⚠️", "texte": "Un pret trop facile, trop rapide, sans garantie : c'est suspect."},
            {"icone": "✍️", "texte": "Verifiez toujours en tapant vous-meme l'adresse officielle de votre banque."},
        ],
        "scenarios": [
            {
                "situation": "Vous recevez un SMS : « Votre compte bancaire sera suspendu dans 24h. "
                             "Cliquez ici pour le reactiver : bit.ly/verif-compte »",
                "choices": ["Je clique tout de suite pour eviter la suspension",
                            "Je me connecte moi-meme via l'application officielle, sans cliquer sur le lien"],
                "correct": 1,
                "explanation": "Une banque ne suspend jamais un compte par simple SMS avec un lien a "
                               "cliquer. C'est une technique de phishing pour voler vos identifiants.",
                "tip": "Astuce : tapez toujours l'adresse de votre banque vous-meme, ou utilisez son "
                       "application officielle - jamais un lien recu par SMS ou email.",
            },
            {
                "situation": "Une offre : « Obtenez 200 000 FCFA de pret en 10 minutes, sans garantie. "
                             "Envoyez juste 5 000 FCFA de frais de dossier par mobile money. »",
                "choices": ["J'envoie les frais pour debloquer le pret",
                            "Je refuse : un vrai pret ne demande jamais de frais avant deblocage"],
                "correct": 1,
                "explanation": "Aucun etablissement de credit legitime ne demande de payer des frais a "
                               "l'avance pour « debloquer » un pret. C'est une arnaque tres repandue.",
                "tip": "Astuce : mefiez-vous de toute offre de credit qui demande un paiement prealable - "
                       "verifiez toujours aupres d'un etablissement agree.",
            },
        ],
    },
    {
        "key": "ingenierie_sociale",
        "label": "Ingenierie Sociale",
        "emoji": "📞",
        "mascot_key": "lieutenant_cyber",
        "mascot_line": "🎖️ Lieutenant Cyber : ici, ce n'est pas votre ecran qui est attaque, c'est votre "
                       "confiance. Apprenons a la proteger.",
        "lecon": [
            {"icone": "🎭", "texte": "L'arnaqueur se fait passer pour quelqu'un de confiance (technicien, employeur, ami)."},
            {"icone": "📲🚫", "texte": "N'installez jamais une application demandee par un appel non sollicite."},
            {"icone": "👨‍👩‍👧", "texte": "Un doute sur un proche ? Rappelez-le directement, sur son vrai numero."},
            {"icone": "🛑", "texte": "Raccrocher n'est jamais impoli face a une demande suspecte."},
        ],
        "scenarios": [
            {
                "situation": "Un appel : « Bonjour, support technique de votre operateur, votre telephone "
                             "est infecte. Installez cette application pour que je le repare a distance. »",
                "choices": ["J'installe l'application pour resoudre le probleme",
                            "Je raccroche : un support technique legitime ne prend jamais le controle de "
                            "mon telephone a l'improviste"],
                "correct": 1,
                "explanation": "Cette technique (« support technique frauduleux ») vise a obtenir un acces "
                               "complet a votre appareil, y compris vos applications mobile money.",
                "tip": "Astuce : aucun support technique legitime ne vous appelle jamais en premier pour "
                       "demander une prise de controle a distance.",
            },
            {
                "situation": "Votre « patron » vous ecrit sur WhatsApp d'un numero inconnu : « Urgent, "
                             "achete-moi 3 recharges mobile money de 20 000 FCFA, je te rembourse demain, "
                             "je suis en reunion je ne peux pas parler. »",
                "choices": ["J'achete les recharges tout de suite pour rendre service",
                            "Je verifie aupres de mon patron par un autre canal avant tout achat"],
                "correct": 1,
                "explanation": "C'est une fraude classique dite « fraude au president/CEO » : creer une "
                               "pression hierarchique et une urgence pour empecher toute verification.",
                "tip": "Astuce : une vraie urgence professionnelle laisse toujours le temps d'un appel de "
                       "verification - mefiez-vous de qui vous l'interdit explicitement.",
            },
        ],
    },
    {
        "key": "reseaux_sociaux",
        "label": "Reseaux Sociaux",
        "emoji": "💬",
        "mascot_key": "lieutenant_cyber",
        "mascot_line": "🎖️ Lieutenant Cyber : en ligne, tout le monde n'est pas qui il pretend etre. "
                       "Gardons un oeil vigilant.",
        "lecon": [
            {"icone": "👤❓", "texte": "Un profil peut etre faux, meme avec une jolie photo."},
            {"icone": "💰➡️🚫", "texte": "N'envoyez jamais d'argent avant de recevoir un article achete en ligne."},
            {"icone": "🏆❌", "texte": "Vous n'avez pas gagne un concours auquel vous n'avez jamais participe."},
            {"icone": "🔒", "texte": "Vos codes et mots de passe ne se partagent avec personne, jamais."},
        ],
        "scenarios": [
            {
                "situation": "Sur une page de vente en ligne, un acheteur insiste : « Envoie-moi d'abord "
                             "les frais de livraison par mobile money, ensuite je te paie l'article. »",
                "choices": ["J'envoie les frais pour conclure la vente rapidement",
                            "Je refuse tout paiement avant d'avoir recu le paiement complet de l'article"],
                "correct": 1,
                "explanation": "Demander a un vendeur de payer des frais en amont est un signal d'arnaque "
                               "classique sur les plateformes de vente entre particuliers.",
                "tip": "Astuce : dans une vente entre particuliers, c'est toujours l'acheteur qui paie en "
                       "premier ou lors d'une remise en main propre - jamais le vendeur qui avance des frais.",
            },
            {
                "situation": "Une personne rencontree en ligne, jamais vue en vrai, vous ecrit : « Je "
                             "t'aime, mais j'ai un souci medical urgent, peux-tu m'envoyer de l'argent par "
                             "mobile money ? »",
                "choices": ["J'envoie de l'argent, la relation compte plus que tout",
                            "Je refuse et reste mefiant(e) face a une demande d'argent d'une personne "
                            "jamais rencontree en personne"],
                "correct": 1,
                "explanation": "L'arnaque sentimentale (« romance scam ») exploite la confiance construite "
                               "en ligne pour obtenir des transferts d'argent repetes.",
                "tip": "Astuce : une relation en ligne qui demande de l'argent, surtout sans jamais s'etre "
                       "rencontres en personne, est un signal d'alerte fort.",
            },
        ],
    },
    {
        "key": "aines",
        "label": "Protection des Aines",
        "emoji": "🧓",
        "mascot_key": "lieutenant_cyber",
        "mascot_line": "🎖️ Lieutenant Cyber : les fraudeurs ciblent souvent nos aines. Protegeons-les "
                       "ensemble, un reflexe a la fois.",
        "lecon": [
            {"icone": "👨‍👩‍👧‍👦", "texte": "Un vrai proche en difficulte accepte toujours d'etre rappele avant l'envoi d'argent."},
            {"icone": "🚔❌", "texte": "La police ne demande jamais d'argent par telephone."},
            {"icone": "🤝", "texte": "Parlez-en a une personne de confiance avant toute decision urgente."},
            {"icone": "🙅", "texte": "Il est toujours correct de dire non et de raccrocher."},
        ],
        "scenarios": [
            {
                "situation": "Un appel : « Grand-pere/Grand-mere, c'est moi, j'ai eu un accident, envoie "
                             "vite de l'argent par mobile money, ne dis rien a la famille ! »",
                "choices": ["J'envoie l'argent tout de suite, c'est mon petit-fils/ma petite-fille",
                            "Je raccroche et j'appelle directement le petit-fils/la petite-fille ou un "
                            "membre de la famille pour verifier"],
                "correct": 1,
                "explanation": "L'arnaque « faux proche en detresse » cible particulierement les personnes "
                               "agees et joue sur la panique et le secret imposé pour empecher toute "
                               "verification.",
                "tip": "Astuce : demander de garder le secret vis-a-vis de la famille est presque toujours "
                       "un signal d'arnaque - verifiez toujours par un autre moyen.",
            },
            {
                "situation": "Un SMS : « Votre pension/allocation sociale est disponible. Confirmez le code "
                             "recu par SMS pour la recevoir immediatement. »",
                "choices": ["Je communique le code recu pour recevoir le paiement",
                            "Je ne communique jamais un code recu par SMS et je contacte l'organisme "
                            "officiellement"],
                "correct": 1,
                "explanation": "Un code recu par SMS sert a authentifier VOTRE compte - le transmettre "
                               "revient a en donner l'acces a quelqu'un d'autre, quel que soit le pretexte.",
                "tip": "Astuce : aucun organisme legitime ne vous demande jamais de lui transmettre un code "
                       "recu par SMS.",
            },
        ],
    },
    {
        "key": "cyber",
        "label": "Cyber & Mots de Passe",
        "emoji": "🔐",
        "mascot_key": "lieutenant_cyber",
        "mascot_line": "🎖️ Lieutenant Cyber, en mission sur le front numerique : mots de passe, codes "
                       "et cartes SIM n'auront plus de secret pour vous.",
        "lecon": [
            {"icone": "🔢🚫", "texte": "Votre code PIN ou mot de passe ne se donne jamais, meme a un agent."},
            {"icone": "📱⚠️", "texte": "Perte soudaine de reseau ? Verifiez immediatement, ca peut etre un vol de SIM."},
            {"icone": "🔑🔑", "texte": "Un mot de passe different pour chaque compte important protege mieux."},
            {"icone": "📩👀", "texte": "Un code recu par SMS que vous n'avez pas demande : ne le partagez jamais."},
        ],
        "scenarios": [
            {
                "situation": "Un email « officiel » vous demande : « Confirmez votre mot de passe mobile "
                             "money en cliquant sur ce lien pour eviter la fermeture de votre compte. »",
                "choices": ["Je clique et je saisis mon mot de passe pour confirmer",
                            "Je n'utilise jamais un lien recu par email pour saisir un mot de passe"],
                "correct": 1,
                "explanation": "Un mot de passe ou un code ne se « confirme » jamais via un lien recu par "
                               "email ou SMS : c'est la technique de phishing la plus courante.",
                "tip": "Astuce : utilisez un mot de passe different pour chaque service important, et "
                       "activez la verification en deux etapes si elle est proposee.",
            },
            {
                "situation": "Un appel : « Ici votre operateur telephonique, pour migrer votre carte SIM "
                             "nous avons besoin du code que vous venez de recevoir par SMS. »",
                "choices": ["Je communique le code recu pour que la migration se fasse",
                            "Je refuse : je ne communique jamais un code recu par SMS, meme a un "
                            "'operateur'"],
                "correct": 1,
                "explanation": "C'est une tentative de « SIM swap » : en obtenant ce code, un fraudeur peut "
                               "prendre le controle de votre numero et donc de vos comptes lies (mobile "
                               "money inclus).",
                "tip": "Astuce : un vrai operateur ne vous appelle jamais pour vous demander un code que "
                       "vous venez de recevoir par SMS.",
            },
        ],
    },
]
