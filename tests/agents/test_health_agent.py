"""
Tests untuk Agents/agents/health_agent.py — check_health.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))

from agents.health_agent import check_health


class TestCheckHealth:
    @pytest.mark.asyncio
    async def test_returns_true_on_http_200(self) -> None:
        """Harus mengembalikan True jika server merespons HTTP 200."""
        emit = AsyncMock()

        def fake_ping() -> int:
            return 200

        with patch("agents.health_agent.asyncio.to_thread", new=AsyncMock(return_value=200)):
            result = await check_health(
                target_url="http://localhost:3000",
                max_retries=3,
                delay_seconds=0,
                websocket_send_fn=emit,
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_on_http_302(self) -> None:
        """HTTP redirect (302) juga harus diterima sebagai sukses (2xx–3xx <400)."""
        with patch("agents.health_agent.asyncio.to_thread", new=AsyncMock(return_value=302)):
            result = await check_health(
                target_url="http://localhost:3000",
                max_retries=3,
                delay_seconds=0,
            )
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_after_max_retries(self) -> None:
        """Harus mengembalikan False jika server tidak merespons setelah max_retries."""
        call_count = 0

        async def always_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise urllib.error.URLError("Connection refused")

        with patch("agents.health_agent.asyncio.to_thread", side_effect=always_fail), \
             patch("agents.health_agent.asyncio.sleep", new=AsyncMock()):
            result = await check_health(
                target_url="http://localhost:9999",
                max_retries=3,
                delay_seconds=0,
            )

        assert result is False
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_emits_in_progress_on_start(self) -> None:
        """Harus memancarkan event agent_thought saat dimulai."""
        emit = AsyncMock()

        with patch("agents.health_agent.asyncio.to_thread", new=AsyncMock(return_value=200)):
            await check_health(
                target_url="http://localhost:3000",
                max_retries=1,
                delay_seconds=0,
                websocket_send_fn=emit,
            )

        first_call_arg = emit.call_args_list[0][0][0]
        assert first_call_arg["type"] == "agent_thought"
        assert first_call_arg["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_emits_completed_on_success(self) -> None:
        """Harus memancarkan status completed saat health check berhasil."""
        emit = AsyncMock()

        with patch("agents.health_agent.asyncio.to_thread", new=AsyncMock(return_value=200)):
            await check_health(
                target_url="http://localhost:3000",
                max_retries=1,
                delay_seconds=0,
                websocket_send_fn=emit,
            )

        completed_calls = [
            c[0][0] for c in emit.call_args_list
            if c[0][0].get("status") == "completed"
        ]
        assert len(completed_calls) >= 1

    @pytest.mark.asyncio
    async def test_handles_http_error_gracefully(self) -> None:
        """HTTPError (mis. 503) tidak boleh crash, hanya log dan coba lagi."""
        emit = AsyncMock()
        call_count = 0

        async def raise_http_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                url="http://localhost:3000",
                code=503,
                msg="Service Unavailable",
                hdrs=MagicMock(),
                fp=None,
            )

        with patch("agents.health_agent.asyncio.to_thread", side_effect=raise_http_error), \
             patch("agents.health_agent.asyncio.sleep", new=AsyncMock()):
            result = await check_health(
                target_url="http://localhost:3000",
                max_retries=2,
                delay_seconds=0,
                websocket_send_fn=emit,
            )

        assert result is False
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_works_without_emit_fn(self) -> None:
        """check_health harus berjalan tanpa error meski websocket_send_fn=None."""
        with patch("agents.health_agent.asyncio.to_thread", new=AsyncMock(return_value=200)):
            result = await check_health(
                target_url="http://localhost:3000",
                max_retries=1,
                delay_seconds=0,
                websocket_send_fn=None,
            )
        assert result is True
