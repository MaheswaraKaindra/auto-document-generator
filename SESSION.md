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

Sesi ini menambah **dukungan parser Java + Spring MVC** — bahasa enterprise
pertama, dan target pasar produk ini. spring-petclinic: **0 → 17 endpoint, 0 → 25
class**, lalu jadi **dokumen Java pertama** yang seluruh isinya berjejak (aktor
`Staff Klinik`/`Pengunjung`, bukan Developer/API Client). Tapi temuan yang paling
berharga bukan kodenya: **prioritas #1 yang saya warisi sendiri ternyata mengukur
benda yang salah**, dan itu ketahuan sebelum sepeser pun keluar. 138 test hijau.
Biaya: **$0,23**.

---

## Yang diselesaikan

| # | Masalah | Inti perbaikannya |
|---|---|---|
| 1 | **Prioritas #1 mengukur benda yang salah** | Rencana: *"ukur Contract A petclinic dalam token, GRATIS, hasilnya menentukan prioritas"*. Tapi `.java` ada di `SOURCE_EXTENSIONS` & tidak di `EXTENSION_TO_LANGUAGE` → yang terukur **daftar path kosong** (6,4 KB), bukan Contract A Java (21 KB). Dibatalkan **sebelum** dikerjakan. |
| 2 | **Seluruh file `.java` = entry kosong** | 33 file → 0 class, 0 dep, 0 endpoint. Sekarang **25 class, 17 endpoint**, coverage 0% → 33%. |
| 3 | **`type` semua "other" walau `OwnerController.java`** | `build_parsed_repo_context` meng-hardcode `type="other"` di fallback, **tak pernah** memanggil `_guess_file_type`. Begitu Java diparse: controller 6, repository 3, model 2 — **tanpa menyentuh heuristiknya**. |
| 4 | **`@GetMapping({"/vets"})` → path jatuh ke `/`** | Array posisional tak cocok cabang mana pun. VetController & WelcomeController sama-sama lapor `GET /`. **Lolos dari angka "17 endpoint"**; ketahuan cuma karena path diperiksa satu-satu. |
| 5 | **Prefix class tidak tersambung** | `@RequestMapping("/owners/{ownerId}")` + `@GetMapping("/pets/new")` = `/owners/{ownerId}/pets/new`. Sama dengan url_prefix Flask, tapi di Java **sefile** → deterministik. |

Ditambah: `tests/test_parser_java.py` (19 test), `repos.json` petclinic berpindah
peran (dulu mengukur lubang → sekarang penjaga regresi Java).

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
- **Nol regresi ke repo nyata** (wajib: `_string_literal_value` dipakai bersama
  Python/TS): fastapi 49 file, flask 25/52 class/72 function/154,9 KB, express 8,
  realworld 69/27 endpoint — identik.
- **Densitas Java terukur 0,64 KB/file** — sebanding saleor (0,81), yang muat di
  85%. Jadi Java **tidak** lebih berat dari Python; klaim lama *"Java tak ada guna
  sebelum chunking beres"* gugur.

---

## Pelajaran metodologis (yang paling mahal kalau dilupakan)

**Pola "memeriksa PROKSI, bukan barangnya" muncul untuk KEEMPAT kalinya — dan kali
ini proksinya ada di RENCANA KERJANYA.** Kalimat *"ukur dulu, gratis, hasilnya
menentukan prioritas"* terdengar persis seperti pelajaran yang benar. Tapi yang
akan terukur adalah bayangan, bukan bendanya:

| Yang mau diukur (proksi) | Barangnya | Akibatnya |
|---|---|---|
| Contract A petclinic **sebelum parser Java ada** (6,4 KB) | Contract A Java **sesungguhnya** (21 KB, 25 class) | Jawabannya salah ke arah **menyenangkan**: "Java cuma 6 KB, muat lega, gas!" — padahal 6 KB **karena kosong** |

> **Urutannya terbalik secara logis:** ukuran Contract A Java adalah *konsekuensi*
> dukungan Java, bukan *prasyaratnya*. Tak ada cara mengukur yang belum dibangun.

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

1. **Tahap 2 ke `saleor` (~$0,60-0,80, Django, 854K token = 85%)** — kasus paling
   tajam yang tersedia sekarang, dan **belum pernah dijalankan**. Dia MUAT sejak
   compact tapi punya **0 endpoint** (Django taruh route di `urls.py`, bukan
   decorator). Pertanyaannya persis yang tertulis di `repos.json`: *dengan 0
   endpoint, apakah LLM tetap menulis fitur dengan percaya diri? Kalau ya, itu
   karangan.* Ini menguji batas kejujuran produk di titik terlemahnya — dan
   hasilnya menentukan apakah **endpoint Django** (#4) layak dikerjakan.
   Catatan biaya: ~4× esteler, jadi hitung ulang sebelum jalan.
2. **`url_prefix` Blueprint Flask** — bug NYATA di dokumen esteler yang sudah jadi:
   `routes/admin.py` & `routes/customer.py` sama-sama lapor `GET /`. Butuh analisis
   lintas-file (`register_blueprint`). **Sesi ini menaikkan nilainya**: versi Java-nya
   sudah selesai (prefix class), jadi bentuk solusinya sudah terbukti — yang beda
   cuma Flask menaruh prefixnya di file lain.
3. **Repo Java enterprise BESAR** — petclinic cuma 33 file, terlalu kecil untuk
   menutup pertanyaan ukuran. Densitas 0,64 KB/file → ekstrapolasi ke ~2.500 file
   = ~677K token (68%, muat), **tapi petclinic nyaris tanpa Javadoc**; enterprise
   ber-Javadoc padat bisa ~2 KB/file → ~2,1 juta token (tidak muat). **Ini
   ekstrapolasi, bukan bukti.** Sekalian menguji `@RequestMapping` tanpa `method=`
   (diaproksimasi GET) yang belum tersentuh repo nyata.
4. **Endpoint Django** — penghalang lamanya (saleor tak muat) **sudah hilang**.
   Urutkan sesudah #1: hasil Tahap 2 saleor menentukan apakah ini mendesak.
5. **Job hilang kalau proses mati** — `BackgroundTasks` in-process: restart/crash
   saat job jalan → berhenti selamanya di `running`, klien polling tanpa akhir.
   Multi-worker BUKAN masalah (sudah diukur); serverless masih (esteler di Vercel).
6. **Tabel Revision History** masih baris kosong — butuh keputusan produk dulu
   (`Summary of Changes` tak punya jawaban jujur untuk dokumen baru).
7. **Sonnet 5 vs Opus** (~$0,50) — default pindah atas dasar reputasi, bukan
   pengukuran. Sekarang ada DUA pembanding murah & bagus: esteler + petclinic.
8. **Chunking monorepo raksasa** — medusa 1.253.878 token = 125%, tetap ditolak.
   Menyaring tak menolong (`classes` 21% & `dependencies` 23% = bahan baku
   dokumen). Masalahnya arsitektur: SELURUH Contract A dikirim dalam SATU panggilan.
9. **Bersihkan `data/documents/`** — tumbuh selamanya, ~400 KB/dokumen, tanpa TTL.

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
