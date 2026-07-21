# auto-document-generator

**Baca source code sebuah repo, keluarkan draf Solution Design Document (SDD) dan
User Acceptance Test (UAT) dalam `.docx` yang siap diedit.**

Tunjuk ke repo GitHub **atau** upload ZIP source code, pilih SDD atau UAT, tunggu
~2-3 menit, unduh dokumennya.

> **Baru bergabung di tim ini?** Loncat ke [Mulai dari mana](#mulai-dari-mana-untuk-kontributor-baru)
> di bawah. Dokumen ini cukup untuk memahami *apa* dan *kenapa*; detail teknis tiap
> keputusan ada di [`CLAUDE.md`](CLAUDE.md).

---

## Daftar isi

- [Kenapa ini ada](#kenapa-ini-ada)
- [Prinsipnya: lebih baik pendek dan benar](#prinsipnya-lebih-baik-pendek-dan-benar)
- [Apa yang dihasilkan](#apa-yang-dihasilkan)
- [Cara kerja (arsitektur end-to-end)](#cara-kerja-arsitektur-end-to-end)
- [Peta struktur proyek](#peta-struktur-proyek)
- [Tiga tahap pipeline (pembagian kerja)](#tiga-tahap-pipeline-pembagian-kerja)
- [Setup](#setup)
- [Menjalankan](#menjalankan)
- [Endpoint utama](#endpoint-utama)
- [Testing](#testing)
- [Mulai dari mana (untuk kontributor baru)](#mulai-dari-mana-untuk-kontributor-baru)
- [Batas yang diketahui](#batas-yang-diketahui)
- [Status](#status)
- [Dokumen pendukung](#dokumen-pendukung)

---

## Kenapa ini ada

Tim yang bekerja dengan ritme agile sering menunda dokumen SDD/UAT — atau
menulisnya asal-asalan setelah development selesai. Alasannya bukan karena
dokumennya tidak penting, tapi karena menulisnya manual itu lambat dan
membosankan: **formatnya selalu sama di tiap project, cuma isinya yang beda.**

Yang terjadi kalau bagian membosankan itu ditulis manual, kami ukur langsung dari
satu Solution Design enterprise sungguhan setebal **87 halaman** yang jadi acuan
produk ini (dokumen internal klien — sengaja tidak ikut ke repo):

- **Daftar Gambar-nya menyebut aplikasi yang sama sekali lain** di seluruh
  entrinya — sisa copy-paste dari dokumen sebelumnya yang tidak pernah
  diperbarui. Badan dokumennya benar; daftarnya membusuk.
- **Daftar Tabel-nya** punya nomor yang lompat dan dobel, dan ikut menyebut
  aplikasi lama itu.

Itu bukan kecerobohan penulisnya. Itu yang terjadi ketika manusia menyusun 87
halaman dengan tenggat: **bagian yang mekanis adalah bagian yang pertama
membusuk**, justru karena tidak ada yang memeriksanya.

Bagian mekanis itu persisnya yang bisa diturunkan dari kode.

## Prinsipnya: lebih baik pendek dan benar

Dokumen 30 halaman yang setiap kalimatnya benar lebih berharga daripada 87
halaman yang separuhnya karangan. Dokumen yang terdengar meyakinkan tapi salah
lebih buruk daripada tidak ada — dia memaksa pembacanya memeriksa tiap baris, dan
itu lebih lambat daripada menulis sendiri.

Karena itu produk ini memisahkan tegas:

| | |
|---|---|
| **Diisi otomatis dari kode** | Deskripsi aplikasi, daftar fitur, use case per aktor, tabel endpoint, diagram arsitektur, diagram integrasi komponen, activity diagram, test case UAT |
| **Ditanyakan lewat form** | Nomor RFC, versi, klasifikasi dokumen, informasi demografi, infrastructure & capacity, security remark, distribution list — hal yang manusia tahu tapi kode tidak akan pernah tahu (semuanya opsional) |
| **Sengaja dibiarkan kosong** | Blok tanda tangan, sertifikasi hasil UAT, mockup UI — hal yang sistem tidak boleh mengarangnya |

Yang tidak punya jejak di kode **tidak ditulis**. Diagram tidak menggambar
komponen yang tidak ada bekasnya di `dependencies` atau di docstring. **Itu nilai
jual utama produk ini** — bukan panjang dokumennya, tapi bahwa isinya bisa
dipercaya.

## Apa yang dihasilkan

**SDD** (`.docx`): Informasi Dokumen · Revision History · Persetujuan · Deskripsi
Aplikasi · Dev System Type · Informasi Demografi · System Requirement · How to
Access · Infrastructure & Capacity · Application Architecture · Application
Security · Features Requirement · Flow Proses Bisnis · Use Case · Activity Diagram

**UAT** (`.docx`): Informasi Dokumen · Distribution List · Version History ·
Rencana UAT · Sertifikasi · Prosedur Pengujian · Ringkasan Aplikasi · Case Pengujian

Diagramnya UML sungguhan (PlantUML — aktor stick-figure, oval use case, activity
ber-start/end) yang ter-embed sebagai gambar, dirender **lokal** — isi diagram
tidak pernah meninggalkan mesin.

**Gaya dokumen bisa dipilih** lewat `template_id`:

- `default` — gaya acuan enterprise (header tabel hitam).
- `premco` — meniru konvensi dokumen PREMCO/Pertamina (tabel use case biru
  menyatu). Menyediakan SDD **dan** UAT.
- **template hasil upload sendiri** — unggah `.docx` template perusahaan lewat
  `POST /templates`, sistem mengukur gayanya (font, tabel, struktur bab) dan
  mendaftarkannya sebagai gaya baru (fitur "V2", masih berkembang).

Contoh nyata — dari repo publik, bukan contoh buatan:

| Repo | Bahasa | Hasil |
|---|---|---|
| esteler-app (kedai online, Flask) | Python | 22 file → **38 endpoint** terdeteksi; deskripsi + ~11 fitur + use case per aktor (**Admin & Customer**); arsitektur berjejak (PostgreSQL/Neon, Cloudinary, Groq) |
| spring-petclinic | Java | 17 endpoint; aktor **Staff Klinik & Pengunjung** |
| realworld (2 repo) | TS/JS | Komponen frontend dipetakan ke endpoint backend, lintas dua repo terpisah |

Aktornya bisnis, bukan "Developer"/"API Client" — itu penanda bahwa isinya
diturunkan dari aplikasinya, bukan dari nama file.

## Cara kerja (arsitektur end-to-end)

```
GitHub (OAuth/PAT) atau ZIP upload
        |
        v
Normalizer  ->  Workspace (format seragam)
        |
        v
narrow_to_product()   tanya pyproject.toml / package.json: mana yang produk?
        |
        v
Parser (Tree-sitter, deterministik, TANPA LLM)  ->  ParsedRepoContext.json   [Contract A]
        |
        v
LLM (Claude)  ->  narasi + script diagram PlantUML  ->  DocumentContent.json  [Contract B]
        |
        v
Jinja2 (Markdown) + PlantUML->PNG (lokal)  ->  Pandoc  ->  .docx
```

Tiap tahap dipisah **kontrak JSON** yang jelas (Contract A, Contract B), jadi
sumber kode bisa diganti tanpa menyentuh parser, dan LLM bisa diganti tanpa
menyentuh ingestion. Isi tiap kontrak dan alasan tiap keputusan ada di
[`CLAUDE.md`](CLAUDE.md).

Seluruh rantai jalan **di latar belakang** (asinkron). Dari sisi klien, bentuknya
tiga langkah — bukan satu request yang digantung 3 menit (yang akan diputus proxy
saat di-deploy):

```
POST /documents/generate   ->  202 + {job_id}          (~50 ms; kerja belum jalan)
GET  /documents/jobs/{id}   ->  status (queued/running/done/failed) — polling
GET  /documents/jobs/{id}/download   ->  unduh .docx
```

Bahasa yang dipahami parser: **Python** (FastAPI, Flask), **TypeScript/JavaScript**
(Express, React, Next.js App Router), **Java** (Spring MVC). Bahasa lain tetap
terbaca, tapi tanpa detail struktur (fitur/use case/diagram tetap disimpulkan LLM
dari nama file & fungsi).

## Peta struktur proyek

```
app/
  domain/            data murni + interface (SourceProvider), tanpa framework
  ingestion/         ambil source dari GitHub/ZIP, saring mana yang "produk"
  services/          INTI logika — tiap file satu tanggung jawab:
    ingestion_service.py       orkestrasi ingest -> Workspace          (Tahap 1)
    parser_service.py          Tree-sitter -> Contract A               (Tahap 1)
    llm_service.py             Contract A -> Contract B via Claude      (Tahap 2)
    compiler_service.py        Contract B -> render diagram -> .docx    (Tahap 3)
    job_store.py               status job async (SQLite)                (Tahap 3)
    template_*_service.py      "V2": ukur docx upload -> template baru  (Tahap 3)
  diagram/           layer diagram (IR + renderer) — fondasi, belum dipakai live
  api/               endpoint FastAPI (routes_*.py) + schema request
  templates/         template Jinja2 (Markdown) + reference.docx (tampilan docx)
  core/config.py     baca .env
  main.py            entrypoint FastAPI

frontend/            React + Vite (satu form: pilih sumber, generate, unduh)
tests/               pytest (296 test) — LLM/PlantUML/GitHub selalu di-mock
dummy_data/          fixture Contract A/B untuk testing manual tanpa ingest+LLM
scripts/             utilitas dev + validation/ (uji ke repo publik nyata)
CLAUDE.md            pengetahuan permanen (arsitektur, kontrak, keterbatasan)
CHANGELOG.md         riwayat perubahan detail (dibaca on-demand)
SESSION.md           foto sesi kerja terakhir (ditimpa tiap sesi)
```

Root sengaja cuma berisi file konfigurasi/dokumen — kode & aset selalu masuk folder.

## Tiga tahap pipeline (pembagian kerja)

Arsitekturnya dibagi jadi tiga tahap yang saling lepas lewat kontrak JSON. Kalau
kamu mau berkontribusi, pilih satu tahap dan mulai dari file intinya:

| Tahap | Tanggung jawab | File inti | Kontrak keluaran |
|---|---|---|---|
| **1 — Ingestion & Parsing** | Ambil kode dari GitHub/ZIP, normalisasi, ekstrak struktur pakai Tree-sitter (tanpa LLM) | `services/ingestion_service.py`, `services/parser_service.py` | Contract A (`ParsedRepoContext`) |
| **2 — AI & Prompt** | Petakan struktur → narasi dokumen + script diagram, lewat Claude | `services/llm_service.py` | Contract B (`DocumentContent`) |
| **3 — Backend & Templating** | Endpoint FastAPI, render diagram, template Jinja2 → `.docx`, frontend | `services/compiler_service.py`, `api/routes_document.py`, `frontend/` | file `.docx` |

Karena batasnya kontrak JSON, tiap tahap bisa dikerjakan & diuji sendiri — mis.
kamu bisa menguji Tahap 3 pakai `dummy_data/document_content_sdd.json` tanpa perlu
memanggil LLM sama sekali.

## Setup

Butuh Python 3.11+, Node.js (untuk frontend), **Java 17+** (untuk render diagram
PlantUML secara lokal), dan [API key Anthropic](https://console.anthropic.com/settings/keys).

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
python -c "import pypandoc; pypandoc.download_pandoc()"   # sekali saja

# plantuml.jar — unduh sekali dari https://github.com/plantuml/plantuml/releases
# (asset plantuml-<versi>.jar), simpan sebagai tools/plantuml.jar

cp .env.example .env           # isi ANTHROPIC_API_KEY minimal

cd frontend && npm install && cd ..
```

Semua variabel `.env` dijelaskan di [`.env.example`](.env.example); hanya
`ANTHROPIC_API_KEY` yang wajib.

## Menjalankan

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000   # -> http://127.0.0.1:8000/docs
cd frontend && npm run dev                                    # -> http://127.0.0.1:5173
```

Buka frontend, pilih sumber kode (**Repo GitHub** atau **Upload ZIP**), pilih tipe
& gaya dokumen, klik Generate, tunggu ~2-3 menit, unduh. Atau pakai Swagger UI di
`/docs` untuk memanggil API langsung.

## Endpoint utama

| Method | Path | Fungsi |
|---|---|---|
| `POST` | `/documents/generate` | **Titik masuk utama (async).** Balik `202` + `job_id`; pipeline jalan di latar belakang. Menerima repo GitHub **atau** `zip_files` (base64), `document_metadata`, `logo_base64`, `template_id` |
| `GET` | `/documents/jobs/{id}` | Status job (`queued`/`running`/`done`/`failed`) |
| `GET` | `/documents/jobs/{id}/download` | Unduh `.docx` hasil |
| `POST` | `/documents/{sdd,uat}` | Render Contract B langsung → `.docx` (untuk uji template tanpa ingest+LLM) |
| `POST` | `/ingest/{github,zip}` | Ingest kode → `Workspace` (tahap analisis saja) |
| `POST` | `/templates` | Upload `.docx` template sendiri → `template_id` siap pakai (V2) |
| `GET` | `/templates` | Daftar gaya dokumen (built-in + hasil upload) |

Daftar lengkap + perilaku error tiap endpoint ada di [`CLAUDE.md`](CLAUDE.md).

## Testing

```bash
pytest                                       # 296 test; LLM/PlantUML/GitHub di-mock, $0
python scripts/validation/run_validation.py  # ingest+parse ke repo publik nyata, gratis
```

`pytest` menjawab *"kode sesuai rancangan?"*; `scripts/validation/` menjawab
*"rancangan bertahan di repo asing?"* — dua pertanyaan berbeda, dan yang kedua yang
menemukan bug tak terduga. **Tahap 2 validasi memanggil Claude sungguhan dan
berbayar**, jadi wajib opt-in (`--with-llm`). Estimasi biaya satu dokumen dari repo
kecil ~$0,10 (Sonnet 5).

## Mulai dari mana (untuk kontributor baru)

Kalau kamu baru masuk dan belum pernah menyentuh project ini, urutan tercepat untuk
paham:

1. **Baca [`CLAUDE.md`](CLAUDE.md)** — bagian *Ringkasan*, *Alur Sistem*, dan
   *Kontrak JSON*. Itu menjelaskan *kenapa* tiap tahap ada dan bentuk data yang
   mengalir di antaranya.
2. **Jalankan sekali** (lihat [Setup](#setup) & [Menjalankan](#menjalankan)),
   generate dokumen dari satu repo publik kecil. Lihat `.docx`-nya — itu bikin
   seluruh pipeline "klik".
3. **Uji Tahap 3 tanpa biaya**: `POST /documents/sdd` dengan
   `dummy_data/document_content_sdd.json`. Kamu dapat `.docx` tanpa memanggil LLM —
   cara termurah bereksperimen dengan template.
4. **Pilih satu tahap** dari [tabel di atas](#tiga-tahap-pipeline-pembagian-kerja)
   dan buka file intinya. Tiap file punya docstring yang menjelaskan tanggung
   jawabnya dan keputusan desain di baliknya.
5. **Sebelum menyentuh kode**, baca bagian *Prinsip Kerja* di `CLAUDE.md` — 8 pola
   pahit yang berulang selama membangun ini (mis. "ukur dulu sebelum memperbaiki",
   "test hijau ≠ produk jalan"). Menghemat kamu dari mengulanginya.

Aturan emas project ini: **jujur soal batas mengalahkan mengarang.** Kalau sesuatu
tidak bisa diturunkan dari kode, biarkan jadi placeholder yang terlihat — jangan
tebak. Itu yang membuat output-nya bernilai.

## Batas yang diketahui

Ditulis terbuka, karena produk ini menjual kejujuran isinya:

- **Django, Nuxt, Next.js Pages Router belum terdeteksi** — route-nya bukan lewat
  pola yang parser kenali. Go, .NET, PHP, Ruby belum didukung parser (fallback:
  file terbaca tapi tanpa detail struktur).
- **Monorepo raksasa tidak muat** — seluruh konteks dikirim dalam satu panggilan
  LLM; repo ~7.000 file menembus context window.
- **Upload ZIP: UI + backend sudah tersambung**, tapi base64-in-JSON membengkak
  ~33% untuk repo besar (cukup untuk MVP).
- **OAuth GitHub baru scaffold** — pakai Personal Access Token untuk sekarang.
- **Job yang jalan hilang kalau prosesnya mati** di tengah — sudah ada *reaper*
  yang menandai job macet jadi `failed` (klien tak lagi polling selamanya), tapi
  kerjanya tidak dijalankan ulang. Belum aman di serverless (Vercel/Lambda).
- **Belum ada autentikasi** — endpoint-nya terbuka. Aman untuk localhost;
  penghalang pertama sebelum deploy ke publik.
- **Template upload (V2) masih berkembang** — untuk template dengan nama bab tak
  umum, pemetaan bab ke kode butuh opsi AI (berbayar) agar tidak jadi placeholder
  semua.

Daftar lengkapnya, dengan angka dan alasan tiap butir, ada di [`CLAUDE.md`](CLAUDE.md).

## Status

Pipeline penuh jalan end-to-end dan sudah menghasilkan dokumen terverifikasi
berjejak untuk beberapa repo nyata (Python/Flask, Java/Spring, TS/JS/Next.js).
**Belum pernah di-deploy dan belum punya pengguna di luar tim** — jadi anggap ini
engine yang matang di dalam produk yang belum jadi. Pekerjaan sisa yang paling
bernilai bukan menambah fitur, melainkan membuktikan & mengemas apa yang sudah ada.

## Dokumen pendukung

- [`CLAUDE.md`](CLAUDE.md) — pengetahuan permanen: arsitektur, kontrak antar-tahap,
  keterbatasan (dengan angka), dan prinsip kerja. **Baca ini kalau mau berkontribusi.**
- [`CHANGELOG.md`](CHANGELOG.md) — riwayat perubahan detail + alasan tiap keputusan.
- `SESSION.md` — catatan sesi kerja terakhir (ditimpa tiap sesi baru).
- `scripts/validation/README.md` — cara menjalankan validasi ke repo publik nyata.
</content>
