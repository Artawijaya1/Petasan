import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIRECTORY / ".env")

DEFAULT_AGENTS_API_URL = "https://jubilant-spirit-production-47e4.up.railway.app"
AGENTS_API_URL = os.environ.get("AGENTS_API_URL", "").strip().rstrip("/")
if not AGENTS_API_URL:
    AGENTS_API_URL = DEFAULT_AGENTS_API_URL
elif not AGENTS_API_URL.startswith(("http://", "https://")):
    AGENTS_API_URL = f"https://{AGENTS_API_URL}"