# PETASAN — Zero-Touch Environment Provisioner

> **PETASAN** adalah sistem orkestrasi lingkungan proyek berbasis AI yang secara otomatis meng-clone repository GitHub, menganalisis manifest dependency, menjalankan perintah instalasi, dan menghidupkan server aplikasi — semuanya melalui antarmuka web real-time dan dengan persetujuan eksplisit dari pengguna di setiap langkah.

---

## Daftar Isi

1. [Gambaran Umum](#gambaran-umum)
2. [Arsitektur Sistem](#arsitektur-sistem)
3. [Struktur Direktori](#struktur-direktori)
4. [Prerequisites](#prerequisites)
5. [Environment Variables](#environment-variables)
6. [Menjalankan Lokal (Windows)](#menjalankan-lokal-windows)
7. [API Reference — Backend WebSocket](#api-reference--backend-websocket)
8. [API Reference — Agents HTTP](#api-reference--agents-http)
9. [Alur Kerja Agent](#alur-kerja-agent)
10. [RAG & Knowledge Base](#rag--knowledge-base)
11. [Testing](#testing)
12. [Keamanan](#keamanan)
13. [Kontribusi](#kontribusi)

---

## Gambaran Umum

PETASAN memecahkan masalah klasik _"works on my machine"_ dengan menyediakan pipeline provisioning yang:

- Meng-**clone** repository GitHub ke workspace sementara secara otomatis
- Menganalisis manifest (`package.json`, `requirements.txt`, `Dockerfile`, dll.) dan meminta **AI (Google Gemini)** untuk merancang rencana setup yang tepat
- Menjalankan setiap **setup command** hanya setelah user memberikan persetujuan eksplisit di UI
- Jika sebuah perintah gagal, **Auto-Healing Agent** berkonsultasi dengan knowledge base lokal (RAG) dan Gemini untuk menghasilkan perintah perbaikan dan mencoba ulang hingga 3 kali
- Menghidupkan **server aplikasi** sebagai proses latar dan memverifikasi layanan melalui health check ke port yang terdeteksi
- Menampilkan seluruh proses secara **real-time** di dashboard web melalui WebSocket

---

## Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser (User)                                                  │
│  React 19 + Vite 8  ←──── WebSocket (/ws/agent) ────────────►  │
└─────────────────────────────────┬────────────────────────────────┘
                                  │ ws://host:8000/ws/agent
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend  (FastAPI, Python)   port 8000                         │
│  ├─ Validasi & normalisasi URL GitHub                           │
│  ├─ git clone --depth 1 → workspace sementara                   │
│  ├─ Deteksi manifest (Node / Python / Docker)                   │
│  ├─ Sistem persetujuan command (approval_required / response)   │
│  ├─ Eksekusi setup commands                                      │
│  ├─ Spawn server aplikasi sebagai proses latar                  │
│  └─ Cleanup proses & workspace saat shutdown                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP POST (Bearer token)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agents API  (FastAPI, Python)   port 8001                      │
│  ├─ POST /v1/scan  → Parser Agent (Gemini)                      │
│  │    Membaca manifest → rencana JSON (commands, start_command, │
│  │    port)                                                      │
│  └─ POST /v1/heal  → Healing Agent (Gemini + RAG)               │
│       Menganalisis stderr → fix_command baru                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ google-genai SDK
                           ▼
                   ☁️  Google Gemini API
                   (gemini-1.5-flash, default)

              + RAG Vector Store (lokal, all-MiniLM-L6-v2)
              + Embedding cache disk (_embedding_cache.json)
```

### Tabel Service

| Service | Teknologi | Port default | Peran |
|---|---|---|---|
| **Frontend** | React 19, Vite 8, Oxlint | `5173` (dev) | Dashboard monitoring & kontrol berbasis WebSocket |
| **Backend** | FastAPI, uvicorn, httpx | `8000` | Orchestrator: clone, validasi, approval, eksekusi |
| **Agents API** | FastAPI, uvicorn, google-genai | `8001` | AI brain: Parser Agent + Auto-Healing Agent + RAG |

---

## Struktur Direktori

```
Petasan/
├── Backend/                     # Service Backend (FastAPI)
│   ├── app/
│   │   ├── main.py              # Entry point FastAPI; lifecycle & CORS
│   │   ├── api/
│   │   │   └── routes.py        # WebSocket /ws/agent; clone + approval loop
│   │   ├── core/
│   │   │   └── config.py        # Baca AGENTS_API_URL dari .env
│   │   └── services/
│   │       ├── agent_runner.py  # Orkestrasi: scan → setup → heal → start service
│   │       └── agents_client.py # HTTP client ke Agents API (Bearer token)
│   ├── requirements.txt         # Dependensi Python backend
│   └── README.md                # Dokumentasi spesifik backend
│
├── Agents/                      # Service Agents API (FastAPI + AI)
│   ├── main.py                  # Entry point; autentikasi token; endpoint scan/heal
│   ├── runner.py                # Utilitas eksekusi command (command whitelist)
│   ├── agents/
│   │   ├── parser_agent.py      # Kirim manifest ke Gemini → rencana JSON setup
│   │   ├── healing_agent.py     # Kirim stderr + RAG context ke Gemini → fix_command
│   │   └── health_agent.py      # Cek HTTP ping ke localhost dengan retry
│   ├── rag/
│   │   ├── vector_store.py      # VectorStore: build index, cosine similarity retrieval
│   │   ├── embeddings_client.py # Encode teks lokal via sentence-transformers
│   │   ├── knowledge_seed.py    # Data awal knowledge base (6 kategori error)
│   │   └── _embedding_cache.json # Cache embedding agar tidak re-compute tiap restart
│   ├── requirements.txt         # Dependensi Python agents
│   └── pyproject.toml           # Metadata paket (zero-touch-agent)
│
├── Frontend/                    # Dashboard web (React + Vite)
│   ├── src/
│   │   ├── App.jsx              # Root component; state management; WebSocket hook
│   │   ├── constants/
│   │   │   └── config.js        # BACKEND_WS_URL; label status koneksi & run
│   │   ├── hooks/
│   │   │   └── useAgentSocket.js # Custom hook: koneksi WS, parsing event, reconnect
│   │   └── components/
│   │       ├── Header.jsx       # Topbar: nama brand + status koneksi + tombol reconnect
│   │       ├── Intro.jsx        # Hero section: judul + URL gateway backend
│   │       ├── ControlPanel.jsx # Form input URL repo + checkbox trust + tombol run
│   │       ├── ActivityPanel.jsx # Daftar event agent_thought real-time
│   │       ├── TerminalPanel.jsx # Output terminal streaming (pre tag)
│   │       └── Footer.jsx       # Footer statis
│   ├── vite.config.js           # Proxy /ws → backend; injeksi VITE_BACKEND_URL
│   └── package.json             # Dependensi Node.js
│
├── tests/                       # Test suite (pytest)
│   ├── conftest.py              # Shared fixtures & setup sys.path
│   ├── agents/                  # Pengujian unit komponen Agents
│   │   ├── test_parser_agent.py
│   │   ├── test_healing_agent.py
│   │   ├── test_health_agent.py
│   │   ├── test_vector_store.py
│   │   ├── test_embeddings_client.py
│   │   ├── test_agents_api.py
│   │   └── test_runner.py
│   └── backend/                 # Pengujian unit komponen Backend
│       ├── test_routes.py
│       ├── test_agent_runner.py
│       └── test_agents_client.py
│
├── pyproject.toml               # Konfigurasi pytest & coverage
└── .gitignore
```

---

## Prerequisites

| Dependensi | Versi minimum | Keterangan |
|---|---|---|
| Python | 3.10 | Dibutuhkan oleh Backend dan Agents |
| Node.js | 18 LTS | Dibutuhkan untuk menjalankan Frontend |
| Git | Versi terbaru | Harus tersedia di PATH host Backend |
| Google AI Studio API Key | — | Diperoleh dari [aistudio.google.com](https://aistudio.google.com) |

> **Catatan:** Model embedding `all-MiniLM-L6-v2` diunduh otomatis oleh `sentence-transformers` dari Hugging Face saat pertama kali dijalankan, dan disimpan di cache lokal `~/.cache/huggingface`. Setelah itu tidak perlu koneksi internet.

---

## Environment Variables

Seluruh variabel sensitif **tidak boleh** di-commit ke source code. Simpan di file `.env` (jangan push ke git) atau di environment settings platform hosting.

### Service Agents (port 8001)

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `GEMINI_API_KEY` | **Ya** | — | API key Google Gemini (dari Google AI Studio) |
| `AGENT_SERVICE_TOKEN` | **Ya** | — | Token Bearer untuk mengamankan endpoint `/v1/scan` dan `/v1/heal` |
| `GEMINI_MODEL` | Tidak | `gemini-1.5-flash` | Nama model Gemini yang digunakan |

### Service Backend (port 8000)

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `AGENTS_API_URL` | Tidak | `http://127.0.0.1:8001` | URL dasar Agents API |
| `AGENT_SERVICE_TOKEN` | **Ya** | — | Harus sama persis dengan token di Agents |

> **Penting:** Nilai `AGENT_SERVICE_TOKEN` di Backend dan Agents harus identik. Token ini tidak boleh dikirim ke browser atau Frontend.

### Membuat Token Acak (PowerShell)

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
[Convert]::ToBase64String($bytes)
```

### Frontend (Vite)

| Variabel | Default | Keterangan |
|---|---|---|
| `VITE_BACKEND_WS_URL` | Auto-detect dari `window.location` | URL WebSocket backend penuh, misal `ws://localhost:8000/ws/agent` |
| `VITE_BACKEND_PORT` | `8000` | Port backend jika tidak mengatur `VITE_BACKEND_WS_URL` |
| `VITE_BACKEND_URL` | `http://127.0.0.1:8000` | Dipakai Vite untuk proxy WebSocket di mode dev |

---

## Menjalankan Lokal (Windows)

### Langkah 1 — Siapkan virtual environment Python

```powershell
# Dari root repository
python -m venv .venv
```

### Langkah 2 — Install dependensi Backend dan Agents

```powershell
.\.venv\Scripts\python.exe -m pip install -r Agents\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r Backend\requirements.txt
```

### Langkah 3 — Jalankan Agents API (Terminal 1)

```powershell
$env:GEMINI_API_KEY     = "<API key dari Google AI Studio>"
$env:AGENT_SERVICE_TOKEN = "<token acak minimal 32 byte>"

.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir Agents --host 127.0.0.1 --port 8001
```

Health check tersedia di: `http://127.0.0.1:8001/health`  
Dokumentasi interaktif: `http://127.0.0.1:8001/docs`

### Langkah 4 — Jalankan Backend (Terminal 2)

```powershell
$env:AGENT_SERVICE_TOKEN = "<token yang sama dengan Agents>"
$env:AGENTS_API_URL      = "http://127.0.0.1:8001"

.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir Backend --host 127.0.0.1 --port 8000
```

Backend tersedia di: `http://127.0.0.1:8000`  
Dokumentasi interaktif: `http://127.0.0.1:8000/docs`

### Langkah 5 — Jalankan Frontend (Terminal 3)

```powershell
cd Frontend
npm install
npm run dev
```

Dashboard tersedia di: `http://localhost:5173`

### Langkah 6 — Gunakan Dashboard

1. Buka `http://localhost:5173` di browser
2. Pastikan status koneksi di header menunjukkan **"Backend terhubung"**
3. Masukkan URL repository GitHub (format `https://github.com/owner/repo`)
4. Centang kotak persetujuan kepercayaan
5. Klik **"Jalankan agent"**
6. Pantau proses di panel **Aktivitas Agent** dan **Terminal**
7. Setujui atau tolak setiap command yang diminta agent

---

## API Reference — Backend WebSocket

### Endpoint

```
WS  /ws/agent
```

Koneksi WebSocket bersifat _persistent_ — satu koneksi bisa digunakan untuk menjalankan beberapa sesi provisioning secara berurutan.

---

### Pesan dari Klien ke Backend

#### 1. Memulai Sesi Provisioning

```json
{
  "action": "start",
  "repo_url": "https://github.com/owner/repository"
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `action` | `string` | Harus berisi `"start"` |
| `repo_url` | `string` | URL HTTPS repository GitHub yang valid |

**Validasi URL yang diterapkan:**
- Skema harus `https`
- Host harus `github.com`
- Format path harus `owner/repository` (tepat 2 segmen)
- Tidak boleh mengandung `@`, port, query string, atau fragment
- Nama owner dan repository hanya boleh berisi `[A-Za-z0-9_.-]`

#### 2. Respons Persetujuan Command

Setelah backend mengirim event `approval_required`, klien wajib membalas:

```json
{
  "action": "approval_response",
  "request_id": "<uuid dari event approval_required>",
  "approved": true
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `action` | `string` | Harus `"approval_response"` |
| `request_id` | `string` | UUID yang dikirim oleh backend dalam event `approval_required` |
| `approved` | `boolean` | `true` untuk menyetujui, `false` untuk menolak |

---

### Pesan dari Backend ke Klien

#### `agent_thought` — Aktivitas & Status Agent

```json
{
  "type": "agent_thought",
  "title": "Menganalisis Repositori Proyek",
  "content": "Memindai manifest dependency...",
  "status": "in_progress"
}
```

| Nilai `status` | Arti |
|---|---|
| `in_progress` | Langkah sedang berjalan |
| `completed` | Langkah berhasil diselesaikan |
| `failed` | Langkah gagal |

#### `terminal_log` — Output Terminal

```json
{
  "type": "terminal_log",
  "content": "$ npm install\n",
  "isError": false
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `content` | `string` | Teks output dari proses |
| `isError` | `boolean` | `true` jika berasal dari stderr |

#### `approval_required` — Permintaan Persetujuan

```json
{
  "type": "approval_required",
  "request_id": "a1b2c3d4e5f6...",
  "command": "npm install",
  "reason": "Menjalankan command setup"
}
```

Backend **menunggu** pesan `approval_response` dari klien sebelum melanjutkan.

#### `agent_error` — Error pada Agent

```json
{
  "type": "agent_error",
  "content": "URL GitHub tidak valid."
}
```

#### `agent_complete` — Sesi Selesai

```json
{
  "type": "agent_complete",
  "status": "completed",
  "service_started": true,
  "content": "Environment siap dan aplikasi berjalan."
}
```

| Field | Nilai `status` | Keterangan |
|---|---|---|
| `status` | `"completed"` | Semua langkah berhasil |
| `status` | `"failed"` | Setidaknya satu langkah gagal |
| `service_started` | `boolean` | `true` jika server aplikasi berhasil dihidupkan dan merespons health check |

---

## API Reference — Agents HTTP

Seluruh endpoint (kecuali `/health`) memerlukan header:

```
Authorization: Bearer <AGENT_SERVICE_TOKEN>
```

---

### `GET /health`

Health check untuk memverifikasi service Agents aktif.

**Response 200:**
```json
{
  "status": "ok",
  "service": "agents"
}
```

---

### `POST /v1/scan`

Menganalisis manifest repository dan menghasilkan rencana setup menggunakan Gemini.

**Request Body:**
```json
{
  "files": {
    "package.json": "{\"name\": \"my-app\", \"scripts\": {\"dev\": \"vite\"}}",
    "requirements.txt": "fastapi\nuvicorn\n"
  }
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `files` | `object` | Key: nama file; Value: isi file (maks. 2000 karakter per file) |

File yang diproses oleh Backend sebelum dikirim ke Agents:
`package.json`, `requirements.txt`, `pyproject.toml`, `Pipfile`, `environment.yml`, `Dockerfile`, `docker-compose.yml`, `compose.yml`, `compose.yaml`, `README.md`

**Response 200:**
```json
{
  "commands": ["npm install"],
  "start_command": "npm run dev -- --host 0.0.0.0",
  "port": 5173
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `commands` | `array<string>` | Daftar setup/install command yang harus dijalankan |
| `start_command` | `string \| null` | Command untuk menghidupkan server; `null` jika tidak ada |
| `port` | `integer \| null` | Port yang dipakai server (misal `5173` untuk Vite, `3000` untuk Next.js) |

**Response 502:** Ketika Gemini API tidak dapat dihubungi atau mengembalikan respons tidak valid.

---

### `POST /v1/heal`

Menganalisis command yang gagal dan error log, lalu menghasilkan perintah perbaikan.

**Request Body:**
```json
{
  "command_failed": "npm install",
  "stderr_log": "npm ERR! Cannot find module 'some-pkg'",
  "attempt": 1
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `command_failed` | `string` | Command yang gagal dijalankan |
| `stderr_log` | `string` | Isi stderr (diambil 1500 karakter terakhir) |
| `attempt` | `integer` | Percobaan ke berapa (1–3) |

**Response 200:**
```json
{
  "thought_title": "Dependency tidak ditemukan",
  "thought_detail": "Package 'some-pkg' tidak terdaftar di node_modules. Kemungkinan node_modules korup.",
  "fix_command": "npm install --legacy-peer-deps"
}
```

| Field | Tipe | Keterangan |
|---|---|---|
| `thought_title` | `string` | Judul ringkas diagnosa masalah |
| `thought_detail` | `string` | Penjelasan mendalam penyebab error |
| `fix_command` | `string` | Command perbaikan yang akan dicoba ulang |

**Response 502:** Ketika Agents tidak dapat menghasilkan diagnosis.

---

## Alur Kerja Agent

Berikut adalah alur lengkap dari satu sesi provisioning:

```
Klien kirim { action: "start", repo_url: "https://github.com/..." }
  │
  ▼
[Backend] Validasi & normalisasi URL GitHub
  │
  ▼
[Backend] git clone --depth 1 → /tmp/petasan-XXXXX/repository/
  │
  ▼
[Backend] Deteksi manifest:
  ├─ package.json?        → node_manifest = True
  ├─ requirements.txt /   → python_manifest = True
  │  pyproject.toml /
  │  Pipfile / environment.yml?
  └─ Dockerfile /         → docker_manifest = True
     docker-compose.yml?
  │
  ├─ Tidak ada manifest → selesai (tidak ada command yang dijalankan)
  │
  ▼
[Backend → Agents] POST /v1/scan { files: { manifest contents } }
  │
  ▼
[Agents / Parser Agent] Kirim manifest ke Gemini
  Gemini mengembalikan:
  { commands: [...], start_command: "...", port: 5173 }
  │
  ▼
[Backend] Filter commands:
  - Tolak command yang tidak cocok dengan manifest yang ada
  - Tolak npm init
  - Pisahkan start_command dari setup commands
  │
  ▼
[Backend] Untuk setiap setup command:
  ├─ Kirim event approval_required ke klien
  ├─ Tunggu approval_response dari klien
  │   ├─ Ditolak? → selesai (command tidak dijalankan)
  │   └─ Disetujui? → jalankan command
  │
  │  Jika command gagal (exit_code != 0):
  │   ├─ Attempt < 3?
  │   │   ├─ [Backend → Agents] POST /v1/heal { command_failed, stderr_log, attempt }
  │   │   ├─ [Agents / Healing Agent] Konsultasi RAG + Gemini → fix_command
  │   │   └─ Ulangi dengan fix_command yang baru (kembali ke approval)
  │   └─ Attempt == 3? → selesai dengan status failed
  │
  ▼
[Backend] Jalankan start_command (jika ada):
  ├─ Kirim approval_required
  ├─ Spawn subprocess (Popen, output di-stream ke terminal)
  ├─ Health check ke http://127.0.0.1:{port} (10x retry, jeda 2 detik)
  │   ├─ Sukses? → simpan proses di _ACTIVE_TARGETS, retain workspace
  │   └─ Gagal? → terminate proses, hapus workspace
  │
  ▼
[Backend] Kirim agent_complete { status: "completed", service_started: true/false }
  │
  ▼
[Backend shutdown] cleanup_target_processes():
  - Terminate semua proses aktif
  - Hapus workspace yang di-retain
```

---

## RAG & Knowledge Base

### Cara Kerja

Healing Agent menggunakan **Retrieval-Augmented Generation (RAG)** untuk memperkaya diagnosis Gemini dengan referensi dari knowledge base lokal:

1. **Build Index** — Saat pertama kali `diagnose_and_fix` dipanggil, `VectorStore.build_index()` mengubah seluruh entry di `KNOWLEDGE_SEED` menjadi embedding menggunakan model `all-MiniLM-L6-v2` yang berjalan **lokal di CPU**
2. **Cache Disk** — Embedding disimpan di `Agents/rag/_embedding_cache.json`. Jika cache ada dan jumlah entry-nya cocok dengan `KNOWLEDGE_SEED`, embedding tidak perlu dihitung ulang saat restart
3. **Retrieval** — Ketika ada error, `stderr_log` di-embed, lalu dilakukan **cosine similarity search** terhadap semua vektor di index. Diambil top-3 entry dengan skor ≥ 0.3
4. **Augmentasi Prompt** — Entry yang relevan disertakan sebagai konteks dalam prompt ke Gemini: `"Saran yang pernah berhasil: {known_fix}"`

### Menambah Entry Knowledge Base

Edit file [`Agents/rag/knowledge_seed.py`](Agents/rag/knowledge_seed.py) dan tambahkan entry baru ke list `KNOWLEDGE_SEED`:

```python
{
    "id": "id_unik_error",
    "text": "Deskripsi gejala error yang lengkap dan jelas...",
    "known_fix": "perintah perbaikan yang terbukti berhasil",
    "category": "kategori_error",
}
```

**Setelah menambah entry baru**, hapus file cache agar index dibangun ulang:

```powershell
Remove-Item Agents\rag\_embedding_cache.json
```

### Kategori Error yang Sudah Ada

| ID | Kategori | Deskripsi |
|---|---|---|
| `eaddrinuse` | `port_conflict` | Port sudah digunakan proses lain |
| `module_not_found` | `missing_dependency` | node_modules tidak ada / korup |
| `permission_denied` | `permission` | File di node_modules/.bin tidak punya permission execute |
| `python_module_not_found` | `missing_dependency` | Package Python belum terinstall |
| `engine_version_mismatch` | `version_mismatch` | Versi Node tidak sesuai requirement |
| `enoent_file_missing` | `missing_file` | File / direktori yang dibutuhkan tidak ditemukan |

---

## Testing

Project menggunakan **pytest** dengan `asyncio_mode = "auto"` untuk mendukung test async.

### Menjalankan Semua Test

```powershell
# Dari root repository
.\.venv\Scripts\python.exe -m pytest
```

### Menjalankan dengan Coverage

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=Agents --cov=Backend --cov-report=term-missing
```

### Menjalankan Test Spesifik

```powershell
# Hanya test Agents
.\.venv\Scripts\python.exe -m pytest tests/agents/

# Hanya test Backend
.\.venv\Scripts\python.exe -m pytest tests/backend/

# Test file spesifik
.\.venv\Scripts\python.exe -m pytest tests/agents/test_healing_agent.py -v
```

### Struktur Test Suite

| File | Yang Diuji |
|---|---|
| `tests/agents/test_parser_agent.py` | `create_installation_plan`: respons valid, error API, JSON invalid, prompt berisi manifest |
| `tests/agents/test_healing_agent.py` | `diagnose_and_fix`: happy path, integrasi RAG, truncate stderr 1500 char, berbagai edge case error |
| `tests/agents/test_health_agent.py` | `check_health`: retry logic, HTTP 2xx/4xx, timeout |
| `tests/agents/test_vector_store.py` | `VectorStore.build_index`, `retrieve`: cosine similarity, cache hit/miss |
| `tests/agents/test_embeddings_client.py` | `get_embedding`, `get_embeddings_batch`: encoding lokal |
| `tests/agents/test_agents_api.py` | Endpoint `/health`, `/v1/scan`, `/v1/heal`: autentikasi, validasi request |
| `tests/agents/test_runner.py` | `is_command_safe`: whitelist command |
| `tests/backend/test_routes.py` | WebSocket `/ws/agent`: approval flow, validasi URL GitHub, error handling |
| `tests/backend/test_agent_runner.py` | `run_agent`: manifest detection, command filtering, healing loop |
| `tests/backend/test_agents_client.py` | `call_agents`: HTTP error, timeout, respons tidak valid |

### Shared Fixtures (`tests/conftest.py`)

| Fixture | Tipe | Keterangan |
|---|---|---|
| `emit_mock` | `AsyncMock` | Mock WebSocket emit function |
| `sample_files` | `dict` | Contoh payload `files` untuk `/v1/scan` |
| `sample_healing_payload` | `dict` | Contoh payload untuk `/v1/heal` |
| `valid_healing_response` | `dict` | Contoh respons valid dari healing agent |
| `valid_scan_response` | `dict` | Contoh respons valid dari parser agent |

> Test tidak memerlukan API key atau koneksi internet. Semua API eksternal (Gemini, sentence-transformers) di-mock menggunakan `unittest.mock`.

---

## Keamanan

### Autentikasi Antar-Service

Komunikasi Backend → Agents diamankan menggunakan **HTTP Bearer Token**:
- Token dibandingkan menggunakan `hmac.compare_digest()` untuk mencegah timing attack
- Jika `AGENT_SERVICE_TOKEN` tidak dikonfigurasi, Agents mengembalikan `503 Service Unavailable`
- Token tidak boleh dikirim ke browser atau disertakan di Frontend

### Validasi URL GitHub

Backend menerapkan validasi ketat sebelum meng-clone repository:

```python
# Cek yang diterapkan di _normalize_github_url():
- scheme == "https"
- hostname == "github.com"
- Tidak ada username/password di URL
- Tidak ada port
- Tidak ada query string atau fragment
- Path harus tepat 2 segmen: owner/repository
- Karakter hanya [A-Za-z0-9_.-]
- Nama owner/repository bukan "." atau ".."
```

### Pemfilteran Command

Backend memvalidasi setiap command dari Agent sebelum memintakan persetujuan user:

| Pola yang Ditolak | Alasan |
|---|---|
| Command Node (`npm`, `npx`, `yarn`, dll.) tanpa `package.json` | Tidak ada manifest Node |
| Command Python (`pip`, `uv`, `poetry`, dll.) tanpa manifest Python | Tidak ada manifest Python |
| Command Docker tanpa Dockerfile / compose | Tidak ada manifest Docker |
| `npm init` | Tidak boleh membuat manifest baru |
| Start command yang tidak cocok manifest | Mencegah menjalankan skrip arbitrer |

### Sistem Approval

Setiap command — baik setup maupun start server — harus **disetujui secara eksplisit** oleh pengguna melalui UI sebelum dijalankan. Jika koneksi WebSocket terputus saat menunggu approval, sesi dianggap gagal.

### Isolasi Workspace

- Setiap sesi menggunakan **temporary directory** yang unik (`/tmp/petasan-XXXXX/`)
- Workspace dihapus otomatis setelah sesi selesai menggunakan `shutil.rmtree`
- Workspace hanya dipertahankan (_retained_) jika server aplikasi berhasil dihidupkan dan tetap hidup
- Saat Backend dimatikan (`lifespan shutdown`), semua proses aktif dihentikan dan semua retained workspace dibersihkan

### Privasi Data

- Isi file `.env` tidak pernah dibaca atau dikirim ke model AI
- Ketika template `.env.example` ditemukan, agent hanya melaporkan keberadaannya tanpa membaca nilainya
- File `.env` tidak dibuat otomatis dari template

---

## Kontribusi

### Code Style

- **Python:** Ikuti konvensi yang sudah ada (type hints, `from __future__ import annotations`, logging via `logging.getLogger`)
- **JavaScript:** Oxlint digunakan sebagai linter — jalankan `npm run lint` dari folder `Frontend/` sebelum commit
- Gunakan **Bahasa Indonesia** untuk pesan log, komentar kode, dan string yang muncul di UI (konsisten dengan codebase yang ada)

### Menambah Agen Baru

1. Buat file baru di `Agents/agents/nama_agent.py`
2. Tambahkan endpoint di `Agents/main.py` dengan decorator `@app.post` dan `dependencies=[Depends(require_service_token)]`
3. Panggil endpoint baru dari `Backend/app/services/agent_runner.py` via `call_agents()`
4. Tambahkan test di `tests/agents/`

### Branching

```
main        ← production-ready
teguh       ← development branch (lihat git log)
```

### Menjalankan Lint Frontend

```powershell
cd Frontend
npm run lint
```

### Menjalankan Build Frontend (Production)

```powershell
cd Frontend
npm run build
# Output di Frontend/dist/
```
