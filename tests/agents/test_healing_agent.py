"""
Tests untuk Agents/agents/healing_agent.py — diagnose_and_fix (Gemini).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock sentence_transformers sebelum rantai import healing_agent → vector_store
sys.modules.setdefault("sentence_transformers", MagicMock())
# Mock google.genai agar tidak butuh API key saat test
_mock_genai = MagicMock()
_mock_genai.Client = MagicMock
_mock_genai.types = MagicMock()
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.genai", _mock_genai)
sys.modules.setdefault("google.genai.types", MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))


def _make_gemini_response(text: str) -> MagicMock:
    """Helper membuat mock respons Gemini."""
    response = MagicMock()
    response.text = text
    return response


# ---------------------------------------------------------------------------
# diagnose_and_fix — happy path
# ---------------------------------------------------------------------------

class TestDiagnoseAndFix:
    @pytest.mark.asyncio
    async def test_returns_valid_dict_on_success(self) -> None:
        """Harus mengembalikan dict dengan key yang benar pada respons normal."""
        from agents.healing_agent import diagnose_and_fix

        payload = {
            "thought_title": "Module hilang",
            "thought_detail": "Dependency belum terinstall.",
            "fix_command": "npm install",
        }
        mock_response = _make_gemini_response(json.dumps(payload))

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("npm install", "Cannot find module 'x'", attempt=1)

        assert result is not None
        assert result["fix_command"] == "npm install"
        assert "thought_title" in result
        assert "thought_detail" in result

    @pytest.mark.asyncio
    async def test_uses_rag_knowledge_in_prompt(self) -> None:
        """Harus memasukkan knowledge dari RAG ke prompt jika tersedia."""
        from agents.healing_agent import diagnose_and_fix

        rag_entry = {
            "text": "EADDRINUSE port sudah dipakai",
            "known_fix": "npx kill-port 3000",
        }
        payload = {"thought_title": "Port conflict", "thought_detail": ".", "fix_command": "npx kill-port 3000"}
        mock_response = _make_gemini_response(json.dumps(payload))

        captured_contents = []

        async def capture_generate(**kwargs):
            captured_contents.append(kwargs.get("contents", ""))
            return mock_response

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[rag_entry])
            mock_client.aio.models.generate_content = capture_generate

            await diagnose_and_fix("npm run dev", "EADDRINUSE 3000", attempt=1)

        assert "npx kill-port 3000" in captured_contents[0]

    @pytest.mark.asyncio
    async def test_stderr_log_trimmed_to_1500_chars(self) -> None:
        """stderr_log harus dipotong 1500 karakter terakhir."""
        from agents.healing_agent import diagnose_and_fix

        long_log = "x" * 5000
        payload = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm install"}
        mock_response = _make_gemini_response(json.dumps(payload))
        captured = []

        async def capture_generate(**kwargs):
            captured.append(kwargs.get("contents", ""))
            return mock_response

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = capture_generate

            await diagnose_and_fix("cmd", long_log, attempt=1)

        assert "x" * 1500 in captured[0]
        assert "x" * 1501 not in captured[0]


# ---------------------------------------------------------------------------
# diagnose_and_fix — error / edge cases
# ---------------------------------------------------------------------------

class TestDiagnoseAndFixErrors:
    @pytest.mark.asyncio
    async def test_returns_none_on_api_exception(self) -> None:
        """Harus mengembalikan None jika Gemini API melempar exception."""
        from agents.healing_agent import diagnose_and_fix

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=Exception("API timeout")
            )

            result = await diagnose_and_fix("npm run dev", "timeout", attempt=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_content(self) -> None:
        """Harus mengembalikan None jika Gemini mengembalikan teks kosong."""
        from agents.healing_agent import diagnose_and_fix

        mock_response = _make_gemini_response("")

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("npm run dev", "error", attempt=2)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self) -> None:
        """Harus mengembalikan None jika respons bukan JSON valid."""
        from agents.healing_agent import diagnose_and_fix

        mock_response = _make_gemini_response("bukan json sama sekali")

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("cmd", "err", attempt=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_fix_command_missing(self) -> None:
        """Harus mengembalikan None jika JSON tidak mengandung fix_command."""
        from agents.healing_agent import diagnose_and_fix

        payload = {"thought_title": "T", "thought_detail": "D"}
        mock_response = _make_gemini_response(json.dumps(payload))

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("cmd", "err", attempt=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_continues_when_rag_fails(self) -> None:
        """Jika RAG throw exception, healing harus tetap berjalan."""
        from agents.healing_agent import diagnose_and_fix

        payload = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm install"}
        mock_response = _make_gemini_response(json.dumps(payload))

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent._client") as mock_client:
            mock_vs.build_index = AsyncMock(side_effect=Exception("RAG down"))
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("cmd", "err", attempt=1)

        assert result is not None
        assert result["fix_command"] == "npm install"
