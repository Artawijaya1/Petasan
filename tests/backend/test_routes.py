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

    def test_empty_repo_url_returns_agent_error(self, client: TestClient) -> None:
        """URL repository kosong harus mengembalikan agent_error."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "start", "repo_url": "   "})
            data = ws.receive_json()
        assert data["type"] == "agent_error"
        assert "url" in data["content"].lower()

    def test_invalid_repo_url_returns_agent_error(self, client: TestClient) -> None:
        """URL GitHub yang tidak valid harus mengembalikan agent_error."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "start", "repo_url": "not-a-github-url"})
            data = ws.receive_json()
        assert data["type"] == "agent_error"
        assert "url" in data["content"].lower()

    def test_valid_request_calls_run_agent(self, client: TestClient) -> None:
        """Dengan URL valid, backend clone lalu memanggil runner."""
        events: list[dict] = []

        async def fake_clone(repo_url, destination, emit_fn) -> None:
            return None

        async def fake_run_agent(repo_path, emit_fn, request_approval) -> bool:
            await emit_fn({"type": "agent_thought", "title": "Done", "content": "ok", "status": "completed"})
            return False

        with patch("app.api.routes._clone_repository", side_effect=fake_clone), \
             patch("app.api.routes.run_agent", side_effect=fake_run_agent):
            with client.websocket_connect("/ws/agent") as ws:
                ws.send_json({"action": "start", "repo_url": "https://github.com/example/repository"})
                events.append(ws.receive_json())

        assert len(events) >= 1
        assert events[0]["type"] == "agent_thought"

    def test_run_agent_exception_emits_agent_thought_failed(self, client: TestClient) -> None:
        """Jika run_agent throw exception, harus memancarkan agent_thought dengan status failed."""
        async def fake_clone(repo_url, destination, emit_fn) -> None:
            return None

        async def raise_error(repo_path, emit_fn, request_approval) -> bool:
            raise RuntimeError("Unexpected failure")

        with patch("app.api.routes._clone_repository", side_effect=fake_clone), \
             patch("app.api.routes.run_agent", side_effect=raise_error):
            with client.websocket_connect("/ws/agent") as ws:
                ws.send_json({"action": "start", "repo_url": "https://github.com/example/repository"})
                events = []
                while True:
                    data = ws.receive_json()
                    events.append(data)
                    if data.get("type") == "agent_complete":
                        break

        errors = [event for event in events if event.get("type") == "agent_error"]
        assert errors
        assert "Unexpected failure" in errors[0]["content"]

    def test_missing_repo_url_returns_agent_error(self, client: TestClient) -> None:
        """URL GitHub wajib diisi."""
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"action": "start"})
            data = ws.receive_json()
        assert data["type"] == "agent_error"

    def test_approval_response_is_forwarded_to_runner(self, client: TestClient) -> None:
        approvals: list[bool] = []

        async def fake_clone(repo_url, destination, emit_fn) -> None:
            return None

        async def fake_run_agent(repo_path, emit_fn, request_approval) -> bool:
            approvals.append(await request_approval("npm install", "Menjalankan setup"))
            return False

        with patch("app.api.routes._clone_repository", side_effect=fake_clone), \
             patch("app.api.routes.run_agent", side_effect=fake_run_agent):
            with client.websocket_connect("/ws/agent") as ws:
                ws.send_json({"action": "start", "repo_url": "https://github.com/example/repository"})
                while True:
                    event = ws.receive_json()
                    if event.get("type") == "approval_required":
                        assert event["command"] == "npm install"
                        ws.send_json({
                            "action": "approval_response",
                            "request_id": event["request_id"],
                            "approved": True,
                        })
                    elif event.get("type") == "agent_complete":
                        break

        assert approvals == [True]

    def test_rejection_is_forwarded_to_runner(self, client: TestClient) -> None:
        approvals: list[bool] = []

        async def fake_clone(repo_url, destination, emit_fn) -> None:
            return None

        async def fake_run_agent(repo_path, emit_fn, request_approval) -> bool:
            approvals.append(await request_approval("npm install", "Menjalankan setup"))
            return False

        with patch("app.api.routes._clone_repository", side_effect=fake_clone), \
             patch("app.api.routes.run_agent", side_effect=fake_run_agent):
            with client.websocket_connect("/ws/agent") as ws:
                ws.send_json({"action": "start", "repo_url": "https://github.com/example/repository"})
                while True:
                    event = ws.receive_json()
                    if event.get("type") == "approval_required":
                        ws.send_json({
                            "action": "approval_response",
                            "request_id": event["request_id"],
                            "approved": False,
                        })
                    elif event.get("type") == "agent_complete":
                        assert event["service_started"] is False
                        break

        assert approvals == [False]
