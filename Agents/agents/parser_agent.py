# parser_agent.py
from __future__ import annotations

import asyncio
import json
import logging
import os

from openai import AsyncOpenAI, APIError, APIConnectionError, APITimeoutError

logger = logging.getLogger("parser_agent")

# Bob inference API — OpenAI-compatible endpoint
# Gunakan Inference API key dari bob.ibm.com (scope: Inference)
# Set env var: BOB_API_KEY dan BOB_BASE_URL
client = AsyncOpenAI(
    api_key=os.environ.get("BOB_API_KEY"),
    base_url=os.environ.get("BOB_BASE_URL", "https://bob.ibm.com/api"),
    timeout=20.0,
    max_retries=2,
)

BOB_MODEL = os.environ.get("BOB_MODEL", "bob")


async def scan_repository(repo_path: str) -> dict:
    files_to_check = ['package.json', 'requirements.txt', 'Dockerfile', 'docker-compose.yml', '.env.example', 'README.md']
    found_files = {}

    def _read_files() -> dict:
        """Baca file secara sinkron — dijalankan lewat asyncio.to_thread agar tidak memblokir event loop."""
        result = {}
        for file_name in files_to_check:
            full_path = os.path.join(repo_path, file_name)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        # Ambil 2000 karakter pertama agar token efisien
                        result[file_name] = f.read(2000)
                except OSError as exc:
                    logger.warning("Gagal membaca %s: %s", full_path, exc)
        return result

    found_files = await asyncio.to_thread(_read_files)

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
    """

    try:
        response = await client.chat.completions.create(
            model=BOB_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
    except (APITimeoutError, APIConnectionError, APIError) as exc:
        logger.error("Bob API error saat parsing repository: %s", exc)
        raise RuntimeError(f"Gagal menghubungi Bob API: {exc}") from exc

    raw_content = response.choices[0].message.content
    if not raw_content:
        raise RuntimeError("Bob API mengembalikan konten kosong.")

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Respons Bob bukan JSON valid: %s", raw_content[:500])
        raise RuntimeError("Bob API tidak mengembalikan JSON yang valid.") from exc