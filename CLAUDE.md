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
dummy_data/                  # fixture JSON — dipakai test otomatis DAN testing manual
scripts/                     # utilitas dev sekali-pakai, bukan bagian dari aplikasi
  model_getter.py            # cetak daftar model yang tersedia untuk API key kamu
```

Root sengaja dijaga cuma berisi file konfigurasi/dokumen (`.env.example`, `.gitignore`, `CLAUDE.md`, `README.md`, `requirements.txt`) — kode dan aset selalu masuk folder. Kalau menambah script utilitas, taruh di `scripts/`, jangan di root.

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
- **Kontaminasi input jauh lebih berbahaya daripada label yang salah — dan blocklist nama folder adalah permainan yang tidak bisa dimenangkan** (ditemukan 2026-07-15 lewat Tahap 2, **belum diperbaiki**). Terbukti lewat perbandingan langsung: **flask** (coverage 0%, semua file `"other"`) menghasilkan SDD yang **akurat** — "Flask adalah kerangka kerja pengembangan aplikasi web" dengan fitur Routing/Request-Response/Session/Template yang semuanya benar. Sebaliknya **fastapi** (coverage 63%) menghasilkan SDD yang **percaya diri tapi salah**: "Sistem ini adalah kumpulan aplikasi backend... mengelola data, otentikasi, unggah berkas", dengan fitur "Manajemen Item" dan "Manajemen Hero". FastAPI itu *framework*, dan "Hero" itu contoh dari tutorial SQLModel. Sebabnya: **456 dari 530 file (86%) berasal dari `docs_src/`** — folder tutorial dokumentasi — dan **seluruh 432 endpoint** berasal dari sana, sementara package `fastapi/` yang asli menyumbang **0 endpoint**. Ini kelas bug yang sama dengan `test/` pada express, tapi lewat pintu berbeda: `docs_src` tidak ada di blocklist. Menambahkan `docs_src` cuma menunda masalah — tiap repo mengarang konvensinya sendiri (`test/`, `examples/`, `docs_src/`, `website/`, `playground/`), jadi daftar nama tidak akan pernah lengkap. Arah yang lebih menjanjikan: **tanya repo-nya sendiri apa yang dia kirim** — `pyproject.toml`/`package.json` mendeklarasikan nama package-nya (fastapi menyatakan package-nya `fastapi`), jadi prioritaskan file di bawah situ alih-alih menebak-nebak folder mana yang bukan produk.
- **Heuristik `type` menebak dari nama file, dan gagal pada penamaan idiomatik Python/Go** (ditemukan 2026-07-15 lewat validasi, belum diperbaiki — tapi **prioritasnya rendah**, lihat butir di atas: flask dengan coverage 0% tetap menghasilkan dokumen akurat, jadi label ternyata bukan bottleneck-nya. LLM sanggup menyimpulkan peran file dari nama class, nama function, dan `dependencies` yang tetap dikirim di Contract A). `_guess_file_type()` di `parser_service.py:144` mencocokkan substring nama file (`"controller"`, `"service"`, `"model"`, ...) plus satu sinyal isi (`has_endpoints`). Konsekuensinya diukur pada repo **flask**: coverage **0%** — 25 file semuanya `"other"` — padahal parser sukses menarik 52 class dan 72 function dari repo yang sama. Jadi parsing-nya jalan, **pelabelannya** yang gagal: flask menamai file secara idiomatik (`app.py`, `helpers.py`, `wrappers.py`), bukan bergaya MVC Java/Spring (`UserController.java`). Artinya `coverage` tinggi selama ini menandakan "repo ini kebetulan pakai konvensi penamaan Java", bukan "parser paham repo ini". Diperparah karena yang dibaca cuma `file_name`, bukan path — file di `app/controllers/user.py` tetap `"other"` sebab nama filenya cuma `user.py`. Perbaikan yang mungkin (termurah dulu): (1) ikut membaca path, bukan cuma nama file; (2) tambah sinyal berbasis isi (ada import ORM? ada query SQL? ada render komponen?) seperti `has_endpoints` yang sudah terbukti jalan.
- **Belum divalidasi ke variasi repo publik yang luas** — untuk produk SaaS generik, ini prioritas validasi berikutnya (bukan menunggu akses ke satu repo tertentu).
- **OAuth GitHub baru scaffold** — endpoint-nya ada tapi belum bisa dipakai sungguhan sampai ada GitHub OAuth App terdaftar (`GITHUB_CLIENT_ID`/`SECRET` belum diisi).
- **Belum ada unit test otomatis untuk `parser_service.py`** (Peran 1). Ingestion sudah sebagian ter-cover: `tests/test_github_provider.py` menguji jalur tarball (GitHub di-mock lewat tarball sintetis di memori, tanpa jaringan/token/kuota), tapi `parser_service.py` dan `ingestion_service.py` sendiri masih kosong.
- **Cross-repo dependency resolution (FE fetch call <-> BE endpoint) sepenuhnya didelegasikan ke instruksi prompt LLM**, bukan langkah pencocokan deterministik terpisah seperti di diagram arsitektur target (`Cross Repository Mapping` -> `Unified Context` sebelum masuk LLM). Bisa jadi cukup untuk MVP, tapi tidak 100% deterministik.
- **Render diagram Mermaid lewat layanan hosted pihak ketiga (`mermaid.ink`)** — ini mengirim ISI diagram (bisa memuat nama endpoint, struktur komponen internal) ke internet. Untuk data confidential (repo perusahaan) di produksi, sebaiknya diganti rendering lokal (mis. `mermaid-cli`). Ini satu-satunya keterbatasan mermaid.ink yang tersisa; bug 502 untuk repo besar sudah selesai (lihat Riwayat Perubahan 2026-07-15).
- **Ceiling diagram masih ada, cuma jauh lebih tinggi.** `mermaid.ink` ada di balik reverse proxy dengan batas URL ~8KB (diukur: 7.720 karakter masih `200`, 9.376 karakter sudah `414`). Encoding `pako:` memberi kompresi ~7x, jadi diagram realistis aman — tapi diagram yang sangat ekstrem tetap bisa menembusnya. `_render_mermaid_to_image` sudah memeriksa panjang URL sebelum request dan gagal dengan pesan jelas (`DiagramRenderError`), bukan menghabiskan request percuma.
- **`LLMService` memakai timeout client 1500 detik (25 menit)** untuk mengantisipasi generation yang lama pada repo besar/kompleks (default SDK 10 menit terbukti kurang untuk repo nyata yang cukup besar saat diuji). Kalau generation tetap sering lambat di masa depan, pertimbangkan pindah ke `.stream()` daripada menaikkan timeout terus-menerus.
- **Frontend (`frontend/src/App.jsx`) masih berupa form dasar tanpa penjelasan** — belum benar-benar dioptimalkan supaya "kalangan manapun" (bukan cuma developer) langsung paham cara pakainya. Prinsip non-teknis sejauh ini baru diterapkan di *isi dokumen yang digenerate* (lewat system prompt LLM), bukan di UI form itu sendiri.
- **Tidak ada hubungan/integrasi dengan project sibling `auto-project-tester`** — keduanya independen. Kalau menjalankan keduanya bersamaan secara lokal, perhatikan **keduanya sama-sama default ke port 8000** untuk backend-nya masing-masing — pastikan tidak salah port sebelum menyimpulkan sesuatu error/berhasil.

## Riwayat Perubahan Penting

- **2026-07-14** — Peran 1 (ingestion multi-source + parser Tree-sitter) selesai & merge ke `develop` (PR #1). Peran 2 versi pertama merge (PR #2), pakai LangChain + Google Gemini (`gemini-2.5-flash`).
- **2026-07-14/15** — Peran 3 (compiler service, template Jinja2, endpoint orkestrator, frontend React+Vite) merge ke `develop` (PR #4, #5) — pipeline penuh `ingest -> parse -> LLM -> template -> docx` tersambung lewat `POST /documents/generate` untuk pertama kali.
- **2026-07-15** — **Tahap 2 (berbayar) dijalankan pertama kali: flask + fastapi, SDD.** Tujuannya menjawab satu pertanyaan sebelum menghabiskan waktu memperbaiki heuristik `type`: seberapa parah dampak label `"other"` ke dokumen jadinya? Jawabannya: **tidak parah — label bukan bottleneck**. flask (coverage 0%) menghasilkan 11 fitur yang akurat, malah lebih banyak dari fastapi (coverage 63%) yang cuma 10 dan isinya salah. Ini menghemat kerja berhari-hari yang nyaris dilakukan ke masalah yang ternyata tidak ada. Sekaligus mengungkap masalah yang jauh lebih penting — kontaminasi input `docs_src/`, lihat Keterbatasan. Pipeline penuh terbukti jalan ke repo nyata: 8 diagram Mermaid ter-embed di SDD flask (bukti encoding pako jalan end-to-end), generation ~103-109 detik per dokumen. Biaya: 2 panggilan Claude. **Pelajaran metodologis: ukur dulu sebelum memperbaiki.**
- **2026-07-15** — **Kerangka validasi dibuat (`scripts/validation/`) dan langsung berbuah.** Dua tahap dipisah berdasarkan biaya: Tahap 1 (`ingest -> parse`, gratis, tanpa LLM) dan Tahap 2 (`--with-llm`, berbayar, opt-in). Menjawab pertanyaan yang tidak bisa dijawab `pytest`: bukan "apakah kode sesuai rancangan?" tapi "apakah rancangan bertahan di repo asing?". Tiga temuan dari 7 repo publik: (1) ingestion 1-request-per-file (sudah diperbaiki, lihat entri berikutnya); (2) kode test & contoh ikut ter-ingest — pada express, **1169 dari 1265 endpoint ternyata berasal dari `test/`**, Contract A menyusut 99.5 KB -> 4.3 KB setelah disaring (sudah diperbaiki, lihat `filters.py`); (3) heuristik `type` gagal pada penamaan idiomatik Python (**belum** diperbaiki, lihat Keterbatasan). Catatan: metrik `coverage` di harness masih cacat — `flask 0%` (kode terbaca tapi salah label) dan `gin-go 0%` (kode sama sekali tidak terbaca) tampil identik padahal butuh perbaikan yang berbeda.
- **2026-07-15** — **Ingestion GitHub pindah dari per-file ke tarball sekali unduh.** `github_provider.py` dulu memanggil `get_git_blob()` **satu request per file**, jadi repo 200 file = 200 request berurutan. Akibatnya batas anonim GitHub (60 request/jam) habis sebelum satu repo pun selesai — mencoba `express` (repo kecil) menghabiskan seluruh jatah lalu menggantung >7 menit tanpa sebab yang kelihatan. Sekarang repo diunduh sebagai tarball dalam **satu** request lalu dibongkar di memori, jadi biaya API turun dari ~N request (N = jumlah file) jadi ~2 per repo, konstan berapa pun ukuran reponya. Guard anti archive-bomb dipindah ke `filters.py` supaya jalur ZIP dan tarball tunduk pada batas yang sama. Ditemukan oleh kerangka validasi di `scripts/validation/` pada percobaan perdananya.
- **2026-07-15** — **Bug render diagram untuk repo besar selesai.** Gejalanya dulu tercatat sebagai "502 Gagal merender diagram" dan diduga soal panjang URL. Dugaan itu benar soal akar masalahnya, tapi 502-nya menyesatkan: itu **pesan error aplikasi sendiri**. `_render_docx_or_502` meratakan SEMUA `requests.RequestException` jadi 502 "layanan tidak merespons" — padahal `raise_for_status()` melempar `HTTPError` (subclass-nya) saat mermaid.ink membalas **`414 URI Too Long`**. Jadi mermaid.ink sebetulnya menjawab dengan jelas, cuma jawabannya ditelan error handler kita. Diperbaiki tiga lapis: (1) encoding `pako:` (zlib) menggantikan base64 polos — kompresi ~7x, diagram 120-node turun dari 9.376 jadi 1.273 karakter URL; (2) `DiagramRenderError` membawa sebab asli (status HTTP + artinya) alih-alih menyamarkannya; (3) code fence ```` ```mermaid ```` dari LLM dibuang otomatis (dulu bikin `400`). Semua angka di atas diukur langsung ke mermaid.ink, bukan diperkirakan.
- **2026-07-15** — Migrasi provider LLM: **Google Gemini (LangChain) -> Anthropic Claude (`claude-opus-4-8`, SDK resmi langsung)**. Sekaligus memperbaiki bug `target_doc_type` yang sebelumnya tidak berpengaruh ke output (selalu bergaya SDD apa pun tipe dokumennya), dan memperkaya Contract B dengan `feature_requirements[]` dan `use_cases[]` (menutup dua bagian template SDD yang sebelumnya kosong/`(diisi manual)`: "Application Features Requirement" dan tabel Use Case per aktor). Perubahan sudah diverifikasi lewat pemanggilan API sungguhan (bukan cuma mock test), termasuk lewat `POST /documents/generate` terhadap repo asli.
