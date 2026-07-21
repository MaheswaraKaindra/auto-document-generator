# Catatan Sesi — 2026-07-21 (lanjutan): redesign visual DOCX + rapikan struktur

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.** Detail perubahan ada di
> **CHANGELOG.md** (9 entri teratas = sesi ini).

---

## ⚠️ BACA DULU: kuota API habis

**Kredit Anthropic pemilik HABIS.** Ini mengubah cara kerja, bukan menghentikannya:

- **Satu-satunya langkah berbayar adalah Contract A → Contract B** (panggilan LLM
  di `llm_service`). Begitu Contract B tersimpan, `template → diagram → docx`
  bisa diulang tanpa batas, **$0**.
- Jadi **seluruh pekerjaan Peran 3 (templating, tabel, diagram, pagination,
  cover) tetap bisa dikerjakan DAN diverifikasi.** Seluruh sesi ini dikerjakan
  begitu — nol panggilan LLM.
- Caranya: `python scripts/render_fixtures.py --out hasil/` (lihat di bawah).

**JANGAN ubah skema Contract B selama kuota habis.** Kalau diubah, ketujuh
fixture yang tersimpan langsung jadi SKEMA-LAMA sekaligus — persis nasib
fastapi/realworld/petclinic — dan **tidak ada cara membuatnya ulang tanpa
membayar**. Kemampuan uji $0 ini bisa hilang dalam satu commit.

## Ringkasan satu paragraf

Sesi redesign visual DOCX + kerapian, **semuanya $0**. (1) **Cover SDD** didesain
ulang dari tumpukan tabel berbingkai jadi hierarki bertingkat. (2) **Visual di
luar cover**: tabel, diagram, pagination. (3) **Empat keterbatasan lama ditutup**
(TTL dokumen, `template_id` di job, landscape per-section, ukuran heading).
(4) **Regresi visual $0 dibuat permanen** — `scripts/render_fixtures.py` + dua
fixture padat masuk repo. (5) **Struktur folder dirapikan** — root repo kembali
patuh aturannya sendiri. Benchmark PREMCO diukur berulang, dan **dua kali
pengukuran itu membantah asumsi yang sedang dikerjakan**. **312 test hijau**,
frontend build/lint hijau, semua di-commit & di-push ke `origin/develop`.

## Yang selesai sesi ini (9 commit, semua sudah di-push)

**Cover SDD** — tipografi jadi style bernama di `reference.docx` (`Cover Eyebrow`
/ `Subtitle` / `Rule` / `Section Label`, dipanggil template lewat div Pandoc
`::: {custom-style="..."}`); judul dipecah dua tingkat oleh `_split_cover_title`
(docProps tetap utuh untuk kaki halaman); blok label→nilai tetap pipe table demi
kolom lurus tapi rupa tabelnya dilepas lewat marker `((CVBAND))`/`((CVLIST))`;
11 field metadata baru (kodifikasi + Tim Project) sehingga sel yang dulu kosong
permanen bisa diisi. Diterapkan ke **dua** template SDD (`premco` & `default`).

**Visual di luar cover** — (a) **tabel**: akar cacat ketemu lewat probe, style
`Compact` `basedOn` `Body Text` yang JUSTIFIED sehingga semua sel bersungai;
sekarang `align="left"` eksplisit. (b) **diagram**: `_image_attr` menaikkan
LANTAI ukuran ke target 80% lebar, dibatasi ukuran huruf (maks 12,5pt) &
ketajaman (min 150 dpi efektif). (c) **pagination**: `keepLines`+`widowControl`
eksplisit, `Figure` dapat `keepNext`, `_bind_lead_in_to_figure` mengikat
pengantar ke gambarnya. (d) **refactor** tanpa ubah perilaku: `_take_table_marker()`
menyatukan deteksi+pembuangan marker dari 3 tempat.

**Empat keterbatasan ditutup** — TTL dokumen (`purge_expired_documents()`, 30
hari, status 410 Gone, dipanggil di titik yang sama dengan reaper); `template_id`
disimpan di job; **landscape per-section (V2)** — outline kini membawa `orient`,
`_apply_orientation_markers` menangani N transisi lewat pasangan `((PORTRAIT))`;
ukuran heading diselaraskan ke angka terukur (16/13/12 → **14/12/11**).

**Regresi visual $0 permanen** — `scripts/render_fixtures.py` merender SEMUA
Contract B tersimpan (plantuml sungguhan, tanpa jaringan). Dua fixture terkaya
dipromosikan ke repo karena `scripts/validation/out/` **gitignored** dan bisa
hilang: `dummy_data/contract_b_rich_sdd.json` (esteler 11f/7uc/7ad) &
`contract_b_rich_uat.json` (MyPertamina **50 test case**).

**Struktur folder** — ~15 file lepas di root dipindah ke **`ref/`** (gitignored,
3 subfolder: `benchmark/`, `template-sumber-lain/`, `keluaran-lama/`); installer
pandoc 41 MB & screenshot UI lama dihapus. Root kini **8 file** (6 `.md` +
`requirements.txt` + config).

## Kejadian yang layak diingat (jebakan & pelajaran)

- **Prinsip #1 kena dua kali, dan dua-duanya membantah rencana.** (a) Target
  "diagram minimal 75-90% lebar" TERBANTAH oleh acuannya sendiri: tiap gambar di
  PDF PREMCO diukur = **43-95%**, mayoritas activity diagram **43-54%**. Masalah
  kita bukan persentase, tapi diagram MUNGIL. (b) "Gap heading" yang saya ajukan
  sebagai gate keputusan ternyata **PALSU** — saya mengukur SUB-heading (12pt
  kiri) lalu menyangkanya heading bab; bab PREMCO ternyata 14pt UPPERCASE tengah,
  sama dengan gaya kita. **Mengukur tidak cukup kalau yang diukur bagian yang salah.**
- **Lebar & ukuran huruf diagram TERKUNCI** satu sama lain (PlantUML membesarkan
  keduanya). Memutusnya butuh diagram lebih kaya (swimlane) = urusan prompt,
  **bukan renderer**. Jangan naikkan target tanpa menaikkan `_DIAGRAM_MAX_TEXT_PT`.
- **`cell.text = "..."` di python-docx membuang paragraf sel BESERTA style-nya** —
  muncul KETIGA kalinya sesi ini (cover, bar judul biru, header hijau). Pakai
  `_strip_marker_in_cell`.
- **Catatan lama "Word mengabaikan pPr dari table style" TIDAK berlaku untuk
  trPr/tcPr** — `cantSplit` & `vAlign` dari style jalan (diprobe langsung), jadi
  tak perlu kode duplikat.
- **Pipe table dengan baris header KOSONG (`|  |  |`) dibaca Pandoc sebagai
  "tabel tanpa header"** — itu yang memungkinkan daftar label→nilai tanpa baris judul.
- **Fixture tipis BUTA terhadap bug tata letak** (kelas prinsip #5). Bug "halaman
  berisi 4 baris lalu 8 inci putih" mustahil terlihat di `dummy_data` (1 fitur);
  cuma muncul pada kepadatan nyata. Itu sebabnya fixture padat masuk repo.
- **"Butuh input eksternal" kadang berarti "butuh input", bukan "dari ORANG
  LAIN".** Landscape per-section dicatat tak bisa diverifikasi tanpa template
  asing — padahal templatenya bisa dibuat sendiri dengan python-docx.
- **Pandoc menulis `<Pages>1</Pages>` sebagai placeholder** — dokumen 29 halaman
  pun melaporkan 1. Jangan pakai itu sebagai jumlah halaman.
- Alat verifikasi visual $0: PyMuPDF (`fitz`) PDF→PNG, Word COM PowerShell
  docx→PDF (+ `Fields.Update()`). `generate_docx` butuh cwd = root repo.

## Task yang BELUM — dikelompokkan menurut apa yang menghalanginya

**A. Bisa dikerjakan sekarang, $0, tak terhalang apa pun**
- **UI edit peta bab (V2)** — satu-satunya butir V2 yang tersisa. Upload +
  ringkasan peta SUDAH ada di frontend; yang belum: mengedit binding lalu
  menyimpannya (butuh endpoint PUT + regenerasi template Jinja). **Sengaja belum
  dikerjakan**: arah pemilik "berhenti nambah fitur", dan nilainya baru terasa
  begitu ada template dari perusahaan lain.
- Sub-heading H2/H3 template `default` belum pernah dilihat halaman-per-halaman
  (premco tak punya sub-bab). Spot-check $0 lewat `render_fixtures.py --out`.

**B. Berbayar — butuh kuota diisi + izin pemilik**
- **Uji Sonnet 5 vs Opus 4.8 (~$1)** — produk ini menjual kualitas dokumen, dan
  pilihan model masih **asumsi** sejak 15 Juli, bukan temuan. Murah, berdampak lama.
- **Generate esteler dari nol (~$0,10)** kalau mau dokumen contoh yang ISInya
  juga baru (yang sekarang visualnya terbaru, isinya dari Contract B 21 Juli pagi).
- Endpoint Django, Nuxt/Next Pages Router, Go/Kotlin — **guardrail CLAUDE.md:
  kemungkinan besar MARGINAL** untuk kualitas dokumen; kerjakan hanya kalau ada
  repo target NYATA yang membutuhkannya.

**C. Terhalang input eksternal (bukan kita yang menahan)**
- **1-2 file `.docx` template dari perusahaan lain** — format `premco` masih
  diukur dari SATU sumber. Ini yang memblokir validasi V2 sungguhan.

**D. Batas yang TIDAK bisa ditutup dari renderer**
- Diagram kita rantai vertikal, PREMCO **swimlane**. Itu bentuk script PlantUML
  dari LLM → perlu ubah prompt. Tercatat jujur, bukan bug.

**E. Di luar repo (hanya pemilik yang bisa)**
- Lengkapi `[ISI: ...]` di `C:\Kuliah\Magang\LAPORAN_MAGANG_draf.md`, konversi ke
  format kampus.
- Demo: ikuti `DEMO.md`. Dokumen contoh terbaru:
  `C:\Kuliah\Magang\Contoh_SDD_EstelerApp_visual_v2.docx` (29 hlm, isi esteler nyata).

## Yang perlu dilakukan manusia

- **Semua sudah di-commit & di-push ke `origin/develop`** (HEAD = `4d0fa9c`).
  Working tree bersih.
- **Utang lama yang belum juga dibereskan:** revoke `GOOGLE_API_KEY` &
  `LLAMA_API_KEY` (sisa migrasi provider); isi `GITHUB_TOKEN` kalau mau ingest
  repo privat / lolos rate limit 60 req/jam.
- **Isi ulang kuota Anthropic** kalau mau melanjutkan apa pun di kelompok B.
