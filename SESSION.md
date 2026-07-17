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

Sesi maraton tiga babak, seluruhnya lapisan presentasi — **nol sentuhan
Contract A/B/prompt/LLM**, biaya total **$0** (semua verifikasi render ulang
dari Contract B esteler tersimpan). **Babak 1 — redesign visual SDD ke bahasa
visual PDF acuan**: halaman acuan untuk pertama kalinya dilihat SEBAGAI GAMBAR,
lalu semuanya ditiru (heading tengah+caps, body justified, dot leader, urutan
halaman cover→revisi→persetujuan→daftar-daftar→isi, caption di bawah tabel,
kotak TTD 1 inci) dan dibuktikan lewat perbandingan berdampingan 12 pasang
halaman. **Babak 2 — slot upload logo** (validasi sinkron 422 sebelum bayar,
pangkas tepi transparan, diuji dengan logo Pertamina sungguhan). **Babak 3 —
ide pemilik "user upload template sendiri" dieksekusi sampai V1**: V0 mengukur
docx PREMCO asli (pemetaan bab 16/16 jelas; swap reference-doc = paket CORRUPT
→ jalur benar SINTESIS; template nyata membawa pembusukan CORETAD), lalu V1
multi-template: registry `default`/`premco` + `template_id` di form, template
premco ber-bar-judul-biru dengan kriteria/langkah di dalam sel. Verifikasi
selalu sama: docx → PDF via Word COM → PNG per halaman → DILIHAT. **212 test
hijau** (dari 191). 7 commit.

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
| 9 | **V0 "upload template perusahaan"** (ide pemilik = roadmap tahap c) | Diukur pada docx PREMCO ASLI (40,7 MB di root, gitignored). Hasil: pemetaan bab 16/16 tanpa ambigu isi (4 ambiguitas format); swap `--reference-doc` mentah = RUSAK total (40 MB, Word bilang corrupt — font/media embed ikut kontainer) → jalur benar SINTESIS reference.docx dari properti terukur (dan angka terukurnya PERSIS yang kita hardcode manual minggu ini); template nyata bawa pembusukan sendiri (6 heading kosong, nomor gambar kacau). Laporan: `scripts/validation/V0_TEMPLATE_PREMCO.md`. Verdict: **layak lanjut V1**. |
| 10 | **V1 MULTI-TEMPLATE selesai** | `_TEMPLATE_REGISTRY` (default/premco) + `template_id` di API & dropdown frontend, 422 sinkron via `validate_template`. Template `sdd_premco_template.md` = kompilasi manual konvensi terukur: bab tanpa nomor, bar judul biru 9CC3E5 (marker `((BAR))` → merge+warna+keepNext), kriteria & langkah DI DALAM sel (marker `((BR))` → line break sungguhan — `<br/>` DIBUANG diam-diam writer docx Pandoc; sel ber-break dipaksa rata kiri), kolom Remark, 2 bab mockup, tanpa Component Integration. Diverifikasi berdampingan dengan dokumen asli. Probe: `out/PROBE15_template_premco_esteler.docx`. 212 test. |

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
- **Writer docx Pandoc MEMBUANG raw HTML tanpa suara** — `<br/>` di sel pipe
  table lenyap, item menyambung jadi satu kalimat. Solusi: marker `((BR))` +
  post-process jadi `<w:br/>` sungguhan.
- **Pandoc memakai reference-doc sebagai KONTAINER paket** — docx user (40 MB,
  font ter-embed) sebagai reference menghasilkan output 40 MB yang Word sebut
  corrupt. Reference harus SELALU disintesis dari kerangka Pandoc yang bersih.
- Verifikasi visual = **docx → PDF lewat Word COM → PNG per halaman → dilihat**.
  Membaca XML tidak akan pernah menangkap hal-hal di atas; sebagian besar
  hanya kelihatan di rendering.

## Kalau melanjutkan besok, mulai dari sini

**V1 SELESAI. Kandidat berikutnya (urutannya keputusan pemilik):**

1. **UAT** (roadmap tahap b) — belum disentuh secara visual maupun bentuk;
   urutan halamannya masih gaya lama (`--toc` di depan). Perlakukan seperti SDD
   minggu ini; idealnya setelah pemilik menyediakan acuan UAT.
2. **V2 template upload** — analisis template dibantu LLM + UI tinjauan
   pemetaan + form dinamis dari slot manual. **Prasyarat: kumpulkan 1-2
   template docx dari sumber LAIN** supaya tidak overfit ke PREMCO (V0/V1 baru
   membuktikan satu sumber). Jalur teknis sudah terbukti: sintesis
   reference.docx (bukan swap — swap menghasilkan paket corrupt), marker
   post-process untuk struktur yang markdown tidak bisa.
3. Murah & menggantung lama: regen petclinic (~$0,25, cross-check tampilan di
   Java), kasus fastapi ATURAN BUKTI (regen murah), ablasi endpoint esteler
   (~$0,15), uji Sonnet 5 vs Opus 4.8 (~$1).

**Menggantung dari sesi-sesi lalu (masih berlaku):**
- Revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY` (5 sesi menggantung).
- Isi `GITHUB_TOKEN` di .env.
- ZIP → dokumen belum tersambung.

## Yang perlu dilakukan manusia

- **Buka `scripts/validation/out/PROBE15_template_premco_esteler.docx`** —
  esteler bergaya PREMCO (bar biru, kriteria di dalam tabel) + logo; sandingkan
  sendiri dengan dokumen aslinya. PROBE13 = pembanding gaya default. Coba juga
  dropdown "Gaya Dokumen" di frontend.
- **Logo uji Anda di `frontend/dist/assets` TERHAPUS** oleh `npm run build`
  (dist = output build, selalu ditimpa; salinan trimmed selamat di media
  PROBE13). Simpan aset uji di luar `dist/`.
- Dua tugas lama: revoke API key lama, isi GITHUB_TOKEN.
