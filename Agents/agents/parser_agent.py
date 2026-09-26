# parser_agent.py
from __future__ import annotations

import asyncio
import json
import logging
import os

from google import genai
from google.genai import types

logger = logging.getLogger("parser_agent")

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")


async def scan_repository(repo_path: str) -> dict:
    files_to_check = ['package.json', 'requirements.txt', 'Dockerfile', 'docker-compose.yml', '.env.example', 'README.md']

    def _read_files() -> dict:
        """Baca file secara sinkron — dijalankan lewat asyncio.to_thread agar tidak memblokir event loop."""
        result = {}
        for file_name in files_to_check:
            full_path = os.path.join(repo_path, file_name)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        result[file_name] = f.read(2000)
                except OSError as exc:
                    logger.warning("Gagal membaca %s: %s", full_path, exc)
        return result

    found_files = await asyncio.to_thread(_read_files)
    return await create_installation_plan(found_files)


async def create_installation_plan(found_files: dict[str, str]) -> dict:

    prompt = f"""
    Kamu adalah DevOps Architect Agent.
    Berdasarkan isi file repository berikut, buat rencana instalasi berupa JSON array of commands.
    
    File yang ditemukan:
    {json.dumps(found_files, indent=2)}

    Format Output Harus Berupa JSON Valid:
    {{
      "env_needed": true,
      "commands": [
        "npm install",
        "npm run dev"
      ]
    }}

    Balas HANYA dengan JSON valid, tanpa teks tambahan apapun.
    """

    try:
        response = await _client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        logger.error("Gemini API error saat parsing repository: %s", exc)
        raise RuntimeError(f"Gagal menghubungi Gemini API: {exc}") from exc

    raw_content = response.text
    if not raw_content:
        raise RuntimeError("Gemini API mengembalikan konten kosong.")

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Respons Gemini bukan JSON valid: %s", raw_content[:500])
        raise RuntimeError("Gemini API tidak mengembalikan JSON yang valid.") from exc
