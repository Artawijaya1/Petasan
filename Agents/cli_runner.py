from __future__ import annotations

import argparse
import asyncio
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


async def main() -> None:
    parser = argparse.ArgumentParser(description="Zero-Touch Provisioner — CLI mode")
    parser.add_argument("--repo-path", required=True, help="Path folder project di komputer ini")
    args = parser.parse_args()

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.is_dir():
        print(f"Error: folder '{repo_path}' tidak ditemukan.")
        return

    # Import di sini (bukan di top-level) supaya jelas dependency-nya eksplisit
    import sys
    backend_path = Path(__file__).resolve().parent.parent / "Backend"
    sys.path.insert(0, str(backend_path))
    from app.services.agent_runner import run_agent  # reuse, TIDAK mengubah file aslinya

    await run_agent(repo_path=repo_path, emit=cli_emit)


if __name__ == "__main__":
    asyncio.run(main())