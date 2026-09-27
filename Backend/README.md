# Petasan Backend dan Agents API

Backend dan Agents berjalan sebagai dua service terpisah. Backend menerima koneksi WebSocket dari klien, membaca berkas proyek dan menjalankan perintah; Agents menerima permintaan scan/healing melalui HTTP dan memakai Bob untuk menghasilkan rencana atau perbaikan.

## Environment variables

Atur variables ini di secret/environment settings hosting, bukan di source code:

| Service | Variable | Kegunaan |
| --- | --- | --- |
| Agents | `BOB_API_KEY` | Kredensial Bob Inference; hanya diperlukan di Agents. |
| Agents | `AGENT_SERVICE_TOKEN` | Token Bearer untuk mengamankan endpoint internal Agents. |
| Agents | `BOB_BASE_URL` | Opsional; default `https://bob.ibm.com/api`. |
| Agents | `BOB_MODEL` | Opsional; default `bob`. |
| Backend | `AGENTS_API_URL` | URL dasar Agents API, misalnya `https://agents.example.com`. |
| Backend | `AGENT_SERVICE_TOKEN` | Nilainya harus sama dengan token pada service Agents. |

Buat token acak minimal 32 byte sekali, lalu simpan nilai yang sama pada kedua hosting. Contoh generator PowerShell:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
[Convert]::ToBase64String($bytes)
```

Jangan kirim token ini ke browser/frontend. `BOB_API_KEY` berbeda dari service token dan tidak perlu disetel pada Backend.

## Menjalankan lokal di Windows

Pasang dependencies untuk masing-masing service:

```powershell
.\.venv\Scripts\python.exe -m pip install -r Agents\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r Backend\requirements.txt
```

Di terminal pertama, atur konfigurasi Agents lalu jalankan dari root repository:

```powershell
$env:BOB_API_KEY = "<Bob Inference key>"
$env:AGENT_SERVICE_TOKEN = "<shared random token>"
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir Agents --host 127.0.0.1 --port 8001
```

Di terminal kedua, atur token yang sama dan URL Agents:

```powershell
$env:AGENT_SERVICE_TOKEN = "<shared random token>"
$env:AGENTS_API_URL = "http://127.0.0.1:8001"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir Backend --host 127.0.0.1 --port 8000
```

Backend tersedia di `http://127.0.0.1:8000`, dokumentasi di `/docs`, dan Agents health check di `http://127.0.0.1:8001/health`.

## API Agents

- `GET /health` untuk health check hosting.
- `POST /v1/scan` menerima `{ "files": { "package.json": "..." } }`.
- `POST /v1/heal` menerima `command_failed`, `stderr_log`, dan `attempt`.

Endpoint scan dan heal memerlukan header `Authorization: Bearer <AGENT_SERVICE_TOKEN>`. Backend menerima URL repository GitHub melalui `ws://127.0.0.1:8000/ws/agent`, meng-clone repository ke direktori sementara, lalu menghapusnya setelah proses selesai. Git harus tersedia di host Backend. Repository privat memerlukan kredensial Git yang sudah dikonfigurasi di host; jangan kirim token lewat browser. Pesan start memakai format:

```json
{
   "action": "start",
   "repo_url": "https://github.com/owner/repository"
}
```

URL harus menunjuk ke repository di `github.com` melalui HTTPS. Backend mengecek manifest sebelum meminta rencana setup. Tanpa manifest yang sesuai, scan berhenti tanpa menjalankan install. Setiap command setup, perbaikan, dan start ditampilkan di UI serta menunggu persetujuan user. `npm init` diblokir dan file `.env` tidak dibuat otomatis atau dikirim ke model. Untuk aplikasi web, parser memisahkan `start_command` dan port; Backend menjalankan server sebagai proses latar dan mengecek port yang dipilih, bukan mengasumsikan 3000. Server yang berhasil start tetap hidup sampai Backend dihentikan, lalu proses dan workspace dibersihkan.
