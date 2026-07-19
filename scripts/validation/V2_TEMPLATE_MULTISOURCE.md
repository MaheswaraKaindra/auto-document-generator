# V2 — Sintesis Template dari Banyak Sumber (menutup gap generalisasi V0)

> Roadmap tahap (c), lanjutan V0. V0 mempelajari **satu** template (PREMCO) lalu
> berhenti dengan batas eksplisit: *"generalisasi butuh 1-2 template dari sumber
> lain (masih dicari)."* Pemilik project membawa template itu. Laporan ini =
> pengukuran + dua increment pertama V2 pada template multi-sumber. Dokumen
> sumbernya di-gitignore (dokumen/template pihak lain); laporan ini hanya memuat
> struktur, angka, dan nama font — tanpa isi.
>
> Dikerjakan 2026-07-18, biaya **$0** (deterministik, tanpa LLM).

## Bahan uji

Pemilik menambah 5 dokumen. Setelah diperiksa, **3 template isian** + **2 acuan**:

| Berkas | Peran | Keluarga |
|---|---|---|
| SDD template gaya IEEE/CMS (EN, `.doc`) | **template isian** | rekayasa-standar |
| UAT template (ID, `.docx`) | **template isian** | enterprise-Indonesia (keluarga PREMCO) |
| UAT template generik (EN, `.doc`) | **template isian** | UAT generik |
| Standar IEEE 1016-2009 (EN) | acuan struktur | — (bukan berkas isian) |
| Panduan UAT + contoh (EN) | acuan/panduan | — (bukan berkas isian) |

`.doc` (biner Word lama) tak terbaca `python-docx` → dikonversi ke `.docx` lewat
Word COM sebelum diukur.

## Temuan 1 — Keragaman struktur NYATA & besar

| Template | Bhs | Bab utama (H1) | Header tabel | Orientasi |
|---|---|---|---|---|
| SDD IEEE/CMS | EN | Introduction, Background, Conceptual Design, System Architecture, Data Design, Detailed Design, External Interface Design, Human-Machine Interface, System Integrity Controls | abu `D9D9D9` | 9 section, **2 landscape** |
| UAT ID | ID | Pengendalian Dokumen, Pendahuluan, Prosedur Testing, Deskripsi Testing | abu `A4A4A4` | 13 section, **4 landscape** |
| UAT EN generik | EN | Instructions, Form-Based Testing, User Security Matrix, Business Process Test Scripts, Defect Tracking | — | 2 section potret |

Pembanding PREMCO (V0): SDD 16 bab ID, header **hitam**; UAT flat, header **hijau**.
Warna header saja sudah menyapu lima nilai berbeda (hitam/hijau/abu D9/abu A4/biru).

## Temuan 2 — Sintesis visual GENERALISASI; pemetaan isi TIDAK

Ini crux V2. Dua paruh berperilaku berlawanan:

**Sintesis (rupa) generalisasi.** Tiap properti yang V0 ukur pada PREMCO terukur
mekanis di kelima berkas — font tema, ukuran/bold/caps/rata heading, warna fill
header tabel, orientasi per-section. Sintesis tak peduli *nilainya* apa; dia
mengukur lalu menirunya. (Lihat Temuan 4 — sudah dibuktikan render.)

**Pemetaan (isi) TIDAK generalisasi — Contract B kita berbentuk PREMCO.**
- **UAT ID hampir = template `premco` UAT kita.** Bab "Deskripsi Testing → Detail
  Testing" berisi `Login / Logout / Menu 1 → Submenu 1 …` — persis grouping
  test-case per-layar premco. Pemetaan **nyaris penuh**, keluarga sama, sumber
  beda. Bukti mesin isi kita generalisasi ke sumber Indonesia lain.
- **SDD IEEE/CMS = degradasi anggun.** Dari 10 bab, cuma ~3-4 punya isi turunan
  kode: Background/Overview → `app_description`; System Architecture →
  `diagrams.system_architecture`; External Interface Design → `api_endpoints`/
  `component_integration`; System Integrity Controls → `meta.security_*`. Bab
  **Data Design, Detailed Design, Human-Machine Interface** tak ada di kode →
  **placeholder jujur**, bukan karangan. Manusia melihatnya di layar tinjauan.

Jadi fork "luas vs fokus" **bukan biner**: satu mesin melayani dua-duanya —
keluarga enterprise-app paling kaya, template asing menghasilkan placeholder yang
jujur. Setia dengan nilai jual ("30 halaman benar > 87 halaman separuh karangan").

Dekay (CORETAD) universal: heading kosong di 3 dari 5, korupsi tab di 2. Aturan
V0 "bersihkan, jangan salin" bertahan lintas sumber.

## Increment 1 (SELESAI) — kontrak `TemplateSpec`

Kontrak JSON baru, diukur deterministik dari docx apa pun, dikonsumsi increment 2
(sintesis) & 3 (pemetaan). Bentuknya:

```
visual: { effective_body_font, effective_heading_font, base_size_pt,
          theme_major/minor, title{size,bold,align},
          headings{"Heading N":{font,size,bold,caps,align}},
          table_header_fill, table_uses_named_style,
          orientations[], has_landscape }
structure: { n_paragraphs/tables/images/sections/toc/numpr,
             heading_usage, outline[{level,text,empty}] }
decay: { empty_headings, tab_in_headings }
```

**Font "efektif" wajib di-resolve, bukan dibaca satu sumber** (pelajaran "bug
Aptos" berulang): `04` men-set `docDefault=theme:minorHAnsi` tapi style `Normal`
override ke **Verdana**; tema IEEE = Aptos tapi style override ke Times New
Roman/Arial. Resolver mengikuti `Normal`→`ascii`/tema; itu yang benar-benar
dicetak. `caps` juga properti terukur (bukan diasumsikan PREMCO).

## Increment 2 (SELESAI) — sintesis reference.docx dari spec

Sintesis = **SALIN reference.docx** (warisi seluruh struktur teruji: dot-leader,
footer fldChar, padding tabel, updateFields, caption) lalu **override cuma yang
sumber-spesifik** dari spec: tema major/minor (font heading vs body TERPISAH),
Title/Heading size/bold/caps/align, warna fill+teks header tabel. Warna teks
header dihitung kontras luminance (fill gelap→putih, terang→hitam), bukan diukur
per-dokumen.

**Dibuktikan render** ($0): markdown sama, dua reference. Output dari spec `04`
→ Tahoma heading rata-kiri, H2 tengah, **tak di-caps**, Verdana body, header
tabel **abu teks hitam**. Output PREMCO → Calibri, semua tengah, **DIPAKSA CAPS**
+ perenggangan, header **hitam teks putih**. Tipografi kini diukur-dari-sumber.

**TERIMPLEMENTASI (2026-07-19, bukan lagi scratchpad).** Pendekatan A: perluas
`scripts/build_reference_docx.py` dengan param `spec=None`. `_resolve_style(spec)`
menggabungkan properti sumber-spesifik di atas fondasi PREMCO; `_set_theme_fonts`
kini menyetel major≠minor berurutan; `_style_table` menerima `header_fill`/`text`;
`_contrast_text` (YIQ, ambang 128) menghitung teks header. **`spec=None` CONTENT-
IDENTIK dengan reference.docx ter-commit** — dan temuan penting: "byte-identik"
tak tepat, yang benar **content-identik per member zip**; raw byte beda hanya di
**timestamp zip** (wajar antar-build, tak berbahaya). Guard test membandingkan
isi tiap member (bukan byte kontainer). 5 tes baru (`tests/test_build_reference_docx.py`),
246 test hijau. A/B render diverifikasi VISUAL ulang di Word sungguhan
(PROBE28_synth_reference_{premco,04}.png).

## Increment 3 (PROTOTIPE SELESAI) — loop penuh pada `04`

outline (dari spec) + **peta bab heuristik** (stand-in untuk peta yang kelak
diusulkan LLM & ditinjau manusia) → **generate template Jinja** → isi dengan
Contract B UAT → render lewat reference-`04` tersintesis. Terbukti $0:

- Template tergenerate mengikuti urutan bab `04` (Pengendalian Dokumen →
  Pendahuluan → Prosedur Testing → Deskripsi Testing); bab non-kode jadi
  boilerplate/placeholder, "Detail Testing" di-bind ke loop `uat_test_groups`,
  dan **sampel Menu/Submenu di bawahnya dibuang** (digantikan isi nyata).
- Render: struktur bab benar, tipografi `04` (Tahoma/Verdana), test case nyata
  dikelompokkan per-modul, header tabel abu dari spec.
- **Cacat satu-satunya = langkah yang sengaja ditunda**: header tabel 7-kolom
  patah-patah di potret — persis alasan `04` memakai LANDSCAPE. Pengukuran
  memprediksi, potret membuktikan. Bukan kegagalan loop.

Jadi ketiga increment terbukti sebagai **satu rantai** pada template non-PREMCO
nyata. V2 de-risked: layak diimplementasikan.

**INTI diport ke kode app (2026-07-19).** `app/services/template_generator_service.py`:
`propose_mapping(spec, doc_type)` (peta bab heuristik berbasis kata kunci, **stand-in
LLM** — keluaran `[{level,text,binding}]` dirancang untuk UI tinjauan) + `generate_jinja_template(mapping)`
(outline → string Jinja; bab isi-kode di-bind loop/tabel Contract B, bab asing →
`*(diisi manual)*` degradasi anggun, anak bab yang isinya diganti dibuang). Snippet
Jinja **diambil dari template `default` terbukti**; warna header TANPA marker —
datang dari `tblStylePr firstRow` reference tersintesis (spec-driven, increment 2).
6 tes fixture sintetis + smoke render dgn Contract B nyata (nol tag Jinja tersisa).
Bukti end-to-end $0 **VISUAL**: outline SDD sintetis → peta → template → isi
`document_content_sdd.json` → render lewat reference-`04` tersintesis → dokumen
SDD lengkap gaya `04` (PROBE29): bab Tahoma-kiri, body Verdana, tabel header-abu
spec-driven, use-case & activity ber-sub-heading benar, Acceptance Criteria list
bernomor (blank-before-list terjaga), Mockup → placeholder jujur. Sisa increment 3
(checkpoint berikut): pendaftaran `_TEMPLATE_REGISTRY` + storage artefak (butuh
desain), LLM auto-usul peta (berbayar), UI tinjauan, orientasi landscape per-section.

## Keputusan arsitektur — "kompilasi upload jadi template terdaftar" (bukan swap)

V2 = otomatiskan persis kerja manual pembuatan `premco`: docx upload → ukur →
hasilkan template Jinja + reference.docx tersintesis + peta bab → manusia tinjau
sekali → template terdaftar di `_TEMPLATE_REGISTRY`. Alasan:
- **Pakai ulang seluruh pipeline matang** (Contract B → Jinja → Pandoc →
  reference.docx, 239 test). V2 menambah *penghasil* template, bukan mengganti
  perender.
- **Swap `--reference-doc` mentah = corrupt** (V0 buktikan). Sintesis satu-satunya
  jalur sehat.
- **Konsisten filosofi**: deterministik di mana bisa (ukur+sintesis visual, tanpa
  LLM), LLM cuma untuk pemetaan bab yang butuh judgment, manusia meninjau.

## Status & sisa

| Increment | Isi | Status |
|---|---|---|
| 1 | `TemplateSpec` (ukur → JSON) | ✅ **KODE app + tes** (`app/services/template_spec_service.py`, 2026-07-18) |
| 2 | Sintesis reference.docx dari spec | ✅ **KODE + tes** (`build_reference_docx.py` param `spec`, 2026-07-19) |
| 3 | Peta bab→Contract B + generasi template Jinja + isi + render | 🟨 **INTI deterministik = KODE + tes** (`app/services/template_generator_service.py`, 2026-07-19); sisa = pendaftaran registry/storage, LLM auto-usul peta, UI tinjauan, landscape |

**Riset V2 SELESAI** — ketiga increment terbukti sebagai satu rantai pada
template non-PREMCO. Sisa = IMPLEMENTASI, bukan lagi kelayakan.

**Batas jujur:** (1) semua masih riset scratchpad, belum kode `app/` ber-tes;
(2) yang belum dibangun = LLM auto-usul peta (template asing), UI tinjauan
manusia, sintesis landscape/per-section orientasi, dan warna tabel khusus
spec-driven (marker premco hijau kini bertabrakan dgn spec); (3) N kecil — 3
template isian; lebih banyak sumber tetap menaikkan keyakinan generalisasi.

**Langkah berikut (IMPLEMENTASI, gaya V1):** konsolidasi 1-3 jadi kode `app/` +
tes fixture sintetis (`TemplateSpec` → sintesis reference → generator template),
lalu tambah pemetaan LLM + UI tinjauan + orientasi per-section. Menyentuh kode
ter-commit → checkpoint dgn pemilik dulu.
