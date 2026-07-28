# Catatan Serah-Terima — 2026-07-28

> **File ini ditimpa habis setiap sesi baru.** Isinya foto sesaat: di mana posisi
> terakhir dan dari mana sebaiknya melanjutkan. Untuk yang **baru melanjutkan
> kerja orang lain, baca file ini dulu.**
>
> Tiga file, tiga peran: **CLAUDE.md** = pengetahuan permanen produk (arsitektur,
> kontrak, keterbatasan) — baca untuk paham produknya. **SESSION.md** (ini) =
> posisi terakhir. **CHANGELOG.md** = riwayat detail per-perubahan (entri teratas
> = paling baru). Kalau bertentangan, **CLAUDE.md yang benar.**

---

## ✅ STATUS: semua ter-commit & push ke `develop`

`HEAD` lokal = `origin/develop` = **`0eb67b7`**, working tree bersih. Tidak ada
kerja menggantung. **369 test hijau** (`pytest`), `vite build` & `oxlint` bersih.

Branch kerja: **`develop`** (bukan `main`). Commit langsung ke `develop`.

---

## 🚀 SETUP CEPAT (untuk yang baru mengambil alih)

`.env` dan `frontend/.env.local` **di-gitignore** — jadi kamu TIDAK dapat file
itu dari `git clone`. Kamu harus membuatnya sendiri. Ini penyebab #1 orang baru
gagal jalan.

```bash
# 1. Backend
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env          # lalu ISI minimal: ANTHROPIC_API_KEY
python -c "import pypandoc; pypandoc.download_pandoc()"   # sekali, untuk .docx
# plantuml.jar: unduh sekali dari github.com/plantuml/plantuml/releases -> tools/plantuml.jar
# (butuh Java 17+ di PATH untuk render diagram)

# 2. Frontend
cd frontend && npm install && cd ..

# 3. Jalankan (dua terminal)
uvicorn app.main:app --reload --port 8000     # -> /docs
cd frontend && npm run dev                    # -> localhost:5173
```

**Auth OPSIONAL** — kalau `.env` TIDAK punya `SUPABASE_URL`, aplikasi jalan **mode
dev tanpa login** (semua job milik "anonymous"). Jadi kamu bisa langsung kerja
tanpa Supabase. Untuk menghidupkan login lihat bagian Auth di bawah.

**Deploy sekali jalan** (butuh Docker Desktop nyala): `docker compose up --build`
→ app utuh di `http://localhost:8000`. Detail: **`DEPLOY.md`**.

---

## APA YANG DIKERJAKAN SESI-SESI TERAKHIR (semua sudah di `develop`)

Semua $0 kecuali disebut, semua ber-tes. Detail lengkap di **CHANGELOG.md**.

1. **Adaptasi template upload lebih tahan (V2)** — `template_spec_service` kini
   membaca judul bab di **text box** & judul bernomor tanpa style (dulu 7 bab
   hilang senyap); deteksi jenis dokumen sinyal-terkuat-menang; `mapping_health`
   berteriak saat peta bab tipis.
2. **Evaluator mutu isi** (`scripts/evaluate_document.py`) — grounding/
   representasi/konsistensi, disambung ke `render_fixtures`. Menangkap karangan.
3. **premco**: tiap activity diagram jadi **sub-bab 2.N** (Heading 3, masuk TOC);
   judul footer di-bake (tampil tanpa update field); Daftar Isi/Gambar/Tabel jadi
   Heading 1 → **TOC 20/20 cocok acuan**; **ekspor `.drawio`** per job
   (`GET /documents/jobs/{id}/diagrams`).
4. **Auth Supabase + isolasi per-pengguna** — lihat bagian Auth di bawah.
5. **Deploy**: `Dockerfile` (bundel Java/pandoc/plantuml) + `docker-compose.yml` +
   `DEPLOY.md` berisi penilaian jujur "Kesiapan SaaS". FastAPI menyajikan SPA
   same-origin (satu container = app utuh).
6. **Redesain UI bergaya Apple** — 3 file CSS + AuthGate. Logika tak tersentuh.

---

## AUTH (yang baru & paling penting untuk dipahami)

Satu seam: `app/services/auth_service.py`. Sisa app cuma bergantung pada
`Principal` (siapa pemanggil), bukan Supabase/JWT.

- **Mode dipilih dari env**: `SUPABASE_URL` kosong → dev/anonymous (tanpa login).
  Terisi → auth aktif (frontend login Supabase → JWT → backend verifikasi).
- Verifikasi menerima **HS256** (JWT Secret) & **ES256/RS256** (JWKS asimetris).
  Project Supabase yang dipakai sekarang **asimetris (ES256)** → `SUPABASE_JWT_SECRET`
  dibiarkan KOSONG (verifikasi lewat JWKS).
- **Isolasi**: kolom `owner` di `jobs`; job orang lain → **404**. Diuji end-to-end.
- Menghidupkan auth: isi `.env` (`SUPABASE_URL=https://<ref>.supabase.co`) DAN
  `frontend/.env.local` (`VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`). Contoh:
  `frontend/.env.local.example`. **Kredensial Supabase milik pemilik project** —
  minta ke dia, atau pakai project Supabase sendiri, atau jalan mode dev.
- Penjaga sesungguhnya di FastAPI (bukan RLS Supabase), karena FE tak konek
  langsung ke DB.

---

## DARI MANA MELANJUTKAN — roadmap "jadi SaaS"

Dua penghalang utama SaaS sudah tertutup sesi ini: **auth/identitas** &
**deployability**. Sisanya (urut prioritas rekomendasi):

**Tingkat 1 — melengkapi multi-tenant: SELESAI SELURUHNYA (2026-07-28).** Ketiga
butirnya tertutup; lanjut ke Tingkat 2 hanya sesudah framing di bawah diputus.
1. ~~**Isolasi template upload per-pengguna**~~ — **SELESAI** (issue #9, 2026-07-28
   lanjutan 2; lihat CHANGELOG). `owner` di manifest template + `compiler_service.
   visible_to` + `Principal` di `routes_template` & `/documents/generate`. Isolasi
   data kini LENGKAP: job/dokumen DAN template. Built-in `default`/`premco`
   sengaja tetap bersama.
2. ~~**Halaman "Dokumen Saya"**~~ — **SELESAI** (issue #10, PR #19, dikerjakan
   rekan paralel dengan #9). `GET /documents/jobs` + panel `DocumentsPanel`.
   Butir ini sempat tertinggal tak-tercoret di sini saat merge; dicoret 2026-07-28
   lanjutan 3.
3. ~~**Rate limiting per-akun**~~ — **SELESAI** (issue #11, 2026-07-28 lanjutan 3;
   lihat CHANGELOG). `rate_limit_service` + dependency `rate_limited_generate` /
   `rate_limited_template_upload`; 429 + `Retry-After`. Kuota dihitung dari tabel
   `jobs` & manifest template yang sudah tersimpan — benar lintas-worker & tahan
   restart tanpa Redis. Mode dev (auth mati) sengaja tak dibatasi.

**Tingkat 2 — mesin SaaS berbayar (besar, keputusan bisnis):**
4. Billing/metering + kuota (Stripe; seam `owner` sudah ada).
5. Worker queue (Redis+RQ) + Postgres — untuk skala horizontal & durabilitas job
   (`BackgroundTasks` kehilangan job kalau proses mati). `job_store` sudah rata
   untuk pindah ke Postgres.

**Tingkat 3 — operasional/legal (kalau benar-benar publik):** monitoring/Sentry,
HTTPS/domain, privacy policy/ToS + ekspor-hapus data.

Framing penting yang belum diputus pemilik: target **tool multi-tenant untuk satu
organisasi** (Tingkat 1 sudah cukup, billing tak relevan) atau **SaaS publik
berbayar** (butuh Tingkat 2). Tanyakan sebelum masuk Tingkat 2.

---

## GATE BERBAYAR & DEPENDENCY (belum dituntaskan — butuh keputusan/uang)

- **Build image Docker belum pernah dijalankan** — Docker Desktop belum nyala di
  mesin ini. Bukti final "benar-benar deploy". `docker compose up --build`; kalau
  gagal biasanya versi pandoc/plantuml di `Dockerfile` (URL sudah diverifikasi
  resolve).
- **Sonnet 5 vs Opus 4.8 belum dibandingkan langsung** untuk kualitas dokumen
  (~$1 sekali bayar). Produk menjual kualitas dokumen — asumsi lama menggantung.
- **Karangan fastapi** belum diverifikasi ulang sesudah "ATURAN BUKTI" masuk
  prompt (~$0,2 regen).
- **Daftar Isi auto-terisi tanpa Ctrl+A F9** butuh **LibreOffice headless**
  (belum terpasang) — keputusan dependency pemilik.
- **Batas 4-`case` per `switch`** di prompt diagram belum diverifikasi ke LLM.

---

## PRINSIP KERJA (jangan diabaikan — ini mengubah CARA kerja)

Ada di CLAUDE.md bagian "Prinsip Kerja", tapi yang paling sering menyelamatkan:
1. **Buka/ukur barangnya, jangan menebak dari proksi** — buka PDF/docx, ukur
   token, render diagram lalu LIHAT. Untuk verifikasi visual $0: render → bake
   Word COM → PDF → raster PyMuPDF → lihat.
2. **Fixture N=1 buta bug antar-item** — uji dengan ≥2 item.
3. **Test hijau ≠ produk jalan** — mock menyembunyikan bug nyata; verifikasi ke
   repo/dokumen NYATA.
4. **Kelayakan fitur besar dibuktikan $0 dulu** (scratchpad) sebelum tulis kode
   `app/` atau bayar LLM.
5. **Jujur soal batas mengalahkan mengarang** — isi yang bisa diturunkan dari
   kode; kosongkan (placeholder terlihat) yang tidak.
