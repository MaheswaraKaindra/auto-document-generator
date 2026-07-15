# Catatan Sesi — 2026-07-15 (sesi lanjutan)

> **File ini ditimpa habis setiap sesi baru.** Isinya cuma satu hal: apa yang
> dikerjakan sesi kemarin, supaya sesi berikutnya tidak mulai dari nol.
>
> Bedanya dengan `CLAUDE.md`: CLAUDE.md itu **pengetahuan permanen** tentang
> produk ini (arsitektur, kontrak, keterbatasan) dan tumbuh pelan-pelan.
> SESSION.md itu **foto sesaat** — dibuang begitu sesi berikutnya selesai.
> Kalau isinya bertentangan, **CLAUDE.md yang benar.**

---

## Ringkasan satu paragraf

Mengerjakan prioritas #1 sesi sebelumnya: penanda `(diisi manual)` sekarang
ditanyakan lewat form, jadi dokumennya keluar utuh. Jumlahnya ternyata **28**,
bukan 16 — 25 ditutup lewat form, 3 sengaja dibiarkan (tanda tangan & sertifikasi
hasil UAT tidak seharusnya diisi sistem). 91 test hijau. **Biaya API sesi ini: $0**
— fitur ini tidak menyentuh LLM sama sekali, jalurnya metadata → template → docx.

Sudah di-commit ke `develop` (belum di-push, belum ada PR): satu commit fitur
(kode + test + entry CLAUDE.md) dan satu commit SESSION.md, mengikuti konvensi
repo yang memisahkan commit "Catat ..." dari commit kode.

---

## Yang dikerjakan

| Berkas | Perubahan |
|---|---|
| `app/api/schemas_document.py` | **baru**: `DocumentMetadata` (25 field, semua `Optional`) + `document_metadata` di `GenerateDocumentRequest` |
| `app/services/compiler_service.py` | `_MetadataDict.__missing__` → fallback `*(diisi manual)*`; param baru `document_metadata` di `generate_docx()` |
| `app/templates/sdd_template.md` | 17 penanda → `{{ meta.* }}`; blok Persetujuan diperjelas kalimatnya |
| `app/templates/uat_template.md` | 8 penanda → `{{ meta.* }}`; 2 blok tanda tangan/sertifikasi diperjelas |
| `app/api/routes_document.py` | teruskan `document_metadata` ke compiler |
| `frontend/src/App.jsx` + `App.css` | section `<details>` "Informasi Dokumen (opsional)", tertutup default, field didefinisikan sebagai data |
| `tests/` | +9 test (total 91), termasuk penjaga typo field di template |

---

## Keputusan yang diambil (dan alasannya — jangan dibalik tanpa baca ini)

1. **Angka 16 di CLAUDE.md salah, yang benar 28** (18 SDD + 10 UAT). Hitungan lama
   cuma mencacah SDD, itu pun melewatkan blok terbesarnya — tabel Demografi (7
   baris). UAT tidak dihitung sama sekali. Sudah dikoreksi di CLAUDE.md.

2. **Targetnya bukan "nol placeholder", tapi "nol placeholder yang manusianya
   sudah tahu jawabannya saat generate".** 3 dibiarkan sengaja: dua blok tanda
   tangan (tanda tangan bukan data yang diketik di form — dokumen acuan enterprise
   juga mengosongkannya) dan Sertifikasi Keberhasilan UAT (isinya tanggal
   penyelesaian + hasil Lolos/Gagal; menanyakannya di form = mengundang orang
   mensertifikasi tes yang belum dijalankan). Kalimatnya diubah supaya terbaca
   sebagai desain, bukan lubang kelupaan.

3. **Semua field opsional** (keputusan pemilik project). Perilaku lama jadi
   *lantai*: form boleh dilewati total → dokumen seperti versi sebelumnya. Kalau
   field diwajibkan, repo tanpa konteks enterprise (proyek open-source yang tidak
   punya nomor RFC) jadi tidak bisa digenerate sama sekali — padahal produk ini
   diposisikan sebagai SaaS generik.

4. **`DocumentMetadata` terpisah dari `DocumentContent` (Contract B).** Contract B
   itu output LLM, ini input manusia — arahnya berlawanan. Digabung = LLM disuruh
   mengarang nomor RFC.

5. **Cuma `dev_system_type` yang jadi dropdown**, sisanya teks bebas. Alasannya
   template-nya sendiri yang menyatakan pilihannya ("ERP / NON ERP"). Mengarang
   enum untuk Document Classification akan memaksa pengguna ikut istilah kita.

---

## Cara verifikasinya (semua gratis, tidak ada panggilan LLM)

- **91 test hijau** (82 lama + 9 baru) — tidak ada regresi.
- **Mutation check**: hapus satu field mana pun dari 17 field SDD → penandanya
  balik tepat 1×; lengkap → 0×. Membuktikan pemetaan field↔lubang 1:1, dan
  membuktikan test "tidak ada penanda tersisa" itu benar-benar bisa merah.
- **Cross-check 3 lapis**: field di `App.jsx` (25) == field di schema (25) ==
  field yang dipakai template (17 SDD + 8 UAT). Ini penting karena typo di form
  akan **diabaikan diam-diam** oleh Pydantic, bukan error.
- **Docx sungguhan dibaca ulang** (bukan cuma assert substring) — tabel Informasi
  Dokumen & Demografi terisi, blok tanda tangan tetap ada.
- **SSR render** komponen React: 19 input / 2 textarea / 2 select, `<details>`
  tertutup default. Build lolos ≠ render lolos, jadi ini dicek terpisah.
- **Server hidup** (`/openapi.json`): 25 field terdaftar, `document_metadata`
  opsional, `required` tetap `['document_type', 'repositories']` → klien lama aman.

---

## Kalau melanjutkan besok, mulai dari sini

1. **Tabel Revision History masih keluar sebagai baris kosong** — temuan baru sesi
   ini, sudah dicatat di Keterbatasan CLAUDE.md. Tiga tabel (Document + Application
   Revision History di SDD, Version History di UAT) punya header tapi isinya
   `| | | | | |`. Luput dari hitungan 28 karena bentuknya bukan penanda `(diisi
   manual)`, tapi dampaknya sama: dua tabel kosong di halaman pertama SDD, persis
   di bawah tabel yang sekarang terisi rapi. Sebagian datanya sudah ada di
   `DocumentMetadata`. **Butuh keputusan produk dulu**, bukan sekadar coding:
   kolom `Summary of Changes` tidak punya jawaban jujur untuk dokumen yang baru
   pertama kali digenerate.
2. **Async + database** — penghalang produksi paling diremehkan, dan **item teknis
   teratas** kalau tidak mau menunggu keputusan produk di #1. Generation ~100-125
   detik ditahan di satu request HTTP sinkron; proxy/load balancer umumnya memutus
   di 30-60 detik, jadi ini patah begitu di-deploy walau di localhost aman. Plus:
   tidak ada DB sama sekali, dokumen hilang setelah response terkirim.
3. **Tambah 2-3 aplikasi bisnis ke `repos.json`** — celah validasi terbesar. Dari 7
   repo, cuma `realworld` yang aplikasi bisnis berbahasa didukung, dan itu pun
   aplikasi contoh yang sengaja rapi. Tahap 1 gratis; Tahap 2 ~$0,15-0,30 per repo.
4. **Bandingkan Sonnet 5 vs Opus** (~$0,30 sekali bayar) — default pindah ke Sonnet
   5 atas dasar **reputasi umum, bukan pengukuran**. Produk ini menjual kualitas
   dokumen; jangan gantung lama.
5. **Larang diagram menggambar komponen tanpa bukti** — fastapi punya nol dependency
   database tapi diagramnya tetap menggambar `Backend → Database`.
6. **Heuristik `type`** — prioritas **rendah**, terbukti bukan bottleneck. Jangan
   kerjakan sebelum yang di atas.

Belum dikerjakan dan bukan bug, cuma memang belum: parser di luar Python/TS-JS,
test untuk `parser_service.py`, OAuth GitHub (masih scaffold), bagian atas form
masih polos tanpa penjelasan, mermaid.ink masih layanan pihak ketiga (isu privasi
untuk repo confidential).

---

## Yang perlu dilakukan manusia (tidak bisa saya kerjakan)

- **Revoke `GOOGLE_API_KEY` dan `LLAMA_API_KEY`.** Sudah dihapus dari `.env`
  lokal, tapi **kuncinya masih hidup** di penyedia masing-masing sampai dicabut
  lewat console. Menghapus baris ≠ mencabut kunci. (Masih belum dilakukan.)
- **Isi `GITHUB_TOKEN`** kalau mau sering menjalankan validasi. Tidak wajib sejak
  pindah ke tarball (~3 request/repo), tapi batas anonim 60/jam gampang habis.
- **Buka form-nya dan lihat sendiri** (`npm run dev` → section "Informasi Dokumen").
  Saya sudah verifikasi render lewat SSR, tapi apakah 17 field terasa terlalu
  banyak atau labelnya membingungkan — itu penilaian manusia.
