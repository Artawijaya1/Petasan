# health_agent.py
import asyncio
import urllib.request
import urllib.error


async def check_health(
    target_url: str = "http://localhost:3000",
    max_retries: int = 15,
    delay_seconds: int = 2,
    websocket_send_fn=None,
) -> bool:
    """
    Periodically checks whether the local application is running and returns HTTP 200/2xx.

    :param target_url: Local URL to check (for example, http://localhost:3000)
    :param max_retries: Maximum number of ping attempts
    :param delay_seconds: Delay between attempts, in seconds
    :param websocket_send_fn: Callback that streams events to the web dashboard
    :return: True if the server returns 2xx, otherwise False
    """
    if websocket_send_fn:
        await websocket_send_fn({
            "type": "agent_thought",
            "title": "Application Health Check",
            "content": f"Checking the local server at {target_url}...",
            "status": "in_progress",
        })

    def _ping() -> int:
        """Perform a simple HTTP request using the standard library."""
        req = urllib.request.Request(target_url, headers={"User-Agent": "HealthCheckerAgent/1.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status

    for attempt in range(1, max_retries + 1):
        try:
            # Run the HTTP ping in a separate thread to avoid blocking the async event loop.
            status_code = await asyncio.to_thread(_ping)

            if 200 <= status_code < 400:
                if websocket_send_fn:
                    await websocket_send_fn({
                        "type": "agent_thought",
                        "title": "Health Check Passed!",
                        "content": f"The service is running and responded at {target_url} (HTTP status: {status_code}).",
                        "status": "completed",
                    })
                return True

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            if websocket_send_fn:
                await websocket_send_fn({
                    "type": "terminal_log",
                    "content": f"[Health Check] Attempt {attempt}/{max_retries} at {target_url}... ({error_msg})\n",
                    "isError": False,
                })

        except (urllib.error.URLError, TimeoutError) as e:
            error_msg = getattr(e, "reason", str(e)) or "Connection Refused"
            if websocket_send_fn:
                await websocket_send_fn({
                    "type": "terminal_log",
                    "content": f"[Health Check] Attempt {attempt}/{max_retries} at {target_url}... ({error_msg})\n",
                    "isError": False,
                })

        await asyncio.sleep(delay_seconds)

    # Report the timeout after all attempts are exhausted.
    if websocket_send_fn:
        await websocket_send_fn({
            "type": "agent_thought",
            "title": "Health Check Warning",
            "content": f"The server did not respond at {target_url} after {max_retries * delay_seconds} seconds. Check the terminal logs.",
            "status": "completed",
        })

    return False