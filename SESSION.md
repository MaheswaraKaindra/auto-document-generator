# Catatan Sesi — 2026-07-19 (V2 increment 2+3 + pendaftaran & storage)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Rantai V2 (upload template → template terdaftar) disambung nyaris penuh jadi
**kode ber-tes**, $0. Sesi ini menyelesaikan: **increment 2** (sintesis
reference.docx dari spec), **increment 3 inti** (generator template Jinja + peta
bab heuristik), dan **pendaftaran + storage** (template hasil-upload jadi
`template_id` nyata yang `generate_docx` render lewat reference tersintesisnya
sendiri). Bukti terkuat: **PROBE30** — `compile_template` → `acme-sdd-template`
terdaftar → `generate_docx` dengan **diagram PlantUML asli** → dokumen SDD gaya
`04` lengkap, dilihat. **256 test hijau** (+5 inc2, +6 inc3, +4 orkestrator).
Sisa V2: **endpoint upload**, LLM auto-usul peta (berbayar), UI tinjauan,
orientasi landscape.

## Yang diselesaikan (berurut)

| # | Apa | Inti |
|---|---|---|
| 1 | **Increment 2 — sintesis reference.docx** | `build_reference_docx.py` param `spec`. `spec=None` content-identik ter-commit. Commit `e4680ae`. |
| 2 | **Increment 3 inti — generator** | `template_generator_service.py`: `propose_mapping` + `generate_jinja_template`. Commit `3b6f4a4`. |
| 3 | **Pindah sintesis ke app** | `scripts/build_reference_docx.py` logika → `app/services/reference_synthesis_service.py` (`build_reference`); script jadi CLI tipis. Runtime butuh memanggilnya. Guard content-identity re-verifikasi. |
| 4 | **Storage + registry dinamis** | `data/templates/<id>/` (manifest + template.md + reference.docx + spec + mapping). `_resolve_template` → `_ResolvedTemplate` (flag `uses_component_integration`/`groups_test_cases`/`uat_toc`) menggantikan cek `== "premco"`. `validate_template`+`list_template_ids` mencakup terkompilasi. |
| 5 | **Orkestrator** | `template_compiler_service.compile_template(spec, name)` + `compile_template_from_docx`. Ukur→generate→sintesis→simpan→daftar. |
| 6 | **Verifikasi** | 256 test hijau. Visual: PROBE28 (A/B reference), PROBE29 (generator), **PROBE30 (jalur produksi penuh, diagram PlantUML asli)**. |

## Kejadian yang layak diingat (jebakan)

- **`from X import KONST` mengikat by-value.** Orkestrator harus mereferensi
  `compiler_service.TEMPLATES_STORE` lewat MODUL, bukan `from ... import
  TEMPLATES_STORE` — kalau tidak, redirect (test/config) di satu tempat tak
  terlihat di tempat lain. Satu sumber kebenaran.
- **Built-in tetap `get_template`, bukan `from_string(read_text)`** — supaya
  output byte-identik, nol risiko regresi 200+ test. Cuma template terkompilasi
  (yang tak ada di FileSystemLoader) pakai `from_string`.
- **`*(diisi manual)*` di-render Pandoc jadi teks MIRING `(diisi manual)`** —
  asterisk penanda italic dibuang. Assertion cari `(diisi manual)`, bukan
  ber-asterisk. (Ketahuan dari test yang gagal.)
- **Flag manifest = jawaban "warna tabel spec-driven" & "diagram integrasi"**
  untuk jalur generate: template hasil-generate tak pakai marker; header
  diwarnai reference tersintesis, integrasi dimatikan lewat flag.
- **"Byte-identik" reference = content-identik per member zip** (timestamp beda).
  Guard test membandingkan isi member.

## Kalau melanjutkan, mulai dari sini

**#1 (prioritas SELAGI MAGANG — Trek A, di tangan pemilik):** kumpulkan **lebih
banyak template SDD/UAT dari vendor/sumber lain**. Kelayakan + mesin V2 sudah
jadi; yang menaikkan keyakinan generalisasi sekarang = **keragaman input**, bukan
kode. **Tanya pemilik: sudah bawa template baru?** Ada → ukur `build_template_spec`
(gratis), lalu `compile_template_from_docx` (gratis) → cek dokumennya.

**#2 (V2 Trek B — sisa, urutan yang disarankan):**
- ✅ increment 1-3 + pendaftaran/storage — KODE+tes. **Mesin V2 lengkap & terbukti.**
- ⏭ **Endpoint upload** ($0, repo-only, LANGKAH BERIKUT PALING LOGIS): `POST`
  multipart terima `.docx` → `compile_template_from_docx` → balas `template_id`.
  Lalu `template_id` itu bisa dipakai di `POST /documents/generate`. Frontend:
  dropdown gaya dokumen isi dari `list_template_ids()` (sudah publik). Ini yang
  membuat fitur BISA DIPAKAI user, bukan cuma lewat kode.
- ⏭ **LLM auto-usul peta bab** (BERBAYAR — gate biaya): ganti `propose_mapping`
  heuristik untuk template asing (IEEE "Data Design"). Kontrak keluaran sama
  (`[{level,text,binding}]`).
- ⏭ **UI tinjauan pemetaan**: tampilkan `mapping_<DOC>.json`, biar manusia edit
  binding sebelum generate final.
- ⏭ **Orientasi landscape per-section**: spec `orientations[]` sudah diukur,
  belum dipakai sintesis. Reuse `_landscape_after_marker`. Untuk tabel test lebar.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Lihat `scripts/validation/out/PROBE30_compiled_template_generate_docx_p1.png`**
  — dokumen SDD digenerate lewat JALUR PRODUKSI PENUH dari template hasil-kompilasi
  (`generate_docx` + diagram PlantUML asli). Bukti mesin V2 bekerja end-to-end.
  (PROBE29 = generator saja; PROBE28 = A/B reference.)
- **PALING PENTING selagi magang:** bawa **lebih banyak template SDD/UAT dari
  vendor/sumber lain** (Trek A). Satu-satunya yang tak bisa diambil setelah keluar.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
