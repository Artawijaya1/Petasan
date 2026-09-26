"""
Tests untuk Agents/agents/healing_agent.py — diagnose_and_fix.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock sentence_transformers sebelum rantai import rag.embeddings_client di-load
sys.modules.setdefault("sentence_transformers", MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))


def _make_openai_response(content: str) -> MagicMock:
    """Helper membuat mock respons OpenAI."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
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
        mock_response = _make_openai_response(json.dumps(payload))

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

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
        mock_response = _make_openai_response(json.dumps(payload))

        captured_messages = []

        async def capture_create(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_response

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[rag_entry])
            mock_client.chat.completions.create = capture_create

            await diagnose_and_fix("npm run dev", "EADDRINUSE 3000", attempt=1)

        user_prompt = captured_messages[1]["content"]
        assert "npx kill-port 3000" in user_prompt

    @pytest.mark.asyncio
    async def test_stderr_log_trimmed_to_1500_chars(self) -> None:
        """stderr_log harus dipotong 1500 karakter terakhir."""
        from agents.healing_agent import diagnose_and_fix

        long_log = "x" * 5000
        payload = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm install"}
        mock_response = _make_openai_response(json.dumps(payload))

        captured_messages = []

        async def capture_create(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_response

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = capture_create

            await diagnose_and_fix("cmd", long_log, attempt=1)

        user_prompt = captured_messages[1]["content"]
        # Yang masuk ke prompt adalah 1500 char terakhir dari long_log
        assert "x" * 1500 in user_prompt
        assert "x" * 1501 not in user_prompt


# ---------------------------------------------------------------------------
# diagnose_and_fix — error / edge cases
# ---------------------------------------------------------------------------

class TestDiagnoseAndFixErrors:
    @pytest.mark.asyncio
    async def test_returns_none_on_api_timeout(self) -> None:
        """Harus mengembalikan None jika terjadi APITimeoutError."""
        from agents.healing_agent import diagnose_and_fix
        from openai import APITimeoutError

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError(request=MagicMock())
            )

            result = await diagnose_and_fix("npm run dev", "timeout", attempt=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_content(self) -> None:
        """Harus mengembalikan None jika Bob mengembalikan konten kosong."""
        from agents.healing_agent import diagnose_and_fix

        mock_response = _make_openai_response("")

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("npm run dev", "error", attempt=2)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_invalid_json(self) -> None:
        """Harus mengembalikan None jika respons bukan JSON valid."""
        from agents.healing_agent import diagnose_and_fix

        mock_response = _make_openai_response("bukan json sama sekali")

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("cmd", "err", attempt=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_fix_command_missing(self) -> None:
        """Harus mengembalikan None jika JSON tidak mengandung fix_command."""
        from agents.healing_agent import diagnose_and_fix

        payload = {"thought_title": "T", "thought_detail": "D"}  # fix_command hilang
        mock_response = _make_openai_response(json.dumps(payload))

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock()
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("cmd", "err", attempt=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_continues_when_rag_fails(self) -> None:
        """Jika RAG throw exception, healing harus tetap berjalan (tanpa knowledge)."""
        from agents.healing_agent import diagnose_and_fix

        payload = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm install"}
        mock_response = _make_openai_response(json.dumps(payload))

        with patch("agents.healing_agent.vector_store") as mock_vs, \
             patch("agents.healing_agent.client") as mock_client:
            mock_vs.build_index = AsyncMock(side_effect=Exception("RAG down"))
            mock_vs.retrieve = AsyncMock(return_value=[])
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await diagnose_and_fix("cmd", "err", attempt=1)

        assert result is not None
        assert result["fix_command"] == "npm install"
