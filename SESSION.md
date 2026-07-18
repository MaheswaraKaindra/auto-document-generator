# Catatan Sesi — 2026-07-18

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Pemilik menegaskan arah: **fokus menyempurnakan template Pertamina** (dia magang
di sana), SaaS/V2 ditunda karena tidak ada template sumber lain untuk dilatih.
Lalu bertanya *"apakah SDD sudah sempurna?"* — dan jawabannya (setelah MEMBUKA
template, bukan mempercayai catatan) **belum**: status "SDD SELESAI" ternyata
distempel untuk template `default`, sementara `premco` — yang justru dimaksudkan
JADI dokumen Pertamina — mewarisi status itu tanpa diperiksa. Dikerjakan **nomor
1 & 2 dari daftar 4 gap**, semuanya lapisan presentasi, biaya **$0**: (1) **font**
diperbaiki dari Aptos ke Calibri (bug: komentar build script MENALAR bukan
mengukur), (2) **How to Access → tabel checklist**, **Infrastructure → kerangka
22 baris**. Diverifikasi VISUAL (docx→PDF→PNG→dilihat). Lalu **perbandingan 16 bab
premco×PREMCO**: TIDAK ada gap ketujuh (3 kecurigaan semuanya kosmetik); sisa
beda = 3 gap Contract B, tapi MEMBUKA bab-nya membatalkan rencana regen — tak
satu pun jujur bisa diisi dari kode (SysReq table-2 = kompatibilitas browser =
deployment; flow nested redundan dgn diagram & esteler tak bercabang; deskripsi
list redundan). Cuma kolom Remark SysReq yang benar & $0 (dikerjakan). Terakhir
**tes repo NYATA `MyPertamina.id-Clone` (Vue/JS, ~$0,20)** membuktikan klaim
netral-bahasa DAN mengungkap bug Nuxt (file `[slug].vue` merusak PlantUML,
mematikan generate premco lewat diagram yang tak dipakainya) — diperbaiki.
Lalu **bug default Nuxt diperbaiki di akar** (sanitasi kurung route-param di
PlantUML, deterministik & $0) — default kini render component_integration
MyPertamina dengan benar (pemetaan FE↔BE utuh, PROBE18). Fix itu **divalidasi 3
repo / 2 framework** SINTETIS ($0): MyPertamina + nuxt/movies Nuxt `.vue`,
taxonomy Next.js `.tsx` — repo kedua mengungkap gap overfit, repo ketiga lolos
tanpa perubahan kode. Lalu **tes END-TO-END Next.js** (taxonomy penuh lewat LLM,
~$0,20) menutup: LLM ALAMI menghasilkan `[...nextauth]` bersarang di label
komponen (persis pola bug), sanitizer menanganinya, diagram render bersih —
fix terbukti pada diagram LLM sungguhan, bukan sintetis. Tes itu **menyingkap
gap parser** (App Router route handler tak terdeteksi endpoint), yang lalu
**DIPERBAIKI**: `route.ts` named export → endpoint, taxonomy 0→8. **234 test
hijau**. Commit: `6b6dd12` (font+tabel), `663a594` (docs), `1330f9b` (Remark),
`9c55248` (premco lewati diagram tak dipakai), `7367382` (docs MyPertamina),
`0f0866c` (sanitasi Nuxt), `6c66d6c` (kurung berimbang nuxt/movies),
`93c6264`+`3d3861d`+`1ebfd0a` (validasi bracket + docs), `6109bce` (docs
end-to-end), `2ed7a8e` (endpoint App Router) + commit ini.

## Yang diselesaikan (babak 1-5 presentasi $0; babak 6-10 menyentuh compiler/LLM)

| # | Apa | Inti |
|---|---|---|
| 1 | **Font → Calibri** | reference.docx keluar ber-Aptos. Sebab: komentar `build_reference_docx.py` "Calibri kebetulan font tema bawaan Pandoc" — SALAH, bawaannya Aptos. Font datang dari TEMA (`theme1.xml`, `asciiTheme=minor/majorHAnsi`), bukan style — makanya semua style benar tapi tiap huruf salah. `_set_theme_fonts` menulis ulang `<a:latin>` major+minor. Menyentuh KEDUA template. |
| 2 | **How to Access → tabel** | Checklist 2 baris (Internal, Published to Internet), kolom Deskripsi YES/NO + Remark — diukur dari docx asli. Field `how_to_access` (teks bebas) diganti 4 field `access_*`; YES/NO jadi dropdown frontend. Kedua template. |
| 3 | **Infrastructure → kerangka** | 22 baris kosong (Akses URL/Server/DB/Web Service per env, Rev. Proxy, TFS) diisi manual di Word — isinya URL deployment. HANYA template premco; default tetap teks bebas. |
| 4 | **Penomoran tabel bergeser** | How to Access disisipkan jadi Tabel 4, sisanya +1, di kedua template. Test penomoran menangkapnya. |
| 5 | **3 test penjaga baru** | Font tema (satu-satunya yang bisa menangkap bug Aptos), tabel How to Access, kerangka Infrastructure. |
| 6 | **SysReq kolom Remark** | premco jadi 4-kolom seperti acuan. Tabel kedua ("Server Side 2") SENGAJA di-drop: isinya kompatibilitas Browser/Android = deployment, tak dapat diturunkan kode. `1330f9b`. |
| 7 | **Perbandingan 16 bab premco×PREMCO** ($0) | Skeleton extractor (`compare_skeleton.py`) diff kedua docx. Verdict: struktur lengkap & sepadan, TIDAK ada gap ketujuh. 3 kecurigaan (demografi 8v7, activity 7v6, use case) semuanya kosmetik. Sisa beda nyata = 3 gap Contract B — tapi membuka bab-nya membatalkan regen (tak jujur code-derivable). |
| 8 | **Tes repo NYATA MyPertamina (Vue/JS)** | Klaim netral-bahasa TERBUKTI: dokumen berjejak (Nuxt/JWT/Express/model dgn bukti kode), aktor bisnis, ~$0,20. Bug Nuxt ditemukan+diperbaiki (bawah). `9c55248`. Probe: `out/PROBE17_mypertamina_premco.docx`. |
| 9 | **Fix bracket Nuxt/Next + sanitizer** | premco lewati diagram tak dipakai (`9c55248`); default disanitasi (`0f0866c`); kurung berimbang untuk param segmen-pertama (`6c66d6c`). Divalidasi 3 repo sintetis + 1 end-to-end. `_sanitize_route_param_brackets`. |
| 10 | **Tes END-TO-END Next.js taxonomy** (~$0,20) | Pipeline penuh: konten berjejak (Prisma/NextAuth/Stripe/Contentlayer benar, aktor Guest/Terdaftar), fix bracket terbukti pd diagram LLM SUNGGUHAN (`[...nextauth]` alami → tersanitasi → render bersih). Menyingkap gap parser App Router (0 endpoint, dampak ringan). Probe: `PROBE20_taxonomy_default.docx` (dgn integrasi), `PROBE21_taxonomy_premco.docx`. |
| 11 | **Deteksi endpoint Next.js App Router** | taxonomy 0→8 endpoint. Named export `GET/POST` di `route.ts`, path dari folder (route group dibuang, `[id]`→`:id`). Ditulis dari AST NYATA. 16 test (`test_parser_app_router.py`, file test TS pertama). `2ed7a8e`. |

## Kejadian yang layak diingat (jebakan, semua DIPROBE)

- **Word COM MENGGANTUNG di `updateFields=true`.** reference.docx menyalakan
  updateFields; saat Word membuka file, muncul dialog "update fields?" yang TAK
  terlihat karena `Visible=False` → gantung selamanya (CPU mentok lalu DATAR =
  modal, bukan komputasi). `DisplayAlerts=0` TIDAK menjangkaunya. Solusi: buang
  `<w:updateFields>` dari SALINAN docx dulu, TOC diisi manual via COM
  `TablesOfContents.Update()`. Skrip: `scratchpad/topdf2.py`.
- **NBSP dari smart-punctuation Pandoc.** "Internal Rev. Proxy" keluar sebagai
  "Internal Rev.\xa0Proxy" (spasi sesudah singkatan jadi non-breaking) — di layar
  identik, tapi assertion `in` gagal. `_docx_text` di test menormalkan `\xa0`.
- **Bug "SDD selesai" = pola "periksa proksi bukan barangnya" ke-6.** Proksinya
  kali ini catatan status kita sendiri. Insting pemilik ("apakah sudah
  sempurna?") yang menemukannya, bukan saya.
- **pywin32 + pymupdf DEV-ONLY** — dipasang untuk verifikasi visual, SENGAJA
  tidak masuk requirements.txt (bukan dependency aplikasi).
- **Kurung siku Nuxt/Next merusak PlantUML.** File `[category]/[slug].vue`
  masuk ke sintaks komponen `[...]` → bersarang → syntax error. Kelas bug yang
  cuma muncul di repo ASLI (mock lewatkan, seperti 414 mermaid). premco kebal
  sesudah fix (tak pakai component_integration); **default MASIH crash** — item
  Keterbatasan. Buka bab yang salah bukan yang dipakai bisa mematikan seluruh
  dokumen: `_build_sdd_context` dulu render KEEMPAT diagram tanpa peduli template.

## Kalau melanjutkan besok, mulai dari sini

**Semua pekerjaan repo-only sesi ini SELESAI** (bracket fix 3 repo + end-to-end,
App Router endpoint, A/B — detail di CLAUDE.md Riwayat 2026-07-18). Yang penting
untuk sesi berikutnya bukan daftar sisa teknis, tapi ARAH — dan arahnya berubah.

**TEMUAN STRATEGIS (baca ini sebelum memutuskan kerja apa): sumur pekerjaan
bernilai-tinggi yang bisa dikerjakan DARI REPO SAJA mulai kering.** A/B endpoint
(v2 regen ~$0,20) membuktikan LLM sudah pandai menyimpulkan struktur dari nama
file — endpoint eksplisit MERAMBAT (v2 pakai notasi parser `:postId`, v1 nebak
`{postId}`) tapi peningkatan kualitasnya MARGINAL karena v1 pun sudah akurat.
Implikasinya: **menambah bahasa/presisi parser (Nuxt server-routes, Pages Router,
Go, Kotlin) kemungkinan besar juga marginal** untuk kualitas dokumen — satu-satunya
nilai jual. Itu kerja NYAMAN (centang hijau, bisa dari repo), bukan kerja
BERHARGA. Jangan tambah bahasa parser lagi tanpa alasan kualitas yang jelas.

**Dua hal yang benar-benar menggerakkan produk terhalang input yang CUMA PEMILIK
bisa bawa** (bukan masalah coding, dan KEDALUWARSA saat magang selesai):
1. **Dokumen UAT Pertamina** → membuka roadmap tahap (b), pekerjaan terbesar yang
   tersisa. Registry premco baru SDD; mengerjakan UAT tanpa acuan = menebak (cuma
   ada `uat_template.md` & output sendiri). **Prioritas: ambil selagi di sana.**
2. **1-2 template dari sumber LAIN** (vendor/divisi lain) → membuka V2 (upload
   template sembarang). V0/V1 baru terbukti pada SATU sumber PREMCO.

**Kalau input eksternal BELUM ada, kerja repo-only yang masih BERHARGA (bukan
marginal) = tepi DEPLOYMENT, bukan fitur baru:**
- Job mati saat proses restart (belum ada reaper untuk `running` basi).
- Jalur ZIP → dokumen belum tersambung (`GenerateDocumentRequest` cuma terima repo GitHub).
- OAuth GitHub baru scaffold (belum ada OAuth App terdaftar).
- Dokumen tumbuh selamanya (belum ada TTL/pembersihan).

**Utang lama (masih berlaku, cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`;
isi `GITHUB_TOKEN` di .env.

## Yang perlu dilakukan manusia

- **Buka `scripts/validation/out/PROBE16_font_tabel_premco_esteler.docx`** —
  esteler gaya premco dengan font Calibri + How to Access & Infrastructure
  berbentuk tabel; sandingkan dengan docx PREMCO asli. (Daftar Gambar/Tabel di
  probe ini menampilkan placeholder karena skrip verifikasi hanya meng-update
  TOC utama, bukan TablesOfFigures — bukan cacat dokumen, cuma probe.)
- **Buka `scripts/validation/out/PROBE17_mypertamina_premco.docx`** — dokumen
  gaya premco dari repo NYATA MyPertamina.id-Clone (Vue/JS), bukan esteler.
  Bukti pipeline netral-bahasa. Ctrl+A → F9 di Word untuk mengisi daftar.
- Untuk demo ke mentor: pakai PROBE17 (repo relevan Pertamina) atau PROBE16;
  sebut sendiri 3 beda yang tersisa (SysReq client-compat, kolom Entitas Tim,
  flow flat) sebagai "sengaja tak dikarang dari kode", bukan tunggu ditemukan.
- **Bukti pipeline netral-bahasa (Next.js/TSX):** `PROBE20_taxonomy_default.docx`
  (dgn diagram Integrasi Komponen) & `PROBE22_taxonomy_default_v2.docx` (versi
  dengan endpoint eksplisit). Buka kalau mau lihat produk jalan di luar Vue/Python.
- **PALING PENTING selagi masih magang** (kata Claude sesi ini, disetujui alur):
  bawa **dokumen UAT Pertamina** dan **1-2 template dokumen dari sumber/vendor
  lain**. Itu satu-satunya yang membuka pekerjaan besar berikutnya dan tak bisa
  diambil setelah keluar. Kerja poles bisa kapan saja; akses tidak.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
