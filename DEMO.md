# Panduan Demo — auto-document-generator

Panduan mendemokan produk ini ke pembimbing/penguji dalam ~5-7 menit, plus poin
yang ditekankan dan antisipasi pertanyaan. Ditulis supaya kamu bisa presentasi
dengan percaya diri, bukan improvisasi.

> **Intinya satu kalimat:** *"Sistem ini membaca source code sebuah aplikasi lalu
> menulis draf dokumen SDD/UAT `.docx` yang isinya benar-benar diturunkan dari
> kodenya — bukan template kosong, dan bukan karangan."*

---

## 1. Persiapan sebelum demo (checklist)

Lakukan **sebelum** di depan penguji — jangan setup live.

- [ ] `.env` terisi `ANTHROPIC_API_KEY` yang valid (dan ada saldo).
- [ ] `tools/plantuml.jar` ada, **Java 17+** di PATH (`java -version`).
- [ ] Pandoc terpasang (`python -c "import pypandoc; print(pypandoc.get_pandoc_version())"`).
- [ ] Backend jalan: `uvicorn app.main:app --reload` → cek `http://127.0.0.1:8000/docs`.
- [ ] Frontend jalan: `npm --prefix frontend run dev` → buka `http://127.0.0.1:5173`.
- [ ] **Dokumen contoh sudah jadi** sebagai cadangan kalau live gagal
      (mis. `Contoh_SDD_EstelerApp_PREMCO.docx`) — buka duluan di Word supaya
      Daftar Isi/Gambar sudah ter-refresh.
- [ ] Siapkan **satu repo target** yang cepat & hasilnya bagus, mis.
      `https://github.com/yudhasw/esteler-app` (Flask, ~22 file, hasil berjejak).

> **Kenapa siapkan cadangan?** Generation live memanggil AI (~2-3 menit) dan
> butuh internet + saldo. Kalau ada gangguan saat demo, langsung tunjukkan
> dokumen contoh yang sudah jadi — pesan produknya tetap tersampaikan.

## 2. Alur demo (~5 menit)

1. **Buka frontend, jelaskan 1 kalimat** (lihat kotak di atas). Tunjukkan formnya
   rapi & menjelaskan diri (tiap field ada keterangannya).
2. **Isi form:**
   - Nama Project: `Esteler App`
   - Tipe Dokumen: **SDD**
   - Gaya Dokumen: **PREMCO** (sudah default) — sebut "meniru konvensi dokumen
     resmi perusahaan".
   - Sumber Kode: **Repo GitHub** → tempel URL esteler. (Sebut: "bisa juga upload
     ZIP untuk kode yang tidak di GitHub.")
3. **Klik Generate.** Tunjuk **log tahapan** yang muncul — khususnya baris
   *"Membaca kode: 22 file, 38 endpoint, 16 class"*. **Ini momen kunci**: buktikan
   sistem benar-benar membaca kodenya, di detik ke-5, sebelum AI menulis sebaris pun.
4. **Sambil menunggu** (~2-3 menit), buka **dokumen contoh** yang sudah jadi dan
   lakukan langkah 5-6 di situ (jangan diamkan layar menunggu).
5. **Buka `.docx` di Word, sorot bukti "berjejak":**
   - **Deskripsi Aplikasi** — sistem pemesanan kedai, preorder tanpa akun, chatbot AI.
   - **Arsitektur** (Gambar 1) — User → Backend → **PostgreSQL (Neon), Cloudinary,
     Groq AI**. Tegaskan: ketiganya **benar-benar ada di kode** (dependencies +
     docstring), bukan tebakan.
   - **Use Case** — tabel biru per use case; tunjuk Acceptance Criteria yang
     menyebut endpoint asli: `/admin/menu/create`, `/admin/menu//toggle` (soft delete).
   - **Diagram Use Case & Flow Proses Bisnis** — UML rapi, aktor **Admin & Customer**
     (bisnis, bukan "Developer"/"API Client").
6. **Tunjuk yang SENGAJA kosong:** No. RFC, tanda tangan, mockup → `(diisi manual)`.
   Tegaskan: *"Yang tidak bisa diketahui dari kode tidak dikarang — dibiarkan
   sebagai placeholder yang jelas. Itu justru nilai jualnya."*

## 3. Poin nilai jual yang ditekankan

- **Berjejak, bukan generik.** Isinya diturunkan dari aplikasi yang bersangkutan —
  buktinya aktor & fitur yang spesifik ke domain (kedai, preorder, walk-in), bukan
  istilah generik.
- **Jujur soal batas.** Yang tak punya jejak di kode dibiarkan kosong. Dokumen 30
  halaman yang tiap kalimatnya benar > 87 halaman yang separuhnya karangan.
- **Bisa lebih baik dari acuan manusia.** Pada dokumen enterprise 87 halaman yang
  jadi acuan, justru bagian mekanis (Daftar Gambar/Tabel) yang membusuk (menyebut
  aplikasi lain, nomor lompat) — karena membosankan & tak ada yang memeriksa.
  Sistem tak pernah bosan.
- **Privasi:** diagram dirender **lokal** (PlantUML) — isi kode tak meninggalkan mesin.
- **Fleksibel:** sumber GitHub **atau** ZIP; gaya default/premco/template sendiri;
  bahasa Python/TypeScript/JavaScript/Java.
- **Murah:** satu dokumen dari repo kecil ~**$0,10** (Claude Sonnet 5).

## 4. Antisipasi pertanyaan penguji

| Pertanyaan | Jawaban singkat |
|---|---|
| "AI-nya mengarang tidak?" | Ada aturan bukti eksplisit di prompt: dilarang menggambar/menulis yang tak punya jejak di kode. Tunjuk placeholder `(diisi manual)` sebagai buktinya. |
| "Kalau kodenya bahasa lain?" | Python, TS/JS, Java dipahami penuh (endpoint, class). Lain tetap terbaca tapi tanpa detail struktur — AI menyimpulkan dari nama file/fungsi. |
| "Repo besar bisa?" | Ada guard: repo yang metadatanya melebihi context window ditolak lebih awal dengan pesan jelas, bukan gagal setelah bayar. |
| "Sudah dipakai orang?" | Belum di-deploy; ini engine yang sudah matang & terbukti pada repo nyata. Sisa pekerjaan = deployment + autentikasi. |
| "Berapa lama & berapa biaya?" | ~2-3 menit, ~$0,10 per dokumen repo kecil. |
| "Bedanya SDD dan UAT?" | SDD = *aplikasinya seperti apa* (fitur, arsitektur, use case). UAT = *langkah pengujiannya* (siapa menguji apa, hasil diharapkan). Dari repo yang sama. |

## 5. Kalau demo live gagal (plan B)

1. Tetap tenang — sebut "generation live butuh AI & internet; ini hasil yang sudah
   jadi dari repo yang sama."
2. Buka dokumen contoh `.docx` yang sudah disiapkan, lanjutkan dari **langkah 5**.
3. Kalau ditanya kenapa, jawab jujur (saldo/koneksi/timeout) — produk ini menjual
   kejujuran, dan itu termasuk saat demo.

## 6. Kalau diminta menjelaskan arsitektur

Tunjuk diagram di [`README.md`](README.md) (bagian *Cara kerja*):

```
GitHub/ZIP → Parser (Tree-sitter, tanpa AI) → Contract A
           → Claude → Contract B → Jinja2 + PlantUML → Pandoc → .docx
```

Tekankan **pemisahan lewat kontrak JSON**: tiap tahap bisa diganti tanpa merusak
yang lain (ganti sumber kode tak menyentuh parser; ganti AI tak menyentuh
ingestion). Detail tiap tahap ada di [`README.md`](README.md) dan [`CLAUDE.md`](CLAUDE.md).
