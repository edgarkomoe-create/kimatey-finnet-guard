/* Systeme de traduction partage FR/EN - Kimatey FinNet Guard (page d'accueil + Espace Grand Public).
   Usage : <span data-i18n="key">texte par defaut (fr)</span> ; placeholders via data-i18n-placeholder.
   La preference de langue est memorisee dans localStorage et partagee entre les deux pages. */

const I18N = {
  fr: {
    // ---- Nav / commun ----
    nav_cta: "Entrer dans la plateforme",
    live_pill: "Surveillance active",
    back_link: "← Retour à l'accueil",

    // ---- Hero (index.html) ----
    eyebrow: "Sécurité réseau & protection citoyenne · Afrique",
    hero_h1_1: "Une seule intelligence artificielle.",
    hero_h1_2: "Deux lignes de défense.",
    hero_sub: "D'un côté, un moteur de machine learning qui détecte les attaques réseau visant les fintechs et les opérateurs mobile money. De l'autre, un assistant conversationnel qui aide chaque citoyen à démasquer une arnaque avant d'y perdre son argent. Même base technique, deux publics protégés.",
    hero_cta1: "Découvrir la plateforme →",
    hero_cta2: "Comment ça marche",
    lane_org: "Organisation",
    lane_public: "Grand public",

    // ---- Probleme ----
    problem_eyebrow: "Le problème",
    problem_h2: "La finance mobile a changé l'Afrique. La fraude a suivi la même courbe.",
    problem1_fig: "75/25",
    problem1_txt: "Sur le trafic réseau analysé, un flux sur quatre porte déjà une signature d'attaque potentielle contre l'infrastructure financière.",
    problem2_fig: "SMS",
    problem2_txt: "Le canal le plus utilisé pour arnaquer un utilisateur mobile money reste le message qui imite une banque ou un opérateur.",
    problem3_fig: "2",
    problem3_txt: "cibles distinctes à protéger en même temps : l'infrastructure des institutions, et le jugement de chaque utilisateur au moment où il reçoit un message.",

    // ---- Comment ca marche ----
    how_eyebrow: "Comment ça marche",
    how_h2: "Deux intelligences artificielles, une seule base technique.",
    how1_tag: "Machine learning supervisé",
    how1_h3: "Le moteur de détection",
    how1_p: "Un arbre de décision optimisé, entraîné et validé sur 50 000 flux réseau, reconnaît une attaque à partir de 5 variables clé : volume de données, taux de paquets, ports sollicités, erreurs de checksum, fréquence des signaux de connexion.",
    how1_s1: "99,04 % d'exactitude en test",
    how1_s2: "99,92 % d'AUC macro",
    how1_s3: "Validé en conditions de type SOC",
    how2_tag: "IA générative",
    how2_h3: "Lieutenant Cyber",
    how2_p: "Un assistant conversationnel (propulsé par Google Gemini) auquel un citoyen décrit un SMS ou un appel suspect, en langage naturel ou à l'oral. Il explique le risque simplement, sans jargon, et sans jamais collecter de donnée personnelle.",
    how2_s1: "Disponible côté Organisation et Grand Public",
    how2_s2: "Complété par un jeu de vigilance gamifié",
    how2_s3: "Zéro collecte de données personnelles",

    // ---- Espaces ----
    spaces_eyebrow: "La plateforme",
    spaces_h2: "Choisissez votre espace",
    card_org_h3: "🏢 Espace Organisation",
    card_org_p: "Tableau de bord technique : détection en temps réel, analyse de logs, surveillance en direct, journal d'alertes. Pour les équipes IT/sécurité des fintechs, opérateurs mobile money, institutions financières et administrations.",
    card_org_cta: "Entrer dans l'Espace Organisation →",
    card_public_h3: "👥 Espace Grand Public",
    card_public_p: "Discutez avec Lieutenant Cyber, testez vos réflexes face aux arnaques mobile money, et aidez à en repérer de nouvelles - sans jamais partager d'information personnelle.",
    card_public_cta: "Entrer dans l'Espace Grand Public →",

    // ---- Preuve ----
    proof_eyebrow: "Base technique validée",
    proof1_label: "flux réseau analysés",
    proof2_label: "algorithmes comparés avant sélection",
    proof3_label: "tests automatisés",
    proof4_label: "variables retenues sur le modèle final",
    proof_note: "Prototype technique validé, pas encore déployé auprès d'utilisateurs ou de partenaires réels.",
    footer_note_index: "Kimatey FinNet Guard - Réalisé par Komoe Edgar Junior - Projet ML Master 1 UFRMI - Responsable de l'enseignement : Dr ASSOHOUN E Stanislas. L'Espace Organisation reste servi par l'application Streamlit existante (deep-link direct) ; l'Espace Grand Public est une page web indépendante consommant directement l'API (voir config.js).",

    // ---- public.html : header ----
    header_desc: "Sécurise l'infrastructure réseau des fintechs, agrégateurs mobile money, institutions de microfinance et administrations publiques - et sensibilise directement les citoyens contre les arnaques mobile money.",
    tab_assistant: "🎖️ Lieutenant Cyber",
    tab_sensibilisation: "🎮 Sensibilisation",

    // ---- Onglet Assistant ----
    assistant_h2: "🎖️ Lieutenant Cyber - l'IA de Kimatey FinNet Guard",
    assistant_hint: "Posez une question en langage courant sur une alerte, une menace, ou un message suspect reçu par mobile money. Cet assistant explique et sensibilise ; il ne remplace pas la détection automatique du tableau de bord de l'Espace Organisation.",
    chat_placeholder: "Écrivez votre question ici...",
    chat_send: "Envoyer",
    mic_btn: "🎤",
    mic_unsupported: "La reconnaissance vocale n'est pas prise en charge par ce navigateur. Essayez Chrome ou Edge, ou écrivez votre question.",
    image_btn: "📷",
    image_too_large: "Image trop volumineuse (8 Mo maximum).",
    image_sent_label: "📷 [Capture d'écran envoyée]",
    chat_voice_hint: "🔊 Les réponses de l'assistant sont lues à voix haute automatiquement (synthèse vocale du navigateur).",
    chat_welcome: "👋 Bonjour ! Posez-moi une question sur une alerte ou un message suspect que vous avez reçu.",
    chat_unavailable: "L'assistant n'est pas disponible pour le moment.",
    chat_server_error: "Impossible de contacter le serveur. Vérifiez que l'API est bien lancée (",

    // ---- Onglet Sensibilisation ----
    sensib_h2: "🎮 Sensibilisation ludique & vigilance collective",
    sensib_hint: "Deux façons de participer : tester vos réflexes face à des situations réelles, et aider à repérer de nouvelles techniques d'arnaque - sans jamais partager d'information personnelle.",
    game_h3: "🧠 Jeu de vigilance : sauriez-vous repérer le piège ?",
    game_note: "Mécanique de gamification (niveaux, Points Bouclier, vies, catégories thématiques) adaptée à la fraude mobile money, avec Lieutenant Cyber (l'IA propre à Kimatey FinNet Guard, une création originale) comme guide. Les Points Bouclier n'ont aucune valeur monétaire ni conversion en argent réel : un indicateur de progression et de vigilance, point. Aucun compte n'est requis pour jouer : votre progression est mémorisée automatiquement dans ce navigateur. Un compte reste possible, mais entièrement optionnel, uniquement si vous voulez synchroniser votre progression entre plusieurs appareils (voir ci-dessous).",
    game_lang_note: "🌍 Les scénarios du quiz et les échanges avec Lieutenant Cyber restent en français pour le moment, quelle que soit la langue choisie ici.",
    lecon_revoir: "📖 Revoir la mini-leçon",
    lecon_precedent: "← Précédent",
    lecon_suivant: "Suivant →",
    lecon_commencer_quiz: "🎯 Commencer le quiz",
    report_h3: "🤝 Racontez à Lieutenant Cyber ce qui vous est arrivé",
    report_hint: "Pas de formulaire à remplir : discutez-en comme vous le feriez avec un ami. Aucune information personnelle n'est demandée - seule la technique utilisée par l'escroc nous intéresse.",

    // ---- Jeu : chrome JS ----
    g_level: "Niveau", g_hearts: "Vies", g_badges: "Badges",
    g_shield_points: " Points Bouclier",
    g_next_level: " (prochain niveau à ", g_shield_suffix: " 🛡️)",
    g_max_level: " - niveau maximal !",
    age_label: "Votre tranche d'âge (adapte simplement le ton de la mascotte) : ",
    age_teen: "🧒 Ado (13-17 ans)", age_adult: "🧑 Adulte (18 ans et plus)",
    teen_tip: "Astuce pour les ados : si un adulte vous pousse à agir vite ou à garder un secret pour de l'argent, parlez-en toujours à un parent ou une personne de confiance avant.",
    quiz_loading: "Chargement du jeu de vigilance...",
    no_lives: "🛡️ Plus de vies pour l'instant sur cette session.",
    recharge: "🔁 Recharger mes vies",
    validate: "Valider ma réponse",
    next_scenario: "Scénario suivant ➡️",
    feedback_good: "✅ Bien joué ! +",
    feedback_bad_1: "⚠️ Pas tout à fait (-1 ❤️, +",
    feedback_bad_2: " 🛡️ quand même, pour avoir essayé). ",
    my_badges: "🏅 Mes badges (",
    badge_locked_req: "(à ",
    badge_locked_req_suffix: " Points Bouclier)",
    game_unavailable: "Jeu de vigilance indisponible : impossible de contacter le serveur (",

    // ---- Temoignage : chrome JS ----
    report_welcome: "👋 Racontez-moi ce qui s'est passé, comme si vous en parliez à un ami - je ne vous demanderai jamais votre nom, votre numéro ou un montant précis.",
    report_thanks_1: "🎉 Merci beaucoup ! Vous êtes la ",
    report_thanks_2: "e personne à nous aider aujourd'hui à mieux repérer ce genre de piège.",
    report_last_detail: "Merci ! Un dernier détail à ajouter, à l'écrit ? C'est facultatif - et toujours sans nom, numéro ni montant.",
    report_restart: "Partager une autre expérience",
    report_detail_placeholder: "Écrivez ici si vous voulez ajouter un détail...",
    report_send: "Envoyer ma contribution 🎉",
    report_skip: "Terminer sans détail",
    report_unavailable: "Échange indisponible : impossible de contacter le serveur (",

    // ---- Certificat citoyen ----
    cert_locked_hint: "🔒 Certificat \"Citoyen Engagé\" : atteignez {xp} Points Bouclier et débloquez {badges} badges (en complétant une catégorie ou en partageant un témoignage) pour le débloquer.",
    cert_unlocked_title: "Certificat \"Citoyen Engagé\" débloqué !",
    cert_unlocked_hint: "Téléchargez votre certificat de sécurité et veille numérique, et partagez-le pour faire connaître la plateforme.",
    cert_name_label: "Nom à afficher (optionnel) :",
    cert_name_placeholder: "Laissez vide pour rester anonyme",
    cert_download_pdf: "📄 Télécharger en PDF",
    cert_download_png: "🖼️ Télécharger en image",
    cert_share: "📤 Partager",
    cert_default_name: "Citoyen Vigilant",
    cert_title: "Certificat Citoyen Engagé",
    cert_subtitle: "Sécurité & veille numérique",
    cert_body: "A activement participé au programme de sensibilisation Kimatey FinNet Guard contre la fraude mobile money, en démontrant vigilance et engagement communautaire.",
    cert_date_prefix: "Délivré le ",
    cert_stat_points: "Points Bouclier",
    cert_stat_badges: "Badges débloqués",
    cert_share_text: "Je viens d'obtenir mon certificat Citoyen Engagé sur Kimatey FinNet Guard, la plateforme IA de sécurité et sensibilisation mobile money !",
    cert_share_copied: "Texte de partage copié dans le presse-papier ! Collez-le sur vos réseaux sociaux avec l'image téléchargée.",

    // ---- Compte optionnel ----
    account_toggle: "🔐 Synchroniser ma progression entre appareils (compte optionnel)",
    account_hint: "Totalement facultatif : sans compte, votre progression reste sauvegardée dans ce navigateur uniquement. Avec un compte, elle se synchronise sur tous vos appareils.",
    account_email_placeholder: "Email",
    account_password_placeholder: "Mot de passe",
    account_register: "Créer un compte",
    account_login: "Se connecter",
    account_missing_fields: "Email et mot de passe requis.",
    account_error_generic: "Une erreur est survenue.",
    account_server_error: "Impossible de contacter le serveur.",
    account_connected_as: "🔐 Connecté en tant que",
    account_logout: "Se déconnecter",

    // ---- Fil de tendances communautaire ----
    trends_empty: "Aucune tendance disponible pour l'instant — soyez parmi les premiers à contribuer ci-dessous !",
    trends_title: "Tendances des techniques d'arnaque signalées",
    trends_based_on: "basé sur",
    trends_contributions: "contributions",
    trends_by_canal: "Par canal utilisé :",
    trends_by_demande: "Par type de demande :",

    // ---- Systeme de Pass (mode demo) ----
    pass_current: "Pass actuel :",
    pass_images_used: "Images analysées ce mois :",
    pass_upgrade_cta: "🎟️ Découvrir le Pass Famille (démo)",
    pass_needs_account: "Créez d'abord un compte optionnel ci-dessus pour souscrire à un Pass.",
    pass_demo_confirm: "Mode démo : aucun paiement réel ne sera prélevé. Activer le Pass Famille (démonstration) ?",
  },

  en: {
    nav_cta: "Enter the platform",
    live_pill: "Live monitoring",
    back_link: "← Back to home",

    eyebrow: "Network security & citizen protection · Africa",
    hero_h1_1: "One artificial intelligence.",
    hero_h1_2: "Two lines of defense.",
    hero_sub: "On one side, a machine learning engine that detects network attacks targeting fintechs and mobile money operators. On the other, a conversational assistant that helps every citizen unmask a scam before losing money to it. Same technical foundation, two protected audiences.",
    hero_cta1: "Discover the platform →",
    hero_cta2: "How it works",
    lane_org: "Organization",
    lane_public: "Public",

    problem_eyebrow: "The problem",
    problem_h2: "Mobile money changed Africa. Fraud followed the same curve.",
    problem1_fig: "75/25",
    problem1_txt: "Across analyzed network traffic, one flow in four already carries a potential attack signature against financial infrastructure.",
    problem2_fig: "SMS",
    problem2_txt: "The most common channel for scamming a mobile money user is still a message impersonating a bank or an operator.",
    problem3_fig: "2",
    problem3_txt: "distinct targets to protect at once: institutions' infrastructure, and each user's judgment the moment they receive a message.",

    how_eyebrow: "How it works",
    how_h2: "Two AI systems, one shared technical foundation.",
    how1_tag: "Supervised machine learning",
    how1_h3: "The detection engine",
    how1_p: "An optimized decision tree, trained and validated on 50,000 network flows, recognizes an attack from 5 key variables: data volume, packet rate, ports used, checksum errors, connection signal frequency.",
    how1_s1: "99.04% test accuracy",
    how1_s2: "99.92% macro AUC",
    how1_s3: "Validated in a SOC-style setting",
    how2_tag: "Generative AI",
    how2_h3: "Lieutenant Cyber",
    how2_p: "A conversational assistant (powered by Google Gemini) that citizens can describe a suspicious SMS or call to, in plain language or by voice. It explains the risk simply, with no jargon, and never collects personal data.",
    how2_s1: "Available on both the Organization and Public sides",
    how2_s2: "Backed by a gamified awareness module",
    how2_s3: "Zero personal data collection",

    spaces_eyebrow: "The platform",
    spaces_h2: "Choose your space",
    card_org_h3: "🏢 Organization Space",
    card_org_p: "Technical dashboard: real-time detection, log analysis, live monitoring, alert log. For IT/security teams at fintechs, mobile money operators, financial institutions, and public administrations.",
    card_org_cta: "Enter the Organization Space →",
    card_public_h3: "👥 Public Space",
    card_public_p: "Chat with Lieutenant Cyber, test your reflexes against mobile money scams, and help spot new ones - without ever sharing personal information.",
    card_public_cta: "Enter the Public Space →",

    proof_eyebrow: "Validated technical foundation",
    proof1_label: "network flows analyzed",
    proof2_label: "algorithms compared before selection",
    proof3_label: "automated tests",
    proof4_label: "features kept in the final model",
    proof_note: "Technically validated prototype, not yet deployed with real users or partners.",
    footer_note_index: "Kimatey FinNet Guard - Built by Komoe Edgar Junior - M1 Computer Science ML project, UFRMI - Course supervisor: Dr ASSOHOUN E Stanislas. The Organization Space is still served by the existing Streamlit app (direct deep-link); the Public Space is an independent web page calling the API directly (see config.js).",

    header_desc: "Secures the network infrastructure of fintechs, mobile money aggregators, microfinance institutions, and public administrations - and directly raises citizen awareness against mobile money scams.",
    tab_assistant: "🎖️ Lieutenant Cyber",
    tab_sensibilisation: "🎮 Awareness",

    assistant_h2: "🎖️ Lieutenant Cyber - Kimatey FinNet Guard's AI",
    assistant_hint: "Ask, in plain language, about an alert, a threat, or a suspicious mobile money message you received. This assistant explains and raises awareness; it does not replace the automatic detection in the Organization dashboard.",
    chat_placeholder: "Type your question here...",
    chat_send: "Send",
    mic_btn: "🎤",
    mic_unsupported: "Voice recognition is not supported by this browser. Try Chrome or Edge, or type your question.",
    image_btn: "📷",
    image_too_large: "Image too large (8 MB maximum).",
    image_sent_label: "📷 [Screenshot sent]",
    chat_voice_hint: "🔊 The assistant's replies are read aloud automatically (browser text-to-speech).",
    chat_welcome: "👋 Hi! Ask me about an alert or a suspicious message you received.",
    chat_unavailable: "The assistant is not available right now.",
    chat_server_error: "Could not reach the server. Check that the API is running (",

    sensib_h2: "🎮 Playful awareness & collective vigilance",
    sensib_hint: "Two ways to take part: test your reflexes against real situations, and help spot new scam techniques - without ever sharing personal information.",
    game_h3: "🧠 Vigilance game: could you spot the trap?",
    game_note: "Gamification mechanics (levels, Shield Points, lives, themed categories) adapted to mobile money fraud, with Lieutenant Cyber (Kimatey FinNet Guard's own AI, an original creation) as guide. Shield Points have no monetary value and cannot be converted to real money: a progress and vigilance indicator, nothing more. No account is required to play: your progress is saved automatically in this browser. An account remains possible, but entirely optional, only if you want to sync your progress across multiple devices (see below).",
    game_lang_note: "🌍 Quiz scenarios and exchanges with Lieutenant Cyber remain in French for now, regardless of the language selected here.",
    lecon_revoir: "📖 Review the mini-lesson",
    lecon_precedent: "← Previous",
    lecon_suivant: "Next →",
    lecon_commencer_quiz: "🎯 Start the quiz",
    report_h3: "🤝 Tell Lieutenant Cyber what happened to you",
    report_hint: "No form to fill out: chat about it like you would with a friend. No personal information is requested - only the scammer's technique matters to us.",

    g_level: "Level", g_hearts: "Lives", g_badges: "Badges",
    g_shield_points: " Shield Points",
    g_next_level: " (next level at ", g_shield_suffix: " 🛡️)",
    g_max_level: " - max level!",
    age_label: "Your age group (simply adjusts the mascot's tone): ",
    age_teen: "🧒 Teen (13-17)", age_adult: "🧑 Adult (18+)",
    teen_tip: "Tip for teens: if an adult pushes you to act fast or keep a secret involving money, always talk to a parent or trusted person first.",
    quiz_loading: "Loading the vigilance game...",
    no_lives: "🛡️ Out of lives for this session, for now.",
    recharge: "🔁 Recharge my lives",
    validate: "Submit my answer",
    next_scenario: "Next scenario ➡️",
    feedback_good: "✅ Well done! +",
    feedback_bad_1: "⚠️ Not quite (-1 ❤️, +",
    feedback_bad_2: " 🛡️ anyway, for trying). ",
    my_badges: "🏅 My badges (",
    badge_locked_req: "(at ",
    badge_locked_req_suffix: " Shield Points)",
    game_unavailable: "Vigilance game unavailable: could not reach the server (",

    report_welcome: "👋 Tell me what happened, like you would with a friend - I will never ask for your name, number, or an exact amount.",
    report_thanks_1: "🎉 Thank you so much! You're the ",
    report_thanks_2: "th person to help us better spot this kind of trap today.",
    report_last_detail: "Thanks! One last detail to add, in writing? It's optional - and always without name, number, or amount.",
    report_restart: "Share another experience",
    report_detail_placeholder: "Write here if you'd like to add a detail...",
    report_send: "Send my contribution 🎉",
    report_skip: "Finish without a detail",
    report_unavailable: "Exchange unavailable: could not reach the server (",

    // ---- Citizen certificate ----
    cert_locked_hint: "🔒 \"Engaged Citizen\" certificate: reach {xp} Shield Points and unlock {badges} badges (by completing a category or sharing a testimony) to unlock it.",
    cert_unlocked_title: "\"Engaged Citizen\" certificate unlocked!",
    cert_unlocked_hint: "Download your digital security & vigilance certificate, and share it to help others discover the platform.",
    cert_name_label: "Name to display (optional):",
    cert_name_placeholder: "Leave blank to stay anonymous",
    cert_download_pdf: "📄 Download as PDF",
    cert_download_png: "🖼️ Download as image",
    cert_share: "📤 Share",
    cert_default_name: "Vigilant Citizen",
    cert_title: "Engaged Citizen Certificate",
    cert_subtitle: "Digital Security & Vigilance",
    cert_body: "Actively took part in the Kimatey FinNet Guard mobile money fraud awareness program, demonstrating vigilance and community engagement.",
    cert_date_prefix: "Issued on ",
    cert_stat_points: "Shield Points",
    cert_stat_badges: "Badges unlocked",
    cert_share_text: "I just earned my Engaged Citizen certificate on Kimatey FinNet Guard, the AI platform for mobile money security and awareness!",
    cert_share_copied: "Share text copied to clipboard! Paste it on social media along with the downloaded image.",

    // ---- Optional account ----
    account_toggle: "🔐 Sync my progress across devices (optional account)",
    account_hint: "Completely optional: without an account, your progress stays saved in this browser only. With an account, it syncs across all your devices.",
    account_email_placeholder: "Email",
    account_password_placeholder: "Password",
    account_register: "Create account",
    account_login: "Log in",
    account_missing_fields: "Email and password required.",
    account_error_generic: "Something went wrong.",
    account_server_error: "Could not reach the server.",
    account_connected_as: "🔐 Connected as",
    account_logout: "Log out",

    // ---- Community trends feed ----
    trends_empty: "No trends available yet — be among the first to contribute below!",
    trends_title: "Trending fraud techniques reported",
    trends_based_on: "based on",
    trends_contributions: "contributions",
    trends_by_canal: "By channel used:",
    trends_by_demande: "By type of request:",

    // ---- Pass system (demo mode) ----
    pass_current: "Current Pass:",
    pass_images_used: "Images analyzed this month:",
    pass_upgrade_cta: "🎟️ Discover the Family Pass (demo)",
    pass_needs_account: "Create an optional account above first to subscribe to a Pass.",
    pass_demo_confirm: "Demo mode: no real payment will be charged. Activate the Family Pass (demonstration)?",
  },
};

function getLang() { return localStorage.getItem("kimatey_lang") || "fr"; }
function setLang(lang) { localStorage.setItem("kimatey_lang", lang); applyLang(); }
function t(key) { const lang = getLang(); return (I18N[lang] && I18N[lang][key] !== undefined) ? I18N[lang][key] : (I18N.fr[key] !== undefined ? I18N.fr[key] : key); }

function applyLang() {
  const lang = getLang();
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (I18N[lang][key] !== undefined) el.textContent = I18N[lang][key];
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (I18N[lang][key] !== undefined) el.placeholder = I18N[lang][key];
  });
  document.querySelectorAll(".lang-toggle-btn").forEach((btn) => {
    btn.textContent = lang === "fr" ? "🌍 EN" : "🌍 FR";
  });
  if (typeof onLangChange === "function") onLangChange();
}

document.addEventListener("DOMContentLoaded", applyLang);
