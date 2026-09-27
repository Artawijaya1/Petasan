from __future__ import annotations

import argparse
import asyncio
import sys
from importlib import import_module
from pathlib import Path
from typing import Any


async def cli_emit(data: dict[str, Any]) -> None:
    """CLI emit function — print to terminal instead of sending via WebSocket."""
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
    print(f"\nAgent is requesting permission: {purpose}")
    print(f"Command: {command}")
    while True:
        try:
            answer = await asyncio.to_thread(input, "Approve this command? [y/N]: ")
        except (EOFError, KeyboardInterrupt):
            print("\nNo approval given; command cancelled.")
            return False

        normalized = answer.strip().lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"", "n", "no"}:
            return False
        print("Answer y to approve or n to deny.")


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
            print("\nApplication is ready. Press Ctrl+C to stop the server.")
            print("(Project folder will NOT be deleted — this is your original local folder.)")
            await asyncio.Event().wait()
    except Exception as exc:
        print(f"[ERROR] CLI workflow failed: {exc}")
    finally:
        await cleanup_target_processes(cleanup_workspace=False)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Zero-Touch Provisioner — CLI mode (local)")
    parser.add_argument("--repo-path", required=True, help="Path to the project folder on this computer")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.is_dir():
        parser.error(f"folder '{repo_path}' not found")

    await run_cli(repo_path)


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()