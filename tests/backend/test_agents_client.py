"""
Tests untuk Backend/app/services/agents_client.py — call_agents.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("AGENTS_API_URL", "http://localhost:8001")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from app.services.agents_client import call_agents


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Buat mock httpx.Response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.text = str(json_data)
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=response,
        )
    return response


class TestCallAgents:
    @pytest.mark.asyncio
    async def test_returns_json_dict_on_success(self) -> None:
        """Harus mengembalikan dict dari JSON response jika HTTP 200."""
        expected = {"env_needed": False, "commands": ["npm install"]}
        mock_response = _mock_response(expected, 200)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.agents_client.httpx.AsyncClient", return_value=mock_client):
            result = await call_agents("/v1/scan", {"files": {}})

        assert result == expected

    @pytest.mark.asyncio
    async def test_sends_bearer_token_header(self) -> None:
        """Harus menyertakan Authorization: Bearer header dari env var."""
        expected = {"result": "ok"}
        mock_response = _mock_response(expected, 200)
        captured_headers: dict = {}

        async def fake_post(url, json=None, headers=None):
            captured_headers.update(headers or {})
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with patch("app.services.agents_client.httpx.AsyncClient", return_value=mock_client), \
             patch.dict(os.environ, {"AGENT_SERVICE_TOKEN": "my-secret-token"}):
            await call_agents("/v1/heal", {})

        assert captured_headers.get("Authorization") == "Bearer my-secret-token"

    @pytest.mark.asyncio
    async def test_uses_correct_url(self) -> None:
        """URL yang dipanggil harus berisi AGENTS_API_URL + endpoint."""
        expected = {"ok": True}
        mock_response = _mock_response(expected, 200)
        captured_url: list[str] = []

        async def fake_post(url, **kwargs):
            captured_url.append(url)
            return mock_response

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post

        with patch("app.services.agents_client.httpx.AsyncClient", return_value=mock_client), \
             patch("app.services.agents_client.AGENTS_API_URL", "http://agents:8001"):
            await call_agents("/v1/scan", {})

        assert captured_url[0] == "http://agents:8001/v1/scan"

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_http_status_error(self) -> None:
        """HTTP 4xx/5xx harus dikonversi menjadi RuntimeError."""
        mock_response = _mock_response({"detail": "Unauthorized"}, 401)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.agents_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                await call_agents("/v1/scan", {})

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_connection_error(self) -> None:
        """Jika Agents API tidak bisa dihubungi, harus raise RuntimeError."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch("app.services.agents_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="Tidak dapat menghubungi"):
                await call_agents("/v1/scan", {})

    @pytest.mark.asyncio
    async def test_raises_runtime_error_when_token_missing(self) -> None:
        """Jika AGENT_SERVICE_TOKEN tidak ada, harus raise RuntimeError sebelum HTTP call."""
        with patch.dict(os.environ, {"AGENT_SERVICE_TOKEN": ""}, clear=False):
            # Hapus sementara agar os.environ.get mengembalikan None
            original = os.environ.pop("AGENT_SERVICE_TOKEN", None)
            try:
                with pytest.raises(RuntimeError, match="AGENT_SERVICE_TOKEN"):
                    await call_agents("/v1/scan", {})
            finally:
                if original is not None:
                    os.environ["AGENT_SERVICE_TOKEN"] = original

    @pytest.mark.asyncio
    async def test_raises_runtime_error_if_response_not_dict(self) -> None:
        """Jika JSON response bukan dict (mis. list), harus raise RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["not", "a", "dict"]  # bukan dict

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.services.agents_client.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RuntimeError, match="objek JSON"):
                await call_agents("/v1/heal", {})
