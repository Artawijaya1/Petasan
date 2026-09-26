import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIRECTORY / ".env")

AGENTS_API_URL = os.environ.get(
    "AGENTS_API_URL",
    "http://127.0.0.1:8001",
).rstrip("/")