"""
Tests untuk Agents/agents/parser_agent.py — create_installation_plan & scan_repository.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))


def _make_openai_response(content: str) -> MagicMock:
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# create_installation_plan
# ---------------------------------------------------------------------------

class TestCreateInstallationPlan:
    @pytest.mark.asyncio
    async def test_returns_plan_dict_on_success(self) -> None:
        """Harus mengembalikan dict dengan env_needed dan commands pada respons valid."""
        from agents.parser_agent import create_installation_plan

        plan = {"env_needed": False, "commands": ["npm install", "npm run dev"]}
        mock_response = _make_openai_response(json.dumps(plan))

        with patch("agents.parser_agent.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await create_installation_plan({"package.json": '{"name": "app"}'})

        assert result["env_needed"] is False
        assert result["commands"] == ["npm install", "npm run dev"]

    @pytest.mark.asyncio
    async def test_files_included_in_prompt(self) -> None:
        """Isi file harus dikirim ke Bob sebagai bagian dari prompt."""
        from agents.parser_agent import create_installation_plan

        plan = {"env_needed": True, "commands": ["pip install -r requirements.txt"]}
        mock_response = _make_openai_response(json.dumps(plan))

        captured = {}

        async def capture_create(**kwargs):
            captured["messages"] = kwargs.get("messages", [])
            return mock_response

        with patch("agents.parser_agent.client") as mock_client:
            mock_client.chat.completions.create = capture_create
            await create_installation_plan({"requirements.txt": "fastapi\nuvicorn"})

        prompt_content = captured["messages"][0]["content"]
        assert "requirements.txt" in prompt_content
        assert "fastapi" in prompt_content

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_api_timeout(self) -> None:
        """Harus raise RuntimeError jika Bob API timeout."""
        from agents.parser_agent import create_installation_plan
        from openai import APITimeoutError

        with patch("agents.parser_agent.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError(request=MagicMock())
            )
            with pytest.raises(RuntimeError, match="Gagal menghubungi Bob API"):
                await create_installation_plan({"package.json": "{}"})

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_empty_content(self) -> None:
        """Harus raise RuntimeError jika Bob mengembalikan konten kosong."""
        from agents.parser_agent import create_installation_plan

        mock_response = _make_openai_response("")

        with patch("agents.parser_agent.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            with pytest.raises(RuntimeError, match="konten kosong"):
                await create_installation_plan({"package.json": "{}"})

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_invalid_json(self) -> None:
        """Harus raise RuntimeError jika respons bukan JSON valid."""
        from agents.parser_agent import create_installation_plan

        mock_response = _make_openai_response("bukan json")

        with patch("agents.parser_agent.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            with pytest.raises(RuntimeError, match="JSON"):
                await create_installation_plan({"package.json": "{}"})


# ---------------------------------------------------------------------------
# scan_repository
# ---------------------------------------------------------------------------

class TestScanRepository:
    @pytest.mark.asyncio
    async def test_reads_files_and_calls_create_plan(self) -> None:
        """scan_repository harus membaca file yang tersedia dan memanggil create_installation_plan."""
        from agents.parser_agent import scan_repository

        plan = {"env_needed": False, "commands": ["npm install"]}
        mock_response = _make_openai_response(json.dumps(plan))

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Buat package.json palsu di tmp dir
            pkg = Path(tmp_dir) / "package.json"
            pkg.write_text('{"name":"test"}', encoding="utf-8")

            with patch("agents.parser_agent.client") as mock_client:
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                result = await scan_repository(tmp_dir)

        assert "commands" in result

    @pytest.mark.asyncio
    async def test_returns_empty_plan_for_empty_directory(self) -> None:
        """Direktori tanpa file yang dikenali harus tetap mengembalikan rencana (mungkin kosong)."""
        from agents.parser_agent import scan_repository

        plan = {"env_needed": False, "commands": []}
        mock_response = _make_openai_response(json.dumps(plan))

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("agents.parser_agent.client") as mock_client:
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                result = await scan_repository(tmp_dir)

        assert isinstance(result, dict)
