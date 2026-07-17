# Catatan Sesi — 2026-07-17

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi satu tema: **redesign visual dokumen SDD** atas permintaan pemilik
("dibandingkan berdampingan dengan PREMCO harus setara; JANGAN sentuh
pipeline/Contract A/Contract B") — dan janji itu ditepati: nol perubahan pada
kontrak, prompt, maupun LLM. Kuncinya: halaman PDF acuan untuk pertama kalinya
**dilihat sebagai gambar** (sesi-sesi lalu cuma membaca teksnya), dan grammar
visualnya langsung kelihatan: heading bab di tengah + caps, body justified,
header tabel hitam dengan teks putih **di tengah**, footer judul-miring +
nomor-kanan, Daftar Isi ber-dot-leader, dan urutan halaman
cover→identitas→revisi→persetujuan→daftar-daftar→isi. Semua itu sekarang ada di
dokumen kita. Diverifikasi 4 putaran dengan **melihat halamannya** (render ulang
esteler dari Contract B tersimpan → docx → PDF via Word COM → PNG per halaman),
bukan membaca XML. 196 test hijau (191+5). Biaya sesi: **$0**.

## Yang diselesaikan (semuanya presentasi, nol pipeline)

| # | Apa | Inti |
|---|---|---|
| 1 | **Urutan halaman ala acuan** | `--toc/--lof/--lot` DILEPAS untuk SDD (Pandoc memakunya tepat sesudah judul — itu sebabnya Daftar Isi selama ini nongkrong di halaman cover). Field code yang sama persis ditanam `sdd_template.md` sesudah Persetujuan; hidup karena `updateFields` ikut dari settings.xml reference.docx (diprobe dulu). UAT tetap `--toc`, belum disentuh (tahap b roadmap). |
| 2 | **Tipografi reference.docx** | Title 22pt (cover bernapas), H2 14pt centered caps + letterspacing, H3 12pt kiri, body 11pt justified line 16, caption 9pt italic biru-kelabu di tengah, style `toc 1..3` + `table of figures` ber-dot-leader (kerangka Pandoc TIDAK punya), TOC Heading pageBreakBefore. |
| 3 | **Tabel** | Padding sel naik (80/115 twip), tinggi baris minimum, vAlign center, `cantSplit` (baris tak lagi terbelah antar halaman), header hitam dengan teks putih **di tengah**, lebar kolom proporsional dari rasio dash separator (`--columns=20`). |
| 4 | **Diagram** | dpi 200→300, `-DPLANTUML_LIMIT_SIZE=16384` (PlantUML memotong diam-diam >4096px), `_image_attr` berhenti meng-upscale (ukuran tampil = piksel/360 → teks diagram konsisten ~9pt antar diagram, tajam). |
| 5 | **Footer & cover** | Footer = judul dokumen miring 9pt kiri + nomor halaman kanan (field kompleks, format selamat dari update Word). Cover = judul + 3 tabel identitas, lega; Tim & Peran pindah ke hal. 2 (di cover dia terbelah jelek — diukur dari probe visual). |
| 6 | **Post-process python-docx** (`_postprocess_docx`) | Header tabel dirata-tengah (satu-satunya jalan; lihat "Kejadian") + **caption tabel dipindah ke BAWAH tabelnya** seperti acuan (permintaan lanjutan pemilik; Pandoc memakunya di atas) + **baris tanda tangan ≥1 inci** dan bloknya diikat utuh se-halaman. Probe terakhir: `out/PROBE11_ttd_tinggi_esteler.docx`. |
| 7 | **Perbandingan berdampingan PREMCO×esteler, 12 pasang halaman** | Dikerjakan sendiri (komposit kiri-kanan per bagian, `pair_*.png` di scratchpad). Verdict: grammar visual setara; gap fungsional tersisa cuma tinggi TTD (→ baris #6) dan logo (→ baris #8). Bonus: Daftar Gambar PREMCO terlihat rusak (semua entri menyebut CORETAD) bersanding dengan punya kita yang benar — bukti visual klaim jualan. |
| 8 | **Slot upload logo di form** | `logo_base64` di `GenerateDocumentRequest` (BUKAN DocumentMetadata — kontrak kosongnya beda) → `decode_logo` validasi SINKRON di POST (422 sebelum job/LLM) → `_add_header_logo` di post-process: kanan-atas header tiap halaman, tinggi 0,45"/lebar maks 2,4", **tepi transparan dipangkas dulu** (logo Pertamina uji dari pemilik ber-padding 50% — tanpa pemangkasan tampil kerdil 0,22"). Frontend: input file di panel Dokumen. Probe FINAL: `out/PROBE13_logo_pertamina_esteler.docx` — disandingkan PREMCO, ukuran/posisi logo praktis identik. |

## Kejadian yang layak diingat (jebakan Word/Pandoc, semua DIPROBE)

- **Word MENGABAIKAN `w:pPr` dari `tblStylePr firstRow`** — jc=center di table
  style tidak pernah jalan; compat flag `overrideTableStyleFontSizeAndJustification`
  true/false/absen ketiganya identik. `rPr`/`tcPr` dihormati, `pPr` tidak.
  Makanya post-process.
- **fldSimple membuang format run saat Word meng-update field** — footer yang
  di-set italic 9pt balik jadi 12pt tegak begitu dibuka. Field kompleks
  (fldChar begin/instrText/separate/end) dengan rPr di run kode = cara Word
  sendiri, formatnya selamat.
- **Titik dua kiri separator pipe table (`|:---|`) menyuntik `w:jc="left"`
  LANGSUNG ke tiap sel** — mengalahkan semua style. Ketahuan dari XML sel, bukan
  dari mata.
- **Autofit Word mengempiskan kolom yang selnya kosong** (Nama di Tim & Peran
  jadi sepersekian cm) — rasio dash hanya dibaca Pandoc kalau ada baris >
  `--columns`; ambang diturunkan ke 20.
- **Rasio dash → lebar kolom** itu fitur Pandoc yang nyata dan terukur
  (5:8:32 dash → 880:1408:5632 twip) — sekarang jadi mekanisme resmi lebar kolom.
- Verifikasi visual = **docx → PDF lewat Word COM → PNG per halaman → dilihat**.
  Membaca XML tidak akan pernah menangkap lima hal di atas; empat di antaranya
  hanya kelihatan di rendering.

## Kalau melanjutkan besok, mulai dari sini

1. **Minta pemilik buka `scripts/validation/out/PROBE13_logo_pertamina_esteler.docx`**
   (706 KB, TERBARU: + logo Pertamina sungguhan di header; PROBE9-12 versi
   bertahap sebelumnya) di Word. Perbandingan berdampingan dengan PREMCO sudah
   dikerjakan (baris #7); yang tersisa untuk mata pemilik: setuju/tidak dengan
   verdict-nya. Catatan: logo uji ada di `frontend/dist/assets/` — folder itu
   DITIMPA tiap `npm run build`, pindahkan kalau mau disimpan. Kalau
   masih ada gap visual, itu daftar kerja berikutnya. (Logo perusahaan di header
   tiap halaman = satu-satunya elemen acuan yang sengaja tidak ditiru — kita
   tidak punya logo; kandidat: slot upload logo di form.)
2. **UAT belum disentuh secara visual** (tahap b roadmap): urutan halamannya
   masih gaya lama (--toc di depan). Perlakukan seperti SDD sesi ini — tapi
   idealnya setelah pemilik menyediakan PDF acuan UAT.
3. Regen petclinic (~$0,25) opsional — cross-check tampilan baru di dokumen Java.
4. Kasus fastapi (ATURAN BUKTI diagram) masih terbuka — butuh regen fastapi murah.

**Menggantung dari sesi-sesi lalu (masih berlaku):**
- Revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY` (5 sesi menggantung).
- Isi `GITHUB_TOKEN` di .env.
- Ablasi endpoint esteler (~$0,15).
- ZIP → dokumen belum tersambung.
- Uji kualitas Sonnet 5 vs Opus 4.8 (~$1, sekali bayar).

## Yang perlu dilakukan manusia

- **Buka PROBE9 di Word + sandingkan dengan PDF acuan** — nilai sendiri:
  9.8/10 tercapai atau belum, dan apa yang kurang.
- Dua tugas lama: revoke API key lama, isi GITHUB_TOKEN.
