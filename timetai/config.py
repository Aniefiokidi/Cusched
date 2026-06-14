import os
from dotenv import load_dotenv

load_dotenv()

_on_vercel = bool(os.getenv("VERCEL"))


def _db_url():
    url = os.getenv("DATABASE_URL", "")
    if url:
        # Heroku/Railway/Render use postgres://, SQLAlchemy 1.4+ needs postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    if _on_vercel:
        return "sqlite:////tmp/timetai.db"
    return "sqlite:///timetai.db"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "timetai-dev-secret-2025")
    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite needs check_same_thread=False for background threads.
    # PostgreSQL (Neon) needs pool_pre_ping so suspended DBs are detected and
    # reconnected automatically, plus a generous connect_timeout for cold starts.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"connect_args": {"check_same_thread": False}}
        if not os.getenv("DATABASE_URL")
        else {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "connect_args": {"connect_timeout": 30},
        }
    )
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MAX_ITERATIONS = 5
    UPLOAD_FOLDER = "/tmp/uploads" if _on_vercel else os.path.join(os.path.dirname(__file__), "data", "uploads")
    ALLOWED_EXTENSIONS = {"csv"}
