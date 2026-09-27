import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIRECTORY / ".env")

AGENTS_API_URL = os.environ.get(
    "AGENTS_API_URL",
    "jubilant-spirit-production-47e4.up.railway.app",
).rstrip("/")