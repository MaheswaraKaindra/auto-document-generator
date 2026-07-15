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
~50ms. Total biaya API: **~$0,42**. 113 test hijau. Semua sudah di-push ke
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
- **medusa** ditolak di pintu → terparse (9.459 file, 39 endpoint).
- **saleor** 502 "coba lagi" → pesan benar, **tanpa membayar sepeser pun**.

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

**Dua klaim SAYA ternyata salah, dan dua-duanya karena mencocokkan pola alih-alih
memeriksa.** (a) "Neon di diagram esteler itu karangan" — dasarnya nol jejak di
`dependencies`; ternyata ADA di Contract A, di **docstring**
`config.py::_normalize_db_url()`. Saya menggeledah satu field lalu menyimpulkan
tentang seluruh dokumen. (b) "Tidak bisa multi-worker" — dasarnya pola kegagalan
klasik `BackgroundTasks` (state di `dict` memori); padahal state di sini ada di
SQLite, file di disk yang dibaca semua proses. Diukur kemudian: `--workers 3`,
50 GET lintas worker 0 kali 404, 30 POST bersamaan 30 sukses.

Keduanya ketahuan bukan dari saya, tapi dari pemilik repo. Keduanya sama
berbahayanya: **klaim salah bikin orang memperbaiki masalah yang tidak ada** —
membangun Redis untuk multi-worker yang sudah jalan, atau menambah guard untuk
LLM yang sebenarnya membaca dengan benar. **Kalau menulis keterbatasan atau
tuduhan karangan, ukur dulu. Pola yang cocok bukan bukti.**

**Ukur dulu, jangan menebak — bahkan untuk hal yang kelihatan sepele.** Rencana
"pindahkan filter ke atas pencacah" ternyata tidak cukup (medusa 9.459 > 5.000);
ketahuan cuma karena diukur dulu. Dan estimasi token 4 karakter/token meleset 2×.

**Test hijau tidak pernah cukup di repo ini.** 11 test hijau pernah menemani
diagram yang gagal di tiap repo nyata. Tiap perbaikan sesi ini dibuktikan ke repo
asli, bukan cuma ke mock.

---

## Kalau melanjutkan besok, mulai dari sini

1. **`narrow_to_product` fail-open di monorepo** — medusa: dari 9.459 file,
   disaring 0; `www/` (dokumentasi) menyumbang 22%. Bentuk yang sama dengan
   `docs_src/` fastapi yang dulu bikin SDD menyebut "Manajemen Hero". Perlu baca
   manifest di `packages/*/`, bukan cuma yang di root.
2. **Job hilang kalau proses mati** — sisa nyata dari async. `BackgroundTasks`
   jalan in-process: restart/crash/deploy saat job jalan → job berhenti selamanya
   di `running` dan klien polling tanpa akhir. Belum ada reaper untuk job
   `running` yang basi. Catatan: **multi-worker BUKAN masalah** (sudah diukur,
   jalan); **serverless masih masalah** (relevan: esteler ada di Vercel).
3. **Endpoint Django** — sengaja belum: satu-satunya kasus Django (saleor)
   terhalang guard context window, jadi perbaikannya tidak bisa dibuktikan
   end-to-end. Butuh aplikasi Django kecil di `repos.json` dulu.
4. **`url_prefix` Blueprint Flask** — path tercatat `/login`, aslinya
   `/auth/login`. Gejalanya: `routes/admin.py` dan `routes/customer.py` sama-sama
   melaporkan `GET /`. Butuh analisis lintas-file (`register_blueprint`).
5. **Tabel Revision History** masih baris kosong — butuh keputusan produk dulu
   (kolom `Summary of Changes` tidak punya jawaban jujur untuk dokumen baru).
6. **Bandingkan Sonnet 5 vs Opus** (~$0,30) — default pindah ke Sonnet 5 atas
   dasar reputasi, bukan pengukuran. Sekarang ada kasus uji yang layak: esteler
   murah (~$0,24) dan hasilnya bagus, jadi pembandingnya jelas.
7. **Bersihkan `data/documents/`** — tumbuh selamanya, ~400 KB per dokumen.
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
