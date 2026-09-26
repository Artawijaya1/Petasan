from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.agent_runner import run_agent

router = APIRouter()


@router.get("/")
def root() -> dict[str, str]:
    return {"message": "Backend Petasan berhasil berjalan!"}


@router.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    async def emit(data: dict[str, Any]) -> None:
        await websocket.send_json(data)

    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict) or data.get("action") != "start":
                await emit({
                    "type": "agent_error",
                    "content": "Pesan tidak valid. Kirim action 'start' untuk menjalankan agent.",
                })
                continue

            repo_path_value = data.get("repo_path", "./my-target-app")
            if not isinstance(repo_path_value, str) or not repo_path_value.strip():
                await emit({
                    "type": "agent_error",
                    "content": "repo_path harus berupa path direktori yang valid.",
                })
                continue

            repo_path = Path(repo_path_value).expanduser().resolve()
            if not repo_path.is_dir():
                await emit({
                    "type": "agent_error",
                    "content": f"Direktori proyek tidak ditemukan: {repo_path}",
                })
                continue

            try:
                await run_agent(repo_path, emit)
            except Exception as exc:
                await emit({
                    "type": "agent_thought",
                    "title": "Agent gagal dijalankan",
                    "content": str(exc),
                    "status": "failed",
                })
    except WebSocketDisconnect:
        return