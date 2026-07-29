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

## Tinggal colok (config/integrasi standar, bukan kerja arsitektur)

- **Auth provider** — seam-nya sudah ada (`auth_service`); mengaktifkan = isi
  `SUPABASE_URL`. Ganti ke Auth0/Cognito = ganti isi `verify_token`, tak menyentuh
  route mana pun.
- **Postgres** untuk multi-instance — `job_store` sengaja rata (bukan ORM); pindah
  dari SQLite = arahkan modul itu ke Postgres (mis. Postgres Supabase).
- **Billing** — Stripe dsb. bertumpu pada identitas yang kini SUDAH ada (kolom
  owner); metering per-owner tinggal ditambahkan di titik create job.
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
  pekerjaan terpisah di lapisan reverse proxy.

Klaim yang tahan diuji: **"Deployable sebagai satu service dengan isolasi
per-pengguna; tinggal colok auth provider + (untuk skala) worker queue &
Postgres."** Tiap "tinggal" menunjuk ke seam yang sudah ada; tiap batas disebut
sendiri.
