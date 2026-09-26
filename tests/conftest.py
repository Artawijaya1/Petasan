"""
Shared fixtures for the entire test suite.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Tambahkan Agents & Backend ke sys.path agar modul-modulnya bisa di-import
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "Agents"
BACKEND_DIR = REPO_ROOT / "Backend"

for _path in (str(AGENTS_DIR), str(BACKEND_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# ---------------------------------------------------------------------------
# Set env vars minimal sebelum apapun di-import (hindari RuntimeError)
# ---------------------------------------------------------------------------
os.environ.setdefault("BOB_API_KEY", "test-api-key")
os.environ.setdefault("AGENT_SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("AGENTS_API_URL", "http://localhost:8001")


# ---------------------------------------------------------------------------
# Fixtures umum
# ---------------------------------------------------------------------------

@pytest.fixture()
def emit_mock() -> AsyncMock:
    """Mock untuk websocket_send_fn / emit yang menerima dict."""
    return AsyncMock()


@pytest.fixture()
def sample_files() -> dict[str, str]:
    """Contoh payload files untuk /v1/scan."""
    return {
        "package.json": '{"name": "my-app", "scripts": {"dev": "next dev"}}',
        "requirements.txt": "fastapi\nuvicorn\n",
    }


@pytest.fixture()
def sample_healing_payload() -> dict:
    """Contoh payload untuk /v1/heal."""
    return {
        "command_failed": "npm install",
        "stderr_log": "npm ERR! Cannot find module 'some-pkg'",
        "attempt": 1,
    }


@pytest.fixture()
def valid_healing_response() -> dict:
    """Contoh respons valid dari healing agent."""
    return {
        "thought_title": "Dependency hilang",
        "thought_detail": "Package tidak ditemukan di registry npm.",
        "fix_command": "npm install --legacy-peer-deps",
    }


@pytest.fixture()
def valid_scan_response() -> dict:
    """Contoh respons valid dari parser agent."""
    return {
        "env_needed": False,
        "commands": ["npm install", "npm run dev"],
    }
