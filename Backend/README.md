# Petasan Backend

## Menjalankan server

1. Dari direktori `Backend`, buat virtual environment dan pasang dependensi:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   .\.venv\Scripts\Activate.ps1
   ```

2. Salin `Agents/.env.example` menjadi `Agents/.env`, lalu isi `BOB_API_KEY` dengan API key Bob Inference yang valid.
3. Jalankan server:

   ```powershell
   uvicorn app.main:app --reload
   ```

Server tersedia di `http://127.0.0.1:8000`. Dokumentasi interaktif tersedia di `/docs`.

## WebSocket agent

Hubungkan klien ke `ws://127.0.0.1:8000/ws/agent`, lalu kirim:

```json
{
  "action": "start",
  "repo_path": "C:\\path\\to\\project"
}
```

`repo_path` harus menunjuk ke direktori proyek yang sudah ada. Server mengirim pesan agent dan log perintah melalui koneksi WebSocket yang sama.
