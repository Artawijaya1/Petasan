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
    failed = False
    failure_detail = ""

    async def emit(data: dict[str, Any]) -> None:
        nonlocal failed, failure_detail
        if data.get("status") == "failed" or data.get("type") == "agent_error":
            failed = True
            failure_detail = str(data.get("content", "Proses agent gagal."))
        await websocket.send_json(data)

    try:
        while True:
            data = await websocket.receive_json()
            failed = False
            failure_detail = ""
            if not isinstance(data, dict) or data.get("action") != "start":
                await emit({
                    "type": "agent_error",
                    "content": "Pesan tidak valid. Kirim action 'start' untuk menjalankan agent.",
                })
                await emit({
                    "type": "agent_complete",
                    "status": "failed",
                    "content": failure_detail,
                })
                continue

            repo_path_value = data.get("repo_path", "./my-target-app")
            if not isinstance(repo_path_value, str) or not repo_path_value.strip():
                await emit({
                    "type": "agent_error",
                    "content": "repo_path harus berupa path direktori yang valid.",
                })
                await emit({
                    "type": "agent_complete",
                    "status": "failed",
                    "content": failure_detail,
                })
                continue

            repo_path = Path(repo_path_value).expanduser().resolve()
            if not repo_path.is_dir():
                await emit({
                    "type": "agent_error",
                    "content": f"Direktori proyek tidak ditemukan: {repo_path}",
                })
                await emit({
                    "type": "agent_complete",
                    "status": "failed",
                    "content": failure_detail,
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
            await emit({
                "type": "agent_complete",
                "status": "failed" if failed else "completed",
                "content": failure_detail or "Provisioning selesai.",
            })
    except WebSocketDisconnect:
        return