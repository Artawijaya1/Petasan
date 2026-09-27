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
        """Read files synchronously in a worker thread to avoid blocking the event loop."""
        result = {}
        for file_name in files_to_check:
            full_path = os.path.join(repo_path, file_name)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        result[file_name] = f.read(2000)
                except OSError as exc:
                    logger.warning("Failed to read %s: %s", full_path, exc)
        return result

    found_files = await asyncio.to_thread(_read_files)
    return await create_installation_plan(found_files)


async def create_installation_plan(found_files: dict[str, str]) -> dict:

    prompt = f"""
    You are a DevOps Architect Agent.
    Based on the provided repository manifests, create an environment setup plan.
    The user must approve every command before it is run.
    Do not create manifests or suggest npm init.

    All human-readable text in your response must be in English.

    Discovered files:
    {json.dumps(found_files, indent=2)}

    Required output format (valid JSON):
    {{
            "commands": ["npm install"],
            "start_command": "npm run dev -- --host 0.0.0.0",
            "port": 5173
    }}

        Rules:
        - Use only the package manager supported by the discovered manifests.
        - Do not suggest installation if the relevant dependency manifest is missing.
        - Do not copy or create .env files; only report if a template is present.
        - Keep install/build commands separate from the long-running start_command.
        - Set start_command to null if the manifest does not define a runnable application.
        - Use the port from project configuration; Vite commonly uses 5173 and Next.js commonly uses 3000.

    Reply ONLY with valid JSON and no additional text.
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
        logger.error("Gemini API error while parsing repository: %s", exc)
        raise RuntimeError(f"Could not reach the Gemini API: {exc}") from exc

    raw_content = response.text
    if not raw_content:
        raise RuntimeError("The Gemini API returned empty content.")

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError as exc:
        logger.error("Gemini response is not valid JSON: %s", raw_content[:500])
        raise RuntimeError("The Gemini API did not return valid JSON.") from exc
