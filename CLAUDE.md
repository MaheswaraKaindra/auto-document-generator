# auto-document-generator

## Ringkasan

**auto-document-generator** adalah produk **SaaS generik** yang membaca source code dari repo mana pun (GitHub OAuth/PAT, atau ZIP upload — bukan tool internal satu perusahaan) dan otomatis membuat draf dua dokumen yang biasanya ditulis manual oleh developer/QA: **Solution Design Document (SDD)** dan **User Acceptance Test (UAT) Document**, keduanya dalam format `.docx` siap pakai.

## Latar Belakang & Tujuan

Tim development yang bekerja dengan ritme agile/Scrum sering menunda pembuatan dokumen SDD/UAT (atau menulisnya asal-asalan setelah development selesai) karena menulis dokumen ini manual itu lambat dan membosankan — padahal formatnya selalu sama di setiap project, cuma isinya yang beda. Ide awalnya muncul dari pengalaman magang salah satu anggota tim di sebuah perusahaan (melihat bottleneck ini secara langsung), tapi produk ini sengaja dibangun **generik** supaya siapa pun dengan masalah yang sama bisa pakai — bukan cuma perusahaan tempat asal ide tersebut, dan bukan cuma untuk developer (product owner, QA manual, dan user bisnis juga harus bisa memahami hasilnya).

**Target kualitas output**: setara dokumen SDD/UAT enterprise yang biasa dipakai di industri (approval workflow, tabel requirement, use case per aktor, activity diagram per fitur) — bagian yang memang bisa diturunkan dari kode (fitur, use case, diagram arsitektur, activity diagram, test case) diisi otomatis; bagian administratif yang tidak mungkin diketahui dari kode (nomor RFC, cost estimation, tanda tangan approval, mockup UI) sengaja dibiarkan sebagai placeholder manual di template.

## Alur Sistem (Arsitektur End-to-End)

```
Source Provider (GitHub OAuth / GitHub PAT / ZIP upload)
        |
        v
Repository Normalizer  ->  Workspace (format seragam, titik ini Parser
        |                   tidak tahu/peduli asal source-nya)
        v
Parser (Tree-sitter, deterministik, TANPA LLM)
        |
        v
ParsedRepoContext.json  ==  Contract A  (Peran 1 -> Peran 2)
        |
        v
LLM (Claude, via Anthropic SDK)  ->  cross-repo mapping (FE fetch <-> BE endpoint)
        |                            + narasi dokumen + script diagram Mermaid
        v
DocumentContent.json  ==  Contract B  (Peran 2 -> Peran 3)
        |
        v
Template Engine (Jinja2, Markdown)  +  Mermaid -> PNG (mermaid.ink)
        |
        v
Pandoc  ->  .docx
        |
        v
Solution Design Document (.docx)  /  UAT Document (.docx)
```

Prinsip desain: setiap tahap dipisah dengan **kontrak JSON** yang jelas (Contract A, Contract B), supaya tim bisa kerja paralel dan tiap tahap bisa diganti tanpa merusak tahap lain (mis. ganti sumber kode dari GitHub ke ZIP tidak menyentuh kode parser; ganti LLM provider tidak menyentuh kode ingestion/parser).

## Tim & Pembagian Kerja

Tim 3 orang, tiap orang pegang satu tahap pipeline:

| Peran | Tanggung Jawab | Status |
|---|---|---|
| **Peran 1 — Ingestion & Parsing** | Ambil source code dari sumber manapun (GitHub OAuth/PAT/ZIP), normalisasi, ekstrak struktur kode pakai Tree-sitter | ✅ Selesai, sudah di `develop` |
| **Peran 2 — AI & Prompt Engineering** | Cross-repo mapping, panggil LLM untuk isi konten dokumen + script diagram Mermaid | ✅ Sudah lengkap — lihat catatan migrasi provider di bawah |
| **Peran 3 — Backend & Templating** | Endpoint FastAPI orkestrator, template Jinja2, ekspor ke `.docx` via Pandoc, frontend | ✅ Sudah ada — pipeline penuh (ingest → parse → LLM → template → docx) sudah tersambung end-to-end lewat `POST /documents/generate` |

Semua tahap sudah terhubung. Sisa pekerjaan yang belum dilakukan (bukan bug, memang belum dikerjakan) ada di bagian **Keterbatasan** di bawah.

## Kontrak JSON Antar-Tahap

### Contract A — `ParsedRepoContext.json` (Peran 1 → Peran 2)

Diimplementasikan di `app/services/parser_service.py` (`build_parsed_repo_context`), deterministik, **tanpa panggilan LLM**. Mendukung Python dan TS/JS/TSX (deteksi endpoint: FastAPI-style Python decorator, Express-style call, method-based TS); bahasa lain jatuh ke entry `"type": "other"` minimal.

```json
{
  "project_name": "...",
  "repositories": [
    {
      "repo_tag": "Backend",
      "files": [
        {
          "file_name": "...",
          "file_path": "...",
          "type": "controller|service|repository|model|ui_component|other",
          "dependencies": ["..."],
          "classes": [
            {"class_name": "...", "methods": [{"method_name": "...", "parameters": ["..."], "return_type": "...", "description": "..."}]}
          ],
          "functions": [
            {"function_name": "...", "parameters": ["..."], "return_type": "...", "description": "..."}
          ],
          "api_endpoints": [
            {"method": "GET|POST|PUT|DELETE", "path": "...", "payload": "..."}
          ]
        }
      ]
    }
  ]
}
```

Catatan: `functions[]` adalah tambahan dari kontrak desain awal (dokumen desain awal cuma punya `classes[]`) — top-level function/standalone function juga diekstrak, bukan cuma method di dalam class.

### Contract B — `DocumentContent.json` (Peran 2 → Peran 3)

Diimplementasikan di `app/services/llm_service.py` (`LLMService.generate_document_content(parsed_repo_context, target_doc_type) -> dict`) via Anthropic Claude (`claude-opus-4-8`) dengan **structured output** (`client.messages.parse(output_format=DocumentContent)` — Pydantic model, bukan parsing JSON manual dari teks).

```json
{
  "document_type": "SDD | UAT",
  "app_description": "...",
  "system_requirements": ["..."],
  "feature_requirements": [
    {"feature_name": "...", "description": "..."}
  ],
  "diagrams": {
    "system_architecture": "mermaid graph LR ...",
    "component_integration": "mermaid graph TD ...",
    "use_case_diagram": "mermaid flowchart LR ...",
    "activity_diagrams": [
      {"activity_name": "...", "description": "...", "mermaid_script": "mermaid flowchart TD ..."}
    ]
  },
  "use_cases": [
    {
      "use_case_id": "UC-01",
      "actor": "...",
      "pre_condition": "...",
      "description": "...",
      "acceptance_criteria": ["...", "..."]
    }
  ],
  "business_flow_description": "...",
  "uat_test_cases": [
    {"test_id": "UAT-01", "role": "...", "activity": "...", "steps": "...", "expected_result": "..."}
  ]
}
```

**`target_doc_type` memengaruhi alokasi kedalaman konten** (bukan cuma label): kalau `SDD`, prompt memprioritaskan kedalaman di `diagrams`/`feature_requirements`/`use_cases` dan `uat_test_cases` cukup representatif; kalau `UAT`, prompt memprioritaskan `uat_test_cases` yang exhaustive (idealnya satu per endpoint/fitur utama) sementara `diagrams`/`use_cases` cukup ringkas. Sudah diverifikasi lewat pemanggilan API sungguhan (bukan cuma baca prompt-nya) — lihat bagian Riwayat Perubahan.

**`app_description`, `feature_requirements[].description`, `use_cases[].description`, dan `business_flow_description` wajib ditulis untuk pembaca non-teknis** (product owner, QA manual, user bisnis) — ini prinsip eksplisit di system prompt `llm_service.py`, konsisten dengan positioning produk sebagai SaaS untuk berbagai kalangan, bukan cuma developer.

## Struktur Proyek

```
app/
  domain/            # data murni + interface (SourceProvider), tanpa dependency framework
    models.py, ports.py, exceptions.py
  ingestion/         # implementasi SourceProvider
    filters.py               # daftar ekstensi/dir yang di-skip (node_modules, venv, dll)
    provider_factory.py      # pilih provider (GitHub / ZIP) berdasarkan SourceType
    providers/github_provider.py, providers/zip_provider.py
  services/
    ingestion_service.py     # orkestrasi ingest -> Workspace (Peran 1)
    parser_service.py        # Tree-sitter structural extraction, Contract A (Peran 1)
    github_oauth_service.py  # OAuth GitHub scaffold (Peran 1)
    llm_service.py           # LLMService, Contract A -> Contract B via Claude (Peran 2)
    compiler_service.py      # Contract B -> render Mermaid -> Jinja2 -> .docx (Peran 3)
  api/
    routes_ingestion.py      # POST /ingest/github, POST /ingest/zip
    routes_auth.py           # GET /auth/github/login, GET /auth/github/callback
    routes_document.py       # POST /documents/sdd, /documents/uat, /documents/generate
    schemas.py, schemas_document.py
  templates/
    sdd_template.md, uat_template.md   # template Jinja2 (Markdown) sebelum dikonversi ke docx
  core/config.py             # baca .env (ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_CLIENT_*)
  main.py                    # entrypoint FastAPI, CORS, daftar router

frontend/                    # React + Vite, form sederhana yang hit POST /documents/generate
  src/App.jsx, src/main.jsx

tests/                       # pytest — lihat bagian Testing
dummy_data/                  # fixture JSON untuk testing manual tanpa perlu repo asli
```

## Tech Stack

- **Backend**: Python + FastAPI + Uvicorn
- **Ingestion**: PyGithub (GitHub OAuth/PAT), ZIP upload in-memory (dengan guard anti zip-bomb)
- **Parsing**: `tree-sitter` + `tree-sitter-language-pack` — AST-based, generik multi-bahasa (bukan regex, bukan LLM)
- **LLM**: **Anthropic Claude** (`claude-opus-4-8`) via official `anthropic` Python SDK, dipanggil langsung (bukan lewat LangChain)
- **Templating & Export**: Jinja2 (Markdown) → Pandoc (`pypandoc`) → `.docx`
- **Diagram**: Mermaid.js — script-nya digenerate LLM, dirender ke PNG lewat layanan hosted `mermaid.ink` (lihat catatan privasi & keterbatasan di bawah)
- **Frontend**: React + Vite (SPA sederhana, satu form)
- **Testing**: `pytest`

## Environment Variables (`.env`, contoh di `.env.example`)

| Variable | Wajib? | Keterangan |
|---|---|---|
| `ANTHROPIC_API_KEY` | Ya (untuk fitur LLM / Peran 2) | https://console.anthropic.com/settings/keys |
| `GITHUB_TOKEN` | Opsional | PAT untuk akses repo privat lewat endpoint ingest berbasis PAT. Repo publik tetap bisa tanpa token, cuma rate-limited 60 req/jam. |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_OAUTH_REDIRECT_URI` | Opsional | Cuma perlu kalau mau flow OAuth GitHub beneran jalan (perlu GitHub OAuth App terdaftar — belum ada saat ini, lihat Keterbatasan). |

## Setup Lokal

```bash
# 1. Buat & aktifkan virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# atau: source venv/bin/activate   # macOS/Linux

# 2. Install dependency Python
pip install -r requirements.txt

# 3. Pandoc wajib ada di sistem untuk fitur export .docx
#    (kalau belum ada, jalankan sekali):
python -c "import pypandoc; pypandoc.download_pandoc()"

# 4. Isi .env (copy dari .env.example, isi ANTHROPIC_API_KEY minimal)
cp .env.example .env

# 5. Install dependency frontend
cd frontend
npm install
cd ..
```

## Menjalankan Aplikasi

```bash
# Backend (dari root project)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# -> Swagger UI: http://127.0.0.1:8000/docs

# Frontend (terminal terpisah)
cd frontend
npm run dev
# -> http://127.0.0.1:5173
```

Frontend hardcode `API_BASE_URL = http://localhost:8000` (lihat `frontend/src/App.jsx`) — kalau backend dijalankan di port lain, port di file itu perlu disesuaikan manual.

### Daftar Endpoint

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/ingest/github` | Ingest repo dari GitHub (OAuth token atau PAT) -> `Workspace` |
| `POST` | `/ingest/zip` | Ingest repo dari file ZIP yang di-upload -> `Workspace` |
| `GET` | `/auth/github/login` | Mulai flow OAuth GitHub (scaffold, belum bisa dipakai sungguhan — lihat Keterbatasan) |
| `GET` | `/auth/github/callback` | Callback OAuth GitHub |
| `POST` | `/documents/sdd` | Terima `DocumentContent` (Contract B) langsung, render jadi SDD `.docx` — untuk testing template tanpa perlu ingest+LLM |
| `POST` | `/documents/uat` | Sama seperti di atas, untuk UAT `.docx` |
| `POST` | `/documents/generate` | **Endpoint utama** — orkestrator penuh: ingest -> parse -> LLM -> compile, satu request, langsung dapat file `.docx` |

## Testing

```bash
pytest
```

Semua test yang ada (`tests/test_compiler_service.py`, `tests/test_routes_document.py`) **selalu mock** pemanggilan LLM (Claude) dan Mermaid.ink — supaya test tidak bergantung pada koneksi internet, API key, atau kuota, dan tidak pernah mengeluarkan biaya API secara tidak sengaja. **Belum ada unit test untuk `parser_service.py` maupun `ingestion_service.py`** (Peran 1) — lihat Keterbatasan.

Untuk testing manual end-to-end (hit API sungguhan, termasuk panggilan LLM yang sesungguhnya) — **lakukan ini hanya saat memang sedang sengaja menguji**, jangan jadikan kebiasaan default karena memakai kuota API berbayar:
- `dummy_data/document_content_sdd.json` / `document_content_uat.json` — contoh `DocumentContent` (Contract B) siap pakai untuk `POST /documents/sdd` / `/documents/uat` langsung (tanpa LLM).
- `dummy_data/parsed_repo_context_sample.json` — contoh `ParsedRepoContext` (Contract A) sintetis (aplikasi task-manager kecil, 2 repo: Backend + FE-Web) untuk diumpankan ke `LLMService.generate_document_content(...)` secara manual, kalau ingin menguji kualitas output LLM tanpa perlu ingest dari GitHub sungguhan.

## Keterbatasan yang Diketahui

- **Parser cuma paham Python dan TS/JS/TSX** — bahasa lain perlu ditambahkan kalau dibutuhkan (fallback saat ini: entry `"type": "other"` minimal, tanpa detail class/function/endpoint).
- **Belum divalidasi ke variasi repo publik yang luas** — untuk produk SaaS generik, ini prioritas validasi berikutnya (bukan menunggu akses ke satu repo tertentu).
- **OAuth GitHub baru scaffold** — endpoint-nya ada tapi belum bisa dipakai sungguhan sampai ada GitHub OAuth App terdaftar (`GITHUB_CLIENT_ID`/`SECRET` belum diisi).
- **Belum ada unit test otomatis untuk `parser_service.py` dan `ingestion_service.py`** (Peran 1) — test yang ada baru meng-cover compiler/routes (Peran 3).
- **Cross-repo dependency resolution (FE fetch call <-> BE endpoint) sepenuhnya didelegasikan ke instruksi prompt LLM**, bukan langkah pencocokan deterministik terpisah seperti di diagram arsitektur target (`Cross Repository Mapping` -> `Unified Context` sebelum masuk LLM). Bisa jadi cukup untuk MVP, tapi tidak 100% deterministik.
- **Render diagram Mermaid lewat layanan hosted pihak ketiga (`mermaid.ink`)** — ini mengirim ISI diagram (bisa memuat nama endpoint, struktur komponen internal) ke internet. Untuk data confidential (repo perusahaan) di produksi, sebaiknya diganti rendering lokal (mis. `mermaid-cli`). **Juga ditemukan (2026-07-15): render bisa gagal (`502 Gagal merender diagram`) untuk repo nyata yang menghasilkan diagram besar/kompleks** — dugaan awal terkait panjang URL base64 dari GET request ke mermaid.ink, belum dikonfirmasi/di-fix (diagram sederhana tetap render normal). Kalau menemukan ini lagi, cek dulu apakah scriptnya sangat panjang sebelum menyalahkan koneksi.
- **`LLMService` memakai timeout client 1500 detik (25 menit)** untuk mengantisipasi generation yang lama pada repo besar/kompleks (default SDK 10 menit terbukti kurang untuk repo nyata yang cukup besar saat diuji). Kalau generation tetap sering lambat di masa depan, pertimbangkan pindah ke `.stream()` daripada menaikkan timeout terus-menerus.
- **Frontend (`frontend/src/App.jsx`) masih berupa form dasar tanpa penjelasan** — belum benar-benar dioptimalkan supaya "kalangan manapun" (bukan cuma developer) langsung paham cara pakainya. Prinsip non-teknis sejauh ini baru diterapkan di *isi dokumen yang digenerate* (lewat system prompt LLM), bukan di UI form itu sendiri.
- **Tidak ada hubungan/integrasi dengan project sibling `auto-project-tester`** — keduanya independen. Kalau menjalankan keduanya bersamaan secara lokal, perhatikan **keduanya sama-sama default ke port 8000** untuk backend-nya masing-masing — pastikan tidak salah port sebelum menyimpulkan sesuatu error/berhasil.

## Riwayat Perubahan Penting

- **2026-07-14** — Peran 1 (ingestion multi-source + parser Tree-sitter) selesai & merge ke `develop` (PR #1). Peran 2 versi pertama merge (PR #2), pakai LangChain + Google Gemini (`gemini-2.5-flash`).
- **2026-07-14/15** — Peran 3 (compiler service, template Jinja2, endpoint orkestrator, frontend React+Vite) merge ke `develop` (PR #4, #5) — pipeline penuh `ingest -> parse -> LLM -> template -> docx` tersambung lewat `POST /documents/generate` untuk pertama kali.
- **2026-07-15** — Migrasi provider LLM: **Google Gemini (LangChain) -> Anthropic Claude (`claude-opus-4-8`, SDK resmi langsung)**. Sekaligus memperbaiki bug `target_doc_type` yang sebelumnya tidak berpengaruh ke output (selalu bergaya SDD apa pun tipe dokumennya), dan memperkaya Contract B dengan `feature_requirements[]` dan `use_cases[]` (menutup dua bagian template SDD yang sebelumnya kosong/`(diisi manual)`: "Application Features Requirement" dan tabel Use Case per aktor). Perubahan sudah diverifikasi lewat pemanggilan API sungguhan (bukan cuma mock test), termasuk lewat `POST /documents/generate` terhadap repo asli.
