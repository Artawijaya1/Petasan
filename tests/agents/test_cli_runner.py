from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "Backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from Agents.cli_runner import request_command_approval, run_cli
from app.services import agent_runner


@pytest.mark.asyncio
async def test_cli_requires_explicit_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(("maybe", "Y"))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    approved = await request_command_approval("npm install", "Menjalankan setup")

    assert approved is True


@pytest.mark.asyncio
async def test_cli_defaults_to_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    approved = await request_command_approval("npm install", "Menjalankan setup")

    assert approved is False


@pytest.mark.asyncio
async def test_run_cli_passes_approval_callback_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval_results: list[bool] = []

    async def fake_run_agent(*, repo_path, emit, request_approval):
        approval_results.append(
            await request_approval("npm install", "Menjalankan setup")
        )
        return False

    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    with patch.object(agent_runner, "run_agent", new=AsyncMock(side_effect=fake_run_agent)) as run_mock, \
         patch.object(agent_runner, "cleanup_target_processes", new=AsyncMock()) as cleanup_mock:
        await run_cli(tmp_path)

    assert run_mock.await_args.kwargs["repo_path"] == tmp_path
    assert callable(run_mock.await_args.kwargs["request_approval"])
    assert approval_results == [False]
    cleanup_mock.assert_awaited_once()
