# Catatan Sesi — 2026-07-20 (3 template vendor + peta LLM prototipe→produksi + redesign layer diagram)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Demo batal → kembali ke Trek A ("jalankan template vendor yang belum diuji").
Tiga template isian yang menganggur di root dijalankan lewat mesin V2 (`04` UAT,
`moe` UAT [ex-`.doc`], dan `Template SDD` — template **Microsoft Dynamics CRM**
yang pemilik tambahkan hari itu). **Ketiganya kompilasi+render tanpa crash** —
fix subtree-drop/dedup sesi lalu tahan pada outline bersarang asing. Temuan
crux: `Template SDD` menghasilkan **0 binding isi dari 29 bab** → dokumen 100%
placeholder. Bukan bug — **plafon heuristik** (nama bab spesifik-domain tak cocok
kata kunci). Lalu **peta bab LLM di-prototipe-kan ($0,034)** dan membuktikan
plafon itu teratasi: 4 binding isi + 3 perbaikan struktural, dokumen kosong jadi
berisi (deskripsi + tabel requirement + diagram arsitektur + tabel fitur). CLAUDE.md
+ roadmap diperbarui: "LLM auto-usul peta" kini **DE-RISKED**. Belum ada commit
(kerja eksplorasi + update dok). Biaya sesi: **$0,034**.

## Yang dikerjakan

1. **Orientasi status** (jawab pertanyaan pemilik): frontend ketinggalan backend —
   `TEMPLATE_OPTIONS` frontend hardcode `premco: SDD-saja` padahal backend sudah
   premco UAT; dan **seluruh V2 (upload template) tak diekspos di frontend sama sekali**.
2. **3 template vendor diuji lewat mesin** (`compile_template_from_docx` →
   `propose_mapping` → `generate_docx` dgn Contract B dummy → docx → PDF → PNG →
   DILIHAT). Semua lolos rantai penuh. `04`/`moe` UAT: `test_groups` benar
   (tabel test per-layar terisi). `Template SDD`: **semua placeholder**.
3. **Prototipe peta bab LLM** (`scratchpad/llm_mapping_proto.py`, BERBAYAR
   $0,034, Sonnet 5, structured output, kontrak keluaran SAMA dgn `propose_mapping`)
   pada `Template SDD`: 0→4 binding isi, before/after dilihat visual.
4. **Dok diperbarui**: entri Riwayat CLAUDE.md 2026-07-20 + roadmap "LLM auto-usul
   peta" ditandai DE-RISKED. SESSION.md ini.

## Kejadian yang layak diingat (jebakan)

- **`Template SDD` = plafon heuristik, bukan bug.** Degradasi anggun konservatif
  menelan SEMUA bab kalau nama-namanya asing (Dynamics/BRD). Ini justru kasus yang
  membenarkan peta LLM — dan prototipe membuktikannya, murah.
- **Peta LLM juga memperbaiki kesalahan STRUKTURAL heuristik**, bukan cuma isi:
  "1 Contents"→skip (TOC yang `_SKIP_KEYWORDS` lewatkan), judul→skip. Nilai tambah
  LLM lebih luas dari sekadar mengenali bab konten.
- **LLM patuh dedup "sekali per binding"** — jaring pengaman first-wins tak terpicu.
  Kontrak keluaran + enum + aturan di system prompt sudah cukup mengarahkan.
- **`.doc` → Word COM `SaveAs2(...,16)`**; docx hasil render V2 punya `updateFields`
  (dari reference tersintesis) → **buang dulu** sebelum Word COM buka (kalau tidak
  menggantung). Word COM PDF `SaveAs2(...,17)`; PDF→PNG via PyMuPDF (`fitz`, ada di venv).
- **Template scratch (`tpl-*`) SUDAH dibersihkan** dari `data/templates/` (turunan
  docx internal, mengotori registry). Store kembali kosong.

## Redesign layer diagram (Option C, sesi ini juga)

Modul BARU `app/diagram/` — Diagram IR (semantik, ala AST) + PlantUML Renderer
(salah satu backend). **Live pipeline TAK disentuh** (DOCX identik; renderer baru
belum dipanggil jalur live). Dibedah dulu kontradiksinya: "IR jadi source of truth"
mustahil bersamaan dgn "DOCX identik" + "jangan ubah LLM/DocumentContent", sebab
LLM menulis PlantUML LANGSUNG ke DocumentContent. Pemilik pilih Option C (fondasi
sekarang, switch nanti).

- `ir/` = graf (node/edge/lane), Pydantic per-tipe (activity/usecase/architecture/
  component) + `base.py`. Graf sengaja (peta langsung ke Mermaid/ReactFlow/drawio).
- `renderer/base.py` `DiagramRenderer` (ABC) + `renderer/plantuml/` `PlantUMLRenderer`.
- Renderer emit PlantUML **struktur-saja tanpa theme** → masuk `_normalize_plantuml`
  →`_run_plantuml` yang SAMA (theme disuntik di sana) = **switch-ready**.
- Verifikasi: **277 test hijau** (263+14, nol regresi); VISUAL — IR arch & usecase
  dirender via jar ASLI = UML identik gaya jalur LLM (`IR_arch.png`, `IR_usecase.png`).
- Menambah SVG kelak = `renderer/svg/` + `SVGRenderer(DiagramRenderer)`, nol ubah IR/pipeline.

## Kalau melanjutkan, mulai dari sini

**#1 (Trek A — tetap PALING BERNILAI selagi magang):** kumpulkan/bawa template
SDD/UAT sumber lain, jalankan lewat mesin (`compile_template_from_docx` + lihat).
Sudah 4 kelas struktur tertutup (PREMCO-family/asing × SDD/UAT × datar/bersarang);
tiap template yang BEDA struktur masih mungkin memancing bug. Satu-satunya kerja
yang tak bisa diambil setelah keluar magang.

**#2 (produksionisasi peta LLM) — ✅ SELESAI (sesi ini).** `app/services/
llm_mapping_service.py` `llm_propose_mapping` (kontrak keluaran SAMA dgn heuristik),
gate opt-in `use_llm_mapping` di `compile_template`/`compile_template_from_docx`/
`POST /templates` (default heuristik $0). Refactor `assemble_plan` (dedup+degradasi)
dipakai bersama. +11 tes (LLM mock), **288 hijau**, nol regresi. Jalur berbayar
diverifikasi ke API nyata (Dynamics 0→**6** binding isi, ~$0,03). Lihat Riwayat CLAUDE.md.

**#3 (frontend, $0 — kandidat berikutnya, TAPI pemilik bilang "frontend cukup" →
KONFIRMASI dulu):** ekspos V2 (widget upload → `POST /templates` [kini terima
`use_llm_mapping`], dropdown dari `GET /templates`) + UI tinjauan/edit peta bab
(`mappings` dari `GET /templates/{id}`) + perbaiki `premco` UAT stale di `TEMPLATE_OPTIONS`.
Sekarang bernilai penuh karena #2 bikin fiturnya berisi, bukan kosong.

**#4 ($0):** orientasi landscape per-section (spec `orientations[]` belum diukur
BENAR — terukur `None` di 3 template; ukur + terapkan untuk tabel test lebar).

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Lihat before/after `Template SDD`** (scratchpad, bukan repo):
  `RENDER_tpl-baru-sdd_p1..2.png` (heuristik = semua placeholder) vs
  `LLM_p1..2.png` (peta LLM = deskripsi + tabel requirement + diagram arsitektur +
  tabel fitur, bab manual tetap jujur). Ini bukti konkret peta LLM layak dikerjakan.
- **Keputusan**: apakah #2 (produksionisasi peta LLM) atau #3 (frontend) duluan?
  Keduanya sudah de-risked; #2 berbayar tiap generate, #3 gratis tapi butuh restu
  "sentuh frontend lagi".
- Dua tugas lama: revoke API key lama, isi `GITHUB_TOKEN`.
