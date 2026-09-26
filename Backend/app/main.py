import asyncio
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIRECTORY / ".env")

AGENTS_API_URL = os.environ.get("AGENTS_API_URL", "http://127.0.0.1:8001").rstrip("/")
FILES_TO_SCAN = (
    "package.json",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    ".env.example",
    "README.md",
)

app = FastAPI(title="Petasan Backend")


@app.get("/")
def root():
    return {
        "message": "Backend Petasan berhasil berjalan!"
    }

async def _call_agents(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    service_token = os.environ.get("AGENT_SERVICE_TOKEN")
    if not service_token:
        raise RuntimeError("AGENT_SERVICE_TOKEN belum dikonfigurasi di Backend.")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{AGENTS_API_URL}{endpoint}",
                json=payload,
                headers={"Authorization": f"Bearer {service_token}"},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        raise RuntimeError(
            f"Agents API mengembalikan HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Tidak dapat menghubungi Agents API: {exc}") from exc

    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Respons Agents API harus berupa objek JSON.")
    return result


def _read_repository_files(repo_path: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for file_name in FILES_TO_SCAN:
        file_path = repo_path / file_name
        try:
            if file_path.is_file():
                files[file_name] = file_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )[:2000]
        except OSError:
            continue
    return files


async def _run_command(
    command: str,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
    cwd: str,
) -> dict[str, Any]:
    await emit({
        "type": "terminal_log",
        "content": f"$ {command}\n",
        "isError": False,
    })

    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if stdout:
        await emit({"type": "terminal_log", "content": stdout, "isError": False})
    if stderr:
        await emit({"type": "terminal_log", "content": stderr, "isError": True})

    return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}


async def _check_target_health(
    target_url: str,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
    max_retries: int = 10,
    delay_seconds: int = 2,
) -> bool:
    await emit({
        "type": "agent_thought",
        "title": "Verifikasi Layanan (Health Check)",
        "content": f"Memverifikasi status server lokal di {target_url}...",
        "status": "in_progress",
    })

    async with httpx.AsyncClient(timeout=3.0) as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.get(target_url)
                if 200 <= response.status_code < 400:
                    await emit({
                        "type": "agent_thought",
                        "title": "Health Check Passed!",
                        "content": f"Layanan merespons dengan HTTP {response.status_code}.",
                        "status": "completed",
                    })
                    return True
                error = f"HTTP {response.status_code}"
            except httpx.HTTPError as exc:
                error = str(exc) or "Connection refused"

            await emit({
                "type": "terminal_log",
                "content": f"[Health Check] Percobaan {attempt}/{max_retries}: {error}\n",
                "isError": False,
            })
            if attempt < max_retries:
                await asyncio.sleep(delay_seconds)

    await emit({
        "type": "agent_thought",
        "title": "Health Check Warning",
        "content": f"Server tidak merespons di {target_url} setelah {max_retries} percobaan.",
        "status": "completed",
    })
    return False


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

    repository_files = await asyncio.to_thread(_read_repository_files, repo_path)
    plan = await _call_agents("/v1/scan", {"files": repository_files})
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
            result = await _run_command(current_command, emit, cwd=str(repo_path))
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
            healing_result = await _call_agents(
                "/v1/heal",
                {
                    "command_failed": current_command,
                    "stderr_log": result["stderr"],
                    "attempt": attempt,
                },
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

    is_healthy = await _check_target_health(
        target_url="http://localhost:3000",
        emit=emit,
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