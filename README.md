# auto-document-generator

**Baca source code sebuah repo, keluarkan draf Solution Design Document (SDD) dan
User Acceptance Test (UAT) dalam `.docx` yang siap diedit.**

Tunjuk ke repo GitHub, pilih SDD atau UAT, tunggu ~2-3 menit, unduh dokumennya.
(Upload ZIP baru sampai tahap analisis kode — belum tersambung ke pembuatan
dokumen; lihat *Batas yang diketahui*.)

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
| **Ditanyakan lewat form** | Nomor RFC, versi, klasifikasi dokumen, informasi demografi, infrastructure & capacity, security remark, distribution list — hal yang manusia tahu tapi kode tidak akan pernah tahu (25 field, semuanya opsional) |
| **Sengaja dibiarkan kosong** | Blok tanda tangan, sertifikasi hasil UAT, mockup UI — hal yang sistem tidak boleh mengarangnya |

Yang tidak punya jejak di kode **tidak ditulis**. Diagram tidak menggambar
komponen yang tidak ada bekasnya di `dependencies` atau di docstring.

## Yang keluar

**SDD** (`.docx`): Informasi Dokumen · Revision History · Persetujuan · Deskripsi
Aplikasi · Dev System Type · Informasi Demografi · System Requirement · How to
Access · Infrastructure & Capacity · Application Architecture · Application
Security · Features Requirement · Flow Proses Bisnis · Use Case · Activity Diagram

**UAT** (`.docx`): Informasi Dokumen · Distribution List · Version History ·
Rencana UAT · Sertifikasi · Prosedur Pengujian · Ringkasan Aplikasi · Case Pengujian

Diagramnya gambar Mermaid yang ter-embed, bukan placeholder.

Contoh nyata — dari repo publik, bukan contoh buatan:

| Repo | Bahasa | Hasil |
|---|---|---|
| aplikasi pemesanan (Flask) | Python | 10 fitur, 9 use case, 8 test case, 9 activity diagram, aktor **Admin & Customer** |
| spring-petclinic | Java | 5 fitur, 5 use case, 17 endpoint, aktor **Staff Klinik & Pengunjung** |
| realworld (2 repo) | TS/JS | Komponen frontend dipetakan ke endpoint backend, lintas dua repo terpisah |

Aktornya bisnis, bukan "Developer"/"API Client" — itu penanda bahwa isinya
diturunkan dari aplikasinya, bukan dari nama file.

## Cara kerja

```
GitHub (OAuth/PAT) atau ZIP
        |
        v
Normalizer  ->  Workspace (format seragam)
        |
        v
narrow_to_product()   tanya pyproject.toml / package.json: mana yang produk?
        |
        v
Parser (Tree-sitter, deterministik, TANPA LLM)  ->  ParsedRepoContext.json
        |
        v
LLM (Claude)  ->  narasi + script diagram Mermaid  ->  DocumentContent.json
        |
        v
Jinja2 (Markdown) + Mermaid->PNG  ->  Pandoc  ->  .docx
```

Tiap tahap dipisah **kontrak JSON** yang jelas, jadi sumber kode bisa diganti
tanpa menyentuh parser, dan LLM bisa diganti tanpa menyentuh ingestion.
Arsitektur lengkap, isi kontraknya, dan alasan tiap keputusan ada di
[`CLAUDE.md`](CLAUDE.md).

Bahasa yang dipahami parser: **Python** (FastAPI, Flask), **TypeScript/JavaScript**
(Express, React), **Java** (Spring MVC). Bahasa lain tetap terbaca, tapi tanpa
detail struktur.

## Setup

Butuh Python 3.11+, Node.js (untuk frontend), dan
[API key Anthropic](https://console.anthropic.com/settings/keys).

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
python -c "import pypandoc; pypandoc.download_pandoc()"   # sekali saja

cp .env.example .env           # isi ANTHROPIC_API_KEY

cd frontend && npm install && cd ..
```

## Menjalankan

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000   # -> /docs
cd frontend && npm run dev                                    # -> :5173
```

Endpoint utamanya **asinkron**: `POST /documents/generate` balik `202` + `job_id`
dalam ~50ms, pipeline jalan di latar belakang, klien polling
`GET /documents/jobs/{id}` lalu unduh hasilnya. Daftar endpoint lengkap ada di
[`CLAUDE.md`](CLAUDE.md).

## Testing

```bash
pytest                                       # 186 test; LLM/Mermaid/GitHub di-mock, $0
python scripts/validation/run_validation.py  # ingest+parse ke 10 repo publik nyata, gratis
```

`pytest` menjawab *"kode sesuai rancangan?"*; `scripts/validation/` menjawab
*"rancangan bertahan di repo asing?"* — dua pertanyaan berbeda, dan yang kedua
yang menemukan bug yang tidak terduga. Tahap 2 validasi memanggil Claude sungguhan
dan **berbayar**, jadi wajib opt-in (`--with-llm`).

## Batas yang diketahui

Ditulis terbuka, karena produk ini menjual kejujuran isinya:

- **Endpoint Django belum terdeteksi** — route-nya di `urls.py` lewat `path()`,
  bukan decorator. Go, .NET, PHP, Ruby belum didukung parser.
- **Monorepo raksasa tidak muat** — seluruh konteks dikirim dalam satu panggilan
  LLM; repo ~7.000 file menembus context window.
- **Diagram dirender lewat layanan hosted** (`mermaid.ink`) — isi diagram keluar
  ke internet. Untuk repo confidential, ganti ke rendering lokal dulu.
- **Upload ZIP belum tersambung ke pembuatan dokumen** — `POST /ingest/zip`
  menganalisis kodenya, tapi `POST /documents/generate` baru menerima repo
  GitHub. Untuk kode yang tidak di GitHub, hasil analisis ZIP harus dikirim
  manual ke `POST /documents/sdd` / `/uat`.
- **OAuth GitHub baru scaffold** — pakai Personal Access Token untuk sekarang.
- **Job hilang kalau prosesnya mati** di tengah jalan; belum aman di serverless.
- **Belum ada autentikasi** — endpoint-nya terbuka. Aman untuk localhost;
  penghalang pertama sebelum deploy ke publik.

Daftar lengkapnya, dengan angka dan alasan tiap butirnya, ada di
[`CLAUDE.md`](CLAUDE.md).

## Status

Pipeline penuh jalan end-to-end dan sudah menghasilkan dokumen terverifikasi untuk
5 repo nyata. **Belum pernah di-deploy dan belum punya pengguna di luar tim** —
jadi anggap ini engine yang matang di dalam produk yang belum jadi.

## Dokumen lain

- [`CLAUDE.md`](CLAUDE.md) — arsitektur, kontrak antar-tahap, keterbatasan, dan
  riwayat kenapa tiap keputusan diambil. Baca ini kalau mau berkontribusi.
- `SESSION.md` — catatan sesi kerja terakhir (ditimpa tiap sesi baru).
- `scripts/validation/README.md` — cara menjalankan validasi ke repo publik nyata.
