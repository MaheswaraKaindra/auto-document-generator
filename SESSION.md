# Catatan Sesi — 2026-07-21 (ZIP UI + reaper → validasi esteler → premco default + onboarding)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi panjang dengan titik balik penting. Awalnya lanjutan teknis (UI upload ZIP di
frontend, lalu job reaper — dua-duanya $0, di-commit & push). Lalu pemilik menegur:
**"dari kemarin muter-muter, gaada progress."** Audit riwayat MEMBENARKANNYA — jantung
nilai (kualitas dokumen) tak disentuh sejak 18 Juli; 2 file dok (CLAUDE.md 67×,
SESSION.md 52×) jadi yang PALING sering diubah; banyak kerja tepi $0 tanpa artefak.
Diagnosis: produk sebetulnya solid, tapi **buktinya tak pernah dikeluarkan** karena
membuktikan nilai inti (generate dokumen nyata → baca) itu berbayar & dihindari.
**Aksi memutus siklus (~$0,10 total):** generate SDD esteler nyata → **terbukti 100%
berjejak** (nol karangan); temukan & perbaiki salah template (default→premco, $0);
jadikan **premco default**; tulis ulang README jadi onboarding tim + buat DEMO.md +
draf laporan magang. **296 test hijau.**

## Yang dikerjakan (urut)

1. **UI upload ZIP** (`frontend/App.jsx`+`App.css`) — pemilih GitHub/ZIP, kirim
   `zip_files` base64. **Commit `fa1e302`, pushed.**
2. **Job reaper** (`job_store.reap_stale_jobs` + `main.py` startup + lazy di GET
   status) — job macet >30 mnt → `failed` 503. **Commit `0d66e04`, pushed.**
3. **Validasi end-to-end esteler** (~$0,10): scratchpad script ingest→parse→LLM→docx.
   22 file/38 endpoint, docx 781 KB. Verifikasi klaim Contract B ke Contract A:
   `ORD-YYYYMMDD-XXXX`/`session_id`/`walkin_order`/`get_top_menus`/`/admin/menu/create`/
   arsitektur Neon+Cloudinary+Groq — **semua berjejak, nol karangan.**
4. **Fix template + premco default**: dokumen awal digenerate `default` (header hitam)
   → pemilik bilang PROBE23 (premco) lebih bagus. Lihat visual (PyMuPDF): beda =
   tabel use case **biru menyatu** (premco) vs hitam-terpisah (default). Render ulang
   esteler premco ($0). Lalu **premco jadi default** (`schemas_document.py="premco"` +
   frontend `useState('premco')`+fallback). 296 test + build/lint hijau.
5. **README ditulis ulang** (`7e3c91b`, pushed) — onboarding tim: peta struktur,
   tabel 3 tahap, "mulai dari mana"; selaras fakta (ZIP tersambung, 296 test, reaper,
   multi-template). **DEMO.md** baru + **draf laporan magang** (luar repo).
6. **Dok diselaraskan** (belum commit — ada di working tree): README (premco default
   + DEMO.md), CLAUDE.md (premco default), CHANGELOG (entri), SESSION ini.

## Kejadian yang layak diingat (jebakan)

- **"Muter-muter" itu NYATA tapi di lapisan yang salah** — produk inti solid & selesai
  sejak ~16 Juli; kerja setelahnya numpuk di tepi ($0) tanpa artefak. Biaya kecil
  ($0,10) untuk membuktikan nilai inti > berhari-hari kerja tepi. (Prinsip #6/#8.)
- **Selalu tanya `template_id`** — default lama `default` (header hitam) kalah rapi
  dari `premco` (tabel use case biru). Instance ini premco-first; premco kini default.
- **Render docx butuh cwd = root repo** (`tools/plantuml.jar` path relatif). Jalankan
  script dari root, bukan subfolder.
- **Verifikasi visual $0 tanpa poppler**: PyMuPDF (`fitz`) render PDF→PNG; docx→PDF
  via Word COM (PowerShell). Pola dipakai berkali-kali sesi ini.

## Kalau melanjutkan, mulai dari sini

**Arah pemilik: BERHENTI nambah fitur, kemas & buktikan.** Produk terbukti bekerja.
- **Laporan magang**: draf di `C:\Kuliah\Magang\LAPORAN_MAGANG_draf.md` — lengkapi
  bagian `[ISI: ...]`, konversi ke format kampus.
- **Demo**: ikuti `DEMO.md`. Dokumen contoh siap di folder Magang (default+premco).
- **Kalau mau dokumen contoh lebih**: generate UAT esteler premco (~$0,10), atau repo
  lain. Selalu pakai `template_id="premco"`.

**Sisa teknis (kalau diminta, $0, tak butuh input eksternal):** cleanup `data/documents/`
(TTL), job simpan `template_id`. **Butuh input eksternal (tunggu pemilik):** Trek A
(template sumber lain) → UI edit peta bab + landscape per-section (V2).

## Yang perlu dilakukan manusia

- **Perubahan sesi ini setelah `7e3c91b` (premco default + DEMO + dok) akan di-commit
  di akhir sesi** (pemilik minta "commit + push"). Contoh docx & laporan draf di folder
  **Magang** (luar repo, tak ke-commit).
- **`Contoh_SDD_EstelerApp.docx` (default) masih di root repo** karena sedang dibuka di
  Word (gitignored, tak masuk git) — tutup Word lalu pindahkan ke Magang kalau mau.
- **Utang lama:** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.
