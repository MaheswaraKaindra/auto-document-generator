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

Sesi terpanjang sejauh ini. **Produk ini akhirnya dipakai manusia sungguhan lewat
UI-nya sendiri** — bukan lewat test, bukan lewat script. Dan satu jam di kursi
pengguna menemukan **tiga bug yang 156 test hijau tidak pernah lihat**. Ditambah:
dukungan **Java + Spring MVC** (bahasa enterprise pertama), `url_prefix` Flask,
**Daftar Gambar & Daftar Tabel** (celah struktur terakhir yang bisa diselesaikan
— sisa cuma Mockup), README, frontend yang menjelaskan dirinya, progress
per-tahap, dan **kualitas visual dokumen** (yang menyingkap tiga cacat fungsional
lagi). Ditutup dengan **redesign frontend** (bahasa visual dokumen + log tahapan
bercentang) dan **audit menyeluruh** — yang menemukan bahwa **jalur ZIP → dokumen
tidak pernah ada** padahal diklaim sejak hari pertama. **Produk siap didemokan.**
186 test hijau, biaya ~$0,6.

---

## Yang diselesaikan

| # | Masalah | Inti perbaikannya |
|---|---|---|
| 1 | **Seluruh file `.java` = entry kosong** | `.java` ada di `SOURCE_EXTENSIONS` tapi tidak di `EXTENSION_TO_LANGUAGE`. petclinic **0 → 17 endpoint, 0 → 25 class**, dan `type` terisi sendiri (controller 6, repository 3) **tanpa menyentuh heuristiknya**. |
| 2 | **Dokumen Java pertama** | ~$0,23. Aktor **Staff Klinik & Pengunjung**. Diagram diaudit dengan menggeledah SELURUH Contract A — semua berjejak. |
| 3 | **Dua controller klaim endpoint sama** (bug NYATA di dokumen esteler) | `url_prefix` Blueprint diabaikan. **Bentrok 2 → 0**, total tetap 38. Diagnosis lama ("butuh analisis lintas-file") **salah**. |
| 4 | **README cuma 1 baris judul** | Pintu depan: apa produknya, kenapa ada, apa yang keluar, batasnya, status jujur. |
| 5 | **Tidak ada Daftar Gambar/Tabel** | `--lof/--lot` → Pandoc menulis **field code Word**, jadi **Word yang menghitung nomor halaman**. Judul Indonesia butuh DUA mekanisme (`lang=id` + `toc-title`). |
| 6 | **Frontend polos** | Tiap field menjelaskan dirinya; tiap klaimnya dicek ke kode dulu. |
| 7 | **404 GitHub menyuruh curiga URL** | Ditemukan pengguna di percobaan PERTAMA. GitHub balas 404 untuk repo-tak-ada DAN repo-privat — identik. Sekarang pesannya menyebut token. |
| 8 | **Semua unduhan bernama `dokumen.docx`** | CORS tanpa `expose_headers` → browser sembunyikan `Content-Disposition` → fallback. Diam-diam. |
| 9 | **2-3 menit tanpa kabar** | Progress per tahap. Detik ke-5: *"Membaca kode: 22 file, 38 endpoint, 16 class"* — angka nyata dari repo pengguna. |
| 10 | **Dokumen terlihat seperti render Markdown** | Diminta pemilik project. Tampilan (tipografi, tabel header hitam, kaki halaman) pindah ke `reference.docx` lewat `--reference-doc`. Pipeline & kedua Contract **tidak disentuh**. |
| 11 | **"Diagram blur" ternyata JPEG** | mermaid.ink membalas JPEG (lossy, untuk foto) pada *line art*, 77 dpi. Disimpan berakhiran `.png` padahal isinya JPEG. → PNG lossless, 246 dpi. |
| 12 | **Acceptance Criteria jadi paragraf gembung** | Markdown butuh baris kosong sebelum list. 8 use case × kriteria terlebur jadi blok tak terbaca. Terukur: paragraf **11 → 42**. |
| 13 | **5 dari 11 gambar tumpah keluar halaman** | Setinggi 17,2 inci di halaman 11 inci. `_image_attr` membatasi sisi yang lebih dulu mentok → **11/11 muat**. |
| 14 | **Frontend redesign** | Bahasa visual dokumen (kertas/tinta/biru-dokumen, section bernomor seperti bab SDD, judul serif); ungu template dibuang. Status jadi **log tahapan bercentang** — murni dari data server, tanpa mencocokkan string. **Belum dilihat mata manusia.** |
| 15 | **Audit menyeluruh: 9 temuan, 7 dieksekusi** | Terbesar: **jalur ZIP → dokumen tidak pernah tersambung** — `/ingest/zip` berhenti di Contract A, `/documents/generate` cuma menerima GitHub; klaim "ZIP upload" sejak hari pertama ditulis dari desain, bukan dari memeriksa jalurnya. README dijujurkan. Sisanya: 47 baris kode mati + blok `__main__` dihapus, `/ingest/zip` nol test → 3 test, `.env.example` dilengkapi, `VITE_API_BASE_URL`, poll timeout 10→30 menit (**harus > timeout LLM 25 menit** — 10 menit memvonis gagal job besar yang masih jalan), klaim basi di README/CLAUDE.md dikoreksi. Rekomendasi tanpa eksekusi: pin versi requirements. |

**Dibatalkan setelah diukur:** Tahap 2 saleor ($2,27, hasilnya ambigu — lihat #2
di prioritas) dan render diagram paralel (503 — lihat pelajaran).

---

## Yang dibuktikan MATA MANUSIA, bukan test

Ini yang membedakan sesi ini dari semua sesi sebelumnya:

- **Demo end-to-end lewat UI**, oleh pemilik project, dengan uang sungguhan
  ($0,17): form → generate → 2,3 menit → docx terunduh. Berhasil.
- **Daftar Gambar terisi 11 baris + nomor halaman di Word**, tanpa refresh manual.
  Membaca XML tidak akan pernah membuktikan itu.
- **Hint frontend menempel ke field yang benar** (dicek dari screenshot).
- **Progress muncul di layar** — *"Membaca kode: 22 file, 38 endpoint"* di detik ke-5.
- **Tiga bug ditemukan dari kursi pengguna** (#7, #8, #9 di atas). Tidak satu pun
  bisa ditemukan lewat test, XML, atau repo nyata.
- **Tiga cacat lagi ditemukan dari INSTING pemilik project** ("outputnya harus
  terlihat profesional") — #11, #12, #13. Ketiganya terlihat kosmetik, ternyata
  merusak fungsi, dan **semuanya gagal sunyi**. Luput seharian karena setiap
  pemeriksaan menguji STRUKTUR dan ISI, tidak pernah TAMPILAN.
- **Tampilan akhirnya dinilai mata manusia**: *"jauh lebih rapi sekarang."*

---

## Pelajaran metodologis (yang paling mahal kalau dilupakan)

**"Memeriksa PROKSI, bukan barangnya" muncul DELAPAN kali hari ini.** Bukan di
tempat yang terlihat seperti tempat bug:

| Yang diperiksa (proksi) | Barangnya | Akibatnya |
|---|---|---|
| Contract A petclinic **sebelum parser Java ada** | Contract A Java sesungguhnya | "Java cuma 6 KB, muat lega" — 6 KB **karena kosong** |
| **Idiom Flask yang lazim** | Kode esteler yang benar-benar ada | Diagnosis `url_prefix` salah berbulan-bulan |
| **"saleor ≈ 4× esteler"** (tebakan) | 22 KB vs 2.075 KB = **94×** | Bilang \$0,60 ke pemilik project; aslinya **\$2,27** |
| **Gagasan tentang dokumen yang baik** | **Dokumen acuan di root**, sejak hari pertama | "Revision History cacat" — acuan pun kosong |
| **"17 endpoint, naik dari 0"** | Path-nya benar atau tidak | `VetController` lapor `GET /`, salah |
| **XML mentah** | Teks yang terlihat pembaca | `"List of Figures"` memang ada — sebagai id internal Word |
| **"404 ini mirip bug yang kita berantas"** | Apakah ada yang terkena? | Tidak ada. Dipergoki pemilik project dengan 4 kata. |
| **String `<w:b/>`** | **XML yang di-parse** | "bold gagal terpasang" — padahal terpasang; Pandoc menulis `<w:b />` dengan spasi |
| **Struktur & isi dokumen** | **Rupanya** | Dokumen "lengkap" tapi diagramnya JPEG 77 dpi, kriteria terlebur, 5 gambar tumpah halaman |

> Pengetahuan umum tentang framework itu **prior**, bukan **bukti**.
> Pertanyaan pertama bukan *"sudah diukur belum?"* tapi **"yang mau saya ukur ini
> ADA belum?"** — dan sesudahnya: **"kalau ini rusak, siapa yang terkena?"**

**Mengukur keuntungan tanpa mengukur BATAS.** Render paralel: 11 diagram × 2,9
detik = 31 detik (20% total) yang saling menunggu tanpa alasan. Dikerjakan, test
hijau semua. Lalu diuji ke mermaid.ink sungguhan: **2 request bersamaan = 503**,
diukur tepat sesudah 1 request tunggal berhasil. Pertukaran aslinya: hemat 25
detik ditukar dengan satu 503 yang menggagalkan **seluruh** dokumen.
**Nyaris terkirim — semua test hijau, karena mermaid.ink di-mock.**

**Test hijau paling tidak berdaya justru di batas sistem.** Tiga bug demo lolos
karena: `TestClient` **tidak menegakkan CORS** (bukan browser), mermaid.ink
**di-mock**, dan tidak ada test yang bisa tahu nama file yang benar-benar
mendarat di folder unduhan. Semua butuh manusia, browser, dan mata.

---

## Kalau melanjutkan besok, mulai dari sini

**Produk siap didemokan. Tidak ada yang menghalangi.** Sebelum demo cukup: isi
`GITHUB_TOKEN` di `.env` (anonim 60/jam, gampang habis kalau penguji minta coba
repo kedua) dan **isi Nama Project dengan benar** — dia jadi nama aplikasi di
seluruh prosa dokumen, bukan cuma judul.

Sisanya, semuanya menunggu pengguna yang belum ada:

1. **Ablasi endpoint esteler (~$0,15)** — uji berbayar dengan nilai/biaya
   terbaik. Hapus `api_endpoints` dari Contract A esteler, generate ulang,
   bandingkan. **esteler satu-satunya repo yang tidak ada di ingatan model** (semua
   yang lain proyek terkenal) dan satu-satunya yang punya ground truth. Menjawab:
   **apakah kedalaman parser layak dibangun sama sekali?** Kalau fitur tetap
   akurat tanpa endpoint, maka Django/Go/.NET/`register_blueprint` lintas-file
   semuanya boleh dicoret — hemat berminggu-minggu.
2. **~~Tahap 2 saleor~~ — DIBATALKAN.** $2,27 (bukan $0,60), **dan hasilnya tidak
   bisa ditafsirkan**: saleor proyek terkenal, jadi dokumen bagus tidak bisa
   membedakan "produk membaca kode" dari "model ingat dari training". Satu-satunya
   yang cuma dia bisa jawab: apakah kualitas bertahan di 85% context window.
3. **Deploy — TIDAK diperlukan untuk demo magang.** Dan ada penghalang serius
   kalau nanti dikerjakan: **tidak ada autentikasi sama sekali** di
   `POST /documents/generate` + `allow_origins=["*"]` → siapa pun bisa
   menghabiskan `ANTHROPIC_API_KEY`. $0,23/dokumen, $2,27 untuk repo besar, tanpa
   rate limit. Auth wajib duluan. Ditambah: Vercel membekukan `BackgroundTasks`,
   SQLite butuh volume, pandoc butuh image, frontend hardcode `localhost:8000`.
4. **Repo Java enterprise BESAR** — petclinic cuma 33 file. Densitas 0,64 KB/file
   → ekstrapolasi ~2.500 file = ~677K token (muat), tapi petclinic nyaris tanpa
   Javadoc. **Ekstrapolasi, bukan bukti.**
5. **`register_blueprint(bp, url_prefix=)` lintas-file** — sengaja belum: esteler
   pakai bentuk konstruktor, jadi jalur ini tak bisa dibuktikan end-to-end.
6. **Endpoint Django** — urutkan sesudah #1.
7. **Job hilang kalau proses mati**; **bersihkan `data/documents/`** (tanpa TTL).
8. **Sonnet 5 vs Opus** (~$0,50) — asumsi kualitas yang menggantung sejak lama.

---

## Yang perlu dilakukan manusia (tidak bisa saya kerjakan)

- **Revoke `GOOGLE_API_KEY` dan `LLAMA_API_KEY`.** Sudah dihapus dari `.env`
  lokal, tapi **kuncinya masih hidup** sampai dicabut lewat console. (Menggantung
  tiga sesi.)
- **Baca dokumen hasilnya sendiri** — `dokumen.docx` (esteler, dari demo) dan
  `scripts/validation/out/spring-petclinic-java__SDD.docx` (Java). Saya sudah
  audit isinya lewat Contract B dan keduanya berjejak, tapi **apakah layak dikirim
  ke klien itu penilaian manusia.**
- **Isi `GITHUB_TOKEN`** sebelum demo.
