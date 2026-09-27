import os
from typing import Any

import httpx

from ..core.config import AGENTS_API_URL


async def call_agents(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    service_token = os.environ.get("AGENT_SERVICE_TOKEN")
    if not service_token:
        raise RuntimeError("AGENT_SERVICE_TOKEN is not configured in the Backend.")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{AGENTS_API_URL}{endpoint}",
                json=payload,
                headers={"Authorization": f"Bearer {service_token}"},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        raise RuntimeError(
            f"Agents API mengembalikan HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not reach the Agents API: {exc}") from exc

    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Respons Agents API harus berupa objek JSON.")
    return result