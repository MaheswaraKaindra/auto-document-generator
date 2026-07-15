# auto-document-generator

> **Baru bergabung / melanjutkan kerja orang lain?** Baca `SESSION.md` dulu — isinya
> apa yang dikerjakan sesi terakhir dan dari mana sebaiknya melanjutkan. File ini
> (CLAUDE.md) adalah pengetahuan permanen tentang produk; `SESSION.md` adalah foto
> sesaat yang **ditimpa habis tiap sesi baru**. Kalau keduanya bertentangan,
> **CLAUDE.md yang benar**.

## Ringkasan

**auto-document-generator** adalah produk **SaaS generik** yang membaca source code dari repo mana pun (GitHub OAuth/PAT, atau ZIP upload — bukan tool internal satu perusahaan) dan otomatis membuat draf dua dokumen yang biasanya ditulis manual oleh developer/QA: **Solution Design Document (SDD)** dan **User Acceptance Test (UAT) Document**, keduanya dalam format `.docx` siap pakai.

## Latar Belakang & Tujuan

Tim development yang bekerja dengan ritme agile/Scrum sering menunda pembuatan dokumen SDD/UAT (atau menulisnya asal-asalan setelah development selesai) karena menulis dokumen ini manual itu lambat dan membosankan — padahal formatnya selalu sama di setiap project, cuma isinya yang beda. Ide awalnya muncul dari pengalaman magang salah satu anggota tim di sebuah perusahaan (melihat bottleneck ini secara langsung), tapi produk ini sengaja dibangun **generik** supaya siapa pun dengan masalah yang sama bisa pakai — bukan cuma perusahaan tempat asal ide tersebut, dan bukan cuma untuk developer (product owner, QA manual, dan user bisnis juga harus bisa memahami hasilnya).

**Target kualitas output**: setara dokumen SDD/UAT enterprise yang biasa dipakai di industri (approval workflow, tabel requirement, use case per aktor, activity diagram per fitur) — bagian yang memang bisa diturunkan dari kode (fitur, use case, diagram arsitektur, activity diagram, test case) diisi otomatis; bagian administratif yang tidak mungkin diketahui dari kode (nomor RFC, cost estimation, tanda tangan approval, mockup UI) sengaja dibiarkan sebagai placeholder manual di template.

**Acuan konkretnya ada**: satu dokumen Solution Design enterprise sungguhan (87 halaman, PDF di root — **di-gitignore karena dokumen internal klien**, jadi tidak ikut ke repo). `app/templates/sdd_template.md` jelas dimodelkan dari dokumen itu. Dibandingkan bab per bab (2026-07-15), strukturnya **sudah cocok hampir seluruhnya** — Revision History, Persetujuan, Deskripsi Aplikasi, Dev System Type, Demografi, System Requirement, How to Access, Infrastructure & Capacity, Application Architecture, Security, Features Requirement, Flow Proses Bisnis, Use Case, Activity Diagram semuanya ada. Yang belum: **Daftar Gambar**, **Daftar Tabel** (mekanis, tinggal dibangkitkan), plus **Mockup Website** dan **Mockup Aplikasi** (mustahil dari kode — kandidat slot upload). **Jadi jarak ke dokumen acuan bukan soal struktur**, melainkan kedalaman (87 halaman vs ~25). Soal placeholder kosong sudah selesai sejak 2026-07-15 — 25 dari 28 penanda `(diisi manual)` kini ditanyakan lewat form (lihat `DocumentMetadata`), sisanya 3 blok tanda tangan/sertifikasi yang memang tidak seharusnya diisi sistem. Catatan penting: panjang bukan ukuran profesional — dokumen acuan panjang sebagian besar karena mockup, timeline proyek, dan tanda tangan. Dokumen 30 halaman yang setiap kalimatnya benar lebih berharga daripada 87 halaman yang separuhnya karangan; justru itu nilai jual produk ini.

## Alur Sistem (Arsitektur End-to-End)

```
Source Provider (GitHub OAuth / GitHub PAT / ZIP upload)
        |
        v
Repository Normalizer  ->  Workspace (format seragam, titik ini Parser
        |                   tidak tahu/peduli asal source-nya)
        v
narrow_to_product()  ->  buang yang bukan produk, berdasarkan manifest repo
        |                (pyproject.toml / package.json). Gagal-membuka:
        |                tidak ketahuan = simpan semua.
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

Diimplementasikan di `app/services/llm_service.py` (`LLMService.generate_document_content(parsed_repo_context, target_doc_type) -> dict`) via Anthropic Claude (model dibaca dari `LLM_MODEL` di `.env`, default `claude-sonnet-5`) dengan **structured output** (`client.messages.parse(output_format=DocumentContent)` — Pydantic model, bukan parsing JSON manual dari teks).

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

**`target_doc_type` memengaruhi alokasi kedalaman konten** (bukan cuma label): kalau `SDD`, prompt memprioritaskan kedalaman di `diagrams`/`feature_requirements`/`use_cases` dan `uat_test_cases` cukup representatif; kalau `UAT`, prompt memprioritaskan `uat_test_cases` yang exhaustive (idealnya satu per endpoint/fitur utama) sementara `diagrams`/`use_cases` cukup ringkas.

Sudah diverifikasi lewat pemanggilan API sungguhan, **termasuk setelah urutan prompt dibalik** (2026-07-15, `target_doc_type` kini muncul sesudah Contract A demi caching): pada `dummy_data`, SDD menghasilkan 5 `uat_test_cases` sementara UAT menghasilkan 9, dengan `feature_requirements`/`use_cases`/`activity_diagrams` yang sama — persis pola yang dijanjikan di atas.

**`app_description`, `feature_requirements[].description`, `use_cases[].description`, dan `business_flow_description` wajib ditulis untuk pembaca non-teknis** (product owner, QA manual, user bisnis) — ini prinsip eksplisit di system prompt `llm_service.py`, konsisten dengan positioning produk sebagai SaaS untuk berbagai kalangan, bukan cuma developer.

### `DocumentMetadata` — isian manusia, BUKAN bagian Contract B

Diimplementasikan di `app/api/schemas_document.py`, masuk lewat `document_metadata` di `GenerateDocumentRequest`, dipakai template sebagai `{{ meta.<field> }}`. Isinya 25 field yang **manusia tahu tapi kode tidak akan pernah tahu**: nomor RFC, No. Solution Design, versi, klasifikasi dokumen, ERP/NON ERP, 7 baris Informasi Demografi, How to Access, Infrastructure & Capacity, 3 remark checklist Security (17 dipakai SDD); Related RFC/Work Order, Change Owner, Prepared/Reviewed By + tanggalnya, Distribution List (8 dipakai UAT).

**Sengaja tidak digabung ke `DocumentContent`.** Contract B itu kontrak *output LLM*; ini *input manusia*. Arahnya berlawanan — LLM tidak boleh mengarang nomor RFC, dan pengguna tidak menulis use case. Menggabungnya akan memaksa LLM mengisi field yang bukan urusannya.

Semua field `Optional`. Yang kosong (termasuk string berisi spasi) jatuh balik ke penanda `*(diisi manual)*` lewat `_MetadataDict.__missing__` di `compiler_service.py` — jadi `document_metadata: null` menghasilkan dokumen persis seperti sebelum form ini ada. Menambah field cukup menyentuh **schema + template**; sengaja tidak ada daftar field ketiga di compiler yang bisa basi diam-diam.

## Struktur Proyek

```
app/
  domain/            # data murni + interface (SourceProvider), tanpa dependency framework
    models.py, ports.py, exceptions.py
  ingestion/         # implementasi SourceProvider
    filters.py               # file mana yang relevan: ekstensi, dir yang di-skip
                             #   (node_modules, venv), dir test/contoh, pola nama file test
    manifest.py              # tanya pyproject.toml/package.json: mana yang produk?
    provider_factory.py      # pilih provider (GitHub / ZIP) berdasarkan SourceType
    providers/github_provider.py, providers/zip_provider.py
  services/
    ingestion_service.py     # orkestrasi ingest -> narrow_to_product -> Workspace (Peran 1)
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

tests/                       # pytest (100 test) — lihat bagian Testing
dummy_data/                  # fixture JSON — dipakai test otomatis DAN testing manual
scripts/                     # utilitas dev, bukan bagian dari aplikasi
  model_getter.py            # cetak daftar model yang tersedia untuk API key kamu
  validation/                # kerangka validasi ke repo publik nyata — lihat Testing
    README.md                #   cara pakai + kenapa ini bukan pengganti pytest
    repos.json               #   10 kasus uji, tiap kasus menguji satu asumsi produk
    run_validation.py        #   harness 2 tahap (gratis / berbayar)
    out/                     #   hasil run (di-gitignore)
```

Root sengaja dijaga cuma berisi file konfigurasi/dokumen (`.env.example`, `.gitignore`, `CLAUDE.md`, `README.md`, `requirements.txt`) — kode dan aset selalu masuk folder. Kalau menambah script utilitas, taruh di `scripts/`, jangan di root.

## Tech Stack

- **Backend**: Python + FastAPI + Uvicorn
- **Ingestion**: PyGithub (GitHub OAuth/PAT), ZIP upload in-memory (dengan guard anti zip-bomb)
- **Parsing**: `tree-sitter` + `tree-sitter-language-pack` — AST-based, generik multi-bahasa (bukan regex, bukan LLM)
- **LLM**: **Anthropic Claude** via official `anthropic` Python SDK, dipanggil langsung (bukan lewat LangChain). Modelnya **bisa diatur** lewat `LLM_MODEL` di `.env` — default `claude-sonnet-5`. Jangan bingung dengan model yang dipakai Claude Code saat mengerjakan repo ini (diatur lewat `/model`): dua-duanya terpisah total.
- **Templating & Export**: Jinja2 (Markdown) → Pandoc (`pypandoc`) → `.docx`
- **Diagram**: Mermaid.js — script-nya digenerate LLM, dirender ke PNG lewat layanan hosted `mermaid.ink` (lihat catatan privasi & keterbatasan di bawah)
- **Frontend**: React + Vite (SPA sederhana, satu form)
- **Testing**: `pytest`

## Environment Variables (`.env`, contoh di `.env.example`)

| Variable | Wajib? | Keterangan |
|---|---|---|
| `ANTHROPIC_API_KEY` | Ya (untuk fitur LLM / Peran 2) | https://console.anthropic.com/settings/keys |
| `LLM_MODEL` | Opsional | Model yang dipakai **aplikasi** untuk menulis dokumen. Kosong = `claude-sonnet-5`. Harga per 1M token (input/output, per 2026-07-15): `claude-sonnet-5` $3/$15 (intro $2/$10 s/d 2026-08-31), `claude-opus-4-8` $5/$25, `claude-haiku-4-5` $1/$5. |
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

# Punya venv dari SEBELUM migrasi Claude (2026-07-15)? Wajib jalankan ulang
# perintah di atas. venv lama tidak punya `anthropic`, dan gejalanya bukan
# test gagal — pytest langsung mati saat collect dengan
# `ModuleNotFoundError: No module named 'anthropic'`, yang gampang disalahartikan
# sebagai migrasinya yang rusak. Paket lama (langchain*, google-genai) juga masih
# menempel dan sudah tidak dipakai; aman dibuang.

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
| `POST` | `/documents/sdd` | Terima `DocumentContent` (Contract B) langsung, render jadi SDD `.docx` — untuk testing template tanpa perlu ingest+LLM. **Tidak menerima `document_metadata`** (body-nya murni Contract B); dokumennya keluar dengan penanda `(diisi manual)` |
| `POST` | `/documents/uat` | Sama seperti di atas, untuk UAT `.docx` |
| `POST` | `/documents/generate` | **Endpoint utama** — orkestrator penuh: ingest -> parse -> LLM -> compile, satu request, langsung dapat file `.docx`. Satu-satunya yang menerima `document_metadata` (isian form, opsional — lihat `DocumentMetadata`) |

## Testing

```bash
pytest
```

100 test, **selalu mock** pemanggilan LLM (Claude), Mermaid.ink, dan GitHub — supaya test tidak bergantung pada koneksi internet, API key, atau kuota, dan tidak pernah mengeluarkan biaya API secara tidak sengaja.

| File | Meng-cover |
|---|---|
| `tests/test_compiler_service.py` | Render Mermaid (encoding pako, batas URL), Jinja2, export docx, metadata dokumen (Peran 3) |
| `tests/test_routes_document.py` | Endpoint `/documents/*` (Peran 3) |
| `tests/test_github_provider.py` | Ingest lewat tarball, pakai tarball sintetis di memori (Peran 1) |
| `tests/test_filters.py` | File mana yang relevan; termasuk penjaga anti-rakus (Peran 1) |
| `tests/test_manifest.py` | Deteksi produk, pakai manifest asli fastapi/flask/requests/express (Peran 1) |
| `tests/test_llm_service.py` | Guard context window: tolak sebelum membayar, pesan yang benar, gagal-membuka (Peran 2) |

**`parser_service.py` masih belum punya test sama sekali** — lihat Keterbatasan.

### Validasi ke repo publik (`scripts/validation/`)

Ini **bukan pengganti `pytest`** dan menjawab pertanyaan yang berbeda:

| | `pytest` | `scripts/validation/` |
|---|---|---|
| Menjawab | "kode sesuai rancangan?" | "rancangan bertahan di repo asing?" |
| LLM & Mermaid | di-mock | sungguhan |
| Biaya | gratis | GitHub API + (opsional) Claude berbayar |

Buktinya keduanya perlu: bug `414` mermaid.ink lolos dari 11 test yang semuanya hijau, justru karena mermaid.ink di-mock.

```bash
python scripts/validation/run_validation.py --list        # daftar kasus
python scripts/validation/run_validation.py               # Tahap 1: ingest+parse, GRATIS
python scripts/validation/run_validation.py --only flask --with-llm   # Tahap 2: BERBAYAR
```

**Tahap 1 gratis** (tanpa LLM) sudah cukup menjawab "parser paham repo ini?" — Contract A-nya disimpan ke `out/` supaya Tahap 2 tidak perlu ingest ulang. **Tahap 2 berbayar**: satu kasus = satu panggilan Claude, wajib opt-in. Baca `scripts/validation/README.md` sebelum menjalankan yang berbayar.

Untuk testing manual end-to-end (hit API sungguhan, termasuk panggilan LLM yang sesungguhnya) — **lakukan ini hanya saat memang sedang sengaja menguji**, jangan jadikan kebiasaan default karena memakai kuota API berbayar:
- `dummy_data/document_content_sdd.json` / `document_content_uat.json` — contoh `DocumentContent` (Contract B) siap pakai untuk `POST /documents/sdd` / `/documents/uat` langsung (tanpa LLM).
- `dummy_data/parsed_repo_context_sample.json` — contoh `ParsedRepoContext` (Contract A) sintetis (aplikasi task-manager kecil, 2 repo: Backend + FE-Web) untuk diumpankan ke `LLMService.generate_document_content(...)` secara manual, kalau ingin menguji kualitas output LLM tanpa perlu ingest dari GitHub sungguhan.

## Keterbatasan yang Diketahui

- **"Dukungan Python" sebenarnya cuma "dukungan Python bergaya FastAPI" — dan ini lubang paling mendesak yang diketahui saat ini** (diukur 2026-07-15, belum diperbaiki). `_python_endpoint_from_decorator` mensyaratkan decorator berbentuk `app.<method>("path")` dengan `<method>` anggota `HTTP_METHODS = {get,post,put,patch,delete}`. Akibatnya: **Flask** (`@app.route("/x", methods=["POST"])` — `route` bukan HTTP method) dan **Django** (route di `urls.py` lewat `path()`, bukan decorator sama sekali) sama-sama menghasilkan **nol endpoint**. Terukur di dua repo: **saleor** (Django, aplikasi e-commerce nyata) 0 endpoint dari 2.573 file; **esteler-app** (Flask, aplikasi milik anggota tim) 0 endpoint padahal `routes/admin.py`, `routes/customer.py`, `routes/auth.py` berisi 32 function yang jelas-jelas view. Ini jauh lebih berat daripada temuan label `type` dulu: pada flask-si-framework, coverage 0% tidak masalah karena LLM bisa menyimpulkan dari nama class. Di sini yang hilang adalah **endpoint itu sendiri** — bahan baku `component_integration` (pemetaan FE↔BE, pembeda utama produk) dan sumber utama `feature_requirements`. Untuk aplikasi bisnis, endpoint *adalah* produknya. Django+Flask menguasai mayoritas aplikasi bisnis Python, jadi ini bukan kasus pinggiran.
- **Parser cuma paham Python dan TS/JS/TSX** — bahasa lain perlu ditambahkan kalau dibutuhkan (fallback saat ini: entry `"type": "other"` minimal, tanpa detail class/function/endpoint).
- **`narrow_to_product()` fail-open di monorepo, dan di monorepo "tidak yakin" itu kasus UMUM** (diukur 2026-07-15 lewat medusa, belum diperbaiki). Deteksi manifest sebelumnya cuma diuji pada repo satu-paket. Monorepo Turborepo menaruh `package.json` di root yang cuma mendeklarasikan workspace — tidak menunjuk ke kode mana pun — sementara paket aslinya di `packages/*/` dengan manifest masing-masing. Terukur: dari 9.459 file relevan medusa, `narrow_to_product` menyaring **0**. Akibatnya `www/` (situs dokumentasi, **2.098 file = 22%**) dan `integration-tests/` ikut terbawa — **bentuk yang sama persis dengan `docs_src/` fastapi** yang dulu bikin SDD menyebut "Manajemen Hero" sebagai fitur produk. Fail-open sendiri tetap keputusan yang benar (filter rakus jauh lebih berbahaya, lihat regresi `samples` di Riwayat), yang perlu ditambah: baca juga manifest di `packages/*/`, bukan cuma yang di root.
- **Diagram `system_architecture` menambahkan komponen yang tidak punya jejak di kode** (ditemukan 2026-07-15 lewat Tahap 2, **belum diperbaiki**). Contract A fastapi punya **nol** dependency database (tidak ada sqlalchemy/sqlmodel/psycopg2 — sudah dicek), tapi diagramnya tetap menggambar `Backend --> Database`. FastAPI itu framework yang sengaja tidak punya lapisan database; kotak itu muncul dari kekosongan. Kelas kesalahannya berbeda dari kasus "Hero": di sana LLM membaca kode nyata tapi kode yang salah (tutorial); di sini tidak ada kode apa pun yang mendasarinya. **Penting — jangan salah baca ini sebagai "diagramnya cuma template".** Dugaan awal itu terbantah oleh realworld pada hari yang sama: di sana diagramnya menulis `Database (PostgreSQL via Prisma)`, dan `prisma` memang benar-benar ada 4x di `dependencies`-nya. Jadi LLM **memang** menurunkan diagram dari kode; masalahnya cuma dia tidak berhenti ketika buktinya tidak ada. Dampaknya ringan untuk mayoritas repo target (aplikasi bisnis biasa memang punya database, jadi tebakannya kebetulan benar) — yang perlu diperbaiki: larang eksplisit menggambar komponen yang tidak punya jejak di `dependencies`.
- **Kualitas `claude-sonnet-5` vs `claude-opus-4-8` untuk tugas ini BELUM diuji.** Default dipindah ke Sonnet 5 pada 2026-07-15 atas keputusan pemilik project, alasannya biaya (Opus ~$1,36/dokumen untuk repo sebesar fastapi; tim menganggap $0,50 sudah mahal). Dasarnya reputasi umum Sonnet 5 yang mendekati Opus, **bukan** perbandingan langsung pada repo nyata — jadi ini asumsi, bukan temuan. Menguji ini murah dan berdampak lama: satu repo × dua model (~$1 sekali bayar) lalu **baca kedua dokumennya**. Kalau kualitasnya turun, ganti balik lewat `LLM_MODEL=claude-opus-4-8` di `.env` (tanpa sentuh kode). Ingat produk ini menjual kualitas dokumen — itu satu-satunya nilainya, jadi jangan biarkan asumsi ini menggantung terlalu lama.
- **Kontaminasi input jauh lebih berbahaya daripada label yang salah** (ditemukan 2026-07-15 lewat Tahap 2; **sudah diperbaiki** lewat deteksi manifest — lihat Riwayat Perubahan. Dicatat di sini karena pelajarannya masih berlaku untuk perubahan berikutnya). Terbukti lewat perbandingan langsung: **flask** (coverage 0%, semua file `"other"`) menghasilkan SDD yang **akurat** — "Flask adalah kerangka kerja pengembangan aplikasi web" dengan fitur Routing/Request-Response/Session/Template yang semuanya benar. Sebaliknya **fastapi** (coverage 63%) menghasilkan SDD yang **percaya diri tapi salah**: "Sistem ini adalah kumpulan aplikasi backend... mengelola data, otentikasi, unggah berkas", dengan fitur "Manajemen Item" dan "Manajemen Hero". FastAPI itu *framework*, dan "Hero" itu contoh dari tutorial SQLModel. Sebabnya: **456 dari 530 file (86%) berasal dari `docs_src/`** — folder tutorial dokumentasi — dan **seluruh 432 endpoint** berasal dari sana, sementara package `fastapi/` yang asli menyumbang **0 endpoint**. Ini kelas bug yang sama dengan `test/` pada express, tapi lewat pintu berbeda: `docs_src` tidak ada di blocklist. Menambahkan `docs_src` cuma menunda masalah — tiap repo mengarang konvensinya sendiri (`test/`, `examples/`, `docs_src/`, `website/`, `playground/`), jadi daftar nama tidak akan pernah lengkap. Arah yang lebih menjanjikan: **tanya repo-nya sendiri apa yang dia kirim** — `pyproject.toml`/`package.json` mendeklarasikan nama package-nya (fastapi menyatakan package-nya `fastapi`), jadi prioritaskan file di bawah situ alih-alih menebak-nebak folder mana yang bukan produk.
- **Heuristik `type` menebak dari nama file, dan gagal pada penamaan idiomatik Python/Go** (ditemukan 2026-07-15 lewat validasi, belum diperbaiki — tapi **prioritasnya rendah**, lihat butir di atas: flask dengan coverage 0% tetap menghasilkan dokumen akurat, jadi label ternyata bukan bottleneck-nya. LLM sanggup menyimpulkan peran file dari nama class, nama function, dan `dependencies` yang tetap dikirim di Contract A). `_guess_file_type()` di `parser_service.py:144` mencocokkan substring nama file (`"controller"`, `"service"`, `"model"`, ...) plus satu sinyal isi (`has_endpoints`). Konsekuensinya diukur pada repo **flask**: coverage **0%** — 25 file semuanya `"other"` — padahal parser sukses menarik 52 class dan 72 function dari repo yang sama. Jadi parsing-nya jalan, **pelabelannya** yang gagal: flask menamai file secara idiomatik (`app.py`, `helpers.py`, `wrappers.py`), bukan bergaya MVC Java/Spring (`UserController.java`). Artinya `coverage` tinggi selama ini menandakan "repo ini kebetulan pakai konvensi penamaan Java", bukan "parser paham repo ini". Diperparah karena yang dibaca cuma `file_name`, bukan path — file di `app/controllers/user.py` tetap `"other"` sebab nama filenya cuma `user.py`. Perbaikan yang mungkin (termurah dulu): (1) ikut membaca path, bukan cuma nama file; (2) tambah sinyal berbasis isi (ada import ORM? ada query SQL? ada render komponen?) seperti `has_endpoints` yang sudah terbukti jalan.
- **Validasi menyentuh 10 repo, tapi masih cuma 3 yang pernah benar-benar jadi dokumen** (flask, fastapi, realworld). Ditambah 2026-07-15: `saleor-django` (Django e-commerce), `medusa-monorepo` (monorepo TS), `esteler-flask` (aplikasi Flask milik anggota tim — satu-satunya kode yang tidak ditulis untuk dipamerkan). Tahap 1 jalan ke semuanya; **Tahap 2 ke aplikasi bisnis masih belum pernah berhasil** — saleor ditolak guard context window (1,2 juta token), medusa juga akan ditolak (Contract A 3,4 MB). `esteler-flask` Contract A-nya cuma 21 KB jadi murah (~$0,01-0,03) — tapi 0 endpoint, jadi yang diuji nanti adalah "seberapa jauh LLM bisa jalan tanpa endpoint", bukan kualitas penuh. `spring-petclinic` ada di daftar tapi Java tidak didukung parser. **Kesimpulannya tidak berubah dan justru menguat: produk ini masih belum pernah menghasilkan satu pun dokumen untuk aplikasi bisnis nyata berbahasa Python.** Penghalangnya sekarang jelas dan bukan lagi soal memilih repo: endpoint Flask/Django tidak terdeteksi (lihat butir pertama).
- **OAuth GitHub baru scaffold** — endpoint-nya ada tapi belum bisa dipakai sungguhan sampai ada GitHub OAuth App terdaftar (`GITHUB_CLIENT_ID`/`SECRET` belum diisi).
- **Belum ada unit test otomatis untuk `parser_service.py`** (Peran 1). Ingestion sudah sebagian ter-cover: `tests/test_github_provider.py` menguji jalur tarball (GitHub di-mock lewat tarball sintetis di memori, tanpa jaringan/token/kuota), tapi `parser_service.py` dan `ingestion_service.py` sendiri masih kosong.
- **Cross-repo dependency resolution (FE fetch call <-> BE endpoint) sepenuhnya didelegasikan ke instruksi prompt LLM**, bukan langkah pencocokan deterministik terpisah seperti di diagram arsitektur target (`Cross Repository Mapping` -> `Unified Context` sebelum masuk LLM). **Terbukti jalan** pada `realworld-fullstack` (2026-07-15 — lihat Riwayat Perubahan), jadi cukup untuk MVP. Tapi karena bersandar pada LLM, hasilnya **tidak dijamin deterministik**: belum diuji pada repo dengan pola pemanggilan API yang tidak lazim (mis. URL dirakit dinamis, atau lewat wrapper client berlapis), dan belum pernah dijalankan dua kali pada repo yang sama untuk melihat apakah pemetaannya konsisten.
- **Render diagram Mermaid lewat layanan hosted pihak ketiga (`mermaid.ink`)** — ini mengirim ISI diagram (bisa memuat nama endpoint, struktur komponen internal) ke internet. Untuk data confidential (repo perusahaan) di produksi, sebaiknya diganti rendering lokal (mis. `mermaid-cli`). Ini satu-satunya keterbatasan mermaid.ink yang tersisa; bug 502 untuk repo besar sudah selesai (lihat Riwayat Perubahan 2026-07-15).
- **Ceiling diagram masih ada, cuma jauh lebih tinggi.** `mermaid.ink` ada di balik reverse proxy dengan batas URL ~8KB (diukur: 7.720 karakter masih `200`, 9.376 karakter sudah `414`). Encoding `pako:` memberi kompresi ~7x, jadi diagram realistis aman — tapi diagram yang sangat ekstrem tetap bisa menembusnya. `_render_mermaid_to_image` sudah memeriksa panjang URL sebelum request dan gagal dengan pesan jelas (`DiagramRenderError`), bukan menghabiskan request percuma.
- **`LLMService` memakai timeout client 1500 detik (25 menit)** untuk mengantisipasi generation yang lama pada repo besar/kompleks (default SDK 10 menit terbukti kurang untuk repo nyata yang cukup besar saat diuji). Kalau generation tetap sering lambat di masa depan, pertimbangkan pindah ke `.stream()` daripada menaikkan timeout terus-menerus.
- **Tabel Revision History masih keluar sebagai baris kosong** (ditemukan 2026-07-15 sesudah form metadata selesai, belum diperbaiki). Tiga tabel — Document Revision History + Application Revision History (SDD), Version History (UAT) — punya header lengkap tapi isinya satu baris kosong `| | | | | |`. Ini **bukan** bagian dari 28 penanda `(diisi manual)` yang sudah ditutup form, jadi luput dari hitungan itu, tapi dampaknya persis sama: dua tabel kosong nongkrong di halaman pertama SDD, tepat di bawah tabel Informasi Dokumen yang sekarang terisi rapi. Sebagian datanya sudah ada di `DocumentMetadata` (`version`, `prepared_by`, `preparation_date`). Yang bikin ini tidak langsung dikerjakan: kolom `Summary of Changes` tidak punya jawaban jujur untuk dokumen yang baru pertama kali digenerate — mengisinya "Dokumen dibuat otomatis dari source code" berarti sistem mengarang riwayat revisi. Perlu keputusan produk dulu, bukan sekadar coding.
- **Belum ada eksekusi asynchronous, dan ini penghalang produksi yang paling diremehkan.** Generation makan ~100-125 detik (terukur pada flask/fastapi/realworld), dan seluruhnya ditahan di satu request HTTP sinkron lewat `POST /documents/generate`. Load balancer, reverse proxy, dan gateway umumnya memutus koneksi di 30-60 detik — jadi ini akan patah begitu di-deploy di belakang infrastruktur apa pun yang wajar, meskipun di localhost terlihat baik-baik saja. Perlu job queue + endpoint polling/webhook sebelum produk ini bisa dipakai orang lain. Berkaitan: **tidak ada database sama sekali** — begitu response terkirim, dokumennya hilang; tidak ada riwayat, tidak bisa unduh ulang.
- **Frontend (`frontend/src/App.jsx`) masih berupa form dasar tanpa penjelasan** — belum benar-benar dioptimalkan supaya "kalangan manapun" (bukan cuma developer) langsung paham cara pakainya. Bagian atas form (nama project, tipe dokumen, token, daftar repo) masih polos: tidak ada penjelasan apa itu `repo_tag`, kenapa butuh token, atau apa bedanya SDD vs UAT. Section "Informasi Dokumen" yang ditambahkan 2026-07-15 sudah punya paragraf pengantar dan field-nya berlabel istilah dokumen (bukan istilah kode), jadi polanya sudah ada — tinggal diterapkan ke bagian atas. Prinsip non-teknis selebihnya masih baru diterapkan di *isi dokumen yang digenerate* (lewat system prompt LLM), bukan di UI.
- **Tidak ada hubungan/integrasi dengan project sibling `auto-project-tester`** — keduanya independen. Kalau menjalankan keduanya bersamaan secara lokal, perhatikan **keduanya sama-sama default ke port 8000** untuk backend-nya masing-masing — pastikan tidak salah port sebelum menyimpulkan sesuatu error/berhasil.

## Riwayat Perubahan Penting

- **2026-07-15** — **Dua bug yang menolak/menyesatkan aplikasi bisnis nyata, ditemukan oleh kasus validasi baru (saleor + medusa).** (1) **Tidak ada guard terhadap Contract A yang melebihi context window.** Terukur: Contract A saleor = **1.226.875 token vs batas 1M** — panggilan berbayar tetap dikirim hanya untuk ditolak API, lalu `except Exception` di `routes_document.py` meratakannya jadi 502 *"Coba lagi beberapa saat"* — saran yang tidak akan pernah menolong karena kegagalannya permanen. **Kelas kesalahan yang sama persis dengan 502 yang dulu menelan 414 mermaid.ink**: sebab spesifik disamarkan jadi ajakan mengulang. Sekarang `_guard_context_window` di `llm_service.py` memeriksa lewat `count_tokens` (gratis) sebelum membayar, dan gagal dengan `ContextWindowExceededError` yang menyebut angka aslinya → HTTP **413**, bukan 502. Batas context window **ditanyakan ke Models API**, tidak di-hardcode (daftar hardcoded pasti basi, dan yang basi diam-diam mengembalikan bug ini); gagal-membuka kalau API tak terjangkau. (2) **Guard anti-bomb mencacah seluruh isi arsip sebelum menyaring relevansi**, jadi monorepo ditolak karena banyak dokumentasi/gambar — bukan karena banyak kode. Terukur di medusa: **22.966 member file, cuma 9.459 relevan (41%), dan cuma 23 MB yang diekstrak** — jauh di bawah batas 200 MB, tapi ditolak di pintu. Filter dinaikkan ke atas pencacah di **kedua** provider (tarball & ZIP punya bug yang sama), dan `MAX_TOTAL_FILES` 5.000 → 20.000 (angka lama warisan dari saat pencacahnya menghitung semua; yang mengikat sebenarnya batas byte, jadi batas memori tidak berubah). Dibuktikan ke repo nyata, bukan cuma test: medusa yang tadinya ditolak sekarang terparse (9.459 file), dan saleor gagal dengan pesan yang benar **tanpa membayar sepeser pun**. 100 test hijau (91 + 9). Biaya sesi: **$0**.
- **2026-07-15** — **Penanda `(diisi manual)` sekarang ditanyakan lewat form: dokumen keluar utuh, bukan berlubang.** Jumlah sebenarnya **28** (18 SDD + 10 UAT), bukan 16 seperti tercatat sebelumnya — hitungan lama cuma mencacah SDD, itu pun melewatkan blok terbesarnya (tabel Demografi, 7 baris), dan UAT tidak dihitung sama sekali. Dari 28: **25 ditutup lewat form** (`DocumentMetadata` di `schemas_document.py` → `document_metadata` di `GenerateDocumentRequest` → `meta.*` di template), **3 sengaja dibiarkan** dan kalimatnya diubah supaya terbaca sebagai desain, bukan lubang kelupaan: dua blok tanda tangan (tanda tangan bukan data yang diketik di form) dan Sertifikasi Keberhasilan UAT (berisi tanggal penyelesaian + hasil Lolos/Gagal — belum ada wujudnya saat generate; menanyakannya di form berarti mengundang orang mensertifikasi tes yang belum jalan). **Semua field opsional**, dan yang kosong jatuh balik ke penanda lama — jadi perilaku sebelumnya adalah *lantai*, bukan langit: form boleh dilewati total, dan repo tanpa konteks enterprise (mis. proyek open-source yang tidak punya nomor RFC) tetap bisa digenerate. Dibuktikan lewat mutation check: hapus satu field mana pun dari 17 field SDD → penandanya balik tepat 1×, lengkap → 0×; jadi pemetaan field↔lubang benar-benar 1:1. 90 test hijau (82 + 8 baru).
- **2026-07-14** — Peran 1 (ingestion multi-source + parser Tree-sitter) selesai & merge ke `develop` (PR #1). Peran 2 versi pertama merge (PR #2), pakai LangChain + Google Gemini (`gemini-2.5-flash`).
- **2026-07-14/15** — Peran 3 (compiler service, template Jinja2, endpoint orkestrator, frontend React+Vite) merge ke `develop` (PR #4, #5) — pipeline penuh `ingest -> parse -> LLM -> template -> docx` tersambung lewat `POST /documents/generate` untuk pertama kali.
- **2026-07-15** — **Cross-repo mapping FE↔BE akhirnya terbukti jalan — pembeda utama produk, dan sampai hari itu belum pernah diuji sama sekali.** Tahap 2 dijalankan ke `realworld-fullstack` (~$0,15, Sonnet 5), aplikasi bisnis nyata (kloningan Medium) dengan bahasa yang didukung parser. `component_integration` menghasilkan pemetaan konkret: `Login.js -> POST /users/login`, `Register.js -> POST /users`, `Home/index.js -> GET /articles`, `Editor.js -> POST /articles`, dst — komponen FE dipetakan ke endpoint BE yang benar, lintas dua repo terpisah. Ini juga menjawab pertanyaan "apakah produk ini diam-diam mengasumsikan setiap repo adalah aplikasi bisnis?": **ya, dan itu tidak masalah** — begitu repo-nya memang aplikasi bisnis, formatnya pas. Aktornya jadi `Guest` dan `Registered User` (bukan `Developer`/`API Client` seperti pada framework), fiturnya bisnis nyata (Autentikasi, Manajemen Artikel, Komentar, Favorit, Follow, Tag), dan namanya dikenali dari kode (`Conduit`). **Pelajaran metodologis: kejanggalan pada dokumen fastapi/flask kemarin itu salah PILIHAN KASUS UJI, bukan cacat produk.** Framework memang tidak punya aktor bisnis. Semua penilaian kualitas sebelumnya diambil dari framework/library — bukan dari target produk yang sebenarnya.
- **2026-07-15** — **Diverifikasi lewat API sungguhan bahwa rantai perbaikan hari ini benar-benar memperbaiki produknya, bukan cuma angkanya** (~$0,41, Sonnet 5). (1) **Caching aktif**: panggilan SDD lalu UAT pada Contract A yang sama → `cache_write=7919 / cache_read=0`, lalu `cache_write=0 / cache_read=7919`; cuma 30 token dibayar penuh. Pada fastapi, `cache_write=63679`. (2) **`target_doc_type` tetap membedakan** setelah urutan prompt dibalik — SDD 5 test case vs UAT 9, sisanya sama. (3) **SDD fastapi sekarang jujur**: dulu "Sistem ini adalah kumpulan aplikasi backend... mengelola data, unggah berkas" dengan fitur "Manajemen Item" dan "Manajemen Hero" (nama tabel dari tutorial SQLModel); sekarang **"FastAPI adalah framework backend berbasis Python"** dengan fitur Routing & Endpoint, Injeksi Dependensi, Validasi Data, Serialisasi, Keamanan, Dokumentasi Otomatis (OpenAPI/Swagger), dan WebSocket — semuanya fitur FastAPI yang sebenarnya, dan tetap ditulis untuk pembaca non-teknis. Contract B-nya disimpan di `scripts/validation/out/` (di-gitignore) supaya bisa dibaca ulang tanpa membayar lagi.
- **2026-07-15** — **Urutan prompt dibalik supaya Contract A bisa di-cache.** Prompt caching itu **cocok-dari-depan** (prefix match): satu byte berbeda membatalkan semua sesudahnya. Versi lama menaruh `target_doc_type` di depan Contract A, jadi ketika repo yang sama diminta SDD lalu UAT, Contract A yang puluhan ribu token itu dibayar **penuh dua kali** padahal isinya identik. Sekarang Contract A duluan (dengan `cache_control` di ujungnya), `target_doc_type` belakangan — panggilan kedua cuma bayar ~10% untuk bagian itu. Determinisme Contract A sudah dibuktikan (parse flask dua kali → sha256 identik; `dependencies` memang `list` yang di-`append`, bukan `set`), jadi cache-nya benar-benar bisa nyantol. `LLMService` sekarang juga mencatat `cache_read`/`cache_write` ke log — tanpa itu, cache yang diam-diam tidak pernah aktif mustahil ketahuan; gejalanya cuma tagihan lebih mahal dari perkiraan. Catatan: minimum cacheable ~2.048 token (Sonnet 5) / 4.096 (Opus 4.8) — prompt kecil tidak akan pernah ter-cache, dan `SYSTEM_PROMPT` sendiri (~2.358 token) terlalu kecil untuk di-cache sendirian di Opus.
- **2026-07-15** — **Deteksi produk dari manifest (`app/ingestion/manifest.py`) menggantikan tebak-tebakan blocklist.** Alih-alih menebak folder mana yang *bukan* produk (permainan yang tidak bisa dimenangkan — `test/` tertangkap, `examples/` lolos, lalu `docs_src/`, lalu `website/`...), sekarang **repo-nya sendiri yang ditanya**: `pyproject.toml` dan `package.json` mendeklarasikan apa yang mereka kirim. Diterapkan di `ingestion_service.narrow_to_product()` — sesudah provider, bukan di dalamnya, karena butuh melihat seluruh repo, dan supaya jalur GitHub & ZIP tunduk pada aturan yang sama. **Hasil pada repo nyata: fastapi 530 -> 49 file**, dan endpoint **432 -> 0** — yang **benar**, karena fastapi si framework *mendefinisikan* `@app.route`, tidak memakainya; 432 tadi semuanya milik tutorial `docs_src/`. Repo yang memang sudah bersih tidak berubah sama sekali (flask 25->25, express 8->8, requests 21->21), jadi deteksinya tidak asal membuang. Biaya input fastapi turun 48% (191.880 -> 60.907 token; ~$0,54 -> ~$0,28 dengan Sonnet 5). Format manifest sangat beragam dan **semua varian di bawah ini diambil dari repo sungguhan, bukan diasumsikan**: fastapi cuma `name = "fastapi"` (package di root); flask `name = "Flask"` huruf besar tapi modulnya `flask` di `src/flask/`; requests `where = ["src"]`; express `files: ["index.js", "lib/"]` (npm menyebut langsung isi paketnya — sinyal terbaik yang ada). **Desainnya sengaja gagal-membuka**: manifest tidak ada/rusak/tidak cocok dengan file mana pun -> simpan SEMUA file. Filter rakus membuang kode produksi diam-diam, dan itu kegagalan yang jauh lebih sulit dilihat daripada kebanyakan noise (lihat regresi `samples` di entri berikutnya).
- **2026-07-15** — **Tahap 2 (berbayar) dijalankan pertama kali: flask + fastapi, SDD.** Tujuannya menjawab satu pertanyaan sebelum menghabiskan waktu memperbaiki heuristik `type`: seberapa parah dampak label `"other"` ke dokumen jadinya? Jawabannya: **tidak parah — label bukan bottleneck**. flask (coverage 0%) menghasilkan 11 fitur yang akurat, malah lebih banyak dari fastapi (coverage 63%) yang cuma 10 dan isinya salah. Ini menghemat kerja berhari-hari yang nyaris dilakukan ke masalah yang ternyata tidak ada. Sekaligus mengungkap masalah yang jauh lebih penting — kontaminasi input `docs_src/`, lihat Keterbatasan. Pipeline penuh terbukti jalan ke repo nyata: 8 diagram Mermaid ter-embed di SDD flask (bukti encoding pako jalan end-to-end), generation ~103-109 detik per dokumen. Biaya: 2 panggilan Claude. **Pelajaran metodologis: ukur dulu sebelum memperbaiki.**
- **2026-07-15** — **Kerangka validasi dibuat (`scripts/validation/`) dan langsung berbuah.** Dua tahap dipisah berdasarkan biaya: Tahap 1 (`ingest -> parse`, gratis, tanpa LLM) dan Tahap 2 (`--with-llm`, berbayar, opt-in). Menjawab pertanyaan yang tidak bisa dijawab `pytest`: bukan "apakah kode sesuai rancangan?" tapi "apakah rancangan bertahan di repo asing?". Tiga temuan dari 7 repo publik: (1) ingestion 1-request-per-file (sudah diperbaiki, lihat entri berikutnya); (2) kode test & contoh ikut ter-ingest — pada express, **1169 dari 1265 endpoint ternyata berasal dari `test/`**, Contract A menyusut 99.5 KB -> 4.3 KB setelah disaring (sudah diperbaiki, lihat `filters.py`); (3) heuristik `type` gagal pada penamaan idiomatik Python (**belum** diperbaiki, lihat Keterbatasan). Catatan: metrik `coverage` di harness masih cacat — `flask 0%` (kode terbaca tapi salah label) dan `gin-go 0%` (kode sama sekali tidak terbaca) tampil identik padahal butuh perbaikan yang berbeda.
- **2026-07-15** — **Ingestion GitHub pindah dari per-file ke tarball sekali unduh.** `github_provider.py` dulu memanggil `get_git_blob()` **satu request per file**, jadi repo 200 file = 200 request berurutan. Akibatnya batas anonim GitHub (60 request/jam) habis sebelum satu repo pun selesai — mencoba `express` (repo kecil) menghabiskan seluruh jatah lalu menggantung >7 menit tanpa sebab yang kelihatan. Sekarang repo diunduh sebagai tarball dalam **satu** request lalu dibongkar di memori, jadi biaya API turun dari ~N request (N = jumlah file) jadi ~2 per repo, konstan berapa pun ukuran reponya. Guard anti archive-bomb dipindah ke `filters.py` supaya jalur ZIP dan tarball tunduk pada batas yang sama. Ditemukan oleh kerangka validasi di `scripts/validation/` pada percobaan perdananya.
- **2026-07-15** — **Bug render diagram untuk repo besar selesai.** Gejalanya dulu tercatat sebagai "502 Gagal merender diagram" dan diduga soal panjang URL. Dugaan itu benar soal akar masalahnya, tapi 502-nya menyesatkan: itu **pesan error aplikasi sendiri**. `_render_docx_or_502` meratakan SEMUA `requests.RequestException` jadi 502 "layanan tidak merespons" — padahal `raise_for_status()` melempar `HTTPError` (subclass-nya) saat mermaid.ink membalas **`414 URI Too Long`**. Jadi mermaid.ink sebetulnya menjawab dengan jelas, cuma jawabannya ditelan error handler kita. Diperbaiki tiga lapis: (1) encoding `pako:` (zlib) menggantikan base64 polos — kompresi ~7x, diagram 120-node turun dari 9.376 jadi 1.273 karakter URL; (2) `DiagramRenderError` membawa sebab asli (status HTTP + artinya) alih-alih menyamarkannya; (3) code fence ```` ```mermaid ```` dari LLM dibuang otomatis (dulu bikin `400`). Semua angka di atas diukur langsung ke mermaid.ink, bukan diperkirakan.
- **2026-07-15** — Migrasi provider LLM: **Google Gemini (LangChain) -> Anthropic Claude (`claude-opus-4-8`, SDK resmi langsung)**. Sekaligus memperbaiki bug `target_doc_type` yang sebelumnya tidak berpengaruh ke output (selalu bergaya SDD apa pun tipe dokumennya), dan memperkaya Contract B dengan `feature_requirements[]` dan `use_cases[]` (menutup dua bagian template SDD yang sebelumnya kosong/`(diisi manual)`: "Application Features Requirement" dan tabel Use Case per aktor). Perubahan sudah diverifikasi lewat pemanggilan API sungguhan (bukan cuma mock test), termasuk lewat `POST /documents/generate` terhadap repo asli.
