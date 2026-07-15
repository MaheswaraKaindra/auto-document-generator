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

Sesi ini menutup celah terbesar yang pernah dicatat project ini: **produk ini
akhirnya menghasilkan dokumen untuk aplikasi bisnis nyata berbahasa Python** —
sesuatu yang belum pernah terjadi sepanjang umurnya. Jalannya lewat tiga bug yang
semuanya ditemukan oleh kasus validasi baru, dan **ketiganya kelas kesalahan yang
sama**: sebab asli tertelan gejala. Total biaya API: **~$0,42**. 109 test hijau.
Semua sudah di-commit ke `develop` (belum di-push).

---

## Yang diselesaikan

| # | Masalah | Inti perbaikannya |
|---|---|---|
| 1 | 28 penanda `(diisi manual)` diserahkan mentah | 25 ditanyakan lewat form (`DocumentMetadata`), 3 sengaja dibiarkan (tanda tangan & sertifikasi hasil tidak seharusnya diisi sistem). Angka lama "16" salah. |
| 2 | Contract A kebesaran → 502 "coba lagi" | `_guard_context_window` periksa lewat `count_tokens` (gratis) sebelum bayar → **413** dengan angka aslinya. Batas **ditanyakan ke Models API**, tidak di-hardcode. |
| 3 | Monorepo ditolak di pintu | Guard anti-bomb mencacah **seluruh isi arsip** sebelum menyaring relevansi. Filter dinaikkan ke atas pencacah di **kedua** provider; `MAX_TOTAL_FILES` 5.000 → 20.000. |
| 4 | **Flask = nol endpoint** | `route` bukan anggota `HTTP_METHODS`. Sekarang `@bp.route(...)` dikenali, termasuk `methods=` dan default GET. |
| 5 | Dokumen terpotong → "Invalid JSON" | `max_tokens` 16.000 → 32.000 + pindah ke `.stream()`. `DocumentTruncatedError` periksa `stop_reason` → **500** yang menyebut tempat memperbaikinya. |

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

**Satu kelas bug muncul TIGA kali sesi ini.** 502 menelan 414 mermaid (kemarin),
502 menelan context window, "Invalid JSON" menelan `max_tokens`. Polanya sama:
error handler meratakan sebab yang spesifik jadi pesan generik, dan gejalanya
selalu "kadang gagal" — mahal justru karena pesannya menyesatkan. **Kalau menulis
`except Exception`, tanyakan dulu: sebab apa yang sedang saya sembunyikan?**

**Menuduh karangan itu klaim, dan klaim juga harus diukur.** Saya sempat menulis
di CLAUDE.md bahwa "Neon" di diagram esteler adalah karangan — dasarnya: nol jejak
di `dependencies`. Pemilik repo mengoreksi ("memang pakai Neon"), dan ternyata
"Neon" **ada** di Contract A, di **docstring** `config.py::_normalize_db_url()`.
Saya menggeledah satu field lalu menyimpulkan tentang seluruh dokumen. Kalau mau
mengaudit karangan: geledah `json.dumps(ctx)`, bukan `dependencies` — Contract A
juga membawa docstring lewat `functions[].description`, dan LLM membacanya.
Tuduhan karangan yang salah lebih berbahaya daripada tidak menuduh sama sekali:
dia bikin orang "memperbaiki" masalah yang tidak ada, dan menggerus kepercayaan
pada bagian produk yang sebenarnya bekerja.

**Ukur dulu, jangan menebak — bahkan untuk hal yang kelihatan sepele.** Rencana
"pindahkan filter ke atas pencacah" ternyata tidak cukup (medusa 9.459 > 5.000);
ketahuan cuma karena diukur dulu. Dan estimasi token 4 karakter/token meleset 2×.

**Test hijau tidak pernah cukup di repo ini.** 11 test hijau pernah menemani
diagram yang gagal di tiap repo nyata. Tiap perbaikan sesi ini dibuktikan ke repo
asli, bukan cuma ke mock.

---

## Kalau melanjutkan besok, mulai dari sini

1. **Push** — semua sudah di-commit, belum di-push.
2. **`narrow_to_product` fail-open di monorepo** — medusa: dari 9.459 file,
   disaring 0; `www/` (dokumentasi) menyumbang 22%. Bentuk yang sama dengan
   `docs_src/` fastapi. Perlu baca manifest di `packages/*/`, bukan cuma root.
4. **Endpoint Django** — sengaja belum: satu-satunya kasus Django (saleor)
   terhalang context window, jadi tidak bisa dibuktikan. Butuh aplikasi Django
   kecil di `repos.json` dulu.
5. **`url_prefix` Blueprint Flask** — path tercatat `/login`, aslinya
   `/auth/login`. Butuh analisis lintas-file.
6. **Async + database** — penghalang produksi paling nyata. Terukur lagi sesi ini:
   generation esteler **191 detik** dalam satu request sinkron, sementara
   proxy/load balancer umumnya memutus di 30-60 detik.
7. **Tabel Revision History** masih baris kosong — butuh keputusan produk dulu
   (kolom `Summary of Changes` tidak punya jawaban jujur untuk dokumen baru).
8. **Bandingkan Sonnet 5 vs Opus** (~$0,30) — default pindah ke Sonnet 5 atas
   dasar reputasi, bukan pengukuran. Sekarang ada kasus uji yang layak
   (esteler murah dan hasilnya bagus, jadi pembandingnya jelas).

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
