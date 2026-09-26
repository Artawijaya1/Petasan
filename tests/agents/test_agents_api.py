"""
Tests untuk Agents/main.py — FastAPI endpoints: /health, /v1/scan, /v1/heal.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Pastikan env vars terset sebelum import modul
os.environ.setdefault("BOB_API_KEY", "test-api-key")
os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-service-token")

# Mock sentence_transformers sebelum rantai import healing_agent → vector_store
from unittest.mock import MagicMock as _MagicMock
sys.modules.setdefault("sentence_transformers", _MagicMock())

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Agents"))

# Import app setelah env vars terset
# Agents/main.py bukan sub-package agents, tapi file main.py di root Agents/
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "agents_main_module",
    Path(__file__).resolve().parents[2] / "Agents" / "main.py",
)
agents_main = _ilu.module_from_spec(_spec)
# Daftarkan ke sys.modules agar patch("agents_main_module.xxx") bisa menemukan modul ini
sys.modules["agents_main_module"] = agents_main
_spec.loader.exec_module(agents_main)  # type: ignore[union-attr]
app = agents_main.app

VALID_TOKEN = "test-service-token"
HEADERS = {"Authorization": f"Bearer {VALID_TOKEN}"}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "agents"


# ---------------------------------------------------------------------------
# POST /v1/scan — auth
# ---------------------------------------------------------------------------

class TestScanAuthMiddleware:
    def test_missing_token_returns_401_or_503(self, client: TestClient) -> None:
        response = client.post("/v1/scan", json={"files": {}})
        assert response.status_code in (401, 503)

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/v1/scan",
            json={"files": {}},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    def test_no_authorization_header_returns_401(self, client: TestClient) -> None:
        response = client.post("/v1/scan", json={"files": {}})
        assert response.status_code in (401, 503)


# ---------------------------------------------------------------------------
# POST /v1/scan — valid request
# ---------------------------------------------------------------------------

class TestScanEndpoint:
    def test_valid_scan_returns_plan(self, client: TestClient) -> None:
        plan = {"env_needed": False, "commands": ["npm install"]}

        with patch("agents_main_module.create_installation_plan", new=AsyncMock(return_value=plan)):
            response = client.post(
                "/v1/scan",
                json={"files": {"package.json": '{"name": "app"}'}},
                headers=HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["commands"] == ["npm install"]

    def test_scan_propagates_502_on_runtime_error(self, client: TestClient) -> None:
        with patch(
            "agents_main_module.create_installation_plan",
            new=AsyncMock(side_effect=RuntimeError("Bob API down")),
        ):
            response = client.post(
                "/v1/scan",
                json={"files": {}},
                headers=HEADERS,
            )

        assert response.status_code == 502
        assert "Bob API down" in response.json()["detail"]

    def test_scan_accepts_empty_files(self, client: TestClient) -> None:
        plan = {"env_needed": False, "commands": []}

        with patch("agents_main_module.create_installation_plan", new=AsyncMock(return_value=plan)):
            response = client.post(
                "/v1/scan",
                json={"files": {}},
                headers=HEADERS,
            )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /v1/heal — auth
# ---------------------------------------------------------------------------

class TestHealAuthMiddleware:
    def test_missing_token_returns_401_or_503(self, client: TestClient) -> None:
        payload = {"command_failed": "npm install", "stderr_log": "err", "attempt": 1}
        response = client.post("/v1/heal", json=payload)
        assert response.status_code in (401, 503)


# ---------------------------------------------------------------------------
# POST /v1/heal — valid request
# ---------------------------------------------------------------------------

class TestHealEndpoint:
    def test_valid_heal_returns_diagnosis(self, client: TestClient) -> None:
        diagnosis = {
            "thought_title": "Module hilang",
            "thought_detail": "Dependency belum terinstall.",
            "fix_command": "npm install --legacy-peer-deps",
        }

        with patch("agents_main_module.diagnose_and_fix", new=AsyncMock(return_value=diagnosis)):
            response = client.post(
                "/v1/heal",
                json={"command_failed": "npm install", "stderr_log": "error", "attempt": 1},
                headers=HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["fix_command"] == "npm install --legacy-peer-deps"

    def test_heal_returns_502_when_agent_returns_none(self, client: TestClient) -> None:
        with patch("agents_main_module.diagnose_and_fix", new=AsyncMock(return_value=None)):
            response = client.post(
                "/v1/heal",
                json={"command_failed": "npm run dev", "stderr_log": "timeout", "attempt": 2},
                headers=HEADERS,
            )

        assert response.status_code == 502

    def test_heal_attempt_validation_min(self, client: TestClient) -> None:
        """attempt < 1 harus ditolak dengan 422."""
        with patch("agents_main_module.diagnose_and_fix", new=AsyncMock(return_value=None)):
            response = client.post(
                "/v1/heal",
                json={"command_failed": "cmd", "stderr_log": "err", "attempt": 0},
                headers=HEADERS,
            )
        assert response.status_code == 422

    def test_heal_attempt_validation_max(self, client: TestClient) -> None:
        """attempt > 3 harus ditolak dengan 422."""
        with patch("agents_main_module.diagnose_and_fix", new=AsyncMock(return_value=None)):
            response = client.post(
                "/v1/heal",
                json={"command_failed": "cmd", "stderr_log": "err", "attempt": 4},
                headers=HEADERS,
            )
        assert response.status_code == 422

    @pytest.mark.parametrize("attempt", [1, 2, 3])
    def test_heal_valid_attempts(self, client: TestClient, attempt: int) -> None:
        """attempt 1, 2, 3 semuanya valid."""
        diagnosis = {"thought_title": "T", "thought_detail": "D", "fix_command": "npm install"}
        with patch("agents_main_module.diagnose_and_fix", new=AsyncMock(return_value=diagnosis)):
            response = client.post(
                "/v1/heal",
                json={"command_failed": "cmd", "stderr_log": "err", "attempt": attempt},
                headers=HEADERS,
            )
        assert response.status_code == 200
