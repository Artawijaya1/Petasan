"""
Tests untuk Agents/agents/parser_agent.py — create_installation_plan & scan_repository (Gemini).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock google.genai agar tidak butuh API key saat test
_mock_genai = MagicMock()
_mock_genai.Client = MagicMock
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.genai", _mock_genai)
sys.modules.setdefault("google.genai.types", MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))


def _make_gemini_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


# ---------------------------------------------------------------------------
# create_installation_plan
# ---------------------------------------------------------------------------

class TestCreateInstallationPlan:
    @pytest.mark.asyncio
    async def test_returns_plan_dict_on_success(self) -> None:
        """Harus mengembalikan setup command dan start command terpisah."""
        from agents.parser_agent import create_installation_plan

        plan = {
            "commands": ["npm install"],
            "start_command": "npm run dev -- --host 0.0.0.0",
            "port": 5173,
        }
        mock_response = _make_gemini_response(json.dumps(plan))

        with patch("agents.parser_agent._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            result = await create_installation_plan({"package.json": '{"name": "app"}'})

        assert result["commands"] == ["npm install"]
        assert result["start_command"] == "npm run dev -- --host 0.0.0.0"
        assert result["port"] == 5173

    @pytest.mark.asyncio
    async def test_files_included_in_prompt(self) -> None:
        """Isi file harus dikirim ke Gemini sebagai bagian dari prompt."""
        from agents.parser_agent import create_installation_plan

        plan = {
            "commands": ["pip install -r requirements.txt"],
            "start_command": None,
            "port": None,
        }
        mock_response = _make_gemini_response(json.dumps(plan))
        captured = []

        async def capture_generate(**kwargs):
            captured.append(kwargs.get("contents", ""))
            return mock_response

        with patch("agents.parser_agent._client") as mock_client:
            mock_client.aio.models.generate_content = capture_generate
            await create_installation_plan({"requirements.txt": "fastapi\nuvicorn"})

        assert "requirements.txt" in captured[0]
        assert "fastapi" in captured[0]
        assert "Jangan membuat manifest" in captured[0]
        assert "jangan membuat manifest" in captured[0].lower()

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_api_exception(self) -> None:
        """Harus raise RuntimeError jika Gemini API melempar exception."""
        from agents.parser_agent import create_installation_plan

        with patch("agents.parser_agent._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=Exception("connection error")
            )
            with pytest.raises(RuntimeError, match="Gagal menghubungi Gemini API"):
                await create_installation_plan({"package.json": "{}"})

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_empty_content(self) -> None:
        """Harus raise RuntimeError jika Gemini mengembalikan konten kosong."""
        from agents.parser_agent import create_installation_plan

        mock_response = _make_gemini_response("")

        with patch("agents.parser_agent._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            with pytest.raises(RuntimeError, match="konten kosong"):
                await create_installation_plan({"package.json": "{}"})

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_invalid_json(self) -> None:
        """Harus raise RuntimeError jika respons bukan JSON valid."""
        from agents.parser_agent import create_installation_plan

        mock_response = _make_gemini_response("bukan json")

        with patch("agents.parser_agent._client") as mock_client:
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
            with pytest.raises(RuntimeError, match="JSON"):
                await create_installation_plan({"package.json": "{}"})


# ---------------------------------------------------------------------------
# scan_repository
# ---------------------------------------------------------------------------

class TestScanRepository:
    @pytest.mark.asyncio
    async def test_reads_files_and_calls_create_plan(self) -> None:
        from agents.parser_agent import scan_repository

        plan = {"commands": ["npm install"], "start_command": None, "port": None}
        mock_response = _make_gemini_response(json.dumps(plan))

        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg = Path(tmp_dir) / "package.json"
            pkg.write_text('{"name":"test"}', encoding="utf-8")

            with patch("agents.parser_agent._client") as mock_client:
                mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
                result = await scan_repository(tmp_dir)

        assert "commands" in result

    @pytest.mark.asyncio
    async def test_returns_empty_plan_for_empty_directory(self) -> None:
        from agents.parser_agent import scan_repository

        plan = {"commands": [], "start_command": None, "port": None}
        mock_response = _make_gemini_response(json.dumps(plan))

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("agents.parser_agent._client") as mock_client:
                mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
                result = await scan_repository(tmp_dir)

        assert isinstance(result, dict)
