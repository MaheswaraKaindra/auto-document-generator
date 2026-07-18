# Catatan Sesi — 2026-07-18 (lanjutan: template premco UAT)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Pemilik membawa **dokumen UAT Pertamina** (`2. UAT_...Phase 2.docx` di root,
gitignore), jadi dikerjakan **roadmap tahap (b): template `premco` UAT** —
persis cara SDD premco dibangun: **ukur dokumen aslinya dulu, jangan menebak**.
Pengukuran (`python-docx`) mengungkap UAT sangat beda dari SDD-nya: struktur
FLAT tanpa heading, nol Daftar Isi, tabel test-case 9 kolom **header HIJAU
`a8d08d`**, test case **dikelompokkan per-layar**, dan **section Case Pengujian
LANDSCAPE** (tabel 10,9 inci) — tanpa mengukur, potret ber-header patah-patah
akan terkirim. Dibangun ($0): `uat_premco_template.md` + wiring compiler
(registry premco→UAT, lewati `--toc`, grouping per `module` dengan fallback satu
tabel, marker `((GH))` header hijau, `_landscape_after_marker` pecah section) +
3 field metadata + 5 tes. **Contract B ditambah `module`** (wajib di output LLM
demi grouping andal, compiler toleran untuk data lama). Diverifikasi **$0**
(Contract B sintetis → docx → PDF → PNG → DILIHAT) lalu **berbayar ~$0,27**
(regen UAT MyPertamina dari Contract A cached): **50 test case, 17 modul unik,
0 tanpa module** — LLM mengelompokkan per-layar dengan benar, konten berjejak
ke fitur MyPertamina nyata. Visual end-to-end (15 halaman) dilihat: persis
bahasa visual PREMCO UAT. **239 test hijau** (+5). Commit: (commit sesi ini).

## Yang diselesaikan

| # | Apa | Inti |
|---|---|---|
| 1 | **Ukur dokumen UAT asli** | `python-docx`: 50 tabel, header test-case hijau `a8d08d`, section 2 LANDSCAPE (tabel 10,9"), nol Heading/TOC, boilerplate (Entry/Exit/Status/Kode Kegagalan) sudah cocok dgn `uat_template.md` default. |
| 2 | **`uat_premco_template.md`** | Flat (bold label, bukan `##`), Document Information 5-baris, Distribution From/To, Sertifikasi L/G, Prosedur, Case Pengujian per-modul. Typo asli "kesalah desain" DIBERSIHKAN. |
| 3 | **Header hijau `((GH))`** | `_apply_green_headers`: latar `a8d08d` + bold + matikan header hitam per-tabel. Marker-driven (template lain tak tersentuh). |
| 4 | **Section landscape** | `_landscape_after_marker` (marker `((LANDSCAPE))`): front-matter potret, Case Pengujian landscape. Lewat API python-docx (reference.docx tak punya pgSz). Lebar kolom disetel supaya header muat. |
| 5 | **Grouping per `module`** | `_build_uat_context` premco → `uat_test_groups` (per `module`, fallback 1 tabel). Langkah multi-baris reuse `((BR))`. Template `default` tak berubah. |
| 6 | **`--toc` dilewati premco UAT** | `_pandoc_args(...,template_id)`; dokumen asli nol field TOC. Default UAT tetap `--toc`. |
| 7 | **Contract B `UATTestCase.module`** | Wajib di output LLM + instruksi prompt (nilai SAMA PERSIS per layar, urut berdampingan). Fixture SDD/UAT diperbarui. Compiler `.get()` toleran. |
| 8 | **3 field metadata UAT** | Quality Review Method, Document Version No/Date (Document Information premco UAT). |
| 9 | **5 tes penjaga** | grouping+hijau, fallback 1 tabel, no-TOC, landscape, cabang "belum menyediakan" (via registry monkeypatch). Tes route: premco+UAT kini 202. |
| 10 | **Verifikasi berbayar ~$0,27** | Regen UAT MyPertamina: 50 tc, 17 modul, 0 tanpa module, konten berjejak, 15 hal landscape grouped. |

## Kejadian yang layak diingat (jebakan)

- **reference.docx TAK punya `<w:pgSz>`.** Swap atribut lebar/tinggi mentah =
  no-op (section tetap portrait, `w=None`). Pakai API python-docx
  (`section.page_width = Inches(11)` dst.) yang MEMBUAT pgSz-nya.
- **Mengukur menyelamatkan dari kirim potret.** Section Case Pengujian asli
  LANDSCAPE — tak akan ketahuan dari membaca teks, cuma dari mengukur orientasi
  section. Header 9 kolom patah-patah ("N o", "Kegiata n") di potret; rapi di
  landscape. Pola "buka barangnya, jangan menebak" lagi.
- **`module` wajib di schema → fixture pecah.** `UATTestCase.module` required
  membuat `/documents/sdd|uat` menolak fixture lama (422). Diperbaiki dengan
  menambah `module` ke fixture (Contract B memang kini memuatnya), BUKAN
  melonggarkan schema — LLM harus selalu grouping; compiler tetap toleran.
- **Header boilerplate premco UAT HITAM (asli putih).** Beda minor yang
  disengaja — konsisten gaya rumah (default & SDD premco), dan tabel-tabelnya
  punya baris header wajar jadi hitam terbaca. Hijau cuma untuk tabel test-case.
- **Word COM `topng.py`** (verifikasi visual): buang `<w:updateFields>` dari
  SALINAN docx dulu (kalau tidak, Word menggantung di dialog "update fields?"
  dengan Visible=False). pywin32+pymupdf DEV-ONLY, tak masuk requirements.txt.

## Kalau melanjutkan besok, mulai dari sini

**Roadmap tahap (a) SDD premco & (b) UAT premco: SELESAI.** premco kini
menyediakan SDD DAN UAT, dua-duanya diverifikasi end-to-end pada repo nyata
(esteler + MyPertamina). Yang tersisa dari visi produk:

**Terhalang input yang CUMA PEMILIK bisa bawa** (bukan coding; kedaluwarsa saat
magang selesai — AMBIL SELAGI DI SANA):
1. **1-2 template dokumen dari sumber/vendor LAIN** → membuka **V2** (upload
   template sembarang + sintesis reference.docx). V0/V1 + kini UAT semua terbukti
   pada SATU sumber PREMCO; generalisasi butuh template dari perusahaan lain.

**Kerja repo-only yang masih BERHARGA (tepi DEPLOYMENT, bukan fitur/bahasa baru
— sumur parser sudah kering, A/B membuktikan marginal):**
- Reaper job `running` basi (job mati saat proses restart, belum ada yang memungut).
- Jalur ZIP → dokumen belum tersambung (`GenerateDocumentRequest` cuma repo GitHub).
- OAuth GitHub baru scaffold (belum ada OAuth App terdaftar).
- Dokumen tumbuh selamanya (belum ada TTL/pembersihan).
- (Kualitas) Verifikasi aturan anti-karangan diagram pada fastapi (~$0,20) — satu-
  satunya karangan terkonfirmasi, fix di SYSTEM_PROMPT belum pernah diverifikasi.

**JANGAN** tambah bahasa/presisi parser (Go/Kotlin/Nuxt-server/Pages-Router)
tanpa alasan kualitas nyata — A/B endpoint membuktikan MARGINAL.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Buka `scripts/validation/out/PROBE25_uat_premco_mypertamina.docx`** — UAT
  gaya PREMCO dari repo NYATA MyPertamina (Vue/JS), test case dikelompokkan
  per-layar, tabel landscape hijau. Ctrl+A → F9 di Word untuk isi field (kalau ada).
  Sandingkan dengan dokumen UAT PREMCO asli — sebut sendiri beda yang disengaja
  (header boilerplate hitam vs putih; kolom Penguji/Tanggal/Status/Komentar
  kosong = diisi manual tim penguji).
- **`scripts/validation/out/PROBE24_uat_premco_synthetic.docx`** — versi data
  sintetis (grouping + fallback terlihat), untuk melihat mekanismenya.
- **PALING PENTING selagi masih magang:** bawa **1-2 template dokumen dari
  sumber/vendor lain** — satu-satunya yang membuka V2 dan tak bisa diambil
  setelah keluar. UAT & SDD Pertamina sudah tertutup; yang berikutnya butuh
  keragaman sumber.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
