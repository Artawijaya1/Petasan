# Plan: Membuat README.md Lengkap untuk Project Petasan

## Top-Level Overview

Membuat file `README.md` di root repository yang menjelaskan project **Petasan** secara menyeluruh kepada developer/kontributor. README ditulis dalam **Bahasa Indonesia** dan mencakup semua aspek teknis: arsitektur, API, environment variables, cara menjalankan lokal, alur kerja agent, RAG, testing, dan keamanan.

---

## Sub-Tasks

### Sub-Task 1 — Tulis README.md

**Intent:** Membuat satu file `README.md` di root repository yang lengkap dan rinci.

**Expected Outcomes:** File `README.md` tersedia di root dan memuat semua seksi di bawah ini.

**Todo List:**
- [x] Tulis seksi Header (nama, badge, deskripsi singkat)
- [x] Tulis seksi Arsitektur (diagram teks + tabel komponen)
- [x] Tulis seksi Struktur Direktori
- [x] Tulis seksi Environment Variables (tabel lengkap semua service)
- [x] Tulis seksi Cara Menjalankan Lokal (Windows — step-by-step)
- [x] Tulis seksi API Reference — Backend WebSocket
- [x] Tulis seksi API Reference — Agents HTTP
- [x] Tulis seksi Alur Kerja Agent (step-by-step provisioning)
- [x] Tulis seksi RAG & Knowledge Base
- [x] Tulis seksi Testing
- [x] Tulis seksi Keamanan
- [x] Tulis seksi Kontribusi / Development Notes

**Relevant Context:**
- `Backend/README.md` — dokumentasi awal backend (sudah ada, tapi minim)
- `Backend/app/api/routes.py` — WebSocket endpoint `/ws/agent`
- `Backend/app/services/agent_runner.py` — alur eksekusi agent
- `Agents/main.py` — FastAPI Agents dengan endpoint `/health`, `/v1/scan`, `/v1/heal`
- `Agents/agents/parser_agent.py` — Google Gemini parser
- `Agents/agents/healing_agent.py` — Auto-healing dengan RAG
- `Agents/rag/` — Vector store lokal dengan `all-MiniLM-L6-v2`
- `Frontend/src/` — React dashboard dengan WebSocket hook
- `tests/` — pytest test suite
- `pyproject.toml` — konfigurasi pytest

**Status:** `[x] done`

---

## Seksi-Seksi README yang Akan Ditulis

1. **Header** — Nama project, deskripsi satu baris, badge Python/Node version
2. **Gambaran Umum** — Apa itu Petasan, masalah apa yang dipecahkan
3. **Arsitektur** — Diagram ASCII + tabel 3 service
4. **Struktur Direktori** — Tree direktori penting dengan penjelasan
5. **Prerequisites** — Python ≥3.10, Node.js, Git, akun Google AI Studio
6. **Environment Variables** — Tabel semua variabel dengan keterangan
7. **Menjalankan Lokal (Windows)** — Step-by-step untuk Agents, Backend, Frontend
8. **API Reference — Backend WebSocket** — `/ws/agent` dengan contoh JSON
9. **API Reference — Agents HTTP** — `/health`, `/v1/scan`, `/v1/heal` dengan contoh request/response
10. **Alur Kerja Agent** — Flow diagram teks dari clone→scan→execute→heal→health-check
11. **RAG & Knowledge Base** — Penjelasan vector store, model embedding, cara menambah entry
12. **Testing** — Cara menjalankan pytest, struktur test suite
13. **Keamanan** — Token autentikasi, validasi URL GitHub, whitelist perintah
14. **Kontribusi** — Code style, branching, konvensi
