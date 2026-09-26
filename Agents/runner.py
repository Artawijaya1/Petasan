import asyncio

ALLOWED_COMMAND_PREFIXES = ("npm ", "npx ", "pip ", "python -m pip", "yarn ")
DANGEROUS_PATTERNS = ["rm -rf", "sudo", "curl ", "wget ", ">", "&&", ";", "|"]

def is_command_safe(cmd: str) -> bool:
    cmd_lower = cmd.strip().lower()
    if any(danger in cmd_lower for danger in DANGEROUS_PATTERNS):
        return False
    return any(cmd_lower.startswith(prefix) for prefix in ALLOWED_COMMAND_PREFIXES)


async def run_command(command: str, websocket_send_fn, cwd: str | None = None) -> dict:
    if not is_command_safe(command):  # <-- DISISIPKAN DI SINI, paling atas fungsi
        await websocket_send_fn({
            "type": "terminal_log",
            "content": f"Command ditolak (tidak lolos whitelist keamanan): {command}\n",
            "isError": True
        })
        return {"exit_code": -1, "stdout": "", "stderr": "Command blocked by security whitelist"}

    await websocket_send_fn({...})

async def run_command(command: str, websocket_send_fn, cwd: str | None = None):
    """
    Menjalankan perintah terminal secara asynchronous
    dan memancarkan log-nya ke WebSocket secara real-time.
    """
    await websocket_send_fn({
        "type": "terminal_log",
        "content": f"$ {command}\n",
        "isError": False
    })

    # Jalankan perintah di shell
    process = await asyncio.create_subprocess_shell(
        command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout_bytes, stderr_bytes = await process.communicate()
    
    stdout_str = stdout_bytes.decode('utf-8', errors='replace')
    stderr_str = stderr_bytes.decode('utf-8', errors='replace')

    if stdout_str:
        await websocket_send_fn({
            "type": "terminal_log",
            "content": stdout_str,
            "isError": False
        })

    if stderr_str:
        await websocket_send_fn({
            "type": "terminal_log",
            "content": stderr_str,
            "isError": True
        })

    return {
        "exit_code": process.returncode,
        "stdout": stdout_str,
        "stderr": stderr_str
    }