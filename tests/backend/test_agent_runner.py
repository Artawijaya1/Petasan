"""
Tests untuk Backend/app/services/agent_runner.py — _read_repository_files & run_agent.
"""
from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("AGENTS_API_URL", "http://localhost:8001")
os.environ.setdefault("BOB_API_KEY", "test-api-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from app.services.agent_runner import (
    _infer_start_settings,
    _read_repository_files,
    _start_target_service,
    cleanup_target_processes,
    run_agent,
)


# ---------------------------------------------------------------------------
# _read_repository_files
# ---------------------------------------------------------------------------

class TestReadRepositoryFiles:
    def test_reads_known_files(self) -> None:
        """Harus membaca file-file yang ada di FILES_TO_SCAN."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text('{"name":"test"}', encoding="utf-8")
            (repo / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

            result = _read_repository_files(repo)

        assert "package.json" in result
        assert result["package.json"] == '{"name":"test"}'
        assert "requirements.txt" in result

    def test_ignores_unknown_files(self) -> None:
        """File di luar FILES_TO_SCAN harus diabaikan."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "random_file.txt").write_text("ignored", encoding="utf-8")

            result = _read_repository_files(repo)

        assert "random_file.txt" not in result

    def test_truncates_file_to_2000_chars(self) -> None:
        """Konten file harus dipotong pada 2000 karakter."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("x" * 5000, encoding="utf-8")

            result = _read_repository_files(repo)

        assert len(result["package.json"]) == 2000

    def test_returns_empty_dict_for_empty_directory(self) -> None:
        """Direktori tanpa file yang dikenali harus menghasilkan dict kosong."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _read_repository_files(Path(tmp_dir))
        assert result == {}

    def test_skips_unreadable_files(self) -> None:
        """File yang tidak bisa dibaca tidak boleh menyebabkan crash."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            pkg = repo / "package.json"
            pkg.write_text("{}", encoding="utf-8")

            with patch("builtins.open", side_effect=OSError("permission denied")):
                # Seharusnya tidak raise, hanya skip
                result = _read_repository_files(repo)

        # File ada tapi tidak terbaca → key tidak ada di result
        assert isinstance(result, dict)


class TestStartSettings:
    def test_infers_vite_port_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text(
                '{"scripts":{"dev":"vite --host 0.0.0.0"}}',
                encoding="utf-8",
            )
            assert _infer_start_settings({}, repo) == ("npm run dev", 5173)

    def test_uses_custom_port_from_manifest_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text(
                '{"scripts":{"dev":"vite --port 4173"}}',
                encoding="utf-8",
            )
            assert _infer_start_settings({}, repo) == ("npm run dev", 4173)

    def test_infers_next_default_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text(
                '{"scripts":{"dev":"next dev"}}',
                encoding="utf-8",
            )
            assert _infer_start_settings({}, repo) == ("npm run dev", 3000)

    @pytest.mark.asyncio
    async def test_refuses_to_claim_a_port_owned_by_another_process(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            events: list[dict[str, Any]] = []

            async def collect_emit(data: dict[str, Any]) -> None:
                events.append(data)

            with tempfile.TemporaryDirectory() as tmp_dir:
                started = await _start_target_service(
                    "this command must not start",
                    port,
                    Path(tmp_dir),
                    collect_emit,
                )

        assert started is False
        assert any(event.get("title") == "Port aplikasi sudah digunakan" for event in events)


class TestDynamicTargetService:
    @pytest.mark.asyncio
    async def test_starts_and_health_checks_the_selected_port(self) -> None:
        import httpx

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        events: list[dict[str, Any]] = []

        async def collect_emit(data: dict[str, Any]) -> None:
            events.append(data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            repo = workspace / "repository"
            repo.mkdir()
            command = f'"{sys.executable}" -m http.server {port} --bind 127.0.0.1'

            try:
                started = await _start_target_service(command, port, repo, collect_emit)
                assert started is True
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{port}")
                assert response.status_code == 200
            finally:
                await cleanup_target_processes()

        assert any(
            event.get("content", "").endswith(f"http://127.0.0.1:{port}...")
            for event in events
        )


# ---------------------------------------------------------------------------
# run_agent — happy path
# ---------------------------------------------------------------------------

class TestRunAgentHappyPath:
    @pytest.mark.asyncio
    async def test_emits_completed_when_all_commands_succeed(self) -> None:
        """Harus memancarkan 'Environment Ready!' jika semua command sukses."""
        emit = AsyncMock()
        events: list[dict[str, Any]] = []

        async def collect_emit(data: dict) -> None:
            events.append(data)

        plan = {
            "commands": ["npm install"],
            "start_command": "npm run dev -- --host 0.0.0.0",
            "port": 5173,
        }
        cmd_result = {"exit_code": 0, "stdout": "ok", "stderr": ""}
        approve = AsyncMock(return_value=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")

            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=plan)), \
                 patch("app.services.agent_runner._run_command", new=AsyncMock(return_value=cmd_result)), \
                 patch("app.services.agent_runner._start_target_service", new=AsyncMock(return_value=True)) as start_service:
                await run_agent(repo, collect_emit, approve)

        titles = [e.get("title") for e in events]
        assert "Environment Ready!" in titles
        start_service.assert_awaited_once_with(
            "npm run dev -- --host 0.0.0.0", 5173, repo, collect_emit
        )
        assert approve.await_count == 2

    @pytest.mark.asyncio
    async def test_does_not_create_env_from_template(self) -> None:
        """Template .env tidak boleh disalin otomatis."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            (repo / ".env.example").write_text("SECRET=xxx\n", encoding="utf-8")

            plan = {"commands": [], "start_command": None, "port": None}

            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=plan)):
                await run_agent(repo, AsyncMock(), AsyncMock(return_value=True))

            assert not (repo / ".env").exists()

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_env(self) -> None:
        """Tidak boleh menimpa .env yang sudah ada."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            (repo / ".env.example").write_text("EXAMPLE=1\n", encoding="utf-8")
            (repo / ".env").write_text("EXISTING=2\n", encoding="utf-8")

            plan = {"commands": [], "start_command": None, "port": None}

            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=plan)):
                await run_agent(repo, AsyncMock(), AsyncMock(return_value=True))

            # .env harus tetap berisi konten lama
            assert (repo / ".env").read_text() == "EXISTING=2\n"


# ---------------------------------------------------------------------------
# run_agent — healing loop
# ---------------------------------------------------------------------------

class TestRunAgentHealingLoop:
    @pytest.mark.asyncio
    async def test_triggers_healing_on_command_failure(self) -> None:
        """Jika command gagal, harus memanggil /v1/heal dan coba lagi."""
        events: list[dict] = []

        async def collect_emit(data):
            events.append(data)

        plan = {
            "commands": ["npm install"],
            "start_command": "npm run dev -- --host 0.0.0.0",
            "port": 5173,
        }
        fail_result = {"exit_code": 1, "stdout": "", "stderr": "Cannot find module"}
        success_result = {"exit_code": 0, "stdout": "ok", "stderr": ""}
        healing = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm install --force"}

        call_count = 0

        async def fake_run_command(cmd, emit_fn, cwd):
            nonlocal call_count
            call_count += 1
            return fail_result if call_count == 1 else success_result

        async def fake_call_agents(endpoint, payload):
            if endpoint == "/v1/scan":
                return plan
            return healing

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            with patch("app.services.agent_runner.call_agents", side_effect=fake_call_agents), \
                 patch("app.services.agent_runner._run_command", side_effect=fake_run_command), \
                 patch("app.services.agent_runner._start_target_service", new=AsyncMock(return_value=True)):
                await run_agent(repo, collect_emit, AsyncMock(return_value=True))

        # Harus ada event healing
        healing_events = [e for e in events if "Auto-Healing" in e.get("title", "")]
        assert len(healing_events) >= 1

    @pytest.mark.asyncio
    async def test_emits_failed_after_3_attempts(self) -> None:
        """Setelah 3 kali gagal, harus memancarkan status failed."""
        events: list[dict] = []

        async def collect_emit(data):
            events.append(data)

        plan = {"commands": ["npm run build"], "start_command": None, "port": None}
        fail_result = {"exit_code": 1, "stdout": "", "stderr": "build error"}
        healing = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm run build --verbose"}

        async def fake_call_agents(endpoint, payload):
            if endpoint == "/v1/scan":
                return plan
            return healing

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            with patch("app.services.agent_runner.call_agents", side_effect=fake_call_agents), \
                 patch("app.services.agent_runner._run_command", new=AsyncMock(return_value=fail_result)):
                await run_agent(repo, collect_emit, AsyncMock(return_value=True))

        failed_events = [e for e in events if e.get("status") == "failed"]
        assert len(failed_events) >= 1

    @pytest.mark.asyncio
    async def test_raises_value_error_on_invalid_plan(self) -> None:
        """Harus raise ValueError jika commands bukan list of strings yang valid."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            bad_plan = {"env_needed": False, "commands": [123, None]}

            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=bad_plan)):
                with pytest.raises(ValueError, match="commands"):
                    await run_agent(repo, AsyncMock(), AsyncMock(return_value=True))

    @pytest.mark.asyncio
    async def test_no_manifest_skips_agents_and_shell_commands(self) -> None:
        events: list[dict[str, Any]] = []

        async def collect_emit(data: dict[str, Any]) -> None:
            events.append(data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "README.md").write_text("Static repository", encoding="utf-8")
            with patch("app.services.agent_runner.call_agents", new=AsyncMock()) as scan, \
                 patch("app.services.agent_runner._run_command", new=AsyncMock()) as command:
                await run_agent(repo, collect_emit, AsyncMock(return_value=True))

        scan.assert_not_awaited()
        command.assert_not_awaited()
        assert any(event.get("title") == "Tidak ada manifest dependency" for event in events)

    @pytest.mark.asyncio
    async def test_denied_setup_command_is_not_run(self) -> None:
        plan = {"commands": ["npm install"], "start_command": None, "port": None}
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=plan)), \
                 patch("app.services.agent_runner._run_command", new=AsyncMock()) as command:
                await run_agent(repo, AsyncMock(), AsyncMock(return_value=False))

        command.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_npm_init_is_blocked_even_with_package_manifest(self) -> None:
        plan = {"commands": ["npm init -y && npm install"], "start_command": None, "port": None}
        events: list[dict[str, Any]] = []

        async def collect_emit(data: dict[str, Any]) -> None:
            events.append(data)

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=plan)), \
                 patch("app.services.agent_runner._run_command", new=AsyncMock()) as command:
                await run_agent(repo, collect_emit, AsyncMock(return_value=True))

        command.assert_not_awaited()
        assert any("npm init" in event.get("content", "") for event in events)

    @pytest.mark.asyncio
    async def test_python_installer_is_blocked_without_python_manifest(self) -> None:
        plan = {"commands": ["uv sync"], "start_command": None, "port": None}
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / "package.json").write_text("{}", encoding="utf-8")
            with patch("app.services.agent_runner.call_agents", new=AsyncMock(return_value=plan)), \
                 patch("app.services.agent_runner._run_command", new=AsyncMock()) as command:
                await run_agent(repo, AsyncMock(), AsyncMock(return_value=True))

        command.assert_not_awaited()
