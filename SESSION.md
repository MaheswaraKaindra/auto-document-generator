# Catatan Sesi — 2026-07-19 (V2: increment 2+3, pendaftaran/storage, endpoint upload)

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
dari kelayakan sampai **BISA DIPAKAI USER**, semuanya $0. Sesi ini: **increment 2**
(sintesis reference.docx dari spec), **increment 3 inti** (generator template
Jinja + peta bab heuristik), **pendaftaran+storage** (template upload jadi
`template_id` yang `generate_docx` render lewat reference tersintesisnya sendiri),
dan **endpoint upload** (`POST /templates` — upload `.docx` → `template_id` siap
pakai di `/documents/generate`). Terbukti VISUAL jalur produksi penuh (PROBE30)
dan lewat aplikasi ASGI nyata (TestClient). **261 test hijau**, biaya sesi **$0**.
Sisa V2: LLM auto-usul peta (berbayar), UI+widget upload frontend, landscape.

## Yang diselesaikan (berurut, 4 commit)

| Commit | Apa | Inti |
|---|---|---|
| `e4680ae` | **Increment 2 — sintesis reference.docx** | `build_reference_docx.py` param `spec`; `spec=None` content-identik. |
| `3b6f4a4` | **Increment 3 inti — generator** | `template_generator_service.py`: `propose_mapping` + `generate_jinja_template`. |
| `9932d2a` | **Pendaftaran + storage** | pindah sintesis ke `reference_synthesis_service.py`; `data/templates/<id>/`; `_resolve_template`/`_ResolvedTemplate` (flag) di compiler; orkestrator `template_compiler_service.compile_template`. |
| (ini) | **Endpoint upload** | `routes_template.py`: `POST /templates` (sinkron, 201 + mappings), `GET /templates[/{id}]`; didaftar di `main.py`. |

## Kejadian yang layak diingat (jebakan)

- **Kompilasi template SINKRON, bukan async.** Beda dari `/documents/generate`:
  deterministik & $0 (tanpa LLM), jadi tak perlu job/polling — balik 201 langsung.
- **Pisahkan 422 (input user) dari 500 (server).** `.doc`/rusak/kosong = 422;
  pandoc mati saat sintesis = 500. Jangan salahkan file user untuk bug server
  (pelajaran berulang: sebab tertelan gejala).
- **Payoff tersambung gratis**: `/documents/generate` sudah `validate_template`
  sinkron, dan itu sejak pendaftaran+storage menerima id terkompilasi → id
  hasil-upload otomatis sah di generate, tanpa sentuh routes_document.
- **`from X import KONST` mengikat by-value** → orkestrator mereferensi
  `compiler_service.TEMPLATES_STORE` lewat MODUL (satu sumber, bisa di-redirect).
- **Built-in tetap `get_template`** (output byte-identik, nol regresi 200+ test);
  cuma template terkompilasi pakai `from_string`.
- **`*(diisi manual)*` di-render jadi teks MIRING `(diisi manual)`** (asterisk
  penanda italic dibuang) — assertion cari tanpa asterisk.

## Kalau melanjutkan, mulai dari sini

**#1 (prioritas SELAGI MAGANG — Trek A):** kumpulkan **lebih banyak template
SDD/UAT dari vendor/sumber lain**. Mesin V2 sudah jadi & bisa dipakai; yang
menaikkan keyakinan generalisasi = **keragaman input**, bukan kode. **Tanya
pemilik: sudah bawa template baru?** Ada → `POST /templates` (atau
`compile_template_from_docx`, gratis) → lihat dokumen + rencana peta-nya.

**#2 (V2 Trek B — sisa, semua PILIHAN, urutan bebas):**
- ✅ increment 1-3 + pendaftaran/storage + **endpoint upload** — KODE+tes. **Fitur
  V2 bisa dipakai via API sekarang.**
- ⏭ **Frontend: widget upload + dropdown gaya dokumen dari `GET /templates`**
  ($0). Ini last-mile untuk user non-teknis. Catatan: pemilik pernah bilang
  "frontend cukup, jangan investasi desain" — ini WIRING fungsional (bukan
  redesign), tapi konfirmasi dulu apakah mau sekarang.
- ⏭ **UI tinjauan pemetaan** ($0): tampilkan `mappings` dari `GET /templates/{id}`,
  biar user edit binding sebelum generate. Perlu endpoint update-mapping +
  re-generate template dari mapping yang disunting.
- ⏭ **LLM auto-usul peta bab** (BERBAYAR — gate biaya): ganti `propose_mapping`
  heuristik untuk template asing (IEEE "Data Design"). Kontrak keluaran sama.
- ⏭ **Orientasi landscape per-section**: spec `orientations[]` sudah diukur,
  belum dipakai sintesis. Reuse `_landscape_after_marker`. Untuk tabel test lebar.

**Utang lama (cepat):** revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY`; isi `GITHUB_TOKEN`.

## Yang perlu dilakukan manusia

- **Coba `POST /templates`** (Swagger `http://127.0.0.1:8000/docs`): upload satu
  `.docx` template → dapat `template_id` + rencana peta → pakai id itu di
  `POST /documents/generate`. (Bukti visual mesinnya: PROBE30.)
- **PALING PENTING selagi magang:** bawa **lebih banyak template SDD/UAT dari
  vendor/sumber lain** (Trek A). Satu-satunya yang tak bisa diambil setelah keluar.
- Dua tugas lama: revoke API key lama (`GOOGLE_API_KEY`/`LLAMA_API_KEY`), isi `GITHUB_TOKEN`.
