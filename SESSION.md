# Catatan Sesi — 2026-07-16 (sesi kedua hari itu)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Sesi arah baru. Pemilik project membawa masukan penguji dan menetapkan roadmap:
**SDD harus sesuai template acuan PREMCO dulu → baru UAT → baru template
generik** (visi akhir: "upload template perusahaanmu + repo/ZIP"). PDF acuan 87
halaman akhirnya **dibaca utuh** dan dibandingkan bagian-per-bagian dengan
dokumen jadi — ketemu 1 bug nyata (heading use case 11.2+ bocor jadi teks
literal) + daftar gap per-bagian. Semua gap dieksekusi dalam sesi yang sama:
kerangka manual acuan (Kelas A, $0), lalu **migrasi diagram Mermaid→PlantUML
LOKAL digabung pendalaman Contract B** (tabel ACT per activity, tabel role,
tahapan flow, system requirement terstruktur) — dipicu keputusan pemilik
setelah melihat lembar perbandingan berdampingan. Diverifikasi regen esteler
(~$0,25-0,30): **semuanya jalan, semua berjejak, 12 diagram UML sungguhan.**
191 test hijau (186→191). Biaya sesi: ~$0,25-0,30.

## Keputusan produk sesi ini (dari pemilik, catat baik-baik)

1. **Frontend dinyatakan cukup** — jangan investasi desain lagi sampai diperlukan.
2. **Roadmap 3 tahap**: (a) SDD ≈ acuan PREMCO — *bagian struktur/bentuk SELESAI
   sesi ini*; (b) UAT; (c) template generik (upload template). Form 25 field
   dianggap penguji membebani; kelak digantikan template upload (tapi field
   manual tidak hilang — jadi placeholder).
3. **PlantUML dipilih** menggantikan Mermaid, lewat perbandingan mata sendiri.
4. Saran penguji soal **multi-agent**: disepakati BELUM sekarang; relevan di
   tahap (c) dan untuk monorepo. Alasan lengkap di percakapan; intinya satu
   panggilan = koheren + murah, dekomposisi menunggu masalah yang menuntutnya.

## Yang diselesaikan

| # | Apa | Inti |
|---|---|---|
| 1 | **Bug heading use case 11.2–11.8** | Pandoc butuh baris kosong SEBELUM heading; trim_blocks memakannya. Lolos 186 test karena fixture cuma 1 use case — bug antar-item mustahil terlihat fixture N=1. |
| 2 | **Kerangka acuan (Kelas A, $0)** | Halaman muka (Fungsi/Kodifikasi, Katalog Proses Bisnis, Tim & Peran), Timeline+Cost+2 blok TTD di Persetujuan, bab "13. Mockup Antarmuka". Sel sengaja KOSONG, bukan `(diisi manual)`. |
| 3 | **Lembar perbandingan diagram** | `scripts/diagram_comparison.py` — diagram sama, 3 bahasa, 1 HTML. Kroki.io DITOLAK guard keamanan (benar!) → render lokal (plantuml.jar + d2.exe). |
| 4 | **Migrasi PlantUML LOKAL + Kelas B** | Satu commit besar: renderer `_run_plantuml` (jar, smetana, gaya disuntik compiler), Contract B baru (ACT metadata, user_roles, business_flow_steps+diagram, sysreq terstruktur), prompt PlantUML + ATURAN BUKTI. Privasi mermaid.ink TUTUP. Dependency baru: Java 17+ & `tools/plantuml.jar` (gitignored; PLANTUML_JAR di .env). |
| 5 | **Regen esteler terverifikasi** | 8 ACT terisi, semua diagram `@startuml` tanpa theme, arsitektur 5/5 komponen berjejak, Gambar 1-12 & Tabel 1-21 urut. Use case & activity ter-render UML klasik. |
| 6 | **Flag `--yes` run_validation** | Konfirmasi berbayar interaktif menggantung selamanya di shell non-interaktif. |

## Kejadian yang layak diingat

- **"Kredit tidak berkurang, aneh?" — pertanyaan pemilik project membongkar
  proses yang saya kira lambat padahal TIDUR.** Regen pertama 30+ menit status
  `running`, nol koneksi TCP, CPU 1,8 detik: tertahan di `input("Lanjut? [y/N]")`.
  Sinyal biaya = alat diagnosis. Status "running" = proksi.
- **Guard keamanan menolak kroki.io, dan penolakan itu BENAR** — struktur
  aplikasi anggota tim jangan dikirim ke layanan pihak ketiga baru secara
  sepihak. Solusi lokalnya justru lebih baik (privasi + kecepatan + tanpa limit).
- **PlantUML menggambar syntax error sebagai PNG** (exit non-nol) — kalau cuma
  percaya stdout, gambar error ter-embed jadi "diagram". Dikunci test.
- Pandoc menulis `No.\xa0Activity` (non-breaking space) — audit string-match
  saya gagal padahal dokumennya benar. Proksi lagi, kali ini di alat auditnya.

## Kalau melanjutkan besok, mulai dari sini

**Prioritas sesuai roadmap pemilik:**

1. **Minta pemilik BACA docx esteler baru** —
   `scripts/validation/out/esteler-flask__SDD.docx` (432 KB). Bentuk sudah ≈
   acuan; yang bisa menilai "sesuai sempurna" tinggal mata manusia. Kalau ada
   yang kurang, itu daftar kerja berikutnya.
2. **Baru pindah ke UAT** (tahap b roadmap): bandingkan uat_template dengan
   dokumen acuan UAT (kalau pemilik punya PDF-nya — minta!), perlakukan seperti
   SDD sesi ini.
3. Regen petclinic (~$0,25) opsional — cross-check prompt PlantUML di Java.
4. Kasus fastapi (ATURAN BUKTI) masih terbuka: perlu regen fastapi murah untuk
   melihat apakah kotak Database yang dikarang hilang.

**Menggantung dari sesi-sesi lalu (masih berlaku):**
- Revoke `GOOGLE_API_KEY` & `LLAMA_API_KEY` (4 sesi menggantung).
- Isi `GITHUB_TOKEN` di .env.
- Ablasi endpoint esteler (~$0,15) — masih uji nilai/biaya terbaik.
- ZIP → dokumen belum tersambung (relevan lagi karena visi penguji menyebut ZIP).
- Keputusan jejak screenshot di riwayat git.
- Uvicorn `--reload` dev server pemilik masih jalan di port 8000 (sejak 12:43).

## Yang perlu dilakukan manusia

- **Baca `esteler-flask__SDD.docx` yang baru** — khususnya bab Activity Diagram
  (tabel ACT + langkah bernomor) dan ketiga diagram pertama. Layak kirim klien?
- Dua tugas lama: revoke API key lama, isi GITHUB_TOKEN.
