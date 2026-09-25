import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIRECTORY = REPOSITORY_ROOT / "Agents"
load_dotenv(AGENTS_DIRECTORY / ".env")

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from Agents.agents.health_agent import check_health
from Agents.agents.healing_agent import diagnose_and_fix
from Agents.agents.parser_agent import scan_repository
from Agents.runner import run_command

app = FastAPI(title="Petasan Backend")


@app.get("/")
def root():
    return {
        "message": "Backend Petasan berhasil berjalan!"
    }


@app.websocket("/ws/agent")
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
                await _run_agent(repo_path, emit)
            except Exception as exc:
                await emit({
                    "type": "agent_thought",
                    "title": "Agent gagal dijalankan",
                    "content": str(exc),
                    "status": "failed",
                })
    except WebSocketDisconnect:
        return


async def _run_agent(
    repo_path: Path,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    await emit({
        "type": "agent_thought",
        "title": "Menganalisis Repositori Proyek",
        "content": f"Memindai struktur berkas di {repo_path}...",
        "status": "in_progress",
    })

    plan = await asyncio.to_thread(scan_repository, str(repo_path))
    if not isinstance(plan, dict):
        raise ValueError("Rencana agent dari parser bukan objek JSON.")

    example_env = repo_path / ".env.example"
    target_env = repo_path / ".env"
    if plan.get("env_needed") and example_env.is_file() and not target_env.exists():
        target_env.write_text(example_env.read_text(encoding="utf-8"), encoding="utf-8")
        await emit({
            "type": "agent_thought",
            "title": "Auto-Generating .env",
            "content": "File .env berhasil dibuat dari .env.example.",
            "status": "completed",
        })

    commands = plan.get("commands", [])
    if not isinstance(commands, list) or any(
        not isinstance(command, str) or not command.strip()
        for command in commands
    ):
        raise ValueError("Daftar commands dari parser tidak valid.")

    for command in commands:
        current_command = command
        succeeded = False

        for attempt in range(1, 4):
            result = await run_command(current_command, emit, cwd=str(repo_path))
            if result["exit_code"] == 0:
                succeeded = True
                break

            if attempt == 3:
                break

            await emit({
                "type": "agent_thought",
                "title": f"Mendeteksi Failure pada '{current_command}'",
                "content": "Error terdeteksi. Mengirim stderr log ke Auto-Healing Agent...",
                "status": "in_progress",
            })
            healing_result = await asyncio.to_thread(
                diagnose_and_fix,
                current_command,
                result["stderr"],
                attempt,
            )
            if not isinstance(healing_result, dict):
                raise ValueError("Respons Auto-Healing Agent bukan objek JSON.")
            current_command = healing_result.get("fix_command", "")
            if not isinstance(current_command, str) or not current_command.strip():
                raise ValueError("Auto-Healing Agent tidak memberikan fix_command yang valid.")

            await emit({
                "type": "agent_thought",
                "title": f"Auto-Healing Strategy: {healing_result.get('thought_title', 'Perbaikan')}",
                "content": healing_result.get("thought_detail", ""),
                "status": "in_progress",
            })

        if not succeeded:
            await emit({
                "type": "agent_thought",
                "title": "Environment belum siap",
                "content": f"Perintah gagal setelah 3 percobaan: {current_command}",
                "status": "failed",
            })
            return

    await emit({
        "type": "agent_thought",
        "title": "Environment Ready!",
        "content": "Semua perintah yang direncanakan berhasil dijalankan.",
        "status": "completed",
    })

    is_healthy = await check_health(
        target_url="http://localhost:3000",
        max_retries=10,
        delay_seconds=2,
        websocket_send_fn=emit,
    )
    await emit({
        "type": "agent_thought",
        "title": "SYSTEM READY FOR DEMO!" if is_healthy else "Health Check Warning",
        "content": (
            "Environment siap digunakan."
            if is_healthy
            else "Perintah berhasil dijalankan, tetapi layanan belum merespons pada port 3000."
        ),
        "status": "completed" if is_healthy else "failed",
    })