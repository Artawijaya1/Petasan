from __future__ import annotations

import argparse
import asyncio
from importlib import import_module
import sys
from pathlib import Path
from typing import Any


async def cli_emit(data: dict[str, Any]) -> None:
    """Emit function versi CLI — cetak ke terminal, bukan kirim ke WebSocket."""
    msg_type = data.get("type", "")
    status = data.get("status", "")
    title = data.get("title", "")
    content = data.get("content", "")

    if msg_type == "terminal_log":
        is_error = data.get("isError", False)
        prefix = "[ERROR]" if is_error else ""
        print(f"{prefix} {content}", end="")
    else:
        status_label = f"[{status.upper()}]" if status else ""
        print(f"{status_label} {title}: {content}")


async def request_command_approval(command: str, purpose: str) -> bool:
    print(f"\nAgent meminta izin: {purpose}")
    print(f"Command: {command}")
    while True:
        try:
            answer = await asyncio.to_thread(input, "Setujui command ini? [y/N]: ")
        except (EOFError, KeyboardInterrupt):
            print("\nTidak ada persetujuan; command dibatalkan.")
            return False

        normalized = answer.strip().lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"", "n", "no"}:
            return False
        print("Jawab y untuk menyetujui atau n untuk menolak.")


async def run_cli(repo_path: Path) -> None:
    backend_path = Path(__file__).resolve().parent.parent / "Backend"
    backend_path_text = str(backend_path)
    if backend_path_text not in sys.path:
        sys.path.insert(0, backend_path_text)

    agent_runner = import_module("app.services.agent_runner")
    cleanup_target_processes = agent_runner.cleanup_target_processes
    run_agent = agent_runner.run_agent

    try:
        service_started = await run_agent(
            repo_path=repo_path,
            emit=cli_emit,
            request_approval=request_command_approval,
        )
        if service_started:
            print("\nAplikasi siap. Tekan Ctrl+C untuk menghentikan server dan membersihkan workspace.")
            await asyncio.Event().wait()
    except Exception as exc:
        print(f"[ERROR] Workflow CLI gagal: {exc}")
    finally:
        await cleanup_target_processes()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Zero-Touch Provisioner — CLI mode")
    parser.add_argument("--repo-path", required=True, help="Path folder project di komputer ini")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.is_dir():
        parser.error(f"folder '{repo_path}' tidak ditemukan")

    await run_cli(repo_path)


if __name__ == "__main__":
    asyncio.run(main())