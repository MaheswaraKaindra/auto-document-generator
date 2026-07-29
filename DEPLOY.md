# Deploy

Satu image Docker berisi aplikasi utuh — SPA (frontend) **dan** API (backend)
disajikan dari satu URL. `docker run` → app jalan.

## Kenapa image ini ada

Bukan kerapian. Produk ini punya tiga dependency yang canggung untuk di-deploy —
**Java** (untuk render PlantUML), **pandoc** (untuk ekspor `.docx`), dan
**plantuml.jar** — dan justru itu yang biasanya diam-diam meruntuhkan klaim
"tinggal deploy". Image ini membundel ketiganya, jadi klaimnya bukan asumsi.

## Build

```bash
# Tanpa login (mode dev — app jalan, tapi tanpa isolasi pengguna):
docker compose up --build

# DENGAN login Supabase (config frontend itu compile-time Vite, jadi lewat build-arg;
# keduanya PUBLIK — anon key memang dirancang untuk browser):
VITE_SUPABASE_URL=https://<ref>.supabase.co \
VITE_SUPABASE_ANON_KEY=<anon key> \
  docker compose up --build
```

Atau langsung dengan `docker`:

```bash
docker build \
  --build-arg VITE_SUPABASE_URL=https://<ref>.supabase.co \
  --build-arg VITE_SUPABASE_ANON_KEY=<anon key> \
  -t auto-doc-gen .

docker run -p 8000:8000 --env-file .env -v app-data:/data auto-doc-gen
```

Buka **http://localhost:8000** — SPA dan API dari origin yang sama.

## Konfigurasi

| Jenis | Diberikan kapan | Contoh |
|---|---|---|
| **Rahasia & config backend** | saat RUN (`--env-file .env`) | `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `LLM_MODEL` |
| **Config Supabase frontend** | saat BUILD (build-arg) | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` |

Rahasia backend **tidak** di-bake ke image — diberikan saat run. Config frontend
Vite bersifat compile-time (di-inline ke bundle), jadi harus saat build; keduanya
publik sehingga aman di build-arg.

Env backend lengkap ada di `.env.example`. Yang wajib untuk fungsi penuh:
`ANTHROPIC_API_KEY` (LLM). Auth (`SUPABASE_URL`) opsional — kosong = mode dev.

## Persistensi

Data yang harus bertahan melewati restart container di-mount ke `/data`:
DB job (`jobs.db`), dokumen hasil, dan template terkompilasi. `docker compose`
sudah membuat volume `app-data`; dengan `docker run` tambahkan `-v app-data:/data`.
Tanpa volume, riwayat job & template upload hilang saat container dibuat ulang.

Volume ini juga yang membuat **rate limit tahan restart**: kuota dihitung dari
baris `jobs` & manifest template di `/data`, bukan dari memori proses. Tanpa
volume, tiap container baru memulai semua kuota dari nol.

## HTTPS + domain (produksi)

Lokal, `docker compose up` tetap seperti sebelumnya: app di
**http://localhost:8000**, tanpa proxy, tanpa TLS. Reverse proxy ada di balik
compose profile supaya alur kerja itu tidak berubah sama sekali.

Untuk produksi, jalankan dengan profile `proxy`:

```bash
SITE_ADDRESS=docgen.contoh.com docker compose --profile proxy up -d --build
```

Caddy (`./Caddyfile`) meminta sertifikat Let's Encrypt sendiri, memperbaruinya
sendiri, dan meneruskan ke container app lewat jaringan internal compose.
Tidak ada certbot, tidak ada cron.

**Prasyarat di luar repo** — tanpa ketiganya sertifikat tidak akan terbit:

1. Domain di `SITE_ADDRESS` sudah punya **A record ke IP server ini**.
2. **Port 80 dan 443 terbuka** dari internet. Port 80 tetap dibutuhkan walau
   situsnya HTTPS: di situlah Let's Encrypt memverifikasi kepemilikan domain.
3. Port **8000 tidak** perlu dibuka. Sejak #15 ia diikat ke `127.0.0.1`, jadi
   satu-satunya jalan masuk adalah lewat proxy.

Menguji jalur proxy tanpa domain: jalankan tanpa `SITE_ADDRESS` (default
`localhost`) — Caddy memakai sertifikat internalnya sendiri, browser akan
memperingatkan, dan itu memang wajar. Ini membuktikan proxy meneruskan dengan
benar; ia **tidak** membuktikan penerbitan sertifikat publik.

Uvicorn dijalankan dengan `--proxy-headers` (lihat `Dockerfile`) supaya log akses
menyebut pengunjung sebenarnya, bukan IP proxy, dan supaya `request.url.scheme`
benar untuk kode yang kelak membangun URL absolut. Sifatnya **pencegahan**: hari
ini tak ada kode aplikasi yang membaca skema atau IP klien.

## CORS

Diatur lewat `ALLOWED_ORIGINS` (dipisah koma). Kosong = dev server Vite saja.

Sebagian besar deploy **tidak perlu menyentuhnya**: SPA disajikan dari origin
yang sama dengan API, jadi tak ada permintaan lintas-origin sama sekali. Yang
perlu mengisinya cuma deploy yang menaruh frontend di domain berbeda:

```bash
ALLOWED_ORIGINS=https://app.contoh.com
```

Tulis tanpa garis miring di ujung (browser mengirim `Origin` tanpa itu; kalau
tak cocok, gagalnya senyap — konfigurasinya memangkasnya untuk berjaga-jaga).
`*` masih boleh tapi harus ditulis sendiri, dan mencatat peringatan saat startup.

## Rahasia di produksi

`--env-file .env` cukup untuk satu VPS milik sendiri, dan itu yang diasumsikan
compose di repo ini. Yang harus benar apa pun caranya:

- **Jangan** taruh rahasia di build-arg atau `ENV` Dockerfile — ia ikut ke image
  dan ke riwayat layer. Rahasia backend diberikan saat **run**. (`VITE_*` adalah
  pengecualian yang disengaja: keduanya memang publik.)
- File `.env` di server: `chmod 600`, milik user yang menjalankan Docker.
- **`POSTGRES_PASSWORD` punya default `adgdev`** di compose — itu untuk mesin
  pengembang. Setel sendiri sebelum deploy publik.
- Rotasi `ANTHROPIC_API_KEY` kalau pernah ter-commit atau terkirim di chat.

Untuk platform yang punya penyimpanan rahasia sendiri (Fly/Railway/Render,
Docker Swarm, AWS Secrets Manager), pakai itu dan jangan mengirim `.env` ke
server: aplikasi cuma membaca **environment variable**, dan `python-dotenv`
hanya mengisi yang belum ada. Jadi tidak ada kode yang perlu berubah — env yang
di-inject platform langsung terpakai.

## Versi tool

Dipatok di `Dockerfile` (bukan "apa pun yang terbaru") supaya image reproducible:
`PANDOC_VERSION`, `PLANTUML_VERSION`. Naikkan lewat `--build-arg` bila perlu.

## Reverse proxy + HTTPS + domain (produksi, #15)

Compose lokal membuka app di `http://localhost:8000` (HTTP polos) — cukup untuk
`docker compose up` di mesin sendiri, TIDAK untuk publik. Untuk domain + HTTPS,
ada overlay `docker-compose.prod.yml` yang menaruh **Caddy** di depan container:

```bash
DOMAIN=app.domain.com TLS_EMAIL=you@domain.com \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Yang terjadi:
- Caddy mengambil sertifikat **Let's Encrypt otomatis** untuk `$DOMAIN` (tanpa
  certbot/renew manual) dan meneruskan trafik ke `app:8000` lewat jaringan
  internal compose.
- `app` **tak lagi** mengekspos `8000` ke publik — hanya Caddy (80/443) yang
  menghadap internet.
- **Syarat agar TLS terbit**: DNS `$DOMAIN` sudah menunjuk ke IP server ini, dan
  port 80 + 443 terbuka (Let's Encrypt memverifikasi lewat keduanya). Ini bagian
  yang butuh server & domain NYATA — tak bisa dibuktikan dari mesin dev.

Config Caddy ada di `deploy/Caddyfile` (termasuk header keamanan: HSTS,
X-Content-Type-Options, X-Frame-Options). Ganti ke nginx/Traefik = ganti file
proxy-nya, sisa compose tetap.

## CORS

Diperketat dari `*` ke daftar origin lewat `CORS_ALLOW_ORIGINS` (koma-pisah).
Default (kosong) = origin dev Vite (`localhost:5173`) — jadi `npm run dev` tetap
jalan, tapi sudah bukan `*`. **Saat SPA disajikan same-origin oleh container**
(bawaan image ini, termasuk di balik Caddy satu domain), **CORS tak terpakai** —
tak perlu menyetel apa pun. CORS baru relevan kalau frontend dilayani dari domain
BERBEDA; isi `CORS_ALLOW_ORIGINS=https://app.domain.com` untuk kasus itu.

## Rahasia di produksi

`--env-file .env` cukup untuk satu server, tapi menaruh rahasia sebagai file di
disk bukan praktik terbaik lintas platform. Alih-alih itu, suntikkan lewat
mekanisme rahasia platform (Docker/Swarm secrets, Kubernetes Secret, atau env
terenkripsi milik penyedia) — kode membaca dari `os.getenv`, jadi sumbernya tak
mengubah aplikasi. Yang **tak boleh**: `.env` ikut ter-commit (sudah di-gitignore)
atau ter-bake ke image (Dockerfile sengaja memberi rahasia saat RUN, bukan build).

---

# Kesiapan SaaS — apa yang siap, apa yang tinggal colok, apa batasnya

Ditulis jujur supaya klaimnya tahan diuji.

## Siap sekarang (bisa ditunjuk)

- **Deployable satu perintah** — image ini; SPA + API satu origin; dependency
  canggung (Java/pandoc/plantuml) terbundel, bukan diasumsikan.
- **Identitas & isolasi per-pengguna** — auth Supabase (JWT diverifikasi backend,
  HS256 & ES256/RS256), dokumen difilter per-owner. Job pengguna lain → 404.
  Diuji end-to-end (bukan cuma unit test).
- **Konfigurasi lewat env** — rahasia tak ter-hardcode; ganti model/DB/provider
  tanpa sentuh kode.
- **Pipeline tahan** — async + reaper job basi + pembersihan dokumen kedaluwarsa
  + guard context window.
- **Isolasi per-pengguna LENGKAP** — job/dokumen DAN template hasil upload
  ber-`owner`; built-in `default`/`premco` sengaja tetap milik bersama (gaya
  bawaan produk, bukan data siapa pun).
- **Rate limit per-akun di endpoint berbayar** — `/documents/generate` &
  `POST /templates` dibatasi (default 10 & 20 per jam, jendela sliding, atur
  lewat env). Kuota habis = 429 + `Retry-After`, bukan job berbayar baru.
  Penghitungnya dari `jobs` & manifest template yang sudah tersimpan, jadi
  **benar walau `--workers` > 1 dan tak hilang saat restart** — tanpa Redis.

- **Kendali data pengguna** — `GET /me/export` (unduh semua datanya) dan
  `DELETE /me/data` (hapus semuanya; catatan biaya dianonimkan, bukan dihapus).
  Keduanya menolak jalan saat auth mati, sebab di sana semua orang adalah satu
  identitas anonim yang sama. Halaman `/privacy` & `/terms` tersedia publik.

## Tinggal colok (config/integrasi standar, bukan kerja arsitektur)

- **Auth provider** — seam-nya sudah ada (`auth_service`); mengaktifkan = isi
  `SUPABASE_URL`. Ganti ke Auth0/Cognito = ganti isi `verify_token`, tak menyentuh
  route mana pun.
- **Postgres** untuk multi-instance — `job_store` sengaja rata (bukan ORM); pindah
  dari SQLite = arahkan modul itu ke Postgres (mis. Postgres Supabase).
- **Billing** — Stripe dsb. bertumpu pada identitas yang kini SUDAH ada (kolom
  owner); metering per-owner tinggal ditambahkan di titik create job.
- **HTTPS/domain** — config-nya kini ADA di repo (`Caddyfile` + profile `proxy`
  di compose + `--proxy-headers`), jadi yang tersisa bukan lagi pekerjaan
  arsitektur: arahkan DNS ke server, buka port 80/443, jalankan dengan
  `SITE_ADDRESS`. **Sengaja tetap di bagian ini, bukan "Siap sekarang":**
  penerbitan sertifikat hanya terjadi terhadap domain sungguhan, jadi belum ada
  yang bisa ditunjuk. Yang sudah bisa ditunjuk cuma jalur proxy-nya di
  `localhost` (sertifikat internal).
- **HTTPS/domain** — overlay Caddy SUDAH disediakan (`docker-compose.prod.yml` +
  `deploy/Caddyfile`, TLS otomatis). "Colok"-nya = arahkan DNS domain ke server +
  jalankan overlay dengan `DOMAIN`/`TLS_EMAIL`. Lihat "Reverse proxy" di atas.

## Batas yang JUJUR (bukan "tinggal setup")

- **Skala horizontal** butuh worker queue sungguhan. `BackgroundTasks` jalan
  di dalam proses web; job mati kalau proses mati (reaper menandainya gagal, tapi
  kerja hilang). Untuk banyak instance / serverless: pindah eksekusi ke Redis+RQ
  atau sejenisnya. Ini perubahan arsitektur, bukan config.
- **Rate limit TIDAK berlaku tanpa auth.** Batasnya per-AKUN, dan saat
  `SUPABASE_URL` kosong semua pemanggil adalah satu identitas anonim yang sama —
  jadi deploy publik tanpa auth tak terlindungi olehnya. Ini disengaja (mode dev
  harus tetap jalan penuh & $0), tapi artinya: **deploy publik = isi
  `SUPABASE_URL`.** Kalau butuh batas per-IP untuk instance tanpa auth, itu
  pekerjaan terpisah di lapisan reverse proxy — dan **proxy Caddy yang kini ada
  TIDAK menutupinya**: batas laju bukan direktif bawaan Caddy, ia butuh plugin
  dan build image sendiri. Jangan anggap kehadiran proxy sudah menjawab ini.

- **Teks privacy/ToS belum sah dipakai.** Mekanismenya ada dan halamannya
  tersaji, tapi isinya masih draf: setiap penanda `[ISI: ...]` harus diganti
  dengan fakta sebenarnya (nama entitas, yurisdiksi, kontak, retensi log,
  kebijakan refund, batas tanggung jawab), lalu ditinjau orang yang berwenang
  secara hukum. Uraian TEKNIS di dalamnya akurat terhadap kode — akurasi teknis
  bukan kelayakan hukum. Selama penanda masih ada, halamannya mengumumkan
  dirinya sebagai draf, jadi tak ada risiko diam-diam terlihat final.

Klaim yang tahan diuji: **"Deployable sebagai satu service dengan isolasi
per-pengguna; tinggal colok auth provider + (untuk skala) worker queue &
Postgres."** Tiap "tinggal" menunjuk ke seam yang sudah ada; tiap batas disebut
sendiri.
