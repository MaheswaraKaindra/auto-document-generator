# Catatan Sesi — 2026-07-16

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi ini menambah **dukungan parser Java + Spring MVC** (bahasa enterprise
pertama, target pasar produk ini): spring-petclinic **0 → 17 endpoint, 0 → 25
class**, lalu jadi **dokumen Java pertama** yang seluruh isinya berjejak (aktor
`Staff Klinik`/`Pengunjung`, bukan Developer/API Client). Lalu memperbaiki
**`url_prefix` Blueprint Flask** — bug nyata di dokumen esteler yang sudah
dikirim: bentrokan endpoint **2 → 0**. Tapi temuan paling berharga bukan kodenya:
**dua rencana kerja yang saya warisi ternyata bersandar pada benda yang salah**,
dan dua-duanya ketahuan sebelum uang keluar. 149 test hijau. Biaya: **$0,23**.

---

## Yang diselesaikan

| # | Masalah | Inti perbaikannya |
|---|---|---|
| 1 | **Prioritas #1 mengukur benda yang salah** | Rencana: *"ukur Contract A petclinic dalam token, GRATIS, hasilnya menentukan prioritas"*. Tapi `.java` ada di `SOURCE_EXTENSIONS` & tidak di `EXTENSION_TO_LANGUAGE` → yang terukur **daftar path kosong** (6,4 KB), bukan Contract A Java (21 KB). Dibatalkan **sebelum** dikerjakan. |
| 2 | **Seluruh file `.java` = entry kosong** | 33 file → 0 class, 0 dep, 0 endpoint. Sekarang **25 class, 17 endpoint**, coverage 0% → 33%. |
| 3 | **`type` semua "other" walau `OwnerController.java`** | `build_parsed_repo_context` meng-hardcode `type="other"` di fallback, **tak pernah** memanggil `_guess_file_type`. Begitu Java diparse: controller 6, repository 3, model 2 — **tanpa menyentuh heuristiknya**. |
| 4 | **`@GetMapping({"/vets"})` → path jatuh ke `/`** | Array posisional tak cocok cabang mana pun. VetController & WelcomeController sama-sama lapor `GET /`. **Lolos dari angka "17 endpoint"**; ketahuan cuma karena path diperiksa satu-satu. |
| 5 | **Prefix class tidak tersambung** | `@RequestMapping("/owners/{ownerId}")` + `@GetMapping("/pets/new")` = `/owners/{ownerId}/pets/new`. Sama dengan url_prefix Flask, tapi di Java **sefile** → deterministik. |
| 6 | **Dua controller klaim endpoint yang sama** (bug NYATA di dokumen esteler yang sudah dikirim) | `url_prefix` Blueprint diabaikan. **18 dari 38 endpoint jadi `/admin/...`, bentrok 2 → 0**, total tetap 38. Diagnosis lama ("butuh analisis lintas-file") **salah** — prefixnya di konstruktor, sefile. |

Ditambah: `tests/test_parser_java.py` (19 test), `test_parser_endpoints.py` +11,
`repos.json` petclinic & esteler berpindah peran jadi penjaga regresi.

---

## Yang dibuktikan lewat repo nyata (bukan test)

- **Dokumen Java pertama** (~$0,23, 128 detik): 5 fitur, 5 use case, 5 test case,
  5 activity diagram, docx 258 KB. **Aktor `Staff Klinik`/`Pengunjung`** — penanda
  paling menentukan, dan lulus. Fiturnya memetakan satu-satu ke controller nyata.
- **Diagramnya diaudit dengan menggeledah SELURUH Contract A**, bukan
  `dependencies` saja (pelajaran dari salah-tuduh "Neon"). Semua berjejak:
  `Backend --> Database` ← `JpaRepository`/`Entity`×18/`Table`/`ManyToOne`;
  "pergantian bahasa" (yang sempat saya curigai karangan) ← `LocaleResolver`,
  `LocaleChangeInterceptor`; "Server-rendered Views" ← `ModelAndView`.
- **esteler: bentrokan endpoint 2 → 0.** `routes/admin.py` kini `/admin/...` (18
  dari 38 endpoint), `auth`/`customer` tidak berubah, total tetap **38** — tidak
  ada endpoint hilang atau muncul, cuma path-nya benar. Memperbaiki dokumen yang
  **sudah dikirim**, bukan menjawab hipotesis.
- **Nol regresi dibuktikan ke repo nyata DUA KALI** — wajib, karena kedua
  perubahan menyentuh kode yang dipakai bersama (`_string_literal_value` oleh
  Java+Python+TS; jalur decorator oleh Flask+FastAPI): fastapi 49 file/0 endpoint,
  flask 25/0/52 class/72 function, express 8/33, realworld 69/27 — identik.
- **Densitas Java terukur 0,64 KB/file** — sebanding saleor (0,81), yang muat di
  85%. Jadi Java **tidak** lebih berat dari Python; klaim lama *"Java tak ada guna
  sebelum chunking beres"* gugur.

---

## Pelajaran metodologis (yang paling mahal kalau dilupakan)

**Pola "memeriksa PROKSI, bukan barangnya" muncul TIGA kali lagi hari ini (total
5×) — dan ketiganya bersembunyi di tempat yang tidak terlihat seperti tempat bug:
rencana kerja, pengetahuan umum, dan aritmetika saya sendiri.** Tiap kali,
barangnya ada dalam jangkauan dan saya memeriksa sesuatu yang mirip:

| Yang saya periksa (proksi) | Barangnya | Akibatnya |
|---|---|---|
| Contract A petclinic **sebelum parser Java ada** (6,4 KB) | Contract A Java **sesungguhnya** (21 KB, 25 class) | Jawabannya salah ke arah **menyenangkan**: "Java cuma 6 KB, muat lega, gas!" — padahal 6 KB **karena kosong** |
| **Idiom Flask yang lazim** (`register_blueprint(bp, url_prefix=...)` di file lain) | **Kode esteler yang benar-benar ada** (`Blueprint(..., url_prefix=...)` sefile) | Diagnosis `url_prefix` salah berbulan-bulan — dan bikin perbaikannya tampak **jauh lebih mahal** daripada aslinya |
| **"saleor ≈ 4× esteler"** (tebakan skala) | **22 KB vs 2.075 KB = 94×** | Saya bilang \$0,60-0,80 ke pemilik project; aslinya **\$2,27**. Dua angka itu sudah ada di layar — saya tinggal membaginya |

> **Urutannya terbalik secara logis:** ukuran Contract A Java adalah *konsekuensi*
> dukungan Java, bukan *prasyaratnya*. Tak ada cara mengukur yang belum dibangun.

**Yang paling licin: proksi berupa PENGETAHUAN UMUM.** Diagnosis `url_prefix`
berbunyi *"blueprint **biasanya** didaftarkan di file lain"* — **benar tentang
Flask pada umumnya**, dan itulah yang membuatnya lolos bertahun-tahun. Tentang
esteler, salah. Kata "biasanya" itu sendiri pengakuan bahwa yang ditulis adalah
distribusi, bukan repo ini. Cukup `grep Blueprint` sekali.

> Pengetahuan umum tentang framework itu **prior**, bukan **bukti**.

**"Ukur dulu" tidak melindungi apa pun kalau yang diukur bukan bendanya.** Ritual
mengukur bisa jadi **pengganti** berpikir, bukan alat berpikir. Pertanyaan pertama
bukan *"sudah diukur belum?"* tapi **"yang mau saya ukur ini ADA belum?"**

**Dan saya nyaris mengulanginya sendiri, di sesi yang sama.** Hasil "17 endpoint,
naik dari 0" terasa seperti bukti. Itu **proksi**; barangnya adalah **path-nya
benar atau tidak**. Diperiksa satu-satu → `VetController` lapor `GET /`, salah.
Kalau berhenti di angka, bug itu masuk ke dokumen.

**Grammar tree-sitter tidak seragam antar bahasa, dan bedanya gagal SUNYI.**
`modifiers` **bukan field** di Java (`child_by_field_name` → `None`) padahal
`name`/`body`/`parameters` memang field. Menyalin pola Python = nol endpoint,
tanpa satu pun error. Dump AST-nya dulu; menebak node type = menulis parser yang
diam-diam salah.

**Label `type` bukan bottleneck — bukti ketiga.** flask 0% → dokumen akurat,
esteler, dan kini petclinic 33% dengan `Owner.java`/`Pet.java` berlabel `other`
→ dokumen tetap benar, karena LLM membaca `@Entity` dari `dependencies`.

---

## Kalau melanjutkan besok, mulai dari sini

1. **Ablasi endpoint di esteler (~$0,15)** — uji berbayar dengan rasio nilai/biaya
   terbaik yang tersedia, dan **menggantikan saleor** (lihat #2). Hapus
   `api_endpoints` dari Contract A esteler, generate ulang, bandingkan dengan
   dokumen yang ada. **Satu variabel berubah.** Kenapa esteler: dia **satu-satunya
   repo yang tidak ada di ingatan model** (semua yang lain — flask, fastapi,
   express, requests, medusa, petclinic, realworld, saleor — proyek terkenal), dan
   satu-satunya yang punya ground truth (pemiliknya di tim). Hasilnya menentukan:
   fitur tetap akurat → **endpoint Django turun prioritas jauh**; fitur ambruk →
   endpoint menopang segalanya. Idealnya + baseline segar (~$0,30) supaya bedanya
   tidak tertukar dengan non-determinisme LLM.
2. **~~Tahap 2 saleor~~ — DIBATALKAN, jangan diulang tanpa alasan baru.** Dua
   sebab: **(a) biayanya $2,27**, bukan $0,60-0,80 seperti sempat saya klaim (94×
   esteler, bukan 4×); **(b) hasilnya tidak bisa ditafsirkan** — saleor proyek
   open-source terkenal, jadi dokumen yang bagus tidak bisa membedakan "produk kita
   membaca kode" dari "model ingat saleor dari training data". Hasil bagus =
   ambigu, dan hasil bagus justru yang paling mungkin. **Satu-satunya hal yang
   cuma bisa dijawab saleor**: apakah kualitas bertahan di 85% context window —
   pertanyaan infrastruktur, tidak mendesak sampai ada yang butuh repo sebesar itu.
3. **Repo Java enterprise BESAR** — petclinic cuma 33 file, terlalu kecil untuk
   menutup pertanyaan ukuran. Densitas 0,64 KB/file → ekstrapolasi ke ~2.500 file
   = ~677K token (68%, muat), **tapi petclinic nyaris tanpa Javadoc**; enterprise
   ber-Javadoc padat bisa ~2 KB/file → ~2,1 juta token (tidak muat). **Ini
   ekstrapolasi, bukan bukti.** Sekalian menguji `@RequestMapping` tanpa `method=`
   (diaproksimasi GET) yang belum tersentuh repo nyata.
4. **Endpoint Django** — penghalang lamanya (saleor tak muat) **sudah hilang**.
   Urutkan sesudah #1: ablasi esteler menentukan apakah ini mendesak.
5. **`register_blueprint(bp, url_prefix=)` lintas-file** — sisa dari perbaikan
   url_prefix hari ini. Bentuk konstruktor sudah jalan; bentuk ini belum, dan
   **sengaja**: esteler (satu-satunya app Flask nyata kita) pakai bentuk
   konstruktor, jadi jalur lintas-file tak bisa dibuktikan end-to-end. Butuh app
   Flask bergaya itu di `repos.json` dulu. Aturan yang sama yang menahan Django.
6. **Job hilang kalau proses mati** — `BackgroundTasks` in-process: restart/crash
   saat job jalan → berhenti selamanya di `running`, klien polling tanpa akhir.
   Multi-worker BUKAN masalah (sudah diukur); serverless masih (esteler di Vercel).
7. **Tabel Revision History** masih baris kosong — butuh keputusan produk dulu
   (`Summary of Changes` tak punya jawaban jujur untuk dokumen baru).
8. **Sonnet 5 vs Opus** (~$0,50) — default pindah atas dasar reputasi, bukan
   pengukuran. Sekarang ada DUA pembanding murah & bagus: esteler + petclinic.
9. **Chunking monorepo raksasa** — medusa 1.253.878 token = 125%, tetap ditolak.
   Menyaring tak menolong (`classes` 21% & `dependencies` 23% = bahan baku
   dokumen). Masalahnya arsitektur: SELURUH Contract A dikirim dalam SATU panggilan.
10. **Bersihkan `data/documents/`** — tumbuh selamanya, ~400 KB/dokumen, tanpa TTL.

---

## Yang perlu dilakukan manusia (tidak bisa saya kerjakan)

- **Revoke `GOOGLE_API_KEY` dan `LLAMA_API_KEY`.** Sudah dihapus dari `.env` lokal,
  tapi **kuncinya masih hidup** sampai dicabut lewat console masing-masing.
  (Masih belum dilakukan sejak dua sesi lalu.)
- **Baca `scripts/validation/out/spring-petclinic-java__SDD.docx`** (258 KB, Java)
  dan **`esteler-flask__SDD.docx`** (408 KB). Saya sudah audit isinya lewat
  Contract B dan keduanya berjejak — tapi apakah dokumennya **layak dikirim ke
  klien** itu penilaian manusia.
- **Isi `GITHUB_TOKEN`** kalau mau sering menjalankan validasi (anonim 60/jam;
  sesi ini terpakai ~15).
