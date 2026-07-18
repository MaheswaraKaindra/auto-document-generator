# Catatan Sesi — 2026-07-18 (V2: kelayakan upload-template multi-sumber)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi UAT premco sebelumnya laptop **mati sebelum commit** — kerjanya utuh di
working tree (diverifikasi 239 test hijau) lalu **di-commit ulang** (`92e9a77`).
Pemilik lalu membawa **5 template dokumen** (memenuhi permintaan V0: *"generalisasi
butuh 1-2 template dari sumber lain"*), jadi dikerjakan **riset kelayakan V2**
(upload template sembarang). Dari 5: **3 template isian** (SDD gaya IEEE/CMS,
UAT ID keluarga-PREMCO, UAT EN generik) + 2 acuan (standar IEEE 1016, panduan
UAT). Diukur mekanis (`python-docx`; `.doc` dikonversi via Word COM). **Temuan
crux**: sintesis **visual GENERALISASI** (tiap properti terukur lintas 5, nilai
liar — 5 warna header beda), pemetaan **isi TIDAK** (Contract B berbentuk PREMCO)
→ template asing = **placeholder jujur** (degradasi anggun), bukan biner
luas-vs-fokus. **Arsitektur diputus: X = kompilasi upload jadi template terdaftar**
(bukan swap runtime yang corrupt). **3 increment terbukti sebagai SATU RANTAI
($0)**: (1) `TemplateSpec` ukur→JSON; (2) sintesis reference.docx dari spec
(A/B tipografi terbukti render); (3) prototipe loop penuh pada `04`
(outline→generate template→isi→render dokumen `04`-style). Laporan durable
`scripts/validation/V2_TEMPLATE_MULTISOURCE.md`; PROBE26/27. **V2 de-risked —
sisa = IMPLEMENTASI, bukan kelayakan.** Implementasi lalu DIMULAI: **increment 1
(`TemplateSpec`) dikonsolidasi dari scratchpad jadi `app/services/template_spec_service.py`
+ 2 tes fixture sintetis, ter-commit (`6f69ff4`), 241 test hijau.**

## Yang diselesaikan

| # | Apa | Inti |
|---|---|---|
| 1 | **Pulihkan + commit kerja UAT premco** | Laptop mati sebelum commit; working tree utuh, 239 test hijau, di-commit `92e9a77`. `*.doc` ditutup gitignore (dokumen vendor). |
| 2 | **Konversi `.doc`→`.docx`** | Word COM (pywin32) — python-docx tak baca `.doc`. |
| 3 | **Ukur 5 template** | 3 isian + 2 acuan (SDD.docx = standar IEEE 1016; Veracity = panduan). Keragaman struktur & warna header NYATA. |
| 4 | **Keputusan arsitektur V2 = X** | Kompilasi upload jadi template terdaftar; pakai ulang pipeline matang; LLM cuma peta; manusia tinjau. |
| 5 | **Increment 1 — `TemplateSpec`** | Kontrak JSON ukur→struktur. Font EFEKTIF wajib di-resolve (`04`=Verdana bukan Calibri temanya — bug-Aptos berulang); `caps` terukur. |
| 6 | **Increment 2 — sintesis reference.docx** | Salin reference + override sumber-spesifik (tema major/minor, heading, warna header). A/B render: `04` Tahoma/Verdana/abu vs PREMCO Calibri-caps/hitam. |
| 7 | **Increment 3 (prototipe) — loop penuh `04`** | outline→generate template Jinja→isi Contract B→render. Dokumen `04`-style lengkap, test case per-modul. Cacat = header patah di potret (konfirmasi kenapa `04` landscape). |
| 8 | **Laporan durable + PROBE** | `V2_TEMPLATE_MULTISOURCE.md`; PROBE26 (loop penuh), PROBE27 (A/B tipografi). |

## Kejadian yang layak diingat (jebakan)

- **Laptop mati ≠ kerja hilang.** Edit menulis file UTUH, jadi yang tersimpan
  terakhir lengkap. Yang hilang cuma commit. Cek `git log` vs isi disk dulu.
- **Font "efektif" ≠ satu sumber.** `docDefault` bisa bertentangan dengan style
  `Normal` dan tema; yang dirender = resolusi `Normal`→ascii/tema. Ukur itu, atau
  sintesis-nya salah font (pelajaran bug-Aptos, versi V2).
- **`.doc` biner tak terbaca python-docx.** Wajib konversi ke `.docx` dulu (Word
  COM di sini; LibreOffice tak terpasang).
- **Prototipe potret mengonfirmasi landscape.** Header 7-kolom patah di potret =
  persis alasan `04` pakai landscape. Pengukuran memprediksi, render membuktikan
  — "buka barangnya" lagi.
- **Konflik marker**: warna tabel khusus premco (hijau) via marker compiler akan
  bertabrakan dgn warna dari spec. V2 harus jadikan warna tabel khusus spec-driven.
- **Word COM konversi**: `DispatchEx` + `Visible=False` + `DisplayAlerts=0` +
  `UpdateLinksAtOpen=False`; buang `<w:updateFields>` dari docx render sebelum
  buka utk PDF (kalau tidak, menggantung di dialog "update fields?").

## Kalau melanjutkan, mulai dari sini

**Riset V2 SELESAI (kelayakan terbukti). Sisa = IMPLEMENTASI**, dan ada pilihan
prioritas yang pemilik perlu putuskan:

**Rekomendasi #1 (prioritas SELAGI MAGANG, tak bisa diambil setelah keluar):**
- Kumpulkan **lebih banyak template dari sumber/vendor lain**. Kelayakan sudah
  terbukti; N=3 (2 non-PREMCO) masih tipis untuk yakin sintesis+pemetaan general,
  bukan overfit halus. Keragaman input yang menaikkan keyakinan — bukan lebih
  banyak kode. Implementasi kerja repo-only yang TAK kedaluwarsa.

**#2 (implementasi Trek B — SUDAH DIMULAI, gaya V1). SAMPAI MANA & LANJUT DARI MANA:**
- ✅ **Increment 1 SELESAI & ter-commit** (`6f69ff4`): `app/services/template_spec_service.py`
  (`build_template_spec(docx)→dict`) + `tests/test_template_spec_service.py` (fixture
  sintetis python-docx). 241 test hijau. Aditif — nol sentuh kode lama.
- ⏭ **Increment 2 = LANGKAH BERIKUTNYA: sintesis reference.docx dari spec.**
  **Pendekatan sudah diputuskan = A**: perluas `scripts/build_reference_docx.py`
  dgn param `spec=None`. `None` = perilaku PREMCO sekarang, **byte-identik** (JANGAN
  regenerasi `app/templates/reference.docx` yang ter-commit → 239 test lama aman);
  spec terisi = override sumber-spesifik (tema major/minor terpisah, Title/Heading
  size/bold/caps/align, warna fill+teks header via kontras luminance). Logika
  TERBUKTI di scratchpad sesi ini (`synth_reference.py` — A/B tipografi `04` vs
  PREMCO, PROBE27) — ini porting kode-terbukti, bukan refactor ke ketidakpastian.
  Verifikasi: byte-compare default hasil regenerasi vs `reference.docx` ter-commit,
  + render spec-driven → lihat (docx→PDF via Word COM→PNG→Read).
- Lalu increment 3 (lebih besar, checkpoint lagi): generator template Jinja dari
  outline (prototipe `full_loop_04.py` di scratchpad) → kode `app/` + registry
  `_TEMPLATE_REGISTRY`; sintesis **landscape/orientasi per-section**; **warna tabel
  khusus spec-driven** (ganti marker hijau premco); **LLM auto-usul peta bab**
  (template asing spt IEEE SDD); **UI tinjauan pemetaan** manusia.

Catatan: kode riset increment 2-3 masih di scratchpad SESI KEMARIN (throwaway,
mungkin sudah terhapus) — kalau perlu, logikanya terekam di
`V2_TEMPLATE_MULTISOURCE.md` dan bisa ditulis ulang dari sana.

**JANGAN** lupa: #1 (kumpulkan template sumber lain — Trek A, di tangan pemilik)
tetap prioritas selagi magang; #2 berjalan paralel.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Buka `scripts/validation/out/PROBE26_v2_fullloop_04.docx` (atau `.pdf`)** —
  dokumen gaya template `04` (UAT ID sumber lain), digenerate OTOMATIS dari outline
  `04` + isi Contract B kita. Lihat: struktur bab benar, tipografi Tahoma/Verdana,
  test case dikelompokkan per-modul. Cacat sengaja: header tabel patah (butuh
  landscape — ditunda).
- **`PROBE27_v2_typografi_04.pdf` vs `..._premco.pdf`** — konten identik, dua
  identitas visual. Bukti sintesis reference.docx spec-driven.
- **PALING PENTING selagi magang:** bawa **lebih banyak template SDD/UAT dari
  vendor/sumber lain**. Satu-satunya yang tak bisa diambil setelah keluar, dan
  yang menaikkan keyakinan generalisasi V2.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
