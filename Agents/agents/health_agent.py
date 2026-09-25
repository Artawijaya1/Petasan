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
    Memeriksa secara berkala apakah layanan aplikasi lokal sudah aktif dan merespons HTTP 200/2xx.

    :param target_url: URL lokal yang ingin diperiksa (misal: http://localhost:3000 atau http://localhost:8000)
    :param max_retries: Jumlah maksimum percobaan ping
    :param delay_seconds: Jeda antar percobaan (dalam detik)
    :param websocket_send_fn: Fungsi pemancar log ke Web Dashboard secara real-time
    :return: True jika server merespons 2xx, False jika timeout/gagal
    """
    if websocket_send_fn:
        await websocket_send_fn({
            "type": "agent_thought",
            "title": "Verifikasi Layanan (Health Check)",
            "content": f"Memverifikasi status server lokal di {target_url}...",
            "status": "in_progress",
        })

    def _ping() -> int:
        """Fungsi sinkron yang melakukan HTTP request sederhana menggunakan standard library."""
        req = urllib.request.Request(target_url, headers={"User-Agent": "HealthCheckerAgent/1.0"})
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status

    for attempt in range(1, max_retries + 1):
        try:
            # Jalankan HTTP ping di thread terpisah agar tidak menghentikan event loop async
            status_code = await asyncio.to_thread(_ping)

            if 200 <= status_code < 400:
                if websocket_send_fn:
                    await websocket_send_fn({
                        "type": "agent_thought",
                        "title": "Health Check Passed! 🚀",
                        "content": f"Layanan berhasil aktif dan merespons dari {target_url} (HTTP Status: {status_code}).",
                        "status": "completed",
                    })
                return True

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}: {e.reason}"
            if websocket_send_fn:
                await websocket_send_fn({
                    "type": "terminal_log",
                    "content": f"[Health Check] Percobaan {attempt}/{max_retries} ke {target_url}... ({error_msg})\n",
                    "isError": False,
                })

        except (urllib.error.URLError, TimeoutError) as e:
            error_msg = getattr(e, "reason", str(e)) or "Connection Refused"
            if websocket_send_fn:
                await websocket_send_fn({
                    "type": "terminal_log",
                    "content": f"[Health Check] Percobaan {attempt}/{max_retries} ke {target_url}... ({error_msg})\n",
                    "isError": False,
                })

        await asyncio.sleep(delay_seconds)

    # Jika melebihi batas waktu percobaan
    if websocket_send_fn:
        await websocket_send_fn({
            "type": "agent_thought",
            "title": "Health Check Warning ⚠️",
            "content": f"Server tidak merespons di {target_url} setelah {max_retries * delay_seconds} detik. Silakan periksa log terminal.",
            "status": "completed",
        })

    return False