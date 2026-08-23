/*
 * Configuration de deploiement - Kimatey FinNet Guard (page d'accueil + Espace
 * Grand Public web). Ce sont les DEUX seules valeurs a changer pour deployer
 * cette page ailleurs qu'en local :
 *
 * - API_BASE_URL : ou tourne l'API FastAPI (voir api/main.py, lancee avec
 *   `uvicorn api.main:app --port 8000`). Le CORS de l'API est ouvert (*),
 *   donc cette page peut etre hebergee sur un domaine different.
 * - ORG_APP_URL : ou tourne l'application Streamlit de l'Espace Organisation
 *   (voir app/app.py, lancee avec `streamlit run app/app.py`). Le lien
 *   d'accueil pointe vers "<ORG_APP_URL>/?view=organisation" pour entrer
 *   directement dans l'espace, sans repasser par la page d'accueil Streamlit.
 */
const API_BASE_URL = "http://localhost:8000";
const ORG_APP_URL = "http://localhost:8501";
