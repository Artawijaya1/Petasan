# healing_agent.py
from __future__ import annotations

import json
import logging
import os

from google import genai
from google.genai import types
from rag.vector_store import vector_store

logger = logging.getLogger("healing_agent")

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

SYSTEM_PROMPT = """You are an Auto-Healing DevOps Agent.
Analyze terminal error logs and provide a specific repair.

Requirements:
1. Explain why the error occurred in the thought fields.
2. Provide one appropriate terminal command to retry.
3. Write all human-readable response text in English, even if the logs or references use another language.

Response format (JSON):
{
    "thought_title": "Short issue title",
    "thought_detail": "Explanation of the cause...",
    "fix_command": "new terminal repair command"
}
"""


async def diagnose_and_fix(command_failed: str, stderr_log: str, attempt: int) -> dict | None:
    trimmed_log = stderr_log[-1500:]
    try:
        await vector_store.build_index()
        knowledge = await vector_store.retrieve(trimmed_log, top_k=3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG is unavailable during healing: %s", exc)
        knowledge = []

    knowledge_context = "\n".join(
        f"- {entry['text']} Saran yang pernah berhasil: {entry['known_fix']}"
        for entry in knowledge
    ) or "No sufficiently relevant knowledge base references were found."

    user_prompt = f"""Failed command: {command_failed}
Error log (stderr):
{trimmed_log}

Knowledge base references (use as context, not as definitive answers):
{knowledge_context}

Attempt {attempt}. Provide a diagnosis and a new repair command.
Reply ONLY with JSON and no additional text.
"""

    try:
        response = await _client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0,
            ),
        )
    except Exception as exc:
        logger.error("Gemini API error during healing (attempt %s): %s", attempt, exc)
        return None

    raw = response.text
    if not raw:
        logger.error("Gemini returned empty content during healing.")
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Healing response is not valid JSON: %s", raw[:500])
        return None

    if not isinstance(parsed.get("fix_command"), str) or not parsed["fix_command"].strip():
        logger.error("Healing response does not contain a valid 'fix_command'.")
        return None

    return parsed
