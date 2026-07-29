# auto-document-generator

> **Baru bergabung / melanjutkan kerja orang lain?** Baca `SESSION.md` dulu — isinya
> apa yang dikerjakan sesi terakhir dan dari mana sebaiknya melanjutkan. Tiga file,
> tiga peran: **CLAUDE.md** = pengetahuan permanen tentang produk (di-load tiap
> sesi, jaga tetap ramping); **SESSION.md** = foto sesaat, **ditimpa habis tiap
> sesi baru**; **CHANGELOG.md** = riwayat perubahan detail, **dibaca on-demand**
> (jangan ditaruh di CLAUDE.md — itu bikin boros token tiap sesi). Kalau ada yang
> bertentangan, **CLAUDE.md yang benar**.

## Ringkasan

**auto-document-generator** adalah produk **SaaS generik** yang membaca source code dari repo mana pun (GitHub OAuth/PAT, atau ZIP upload — bukan tool internal satu perusahaan) dan otomatis membuat draf dua dokumen yang biasanya ditulis manual oleh developer/QA: **Solution Design Document (SDD)** dan **User Acceptance Test (UAT) Document**, keduanya dalam format `.docx` siap pakai.

## Latar Belakang & Tujuan

Tim development yang bekerja dengan ritme agile/Scrum sering menunda pembuatan dokumen SDD/UAT (atau menulisnya asal-asalan setelah development selesai) karena menulis dokumen ini manual itu lambat dan membosankan — padahal formatnya selalu sama di setiap project, cuma isinya yang beda. Ide awalnya muncul dari pengalaman magang salah satu anggota tim di sebuah perusahaan (melihat bottleneck ini secara langsung), tapi produk ini sengaja dibangun **generik** supaya siapa pun dengan masalah yang sama bisa pakai — bukan cuma perusahaan tempat asal ide tersebut, dan bukan cuma untuk developer (product owner, QA manual, dan user bisnis juga harus bisa memahami hasilnya).

**Target kualitas output**: setara dokumen SDD/UAT enterprise yang biasa dipakai di industri (approval workflow, tabel requirement, use case per aktor, activity diagram per fitur) — bagian yang memang bisa diturunkan dari kode (fitur, use case, diagram arsitektur, activity diagram, test case) diisi otomatis; bagian administratif yang tidak mungkin diketahui dari kode (nomor RFC, cost estimation, tanda tangan approval, mockup UI) sengaja dibiarkan sebagai placeholder manual di template.

**Acuan konkretnya ada**: satu dokumen Solution Design enterprise sungguhan (87 halaman, PDF di `ref/benchmark/` — **di-gitignore karena dokumen internal klien**, jadi tidak ikut ke repo). `app/templates/sdd_template.md` jelas dimodelkan dari dokumen itu. Dibandingkan bab per bab (2026-07-15), strukturnya **sudah cocok hampir seluruhnya** — Revision History, Persetujuan, Deskripsi Aplikasi, Dev System Type, Demografi, System Requirement, How to Access, Infrastructure & Capacity, Application Architecture, Security, Features Requirement, Flow Proses Bisnis, Use Case, Activity Diagram semuanya ada. **Daftar Gambar** dan **Daftar Tabel** kini **SUDAH ada** (2026-07-16 — lihat Riwayat). Yang tersisa cuma **Mockup Website** dan **Mockup Aplikasi** (mustahil dari kode — kandidat slot upload), jadi **jarak struktur ke dokumen acuan praktis tertutup**. Soal Daftar Gambar/Tabel, dua hal yang layak diingat: (1) dulu dicatat remeh — *"mekanis, tinggal dibangkitkan"* — padahal **di dokumen acuan justru dua bagian itulah yang RUSAK**: seluruh entri Daftar Gambar-nya menyebut aplikasi yang sama sekali lain (sisa copy-paste dari dokumen sebelumnya; nama aplikasi asing itu muncul 5× di seluruh 87 halaman dan kelimanya cuma di Daftar Gambar/Tabel), sementara Daftar Tabel-nya kehilangan nomor 6 & 9 dan menduplikasi 5, 13/14, 15/16. **Dua bagian yang kita belum punya ternyata persis dua bagian yang manusia gagal** — justru *karena* mekanis: membosankan, tidak ada yang memeriksa, lalu membusuk. Di sinilah produk ini **lebih baik daripada acuannya**, bukan sekadar setara — dan itu argumen jualan terkuat yang kita punya (sudah dipakai di `README.md`, dianonimkan karena acuan itu dokumen internal klien). (2) Sengaja **SDD saja**: UAT punya nol gambar dan cuma satu tabel isi, jadi memasangnya di sana menghasilkan dua halaman indeks kosong. **Jadi jarak ke dokumen acuan bukan soal struktur**, melainkan kedalaman (87 halaman vs ~25). Soal placeholder kosong sudah selesai sejak 2026-07-15 — 25 dari 28 penanda `(diisi manual)` kini ditanyakan lewat form (lihat `DocumentMetadata`), sisanya 3 blok tanda tangan/sertifikasi yang memang tidak seharusnya diisi sistem. Catatan penting: panjang bukan ukuran profesional — dokumen acuan panjang sebagian besar karena mockup, timeline proyek, dan tanda tangan. Dokumen 30 halaman yang setiap kalimatnya benar lebih berharga daripada 87 halaman yang separuhnya karangan; justru itu nilai jual produk ini.

## Arah Produk (keputusan pemilik project 2026-07-16, dari masukan penguji)

Tiga keputusan yang mengatur prioritas kerja ke depan:

1. **Frontend dinyatakan cukup.** Sudah dilihat & dinilai pemilik project: "sudah bagus". Artinya: **jangan investasi ke desain frontend lagi sampai memang diperlukan** — bukan karena sempurna, tapi karena bukan bottleneck.
2. **Visi input jangka panjang: "masukkan template dokumen Anda" + link repo / upload ZIP.** Masukan penguji: form metadata 25 field terasa membebani (walau opsional) — mengisinya bikin malas, menghabiskan SDM. Arah akhirnya: pengguna meng-upload template dokumen perusahaannya sendiri, sistem men-generate mengikuti template itu. **Belum dikerjakan** — dan sadari implikasinya: template upload TIDAK menghapus masalah field manual (nomor RFC tetap tidak bisa dikarang dari kode; field itu akan balik jadi placeholder di dokumen), jadi form-nya kelak digantikan, bukan sekadar dibuang.
3. **Urutan kerja menuju visi itu**: (a) dokumen SDD hasil generate harus **sesuai dengan template acuan PREMCO** (PDF 87 halaman di `ref/benchmark/`) — *SELESAI secara struktur, bentuk, dan visual (2026-07-16/17: redesign visual + perbandingan berdampingan 12 pasang halaman + logo header). **Catatan 2026-07-18: "SELESAI" itu distempel untuk template `default`; ketika `premco` dibuat (V1) statusnya diwarisi tanpa diperiksa ulang, padahal template `premco` — yang justru dimaksudkan JADI dokumen Pertamina — masih punya gap: font Aptos (bug, harusnya Calibri), How to Access & Infrastructure belum berbentuk tabel. Ketiganya ditutup 2026-07-18 (lihat Riwayat). Sisa gap `premco` yang belum ditutup butuh Contract B: System Requirement 2-tabel, langkah flow bersarang, list fitur utama di Deskripsi Aplikasi. **Update 2026-07-21 lanjutan 10: tiga gap VISUAL cover/tanda tangan/hierarki ditutup atas permintaan pemilik "cover premco PERSIS docx PREMCO"** — cover jadi tiga tabel berbingkai header gelap (Fungsi/Kodifikasi, Katalog, Entitas/Jabatan/Nama + merge vertikal), blok tanda tangan jadi bar hitam 2×2, Use Case/Activity/Mockup jadi sub-bab bernomor 1-4; diverifikasi VISUAL (render→bake Word→PDF→lihat), bukan cuma XML. **Perbandingan penuh DITUNTASKAN 2026-07-22 (lanjutan 8): 20 dari 20 entri Daftar Isi cocok dengan acuan, berikut urutannya.** Satu gap ditemukan & ditutup di situ — judul Daftar Isi/Gambar/Tabel dulu memakai style `TOCHeading` sehingga TIDAK ikut terdaftar, padahal PDF acuan halaman 5 memuat ketiganya sebagai entri; premco kini memakai `Heading 1` (default tetap `TOCHeading` — dia bukan tiruan PREMCO). Diverifikasi VISUAL lewat bake Word→PDF.***; (b) baru pindah ke penyempurnaan UAT — *template `premco` UAT SELESAI 2026-07-18: dimodelkan dari dokumen UAT PREMCO asli (`2. UAT_...docx` di `ref/benchmark/`, gitignore), diverifikasi end-to-end pada MyPertamina (grouping test case per-layar jalan). Lihat Riwayat*; (c) baru dukungan template lain/generik — *V0 (studi kelayakan pada docx PREMCO asli) dan V1 (template kedua "premco" + multi-template via `template_id`) SELESAI 2026-07-17; lihat `scripts/validation/V0_TEMPLATE_PREMCO.md` dan Riwayat. Yang tersisa dari visi ini = V2: upload template sembarang + kompilasi dibantu LLM + tinjauan pemetaan oleh user; jalur teknisnya sintesis-reference.docx, bukan swap (swap terbukti menghasilkan paket corrupt). **KELAYAKAN V2 TERBUKTI 2026-07-18** — 5 template multi-sumber diukur, arsitektur diputus (kompilasi upload jadi template terdaftar), dan 3 increment (ukur→`TemplateSpec` / sintesis reference.docx / generate-template→isi→render) terbukti sebagai SATU RANTAI $0 pada template non-PREMCO nyata; lihat `scripts/validation/V2_TEMPLATE_MULTISOURCE.md` & Riwayat. **Sisa SAAT ITU (2026-07-18) = implementasi (konsolidasi ke `app/`+tes, LLM auto-usul peta, UI tinjauan, landscape/orientasi per-section), bukan lagi kelayakan** — status terkini tiap butirnya ada di kurung berikutnya, JANGAN baca daftar ini sebagai sisa pekerjaan hari ini.* *(increment 1 `TemplateSpec`, increment 2 sintesis reference.docx, increment 3 [generator template Jinja + peta bab heuristik], pendaftaran+storage [kompilasi upload jadi template terdaftar yang dirender `generate_docx` lewat reference tersintesisnya sendiri], DAN endpoint upload [`POST /templates` multipart docx → template_id siap pakai di `/documents/generate`] kini KODE ber-tes [2026-07-18/19] — lihat Riwayat; tersisa: LLM auto-usul peta [berbayar — **DE-RISKED 2026-07-20**: prototipe pada `Template SDD` Dynamics buktikan LLM mengubah dokumen 0→4 binding isi, $0,034; PRODUKSIONISASI SELESAI 2026-07-20 — opt-in `use_llm_mapping` (default heuristik $0), ber-tes, jalur berbayar diverifikasi ke API nyata], UI **edit** peta bab di frontend **SELESAI 2026-07-22** — `PUT /templates/{id}/mappings/{doc_type}` + panel tinjauan (lihat Riwayat). **Orientasi landscape per-section SELESAI 2026-07-21**: `template_spec_service` kini mengorelasikan tiap entri outline dengan orientasi section-nya (`orient`), generator memancarkan `((LANDSCAPE))`/`((PORTRAIT))` saat BERUBAH, dan `_apply_orientation_markers` (generalisasi `_landscape_after_marker`) menerjemahkannya jadi N section — diverifikasi end-to-end pada template sintetis potret→landscape→potret.)* "Sesuai sempurna" di sini artinya **kesetaraan struktur dan bentuk penyajian** — bagian yang mustahil dari kode (mockup, timeline, cost, tanda tangan, URL infra) tetap placeholder; mengarang isinya justru merusak nilai jual produk.

## Alur Sistem (Arsitektur End-to-End)

```
Source Provider (GitHub OAuth / GitHub PAT / ZIP upload)
        |
        v
Repository Normalizer  ->  Workspace (format seragam, titik ini Parser
        |                   tidak tahu/peduli asal source-nya)
        v
narrow_to_product()  ->  buang yang bukan produk, berdasarkan manifest repo
        |                (pyproject.toml / package.json). Gagal-membuka:
        |                tidak ketahuan = simpan semua.
        v
Parser (Tree-sitter, deterministik, TANPA LLM)
        |
        v
ParsedRepoContext.json  ==  Contract A  (Peran 1 -> Peran 2)
        |
        v
LLM (Claude, via Anthropic SDK)  ->  cross-repo mapping (FE fetch <-> BE endpoint)
        |                            + narasi dokumen + script diagram Mermaid
        v
DocumentContent.json  ==  Contract B  (Peran 2 -> Peran 3)
        |
        v
Template Engine (Jinja2, Markdown)  +  PlantUML -> PNG (LOKAL, plantuml.jar)
        |
        v
Pandoc  ->  .docx
        |
        v
Solution Design Document (.docx)  /  UAT Document (.docx)
```

Seluruh rantai di atas jalan **di latar belakang** (sejak 2026-07-16). Dari sisi
klien bentuknya tiga langkah, bukan satu:

```
POST /documents/generate   ->  202 + {job_id}      (~50ms; kerjanya belum jalan)
        |                          |
        |                     BackgroundTasks: rantai di atas (~100-190 detik)
        |                          |
        |                     job_store (SQLite): queued -> running -> done/failed
        v                          v
GET /documents/jobs/{id}   ->  status  ->  GET /documents/jobs/{id}/download
```

Alasannya bukan kerapian: menahan pipeline 191 detik di satu request HTTP membuat
produk ini **mustahil di-deploy** — proxy/load balancer memutus di 30-60 detik
(Heroku 30, nginx & AWS ALB 60, Vercel 10-60), sementara server tetap lanjut
bekerja dan tetap membayar LLM untuk dokumen yang tidak pernah sampai ke siapa
pun. Di localhost tidak ada satu pun batas itu, jadi bug-nya tak terlihat.

Prinsip desain: setiap tahap dipisah dengan **kontrak JSON** yang jelas (Contract A, Contract B), supaya tim bisa kerja paralel dan tiap tahap bisa diganti tanpa merusak tahap lain (mis. ganti sumber kode dari GitHub ke ZIP tidak menyentuh kode parser; ganti LLM provider tidak menyentuh kode ingestion/parser).

## Tim & Pembagian Kerja

Tim 3 orang, tiap orang pegang satu tahap pipeline:

| Peran | Tanggung Jawab | Status |
|---|---|---|
| **Peran 1 — Ingestion & Parsing** | Ambil source code dari sumber manapun (GitHub OAuth/PAT/ZIP), normalisasi, ekstrak struktur kode pakai Tree-sitter | ✅ Selesai, sudah di `develop` |
| **Peran 2 — AI & Prompt Engineering** | Cross-repo mapping, panggil LLM untuk isi konten dokumen + script diagram Mermaid | ✅ Sudah lengkap — lihat catatan migrasi provider di bawah |
| **Peran 3 — Backend & Templating** | Endpoint FastAPI orkestrator, template Jinja2, ekspor ke `.docx` via Pandoc, frontend | ✅ Sudah ada — pipeline penuh (ingest → parse → LLM → template → docx) sudah tersambung end-to-end lewat `POST /documents/generate` |

Semua tahap sudah terhubung. Sisa pekerjaan yang belum dilakukan (bukan bug, memang belum dikerjakan) ada di bagian **Keterbatasan** di bawah.

## Kontrak JSON Antar-Tahap

### Contract A — `ParsedRepoContext.json` (Peran 1 → Peran 2)

Diimplementasikan di `app/services/parser_service.py` (`build_parsed_repo_context`), deterministik, **tanpa panggilan LLM**. Mendukung Python, TS/JS/TSX, dan **Java** (deteksi endpoint: FastAPI/Flask-style Python decorator, Express-style call, method-based TS, **Spring MVC annotation**, **Next.js App Router** `route.ts` named-export dengan path dari struktur folder); bahasa lain jatuh ke entry `"type": "other"` minimal.

```json
{
  "project_name": "...",
  "repositories": [
    {
      "repo_tag": "Backend",
      "files": [
        {
          "file_name": "...",
          "file_path": "...",
          "type": "controller|service|repository|model|ui_component|other",
          "dependencies": ["..."],
          "classes": [
            {"class_name": "...", "methods": [{"method_name": "...", "parameters": ["..."], "return_type": "...", "description": "..."}]}
          ],
          "functions": [
            {"function_name": "...", "parameters": ["..."], "return_type": "...", "description": "..."}
          ],
          "api_endpoints": [
            {"method": "GET|POST|PUT|DELETE", "path": "...", "payload": "..."}
          ]
        }
      ]
    }
  ]
}
```

Catatan: `functions[]` adalah tambahan dari kontrak desain awal (dokumen desain awal cuma punya `classes[]`) — top-level function/standalone function juga diekstrak, bukan cuma method di dalam class.

### Contract B — `DocumentContent.json` (Peran 2 → Peran 3)

Diimplementasikan di `app/services/llm_service.py` (`LLMService.generate_document_content(parsed_repo_context, target_doc_type) -> dict`) via Anthropic Claude (model dibaca dari `LLM_MODEL` di `.env`, default `claude-sonnet-5`) dengan **structured output** (`client.messages.parse(output_format=DocumentContent)` — Pydantic model, bukan parsing JSON manual dari teks).

```json
{
  "document_type": "SDD | UAT",
  "app_description": "...",
  "user_roles": [
    {"role_name": "...", "description": "hak akses & tanggung jawab, non-teknis"}
  ],
  "system_requirements": [
    {"name": "Programming Language | Web Framework | Database | ...", "detail": "..."}
  ],
  "feature_requirements": [
    {"feature_name": "...", "description": "..."}
  ],
  "diagrams": {
    "system_architecture": "@startuml ... @enduml (PlantUML component diagram)",
    "component_integration": "@startuml ... @enduml",
    "business_process_flow": "@startuml ... @enduml (activity, alur bisnis end-to-end)",
    "use_case_diagram": "@startuml ... @enduml (actor + usecase + rectangle)",
    "activity_diagrams": [
      {"activity_name": "...", "description": "...", "actor": "...", "pre_condition": "...",
       "steps": ["langkah 1", "langkah 2"], "diagram_script": "@startuml ... @enduml"}
    ]
  },
  "use_cases": [
    {
      "use_case_id": "UC-01",
      "actor": "...",
      "pre_condition": "...",
      "description": "...",
      "acceptance_criteria": ["...", "..."]
    }
  ],
  "business_flow_description": "...",
  "business_flow_steps": ["tahapan bernomor 1", "tahapan 2", "..."],
  "uat_test_cases": [
    {"test_id": "UAT-01", "role": "...", "module": "layar/fitur yang diuji, mis. 'Halaman Login'", "activity": "...", "steps": "...", "expected_result": "..."}
  ]
}
```

`module` ditambahkan 2026-07-18 (untuk grouping test case per-layar di template `premco` UAT — lihat Riwayat). Wajib (bukan Optional) di schema output LLM supaya grouping selalu punya data; **compiler tetap toleran** kalau field ini tak ada (`_group_test_cases` pakai `.get("module")`), jadi Contract B lama tanpa `module` tetap render (jatuh ke satu tabel). Template `default` mengabaikannya. Test case dengan nilai `module` SAMA dikelompokkan jadi satu tabel; prompt mewajibkan nilai konsisten huruf-demi-huruf + urutan berdampingan.

**Skema di atas berubah besar 2026-07-16** (migrasi PlantUML + pendalaman ke bentuk acuan): semua field diagram kini PlantUML (dulu Mermaid; `mermaid_script` → `diagram_script`), activity diagram membawa metadata acuan (`actor`/`pre_condition`/`steps`), dan `user_roles`/`business_flow_steps`/`business_process_flow` baru; `system_requirements` berubah dari `list[str]` jadi terstruktur. **Contract B lama tidak kompatibel** — file `*_contract_b.json` di `scripts/validation/out/` dari sebelum tanggal itu tidak bisa di-render ulang dengan compiler baru.

**`target_doc_type` memengaruhi alokasi kedalaman konten** (bukan cuma label): kalau `SDD`, prompt memprioritaskan kedalaman di `diagrams`/`feature_requirements`/`use_cases` dan `uat_test_cases` cukup representatif; kalau `UAT`, prompt memprioritaskan `uat_test_cases` yang exhaustive (idealnya satu per endpoint/fitur utama) sementara `diagrams`/`use_cases` cukup ringkas.

Sudah diverifikasi lewat pemanggilan API sungguhan, **termasuk setelah urutan prompt dibalik** (2026-07-15, `target_doc_type` kini muncul sesudah Contract A demi caching): pada `dummy_data`, SDD menghasilkan 5 `uat_test_cases` sementara UAT menghasilkan 9, dengan `feature_requirements`/`use_cases`/`activity_diagrams` yang sama — persis pola yang dijanjikan di atas.

**`app_description`, `feature_requirements[].description`, `use_cases[].description`, dan `business_flow_description` wajib ditulis untuk pembaca non-teknis** (product owner, QA manual, user bisnis) — ini prinsip eksplisit di system prompt `llm_service.py`, konsisten dengan positioning produk sebagai SaaS untuk berbagai kalangan, bukan cuma developer.

### `DocumentMetadata` — isian manusia, BUKAN bagian Contract B

Diimplementasikan di `app/api/schemas_document.py`, masuk lewat `document_metadata` di `GenerateDocumentRequest`, dipakai template sebagai `{{ meta.<field> }}`. Isinya 37 field yang **manusia tahu tapi kode tidak akan pernah tahu**: nomor RFC, No. Solution Design, versi, klasifikasi dokumen, ERP/NON ERP, **4 field kodifikasi/katalog + 1 `entitas` (nama perusahaan, kolom pertama tabel Tim Project gaya premco — ditambah 2026-07-21 lanjutan 10) + 7 nama Tim Project untuk halaman cover** (ditambah 2026-07-21 saat cover didesain ulang — sebelumnya sel-sel itu kosong permanen di template), 7 baris Informasi Demografi, How to Access, Infrastructure & Capacity, 3 remark checklist Security (29 dipakai SDD); Related RFC/Work Order, Change Owner, Prepared/Reviewed By + tanggalnya, Distribution List, **Quality Review Method + Document Version No/Date** (3 terakhir ditambah 2026-07-18 untuk tabel Document Information di template premco UAT) (11 dipakai UAT).

**Sengaja tidak digabung ke `DocumentContent`.** Contract B itu kontrak *output LLM*; ini *input manusia*. Arahnya berlawanan — LLM tidak boleh mengarang nomor RFC, dan pengguna tidak menulis use case. Menggabungnya akan memaksa LLM mengisi field yang bukan urusannya.

Semua field `Optional`. Yang kosong (termasuk string berisi spasi) jatuh balik ke penanda `*(diisi manual)*` lewat `_MetadataDict.__missing__` di `compiler_service.py` — jadi `document_metadata: null` menghasilkan dokumen persis seperti sebelum form ini ada. Menambah field cukup menyentuh **schema + template**; sengaja tidak ada daftar field ketiga di compiler yang bisa basi diam-diam.

**Logo perusahaan BUKAN field `DocumentMetadata`** walau sama-sama isian manusia (sejak 2026-07-17): dia `logo_base64` sendiri di `GenerateDocumentRequest`. Kontrak metadata itu "string yang jatuh ke penanda `(diisi manual)` kalau kosong"; logo itu biner yang jatuh ke "tanpa header" — perilaku kosongnya beda, dan menaruh base64 di `meta.*` akan bocor sebagai teks ke template.

## Struktur Proyek

```
app/
  domain/            # data murni + interface (SourceProvider), tanpa dependency framework
    models.py, ports.py, exceptions.py
  ingestion/         # implementasi SourceProvider
    filters.py               # file mana yang relevan: ekstensi, dir yang di-skip
                             #   (node_modules, venv), dir test/contoh, pola nama file test
    manifest.py              # tanya pyproject.toml/package.json: mana yang produk?
    provider_factory.py      # pilih provider (GitHub / ZIP) berdasarkan SourceType
    providers/github_provider.py, providers/zip_provider.py
  services/
    ingestion_service.py     # orkestrasi ingest -> narrow_to_product -> Workspace (Peran 1)
    parser_service.py        # Tree-sitter structural extraction, Contract A (Peran 1)
    github_oauth_service.py  # OAuth GitHub scaffold (Peran 1)
    llm_service.py           # LLMService, Contract A -> Contract B via Claude (Peran 2)
    db.py                    # lapisan DB bersama: SQLite (default) ATAU Postgres
                             #   kalau DATABASE_URL diisi (#13). Menerjemahkan yang
                             #   memang dialek (?→%s, `IS ?`→IS NOT DISTINCT FROM,
                             #   PRAGMA→information_schema); sisa SQL ditulis dalam
                             #   irisan yang dipahami DUA mesin, supaya tak ada dua
                             #   versi query yang bisa menyimpang diam-diam.
    job_queue.py             # seam EKSEKUSI job (#13): REDIS_URL kosong = inline
                             #   (BackgroundTasks), terisi = RQ (worker terpisah).
                             #   requeue_abandoned() MELANJUTKAN job yang mati
                             #   bersama worker-nya — beda dari reaper yang cuma
                             #   memvonis. Argumen job tersimpan di Redis, jadi
                             #   payload tak perlu diduplikasi ke tabel `jobs`.
    job_store.py             # status job + path dokumen (SQLite stdlib) — Peran 3
    rate_limit_service.py    # batas pemakaian per-akun untuk endpoint berbayar.
                             #   Penghitungnya BUKAN struktur data baru: dihitung
                             #   dari baris `jobs` & manifest template yang memang
                             #   sudah tersimpan — itu yang bikin benar lintas-worker
                             #   & tahan restart tanpa Redis. Jendela SLIDING.
    billing_service.py       # metering token + estimasi biaya, kuota per tier, Stripe.
                             #   Tabel `user_subscriptions` & `usage_records` di DB yang
                             #   SAMA dengan job_store. Tier cuma naik lewat webhook
                             #   ber-signature. Kuota menghitung job yang benar-benar
                             #   memakai LLM — job yang mati sebelum LLM tak memotong.
                             #   Tarif dari LLM_MODEL (harga daftar = PLAFON).
    compiler_service.py      # Contract B -> render Mermaid -> Jinja2 -> .docx (Peran 3)
    template_spec_service.py # V2: ukur docx template user -> TemplateSpec (JSON), deterministik
                             #   Judul bab dicari di SELURUH wadah terukur, bukan cuma
                             #   style Heading: text box (tanpa style) ikut dipindai —
                             #   lihat _extract_outline untuk sinyal yang sengaja TIDAK dipakai
    template_generator_service.py  # V2: outline TemplateSpec -> template Jinja (+ peta bab heuristik)
    reference_synthesis_service.py # V2: TemplateSpec -> reference.docx tersintesis (logika
                             #   dipindah dari scripts/; CLI build_reference_docx.py pakai ini)
    template_compiler_service.py   # V2: orkestrator — docx upload -> ukur -> generate ->
                             #   sintesis -> simpan+daftar di data/templates/<id>/
    user_data_service.py     # ekspor & hapus data pengguna (#16). SATU tempat yang
                             #   memegang daftar LIMA penyimpanan data pengguna —
                             #   daftar di dua tempat pasti akan menyimpang, dan
                             #   menyimpangnya baru ketahuan saat seseorang
                             #   menanyakan data yang katanya sudah dihapus.
                             #   Menolak jalan di mode dev: di sana semua orang
                             #   satu identitas anonim, jadi "hapus data saya"
                             #   akan mengosongkan instance.
  diagram/                   # LAYER DIAGRAM
    activity_render.py       # ACTIVITY gaya draw.io: PlantUML -> IR -> PNG (docx)
                             #   & .drawio (suntingan). Tata letak dihitung SENDIRI
                             #   (satu node/baris, routing koridor). SUDAH dipakai
                             #   pipeline live; jatuh ke PlantUML lewat supports()
                             #   bila script di luar subset. Sejak 2026-07-22 file
                             #   .drawio-nya ikut dibundel & bisa diunduh per job.
    ir/                      # (redesign 2026-07-20, Option C) IR semantik + renderer
                             #   per-backend, ala AST+codegen. BELUM disambung ke
                             #   pipeline live — activity_render.py punya parser &
                             #   layout sendiri. Fondasi untuk "LLM emit IR" kelak.
                             #   Isinya: representasi diagram NETRAL (makna, bukan
                             #   syntax/layout);
                             #   model GRAF (node/edge/lane). base.py + activity.py,
                             #   usecase.py, architecture.py, component.py
    renderer/                # IR -> source backend (IR tak tahu renderer ada)
      base.py                #   DiagramRenderer (antarmuka abstrak)
      plantuml/              #   backend PERTAMA: IR -> PlantUML struktur-saja (theme
                             #     tetap disuntik compiler_service._normalize_plantuml)
  api/
    routes_ingestion.py      # POST /ingest/github, POST /ingest/zip
    routes_auth.py           # GET /auth/github/login, GET /auth/github/callback
    routes_document.py       # POST /documents/{sdd,uat,generate}, GET /documents/jobs/*
    routes_template.py       # V2: POST /templates (upload docx), GET /templates[/{id}]
    routes_billing.py        # GET /billing/usage, POST /billing/checkout, POST /billing/webhook
    routes_account.py        # #16: GET /me/export, DELETE /me/data
    routes_legal.py          # #16: GET /privacy, /terms — publik, tanpa auth
    schemas.py, schemas_document.py
  legal/                     # privacy.html, terms.html — DRAF berisi penanda
                             #   [ISI: ...] untuk fakta yang cuma pemilik tahu
                             #   (nama entitas, yurisdiksi, kontak). Spanduk
                             #   "draf" DITURUNKAN dari ada-tidaknya penanda,
                             #   bukan ditulis manual: spanduk manual bisa lupa
                             #   dipasang DAN lupa dihapus.
  templates/
    sdd_template.md, uat_template.md   # template Jinja2 (Markdown) sebelum dikonversi ke docx
    sdd_premco_template.md      # template gaya PREMCO SDD (kompilasi manual V1) —
                                #   dipilih lewat template_id="premco" di form
    uat_premco_template.md      # template gaya PREMCO UAT (2026-07-18): header
                                #   hijau, grouping per-modul, section landscape
    reference.docx             # kerangka TAMPILAN dokumen: tipografi, gaya tabel,
                               #   kaki halaman bernomor. LOGIKA di services/
                               #   reference_synthesis_service.py; regenerasi lewat
                               #   CLI scripts/build_reference_docx.py — JANGAN diedit
                               #   tangan, hasil editnya akan tertimpa.
                               #   Dikecualikan dari pola `*.docx` di .gitignore.
  core/config.py             # baca .env (ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_CLIENT_*,
                             #   TEMPLATES_STORE_PATH untuk data/templates/ V2)
  main.py                    # entrypoint FastAPI, CORS, daftar router
  worker.py                  # entrypoint WORKER (#13): `python -m app.worker`.
                             #   Proses TERPISAH dari web — itu seluruh gunanya.
                             #   Butuh REDIS_URL; menolak start tanpa itu.

frontend/                    # React + Vite, form sederhana yang hit POST /documents/generate
  src/App.jsx, src/main.jsx
  src/AccountDataPanel.jsx   # #16: unduh/hapus data + footer tautan legal

Caddyfile                    # #15: reverse proxy TLS otomatis. Dipakai HANYA lewat
                             #   `docker compose --profile proxy up` — `up` biasa
                             #   tak menjalankannya, jadi alur lokal tak berubah.

tests/                       # pytest (441 test) — lihat bagian Testing
tests/                       # pytest (427 test) — lihat bagian Testing
dummy_data/                  # fixture JSON — dipakai test otomatis DAN testing manual
scripts/                     # utilitas dev, bukan bagian dari aplikasi
  model_getter.py            # cetak daftar model yang tersedia untuk API key kamu
  evaluate_document.py       # ukur MUTU ISI dokumen thd Contract A: grounding
                             #   (karangan), representasi (kelalaian), konsistensi.
                             #   Dipanggil render_fixtures tiap jalan; ber-tes.
  render_fixtures.py         # render SEMUA Contract B tersimpan -> docx ($0, tanpa
                             #   LLM & tanpa jaringan). Regresi visual saat kuota API
                             #   habis: langkah berbayar cuma Contract A->B.
  validation/                # kerangka validasi ke repo publik nyata — lihat Testing
    README.md                #   cara pakai + kenapa ini bukan pengganti pytest
    repos.json               #   10 kasus uji, tiap kasus menguji satu asumsi produk
    run_validation.py        #   harness 2 tahap (gratis / berbayar)
    out/                     #   hasil run (di-gitignore)
```

Root sengaja dijaga cuma berisi file konfigurasi/dokumen (`.env.example`, `.gitignore`, `CLAUDE.md`, `README.md`, `requirements.txt`) — kode dan aset selalu masuk folder. Kalau menambah script utilitas, taruh di `scripts/`, jangan di root.

**Bahan kerja yang tidak ikut repo ada di `ref/`** (seluruh folder di-gitignore, dirapikan 2026-07-21 — sebelumnya ~15 file berserakan di root dan melanggar aturan di atas):

```
ref/                       # TIDAK ikut repo; ada di mesin pengembang saja
  benchmark/               # PREMCO SDD (.pdf 87 hlm + .docx) & UAT .docx —
                           #   dokumen internal klien, acuan visual produk ini
  template-sumber-lain/    # template docx dari sumber LAIN (bahan uji V2):
                           #   Template SDD (Dynamics), moe_mal, system_design_
                           #   document_template, 04. Dokumen UAT, Veracity
  keluaran-lama/           # docx hasil generate lampau (bukan acuan apa pun)
```

Dulu ada `lain-lain/` berisi installer pandoc 41 MB + screenshot UI lama; **dua-duanya dihapus 2026-07-21** dan foldernya dibuang. Keduanya bisa didapat lagi kalau benar-benar perlu: pandoc lewat `pypandoc.download_pandoc()` (lihat Setup Lokal), tampilan frontend lama dengan checkout commit sebelum redesign lalu `npm run dev`.

`ref/` ditutup **seluruh folder** di `.gitignore`, bukan per-ekstensi. Alasannya masih berlaku walau isinya sekarang cuma dokumen: pola `*.docx`/`*.doc`/`*.pdf` berlaku global, tapi `/*.png` cuma menutup root — begitu ada gambar/aset non-dokumen masuk `ref/`, mengandalkan pola per-ekstensi akan membocorkannya.

## Tech Stack

- **Backend**: Python + FastAPI + Uvicorn
- **Ingestion**: PyGithub (GitHub OAuth/PAT), ZIP upload in-memory (dengan guard anti zip-bomb)
- **Parsing**: `tree-sitter` + `tree-sitter-language-pack` — AST-based, generik multi-bahasa (bukan regex, bukan LLM)
- **LLM**: **Anthropic Claude** via official `anthropic` Python SDK, dipanggil langsung (bukan lewat LangChain). Modelnya **bisa diatur** lewat `LLM_MODEL` di `.env` — default `claude-sonnet-5`. Jangan bingung dengan model yang dipakai Claude Code saat mengerjakan repo ini (diatur lewat `/model`): dua-duanya terpisah total.
- **Templating & Export**: Jinja2 (Markdown) → Pandoc (`pypandoc`) → `.docx`. **Tampilannya** (tipografi, gaya tabel, kaki halaman bernomor) datang dari `app/templates/reference.docx` lewat `--reference-doc`, **bukan** dari template Jinja2 — jadi mengubah rupa dokumen umumnya tidak menyentuh markup-nya. File itu dibangun `scripts/build_reference_docx.py`; edit script-nya, jangan docx-nya. **Empat pengecualian yang memang tidak bisa dibawa reference.docx** (2026-07-17, alasan lengkap di Riwayat): lebar kolom tabel = rasio dash pada separator row template (dibaca karena `--columns=20`); perataan tengah teks header tabel + caption tabel DI BAWAH tabelnya (konvensi acuan; Pandoc selalu menulisnya di atas) + baris tabel tanda tangan setinggi ≥1 inci dan bloknya diikat utuh se-halaman = post-process `_postprocess_docx` di compiler (Word mengabaikan `pPr` dari table style — diprobe); posisi Daftar Isi/Gambar/Tabel SDD = field code Word yang ditanam langsung di template (Pandoc memaku `--toc` di tempat yang salah); **halaman cover** (2026-07-21) = judul dipecah jadi dua tingkat + blok bermarker `((CVBAND))`/`((CVLIST))` yang dilepas rupa tabelnya (Pandoc tak bisa menunjuk table style per-tabel, Markdown tak punya "tabel tanpa garis"). Tipografi cover-nya sendiri TETAP di reference.docx sebagai style bernama (`Cover Eyebrow`/`Subtitle`/`Rule`/`Section Label`), dipanggil template lewat div `::: {custom-style="..."}`. **Perbedaan `premco` (2026-07-21, lanjutan 10 — atas permintaan pemilik "cover premco PERSIS docx PREMCO")**: template `premco` TIDAK memakai cover minimalis borderless itu — dia memakai TIGA tabel berbingkai header gelap (Fungsi/Kodifikasi, Katalog Proses Bisnis, Entitas/Jabatan/Nama), jadi cukup pipe table biasa (header hitam dari style tabel bawaan). Marker khusus premco: `((CVMERGE))` (merge vertikal kolom Entitas → `_merge_cover_entity_column`), `((SIGBAR))` (bar hitam blok tanda tangan Perwakilan User/Pengembang, 2 kolom × 2 baris → `_apply_signature_bars`, berbagi helper `_merge_first_row_into_bar` dengan bar biru `((BAR))`). `((CVBAND))`/`((CVLIST))` tetap MILIK `default`. Di `premco`, Use Case/Activity Diagram/Mockup Website/Mockup Aplikasi kini SUB-BAB Heading 2 bernomor 1-4 di bawah Flow Proses Bisnis (meniru Daftar Isi docx asli), bukan bab tersendiri. **Sejak 2026-07-23, tiap activity diagram jadi SUB-BAB SENDIRI Heading 3 bernomor manual "2.N"** ("2.1 Activity Diagram Login", "2.2 …" — meniru docx PREMCO yang memecah tiap activity jadi bagian terpisah; keputusan pemilik: sub-bab ini MASUK Daftar Isi lewat TOC level 1-3, jadi TOC premco kini lebih rinci dari 20-entri acuan). **Logo header & footer bernomor `premco` bukan hal baru** — logo lewat `logo_base64` upload (`_add_header_logo`, kanan-atas tiap halaman; TIDAK di-bake ke repo — trademark klien, sama alasan `ref/` gitignore), footer TITLE+PAGE dari reference.docx; dua-duanya sudah ada sebelum 2026-07-23 dan cuma dikonfirmasi visual. **Dua penyempurnaan lanjutan 11** (atas feedback pemilik pada output esteler nyata): (1) blok judul cover `premco` SDD **di-align KANAN** (`_right_align_cover` — paragraf `Cover Eyebrow`/`Title`/`Cover Subtitle`), di-gate flag `cover_align_right` di `_ResolvedTemplate` (premco-only, SDD-only; default tetap tengah); (2) tabel Infrastructure `premco`: sel sub-environment + Remark yang DUA-DUANYA kosong digabung jadi satu sel lebar (`_merge_infra_empty_cells`, tabel dikenali `_is_infra_table` dari header `No.|Resources|<kosong>|Remark`) — baris ber-sub-env (Akses URL → Development/QA) tetap terpisah.
- **Diagram**: **PlantUML** (sejak 2026-07-16; sebelumnya Mermaid via mermaid.ink) — script digenerate LLM, dirender ke PNG **secara lokal** lewat `plantuml.jar` (butuh **Java 17+**; layout engine `smetana` bawaan jar, jadi tidak butuh Graphviz). Dipilih pemilik project lewat perbandingan berdampingan (`scripts/diagram_comparison.py`): gaya UML-nya (aktor stick-figure, oval use case, activity ber-start/end) persis bahasa visual dokumen acuan enterprise, dan render lokal berarti isi diagram tidak pernah meninggalkan mesin. Gaya visual disuntik compiler (`_PLANTUML_STYLE_PREAMBLE`), bukan ditulis LLM — filosofi yang sama dengan `reference.docx`. **Sejak 2026-07-22 gaya dipisah PER TIPE DIAGRAM** (keputusan pemilik, dari perbandingan ke acuan): **arsitektur & integrasi komponen** memakai "tema enterprise" berwarna (`_PLANTUML_STYLE_PREAMBLE` — rounded, shadow, palet biru-abu + aksen hangat), sementara **use case, activity, & flow proses bisnis** memakai `_PLANTUML_PLAIN_PREAMBLE` (UML **hitam-putih**, hanya `!theme plain` + dpi) karena acuannya (digambar draw.io) memang hitam-putih. `_normalize_plantuml`/`_render_diagram_to_image` menerima parameter `style`. Dipilih lewat **Fase 0** — perbandingan berdampingan render esteler (PlantUML kini vs ber-tema vs D2, di scratchpad, $0): tema uplift SERAGAM di ketiga tipe tanpa dependency/perubahan pipeline AI, dan untuk use case + activity JUSTRU lebih baik dari D2 (D2 unggul hanya di graf-node arsitektur, DAN butuh Playwright/headless-browser untuk ekspor PNG — dep berat yang dihindari, sama seperti alasan Mermaid.ink dulu). Ikon vendor SENGAJA tidak ditambahkan (glyph generik redundan dengan bentuk; logo vendor tak bisa dicocokkan andal untuk service sembarang). Font tidak dipatok (diagram dirender server-side; font Windows-only tak konsisten). **Activity diagram ber-SWIMLANE sejak 2026-07-22**: `_add_swimlanes` menyisipkan `|Aktor|`/`|Sistem|` ke PlantUML activity dari LLM — ciri utama activity diagram dokumen acuan (dibuat draw.io). **Tanpa menyentuh pipeline AI**: informasi "siapa mengerjakan apa" SUDAH ada karena prompt mewajibkan langkah difrasakan *"Aktor melakukan X"/"Sistem merespons Y"*, jadi subjeknya di awal kalimat; nama lane manusia diambil dari field `actor` Contract B. Lane ditulis hanya saat BERUBAH. Konservatif: script yang sudah ber-lane tak ditimpa, script tanpa baris `:Langkah;` (arsitektur/komponen/use case) dikembalikan apa adanya, dan langkah tanpa subjek jelas MEWARISI lane berjalan (menebak = salah menyatakan tanggung jawab, kesalahan ISI bukan rupa). `_render_activity_diagram` punya fallback sempit: versi ber-lane gagal → pakai versi tanpa lane (rupa tak boleh menggagalkan dokumen). Terukur di 8 diagram esteler: 8/8 render, 0 ambigu. **Swimlane DIBENTUK JADI TABEL** `_close_swimlane_border`: PlantUML cuma menggambar garis VERTIKAL (kotaknya menganga — keluhan pemilik "kotak tidak tertutup"; dua varian skinparam diprobe, output identik → PlantUML memang tak punya opsinya), jadi bingkai luar DAN **garis di bawah baris judul lane** digambar pada kotak-batas isi SESUDAH PNG jadi. Batas header dideteksi `_swimlane_header_bottom` dari profil tinta per baris (pita judul → celah yang isinya cuma garis lane), dijaga `_SWIMLANE_HEADER_MAX_FRAC` supaya tak memotong badan diagram. Hasilnya kolom kiri = lajur aktor, kanan = lajur Sistem, header terkotak — "tabel sebagai latar, alur menyesuaikan lajur". **Efek samping geometri yang perlu diingat**: tiap `case` pada `switch` menjadi satu kolom SEJAJAR, jadi cabang berlebih membuat diagram melar dan hurufnya mengecil saat dimuat ke lebar halaman (terukur: 6 `case` → rasio 4,28). Prompt karenanya membatasi **maksimal 4 `case` per `switch`**. **Dua sentuhan terakhir menuju bentuk draw.io (2026-07-22 lanjutan 5)**: `skinparam conditionStyle InsideDiamond` di preamble polos (keputusan jadi DIAMOND berteks di dalam, bukan heksagon bawaan — diprobe berdampingan) dan `_add_diagram_title` menyisipkan `title <activity_name>` sehingga judul terkurung DI DALAM bingkai sebagai pita judul di atas baris nama lane (`_swimlane_header_bottoms` mendeteksi sampai 2 pita header). **Batas PlantUML yang TIDAK bisa ditiru — jangan dikejar lagi**: tanda X di dalam diamond, dan garis putus-putus untuk alur balik (activity beta tak bisa menata gaya per-edge). **Flow proses bisnis SENGAJA TANPA swimlane** — di acuan ia flowchart bercabang, bukan diagram berlajur. **Sejak 2026-07-22 (lanjutan 3) prompt IKUT diperkuat** supaya ISI diagram sekaya acuan: use case wajib menambah relasi `<<include>>`/`<<extend>>` bila berjejak (maks 1-4, dilarang mengarang); business flow wajib ≥2 titik keputusan dan DILARANG memakai swimlane; activity wajib menulis swimlane sendiri + `switch` untuk cabang >2 + menceritakan workflow fitur utuh (sasaran 8-16 langkah). Penyeimbangnya **ATURAN KEJUJURAN UNTUK KEPADATAN DIAGRAM** — angka sasaran BUKAN kuota, "8 langkah berjejak > 16 langkah separuh karangan". Diverifikasi berbayar pada esteler + audit karangan (nol temuan). Karena LLM kini menulis lane sendiri, `_add_swimlanes` melewatinya dan `_has_swimlanes` yang menentukan pembingkaian. **D2/draw.io TIDAK diperlukan untuk ini** — dan D2 memang ditolak: dependency-nya tak berkurang walau dipakai satu tipe saja (binari + rasterizer SVG tetap wajib), dan layout-nya tak punya titik tengah (`direction: down` rasio 0,61 terlalu tinggi; `right` 10,7 terlalu lebar; v0.7.1 tanpa knob spacing). Menaikkan KEKAYAAN alur (lebih banyak langkah/keputusan/loop seperti acuan) masih butuh penyetelan prompt — belum diambil.
- **Frontend**: React + Vite (SPA sederhana, satu form)
- **Testing**: `pytest`

## Environment Variables (`.env`, contoh di `.env.example`)

| Variable | Wajib? | Keterangan |
|---|---|---|
| `ANTHROPIC_API_KEY` | Ya (untuk fitur LLM / Peran 2) | https://console.anthropic.com/settings/keys |
| `LLM_MODEL` | Opsional | Model yang dipakai **aplikasi** untuk menulis dokumen. Kosong = `claude-sonnet-5`. Harga per 1M token (input/output, per 2026-07-15): `claude-sonnet-5` $3/$15 (intro $2/$10 s/d 2026-08-31), `claude-opus-4-8` $5/$25, `claude-haiku-4-5` $1/$5. |
| `DATABASE_PATH` | Opsional | Lokasi SQLite untuk status job + dokumen. Kosong = `data/jobs.db` (di-gitignore, dibuat otomatis). **Sengaja bukan folder temp**: generation itu async, dan seluruh guna DB ini adalah bertahan melewati response — bahkan melewati restart. |
| `PLANTUML_JAR` | Opsional | Path ke `plantuml.jar` untuk render diagram lokal (butuh Java 17+ di PATH). Kosong = `tools/plantuml.jar`. Unduh sekali dari https://github.com/plantuml/plantuml/releases. |
| `GITHUB_TOKEN` | Opsional | PAT untuk akses repo privat lewat endpoint ingest berbasis PAT. Repo publik tetap bisa tanpa token, cuma rate-limited 60 req/jam. |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_OAUTH_REDIRECT_URI` | Opsional | Cuma perlu kalau mau flow OAuth GitHub beneran jalan (perlu GitHub OAuth App terdaftar — belum ada saat ini, lihat Keterbatasan). |
| `RATE_LIMIT_WINDOW_SECONDS` / `RATE_LIMIT_GENERATE_PER_WINDOW` / `RATE_LIMIT_TEMPLATE_UPLOAD_PER_WINDOW` | Opsional | Batas pemakaian **per-akun** untuk endpoint berbayar. Default 3600 detik / 10 generate / 20 upload template. Jendela **sliding** (bukan reset di jam bulat). `0` = matikan batas untuk endpoint itu; nilai tak masuk akal **menggagalkan startup** (`config._int_env`) supaya salah-ketik tak diam-diam jadi "tanpa batas". Cuma berlaku kalau `SUPABASE_URL` diisi — lihat `rate_limit_service`. |
| `REDIS_URL` / `JOB_QUEUE_NAME` / `JOB_MAX_ATTEMPTS` | Opsional | **Worker queue (#13).** `REDIS_URL` kosong = eksekusi INLINE lewat `BackgroundTasks` (perilaku lama, nol layanan tambahan, cukup untuk 1 instance). Terisi = web cuma mengantri dan `python -m app.worker` yang mengeksekusi → job **selamat dari restart/crash/deploy proses web**. `JOB_MAX_ATTEMPTS` (default 1) = berapa kali job yang mati BERSAMA worker-nya diulang otomatis; kegagalan permanen (413/422/500) tak pernah diulang. `0` = matikan re-queue. |
| `ALLOWED_ORIGINS` | Opsional | **CORS (#15).** Origin yang boleh memanggil API dari browser, dipisah koma. Kosong = dev server Vite (`http://localhost:5173` + `127.0.0.1:5173`) — dulu `["*"]` HARDCODE. Sebagian besar deploy tak perlu menyentuhnya: di Docker SPA disajikan same-origin, jadi CORS praktis tak terpakai. Garis miring di ujung dipangkas (browser mengirim `Origin` tanpa itu; ketidakcocokannya SENYAP). `*` masih boleh tapi harus ditulis sendiri + mencatat peringatan startup. **`SITE_ADDRESS` (domain untuk Caddy) BUKAN env aplikasi** — dia dibaca `docker compose`, jadi tak ada di `config.py`. |
| `DATABASE_URL` | Opsional | **Postgres (#13).** Kosong = SQLite di `DATABASE_PATH`. Terisi = state dibagi lintas **MESIN** — yang dibutuhkan begitu web & worker hidup di container berbeda. Multi-worker di SATU mesin sudah lama jalan dengan SQLite (lihat Keterbatasan), jadi ini menutup gap yang sempit, bukan memperbaiki yang rusak. Bentuk: `postgresql://user:sandi@host:port/db`. |
| `TIER_FREE_LIMIT` / `TIER_PRO_LIMIT` | Opsional | Kuota generate dokumen **per 30 hari per akun** menurut tier (billing). Default **0 = tanpa batas** / 100. Default nol DISENGAJA: kuota berbayar itu keputusan bisnis, dan default tak-nol menyalakan tembok di setiap instance yang memasang Supabase tanpa ada yang memutuskannya (tagihan sudah dijaga `RATE_LIMIT_*`, yang menjawab pertanyaan berbeda). Kuota habis = **402** + ajakan upgrade. Job yang gagal SEBELUM LLM dipanggil tidak memotong kuota. Cuma berlaku kalau `SUPABASE_URL` diisi. |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRO_PRICE_ID` | Opsional | Pembayaran langganan Pro. **Kosong = pembayaran mati**: tombol upgrade jalan mode SIMULASI yang menyatakan apa adanya bahwa tier tidak berubah. Tier hanya bisa naik lewat **webhook Stripe ber-signature sah** — tidak ada jalan lain. `STRIPE_SECRET_KEY` terisi tanpa `STRIPE_PRO_PRICE_ID` ditolak berisik (bukan jadi error parameter Stripe yang menyesatkan). |
| `FRONTEND_URL` | Opsional | Asal URL untuk success/cancel Stripe Checkout. Kosong = `http://localhost:5173`. |
| `SENTRY_DSN` / `SENTRY_ENVIRONMENT` | Opsional | **Error tracking (#14).** Kosong = mati; `sentry-sdk` tak pernah di-import. Terisi = exception job (jalur 500/502 + sebab tak dikenal) dikirim ke Sentry dengan tag `job_id`/`owner`/`stage`. Kegagalan sisi input pengguna (422/413/400) TIDAK dikirim (bukan bug, cuma derau). DSN terisi tapi paket tak terpasang = peringatan sekali, bukan crash boot. |
| `LOG_FORMAT` / `LOG_LEVEL` | Opsional | **Structured logging (#14).** `LOG_FORMAT=json` = satu objek JSON per baris dengan `job_id`/`owner`/`stage` + field metrik (`duration_ms`/`outcome`/`error_status`), siap diagregasi collector. Kosong/nilai lain = plain (enak dibaca saat dev). `LOG_LEVEL` default `INFO`. |
| `CORS_ALLOW_ORIGINS` | Opsional | **CORS diperketat (#15).** Daftar origin (koma-pisah) yang boleh memanggil API lintas-origin. Kosong = default origin dev Vite (`localhost:5173`) — sudah BUKAN `*`. `*` = izinkan semua (opt-in eksplisit). Saat SPA disajikan same-origin oleh container, CORS tak terpakai sama sekali. `DOMAIN`/`TLS_EMAIL` (reverse proxy Caddy) dibaca `docker-compose.prod.yml`, BUKAN aplikasi — lihat `DEPLOY.md`. |

## Setup Lokal

```bash
# 1. Buat & aktifkan virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# atau: source venv/bin/activate   # macOS/Linux

# 2. Install dependency Python
pip install -r requirements.txt

# Punya venv dari SEBELUM migrasi Claude (2026-07-15)? Wajib jalankan ulang
# perintah di atas. venv lama tidak punya `anthropic`, dan gejalanya bukan
# test gagal — pytest langsung mati saat collect dengan
# `ModuleNotFoundError: No module named 'anthropic'`, yang gampang disalahartikan
# sebagai migrasinya yang rusak. Paket lama (langchain*, google-genai) juga masih
# menempel dan sudah tidak dipakai; aman dibuang.

# 3. Pandoc wajib ada di sistem untuk fitur export .docx
#    (kalau belum ada, jalankan sekali):
python -c "import pypandoc; pypandoc.download_pandoc()"

# 3b. Diagram dirender LOKAL oleh PlantUML — butuh Java 17+ di PATH, dan
#     plantuml.jar (unduh sekali dari github.com/plantuml/plantuml/releases,
#     asset plantuml-<versi>.jar, simpan sebagai tools/plantuml.jar)

# 4. Isi .env (copy dari .env.example, isi ANTHROPIC_API_KEY minimal)
cp .env.example .env

# 5. Install dependency frontend
cd frontend
npm install
cd ..
```

## Menjalankan Aplikasi

```bash
# Backend (dari root project)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# -> Swagger UI: http://127.0.0.1:8000/docs

# Frontend (terminal terpisah)
cd frontend
npm run dev
# -> http://127.0.0.1:5173
```

URL backend frontend dibaca dari `VITE_API_BASE_URL` (taruh di `frontend/.env.local`), fallback `http://localhost:8000` — sejak audit 2026-07-16; sebelumnya hardcoded.

### Daftar Endpoint

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/health` | Liveness: proses hidup & menjawab. Sengaja TANPA cek dependency (orchestrator memakainya untuk memutuskan restart) |
| `GET` | `/ready` | **Readiness (#14):** proses bisa MENGERJAKAN pekerjaannya — cek DB + pandoc + Java + plantuml.jar. **200** kalau semua ada, **503** kalau satu saja hilang (sinyal orchestrator jangan kirim trafik). Body memuat status per-dependency |
| `POST` | `/ingest/github` | Ingest repo dari GitHub (OAuth token atau PAT) -> `Workspace` |
| `POST` | `/ingest/zip` | Ingest repo dari file ZIP yang di-upload -> `Workspace` |
| `GET` | `/auth/github/login` | Mulai flow OAuth GitHub (scaffold, belum bisa dipakai sungguhan — lihat Keterbatasan) |
| `GET` | `/auth/github/callback` | Callback OAuth GitHub |
| `POST` | `/documents/sdd` | Terima `DocumentContent` (Contract B) langsung, render jadi SDD `.docx` — untuk testing template tanpa perlu ingest+LLM. **Tidak menerima `document_metadata`** (body-nya murni Contract B); dokumennya keluar dengan penanda `(diisi manual)` |
| `POST` | `/documents/uat` | Sama seperti di atas, untuk UAT `.docx` |
| `POST` | `/documents/generate` | **Endpoint utama, ASYNC.** Balik **202** + `{job_id, status_url}` dalam ~50ms; pipeline penuh (ingest -> parse -> LLM -> compile) jalan di latar belakang. Sumber kode: `repositories` (GitHub) **ATAU** `zip_files` (upload ZIP base64 — kalau ada, ZIP yang dipakai; base64 rusak = 422 sinkron; sejak 2026-07-20). Satu-satunya yang menerima `document_metadata` (isian form, opsional — lihat `DocumentMetadata`) dan `logo_base64` (logo perusahaan → header tiap halaman; divalidasi SINKRON, file rusak = 422 sebelum job dibuat), plus `template_id` ("default"/"premco", ATAU id hasil upload lewat `POST /templates` — kombinasi tak tersedia = 422 sinkron). **Dibatasi rate limit per-akun**: kuota habis = **429** + header `Retry-After`, tanpa job berbayar baru. **Dan dibatasi kuota tier** (kalau `TIER_FREE_LIMIT` diisi): jatah 30-harian habis = **402** + `detail` berbentuk objek (`message`/`upgrade_required`/`used`/`limit`), juga tanpa job berbayar baru. Dua batas berbeda: 429 = terlalu cepat, 402 = jatahnya memang habis |
| `GET` | `/documents/jobs/{job_id}` | Status job: `queued`/`running`/`done`/`failed`. **200 walau job-nya gagal** — kegagalannya ada di payload (`error` + `error_status`), karena pertanyaannya sendiri berhasil dijawab |
| `GET` | `/documents/jobs/{job_id}/download` | Unduh `.docx` hasil. **409** kalau job belum selesai (bukan 404 — job-nya ada, cuma belum siap) |
| `GET` | `/documents/jobs/{job_id}/diagrams` | Unduh ZIP berisi `.drawio` activity diagram dokumen ini (versi yang bisa DISUNTING, lahir dari geometri yang sama dengan gambar cetaknya). **404** kalau dokumennya memang tak punya activity diagram — status job cuma mengumumkan `diagrams_url` kalau bundelnya nyata |
| `POST` | `/templates` | **V2 — upload `.docx` template user.** Multipart (`file`, opsional `name`/`doc_types`/`use_llm_mapping`). **SINKRON**: ukur → peta bab (heuristik $0 DEFAULT; `use_llm_mapping=true` = peta LLM BERBAYAR, satu panggilan Claude per doc_type) → generate template Jinja + sintesis reference.docx → simpan+daftar di `data/templates/<id>/`. Balik **201** + `{manifest, mappings}` (rencana peta bab untuk ditinjau). `.doc`/non-docx/rusak = 422; kebesaran = 413; **kuota per-akun habis = 429** + `Retry-After`. `template_id` hasilnya langsung bisa dipakai di `/documents/generate`. Manifest menyimpan `owner` = pemanggil → template ini **hanya terlihat & terpakai olehnya** |
| `GET` | `/templates` | Semua template (built-in + hasil-upload **milik pemanggil**) dengan `doc_types`/`source`/`name` — untuk mengisi dropdown gaya dokumen di frontend (menghormati ketersediaan per jenis dokumen) |
| `GET` | `/templates/{id}` | Detail template terkompilasi: manifest + rencana peta bab (untuk UI tinjauan). **404** kalau bukan template hasil-upload **atau milik pengguna lain** (pesannya sama persis — jangan bocorkan keberadaannya) |
| `GET` | `/templates/bindings` | Pilihan isi yang boleh dipasang ke sebuah bab — sumber kebenaran dropdown UI tinjauan. Dideklarasikan SEBELUM `/{template_id}` supaya path parameter tak menelannya |
| `PUT` | `/templates/{id}/mappings/{doc_type}` | **Simpan peta bab hasil tinjauan manusia** → generate ulang template Jinja. Body: `{bindings: [...]}` PARALEL dengan peta tersimpan (cuma binding — struktur bab hasil pengukuran, bukan pendapat). **404** template/doc_type tak ada **atau milik pengguna lain**; **422** jumlah tak cocok / binding tak dikenal / satu isi dipakai dua bab |
| `GET` | `/billing/usage` | Ringkasan kuota & pemakaian LLM pemanggil dalam 30 hari: `tier`, `limit`, `jobs_used`, `remaining`, `total_tokens`, `total_cost_usd`. Biayanya **estimasi berdasarkan harga daftar** model yang dipakai (`LLM_MODEL`) — plafon, bukan tagihan |
| `POST` | `/billing/checkout` | Mulai upgrade ke Pro lewat Stripe Checkout → `{checkout_url, session_id, is_stub}`. **`is_stub: true` = Stripe belum dikonfigurasi**: tak ada pembayaran & tier TIDAK berubah, dan klien WAJIB mengatakannya apa adanya. **500** kalau env Stripe setengah terisi (pesan menyebut env-nya), **502** kalau Stripe sendiri yang gagal |
| `GET` | `/me/export` | **Unduh SELURUH data akun** sebagai ZIP: `data.json` (riwayat job, langganan, catatan pemakaian, manifest template) + berkas `.docx` yang masih tersimpan + bundel `.drawio` + template hasil upload + `BACA-SAYA.txt`. **409** kalau auth mati (`SUPABASE_URL` kosong) — di sana semua pemanggil satu identitas anonim yang sama, jadi "data saya" tak punya arti |
| `DELETE` | `/me/data` | **Hapus seluruh data akun.** Job + docx + bundel diagram + template dihapus; `user_subscriptions` dihapus; `usage_records` **owner-nya dianonimkan** (bukan dihapus — catatan biaya). Balik ringkasan berangka, bukan 204: "0 dokumen dihapus" harus terlihat. **409** kalau auth mati (kalau tidak, satu permintaan akan mengosongkan seluruh instance) |
| `GET` | `/privacy` / `/terms` | Halaman Kebijakan Privasi & Syarat-Ketentuan (HTML statis di `app/legal/`). **Publik, sengaja tanpa auth.** Spanduk "draf" muncul OTOMATIS selama masih ada penanda `[ISI: ...]` yang belum diganti, dan hilang sendiri saat penanda terakhir diisi |
| `POST` | `/billing/webhook` | Webhook Stripe — **satu-satunya jalur yang boleh menaikkan/menurunkan tier**. Tanpa auth (memang tak boleh, pemanggilnya Stripe), tapi payload **wajib lolos verifikasi signature** (`stripe.Webhook.construct_event`); tanpa `STRIPE_WEBHOOK_SECRET` semua event ditolak, bukan diterima diam-diam. **400** signature tak sah / header hilang |

## Testing

```bash
pytest
```

441 test, **selalu mock** pemanggilan LLM (Claude — termasuk pemeta bab LLM di boundary `_request_bindings`), proses plantuml.jar, dan GitHub — supaya test tidak bergantung pada koneksi internet, Java/jar terpasang, API key, atau kuota, dan tidak pernah mengeluarkan biaya API secara tidak sengaja. (Pengecualian sadar: test V2 template — `test_build_reference_docx`, `test_template_compiler_service`, `test_routes_template` — memakai pandoc ASLI untuk mensintesis/merender reference.docx; itu deterministik & $0, tak keluar ke jaringan.)
427 test, **selalu mock** pemanggilan LLM (Claude — termasuk pemeta bab LLM di boundary `_request_bindings`), proses plantuml.jar, dan GitHub — supaya test tidak bergantung pada koneksi internet, Java/jar terpasang, API key, atau kuota, dan tidak pernah mengeluarkan biaya API secara tidak sengaja. (Pengecualian sadar: test V2 template — `test_build_reference_docx`, `test_template_compiler_service`, `test_routes_template` — memakai pandoc ASLI untuk mensintesis/merender reference.docx; itu deterministik & $0, tak keluar ke jaringan.)

**Cara MEMBUKTIKAN klaim "selalu mock" itu, dan kenapa perlu:**

```bash
ANTHROPIC_API_KEY=sk-ant-palsu pytest    # tetap hijau = nol panggilan berbayar
```

Klaim itu pernah SALAH tanpa ada yang tahu. Tiga test (`test_mode_dev_tanpa_supabase_tak_butuh_login`, `test_dokumen_terisolasi_antar_pengguna`, `test_list_jobs_owner_scoped_dan_terbaru_dulu` — dua dari kerja auth, satu dari "Dokumen Saya") memanggil `_generate` tanpa mem-patch `generate_document_content`, jadi tiap `pytest` penuh benar-benar membayar Claude. Ditemukan & ditutup 2026-07-28 lanjutan 3. Kalimat "selalu mock" di atas selama itu diperiksa lewat **proksi** — kebiasaan menulis test — bukan lewat barangnya (prinsip #1 lagi, dan ini bentuknya yang paling mahal karena gejalanya bukan test merah, melainkan tagihan). Perintah satu baris di atas memeriksa barangnya; jalankan sebelum mengklaim ulang.

| File | Meng-cover |
|---|---|
| `tests/test_compiler_service.py` | Render PlantUML, Jinja2, export docx, metadata dokumen, halaman cover (judul dua tingkat + blok tanpa rupa tabel), template premco (bar biru SDD; header hijau + grouping per-modul + section landscape UAT) (Peran 3) |
| `tests/test_rate_limit_service.py` | Batas per-akun: jendela sliding, Retry-After, akun lain tak terpengaruh, mode dev dilewati, limit 0 mematikan, env salah-ketik menggagalkan startup |
| `tests/test_observability.py` | Observability #14: probe `/ready` (200 siap / 503 satu dep hilang), health tetap tanpa cek dep, JSON log membawa konteks job + field extra, seam Sentry mati by default = no-op yang tak melempar (Peran 3) |
| `tests/test_cors.py` | CORS diperketat #15: default bukan `*`, parsing `CORS_ALLOW_ORIGINS`, origin diizinkan dipantulkan, origin asing tidak (Peran 3) |
| `tests/test_job_queue.py` | Seam eksekusi (#13): default inline, mode RQ tak menyentuh `BackgroundTasks` (dua-duanya = pipeline berbayar jalan 2x), meta `job_id`, timeout selaras reaper, re-queue no-op/dimatikan, `mark_requeued` membersihkan sisa error |
| `tests/test_billing_service.py` | Metering token & tarif per model (id ber-tanggal, model tak dikenal), kuota tier (job gagal-sebelum-LLM tak memotong, gagal-sesudah-LLM memotong, job berjalan ikut, limit 0 tak membatasi), checkout simulasi tak menaikkan tier, price id kosong ditolak berisik, webhook Stripe menaikkan tier |
| `tests/test_routes_billing.py` | Endpoint `/billing/*` + penolakan **402** di `/documents/generate` saat kuota habis |
| `tests/test_user_data_service.py` | Ekspor & hapus data (#16): penjaga mode dev, sapuan LIMA penyimpanan, data pengguna lain selamat, template tanpa owner tak ikut, usage dianonimkan bukan dihapus. Tiap test hapus memeriksa **barangnya** lewat `residual_data`, bukan nilai kembalian fungsinya |
| `tests/test_routes_account.py` | Boundary `/me/*`: 409 mode dev, 401 tanpa token, ekspor tak membocorkan data pengguna lain |
| `tests/test_routes_legal.py` | `/privacy` & `/terms` tersaji, terbuka tanpa login, spanduk draf mengikuti isi dokumen |
| `tests/test_cors_config.py` | CORS dari env (#15): default bukan `*`, garis miring ujung dipangkas, `main.py` memakai config bukan hardcode |
| `tests/test_routes_document.py` | Endpoint `/documents/*` (Peran 3) |
| `tests/test_routes_ingestion.py` | Endpoint `/ingest/zip`: multipart, pemasangan file↔tag, error 422 (Peran 1) |
| `tests/test_github_provider.py` | Ingest lewat tarball, pakai tarball sintetis di memori (Peran 1) |
| `tests/test_filters.py` | File mana yang relevan; termasuk penjaga anti-rakus (Peran 1) |
| `tests/test_manifest.py` | Deteksi produk, pakai manifest asli fastapi/flask/requests/express/medusa/cal.com (Peran 1) |
| `tests/test_llm_service.py` | Guard context window & deteksi dokumen terpotong; tolak sebelum membayar (Peran 2) |
| `tests/test_parser_endpoints.py` | Deteksi endpoint Python: Flask (`@bp.route`, `url_prefix` Blueprint) & FastAPI (Peran 1) |
| `tests/test_parser_java.py` | Parser Java: endpoint Spring MVC (termasuk prefix class), interface, Javadoc, import (Peran 1) |
| `tests/test_parser_app_router.py` | Deteksi endpoint Next.js App Router: `route.ts` named export + path dari struktur folder (Peran 1) |

**`parser_service.py` ter-cover di bagian deteksi endpoint Python (18 test), seluruh jalur Java (19 test), dan endpoint Next.js App Router (16 test)** — bagian yang paling baru diubah dan paling mahal kalau salah. Ekstraksi class/function Python/TS, heuristik `type`, dan deteksi endpoint Express-style masih tanpa test khusus — lihat Keterbatasan.

### Validasi ke repo publik (`scripts/validation/`)

Ini **bukan pengganti `pytest`** dan menjawab pertanyaan yang berbeda:

| | `pytest` | `scripts/validation/` |
|---|---|---|
| Menjawab | "kode sesuai rancangan?" | "rancangan bertahan di repo asing?" |
| LLM & Mermaid | di-mock | sungguhan |
| Biaya | gratis | GitHub API + (opsional) Claude berbayar |

Buktinya keduanya perlu: bug `414` mermaid.ink lolos dari 11 test yang semuanya hijau, justru karena mermaid.ink di-mock.

```bash
python scripts/validation/run_validation.py --list        # daftar kasus
python scripts/validation/run_validation.py               # Tahap 1: ingest+parse, GRATIS
python scripts/validation/run_validation.py --only flask --with-llm   # Tahap 2: BERBAYAR
```

**Tahap 1 gratis** (tanpa LLM) sudah cukup menjawab "parser paham repo ini?" — Contract A-nya disimpan ke `out/` supaya Tahap 2 tidak perlu ingest ulang. **Tahap 2 berbayar**: satu kasus = satu panggilan Claude, wajib opt-in. Baca `scripts/validation/README.md` sebelum menjalankan yang berbayar.

### Regresi visual tanpa kuota API (`scripts/render_fixtures.py`)

**Satu-satunya langkah berbayar adalah Contract A → Contract B.** Begitu Contract B
tersimpan, seluruh sisa pipeline (template → diagram → docx) bisa diulang berapa
kali pun **$0**. Artinya: kuota API habis TIDAK memblokir pekerjaan Peran 3
(templating, tabel, diagram, pagination, cover) — semuanya tetap bisa dikerjakan
DAN diverifikasi.

```bash
python scripts/render_fixtures.py              # semua fixture x semua template
python scripts/render_fixtures.py --out hasil/ # simpan docx-nya untuk dibuka
```

Fixture datang dari `dummy_data/*.json` (ikut repo) dan `scripts/validation/out/`
(hasil run berbayar lampau, **gitignored** — bisa hilang). Karena itu dua Contract B
terkaya disalin ke repo: `dummy_data/contract_b_rich_sdd.json` (esteler, 11 fitur /
7 use case / 7 activity diagram) dan `contract_b_rich_uat.json` (MyPertamina, **50
test case**). Keduanya penting justru karena `document_content_sdd.json` cuma punya
1 fitur/1 use case — kepadatan setipis itu BUTA terhadap bug tata letak (bug
"halaman berisi 4 baris lalu 8 inci putih" cuma muncul pada kepadatan nyata).

Contract B dari **sebelum 2026-07-16** (migrasi Mermaid → PlantUML) tidak lagi
kompatibel; script melaporkannya `SKEMA-LAMA` dan menghitungnya terpisah dari
kegagalan — supaya exit code tetap bermakna.

Untuk testing manual end-to-end (hit API sungguhan, termasuk panggilan LLM yang sesungguhnya) — **lakukan ini hanya saat memang sedang sengaja menguji**, jangan jadikan kebiasaan default karena memakai kuota API berbayar:
- `dummy_data/document_content_sdd.json` / `document_content_uat.json` — contoh `DocumentContent` (Contract B) siap pakai untuk `POST /documents/sdd` / `/documents/uat` langsung (tanpa LLM).
- `dummy_data/parsed_repo_context_sample.json` — contoh `ParsedRepoContext` (Contract A) sintetis (aplikasi task-manager kecil, 2 repo: Backend + FE-Web) untuk diumpankan ke `LLMService.generate_document_content(...)` secara manual, kalau ingin menguji kualitas output LLM tanpa perlu ingest dari GitHub sungguhan.

## Keterbatasan yang Diketahui

- **Endpoint Django belum terdeteksi** (Flask **sudah** sejak 2026-07-16, lihat Riwayat). Django menaruh route di `urls.py` lewat `path()` — bukan decorator sama sekali, jadi `_python_endpoints_from_decorator` tidak bisa melihatnya; perlu jalur pengenalan tersendiri. Terukur: **saleor** 0 endpoint dari 2.573 file. **Sengaja belum dikerjakan**, dan alasannya penting: satu-satunya kasus Django yang kita punya (saleor) tetap terhalang guard context window (1,2 juta token), jadi perbaikannya **tidak bisa dibuktikan end-to-end** — kita cuma akan mengirim kode yang tidak terverifikasi. Butuh aplikasi Django yang lebih kecil di `repos.json` dulu.
- **Next.js App Router SUDAH terdeteksi (2026-07-18); yang tersisa: Nuxt `server/api` + Next.js Pages Router.** App Router (`app/api/**/route.ts`, named export `GET/POST/...`) kini didukung — `_ts_app_router_endpoints` + `_app_router_path`, terukur taxonomy 0→8 endpoint (lihat Riwayat). **Belum**: (1) **Nuxt server routes** `server/api/*.ts` lewat `defineEventHandler` (method dari akhiran nama file: `users.get.ts`→GET, atau `[id].ts`→semua method); (2) **Next.js Pages Router** `pages/api/**` lewat `export default function handler(req,res)` — SATU handler untuk SEMUA method (method dicek runtime via `req.method`), jadi method-nya **tak bisa ditentukan statis** (taxonomy punya satu: `pages/api/auth/[...nextauth].ts`). Keduanya lebih jarang dari App Router di repo baru. **Dampak ketiadaan ini RINGAN & terbukti**: taxonomy sebelum fix (0 endpoint) tetap menghasilkan dokumen berjejak dengan diagram integrasi benar (LLM menyimpulkan dari nama file/fungsi) — jadi ini penurun kualitas potensial, bukan blocker.
- **`url_prefix` Blueprint Flask lewat `register_blueprint()` belum ditangani** (bentuk konstruktor **sudah**, sejak 2026-07-16 — lihat Riwayat). Flask punya dua tempat menaruh prefix, dan yang didukung baru satu: `Blueprint("admin", __name__, url_prefix="/admin")` (di file yang sama dengan route-nya) jalan; `app.register_blueprint(admin_bp, url_prefix="/admin")` (di file lain) **tidak** — path-nya keluar tanpa prefix, seperti perilaku lama. Kalau keduanya ada, Flask memenangkan yang di `register_blueprint`, jadi kita bisa salah di kasus itu. **Sengaja belum dikerjakan, alasannya sama dengan Django**: satu-satunya aplikasi Flask nyata yang kita punya (esteler) memakai bentuk konstruktor, jadi jalur lintas-file **tidak bisa dibuktikan ke repo asli** — kita cuma akan mengirim kode yang tidak terverifikasi, dan menebak prefix yang salah menaruh endpoint di URL yang tidak ada (lebih buruk daripada path kurang lengkap). Menyelesaikannya butuh resolusi impor lintas-file (`from routes.admin import admin_bp as x` → cocokkan `x` balik ke file & variabel aslinya). Butuh aplikasi Flask bergaya itu di `repos.json` dulu.
- **Parser paham Python, TS/JS/TSX, dan Java** (Java sejak 2026-07-16) — bahasa lain perlu ditambahkan kalau dibutuhkan (fallback saat ini: entry `"type": "other"` minimal, tanpa detail class/function/endpoint). Terukur pada **gin-go: 59 file, 0 class, 0 endpoint, Contract A 7,9 KB** — itu ukuran lubang Go, dan bentuknya sama persis dengan Java sebelum didukung. **TAPI — guardrail prioritas (temuan A/B 2026-07-18, jangan diabaikan diam-diam): menambah bahasa/presisi parser kemungkinan besar MARGINAL untuk kualitas dokumen.** A/B taxonomy membuktikan LLM sudah pandai menyimpulkan struktur dari nama file — endpoint eksplisit dari parser cuma menggeser dokumen sedikit (lihat Riwayat). Nilai jual produk = KUALITAS DOKUMEN, dan parser breadth sudah lewat titik hasil-menurun untuk itu. Menambah Go/Kotlin/dst. itu kerja NYAMAN (centang hijau, bisa dari repo saja), bukan kerja BERHARGA — kerjakan hanya kalau ada repo target NYATA yang membutuhkannya, bukan demi kelengkapan. Pekerjaan bernilai-tinggi berikutnya justru terhalang input eksternal (dokumen UAT & template sumber lain) atau ada di tepi deployment (job reaper, jalur ZIP, OAuth), bukan di parser.
- **Repo Java enterprise besar belum pernah diuji — dukungan Java baru terbukti di satu sample app 33 file.** `spring-petclinic` menghasilkan 17 endpoint yang semuanya benar **dan dokumen yang seluruh isinya berjejak** (lihat Riwayat), tapi dia aplikasi contoh, bukan aplikasi bisnis sungguhan. Dua hal yang belum terjawab: (1) **ukuran** — densitas Java terukur **0,64 KB/file**, sebanding saleor (0,81 KB/file, muat di 85%), jadi ekstrapolasi ke ~2.500 file memberi ~677K token (68%, muat); tapi petclinic nyaris tanpa Javadoc, dan repo enterprise ber-Javadoc padat bisa naik ke ~2 KB/file (seperti fastapi) yang berarti ~2,1 juta token — **tidak muat**. Ini ekstrapolasi, bukan bukti. (2) **`@RequestMapping` tanpa `method=`** diaproksimasi GET (lihat komentar di `_java_endpoints_from_annotations`); petclinic memakai `@GetMapping`/`@PostMapping` eksplisit di semua handler-nya, jadi cabang itu belum tersentuh repo nyata — butuh repo Spring bergaya lama. Keduanya butuh kasus uji Java yang lebih besar di `repos.json`.
- **Monorepo besar tetap tidak muat; menyaring TIDAK akan menolong** (diukur 2026-07-16 dalam token, bukan KB). medusa sesudah `workspaces` + compact: **1.253.878 token = 125% context window** → tetap ditolak `_guard_context_window`. Yang tersisa **memang kode produk**, jadi tidak ada lagi yang bisa dibuang tanpa membuang barang asli. Diukur per-field: `api_endpoints` cuma **0,1%** (membuangnya sia-sia), sementara yang mahal justru `classes` (21%) dan `dependencies` (23%) — dua-duanya bahan baku dokumen. Bahkan membuang `classes`+`functions` sekaligus cuma turun ke **97%** — terlalu mepet, bukan solusi. **Masalahnya arsitektur: produk ini mengirim SELURUH Contract A dalam SATU panggilan.** Arah yang mungkin (belum diputuskan): pecah per-workspace-package lalu gabungkan; ringkas dulu pakai model murah; atau kirim struktur tanpa detail. **Catatan urutan prioritas — klaim lama di sini sudah GUGUR.** Dulu tertulis *"memperbaiki dukungan Java/.NET tidak ada gunanya sebelum ini beres, repo enterprise justru yang paling besar"*. Itu ditulis waktu saleor juga tidak muat; sesudah compact, saleor MUAT (85%), jadi yang tersisa tidak muat cuma **monorepo raksasa** — kasus yang jauh lebih sempit dari "repo enterprise". Java dikerjakan 2026-07-16 tanpa menunggu chunking, dan densitasnya terukur **0,64 KB/file** — lebih ringan dari saleor, bukan lebih berat. Pelajarannya: klaim itu adalah **tebakan tentang ukuran yang tidak pernah diukur**, dan dia menahan pekerjaan yang ternyata tidak terhalang.
- **Ukuran diagram dibatasi ukuran HURUF di dalamnya, bukan oleh ruang halaman** (aturan `_image_attr`, ditetapkan 2026-07-21 menggantikan aturan lama "jangan pernah upscale"). Diagram dibesarkan sampai `_DIAGRAM_TARGET_WIDTH_FRAC` (80% lebar area teks), TAPI pembesarannya dibatasi dua ambang terukur: huruf di dalam diagram tak boleh lewat 12,5pt (teks badan 11pt — diagram berhuruf lebih besar dari badan terbaca seperti poster) dan kerapatan efektif tak boleh turun di bawah 150 dpi. **Konsekuensi yang disengaja**: diagram yang secara STRUKTUR sederhana (use case 1 aktor 2 oval) berhenti di ~60% dan memang tidak akan mencapai target — lebar dan ukuran huruf terkunci satu sama lain karena PlantUML membesarkan keduanya bersamaan. Satu-satunya cara memutus kuncian itu adalah membuat diagramnya lebih kaya (mis. swimlane seperti acuan), dan itu urusan prompt LLM, bukan renderer. **Jangan naikkan target tanpa menaikkan `_DIAGRAM_MAX_TEXT_PT`** — targetnya tidak akan tercapai, cuma batasnya yang menggigit lebih sering.
- **Diagram `system_architecture` menambahkan komponen yang tidak punya jejak di kode** (ditemukan 2026-07-15 lewat Tahap 2, **belum diperbaiki**). Contract A fastapi punya **nol** dependency database (tidak ada sqlalchemy/sqlmodel/psycopg2 — sudah dicek), tapi diagramnya tetap menggambar `Backend --> Database`. FastAPI itu framework yang sengaja tidak punya lapisan database; kotak itu muncul dari kekosongan. Kelas kesalahannya berbeda dari kasus "Hero": di sana LLM membaca kode nyata tapi kode yang salah (tutorial); di sini tidak ada kode apa pun yang mendasarinya. **Penting — jangan salah baca ini sebagai "diagramnya cuma template".** Dugaan awal itu terbantah oleh realworld pada hari yang sama: di sana diagramnya menulis `Database (PostgreSQL via Prisma)`, dan `prisma` memang benar-benar ada 4x di `dependencies`-nya. Jadi LLM **memang** menurunkan diagram dari kode; masalahnya cuma dia tidak berhenti ketika buktinya tidak ada. Dampaknya ringan untuk mayoritas repo target (aplikasi bisnis biasa memang punya database, jadi tebakannya kebetulan benar) — yang perlu diperbaiki: larang eksplisit menggambar komponen yang tidak punya jejak di `dependencies`. **Batasnya makin sempit, bukan makin lebar — fastapi masih SATU-SATUNYA kasus karangan yang terkonfirmasi.** Pada esteler-app (2026-07-16) diagramnya menulis `Groq`, `Cloudinary`, dan `Database PostgreSQL (Neon)`, dan **semuanya punya jejak**: `Groq` ×1 dan `cloudinary`/`cloudinary.uploader`/`CloudinaryError` dari `dependencies`, `SQLAlchemy` ×1 untuk Database, dan **"Neon" + "PostgreSQL" dari DOCSTRING** `config.py::_normalize_db_url()` ("Normalisasi DATABASE_URL agar selalu siap pakai untuk Neon. — postgres:// → postgresql:// ..."). **Catatan untuk siapa pun yang mengaudit karangan di kemudian hari: `dependencies` BUKAN satu-satunya bukti di Contract A.** `functions[].description` dan `classes[].methods[].description` membawa docstring, dan LLM memang membacanya — sesi ini sempat salah menuduh "Neon" sebagai karangan justru karena cuma menggeledah `dependencies`. Geledah seluruh Contract A (`json.dumps(ctx)`), bukan satu field. Yang perlu diperbaiki tetap sama: larang eksplisit menggambar komponen yang tidak punya jejak **di mana pun** di Contract A — **larangan itu SUDAH ditulis ke SYSTEM_PROMPT 2026-07-16** ("ATURAN BUKTI UNTUK DIAGRAM", ikut migrasi PlantUML), tapi efeknya **belum diverifikasi** ke kasus fastapi; kasus itu tetap terbuka sampai ada regen fastapi yang diagram-nya berhenti mengarang Database. **Diperkuat lagi oleh petclinic (2026-07-16, Java)**: diagramnya menggambar `Backend --> Database`, dan jejaknya kuat (`JpaRepository`, `Entity`×18, `Table`, `Column`, `ManyToOne`, `Transactional`) — begitu pula "Server-rendered Views" (`ModelAndView`, `WebMvcConfigurer`) dan "pergantian bahasa" (`LocaleResolver`, `LocaleChangeInterceptor`). Jadi **tiga repo berturut-turut** (realworld, esteler, petclinic) menggambar dari bukti, dan fastapi tetap SATU-SATUNYA karangan yang terkonfirmasi. Ini menaikkan dugaan bahwa pemicunya spesifik: fastapi itu *framework* yang sengaja tidak punya lapisan database, jadi kotak Database muncul justru dari **kekosongan** — bukan dari kebiasaan menggambar template.
- **Kualitas `claude-sonnet-5` vs `claude-opus-4-8` untuk tugas ini BELUM diuji.** Default dipindah ke Sonnet 5 pada 2026-07-15 atas keputusan pemilik project, alasannya biaya (Opus ~$1,36/dokumen untuk repo sebesar fastapi; tim menganggap $0,50 sudah mahal). Dasarnya reputasi umum Sonnet 5 yang mendekati Opus, **bukan** perbandingan langsung pada repo nyata — jadi ini asumsi, bukan temuan. Menguji ini murah dan berdampak lama: satu repo × dua model (~$1 sekali bayar) lalu **baca kedua dokumennya**. Kalau kualitasnya turun, ganti balik lewat `LLM_MODEL=claude-opus-4-8` di `.env` (tanpa sentuh kode). Ingat produk ini menjual kualitas dokumen — itu satu-satunya nilainya, jadi jangan biarkan asumsi ini menggantung terlalu lama.
- **Kontaminasi input jauh lebih berbahaya daripada label yang salah** (ditemukan 2026-07-15 lewat Tahap 2; **sudah diperbaiki** lewat deteksi manifest — lihat Riwayat Perubahan. Dicatat di sini karena pelajarannya masih berlaku untuk perubahan berikutnya). Terbukti lewat perbandingan langsung: **flask** (coverage 0%, semua file `"other"`) menghasilkan SDD yang **akurat** — "Flask adalah kerangka kerja pengembangan aplikasi web" dengan fitur Routing/Request-Response/Session/Template yang semuanya benar. Sebaliknya **fastapi** (coverage 63%) menghasilkan SDD yang **percaya diri tapi salah**: "Sistem ini adalah kumpulan aplikasi backend... mengelola data, otentikasi, unggah berkas", dengan fitur "Manajemen Item" dan "Manajemen Hero". FastAPI itu *framework*, dan "Hero" itu contoh dari tutorial SQLModel. Sebabnya: **456 dari 530 file (86%) berasal dari `docs_src/`** — folder tutorial dokumentasi — dan **seluruh 432 endpoint** berasal dari sana, sementara package `fastapi/` yang asli menyumbang **0 endpoint**. Ini kelas bug yang sama dengan `test/` pada express, tapi lewat pintu berbeda: `docs_src` tidak ada di blocklist. Menambahkan `docs_src` cuma menunda masalah — tiap repo mengarang konvensinya sendiri (`test/`, `examples/`, `docs_src/`, `website/`, `playground/`), jadi daftar nama tidak akan pernah lengkap. Arah yang lebih menjanjikan: **tanya repo-nya sendiri apa yang dia kirim** — `pyproject.toml`/`package.json` mendeklarasikan nama package-nya (fastapi menyatakan package-nya `fastapi`), jadi prioritaskan file di bawah situ alih-alih menebak-nebak folder mana yang bukan produk.
- **Heuristik `type` menebak dari nama file, dan gagal pada penamaan idiomatik Python/Go** (ditemukan 2026-07-15 lewat validasi, belum diperbaiki — tapi **prioritasnya rendah**, lihat butir di atas: flask dengan coverage 0% tetap menghasilkan dokumen akurat, jadi label ternyata bukan bottleneck-nya. LLM sanggup menyimpulkan peran file dari nama class, nama function, dan `dependencies` yang tetap dikirim di Contract A). `_guess_file_type()` di `parser_service.py:144` mencocokkan substring nama file (`"controller"`, `"service"`, `"model"`, ...) plus satu sinyal isi (`has_endpoints`). Konsekuensinya diukur pada repo **flask**: coverage **0%** — 25 file semuanya `"other"` — padahal parser sukses menarik 52 class dan 72 function dari repo yang sama. Jadi parsing-nya jalan, **pelabelannya** yang gagal: flask menamai file secara idiomatik (`app.py`, `helpers.py`, `wrappers.py`), bukan bergaya MVC Java/Spring (`UserController.java`). Artinya `coverage` tinggi selama ini menandakan "repo ini kebetulan pakai konvensi penamaan Java", bukan "parser paham repo ini". Diperparah karena yang dibaca cuma `file_name`, bukan path — file di `app/controllers/user.py` tetap `"other"` sebab nama filenya cuma `user.py`. Perbaikan yang mungkin (termurah dulu): (1) ikut membaca path, bukan cuma nama file; (2) tambah sinyal berbasis isi (ada import ORM? ada query SQL? ada render komponen?) seperti `has_endpoints` yang sudah terbukti jalan.
- **Validasi menyentuh 10 repo, tapi masih cuma 3 yang pernah benar-benar jadi dokumen** (flask, fastapi, realworld). Ditambah 2026-07-15: `saleor-django` (Django e-commerce), `medusa-monorepo` (monorepo TS), `esteler-flask` (aplikasi Flask milik anggota tim — satu-satunya kode yang tidak ditulis untuk dipamerkan). Tahap 1 jalan ke semuanya; **Tahap 2 ke aplikasi bisnis masih belum pernah berhasil** — saleor ditolak guard context window (1,2 juta token), medusa juga akan ditolak (Contract A 3,4 MB). **Butir ini sebagian besar sudah terlampaui** — hitungannya kini **7**: ditambah `esteler-flask` (aplikasi bisnis Python nyata pertama) dan `spring-petclinic` (Java, keduanya 2026-07-16), lalu **`MyPertamina.id-Clone` (Vue/JS/TS)** dan **`shadcn-ui/taxonomy` (Next.js/TSX, keduanya 2026-07-18 — lihat Riwayat)**. Pertanyaan lama *"kalau coverage rendah, apakah LLM mengarang dari nama file?"* **terjawab TIDAK untuk Java DAN TS/JS**: petclinic coverage 33% & MyPertamina 27%, dokumennya tetap berjejak seluruhnya; taxonomy malah coverage 77% tapi 0 endpoint (App Router tak terdeteksi) — dan dokumennya TETAP berjejak, menegaskan LLM menyimpulkan API dari nama file/fungsi. Yang tersisa: **saleor** (Django) sekarang MUAT (85%) tapi belum pernah dijalankan Tahap 2 — dan 0 endpoint-nya membuatnya kasus paling tajam yang tersedia untuk menguji karangan; **medusa** masih tidak muat; **gin-go** (Go) & repo Java **besar** belum tersentuh.
- ~~**Jalur ZIP → dokumen TIDAK PERNAH tersambung**~~ — **BACKEND SELESAI 2026-07-20** (lihat CHANGELOG). Dulu `POST /documents/generate` cuma menerima `repositories` GitHub, jadi ZIP bisa *dianalisis* (`/ingest/zip`) tapi tak bisa *jadi dokumen*. Sekarang `GenerateDocumentRequest` punya field **`zip_files`** (upload ZIP base64, pola sama dengan `logo_base64` — bukan multipart/endpoint terpisah, supaya menyatu dengan kontrak JSON yang ada): kalau diisi, ZIP jadi sumber kode lewat pipeline yang SAMA (ingest ZIP → parse → LLM → compile); kalau tidak, jatuh ke GitHub. base64 rusak = 422 sinkron; isi ZIP rusak/zip-bomb = 422 di job (lapisan ingestion). Diverifikasi: ingest+parse ZIP sintetis nyata mengekstrak class/function/endpoint benar; 2 test baru (happy path + bad-base64). **UI upload ZIP di frontend SELESAI 2026-07-21**: pemilih "Repo GitHub" vs "Upload file ZIP" di section Sumber Kode; tiap ZIP = satu repo dengan Tag + input file (dibaca base64 via FileReader, dikirim sebagai `zip_files`). Verifikasi $0: `vite build` + `oxlint` hijau, bentuk payload dicocokkan ke kontrak backend dua sisi (data-URL prefix ditoleransi `_decode_zip_files`). Belum dijalankan browser→generate penuh (memicu job LLM berbayar = gate pemilik). **Sisa (belum): base64-in-JSON membengkak ~33% untuk repo besar** — cukup untuk MVP (ada guard zip-bomb di ingestion), kalau perlu efisiensi nanti pindah ke multipart. Kelas pelajaran lama tetap berlaku: **klaim dulu ditulis dari desain, bukan dari memeriksa jalurnya ada.**
- **OAuth GitHub baru scaffold** — endpoint-nya ada tapi belum bisa dipakai sungguhan sampai ada GitHub OAuth App terdaftar (`GITHUB_CLIENT_ID`/`SECRET` belum diisi).
- **`parser_service.py` baru ter-cover sebagian** (Peran 1). `tests/test_parser_endpoints.py` (18 test) mengunci deteksi endpoint Python, `tests/test_parser_java.py` (19 test) mengunci seluruh jalur Java, dan `tests/test_parser_app_router.py` (16 test, 2026-07-18) mengunci endpoint Next.js App Router — bagian yang paling baru diubah dan paling mahal kalau salah. Yang masih kosong: ekstraksi class/function Python & TS, heuristik `type`, dan deteksi endpoint Express-style (`_ts_endpoint_from_call`). `ingestion_service.py` juga masih tanpa test; ingestion sendiri sudah sebagian ter-cover lewat `tests/test_github_provider.py` (jalur tarball, GitHub di-mock lewat tarball sintetis di memori).
- **Cross-repo dependency resolution (FE fetch call <-> BE endpoint) sepenuhnya didelegasikan ke instruksi prompt LLM**, bukan langkah pencocokan deterministik terpisah seperti di diagram arsitektur target (`Cross Repository Mapping` -> `Unified Context` sebelum masuk LLM). **Terbukti jalan** pada `realworld-fullstack` (2026-07-15 — lihat Riwayat Perubahan), jadi cukup untuk MVP. Tapi karena bersandar pada LLM, hasilnya **tidak dijamin deterministik**: belum diuji pada repo dengan pola pemanggilan API yang tidak lazim (mis. URL dirakit dinamis, atau lewat wrapper client berlapis), dan belum pernah dijalankan dua kali pada repo yang sama untuk melihat apakah pemetaannya konsisten.
- ~~**Render diagram lewat layanan hosted (`mermaid.ink`) + batas URL ~8KB-nya**~~ — **SELESAI 2026-07-16** lewat migrasi ke PlantUML lokal (lihat Riwayat): isi diagram tidak lagi meninggalkan mesin, batas panjang URL tidak ada lagi (input lewat stdin), dan larangan paralelisasi 503 mermaid.ink tidak berlaku (render lokal — belum diparalelkan, tapi kini boleh kalau dibutuhkan). Harga yang dibayar: dependency runtime baru — **Java 17+ dan plantuml.jar wajib ada di mesin** (gagal dengan `DiagramRenderError` yang menyebut cara pasangnya kalau tidak ada).
- **`LLMService` memakai timeout client 1500 detik (25 menit)** untuk mengantisipasi generation yang lama pada repo besar/kompleks (default SDK 10 menit terbukti kurang untuk repo nyata yang cukup besar saat diuji). Kalau generation tetap sering lambat di masa depan, pertimbangkan pindah ke `.stream()` daripada menaikkan timeout terus-menerus.
- ~~**Tabel Revision History keluar sebagai baris kosong**~~ — **BUKAN CACAT. Butir ini SALAH, dicoret 2026-07-16.** Tercatat sejak 2026-07-15 sebagai *"dua tabel kosong nongkrong di halaman pertama SDD"* yang katanya butuh keputusan produk. Begitu dokumen acuan benar-benar **dibaca** (87 halaman, PDF di `ref/benchmark/`, ada sejak hari pertama), halaman 2-nya ternyata: `DOCUMENT REVISION HISTORY` + header lima kolom, lalu **satu baris kosong**; `APPLICATION REVISION HISTORY` sama persis. **Output kita sudah identik dengan acuan.** Dokumen Solution Design yang baru dibuat memang belum punya riwayat revisi — tabel itu kolom isian manual untuk revisi *berikutnya*, dan mengisinya justru berarti sistem mengarang riwayat. Kekhawatiran lama (*"`Summary of Changes` tidak punya jawaban jujur untuk dokumen baru"*) ternyata **benar**, dan jawabannya: memang tidak diisi — persis yang sudah dilakukan. **Pelajarannya lebih berharga daripada butirnya**: ini dicap cacat dengan membandingkan output ke *gagasan tentang dokumen yang baik*, bukan ke dokumen acuan yang sudah ada di repo ini sejak awal. Pola "memeriksa proksi, bukan barangnya" lagi — dan proksinya kali ini **selera**. Sebelum menyebut sesuatu cacat, buka PDF-nya.
- ~~**Job yang sedang jalan hilang kalau prosesnya mati**~~ — **TERTUTUP 2026-07-29 lewat #13, TAPI hanya kalau `REDIS_URL` diisi.** Dengan worker queue, argumen job tersimpan di Redis dan `job_queue.requeue_abandoned()` MELANJUTKAN pekerjaan yang mati bersama worker-nya (dibuktikan end-to-end: worker di-SIGKILL di tengah jalan, worker baru menyelesaikannya sampai `done`). Dua batas yang tersisa dan sengaja diterima: **(1)** tanpa `REDIS_URL` (mode inline, default) perilakunya persis seperti butir lama di bawah — reaper memvonis, kerjanya hilang; **(2)** deteksinya menunggu lease RQ lewat (ambang yang sama dengan reaper, ~30 menit), jadi job dilanjutkan tapi **tidak seketika**. Paragraf berikut tetap berlaku apa adanya untuk mode inline:
- **Job yang sedang jalan hilang kalau prosesnya mati** (berlaku di **mode inline**; batas yang diketahui & diterima sejak async masuk, 2026-07-16; gejala "stuck `running` selamanya" DITUTUP 2026-07-21 lewat reaper, sisa lost-work belum). `BackgroundTasks` menjalankan job **di dalam proses yang menerima POST**, jadi kalau uvicorn di-restart (deploy, crash, OOM) saat job jalan, kerjanya hilang. **Reaper `job_store.reap_stale_jobs()` (2026-07-21)** kini memungut job `running`/`queued` yang tak di-update > 30 menit (ambang aman di atas timeout LLM 25 menit; `updated_at` disegarkan tiap `set_progress`, jadi job sehat tak terlihat basi) → ditandai `failed` dengan `error_status` **503** (sementara, boleh diulang — beda dari 413/500 permanen) + pesan jelas; dipanggil **saat startup** (proses baru membersihkan job basi proses lama; di `main.py` import-time, bukan startup hook — alasan sama dengan `init_db`) **+ lazy tiap GET status** (worker hidup memungut job basi worker mati). Jadi klien **tak lagi polling tanpa akhir** — dulu job tergantung di `running` selamanya. **Yang MASIH belum**: reaper cuma menandai gagal, TIDAK menjalankan ulang — kerja yang hilang tetap hilang (pengguna generate ulang). Re-queue butuh Redis + RQ yang menambah layanan yang harus hidup saat deploy — sengaja belum, penghalang aslinya (request digantung 191 detik lalu diputus proxy) sudah selesai dengan nol infrastruktur baru. **Multi-worker TIDAK termasuk masalah — sudah diukur, dan jalan** (lihat butir berikut). Catatan penting untuk deploy: **di platform serverless (Vercel/Lambda) `BackgroundTasks` tidak aman** — proses bisa dibekukan begitu response terkirim, jadi job-nya mati di tengah jalan (reaper tetap memungutnya di invocation berikutnya, tapi kerjanya tetap hilang). Butuh worker sungguhan di sana. (esteler-app milik anggota tim ada di Vercel — kalau generator ini ikut ke sana, ini penghalangnya.)
- **Multi-worker JALAN — jangan percaya klaim sebaliknya** (diukur 2026-07-16 di server hidup: `uvicorn --workers 3`, 50 GET lintas worker → **0 kali 404**; 30 POST bersamaan → **30 sukses, 0 gagal**, 35 job tercatat utuh, tanpa `database is locked`). Ini dicatat karena CLAUDE.md sempat mengklaim sebaliknya, dan klaim itu **salah**: ditulis dengan mencocokkan pola kegagalan klasik `BackgroundTasks` (state disimpan di `dict` Python di memori → worker lain tidak bisa melihatnya → polling 404 acak) padahal produk ini **tidak begitu**. State-nya di SQLite, file di disk yang dibaca semua proses — itu sebabnya lintas-worker justru bekerja. **Pelajarannya: state di luar proses adalah yang membuat multi-worker mungkin, bukan mekanisme antriannya.** Pelajaran itu DIPAKAI 2026-07-28 saat rate limit dibangun: kuota dihitung dari tabel `jobs` & manifest template, bukan dari dict di memori — penghitung in-memory akan memberi tiap worker kuotanya sendiri dan diam-diam mengubah "10/jam" jadi 30/jam. Yang belum diuji: banyak job PANJANG (~3 menit) berbarengan — job uji di atas gagal cepat di ingest, jadi tidak menahan thread lama. Kalau nanti diuji, batas yang lebih dulu tersentuh kemungkinan besar rate limit Anthropic, bukan worker-nya.
- ~~**Dokumen tidak pernah dibersihkan**~~ — **SELESAI 2026-07-21.** `data/documents/` dulu tumbuh selamanya (satu docx ~700 KB). Sekarang `job_store.purge_expired_documents()` menghapus docx yang lebih tua dari `DOCUMENT_TTL_SECONDS` (30 hari) lalu MELEPAS `docx_path`-nya di DB — DB tak boleh menunjuk ke file yang tak ada, aturan yang sama dengan `mark_done` tapi arah sebaliknya. Job-nya sendiri TIDAK dihapus (riwayat tetap berguna); statusnya jadi `failed` + `error_status` **410 Gone**, supaya unduh punya jawaban jujur "dulu ada, sudah dibersihkan" alih-alih 404 ("id salah"). Dipanggil di titik yang sama dengan reaper: startup + lazy tiap GET status — nol scheduler.
- ~~**Frontend masih form dasar tanpa penjelasan**~~ — **selesai 2026-07-16, dua tahap.** Tiap field kini menjelaskan dirinya (tiap klaim hint diverifikasi ke kode dulu), lalu di-redesign: bahasa visual dokumen (kertas/tinta/biru-dokumen, section bernomor seperti bab SDD), dan area status jadi log tahapan bercentang yang murni dari data server (tanpa mencocokkan string). Yang masih benar dari butir lama: prinsip non-teknis di *isi dokumen* datang dari system prompt LLM, bukan UI.
- ~~**Template `default` CRASH pada repo Nuxt/Next**~~ — **SELESAI 2026-07-18** (lihat Riwayat). Nama file dynamic-route (`[category]/[slug].vue`) merusak sintaks komponen PlantUML `[...]`; sekarang `_sanitize_route_param_brackets` di `_normalize_plantuml` melepas kurung route-param sebelum plantuml.jar, jadi diagram TETAP dirender (bukan placeholder) dan default tak lagi crash. Diverifikasi visual pada component_integration MyPertamina: pemetaan FE↔BE lengkap & benar. Batas yang tersisa & diterima: kalau LLM menghasilkan PlantUML rusak lewat jalur LAIN (bukan kurung route-param), diagram yang DIPAKAI template masih gagal-berisik — belum ada resiliensi per-diagram (placeholder), dan itu keputusan sadar (menjaga filosofi gagal-berisik). Repo Kotlin (Android PREMCO) tetap lemah — parser tak mendukungnya (lihat butir bahasa).
- **Template upload (V2): STRUKTUR sudah tahan template berantakan, PEMETAAN masih butuh manusia — dan itu memang batasnya.** Sejak 2026-07-22 `_extract_outline` memindai judul bab di **text box tanpa style** dan judul bernomor manual, bukan cuma style `Heading N` — sebelumnya template yang menaruh bab di text box kehilangan bab-bab itu **tanpa satu pun pesan** (terukur: 7 dari 36 bab hilang senyap). Yang **sengaja tidak** dipindai, diukur pada 4 template nyata bukan ditebak: sel tabel (nol judul asli; satu-satunya yang "mirip judul" justru false positive `18 March 2021`) dan `w:outlineLvl` (nol pemakaian — sinyal sah menurut spec Word tapi tak bisa dibuktikan jalan di template mana pun yang kita punya; jangan tambahkan tanpa kasus uji). **Yang MASIH terbuka**: (1) wadah lain yang belum ketemu di template kita (header/footer, `w:sdt` content control, tabel-sebagai-tata-letak) akan mengulang kelas bug yang sama — obatnya bukan menebak-nebak wadah, melainkan **ukur dulu template yang gagal**; (2) pemeta heuristik tetap tipis untuk template asing (`Template SDD` cuma 3 dari 8 jenis isi) — pemeta LLM menutup sebagian, tapi bagian terakhir memang **penilaian manusia** dan tak bisa diotomatiskan: tak ada ekstraktor yang bisa tahu bab bernama "Setup" itu tempat screenshot. Karena itu jalurnya diakhiri UI tinjauan (`PUT /templates/{id}/mappings/{doc_type}`), bukan pemeta yang lebih pintar. Sistem kini **berisik saat ragu** (`mapping_health`, ambang 50% jenis isi yang MUNGKIN diikat — relatif per jenis dokumen, sebab kosakata UAT cuma punya 2 jenis sementara SDD 8, dan ambang mutlak memvonis setiap template UAT sakit).

- **Template `premco` kini menyediakan SDD DAN UAT (UAT sejak 2026-07-18); gaya-nya terbukti netral-bahasa (Python + TS/JS), tapi FORMAT-nya masih dari SATU sumber template.** Diverifikasi menghasilkan dokumen berjejak pada esteler (Python/Flask) DAN MyPertamina.id-Clone (Vue/JS/TS, 2026-07-18) — jadi klaim "repo bahasa apa pun yang didukung → gaya premco" bukan lagi asumsi. Yang MASIH satu sumber: bentuk visual/struktur premco diukur dari satu dokumen PREMCO SDD **dan** satu dokumen PREMCO UAT (dari perusahaan yang template default kita pun dimodelkan darinya), jadi V2 (upload sembarang template) tetap menunggu 1-2 template docx dari sumber lain. Roadmap tahap (b) — gaya premco untuk UAT — SELESAI. Job kini MENYIMPAN `template_id` (kolom + migrasi, 2026-07-21) dan mengembalikannya di GET status, jadi riwayat job bisa menjawab "dokumen ini gaya apa"; `None` untuk job dari DB lama. **Sejak 2026-07-21, `premco` jadi DEFAULT `template_id`** (`schemas_document.py` `= "premco"` + initial state frontend `useState('premco')`) — instance ini premco-first, jadi generate tanpa memilih langsung dapat gaya premco; `default` tetap tersedia sebagai pilihan.
- **Daftar Isi/Gambar/Tabel SDD tampak KOSONG sampai field di-update — ini perilaku Word standar, BUKAN bug (diverifikasi 2026-07-21 lanjutan 10).** Ketiganya ditanam sebagai Word field code (`TOC ...` + `updateFields=true` di settings.xml) — field code-nya SUDAH benar: dibuktikan lewat Word COM, begitu field di-update ketiga daftar terisi lengkap + nomor halaman + hyperlink clickable, dan Daftar Isi menampilkan hierarki acuan persis (bab tanpa nomor, sub-bab 1-4 di bawah Flow Proses Bisnis). Yang bikin tampak kosong: pengguna membuka docx TANPA meng-update field (klik "No" pada prompt Word, atau pakai viewer non-Word). Placeholder-nya sudah diubah jadi instruksi ("tekan Ctrl+A lalu F9"). **Nomor halaman MUSTAHIL di-bake Pandoc** — cuma mesin layout (Word/LibreOffice) yang bisa menghitungnya, jadi field code adalah cara docx standar; complex field `dirty=true` pun tak terisi pada plain-open (diuji). **Agar auto-terisi di viewer APA PUN tanpa aksi pengguna, perlu bake server-side lewat LibreOffice headless** — dependency baru yang belum terpasang, jadi belum di-ship (belum bisa diverifikasi; prinsip #4). Kandidat follow-up, keputusan pemilik.
- **Jalur bayar Stripe DITULIS & ber-tes, tapi BELUM pernah terbukti end-to-end.** Seluruh test mem-mock `stripe.Webhook.construct_event`, jadi yang dijaga adalah *"kalau event sah datang, tier naik"* — bukan *"Stripe benar-benar mengirim event itu"*. Acceptance criteria ketiga issue #12 (*"alur bayar test mode menaikkan tier"*) karenanya **belum tercentang**, dan itu bukan detail: yang belum diuji justru satu-satunya jalur yang boleh mengubah tier. Menutupnya butuh akun Stripe test-mode milik pemilik (secret key + price id + endpoint webhook yang bisa dijangkau Stripe, mis. lewat `stripe listen`) — tak bisa diselesaikan dari dalam repo. Sampai itu terjadi, perlakukan billing sebagai "siap dicoba", bukan "terbukti". Pola yang sama dengan gate Docker (#17) — bedanya gate Docker itu **sudah ditutup 2026-07-29**: image di-build & dijalankan pemilik, generate berbayar end-to-end menghasilkan docx (job `done` di Postgres). Jadi gate manual semacam ini memang bisa ditutup; Stripe tinggal menunggu giliran yang sama.
- **Pemeriksaan kuota dan pembuatan job tidak atomik** (TOCTOU, diketahui & diterima). `check_quota_available` membaca hitungan lalu `create_job` menulis; dua request yang benar-benar bersamaan bisa lolos bersama dan melewati batas satu-dua dokumen. Kelas yang sama dengan rate limit, dan obatnya pun sama (kunci/transaksi di titik tulis) — belum diambil karena taruhannya kecil: kelebihan satu dokumen bukan kelas kerugian yang sama dengan kuota yang bocor lipat-ganda antar worker.
- **Tidak ada hubungan/integrasi dengan project sibling `auto-project-tester`** — keduanya independen. Kalau menjalankan keduanya bersamaan secara lokal, perhatikan **keduanya sama-sama default ke port 8000** untuk backend-nya masing-masing — pastikan tidak salah port sebelum menyimpulkan sesuatu error/berhasil.

## Prinsip Kerja (pelajaran yang berulang)

Pola-pola ini muncul BERKALI-KALI selama membangun produk ini (detail tiap kasus
di `CHANGELOG.md`). Mereka mengubah CARA kerja, jadi sengaja tetap di sini — bukan
ikut pindah ke changelog:

1. **Buka/ukur barangnya, jangan menebak dari proksi.** Sebelum menyebut sesuatu
   cacat atau selesai: buka PDF/docx-nya, ukur token-nya, render diagram lalu
   LIHAT gambarnya. "Memeriksa proksi (selera, catatan status kita sendiri,
   pengetahuan umum framework) alih-alih barangnya" sudah menyesatkan >=5x.
2. **Ukur dulu sebelum memperbaiki.** Jangan perbaiki masalah yang belum
   dibuktikan ada. Contoh mahal: label `type` disangka bottleneck (ternyata
   bukan); `dot` disangka jauh lebih rapi dari smetana (ternyata ~ sama). Tahap 1
   validasi GRATIS dulu.
3. **Sebab asli jangan ditelan gejala.** `except` yang terlalu lebar meratakan
   sebab spesifik jadi "coba lagi" generik (muncul 4x). Pisahkan kegagalan
   PERMANEN (413/500) dari SEMENTARA (502) — pengguna harus bisa membedakannya.
4. **Test hijau != produk jalan.** Mock menyembunyikan bug nyata (414 mermaid.ink,
   kurung route-param Nuxt/Next). Verifikasi end-to-end ke repo/dokumen NYATA, dan
   untuk yang visual: LIHAT hasilnya, bukan baca XML-nya.
5. **Fixture N=1 buta terhadap bug ANTAR-item.** Bug heading use case &
   subtree-drop hanya muncul dari item KEDUA. Uji dengan >=2 item.
6. **Kelayakan fitur besar dibuktikan $0 dulu.** Prototipe di scratchpad sebelum
   nulis kode `app/` atau bayar LLM — yang tersisa jadi implementasi, bukan taruhan.
7. **Premis yang belum diuji jangan dijadikan fondasi.** Kalau permintaan
   bersandar pada "X bikin rapi/cepat/benar", uji premisnya $0 SEBELUM kerja besar
   (mis. "dot bikin diagram rapi" — ternyata crossing itu struktural, bukan engine).
8. **Jujur soal batas mengalahkan mengarang.** Isi yang bisa diturunkan dari kode;
   kosongkan (placeholder yang TERLIHAT) yang tidak. 30 halaman benar > 87 halaman
   separuh karangan — itu nilai jual produk, bukan kekurangannya.

## Riwayat Perubahan

Riwayat perubahan detail (dulu ~65% isi file ini, di-load tiap sesi walau jarang
dipakai) dipindah ke **`CHANGELOG.md`** (2026-07-20) supaya CLAUDE.md tetap ramping
dan berhenti membengkak tiap sesi. Baca `CHANGELOG.md` kalau butuh sejarah atau
ALASAN di balik satu perubahan — semua referensi "lihat Riwayat" di dokumen ini
menunjuk ke sana. **Entri baru DITULIS ke `CHANGELOG.md`** (terbaru di atas), bukan
ke sini; CLAUDE.md disentuh hanya kalau pengetahuan permanen berubah
(arsitektur/kontrak/keterbatasan/prinsip).
