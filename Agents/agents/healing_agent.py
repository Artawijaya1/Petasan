# healing_agent.py
from __future__ import annotations

import json
import logging
import os

from openai import AsyncOpenAI, APIError, APIConnectionError, APITimeoutError

logger = logging.getLogger("healing_agent")

client = AsyncOpenAI(
    api_key=os.environ.get("BOB_API_KEY"),
    base_url=os.environ.get("BOB_BASE_URL", "https://bob.ibm.com/api"),
    timeout=20.0,
    max_retries=2,
)
BOB_MODEL = os.environ.get("BOB_MODEL", "bob")

SYSTEM_PROMPT = """Kamu adalah Auto-Healing DevOps Agent.
Tugasmu adalah menganalisis error log terminal dan memberikan perbaikan spesifik.

Tugasmu:
1. Berikan alasan kenapa error terjadi (Thought Process).
2. Berikan 1 perintah perbaikan terminal yang tepat untuk dicoba ulang.

Format JSON Response:
{
  "thought_title": "Judul Singkat Masalah",
  "thought_detail": "Penjelasan mendalam penyebab error...",
  "fix_command": "perintah perbaikan terminal baru"
}
"""


async def diagnose_and_fix(command_failed: str, stderr_log: str, attempt: int) -> dict | None:
    trimmed_log = stderr_log[-1500:]
    user_prompt = f"""Perintah yang gagal: {command_failed}
Error Log (stderr):
{trimmed_log}

Percobaan ke-{attempt}. Berikan diagnosis dan perintah perbaikan baru.
"""

    try:
        response = await client.chat.completions.create(
            model=BOB_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except (APITimeoutError, APIConnectionError, APIError) as exc:
        logger.error("Bob API error saat healing (attempt %s): %s", attempt, exc)
        return None

    raw = response.choices[0].message.content
    if not raw:
        logger.error("Bob mengembalikan konten kosong saat healing.")
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Respons healing bukan JSON valid: %s", raw[:500])
        return None

    if not isinstance(parsed.get("fix_command"), str) or not parsed["fix_command"].strip():
        logger.error("Respons healing tidak memiliki 'fix_command' yang valid.")
        return None

    return parsed