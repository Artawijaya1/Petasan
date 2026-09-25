import asyncio

async def run_command(command: str, websocket_send_fn):
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