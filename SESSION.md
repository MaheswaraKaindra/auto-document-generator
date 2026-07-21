# Catatan Sesi — 2026-07-21 (UI upload ZIP + job reaper)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Dua hal selesai, keduanya $0 tanpa LLM. **(1) UI upload ZIP di frontend** —
melengkapi jalur ZIP→dokumen (backend `zip_files` sudah ada sejak sesi lalu).
Section "Sumber Kode" kini punya pemilih GitHub vs Upload ZIP; **sudah di-commit**
(`fa1e302`). **(2) Job reaper** — menutup keterbatasan lama "job macet di `running`
selamanya kalau proses mati". Pemilik menyatakan template sumber lain tak akan ada
untuk waktu lama, jadi dua kandidat V2 lain (UI edit peta bab, landscape) sama-sama
tak bisa diverifikasi tanpa input eksternal; job reaper dipilih karena CLAUDE.md
sendiri menominasikannya sebagai kerja tepi-deployment yang **tak terhalang input
eksternal**. **296 test hijau (+6). Reaper BELUM di-commit** (nunggu review).

## Yang dikerjakan

1. **UI upload ZIP** (`frontend/src/App.jsx` + `App.css`): pemilih `sourceType`
   GitHub/ZIP, tiap ZIP = satu repo (Tag + input `.zip` dibaca base64 via
   FileReader), dikirim sebagai `zip_files`. Guard 50 MB + tolak dini kalau tak
   ada file/tag. Verifikasi: `vite build` + `oxlint` hijau. **Sudah di-commit.**
2. **Investigasi $0 SEBELUM pilih arah** (prinsip repo #2): baca
   `template_spec_service` + `compiler_service` → temuan yang **mengalihkan
   pilihan dari landscape ke reaper**: pengukuran orientasi (`orientations`/
   `has_landscape`) DAN penerapan (`_landscape_after_marker` + marker
   `((LANDSCAPE))`, dipakai premco UAT) **sudah ada**; sisa landscape sejati cuma
   penyambungan ke V2 (butuh template upload landscape → tak akan ada).
3. **Job reaper** (`job_store.reap_stale_jobs`): tandai job `running`/`queued`
   yang tak update > 30 menit (ambang aman di atas timeout LLM 25 menit) jadi
   `failed` 503 (sementara). Dipanggil di `main.py` startup (import-time) + lazy di
   `get_job_status` route. Nol infrastruktur baru (SQLite, tak ada thread).
4. **Test +6**: `tests/test_job_store.py` (5: stale running/queued, fresh,
   done/failed untouched, count) + 1 route test di `test_routes_document.py`
   (GET status lewat ASGI nyata memungut job basi). **296 hijau, nol regresi.**
5. **Dok**: CHANGELOG 2 entri baru (ZIP UI + reaper); CLAUDE.md butir keterbatasan
   ZIP (UI selesai) + job-hilang (reaper menutup gejala stuck-running); SESSION ini.

## Kejadian yang layak diingat (jebakan)

- **Investigasi $0 dulu menyelamatkan dari pilihan lemah.** Aku sudah mengumumkan
  "landscape" sebelum investigasi; membaca kodenya menunjukkan landscape sebagian
  besar SUDAH ada & sisanya butuh input yang tak akan ada. Ganti ke reaper. Persis
  prinsip repo "ukur/buka barangnya sebelum kerja".
- **Reaper TIDAK boleh membunuh job sehat.** Job sehat bisa "diam" ~25 menit saat
  menunggu LLM (client timeout 25 menit, tak ada `set_progress` selama itu). Ambang
  30 menit dipilih di ATAS itu. Ambang lebih pendek = salah-bunuh.
- **`main.py` panggil `init_db`/`reap` saat IMPORT, bukan startup event** — sengaja:
  TestClient & sebagian deploy tak jalankan startup hook. Reaper ikut pola itu.
- **Reaper cuma menandai gagal, tidak re-run** — kerja hilang tetap hilang.
  Re-queue (Redis+RQ) sengaja belum; nol infrastruktur baru dipertahankan.

## Kalau melanjutkan, mulai dari sini

**Belum di-commit: perubahan job reaper** (job_store.py, main.py, routes_document.py,
tests/test_job_store.py, tests/test_routes_document.py, CLAUDE.md, CHANGELOG.md,
SESSION.md). ZIP UI sudah di-commit (`fa1e302`). Semua **belum di-push**.

**Kandidat kerja $0 berikutnya** (tak butuh template sumber lain):
- **Cleanup dokumen** (`data/documents/` tumbuh selamanya — belum ada TTL). $0,
  self-contained, pola sama dengan reaper (sapuan job_store).
- **Job simpan `template_id`** — kecil; riwayat job jadi bisa jawab "gaya apa".
- **Heuristik `type` baca path + sinyal isi** — prioritas rendah (label bukan
  bottleneck, sudah dibuktikan), tapi $0 & verifiable Tahap 1.

**Terhalang input eksternal (tunggu pemilik):**
- **Trek A** (template SDD/UAT sumber lain) — paling bernilai selagi magang.
- **UI edit peta bab & landscape per-section (V2)** — butuh template asing untuk
  diverifikasi; menunggu Trek A.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Review + restu commit reaper** (ZIP UI sudah di-commit tapi belum push). Kalau
  oke, aku commit reaper lalu bisa push dua-duanya ke origin/develop.
- **Server dev DIMATIKAN** — verifikasi sesi ini lewat pytest + build, tak butuh
  server. Reaper diuji lewat TestClient (ASGI nyata), bukan mock.
