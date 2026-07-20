# Catatan Sesi — 2026-07-20 (balik ke satu diagram use case gabungan; split per-aktor dibuang)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Pemilik berubah pikiran: split diagram use case per-aktor (sesi lalu, untuk fix
panah menyilang Flowy) **DIBATALKAN** — mau **SATU diagram gabungan** saja (semua
aktor dalam satu gambar), asal rapi. Kandidat sesi lalu (Graphviz `dot`) diinvestigasi
**$0 dulu** (instruksi pemilik: timbang trade-off dependency sebelum kerja besar) dan
**premisnya gugur**: (1) `dot` ternyata SUDAH dibundel di `plantuml.jar` (Windows
auto-extract ke `%TEMP%\_graphviz\`, jadi bukan dependency baru di Windows), TAPI
(2) `dot` ≈ `smetana` dan **tak ada engine yang menghapus panah menyilang** untuk
diagram gabungan padat — itu **struktural**, bukan kualitas engine (diukur visual
smetana/dot/elk pada 3 aktor × 13 use case); (3) kasus NYATA cuma 2 aktor / 5-8 use
case, dan di situ **smetana pun sudah bersih**. Keputusan otonom (premis pemilik
gugur): **Opsi A — balik ke gabungan, tetap smetana** (paling sederhana, nol
dependency, dot tak menolong dense & keunggulannya hilang di deploy Linux). Revert
bersih + verifikasi visual default & premco. **288 test hijau, $0.** Belum commit
(nunggu review pemilik).

## Yang dikerjakan

1. **Investigasi layout $0** (sebelum kerja besar, per instruksi pemilik):
   - `java -jar plantuml.jar -version` → PlantUML **menemukan** Graphviz 2.44.1;
     jejaknya `%TEMP%\_graphviz\dot.exe` (kelas `GraphvizWindowsLite` di jar
     29 MB). Shell tak lihat dot (bukan PATH/registry), tapi PlantUML pakai.
   - Render **3 engine** pada kasus padat (3 aktor × 13 use case): `smetana`
     (kusut), `dot` (sedikit lebih halus, TETAP menyilang), `elk` (orthogonal
     tapi 2204px — mustahil potret, tetap menyilang). → crossing **struktural**.
   - Render kasus **tipikal** (2 aktor × 8 use case): smetana & dot **dua-duanya
     bersih**. → Flowy patologis, bukan norma.
2. **Revert split → gabungan** (Opsi A, smetana). File: `compiler_service.py`
   (buang `_usecase_plantuml_to_ir`/`_split_usecase_images`/regex `_UC_*`/flag
   `splits_usecase`/param `split_usecase`/context `use_case_diagrams_by_actor`+
   `use_case_figure_count`), `sdd_template.md` + `sdd_premco_template.md` +
   `template_generator_service._BODY[USE_CASES]` (loop per-aktor → satu
   `![Use Case Diagram]`), offset gambar activity balik hardcode (default `+4`,
   premco `+3`), `template_compiler_service` manifest tak tulis `splits_usecase`,
   `tests/test_usecase_split.py` **dihapus**, 2 tes lain dibersihkan.
3. **Verifikasi VISUAL $0** (docx → PDF Word COM → PNG → dilihat) pada Contract B
   2-aktor (Customer+Admin): **default** `Gambar 4 Use Case`(1 gambar, 2 aktor)→
   `Gambar 5 Activity`; **premco** `Gambar 3`→`Gambar 4` + bar biru use case utuh.
   Penomoran benar ujung-ke-ujung.
4. **Dok**: entri Riwayat baru (+ split lama ditandai DIBALIK); SESSION.md ini.
5. **BONUS — pisah changelog dari CLAUDE.md** (permintaan pemilik: CLAUDE.md boros
   token). "Riwayat Perubahan Penting" (~65% isi, ~30k token, di-load tiap sesi)
   dipindah ke **`CHANGELOG.md`** (dibaca on-demand). CLAUDE.md **~47,5k → ~17,5k
   token (−63%)**. Ditambah seksi **"Prinsip Kerja"** (8 pola distilasi) supaya
   pelajaran tetap ter-load. Memory checkpoint + header model-file di-update: entri
   baru → CHANGELOG.md, CLAUDE.md hanya kalau pengetahuan permanen berubah. 48 entri
   terbawa utuh. Lihat entri teratas CHANGELOG.md.

## Kejadian yang layak diingat (jebakan)

- **`dot` dibundel `plantuml.jar` di Windows** (`GraphvizWindowsLite`, extract ke
  `%TEMP%\_graphviz\`). "dot: command not found" sesi lalu MENYESATKAN — shell tak
  lihat, PlantUML lihat. Cukup buang `-Playout=smetana` untuk pakai dot. Tapi ini
  Windows-only (Linux deploy tak dapat).
- **Panah use case menyilang di diagram GABUNGAN itu STRUKTURAL**, bukan bug engine.
  Banyak aktor berbagi banyak use case dalam satu kolom = pasti menyilang. dot/elk
  tak menyelesaikannya. Satu-satunya solusi "selalu bersih" = split per-aktor (yang
  justru dibuang). Untuk dokumen normal (2-3 aktor) gabungan sudah bersih.
- **Premis yang tak pernah diuji** ("dot jauh lebih rapi") menahan pekerjaan &
  menyesatkan arah. Ukur $0 dulu sebelum install/refactor — persis pola repo ini.
- **`app/diagram/` (IR + renderer) kini tak dipakai pipeline live lagi** (split
  adalah satu-satunya pemakainya). Balik jadi fondasi-saja; modul + tesnya utuh.

## Kalau melanjutkan, mulai dari sini

**#0 (permintaan pemilik sesi ini) — ✅ SELESAI.** Diagram use case balik ke satu
gabungan, split dibuang, smetana dipertahankan, diverifikasi visual. Batas jujur
yang diterima pemilik: dokumen ultra-padat (Flowy) tetap menyilang di bentuk
gabungan — tak terhindarkan tanpa split. **Belum di-commit** (nunggu review).

**#1 (Trek A — PALING BERNILAI selagi magang):** kumpulkan/bawa template SDD/UAT
sumber lain, jalankan lewat mesin (`compile_template_from_docx` + lihat). Sudah 4
kelas struktur tertutup; template BEDA struktur masih mungkin memancing bug. Kerja
yang tak bisa diambil setelah keluar magang.

**#2 (sisa V2, $0):** UI tinjauan/**EDIT** peta bab sebelum generate (tampilkan
`mappings` dari `GET /templates/{id}`, user sunting binding lalu generate) +
orientasi landscape per-section (spec `orientations[]` terukur `None` di 3 template
— pengukuran + penerapan sama-sama belum jalan) + job simpan `template_id`.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Review perubahan lalu commit** (belum aku commit) — DUA pekerjaan terpisah,
  sarannya **dua commit**: (1) **revert use case** → satu diagram gabungan
  (smetana); (2) **pisah changelog** (CLAUDE.md ramping + `CHANGELOG.md` baru).
  Verifikasi visual revert di scratchpad: `verify_default_p12.png` (Gambar 4, 2
  aktor 1 gambar) & `verify_premco_p12.png` (Gambar 3, bar biru). Perbandingan
  engine: `uc_smetana.png`/`uc_dot.png`/`uc_elk.png` (kenapa dot tak menolong dense).
- **Server dev DIMATIKAN** (masih, dari sesi lalu). Kalau mau testing lewat
  frontend: `uvicorn app.main:app --reload` + `npm --prefix frontend run dev`.
  (Verifikasi sesi ini tak butuh server — render langsung lewat compiler.)
- **Keputusan opsional**: kalau kelak mau diagram gabungan sedikit lebih halus DAN
  siap bayar dependency Graphviz di deploy Linux, tinggal buang `-Playout=smetana`
  di `_run_plantuml` (khusus use case) + install graphviz di Linux. Aku sengaja
  TIDAK ambil ini (marginal, hilang di Linux, nambah knob).
