# V0 — Studi Kelayakan "Upload Template Perusahaan" pada Template Nyata (PREMCO)

> Artefak kerja roadmap tahap (c): *user meng-upload template dokumen
> perusahaannya, sistem mengisinya dari repo*. V0 = pengukuran dengan tangan
> pada SATU template nyata SEBELUM menulis kode apa pun. Dokumen sumbernya
> (docx 40,7 MB di root) **di-gitignore** — dokumen internal klien; laporan ini
> hanya memuat struktur & angka, tanpa isi.
>
> Dikerjakan 2026-07-17, biaya $0. Tiga pertanyaan, tiga jawaban.

## Pertanyaan 1 — Bisakah manusia memetakan bab-babnya ke Contract B tanpa ambigu?

**JAWABAN: YA di level "bab ini diisi apa" (16/16 bab terpetakan); ambiguitasnya
hidup di level FORMAT.** Peta lengkapnya:

| Bab (Heading 1/2 mereka) | Sumber isi | Kelas |
|---|---|---|
| Cover (identitas, Fungsi/Kodifikasi, Katalog, Tim) | `meta.*` + kerangka kosong | form/manual |
| Document/Application Revision History | kerangka kosong | biarkan |
| Persetujuan Dokumen (+Timeline, Cost, TTD) | boilerplate + kerangka | biarkan |
| Daftar Isi / Gambar / Tabel | **3 field TOC sungguhan** | regenerasi (updateFields) |
| Deskripsi Aplikasi | `app_description` + list fitur utama + tabel role (`user_roles`) | Contract B |
| Application Dev System Type | `meta.dev_system_type` (format checkbox `ERP [ ] NON ERP [X]`) | form |
| Informasi Demografi Aplikasi | `meta.*` 7 baris | form |
| System Requirement | `system_requirements` — **mereka DUA tabel** (Server Side 1 & 2) | Contract B ⚠ format |
| How to Access | `meta.how_to_access` — **mereka TABEL**, form kita teks bebas | form ⚠ format |
| Infrastructure & Capacity Planning | **tabel 23 baris** — teks bebas form kita tidak memadai | manual ⚠ |
| Application Architecture | `diagrams.system_architecture` (1 gambar) — **tidak ada slot component_integration** | Contract B ⚠ |
| Application Security | `meta.security_*` | form |
| Application Features Requirement | `feature_requirements` (+kolom Remark kosong) | Contract B |
| Flow Proses Bisnis | `business_flow_description` + diagram + langkah — **langkah mereka BERSARANG (a/b)**, `business_flow_steps` kita flat | Contract B ⚠ |
| Use Case (H2) | `use_case_diagram` + `use_cases` — tabel ber-BAR JUDUL biru (`9CC3E5`), acceptance criteria DI DALAM tabel | Contract B |
| Activity Diagram (H2) | `activity_diagrams` — unit 5-elemen SANGAT regular (lihat bawah) | Contract B |
| Mockup Website / Aplikasi (2×H2) | gambar-gambar | slot upload manual |

**Unit berulang activity diagram — regular sempurna, kabar terbaik V0** (±20×):
`p[list] judul item → p[gambar diagram] → p[Heading 6] caption "Gambar N ..." →
TABEL metadata (bar judul, ACT00x, Actor, ...) → p caption "Tabel N ..."`.
Blok use case juga regular (2×). Artinya deteksi blok-yang-diulang PUNYA pola
untuk dipegang — bukan tebakan bebas.

**Empat ambiguitas format yang butuh keputusan di V1** (bukan blocker): SysReq
1 list vs 2 tabel; langkah flow bersarang vs flat; infra tabel 23 baris vs teks
bebas; `component_integration` kita tidak punya rumah (aturan V1 "mengisi,
bukan merestrukturisasi" → di-drop).

## Pertanyaan 2 — Berapa banyak rupa terbawa lewat `--reference-doc` mentah?

**JAWABAN: NOL — bukan sebagian, tapi RUSAK.** Diprobe sungguhan (esteler +
reference=docx mereka): Pandoc memakai reference-doc sebagai KONTAINER paket,
jadi (1) media + font ter-embed mereka ikut terseret — output 40 MB; (2)
python-docx menolak paketnya (part font tak terdeklarasi di
`[Content_Types].xml`); (3) **Word sendiri bilang "file appears to be
corrupted"**. Ditambah: dari 14 nama style yang dicari Pandoc/pipeline, docx
mereka hanya punya 4 (Title, Heading 1-3) — Body Text/Compact/caption/Table/TOC
tidak ada, jadi seandainya pun paketnya sehat, tabel & body jatuh ke default Word.

**Jalur yang benar: SINTESIS, bukan swap.** Langkah kompilasi template MENGUKUR
properti visual dokumen user lalu MEMBANGUN reference.docx bersih dari kerangka
Pandoc — persis yang `build_reference_docx.py` lakukan hari ini dengan angka
hardcode. Buktinya parameter mereka terukur mekanis dari file:

| Parameter | Terukur dari docx PREMCO | Yang kita hardcode minggu ini |
|---|---|---|
| Font & ukuran dasar | Calibri 11pt | Calibri 11pt ✓ |
| Heading bab | 14pt, center, bold | 14pt, center, bold, caps ✓ |
| Header tabel | fill hitam `000000` (52 sel) | hitam ✓ |
| Bar judul use case | biru muda `9CC3E5` (27 sel) | (belum ada — bahan V1) |

Kecocokan kolom kanan-kiri = pendekatan sintesis SUDAH terbukti sekali, manual.
V2 tinggal mengotomatiskan pengukurannya.

## Pertanyaan 3 — Anatomi template nyata seperti apa?

445 paragraf, **125 tabel** (semua TANPA table style — formatting langsung),
187 gambar, 1 section, 3 field TOC, 186 `numPr`. Heading styles DIPAKAI dengan
benar (H1×16 bab, H2×4, H6×54 sebagai caption gambar), `rFonts` eksplisit hanya
~18% run. **Dan pembusukan ala CORETAD nyata di dalamnya**: heading KOSONG ×6
(jadi entri hampa di Daftar Isi), nomor gambar mockup kacau (Gambar 37 muncul
sesudah Gambar 47; 37/38/39 dobel; banyak caption tanpa nomor). Template yang
di-upload user = dokumen jadi project lama, LENGKAP dengan cacatnya — langkah
kompilasi wajib membersihkan, bukan menyalin buta.

## Verdict V0

**Ide layak diteruskan ke V1**, dengan dua koreksi arah yang dibayar murah oleh
V0 ini: (1) lupakan swap reference-doc — bangun sintesis; (2) pemetaan bab bisa
sangat terarah karena heading styles nyata + unit berulang yang regular, tapi
WAJIB ada langkah tinjauan manusia untuk empat ambiguitas format + pembersihan
pembusukan. Batas V0 yang jujur: ini SATU template, dari perusahaan yang
template kita sendiri dimodelkan darinya — generalisasi butuh 1-2 template dari
sumber lain (masih dicari).

**Bentuk V1 yang disarankan**: kompilasi MANUAL template PREMCO ini jadi
template kedua di sistem (template Jinja + reference.docx tersintesis + bar
judul biru + tabel ganda SysReq), sekaligus membuat pipeline melayani >1
template. Semua mekanisme yang dibutuhkan sudah ada: template = data, rupa =
reference.docx, penyimpangan = post-process.
