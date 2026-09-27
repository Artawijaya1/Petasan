import asyncio
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.agent_runner import is_workspace_retained, run_agent

router = APIRouter()
GITHUB_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def _normalize_github_url(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter a GitHub repository URL.")

    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid GitHub URL.") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an HTTPS repository URL from github.com.")

    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        raise ValueError("URL must use the format https://github.com/owner/repository.")

    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if (
        not GITHUB_NAME_PATTERN.fullmatch(owner)
        or not GITHUB_NAME_PATTERN.fullmatch(repository)
        or owner in {".", ".."}
        or repository in {".", ".."}
    ):
        raise ValueError("GitHub owner or repository name is invalid.")

    return f"https://github.com/{owner}/{repository}.git"


def _run_git_clone(repo_url: str, destination: Path) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--", repo_url, str(destination)],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Git was not found on the Backend host.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Cloning the repository exceeded the 120-second timeout.") from exc

    return result.returncode, result.stdout.strip(), result.stderr.strip()


async def _clone_repository(
    repo_url: str,
    destination: Path,
    emit: Any,
) -> None:
    await emit({
        "type": "agent_thought",
        "title": "Downloading GitHub repository",
        "content": f"Cloning {repo_url} into a temporary workspace...",
        "status": "in_progress",
    })

    exit_code, stdout, stderr = await asyncio.to_thread(
        _run_git_clone,
        repo_url,
        destination,
    )
    if stdout:
        await emit({"type": "terminal_log", "content": f"{stdout}\n", "isError": False})
    if stderr:
        await emit({"type": "terminal_log", "content": f"{stderr}\n", "isError": exit_code != 0})
    if exit_code != 0:
        detail = stderr or stdout or "git clone failed."
        raise RuntimeError(f"Failed to clone repository: {detail[-1500:]}")

    await emit({
        "type": "agent_thought",
        "title": "Repository downloaded",
        "content": "The repository is ready for analysis.",
        "status": "completed",
    })


@router.get("/")
def root() -> dict[str, str]:
    return {"message": "Petasan Backend is running!"}


@router.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    failed = False
    failure_detail = ""

    async def emit(data: dict[str, Any]) -> None:
        nonlocal failed, failure_detail
        if data.get("status") == "failed" or data.get("type") == "agent_error":
            failed = True
            failure_detail = str(data.get("content", "The agent process failed."))
        await websocket.send_json(data)

    try:
        while True:
            data = await websocket.receive_json()
            failed = False
            failure_detail = ""
            if not isinstance(data, dict) or data.get("action") != "start":
                await emit({
                    "type": "agent_error",
                    "content": "Invalid message. Send the 'start' action to run the agent.",
                })
                await emit({
                    "type": "agent_complete",
                    "status": "failed",
                    "content": failure_detail,
                })
                continue

            try:
                repo_url = _normalize_github_url(data.get("repo_url"))
            except ValueError as exc:
                await emit({
                    "type": "agent_error",
                    "content": str(exc),
                })
                await emit({
                    "type": "agent_complete",
                    "status": "failed",
                    "content": failure_detail,
                })
                continue

            workspace = Path(tempfile.mkdtemp(prefix="petasan-"))
            service_started = False
            try:
                repo_path = workspace / "repository"
                await _clone_repository(repo_url, repo_path, emit)

                async def request_approval(command: str, purpose: str) -> bool:
                    request_id = uuid.uuid4().hex
                    await emit({
                        "type": "approval_required",
                        "request_id": request_id,
                        "command": command,
                        "reason": purpose,
                    })
                    while True:
                        response = await websocket.receive_json()
                        if (
                            isinstance(response, dict)
                            and response.get("action") == "approval_response"
                            and response.get("request_id") == request_id
                            and isinstance(response.get("approved"), bool)
                        ):
                            return response["approved"]
                        await emit({
                            "type": "terminal_log",
                            "content": "Invalid approval response; use the Approve or Reject button.\n",
                            "isError": True,
                        })

                service_started = await run_agent(repo_path, emit, request_approval)
            except Exception as exc:
                if isinstance(exc, WebSocketDisconnect):
                    raise
                detail = str(exc).strip() or f"{type(exc).__name__} (tanpa detail tambahan)."
                await emit({
                    "type": "terminal_log",
                    "content": f"[Backend error] {detail}\n",
                    "isError": True,
                })
                await emit({"type": "agent_error", "content": detail})
            finally:
                if not is_workspace_retained(workspace):
                    shutil.rmtree(workspace, ignore_errors=True)
            await emit({
                "type": "agent_complete",
                "status": "failed" if failed else "completed",
                "service_started": service_started,
                "content": failure_detail or (
                    "The process failed. Check the error details above."
                    if failed
                    else (
                        "The environment is ready and the application is running."
                        if service_started
                        else "Environment checks are complete; no application was started."
                    )
                ),
            })
    except WebSocketDisconnect:
        return