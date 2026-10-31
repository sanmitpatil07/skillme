import os, secrets
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent

# Automatically load environment variables from .env in project root
load_dotenv(ROOT / ".env")

DB_PATH = os.getenv("SKILLME_DB", str(ROOT / "skillme.db"))
SECRET = (os.getenv("SKILLME_SECRET") or secrets.token_hex(32)).strip("\"' \t\r\n")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip("\"' \t\r\n")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip("\"' \t\r\n")
# Ensure invalid or placeholder model names map to a standard supported Anthropic model
if MODEL in ("claude-sonnet-5-5", "claude-sonnet-3-5", ""):
    MODEL = "claude-3-5-sonnet-20241022"

TAGGER = Path(os.getenv("SKILLME_TAGGER", str(ROOT / "models" / "tagger.joblib")))
FRONT = ROOT / "frontend"
