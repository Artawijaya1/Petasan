from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv
load_dotenv() #Update disini
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

AGENTS_DIRECTORY = Path(__file__).resolve().parent
load_dotenv(AGENTS_DIRECTORY / ".env")

if not os.environ.get("GEMINI_API_KEY"):
    raise RuntimeError(
        f"GEMINI_API_KEY tidak ditemukan. Isi {AGENTS_DIRECTORY / '.env'} "
        "atau set environment variable GEMINI_API_KEY."
    )

if str(AGENTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(AGENTS_DIRECTORY))

from agents.healing_agent import diagnose_and_fix
from agents.parser_agent import create_installation_plan

app = FastAPI(title="Petasan Agents API")
bearer_scheme = HTTPBearer(auto_error=False)


class ScanRequest(BaseModel):
    files: dict[str, str]


class HealingRequest(BaseModel):
    command_failed: str
    stderr_log: str
    attempt: int = Field(ge=1, le=3)


async def require_service_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> None:
    expected_token = os.environ.get("AGENT_SERVICE_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AGENT_SERVICE_TOKEN belum dikonfigurasi.",
        )

    if credentials is None or not hmac.compare_digest(
        credentials.credentials,
        expected_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service token tidak valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agents"}


@app.post("/v1/scan", dependencies=[Depends(require_service_token)])
async def scan(request: ScanRequest) -> dict[str, Any]:
    try:
        return await create_installation_plan(request.files)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/v1/heal", dependencies=[Depends(require_service_token)])
async def heal(request: HealingRequest) -> dict[str, Any]:
    result = await diagnose_and_fix(
        request.command_failed,
        request.stderr_log,
        request.attempt,
    )
    if result is None:
        raise HTTPException(
            status_code=502,
            detail="Agents tidak dapat menghasilkan diagnosis perbaikan.",
        )
    return result