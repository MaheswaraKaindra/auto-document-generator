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
fix terbukti pada diagram LLM sungguhan, bukan sintetis. Menyingkap keterbatasan
parser baru (App Router route handler tak terdeteksi endpoint; dampak ringan,
dokumen tetap berjejak). **218 test hijau**. Commit: `6b6dd12` (font+tabel),
`663a594` (docs), `1330f9b` (Remark), `9c55248` (premco lewati diagram tak
dipakai), `7367382` (docs MyPertamina), `0f0866c` (sanitasi Nuxt), `6c66d6c`
(kurung berimbang nuxt/movies), `93c6264`+`3d3861d`+`1ebfd0a` (validasi + docs)
+ commit ini.

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

**Perbandingan 16 bab SUDAH dilakukan (tak ada gap ketujuh). premco praktis
demo-ready. Bug Nuxt default SUDAH diperbaiki. Kandidat berikutnya:**

1. ~~**Bug `default` crash pada Nuxt/Next**~~ — **SELESAI & DIVALIDASI 3 repo, 2
   framework**: `_sanitize_route_param_brackets` di `_normalize_plantuml` melepas
   kurung route-param sebelum plantuml.jar (deterministik, $0, diagram TETAP
   dirender bukan placeholder). (1) MyPertamina (Nuxt `.vue`, PROBE18) — fix
   pertama. (2) nuxt/movies (Nuxt `.vue`) — mengungkap gap overfit (param jadi
   segmen pertama `[[type]/...` memakan kurung komponen); diperbaiki dgn cocok
   kurung berimbang, double dulu (PROBE19). (3) shadcn-ui/taxonomy (**Next.js
   `.tsx`, App Router**) — lolos TANPA perubahan kode; route group `(marketing)`
   (kurung BIASA) dipertahankan sementara kurung siku dilepas; `[[...slug]]` &
   `[...nextauth]` bersih. **Pelajaran: 1 repo = fix jalan, 2 repo = fix general,
   3 repo (framework lain) = fix tak sempit ke satu ekosistem.** Uji ketiganya
   $0 (tarik nama file asli + render sintetis plantuml.jar, tanpa LLM). Sisa yang
   MUNGKIN suatu saat: resiliensi per-diagram (placeholder untuk PlantUML rusak
   lewat jalur lain) — sengaja belum, menjaga filosofi gagal-berisik.
2. **3 gap Contract B — SEBAGIAN BESAR DIBATALKAN setelah dibuka** (bukan lagi
   "~$0,25 regen"): SysReq table-2 = kompatibilitas Browser/Android = deployment,
   TAK code-derivable (kolom Remark sudah ditambah $0, tabel kedua di-drop); flow
   nested redundan dgn diagram flow + esteler tak bercabang jadi regen tak akan
   membuktikannya; deskripsi "fitur utama" redundan dgn bab Features. Sisa yang
   layak SUATU SAAT: flow nested sebagai peningkatan Contract B, diverifikasi
   pada repo yang logika bisnisnya bercabang (BUKAN esteler).
3. **Deteksi endpoint Next.js/Nuxt route handler** (BARU, dari tes taxonomy).
   App Router `app/api/**/route.ts` pakai named-export `export async function
   GET/POST(req)`, Nuxt `server/api/*.ts` pakai `defineEventHandler` — dua-duanya
   tak dikenali `_ts_endpoints`. taxonomy = 0 endpoint dari 130 file. **Dampak
   ringan & terbukti** (dokumen tetap berjejak, LLM simpulkan dari nama file),
   tapi INI SATU-SATUNYA gap endpoint yang bisa dibuktikan END-TO-END (taxonomy
   muat 20K token) — beda dari Django/Flask yang tak punya kasus terverifikasi.
   Kalau mau menambah dukungan endpoint, INI kandidat termudah & terverifikasi.
4. **UAT premco** (roadmap tahap b) — **BLOCKER: tidak ada acuan UAT Pertamina
   di repo** (dicek: cuma ada `uat_template.md` & output kita sendiri). Registry
   `premco` pun baru SDD. Mengerjakannya sekarang = menebak. Butuh pemilik
   membawa dokumen UAT dari kantor.

**Yang cuma bisa diambil pemilik SELAGI magang** (kedaluwarsa saat magang
selesai, beda dari kerja poles yang bisa kapan saja): (a) dokumen **UAT**
Pertamina, (b) 1-2 template dari **sumber lain** (vendor/divisi lain) untuk
membuka V2, (c) penilaian engineer Pertamina atas PROBE16/PROBE15.

**Menggantung dari sesi-sesi lalu (masih berlaku):**
- Revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY` (menggantung berkali-kali).
- Isi `GITHUB_TOKEN` di .env.
- ZIP → dokumen belum tersambung.

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
- Dua tugas lama: revoke API key lama, isi GITHUB_TOKEN.
