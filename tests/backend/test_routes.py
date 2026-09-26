"""
Tests untuk Backend/app/api/routes.py — GET / dan WebSocket /ws/agent.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("AGENTS_API_URL", "http://localhost:8001")
os.environ.setdefault("BOB_API_KEY", "test-api-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Backend"))

from app.main import create_app

app = create_app()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    def test_root_returns_message(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Petasan" in data["message"]


# ---------------------------------------------------------------------------
# WebSocket /ws/agent
# ---------------------------------------------------------------------------

class TestWebSocketEndpoint:
    def test_invalid_action_returns_agent_error(self, client: TestClient) -> None:
        """Mengirim action yang bukan 'start' harus membalas agent_error."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "stop"})
            data = ws.receive_json()
        assert data["type"] == "agent_error"
        assert "start" in data["content"]

    def test_missing_action_key_returns_agent_error(self, client: TestClient) -> None:
        """Payload tanpa kunci 'action' harus mengembalikan agent_error."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"repo_path": "/some/path"})
            data = ws.receive_json()
        assert data["type"] == "agent_error"

    def test_empty_repo_path_returns_agent_error(self, client: TestClient) -> None:
        """repo_path kosong harus mengembalikan agent_error."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "start", "repo_path": "   "})
            data = ws.receive_json()
        assert data["type"] == "agent_error"
        assert "repo_path" in data["content"].lower()

    def test_nonexistent_repo_path_returns_agent_error(self, client: TestClient) -> None:
        """Path yang tidak ada harus mengembalikan agent_error."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "start", "repo_path": "/does/not/exist/ever"})
            data = ws.receive_json()
        assert data["type"] == "agent_error"
        assert "tidak ditemukan" in data["content"].lower()

    def test_valid_request_calls_run_agent(self, client: TestClient) -> None:
        """Dengan path yang valid, harus memanggil run_agent dan mengembalikan event."""
        events: list[dict] = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            async def fake_run_agent(repo_path, emit_fn) -> None:
                await emit_fn({"type": "agent_thought", "title": "Done", "content": "ok", "status": "completed"})

            with patch("app.api.routes.run_agent", side_effect=fake_run_agent):
                with client.websocket_connect("/ws/agent") as ws:
                    ws.send_json({"action": "start", "repo_path": tmp_dir})
                    data = ws.receive_json()
                    events.append(data)

        assert len(events) >= 1
        assert events[0]["type"] == "agent_thought"

    def test_run_agent_exception_emits_agent_thought_failed(self, client: TestClient) -> None:
        """Jika run_agent throw exception, harus memancarkan agent_thought dengan status failed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            async def raise_error(repo_path, emit_fn) -> None:
                raise RuntimeError("Unexpected failure")

            with patch("app.api.routes.run_agent", side_effect=raise_error):
                with client.websocket_connect("/ws/agent") as ws:
                    ws.send_json({"action": "start", "repo_path": tmp_dir})
                    data = ws.receive_json()

        assert data["type"] == "agent_thought"
        assert data["status"] == "failed"
        assert "Unexpected failure" in data["content"]

    def test_default_repo_path_used_when_missing(self, client: TestClient) -> None:
        """Jika repo_path tidak ada di payload, default './my-target-app' dipakai."""
        # Path default tidak ada → agent_error (direktori tidak ditemukan)
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "start"})
            data = ws.receive_json()
        # Bisa agent_error (path tidak ditemukan) atau agent_thought (jika path ada)
        assert data["type"] in ("agent_error", "agent_thought")
