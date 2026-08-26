"""
Connexion a une base de donnees PostgreSQL persistante (Neon, Supabase, Render Postgres...),
avec repli automatique sur le stockage fichier JSON si aucune base n'est configuree.

Pourquoi ce module existe : sur le plan gratuit Render, le disque n'est PAS persistant -
chaque redeploiement recree le conteneur depuis zero, effacant tout fichier JSON ecrit en
cours d'execution (comptes utilisateurs, journal d'alertes, abonnements Pass...). Une vraie
base de donnees externe resout ce probleme definitivement.

Usage :
- Si la variable d'environnement DATABASE_URL est definie (ex. fournie par Neon), les
  fonctions de ce module s'y connectent et y persistent les donnees reellement.
- Sinon, `get_connection()` retourne None, et le code appelant doit se rabattre sur son
  ancien comportement fichier JSON (voir api/auth.py pour un exemple de ce pattern).
"""
import os
from contextlib import contextmanager

try:
    import psycopg
    PSYCOPG_AVAILABLE = True
except ImportError:
    psycopg = None
    PSYCOPG_AVAILABLE = False


def database_configured() -> bool:
    return PSYCOPG_AVAILABLE and bool(os.environ.get("DATABASE_URL"))


@contextmanager
def get_connection():
    """Context manager : fournit une connexion psycopg si DATABASE_URL est configuree,
    sinon leve RuntimeError (l'appelant doit verifier database_configured() avant)."""
    if not database_configured():
        raise RuntimeError("DATABASE_URL non configuree - utiliser le repli fichier JSON.")
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema():
    """Cree les tables necessaires si elles n'existent pas encore. A appeler une fois au
    demarrage de l'API (idempotent - sans effet si les tables existent deja)."""
    if not database_configured():
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
