import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from .agents_client import call_agents

FILES_TO_SCAN = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "environment.yml",
    "Dockerfile",
    "docker-compose.yml",
    "compose.yml",
    "compose.yaml",
    "README.md",
)
PYTHON_MANIFESTS = ("requirements.txt", "pyproject.toml", "Pipfile", "environment.yml")
DOCKER_MANIFESTS = ("Dockerfile", "docker-compose.yml", "compose.yml", "compose.yaml")
NODE_COMMAND_PATTERN = re.compile(r"(?:^|[\s;&|])(?:npm|npx|pnpm|yarn|bun)(?:\.cmd)?(?:\s|$)", re.IGNORECASE)
NPM_INIT_PATTERN = re.compile(r"(?:^|[\s;&|])npm(?:\.cmd)?\s+init(?:\s|$)", re.IGNORECASE)
PYTHON_INSTALL_PATTERN = re.compile(r"(?:^|[\s;&|])(?:pip(?:\d+(?:\.\d+)*)?|(?:python|py)(?:\d+(?:\.\d+)*)?(?:\.exe)?\s+-m\s+pip|uv(?:\s+pip)?\s+(?:sync|install|add)|poetry\s+(?:install|add)|conda\s+(?:install|env\s+(?:create|update)))(?:\s|$)", re.IGNORECASE)
DOCKER_COMMAND_PATTERN = re.compile(r"(?:^|[\s;&|])docker(?:\.exe)?(?:\s|$)", re.IGNORECASE)
START_SCRIPT_PATTERN = re.compile(r"\b(?:run\s+(?:dev|start|serve)|start|serve)\b", re.IGNORECASE)


@dataclass
class TargetRuntime:
    process: subprocess.Popen[str]
    workspace: Path
    output_task: asyncio.Task[None]


_ACTIVE_TARGETS: dict[int, TargetRuntime] = {}
_RETAINED_WORKSPACES: set[Path] = set()


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


def _run_shell_command(command: str, cwd: str) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


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

    result = await asyncio.to_thread(_run_shell_command, command, cwd)
    stdout = result["stdout"]
    stderr = result["stderr"]

    if stdout:
        await emit({"type": "terminal_log", "content": stdout, "isError": False})
    if stderr:
        await emit({"type": "terminal_log", "content": stderr, "isError": True})

    return result

async def _check_target_health(
    target_url: str,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
    max_retries: int = 10,
    delay_seconds: int = 2,
    process: subprocess.Popen[str] | None = None,
) -> bool:
    await emit({
        "type": "agent_thought",
        "title": "Application Health Check",
        "content": f"Checking the local server at {target_url}...",
        "status": "in_progress",
    })

    async with httpx.AsyncClient(timeout=3.0) as client:
        for attempt in range(1, max_retries + 1):
            if process is not None and process.poll() is not None:
                error = f"The server process exited with code {process.returncode}"
                await emit({
                    "type": "terminal_log",
                    "content": f"[Health Check] {error}\n",
                    "isError": True,
                })
                break
            try:
                response = await client.get(target_url)
                if 200 <= response.status_code < 400:
                    await emit({
                        "type": "agent_thought",
                        "title": "Health Check Passed!",
                        "content": f"The service responded with HTTP {response.status_code}.",
                        "status": "completed",
                    })
                    return True
                error = f"HTTP {response.status_code}"
            except httpx.HTTPError as exc:
                error = str(exc) or "Connection refused"

            await emit({
                "type": "terminal_log",
                "content": f"[Health Check] Attempt {attempt}/{max_retries}: {error}\n",
                "isError": False,
            })
            if attempt < max_retries:
                await asyncio.sleep(delay_seconds)

    await emit({
        "type": "agent_thought",
        "title": "Health Check Warning",
        "content": f"The server did not respond at {target_url} after {max_retries} attempts.",
        "status": "completed",
    })
    return False


async def _stream_target_output(
    process: subprocess.Popen[str],
    emit: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    if process.stdout is None:
        return
    while line := await asyncio.to_thread(process.stdout.readline):
        try:
            await emit({"type": "terminal_log", "content": line, "isError": False})
        except Exception:
            continue


async def _stop_target_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        await asyncio.to_thread(
            subprocess.run,
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
    try:
        await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=5)
    except asyncio.TimeoutError:
        process.kill()
        await asyncio.to_thread(process.wait)


async def _start_target_service(
    command: str,
    port: int,
    repo_path: Path,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
) -> bool:
    target_url = f"http://127.0.0.1:{port}"
    with socket.socket() as port_probe:
        try:
            port_probe.bind(("127.0.0.1", port))
        except OSError:
            await emit({
                "type": "agent_thought",
                "title": "Application port is already in use",
                "content": f"Port {port} is occupied. The new server was not started to avoid checking the health of a different service.",
                "status": "failed",
            })
            return False

    await emit({
        "type": "agent_thought",
        "title": "Starting application",
        "content": f"Running the approved command at {target_url}...",
        "status": "in_progress",
    })
    process = await asyncio.to_thread(
        subprocess.Popen,
        command,
        cwd=str(repo_path),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    output_task = asyncio.create_task(_stream_target_output(process, emit))
    healthy = await _check_target_health(target_url, emit, process=process)
    if healthy and process.poll() is None:
        workspace = repo_path.parent.resolve()
        _ACTIVE_TARGETS[process.pid] = TargetRuntime(process, workspace, output_task)
        _RETAINED_WORKSPACES.add(workspace)
        await emit({
            "type": "agent_thought",
            "title": "Application ready",
            "content": f"The application is responding at {target_url}.",
            "status": "completed",
        })
        return True

    await _stop_target_process(process)
    await output_task
    await emit({
        "type": "agent_thought",
        "title": "Application is not ready",
        "content": f"The server did not respond at {target_url}. Check the command and logs above.",
        "status": "failed",
    })
    return False


async def cleanup_target_processes(cleanup_workspace: bool = True) -> None:
    for runtime in list(_ACTIVE_TARGETS.values()):
        await _stop_target_process(runtime.process)
        if not runtime.output_task.done():
            await runtime.output_task
        if cleanup_workspace:
            shutil.rmtree(runtime.workspace, ignore_errors=True)
    _ACTIVE_TARGETS.clear()
    _RETAINED_WORKSPACES.clear()


def is_workspace_retained(workspace: Path) -> bool:
    return workspace.resolve() in _RETAINED_WORKSPACES


def _command_matches_manifest(command: str, node: bool, python: bool, docker: bool) -> bool:
    if NPM_INIT_PATTERN.search(command):
        return False
    if NODE_COMMAND_PATTERN.search(command) and not node:
        return False
    if PYTHON_INSTALL_PATTERN.search(command) and not python:
        return False
    if DOCKER_COMMAND_PATTERN.search(command) and not docker:
        return False
    return True


def _infer_start_settings(plan: dict[str, Any], repo_path: Path) -> tuple[str | None, int | None]:
    start_command = plan.get("start_command")
    port = plan.get("port")
    package_file = repo_path / "package.json"

    package_data: dict[str, Any] = {}
    if package_file.is_file():
        try:
            package_data = json.loads(package_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            package_data = {}

    scripts = package_data.get("scripts", {})
    scripts = scripts if isinstance(scripts, dict) else {}
    start_script = next(
        (name for name in ("dev", "start", "serve") if isinstance(scripts.get(name), str)),
        None,
    )

    if not start_command and start_script:
        start_command = f"npm run {start_script}"

    if start_command and not isinstance(start_command, str):
        raise ValueError("Agent start_command must be a string or null.")

    if isinstance(port, str) and port.isdigit():
        port = int(port)
    if port is None and start_command:
        script_text = str(scripts.get(start_script, "")) if start_script else ""
        port_match = re.search(r"(?:--port(?:=|\s+)|PORT=)(\d{2,5})", f"{start_command} {script_text}")
        if port_match:
            port = int(port_match.group(1))
        elif "vite" in script_text.lower() or "vite" in start_command.lower():
            port = 5173
        elif "next" in script_text.lower() or "next" in start_command.lower():
            port = 3000

    if start_command and port is None:
        raise ValueError("Server port could not be detected. The agent must provide a valid port.")
    if port is not None and (
        not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535
    ):
        raise ValueError("The server port returned by the agent is invalid.")
    return start_command, port


async def run_agent(
    repo_path: Path,
    emit: Callable[[dict[str, Any]], Awaitable[None]],
    request_approval: Callable[[str, str], Awaitable[bool]] | None = None,
) -> bool:
    await emit({
        "type": "agent_thought",
        "title": "Checking repository environment",
        "content": "Checking dependency manifests before planning installation...",
        "status": "in_progress",
    })

    repository_files = await asyncio.to_thread(_read_repository_files, repo_path)
    node_manifest = (repo_path / "package.json").is_file()
    python_manifest = any((repo_path / name).is_file() for name in PYTHON_MANIFESTS)
    docker_manifest = any((repo_path / name).is_file() for name in DOCKER_MANIFESTS)

    env_templates = [
        name for name in (".env.example", ".env.sample", ".env.template")
        if (repo_path / name).is_file()
    ]
    if env_templates:
        env_exists = (repo_path / ".env").is_file()
        await emit({
            "type": "agent_thought",
            "title": ".env file available" if env_exists else "Review .env template",
            "content": (
                f"Found template(s): {', '.join(env_templates)}. File values were not read; .env was not created automatically."
                if not env_exists
                else f"Found template(s): {', '.join(env_templates)} and an existing .env file. File values were not read."
            ),
            "status": "completed",
        })
    elif (repo_path / ".env").is_file():
        await emit({
            "type": "agent_thought",
            "title": ".env file available",
            "content": "An .env file was found. Its contents were not read or sent to the model.",
            "status": "completed",
        })

    if not (node_manifest or python_manifest or docker_manifest):
        await emit({
            "type": "agent_thought",
            "title": "No dependency manifest found",
            "content": "This repository has no package.json, Python, or Docker manifest. No installation commands were run.",
            "status": "completed",
        })
        return False

    plan = await call_agents("/v1/scan", {"files": repository_files})
    if not isinstance(plan, dict):
        raise ValueError("The parser agent plan is not a JSON object.")

    commands = plan.get("commands", [])
    if not isinstance(commands, list) or any(
        not isinstance(command, str) or not command.strip()
        for command in commands
    ):
        raise ValueError("The commands returned by the parser are invalid.")

    start_command, port = _infer_start_settings(plan, repo_path)
    setup_commands: list[str] = []
    for command in commands:
        if not _command_matches_manifest(command, node_manifest, python_manifest, docker_manifest):
            await emit({
                "type": "terminal_log",
                "content": f"Command rejected: it does not match the manifest or would create a new manifest: {command}\n",
                "isError": True,
            })
            continue
        if NODE_COMMAND_PATTERN.search(command) and START_SCRIPT_PATTERN.search(command):
            if start_command is None:
                start_command = command
            continue
        setup_commands.append(command)

    async def approve(command: str, purpose: str) -> bool:
        if request_approval is None:
            return False
        return await request_approval(command, purpose)

    async def report_denial(command: str) -> None:
        await emit({
            "type": "agent_thought",
            "title": "Command not run",
            "content": f"Approval was not granted for: {command}",
            "status": "completed",
        })

    if not setup_commands and start_command is None:
        await emit({
            "type": "agent_thought",
            "title": "Environment check complete",
            "content": "The project does not define any installation or server commands.",
            "status": "completed",
        })
        return False

    for command in setup_commands:
        current_command = command
        succeeded = False

        for attempt in range(1, 4):
            purpose = "Run setup command" if attempt == 1 else "Run repair command"
            if not await approve(current_command, purpose):
                await report_denial(current_command)
                return False

            result = await _run_command(current_command, emit, cwd=str(repo_path))
            if result["exit_code"] == 0:
                succeeded = True
                break

            if attempt == 3:
                break

            await emit({
                "type": "agent_thought",
                "title": f"Failure detected for '{current_command}'",
                "content": "An error was detected. Sending stderr logs to the Auto-Healing agent...",
                "status": "in_progress",
            })
            healing_result = await call_agents(
                "/v1/heal",
                {
                    "command_failed": current_command,
                    "stderr_log": result["stderr"],
                    "attempt": attempt,
                },
            )
            if not isinstance(healing_result, dict):
                raise ValueError("The Auto-Healing agent response is not a JSON object.")
            current_command = healing_result.get("fix_command", "")
            if not isinstance(current_command, str) or not current_command.strip():
                raise ValueError("The Auto-Healing agent did not provide a valid fix_command.")
            if not _command_matches_manifest(current_command, node_manifest, python_manifest, docker_manifest):
                await emit({
                    "type": "terminal_log",
                    "content": f"Repair command rejected: it does not match the manifest or would create a new manifest: {current_command}\n",
                    "isError": True,
                })
                return False

            await emit({
                "type": "agent_thought",
                "title": f"Auto-Healing Strategy: {healing_result.get('thought_title', 'Repair')}",
                "content": healing_result.get("thought_detail", ""),
                "status": "in_progress",
            })

        if not succeeded:
            await emit({
                "type": "agent_thought",
                "title": "Environment is not ready",
                "content": f"The command failed after 3 attempts: {current_command}",
                "status": "failed",
            })
            return False

    if start_command is None:
        await emit({
            "type": "agent_thought",
            "title": "Environment setup complete",
            "content": "Setup is complete; the project does not define an application server to start.",
            "status": "completed",
        })
        return False

    if port is None:
        raise ValueError("Application port was not found. The agent must select the port from the project configuration.")
    if not _command_matches_manifest(start_command, node_manifest, python_manifest, docker_manifest):
        await emit({
            "type": "terminal_log",
            "content": f"Start command rejected because it does not match the manifest: {start_command}\n",
            "isError": True,
        })
        return False
    if not await approve(start_command, "Start application server"):
        await report_denial(start_command)
        return False

    is_healthy = await _start_target_service(start_command, port, repo_path, emit)
    if is_healthy:
        await emit({
            "type": "agent_thought",
            "title": "Environment Ready!",
            "content": f"The application is running and responding at http://127.0.0.1:{port}.",
            "status": "completed",
        })
    return is_healthy