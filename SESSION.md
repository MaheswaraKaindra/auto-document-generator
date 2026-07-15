# Catatan Sesi — 2026-07-15

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi ini berangkat dari satu bug (diagram gagal render) dan berakhir dengan
**pembeda utama produk terbukti bekerja untuk pertama kalinya**. Rantainya
berantai: tiap perbaikan membuka masalah berikutnya yang lebih dalam. Semua
sudah di `develop`, 82 test hijau, tidak ada kerja yang menggantung setengah
jalan.

Total biaya API sesi ini: **~$0,56** untuk 6 panggilan Claude.

---

## Yang diselesaikan (semua sudah merge ke `develop`)

Urut dari yang paling awal. Tiap baris punya commit-nya sendiri.

| # | Masalah | Inti perbaikannya |
|---|---|---|
| 1 | Diagram gagal render di repo besar (`502`) | 502 itu **pesan kita sendiri** yang menelan `414` dari mermaid.ink. Ganti base64 → **pako** (kompresi ~7x), dan berhenti menyamarkan sebab asli. |
| 2 | Log menyebut provider lama ("Gemini") | Nama provider dihapus, bukan diganti — route layer tidak seharusnya tahu providernya siapa. |
| 3 | Repo berantakan | Root tracked sekarang cuma file konfigurasi/dokumen. Output docx, PDF internal, `.pytest_cache` diabaikan git. |
| 4 | **Ingestion 1 request per file** | Repo 200 file = 200 request → jatah anonim GitHub (60/jam) habis sebelum satu repo selesai. Sekarang **tarball sekali unduh**: ~3 request/repo, konstan. |
| 5 | Kode test & contoh ikut ter-ingest | Pada express, **1169 dari 1265 endpoint** ternyata dari `test/`. Ditambah filter dir + pola nama file test (Go menaruh `foo_test.go` di sebelah `foo.go` — blocklist folder saja tidak cukup). |
| 6 | **Kontaminasi `docs_src/` (yang terpenting)** | 86% file fastapi dari folder tutorial → SDD-nya menyebut "Manajemen **Hero**" (nama tabel tutorial SQLModel) sebagai fitur produk. Diganti **deteksi manifest**: tanya `pyproject.toml`/`package.json` mana yang produk. fastapi **530 → 49 file**. |
| 7 | Model aplikasi di-hardcode | Pindah ke `LLM_MODEL` di `.env`, default **`claude-sonnet-5`** (dari Opus, alasan biaya — keputusan pemilik project). |
| 8 | Contract A dibayar dua kali untuk repo yang sama | `target_doc_type` ada di **depan** Contract A → merusak prefix cache. Urutan dibalik + `cache_control`. Terverifikasi: `cache_read=7919`. |

Dibuat baru sesi ini: **kerangka validasi** (`scripts/validation/`) — 2 tahap
dipisah berdasarkan biaya. Harness inilah yang menemukan #4, #5, dan #6.

---

## Yang dibuktikan lewat API sungguhan (bukan mock)

Ini yang mock tidak akan pernah bisa jawab:

1. **Cross-repo mapping FE↔BE jalan** — `Login.js → POST /users/login`,
   `Home/index.js → GET /articles`, lintas dua repo terpisah. **Pembeda utama
   produk ini, dan sampai sesi ini belum pernah diuji sama sekali.**
2. **Dokumen fastapi jujur sekarang** — dari "kumpulan aplikasi backend...
   Manajemen Hero" jadi "FastAPI adalah **framework** backend berbasis Python"
   dengan fitur Routing, Injeksi Dependensi, WebSocket. Semuanya benar.
3. **Caching aktif** — `cache_write=7919` lalu `cache_read=7919`.
4. **`target_doc_type` tetap membedakan** setelah urutan prompt dibalik —
   SDD 5 test case vs UAT 9.

---

## Pelajaran metodologis (yang paling mahal kalau dilupakan)

**Ukur dulu sebelum memperbaiki.** Kami hampir menghabiskan berhari-hari
memperbaiki heuristik `type` karena flask coverage-nya 0%. Dua panggilan Claude
($0,75) membuktikan itu **bukan bottleneck**: flask dengan coverage 0%
menghasilkan dokumen yang **akurat**, malah lebih banyak fiturnya daripada
fastapi yang coverage 63%. LLM ternyata sanggup menyimpulkan peran file dari nama
class dan `dependencies`.

**Salah pilih kasus uji terlihat seperti cacat produk.** Semua penilaian
kualitas sebelum realworld diambil dari framework/library. Framework memang tidak
punya aktor bisnis — jadi dokumennya terasa janggal, dan itu bikin kami mengira
produknya bermasalah. Begitu diberi aplikasi bisnis nyata, formatnya langsung
pas: aktornya `Guest`/`Registered User`, bukan `Developer`/`API Client`.

**Filter yang terlalu rakus lebih berbahaya daripada noise.** Aturan `samples`
sempat menghapus **seluruh 48 file Java** spring-petclinic karena nama package-nya
`org.springframework.samples`. Ketahuan oleh validasi, bukan oleh review. Karena
itu `manifest.py` sengaja **gagal-membuka**: tidak yakin = simpan semua.

**Mock bisa hijau sementara produknya rusak.** 11 test hijau sementara diagram
gagal untuk tiap repo nyata — karena mermaid.ink di-mock. Itu alasan
`scripts/validation/` ada.

---

## Perbandingan dengan dokumen acuan (dilakukan di akhir sesi)

Dokumen Solution Design enterprise sungguhan (87 halaman, PDF di root,
di-gitignore) dibaca dan dibandingkan bab per bab dengan `sdd_template.md`.
Hasilnya mengubah prioritas:

**Strukturnya sudah cocok hampir seluruhnya.** Template kita jelas dimodelkan
dari dokumen itu — Revision History, Persetujuan, Deskripsi, Dev System Type,
Demografi, System Requirement, How to Access, Infrastructure, Architecture,
Security, Features Requirement, Flow Proses Bisnis, Use Case, Activity Diagram
semuanya ada. **Jadi jaraknya bukan soal struktur.**

Yang belum ada: Daftar Gambar + Daftar Tabel (mekanis), Mockup Website + Mockup
Aplikasi (mustahil dari kode — kandidat slot upload).

Jaraknya ada di **kedalaman** (87 halaman vs ~25) dan **16 placeholder yang
dibiarkan kosong**. Tapi jangan kejar 87 halaman: dokumen acuan panjang sebagian
besar karena mockup, timeline, dan tanda tangan.

## Kalau melanjutkan besok, mulai dari sini

Urut menurut dampak-per-usaha. Semua sudah tercatat lengkap di **Keterbatasan**
CLAUDE.md.

1. **Isi 16 placeholder lewat form** — rasio dampak-per-usaha tertinggi yang
   diketahui. Isinya (RFC #, No. Solution Design, Document Classification, baris
   approval, checklist security) memang tidak bisa datang dari kode — tapi
   **manusia tahu**. Sekarang produk menyerahkan docx berisi 16 lubang dan
   pengguna berburu di Word. Seharusnya: tanyakan di form, dokumen keluar utuh.
   Sentuh `frontend/src/App.jsx` + `GenerateDocumentRequest` + template.
2. **Async + database** — penghalang produksi paling diremehkan. Generation ~100-125
   detik ditahan di satu request HTTP sinkron; proxy/load balancer umumnya memutus
   di 30-60 detik, jadi ini patah begitu di-deploy walau di localhost aman. Plus:
   tidak ada DB sama sekali, dokumen hilang setelah response terkirim.
3. **Tambah 2-3 aplikasi bisnis ke `repos.json`** — celah validasi terbesar. Dari 7
   repo, cuma `realworld` yang aplikasi bisnis berbahasa didukung, dan itu pun
   aplikasi contoh yang sengaja rapi. Kode perusahaan sungguhan jauh lebih
   berantakan. Tahap 1 gratis; Tahap 2 ~$0,15-0,30 per repo.
4. **Bandingkan Sonnet 5 vs Opus** (~$0,30 sekali bayar) — default pindah ke Sonnet
   5 atas dasar **reputasi umum, bukan pengukuran**. Produk ini menjual kualitas
   dokumen; jangan gantung lama. Sekarang waktunya tepat karena input sudah bersih.
5. **Larang diagram menggambar komponen tanpa bukti** — fastapi punya nol dependency
   database tapi diagramnya tetap menggambar `Backend → Database`. (LLM **memang**
   baca kode — realworld menghasilkan `Database (PostgreSQL via Prisma)` dan prisma
   memang ada 4x. Masalahnya cuma dia tidak berhenti saat buktinya kosong.)
6. **Heuristik `type`** — prioritas **rendah**, terbukti bukan bottleneck. Jangan
   kerjakan sebelum lima di atas.

Belum dikerjakan dan bukan bug, cuma memang belum: parser di luar Python/TS-JS,
test untuk `parser_service.py`, OAuth GitHub (masih scaffold), frontend masih
form dasar, mermaid.ink masih layanan pihak ketiga (isu privasi untuk repo
confidential).

---

## Yang perlu dilakukan manusia (tidak bisa saya kerjakan)

- **Revoke `GOOGLE_API_KEY` dan `LLAMA_API_KEY`.** Sudah dihapus dari `.env`
  lokal, tapi **kuncinya masih hidup** di penyedia masing-masing sampai dicabut
  lewat console. Menghapus baris ≠ mencabut kunci.
- **Isi `GITHUB_TOKEN`** kalau mau sering menjalankan validasi. Tidak wajib lagi
  sejak pindah ke tarball (~3 request/repo), tapi batas anonim 60/jam gampang
  habis kalau iterasi cepat.
