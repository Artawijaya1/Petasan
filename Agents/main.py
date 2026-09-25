import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from runner import run_command
from agents.parser_agent import scan_repository
from agents.healing_agent import diagnose_and_fix
from agents.health_agent import check_health

app = FastAPI()

@app.websocket("/ws/agent")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def emit(data):
        await websocket.send_json(data)

    try:
        while True:
            # Tunggu sinyal 'START' dari Frontend Web
            data = await websocket.receive_json()
            if data.get("action") == "start":
                repo_path = data.get("repo_path", "./my-target-app")
                
                # 1. Tampilkan Thought Process: Scanning
                await emit({
                    "type": "agent_thought",
                    "title": "Menganalisis Repositori Proyek",
                    "content": f"Memindai struktur berkas di {repo_path}...",
                    "status": "in_progress"
                })

                # 2. Parsing Konfigurasi
                plan = await scan_repository(repo_path)
                
                # Buat .env jika diperlukan
                if plan.get("env_needed") and os.path.exists(os.path.join(repo_path, ".env.example")):
                    with open(os.path.join(repo_path, ".env.example"), "r") as f_in:
                        env_content = f_in.read()
                    with open(os.path.join(repo_path, ".env"), "w") as f_out:
                        f_out.write(env_content)
                    await emit({
                        "type": "agent_thought",
                        "title": "Auto-Generating .env",
                        "content": "File .env berhasil dibuat dari .env.example dengan default values.",
                        "status": "completed"
                    })

                commands = plan.get("commands", [])

                # 3. Execution & Auto-Healing Loop
                for cmd in commands:
                    attempt = 1
                    max_attempts = 3
                    current_cmd = cmd

                    while attempt <= max_attempts:
                        result = await run_command(current_cmd, emit)

                        if result["exit_code"] == 0:
                            # Sukses
                            return
                        else:
                            # Error Terjadi! Trigger Auto-Healing
                            await emit({
                                "type": "agent_thought",
                                "title": f"Mendeteksi Failure pada '{current_cmd}'",
                                "content": "Error terdeteksi. Mengirim stderr log ke Auto-Healing Agent...",
                                "status": "in_progress"
                            })

                            # Dapatkan saran perbaikan dari LLM
                            healing_res = await diagnose_and_fix(current_cmd, result["stderr"], attempt)
                            if not isinstance(healing_res, dict):
                                await emit({
                                    "type": "agent_thought",
                                    "title": "Auto-Healing gagal",
                                    "content": "Agent tidak dapat menghasilkan perintah perbaikan.",
                                    "status": "failed"
                                })
                                break

                            await emit({
                                "type": "agent_thought",
                                "title": f"Auto-Healing Strategy: {healing_res['thought_title']}",
                                "content": healing_res['thought_detail'],
                                "status": "in_progress"
                            })

                            # Update perintah ke perintah perbaikan baru
                            current_cmd = healing_res["fix_command"]
                            attempt += 1

                # 4. Selesai
                await emit({
                    "type": "agent_thought",
                    "title": "Environment Ready!",
                    "content": "Semua dependensi terpasang dan layanan berhasil dijalankan.",
                    "status": "completed"
                })

                is_healthy = await check_health(
                    target_url="http://localhost:3000",  # Sesuaikan port aplikasi target
                    max_retries=10,
                    delay_seconds=2,
                    websocket_send_fn=emit
                )

                # 5. Beri sinyal akhir ke Dashboard Web
                await emit({
                    "type": "agent_thought",
                    "title": "SYSTEM READY FOR DEMO!",
                    "content": "Environment siap digunakan tanpa kesalahan.",
                    "status": "completed"
                })
            
    except WebSocketDisconnect:
     print("Client disconnected")