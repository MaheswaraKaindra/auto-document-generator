# Catatan Sesi — 2026-07-15/16

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi ini menutup dua celah terbesar yang pernah dicatat project ini. **(1) Produk
ini akhirnya menghasilkan dokumen untuk aplikasi bisnis nyata berbahasa Python** —
belum pernah terjadi sepanjang umurnya; jalannya lewat lima bug yang semuanya
ditemukan oleh kasus validasi baru, dan **empat di antaranya kelas kesalahan yang
sama**: sebab asli tertelan gejala. **(2) Penghalang produksi terbesar hilang** —
pipeline 191 detik tidak lagi ditahan di satu request HTTP; POST balik dalam
~50ms. Total biaya API: **~$0,66**. 119 test hijau. Semua sudah di-push ke
`origin/develop`.

---

## Yang diselesaikan

| # | Masalah | Inti perbaikannya |
|---|---|---|
| 1 | 28 penanda `(diisi manual)` diserahkan mentah | 25 ditanyakan lewat form (`DocumentMetadata`), 3 sengaja dibiarkan (tanda tangan & sertifikasi hasil tidak seharusnya diisi sistem). Angka lama "16" salah. |
| 2 | Contract A kebesaran → 502 "coba lagi" | `_guard_context_window` periksa lewat `count_tokens` (gratis) sebelum bayar → **413** dengan angka aslinya. Batas **ditanyakan ke Models API**, tidak di-hardcode. |
| 3 | Monorepo ditolak di pintu | Guard anti-bomb mencacah **seluruh isi arsip** sebelum menyaring relevansi. Filter dinaikkan ke atas pencacah di **kedua** provider; `MAX_TOTAL_FILES` 5.000 → 20.000. |
| 4 | **Flask = nol endpoint** | `route` bukan anggota `HTTP_METHODS`. Sekarang `@bp.route(...)` dikenali, termasuk `methods=` dan default GET. |
| 5 | Dokumen terpotong → "Invalid JSON" | `max_tokens` 16.000 → 32.000 + pindah ke `.stream()`. `DocumentTruncatedError` periksa `stop_reason` → **500** yang menyebut tempat memperbaikinya. |
| 6 | **Pipeline 191 detik ditahan di 1 request HTTP** | Proxy memutus di 30-60 detik → produk mustahil di-deploy. Sekarang **202 + job_id dalam ~50ms**, kerja di `BackgroundTasks`, status di **SQLite** (`job_store.py`), klien polling. Nol dependency baru. |
| 7 | **Monorepo: `www/` medusa (22%) mencemari dokumen** | `manifest.py` MENDETEKSI monorepo lalu sengaja menyerah. Petunjuknya ada di field yang sama: `workspaces` mendeklarasikan lokasi paket. **9.459 → 7.355 file, `www/` 2.098 → 0**, nol regresi. |
| 8 | **Kami membayari spasi; dan alat ukur kami berbohong** | `indent=2` = **30% token**. saleor **1.224.476 → 854.181 token: DITOLAK jadi MUAT**, nol perubahan arsitektur. Sekaligus: harness mengukur `compact` sementara yang dikirim `indent=2` — meleset 21-25%. Diperbaiki jadi **satu sumber kebenaran** (`format_contract_a`). |

Ditambah ke `repos.json`: **saleor-django**, **medusa-monorepo**, **esteler-flask**.
Ketiganya langsung berbuah — semua bug di atas ditemukan oleh mereka.

---

## Yang dibuktikan lewat repo nyata (bukan test)

- **Dokumen pertama untuk aplikasi bisnis Python**: `esteler-app` → 10 fitur, 9
  use case, 8 test case, 9 activity diagram, docx 408 KB (~$0,24). Isinya
  diperiksa: fiturnya memetakan satu-satu ke `services/*` yang nyata, aktornya
  **Admin & Customer** (bukan Developer/API Client), dan seluruh isi diagramnya
  **punya jejak** — Groq/Cloudinary/SQLAlchemy dari `dependencies`, dan
  `PostgreSQL (Neon)` dari **docstring** `config.py::_normalize_db_url()`.
- **Flask 0 → 38 endpoint**, coverage 41% → 55%, `routes/` otomatis jadi
  `controller` — tanpa menyentuh heuristik `type` sama sekali.
- **medusa** ditolak di pintu → terparse (9.459 file) → disaring `workspaces`
  jadi **7.355 file**, `www/` (situs dokumentasi, 22%) hilang seluruhnya.
  Nol regresi: fastapi 49→49, flask 25→25, express 8→8.
- **saleor** 502 "coba lagi" → pesan benar, **tanpa membayar sepeser pun**.
- **saleor sekarang MUAT** (854.181 token = 85% batas) cuma karena berhenti
  mengirim indentasi. A/B kualitas di esteler (~$0,24): 10→11 fitur, aktor &
  jejak diagram tetap — tidak ada yang turun.

---

## Pelajaran metodologis (yang paling mahal kalau dilupakan)

**Satu kelas bug muncul EMPAT kali sesi ini.** 502 menelan 414 mermaid (kemarin),
502 menelan context window, "Invalid JSON" menelan `max_tokens`, dan — yang paling
memalukan — `except RuntimeError` untuk "Pandoc tidak ada" saya taruh membungkus
seluruh pipeline, jadi RuntimeError dari LLM dilaporkan sebagai "Pandoc tidak
tersedia". Yang terakhir saya tulis **sambil memberantas pola itu**, dan yang
menangkapnya test. Polanya sama tiap kali: error handler meratakan sebab yang
spesifik jadi pesan generik, gejalanya cuma "kadang gagal", dan mahal justru
karena pesannya menyesatkan. **Kalau menulis `except`, tanyakan dulu: sebab apa
yang sedang saya sembunyikan, dan apakah cakupan tangkapannya sesempit sebabnya?**

**MEMERIKSA PROKSI, BUKAN BARANGNYA — muncul 3×.** Tiap kali ada sesuatu yang
MIRIP barangnya, dan saya memeriksa itu:

| Yang saya periksa (proksi) | Barangnya | Akibatnya |
|---|---|---|
| Field `dependencies` | **Seluruh** Contract A | "Neon itu karangan" — padahal ADA di **docstring** |
| Pola kegagalan `BackgroundTasks` yang lazim | **Kode yang benar-benar ada** | "tidak bisa multi-worker" — padahal jalan |
| `json.dumps()` compact di harness | `indent=2` yang **dikirim** | Laporan meleset 21-25%; medusa "2.831 KB" = **1,58 juta token** |

Dua yang pertama ketahuan dari pemilik repo, bukan dari saya. **Yang ketiga
paling berbahaya** karena proksinya adalah **alat ukur kami sendiri** — dan alat
ukur yang salah lebih buruk daripada tidak ada: dia memberi rasa aman palsu.
Kesimpulan "monorepo butuh chunking" sebagian lahir dari angka yang salah itu.

**Akar masalah yang ketiga bukan `indent=2`** — tapi **dua tempat men-serialisasi
hal yang sama**. Itu bukan duplikasi; itu **dua jawaban yang menunggu untuk
berbeda**. Diperbaiki dengan satu sumber kebenaran, bukan menambal dua tempat.

> Sebelum menyimpulkan, tanya: **yang saya periksa ini BENDA-nya, atau sesuatu
> yang mirip benda itu?**

**Ukur dulu, jangan menebak — bahkan untuk hal yang kelihatan sepele.** Rencana
"pindahkan filter ke atas pencacah" ternyata tidak cukup (medusa 9.459 > 5.000);
ketahuan cuma karena diukur dulu. Dan estimasi token 4 karakter/token meleset 2×.
Kebalikannya juga terbukti: prediksi monorepo (7.354) meleset SATU dari hasil
(7.355) — bukan keberuntungan, tapi karena `workspaces` medusa dibaca dulu.
Ternyata ada DUA bentuk (`list` di cal.com, `dict` di medusa) dan `name`-nya
"root" — tidak satu pun akan ditebak benar.

**Test hijau tidak pernah cukup di repo ini.** 11 test hijau pernah menemani
diagram yang gagal di tiap repo nyata. Tiap perbaikan sesi ini dibuktikan ke repo
asli, bukan cuma ke mock.

---

## Kalau melanjutkan besok, mulai dari sini

1. **Ukur Contract A `spring-petclinic` (Java) dalam token — GRATIS, dan hasilnya
   menentukan prioritas berikutnya.** Ini menggantikan "chunking" yang tadinya #1.
   Alasannya: waktu itu ditulis, saleor juga tidak muat, jadi kesimpulannya
   *"aplikasi bisnis besar tidak terlayani, ukuran dulu baru bahasa"*. **Sesudah
   compact, saleor MUAT (85%)** — jadi yang tersisa tidak muat cuma **monorepo
   raksasa**, kasus yang jauh lebih sempit. Repo Java enterprise kemungkinan
   seukuran **saleor** (satu aplikasi besar), bukan **medusa** (monorepo 7.000
   file) — kalau benar, **dukungan Java bisa dikerjakan sekarang** tanpa menunggu
   chunking, dan urutan prioritasnya terbalik lagi. **Ini hipotesis, bukan
   kesimpulan.** Ukur dulu; satu perintah `count_tokens`, nol biaya.
2. **Chunking untuk monorepo raksasa** — urgensinya TURUN (lihat #1). medusa
   sesudah compact: **1.253.878 token = 125%**, tetap ditolak. Diukur per-field:
   `api_endpoints` cuma **0,1%** (buang = sia-sia), yang mahal justru `classes`
   (21%) dan `dependencies` (23%) — dua-duanya bahan baku dokumen. Bahkan membuang
   `classes`+`functions` sekaligus cuma turun ke **97%** — terlalu mepet, bukan
   solusi. Jadi menyaring memang tidak akan menolong; masalahnya arsitektur
   (SELURUH Contract A dikirim dalam SATU panggilan). Arah: pecah
   per-workspace-package, atau ringkas dulu pakai model murah.
3. **Job hilang kalau proses mati** — sisa nyata dari async. `BackgroundTasks`
   jalan in-process: restart/crash/deploy saat job jalan → job berhenti selamanya
   di `running` dan klien polling tanpa akhir. Belum ada reaper untuk job
   `running` yang basi. Catatan: **multi-worker BUKAN masalah** (sudah diukur,
   jalan); **serverless masih masalah** (relevan: esteler ada di Vercel).
4. **Endpoint Django** — sengaja belum: satu-satunya kasus Django (saleor)
   terhalang guard context window, jadi perbaikannya tidak bisa dibuktikan
   end-to-end. Butuh aplikasi Django kecil di `repos.json` dulu.
5. **`url_prefix` Blueprint Flask** — path tercatat `/login`, aslinya
   `/auth/login`. Gejalanya: `routes/admin.py` dan `routes/customer.py` sama-sama
   melaporkan `GET /`. Butuh analisis lintas-file (`register_blueprint`).
6. **Tabel Revision History** masih baris kosong — butuh keputusan produk dulu
   (kolom `Summary of Changes` tidak punya jawaban jujur untuk dokumen baru).
7. **Bandingkan Sonnet 5 vs Opus** (~$0,30) — default pindah ke Sonnet 5 atas
   dasar reputasi, bukan pengukuran. Sekarang ada kasus uji yang layak: esteler
   murah (~$0,24) dan hasilnya bagus, jadi pembandingnya jelas.
8. **Bersihkan `data/documents/`** — tumbuh selamanya, ~400 KB per dokumen.
   Belum ada TTL. Belum masalah sekarang, jadi masalah begitu dipakai rutin.

---

## Yang perlu dilakukan manusia (tidak bisa saya kerjakan)

- **Revoke `GOOGLE_API_KEY` dan `LLAMA_API_KEY`.** Sudah dihapus dari `.env`
  lokal, tapi **kuncinya masih hidup** sampai dicabut lewat console masing-masing.
  (Masih belum dilakukan sejak sesi sebelumnya.)
- **Baca `scripts/validation/out/esteler-flask__SDD.docx`.** Saya sudah periksa
  isinya lewat Contract B dan hasilnya kuat, tapi apakah dokumen itu benar-benar
  layak dikirim ke klien — itu penilaian manusia, dan Anda yang paling tahu
  aplikasinya.
- **Isi `GITHUB_TOKEN`** kalau mau sering menjalankan validasi (batas anonim
  60/jam gampang habis kalau iterasi cepat).
