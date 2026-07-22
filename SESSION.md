## TERBARU #6: activity SANGAT dekat draw.io (2026-07-22) — BELUM di-commit

Menjawab "gimana caranya supaya sangat mirip draw.io". Gap sisanya diprobe:
1. **Diamond keputusan** — `skinparam conditionStyle InsideDiamond` (diprobe 3
   varian; bawaan PlantUML heksagon, ini diamond berteks-di-dalam = acuan).
2. **Pita judul DI DALAM kotak** — `_add_diagram_title` menyisipkan `title
   <activity_name>`; karena bingkai ditarik pada kotak-batas isi, judul ikut
   terkurung di atas baris nama lane. `_swimlane_header_bottoms` (jamak)
   mendeteksi sampai 2 pita header — dengan judul 2 garis, tanpa judul 1.

Struktur acuan kini lengkap: pita judul + header lajur + kotak tertutup + diamond.
**Tak bisa ditiru (batas PlantUML, jangan dikejar lagi)**: tanda X di dalam
diamond, garis putus-putus alur balik.

**329 test hijau**, `render_fixtures` 0 gagal.

## TERBARU #5: swimlane jadi TABEL + batas lebar switch (2026-07-22) — BELUM di-commit

Pemilik: *"kiri tabel user, kanan tabel sistem — tabel sebagai background, activity
menyesuaikan"*. Diperiksa ke render nyata: bingkai luar & pemisah vertikal SUDAH ada;
yang kurang **garis horizontal di bawah baris judul lane** (tanpa itu judul cuma teks
mengambang, bukan header tabel). `_swimlane_header_bottom` mendeteksinya dari profil
tinta per baris, dijaga `_SWIMLANE_HEADER_MAX_FRAC` (0,25) agar tak memotong diagram.

**Regresi dari lanjutan-3 yang ikut ditutup**: prompt `switch` membuat tiap `case`
jadi kolom SEJAJAR — terukur 2 dari 7 activity melar (6 case → rasio 4,28), huruf
mengecil di halaman. Prompt diberi **batas maksimal 4 `case` per `switch`**.
**Batas ini BELUM diverifikasi ulang ke LLM** (butuh 1 panggilan ~$0,2).

**329 test hijau.**

# Catatan Sesi — 2026-07-21 (lanjutan 10): cover/tanda tangan/hierarki premco PERSIS PREMCO

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan). SESSION.md itu **foto sesaat**.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.** Detail perubahan ada di
> **CHANGELOG.md** (entri teratas = sesi ini).

---

## ⚠️ BACA DULU: kuota API kemungkinan masih habis

Seluruh sesi ini dikerjakan **$0, nol panggilan LLM**. Langkah berbayar HANYA
Contract A → Contract B; begitu Contract B tersimpan, `template → diagram → docx`
bisa diulang tanpa batas. Jadi seluruh pekerjaan Peran 3 (template, tabel,
cover, tanda tangan, TOC) tetap bisa dikerjakan DAN diverifikasi tanpa bayar.

- Render cepat semua fixture: `python scripts/render_fixtures.py --out hasil/`
- **JANGAN ubah skema Contract B** selama kuota habis — fixture tersimpan langsung
  jadi SKEMA-LAMA dan tak bisa dibuat ulang tanpa membayar.

## ⚠️ STATUS COMMIT (baca ini)

- Pekerjaan **cover/tanda tangan/hierarki premco + align kanan + infra merge**
  (di bawah) **SUDAH di-commit & push** ke `develop` (commit `8cb1392`).
- Pekerjaan **TERBARU: "tema enterprise" diagram (Fase 1) + swimlane activity
  (Opsi B)** — **BELUM di-commit.** Menunggu review pemilik. File tersentuh:
  `app/services/compiler_service.py` (`_PLANTUML_STYLE_PREAMBLE`,
  `_add_swimlanes`, `_render_activity_diagram`),
  `tests/test_compiler_service.py` (+6 test), `CLAUDE.md`, `CHANGELOG.md`,
  `SESSION.md`.

## TERBARU #4: "Opsi A" — prompt diperkaya (2026-07-22) — BELUM di-commit

Pemilik memberi akses penuh mengubah prompt. Tiga gap ISI ditutup di
`llm_service.SYSTEM_PROMPT`: use case wajib `<<include>>`/`<<extend>>` bila
berjejak; business flow jadi ATURAN sendiri (flowchart, DILARANG swimlane, wajib
≥2 keputusan); activity jadi ATURAN sendiri (wajib swimlane + `switch` + workflow
fitur utuh, sasaran 8-16 langkah). Ditambah **ATURAN KEJUJURAN KEPADATAN** sebagai
rem: angka sasaran BUKAN kuota, "8 langkah berjejak > 16 langkah separuh karangan".

**Hasil verifikasi berbayar (1 panggilan, ~$0,2, 191 detik) di esteler:**
use case 0→**5** relasi; business flow 0→**3** keputusan & 0 lajur (benar);
activity **7-11 langkah, 1-3 keputusan**, LLM menulis swimlane sendiri.
**Audit karangan: nol temuan** (istilah teknis di diagram semuanya berjejak di
Contract A). Contract B kaya itu dipromosikan jadi `dummy_data/contract_b_rich_sdd.json`
supaya regresi $0 ikut menguji swimlane/switch/include-extend.

Bug tertutup: `_render_activity_diagram` dulu cuma membingkai kalau KITA yang
menambah lane — begitu LLM menulis lane sendiri, bingkai lolos. Sekarang
`_has_swimlanes` (hasil akhir) yang menentukan.

`render_fixtures` 0 gagal, **328 test hijau**.

## TERBARU #3: gaya diagram per-tipe + bingkai swimlane (2026-07-22) — BELUM di-commit

Dari 4 gambar acuan pemilik (use case PREMCO, activity draw.io, flowchart proses
bisnis) + arahan *"use case, activity, flow bisnis tidak perlu tema"*:
1. **Gaya per-tipe** — `_PLANTUML_PLAIN_PREAMBLE` (UML hitam-putih) untuk use case,
   activity, flow bisnis; tema BERWARNA tetap untuk arsitektur & integrasi komponen.
   `_normalize_plantuml`/`_render_diagram_to_image` kini punya parameter `style`.
2. **Bingkai penutup swimlane** (`_close_swimlane_border`) — PlantUML cuma
   menggambar garis vertikal, kotaknya menganga; 2 varian skinparam diprobe →
   output identik, jadi PlantUML memang tak punya opsinya. Bingkai digambar pada
   kotak-batas isi sesudah PNG jadi.
3. **Flow bisnis dilepas dari swimlane** (mengoreksi #2 di bawah) — di acuan ia
   flowchart bercabang, bukan berlajur.

Diverifikasi visual end-to-end. **328 test hijau** (+3).

**Sisa yang BUTUH prompt (Opsi A, belum diambil)**: relasi `<<include>>`/
`<<extend>>` di use case, dan percabangan/loop lebih kaya di flow bisnis &
activity. Semuanya ISI, bukan rupa — perlu 1 panggilan LLM berbayar utk verifikasi.

## TERBARU #2: activity diagram ber-SWIMLANE (2026-07-22, "Opsi B") — BELUM di-commit

Pemilik menunjukkan activity diagram **draw.io** asli (PREMCO "Sarana & Fasilitas –
Tab EDC") sebagai standar. **Diagnosis ulang**: ciri pembedanya bukan engine/tema,
melainkan **SWIMLANE** (kolom User|Sistem) — dan **PlantUML mendukungnya native**,
jadi D2/draw.io tak diperlukan. Yang kurang cuma info "siapa mengerjakan apa", dan
itu SUDAH ada: prompt mewajibkan langkah difrasakan "Aktor melakukan X"/"Sistem
merespons Y". `_add_swimlanes` membacanya → sisip `|Lane|` saat lane BERUBAH; nama
lane manusia dari field `actor` Contract B. **Nol perubahan pipeline AI.**
Prototipe $0 di 8 diagram esteler: **8/8 render, 0 ambigu**. Aman: sudah-ber-lane
tak ditimpa; non-activity (arsitektur/komponen/use case) tak tersentuh; langkah
ambigu mewarisi lane (bukan ditebak); `_render_activity_diagram` fallback ke versi
tanpa lane kalau gagal. Diverifikasi end-to-end (bake Word→PDF→lihat). Efek
samping bagus: dokumen **30 → 26 halaman**. **325 test hijau** (+5).

**Sisa yang BELUM diambil**: menaikkan KEKAYAAN alur (lebih banyak langkah,
keputusan berlabel, loop balik seperti acuan draw.io) — itu butuh penyetelan
**prompt** ("Opsi A"), dan perlu 1 panggilan LLM berbayar (~$0,11–0,17) untuk
verifikasi. Menunggu keputusan pemilik.

## TERBARU: kualitas visual diagram (Fase 0 → Fase 1, 2026-07-22)

Pemilik minta diagram mendekati draw.io/enterprise **tanpa mengubah pipeline AI**.
Dikerjakan sebagai diskusi arsitektur dulu, lalu **Fase 0** (perbandingan
berdampingan $0 di scratchpad: PlantUML kini vs ber-tema vs D2 pada diagram
esteler). **Temuan**: D2 unggul HANYA di graf-node arsitektur; untuk use case +
activity PlantUML ber-tema JUSTRU lebih bagus; dan D2 butuh Playwright (headless
browser) untuk PNG — dep berat yang dihindari. Ikon (Fase 1.5) dievaluasi &
DITOLAK (glyph generik redundan dgn bentuk; logo vendor = cherry-pick).
**Dikirim Fase 1**: `_PLANTUML_STYLE_PREAMBLE` jadi tema enterprise (rounded +
shadow + palet biru-abu), `!theme plain` tetap basis lalu ditimpa skinparam.
Nol perubahan pipeline AI, nol dep baru. Diverifikasi VISUAL end-to-end (render
esteler premco → bake Word → PDF → lihat; arsitektur/use case/activity ber-tema).
**320 test hijau.** Perbandingan Fase 0 ada di Desktop `fase0-diagram-comparison/`.
Kalau kelak mau kualitas draw.io PENUH: jalurnya parser PlantUML→IR→D2 (Fase 3,
scaffold `app/diagram/` sudah ada) — tapi Fase 0 menunjukkan itu belum tentu perlu.

## Ringkasan satu paragraf (sesi cover/tanda tangan premco — SUDAH di-commit)

Pemilik menaruh gambar berdampingan (output kita vs docx PREMCO asli) dan minta
**cover template `premco` SDD dibuat PERSIS PREMCO** (6 permintaan konkret).
Semuanya dikerjakan **$0** dan **diverifikasi VISUAL** (render → bake field via
Word COM → export PDF → raster → LIHAT halamannya, bukan cuma baca XML). **319
test hijau** (+7), `vite build` hijau — **sudah di-commit `8cb1392`.**

## Yang selesai sesi ini (6 permintaan pemilik)

Semua perubahan ada di template **`premco` saja** + fungsi compiler **opt-in lewat
marker**, jadi template `default` (aesthetic minimalis yang sudah disetujui
pemilik) **tak tersentuh** — semua test default tetap hijau tanpa satu pun diubah.

1. **Cover** (`request 1`) — dari cover minimalis borderless jadi **tiga tabel
   berbingkai header GELAP** persis PREMCO: `Fungsi | No Kodifikasi`,
   `Katalog Proses Bisnis | No. Kategori Proses`, `Entitas | Jabatan | Nama`.
   Header hitam otomatis dari style tabel reference.docx (fill PREMCO 3b3838/252525
   praktis = hitam). Kolom **Entitas di-merge vertikal** (marker baru `((CVMERGE))`
   → `_merge_cover_entity_column`). Field metadata baru **`entitas`** (nama
   perusahaan) di schema + form frontend.

2. **+3. Tanda tangan** (`request 2 & 3`) — Perwakilan User & Pengembang jadi
   **bar judul HITAM (000000) selebar tabel + 2 kolom × 2 baris** (ruang tanda
   tangan di atas ±1 inci, nama di bawah), bukan lagi tabel 3-kolom
   Nama/Jabatan/Tanda Tangan. Marker baru `((SIGBAR))` → `_apply_signature_bars`.
   `_apply_title_bars` di-refactor berbagi helper `_merge_first_row_into_bar`
   (biru `((BAR))` teks gelap vs hitam `((SIGBAR))` teks putih).

4. **Hierarki bab** (bagian `request 4`) — Use Case / Activity Diagram / Mockup
   Website / Mockup Aplikasi digeser dari `#` (Heading 1) ke `## 1./2./3./4.`
   (Heading 2 bernomor) di bawah Flow Proses Bisnis — meniru Daftar Isi docx asli.

**Dua penyempurnaan lanjutan (lanjutan 11)** dari feedback pemilik atas output
esteler NYATA (setelah test end-to-end berbayar berhasil):
5. **Cover di-align KANAN** — blok judul (eyebrow + judul + baris identitas)
   diratakan kanan meniru cover PREMCO (`_right_align_cover`, flag
   `cover_align_right` premco-only + SDD-only; default tetap tengah).
6. **Tabel Infrastructure: sel kosong digabung** — baris yang sub-environment
   (idx 2) & Remark (idx 3) dua-duanya kosong (Infrastructure Tech Req, Network,
   Data Center) jadi satu sel lebar (`_merge_infra_empty_cells`); baris ber-sub-env
   (Akses URL) tetap terpisah. Meniru docx PREMCO.

## Temuan penting: Daftar Isi/Gambar/Tabel "kosong" (`request 4-6`) — BUKAN bug

Field code TOC (`fldSimple TOC ...` + `updateFields=true`) **sudah benar dan lama
ada**. Dibuktikan lewat **Word COM**: begitu field di-update, ketiga daftar terisi
LENGKAP + nomor halaman + hyperlink clickable, dan Daftar Isi menampilkan hierarki
gambar acuan **persis** (bab tanpa nomor; sub-bab 1-4 di bawah Flow Proses Bisnis).
Screenshot bukti ada di scratchpad.

Pengguna melihatnya kosong karena membuka docx **tanpa meng-update field** (klik
"No" pada prompt Word, atau viewer non-Word). **Nomor halaman MUSTAHIL di-bake
Pandoc** — cuma mesin layout (Word/LibreOffice) yang menghitungnya; complex field
`dirty=true` pun tak terisi pada plain-open (diuji). Yang dikerjakan: placeholder
dibuat actionable ("tekan Ctrl+A lalu F9…").

**KEPUTUSAN PEMILIK yang tersisa**: agar ketiga daftar auto-terisi di viewer APA
PUN tanpa aksi pengguna, perlu **bake server-side pakai LibreOffice headless** —
dependency baru (belum terpasang di mesin ini, jadi belum bisa diverifikasi &
sengaja belum di-ship; prinsip #4). Kalau pemilik OK dengan dependency itu, ini
follow-up jelas berikutnya: pasang LibreOffice → tambah langkah bake di pipeline →
verifikasi end-to-end.

## Verifikasi

- `pytest` → **319 hijau** (+7 test premco baru: cover boxed, entity merge,
  signature bar 2×2, sub-bab bernomor, cover rata-kanan, default TIDAK ikut,
  infra merge sel kosong). File: `tests/test_compiler_service.py`.
- `cd frontend && npm run build` → hijau (field `entitas` ditambah ke form).
- Visual: `premco_verify.pdf` (baked via Word) — cover, tanda tangan, ketiga
  daftar dilihat langsung, benar semua.

## Kalau mau lanjut

- **Keputusan LibreOffice baking** (di atas) — satu-satunya bagian request 4-6
  yang belum tuntas; butuh restu pemilik atas dependency.
- Warna header cover masih hitam (000000) vs PREMCO 3b3838/252525 — praktis sama;
  kalau pemilik mau PERSIS, tinggal post-process fill per tabel cover.
- Perbandingan berdampingan 16 bab `premco`×PREMCO masih belum tuntas (yang sudah:
  cover, tanda tangan, tiga daftar).
