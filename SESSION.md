# Catatan Sesi — 2026-07-19 (V2: increment 2+3, endpoint upload, validasi vendor asli)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Fitur V2 (upload template → generate dokumen mengikuti template itu) disambung
dari kelayakan sampai **jadi & TERUJI pada template vendor asli**, semua $0. Sesi
ini: increment 2 (sintesis reference.docx), increment 3 inti (generator + peta
heuristik), pendaftaran+storage (registry dinamis), endpoint upload (`POST
/templates`), lalu **validasi END-TO-END pada 3 template vendor asli** (IEEE SDD,
UAT ID `04`, UAT EN generik). Validasi itu membuktikan mesin ukur+peta+sintesis
**jalan pada template asing** (bukan cuma sintetis) DAN memancing **2 cacat
heuristik** (duplikasi isi + subtree-drop rakus) yang cuma muncul pada outline
BERSARANG — keduanya diperbaiki, terbukti before/after visual (PROBE31). **263
test hijau**, biaya sesi **$0**.

## Yang diselesaikan (6 commit)

| Commit | Apa |
|---|---|
| `e4680ae` | Increment 2 — sintesis reference.docx dari spec (`build_reference_docx.py` param `spec`) |
| `3b6f4a4` | Increment 3 inti — generator (`template_generator_service.py`) |
| `9932d2a` | Pendaftaran+storage — pindah sintesis ke `reference_synthesis_service.py`; `data/templates/<id>/`; registry dinamis `_resolve_template`; orkestrator `template_compiler_service` |
| `f073d46` | Endpoint upload — `routes_template.py` (`POST /templates`, `GET /templates[/{id}]`) |
| (ini) | **Validasi vendor asli + 2 fix heuristik** — dedup isi (first-wins) + `_OWNS_SUBTREE` dipersempit ke binding sub-heading saja |

## Kejadian yang layak diingat (jebakan)

- **Uji sintetis (outline DATAR) buta terhadap bug BERSARANG.** Cacat A/B cuma
  muncul saat template nyata (IEEE, bersarang L1-L3) dijalankan. Kembaran
  "fixture N=1 buta ke bug antar-item". **Template vendor nyata = validasi tak
  tergantikan** (bukan data latih — mesin deterministik; satu contoh cukup).
- **`_OWNS_SUBTREE` HANYA untuk binding yang meng-emit sub-heading sendiri**
  (use_cases/activity/test_groups). Isi skalar (app_description/architecture) TAK
  boleh menelan sub-pohon — kalau tidak, bab anak ber-pemetaan-sendiri hilang.
- **Dedup isi di `propose_mapping`** (bukan di generator) supaya rencana peta yang
  ditinjau user = yang dihasilkan. Binding isi dipakai sekali, yang pertama menang.
- **`.doc` (Word lama) tak terbaca python-docx** → konversi Word COM dulu.
  Endpoint menolak `.doc` (konversi butuh Word, tak ada di deployment).
- **Pisahkan 422 (input user) dari 500 (server)** di endpoint upload.

## Kalau melanjutkan, mulai dari sini

**#1 (prioritas SELAGI MAGANG — Trek A, PALING BERNILAI SEKARANG):** bawa **lebih
banyak template SDD/UAT sumber lain**. Mesin V2 sudah jadi & terbukti bisa
menemukan cacatnya sendiri saat diberi template nyata — jadi tiap template baru =
langsung uji + kemungkinan besar temuan/fix bernilai. Template di root masih ada
(gitignore); yang belum dijalankan lewat mesin: UAT `04` & moe UAT (baru diukur,
belum di-render penuh). **Cara**: `compile_template_from_docx(path)` atau `POST
/templates`, lalu LIHAT dokumen + rencana peta. Satu-satunya kerja yang tak bisa
diambil setelah keluar magang.

**#2 (V2 Trek B — sisa, semua PILIHAN):**
- ✅ increment 1-3 + pendaftaran/storage + endpoint upload + validasi vendor —
  KODE+tes. **Mesin V2 lengkap, bisa dipakai via API, terbukti pada vendor asli.**
- ⏭ **LLM auto-usul peta bab** (BERBAYAR — gate biaya): ganti heuristik "yang
  pertama menang" dgn judgment (bab MANA paling pas untuk tiap isi — mis. "Overview
  of the System" mungkin lebih pas app_description dari "Introduction"). Kontrak
  keluaran sama (`[{level,text,binding}]`).
- ⏭ **Frontend: widget upload + dropdown dari `GET /templates`** ($0). Pemilik
  bilang "frontend cukup" — konfirmasi dulu.
- ⏭ **UI tinjauan pemetaan** ($0): tampilkan `mappings` dari `GET /templates/{id}`,
  user edit binding sebelum generate.
- ⏭ **Orientasi landscape per-section** ($0): spec `orientations[]` diukur, belum
  dipakai sintesis. Untuk tabel test lebar.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Lihat `scripts/validation/out/PROBE31_ieee_vendor_sdd_p1_fixed.png`** — dokumen
  digenerate mengikuti struktur template SDD **IEEE asli** (bukan PREMCO): bab
  Introduction terisi + sub-babnya jadi placeholder jujur. Bukti mesin V2 jalan
  pada template asing. (PROBE30 = jalur produksi; PROBE29 = generator; PROBE28 = A/B.)
- **PALING PENTING selagi magang:** bawa **lebih banyak template SDD/UAT dari
  vendor/sumber lain** (Trek A). Tiap template baru langsung menguji + menemukan
  lubang. Satu-satunya yang tak bisa diambil setelah keluar.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
