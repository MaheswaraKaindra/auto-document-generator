# Catatan Sesi — 2026-07-19 (V2 increment 2: sintesis reference.docx dari spec)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

**V2 increment 2 (sintesis reference.docx dari `TemplateSpec`) SELESAI jadi kode
ber-tes** — lanjutan langsung dari increment 1 (`TemplateSpec`) sesi kemarin.
Pendekatan A (diputuskan pemilik): perluas `scripts/build_reference_docx.py`
dengan param `spec=None`. `spec=None` = perilaku PREMCO, **content-identik**
dengan `reference.docx` ter-commit; `spec` terisi = override sumber-spesifik
(tema major/minor terpisah, Title/Heading size/bold/caps/align, warna fill+teks
header via kontras luminance). **Temuan: "byte-identik" istilah yang salah** —
`build()` dua kali menghasilkan raw byte beda karena **timestamp zip**; yang
invariant = **isi tiap member zip**. Guard test membandingkan isi per-member.
Diverifikasi **VISUAL A/B di Word sungguhan** ($0, PROBE28): konten sama, dua
identitas — PREMCO (Calibri/tengah/CAPS/header-hitam) vs `04` (Tahoma/kiri/
campuran/Verdana/header-abu-teks-hitam). **246 test hijau (+5)**, biaya **$0**.

## Yang diselesaikan

| # | Apa | Inti |
|---|---|---|
| 1 | **Baca posisi** | SESSION lama + CLAUDE.md + `V2_TEMPLATE_MULTISOURCE.md` + increment 1 (`template_spec_service.py`) + `build_reference_docx.py`. |
| 2 | **Ukur dulu: apakah byte-compare valid?** | `build()` saat ini → temp, bandingkan committed: **isi tiap member zip IDENTIK**, cuma **timestamp beda**. Byte-compare mentah TAK valid; content-compare per-member yang benar. |
| 3 | **Perluas `build_reference_docx.py`** | Param `spec=None`. `_resolve_style(spec)` (fallback PREMCO), `_contrast_text` (YIQ 128), `_letterspacing(caps)`, `_set_theme_fonts` major≠minor berurutan, `_style_table(header_fill,header_text)`. Aditif; `spec=None` content-identik. |
| 4 | **Tes** | `tests/test_build_reference_docx.py` (5): content-identity guard, override spec-driven, fallback spec kosong, kontras dua arah. 246 hijau. |
| 5 | **Verifikasi visual A/B** | Konten sama lewat 2 reference → docx → PDF (Word COM) → PNG → **dilihat**. Dua identitas visual benar. Durable: `out/PROBE28_synth_reference_{premco,04}.{png,docx}`. |
| 6 | **Dokumentasi** | CLAUDE.md (Riwayat + roadmap c), `V2_TEMPLATE_MULTISOURCE.md` (increment 2 → KODE ber-tes), SESSION.md. |

## Kejadian yang layak diingat (jebakan)

- **"Byte-identik" ≠ yang diinginkan.** python-docx menulis timestamp waktu-kini
  ke tiap member zip, jadi build yang sama menghasilkan raw byte beda. Yang
  invariant = **isi member**. Menguji byte kontainer = menguji proksi, bukan
  barangnya (kelas kesalahan sama dgn menguji XML mentah dulu). **Ukur asumsi
  sebelum menuliskannya jadi test.**
- **Font dari TEMA, bukan style** (pelajaran bug-Aptos, lagi). Override font =
  tulis ulang `<a:latin>` major & minor di `word/theme/theme1.xml`, berurutan.
- **`char_spacing` diturunkan dari `caps`**, bukan knob terpisah — satu aturan
  (`_letterspacing`) mereproduksi PREMCO byte-identik DAN waras untuk spec asing.
- **Word COM jebakan `updateFields`** (SESSION lama, terpakai lagi): buang
  `<w:updateFields>` dari docx render sebelum buka utk PDF, kalau tidak Word
  menggantung di dialog "update fields?" dengan `Visible=False`.
- **`build_reference_docx.py` di `scripts/`, bukan paket app** → di-tes lewat
  `importlib.util.spec_from_file_location`, tanpa mengotori sys.path.

## Kalau melanjutkan, mulai dari sini

**#1 (prioritas SELAGI MAGANG — Trek A, di tangan pemilik):** kumpulkan **lebih
banyak template SDD/UAT dari vendor/sumber lain**. Kelayakan V2 sudah terbukti;
N=3 (2 non-PREMCO) masih tipis untuk yakin sintesis+pemetaan general bukan
overfit. Keragaman input menaikkan keyakinan — bukan lebih banyak kode. **Tanya
pemilik: sudah bawa template baru?** (belum ditanya di akhir sesi ini — tanyakan).

**#2 (implementasi Trek B — LANJUT DARI increment 3):**
- ✅ Increment 1 `TemplateSpec` — `app/services/template_spec_service.py` (KODE+tes).
- ✅ Increment 2 sintesis reference.docx — `build_reference_docx.py` param `spec`
  (KODE+tes). **BARU SELESAI sesi ini.**
- ⏭ **Increment 3 = LANGKAH BERIKUTNYA**, lebih besar → checkpoint dgn pemilik dulu:
  1. **Generator template Jinja dari outline** (prototipe `full_loop_04.py` di
     scratchpad kemarin — mungkin sudah terhapus; logika di `V2_TEMPLATE_MULTISOURCE.md`
     increment 3). Outline `TemplateSpec` → template `.md` bergaya bab sumber.
  2. **`_TEMPLATE_REGISTRY`** di compiler menerima template hasil-generate +
     reference.docx hasil-sintesis (satu `template_id` baru per upload).
  3. **Sintesis orientasi/landscape per-section** (spec `orientations[]` sudah
     diukur increment 1; belum dipakai sintesis — inilah yang membuat header
     7-kolom `04` tak patah).
  4. **Warna tabel khusus spec-driven** — marker hijau premco (`((GH))`) kini
     bertabrakan dgn warna header dari spec; jadikan spec-driven.
  5. **LLM auto-usul peta bab** (template asing spt IEEE SDD) + **UI tinjauan**
     pemetaan manusia. LLM = satu-satunya bagian non-deterministik (checkpoint biaya).

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Buka `scripts/validation/out/PROBE28_synth_reference_premco.png` vs `_04.png`**
  — konten IDENTIK, dua identitas visual (bukti sintesis reference.docx
  spec-driven bekerja di Word sungguhan). `.docx`-nya juga ada di situ.
- **PALING PENTING selagi magang:** bawa **lebih banyak template SDD/UAT dari
  vendor/sumber lain** (Trek A). Satu-satunya yang tak bisa diambil setelah keluar.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
