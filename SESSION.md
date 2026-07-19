# Catatan Sesi — 2026-07-19 (V2 increment 2 + inti increment 3)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Dua langkah implementasi V2 (upload template → template terdaftar) diselesaikan
jadi **kode ber-tes**, lanjutan dari increment 1 (`TemplateSpec`) sesi kemarin:
**Increment 2** — sintesis reference.docx dari spec (`build_reference_docx.py`
param `spec=None`; `spec=None` content-identik reference ter-commit, spec terisi
override tema/heading/warna-header). **Increment 3 (INTI deterministik)** —
`app/services/template_generator_service.py`: `propose_mapping` (peta bab
heuristik, stand-in LLM) + `generate_jinja_template` (outline → template Jinja;
bab isi-kode di-bind Contract B, bab asing → placeholder jujur). **Rantai penuh
spec→peta→template→isi→render terbukti VISUAL $0** (PROBE28 A/B tipografi, PROBE29
dokumen SDD gaya `04` tergenerate). **252 test hijau** (+5 increment 2, +6
increment 3). Biaya sesi: **$0**. Sisa V2 = pendaftaran registry/storage + LLM
peta + UI tinjauan + landscape (checkpoint, sebagian berbayar).

## Yang diselesaikan

| # | Apa | Inti |
|---|---|---|
| 1 | **Increment 2 — sintesis reference.docx** | `build_reference_docx.py` param `spec`. `spec=None` **content-identik** ter-commit (isi member zip; byte beda cuma timestamp). Override: tema major≠minor, Title/Heading, `_contrast_text` (YIQ). Commit `e4680ae`. |
| 2 | **Increment 3 inti — generator** | `template_generator_service.py`: `propose_mapping` + `generate_jinja_template`. Snippet dari template `default` terbukti; warna header dari reference tersintesis (tanpa marker). Degradasi anggun untuk bab asing. |
| 3 | **Tes** | +5 (`test_build_reference_docx.py`) +6 (`test_template_generator_service.py`, termasuk smoke render template hasil-generate dgn Contract B nyata). 252 hijau. |
| 4 | **Verifikasi visual $0** | PROBE28 (A/B tipografi PREMCO vs `04`), PROBE29 (dokumen SDD gaya `04` tergenerate: bab Tahoma, tabel abu, use-case/activity benar, Mockup placeholder). Semua **dilihat**, bukan cuma XML. |
| 5 | **Dokumentasi** | CLAUDE.md (2 entri Riwayat + roadmap + Struktur Proyek), `V2_TEMPLATE_MULTISOURCE.md` (increment 2→KODE, 3→INTI kode), SESSION.md. |

## Kejadian yang layak diingat (jebakan)

- **"Byte-identik" istilah salah.** python-docx menulis timestamp waktu-kini ke
  tiap member zip → build sama, raw byte beda. Invariant = **isi member zip**.
  Ukur asumsi sebelum menuliskannya jadi test (menguji proksi vs barangnya).
- **Snippet generator DIAMBIL dari template terbukti, bukan ditulis baru.** Markup
  Jinja harus valid di bawah `trim_blocks`/`lstrip_blocks`, termasuk baris-kosong-
  sebelum-heading/list (blank_before_header) — tanpa itu heading/kriteria bocor
  jadi teks literal (bug lama esteler). Meniru yang sudah render = aman.
- **Warna tabel spec-driven "gratis" untuk jalur generate.** Template hasil-generate
  tak pakai marker warna; header diwarnai `tblStylePr firstRow` reference
  tersintesis. Marker hijau premco cuma soal template buatan-tangan.
- **Peta heuristik sengaja konservatif** (nama tak dikenali → placeholder, tak
  menebak). LLM-lah yang kelak memetakan bab asing; modul menyediakan kontrak.
- **Word COM `updateFields`**: buang `<w:updateFields>` dari docx sebelum buka
  untuk PDF, kalau tidak Word menggantung di dialog dgn `Visible=False`.
- **`scripts/build_reference_docx.py` bukan paket app** → di-tes lewat
  `importlib.util.spec_from_file_location`, tak mengotori sys.path.

## Kalau melanjutkan, mulai dari sini

**#1 (prioritas SELAGI MAGANG — Trek A, di tangan pemilik):** kumpulkan **lebih
banyak template SDD/UAT dari vendor/sumber lain**. Kelayakan V2 terbukti; N=3 (2
non-PREMCO) tipis untuk yakin sintesis+pemetaan general bukan overfit halus.
Keragaman input menaikkan keyakinan — bukan lebih banyak kode. **Tanya pemilik:
sudah bawa template baru?** Kalau ada → ukur pakai `build_template_spec` (gratis)
sebelum lanjut.

**#2 (V2 Trek B — sisa increment 3, CHECKPOINT dulu, sebagian BERBAYAR):**
- ✅ Increment 1 `TemplateSpec`, 2 sintesis reference, 3-INTI generator — KODE+tes.
- ⏭ **Pendaftaran + storage** (deterministik, $0, BISA dikerjakan repo-only):
  `generate_docx` masih hardcode `REFERENCE_DOCX` & muat template dari
  `TEMPLATES_DIR` (FileSystemLoader). Untuk template hasil-upload perlu: (a)
  simpan template `.md` hasil-generate + reference.docx tersintesis per-upload
  (mis. `data/templates/<id>/`), (b) `_TEMPLATE_REGISTRY` dinamis / override
  reference.docx per-`template_id` di `generate_docx`, (c) `_build_uat_context`
  mengelompokkan test-case untuk template generate juga (kini cuma untuk premco).
  Ini keputusan arsitektur kecil — bahas dulu.
- ⏭ **LLM auto-usul peta bab** (BERBAYAR, non-deterministik — gate biaya):
  ganti `propose_mapping` heuristik dengan usulan LLM untuk template asing (mis.
  IEEE SDD "Data Design"). Kontrak keluarannya sudah sama (`[{level,text,binding}]`).
- ⏭ **UI tinjauan pemetaan** (frontend): tampilkan rencana peta, biarkan manusia
  edit binding sebelum generate.
- ⏭ **Orientasi landscape per-section**: spec `orientations[]` sudah diukur
  (increment 1), belum dipakai sintesis — inilah yang membuat tabel test 7+ kolom
  tak patah di potret (cacat prototipe `04`). Reuse `_landscape_after_marker`.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Lihat `scripts/validation/out/PROBE29_generated_sdd_04_p1.png` & `_p2.png`** —
  dokumen SDD yang **digenerate otomatis** dari outline + isi Contract B, bergaya
  template `04` (sumber lain). Bukti rantai V2 penuh bekerja pada kode app.
  (PROBE28 = A/B tipografi reference.docx spec-driven.)
- **PALING PENTING selagi magang:** bawa **lebih banyak template SDD/UAT dari
  vendor/sumber lain** (Trek A). Satu-satunya yang tak bisa diambil setelah keluar.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
