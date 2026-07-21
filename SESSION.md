# Catatan Sesi — 2026-07-21 (UI upload ZIP di frontend)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Melanjutkan langsung dari sesi kemarin: backend jalur ZIP → dokumen sudah jadi
(field `zip_files` base64 di `POST /documents/generate`), yang tersisa cuma **UI
upload ZIP di frontend**. Itu yang dikerjakan sesi ini — $0, tanpa LLM, reversible.
Section "Sumber Kode" sekarang punya pemilih **GitHub vs Upload ZIP**; mode ZIP =
daftar baris (satu ZIP = satu repo) dengan Tag + input file `.zip` yang dibaca
base64 (pola persis logo), dikirim sebagai `zip_files`. `vite build` + `oxlint`
hijau. **Belum di-commit** (nunggu review pemilik), dan **belum dijalankan
browser→generate penuh** karena itu memicu job LLM berbayar (gate pemilik) —
jalur sinkron decode/reject-nya sendiri sudah di-unit-test backend kemarin.

## Yang dikerjakan

1. **Baca kontrak backend dua sisi dulu** (sebelum sentuh frontend): `zip_files`
   di `schemas_document.py` = `list[{repo_tag, filename, zip_base64}]`, precedence
   di atas `repositories`; `_decode_zip_files` di `routes_document.py` membuang
   prefiks `data:…;base64,` sendiri → aman kirim data-URL utuh dari FileReader.
2. **`frontend/src/App.jsx`**:
   - State baru: `sourceType` ('github'|'zip'), `zipRepos` (list `{repo_tag,
     filename, base64, error}`), factory `emptyZip()`, konstanta `ZIP_MAX_BYTES`
     (50 MB).
   - Handler: `updateZip`/`addZip`/`removeZip`/`handleZipFile` (FileReader →
     base64 data URL; file >50 MB atau gagal-baca → error per-baris, bukan lempar).
   - `handleSubmit`: cabang `usingZip` — kumpulkan `zipFiles` (hanya baris yang
     base64 & tag-nya terisi), tolak lebih awal kalau kosong, kirim `zip_files`
     ATAU `repositories` (yang satunya dikosongkan) + `github_token` null di ZIP.
   - JSX section 2: pemilih sumber + render kondisional (GitHub lama utuh di satu
     cabang, grup ZIP di cabang lain). Subtitle masthead dikoreksi.
3. **`frontend/src/App.css`**: `.zip-row` (grid 3 kolom: tag/file/hapus, +
   responsif <620px) & `.zip-status` (pesan filename siap / error merah).
4. **Verifikasi $0**: `vite build` (17 modul transformed) + `npm run lint`
   (oxlint) dua-duanya bersih.
5. **Dok**: entri CHANGELOG.md baru (teratas); butir keterbatasan ZIP di CLAUDE.md
   di-update (UI SELESAI 2026-07-21, sisa cuma efisiensi base64); SESSION.md ini.

## Kejadian yang layak diingat (jebakan)

- **`FileReader.readAsDataURL` untuk .zip bisa memberi MIME beda di Windows**
  (`application/x-zip-compressed`), TAPI tak masalah — backend `.partition(",")[2]`
  membuang prefiks `data:` apa pun. Jangan tergoda "membersihkan" prefiks di
  frontend; backend sudah menoleransinya (konsisten dgn `logo_base64`).
- **`required` pada input yang dirender kondisional**: input repositori GitHub
  punya `required`. Karena mode ZIP me-render cabang LAIN (input GitHub tak ada di
  DOM), `required`-nya tak memblokir submit mode ZIP. Itu sebabnya render
  kondisional (bukan `hidden`) yang dipilih.
- **Full E2E = bayar LLM**: `POST /documents/generate` balik 202 lalu job jalan di
  latar belakang MEMANGGIL LLM. Jadi "coba upload ZIP lewat browser sampai dokumen
  jadi" bukan verifikasi $0 — itu gate pemilik. Reject-path (bad base64 → 422
  sinkron) bisa diuji $0 tapi sudah di-unit-test backend kemarin.

## Kalau melanjutkan, mulai dari sini

**Jalur ZIP → dokumen: SELESAI end-to-end** (backend kemarin + UI hari ini).
Sisa cuma efisiensi base64-in-JSON untuk repo besar (cukup untuk MVP).

**#1 (Trek A — PALING BERNILAI selagi magang):** kumpulkan/bawa template SDD/UAT
sumber lain, jalankan lewat mesin (`compile_template_from_docx` + lihat). Kerja
yang tak bisa diambil setelah keluar magang.

**#2 (sisa V2, $0):** UI tinjauan/**EDIT** peta bab sebelum generate (tampilkan
`mappings` dari `GET /templates/{id}`, user sunting binding lalu generate) +
orientasi landscape per-section (spec `orientations[]` terukur `None` di 3
template — pengukuran + penerapan sama-sama belum jalan) + job simpan `template_id`.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **BELUM DI-COMMIT.** Perubahan sesi ini (App.jsx, App.css, CLAUDE.md,
  CHANGELOG.md, SESSION.md) masih di working tree — nunggu review pemilik sebelum
  commit. Tak ada perubahan backend/test, jadi `pytest` tak perlu dijalankan ulang
  (frontend-only).
- **Uji manual kalau mau** (opsional, tapi ZIP-nya baru diuji lewat build+lint,
  belum diklik di browser): `uvicorn app.main:app --reload` +
  `npm --prefix frontend run dev`, pilih "Upload file ZIP", upload .zip source
  code kecil (kecualikan node_modules/venv), beri Tag, generate. **Ini memicu LLM
  berbayar** — lakukan hanya kalau memang mau menguji end-to-end.
- **Server dev DIMATIKAN** (belum dinyalakan sesi ini — verifikasi lewat build
  saja, tak butuh server).
