import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    """Env numerik, gagal BERISIK kalau tak masuk akal.

    Batas rate limit yang salah-ketik ("sepuluh", "10 ", "-1") tak boleh diam-diam
    jatuh ke default: yang dikira "batas 10/jam" bisa jadi TANPA batas sama sekali,
    dan itu baru ketahuan lewat tagihan. Salah konfigurasi harus menggagalkan
    startup, bukan mengubah kebijakan tanpa memberi tahu siapa pun.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as e:
        raise ValueError(f"{name} harus bilangan bulat, dapat {raw!r}.") from e
    if value < 0:
        raise ValueError(f"{name} tak boleh negatif, dapat {value}. Pakai 0 untuk mematikan batas.")
    return value

def _origins_env(name: str, default: list[str]) -> list[str]:
    """Daftar origin dipisah koma, dinormalkan supaya salah-tulis tak diam-diam.

    Browser mengirim header `Origin` TANPA garis miring di ujung
    (`https://app.contoh.com`, bukan `https://app.contoh.com/`), dan
    CORSMiddleware mencocokkannya sebagai string persis. Jadi satu garis miring
    yang tak sengaja ikut ter-copy membuat origin itu TIDAK PERNAH cocok —
    tanpa error di server, cuma request yang ditolak browser. Dipangkas di sini.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Model yang dipakai APLIKASI untuk menulis dokumen. Ini TIDAK ada hubungannya
# dengan model yang dipakai Claude Code saat mengerjakan project ini (itu diatur
# lewat perintah /model) — keduanya terpisah total.
#
# Default Sonnet 5: kualitasnya mendekati Opus untuk banyak tugas dengan biaya
# jauh lebih rendah (~$2/$10 per 1M token harga intro s/d 2026-08-31, vs $5/$25
# Opus 4.8). Ganti ke "claude-opus-4-8" lewat .env kalau kualitas dokumen ternyata
# turun — perbandingannya belum diuji langsung, lihat Keterbatasan di CLAUDE.md.
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")

# SQLite untuk status job + path dokumen. Sengaja BUKAN di folder temp: generation
# itu async sekarang, dan seluruh gunanya database ini adalah bertahan melewati
# response — bahkan melewati restart. DB di temp akan hilang diam-diam dan
# meninggalkan riwayat yang menunjuk ke file yang sudah tidak ada.
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/jobs.db")

# Postgres untuk state BERSAMA lintas mesin (#13). Kosong = SQLite di
# DATABASE_PATH di atas — dan itu tetap default karena multi-worker di SATU mesin
# sudah jalan dengan SQLite (state-nya file di disk, bukan dict di memori; lihat
# CLAUDE.md). Yang TIDAK bisa dilakukan file SQLite adalah dibagi antar CONTAINER
# atau host — begitu web dan worker hidup terpisah, mereka butuh ini.
#
# Bentuk: postgresql://user:sandi@host:port/nama_db
DATABASE_URL = os.getenv("DATABASE_URL")

# Direktori tempat template hasil-KOMPILASI upload user disimpan (V2). Persisten
# seperti DATABASE_PATH — template terdaftar (template Jinja hasil-generate +
# reference.docx tersintesis + manifest) harus bertahan melewati restart, sama
# alasannya dengan DB job. Kosong = data/templates (di-gitignore lewat data/).
TEMPLATES_STORE_PATH = os.getenv("TEMPLATES_STORE_PATH", "data/templates")

# Path ke plantuml.jar untuk merender diagram secara LOKAL (butuh Java 17+ di
# PATH). Rendering diagram pindah dari mermaid.ink (layanan hosted) ke PlantUML
# lokal pada 2026-07-16: (1) isi diagram — nama endpoint, struktur komponen —
# tidak lagi dikirim ke internet; (2) gaya UML-nya (aktor stick-figure, oval use
# case) cocok dengan dokumen acuan enterprise. Unduh sekali dari
# https://github.com/plantuml/plantuml/releases (asset plantuml-<versi>.jar).
PLANTUML_JAR = os.getenv("PLANTUML_JAR", "tools/plantuml.jar")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback")

# --- Autentikasi (Supabase) -------------------------------------------------
# Identitas pengguna untuk mengisolasi dokumen per-akun. INI SATU-SATUNYA seam
# auth: kalau SUPABASE_URL kosong, aplikasi jalan mode ANONYMOUS (dev) — semua
# job jadi milik "anonymous", tak ada yang ditolak. Begitu diisi, backend
# memverifikasi JWT Supabase yang dikirim frontend dan memfilter data per-owner.
# Jadi "pasang auth" harfiah = isi tiga env ini, bukan mengubah kode.
#
# SUPABASE_URL         : https://<ref>.supabase.co (Project Settings -> API).
# SUPABASE_JWT_SECRET  : "JWT Secret" (Project Settings -> API -> JWT Settings).
#                        Untuk project ber-signing-key ASIMETRIS, kosongkan —
#                        backend verifikasi lewat JWKS yang diturunkan dari URL.
# SUPABASE_JWT_AUD     : audience token; Supabase memakai "authenticated".
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_JWT_AUD = os.getenv("SUPABASE_JWT_AUD", "authenticated")

# --- Rate limiting per-akun -------------------------------------------------
# Tiap POST /documents/generate memicu panggilan Claude BERBAYAR, jadi tanpa batas
# satu akun (atau token yang bocor) bisa membengkakkan tagihan tanpa ada yang
# menyadarinya sampai akhir bulan. Batas dikunci ke identitas yang sudah ada
# (`Principal.id`) — lihat `rate_limit_service`.
#
# Jendelanya SLIDING (bukan "reset tiap jam bulat"): batas per-jam yang di-reset
# di menit ke-0 memperbolehkan 2N generate dalam dua menit di sekitar pergantian
# jam — persis lonjakan yang batas ini ada untuk mencegah.
#
# 0 = MATIKAN batas untuk endpoint itu. Sengaja ada: instance internal satu tim
# tak butuh kuota, dan mematikannya lewat env lebih jujur daripada menyetel angka
# raksasa yang terlihat seperti batas sungguhan.
RATE_LIMIT_WINDOW_SECONDS = _int_env("RATE_LIMIT_WINDOW_SECONDS", 3600)

# 10/jam: satu dokumen butuh ~2-3 menit, jadi pemakaian MANUSIA yang paling rajin
# pun sulit menembusnya, sementara skrip yang lepas kendali menabraknya dalam
# hitungan detik. Angka konservatif — dinaikkan lewat env kalau memang menghalangi.
RATE_LIMIT_GENERATE_PER_WINDOW = _int_env("RATE_LIMIT_GENERATE_PER_WINDOW", 10)

# Upload template lebih longgar: jalur $0-nya cuma pandoc + pengukuran docx. Tetap
# dibatasi karena `use_llm_mapping=true` BERBAYAR (satu panggilan Claude per
# doc_type) dan file 50 MB tetap memakan CPU/disk walau tanpa LLM.
RATE_LIMIT_TEMPLATE_UPLOAD_PER_WINDOW = _int_env("RATE_LIMIT_TEMPLATE_UPLOAD_PER_WINDOW", 20)

# Direktori hasil build frontend (Vite). Kalau ADA, FastAPI menyajikannya dari
# origin yang SAMA dengan API — satu container, satu URL, tanpa CORS. Kalau tidak
# (dev pakai `npm run dev`, atau test), penyajian ini mati total dan tak
# berpengaruh. Di image Docker, build frontend disalin ke sini.
FRONTEND_DIST = os.getenv("FRONTEND_DIST", "frontend/dist")

# --- CORS --------------------------------------------------------------------
# Origin mana yang boleh memanggil API ini dari browser. Dulu `["*"]` HARDCODE —
# nyaman untuk dev, tapi artinya situs mana pun di internet bisa memanggil API
# ini memakai browser pengunjungnya.
#
# Penting supaya tak salah menilai risikonya: token dikirim lewat header
# `Authorization` (bukan cookie), jadi `*` TIDAK membuat browser ikut mengirim
# kredensial pengguna — kerugiannya lebih sempit dari kelihatannya. Tetap
# dipersempit karena tak ada alasan membiarkannya terbuka: di Docker, SPA
# disajikan dari origin yang SAMA (lihat FRONTEND_DIST), jadi produksi nyaris
# tak memakai CORS sama sekali.
#
# Default = dev server Vite. Yang perlu diubah cuma deploy yang menyajikan
# frontend dari domain BERBEDA dengan API.
#
# `*` masih boleh, tapi kini harus DITULIS (`ALLOWED_ORIGINS=*`) — jadi ia
# keputusan seseorang, bukan warisan default yang tak pernah ditinjau.
ALLOWED_ORIGINS = _origins_env(
    "ALLOWED_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"])

# --- Worker queue (Redis + RQ) ----------------------------------------------
# KOSONG = eksekusi INLINE lewat BackgroundTasks (perilaku sebelum #13): pipeline
# jalan di dalam proses web, nol layanan tambahan, cukup untuk satu instance.
# TERISI = web cuma mengantri, worker terpisah mengeksekusi — job selamat dari
# restart/crash/deploy proses web, dan web bisa diperbanyak tanpa menggandakan
# eksekutor. Seam-nya di `job_queue.py`; sisa aplikasi tak tahu bedanya.
#
# Bentuk: redis://host:port/db (mis. redis://localhost:6379/0).
REDIS_URL = os.getenv("REDIS_URL")
JOB_QUEUE_NAME = os.getenv("JOB_QUEUE_NAME", "documents")

# Berapa kali job yang mati BERSAMA worker-nya boleh diulang otomatis. Yang diulang
# HANYA kegagalan sementara (`error_status` 503 — proses mati di tengah jalan);
# kegagalan permanen (413 repo kebesaran, 422 input salah, 500 bug) tak pernah
# diulang, karena mengulangnya cuma membakar uang LLM untuk hasil yang sama.
#
# 1, bukan 3: percobaan kedua menutup kasus yang nyata (deploy/OOM saat job jalan),
# sementara percobaan ketiga-keempat lebih mungkin berarti "job ini memang
# meruntuhkan worker" — dan mengulangnya berarti meruntuhkannya lagi, sambil
# membayar Claude tiap putaran. 0 = matikan re-queue.
JOB_MAX_ATTEMPTS = _int_env("JOB_MAX_ATTEMPTS", 1)

# --- Billing & Quota (Stripe) ------------------------------------------------
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# TANPA default. Dulu berisi "price_pro_test" — id palsu yang terlihat seperti
# konfigurasi sah, jadi lupa mengisinya baru ketahuan sebagai error Stripe tentang
# parameter API, bukan sebagai "env belum diisi". Kosong = ditolak berisik di
# billing_service saat Stripe memang aktif.
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Kuota generate dokumen per 30 hari, per akun, menurut tier. 0 = TANPA batas.
#
# Default 0 (bukan 3) DISENGAJA: kuota ini cuma berlaku kalau auth aktif, jadi
# default tak-nol menyalakan pembatasan berbayar di SETIAP instance yang memasang
# Supabase — termasuk instance internal satu tim yang tak pernah minta ditagih, dan
# tanpa satu pun baris konfigurasi yang berubah. Menaikkan tembok itu keputusan
# bisnis; menaruhnya sebagai default berarti keputusan itu diambil diam-diam oleh
# nilai literal di file ini.
#
# Tagihan tetap terjaga tanpa ini: `RATE_LIMIT_GENERATE_PER_WINDOW` (10/jam) sudah
# menahan skrip yang lepas kendali. Kuota tier menjawab pertanyaan yang BERBEDA —
# "berapa yang boleh dipakai pelanggan gratis" — dan pertanyaan itu baru ada
# begitu produk ini benar-benar dijual. Isi TIER_FREE_LIMIT di .env untuk
# menyalakannya (mis. 3), lalu penolakannya keluar sebagai 402 + ajakan upgrade.
TIER_FREE_LIMIT = _int_env("TIER_FREE_LIMIT", 0)
TIER_PRO_LIMIT = _int_env("TIER_PRO_LIMIT", 100)

# --- Observability (#14) -----------------------------------------------------
# Seam yang sama dengan REDIS_URL/SUPABASE_URL: kosong = mati, tanpa layanan
# tambahan. SENTRY_DSN kosong → error tracking tak aktif dan sentry-sdk tak
# pernah di-import (lihat telemetry.py), jadi dev/test/demo $0 tak menuntutnya.
SENTRY_DSN = os.getenv("SENTRY_DSN")
# Lingkungan yang dilaporkan ke Sentry (development/staging/production).
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")

# Format log: "plain" (default, enak dibaca manusia saat dev) atau "json" (satu
# objek per baris, siap diagregasi collector di produksi). Nilai lain → plain,
# supaya salah-ketik tak mematikan log sama sekali.
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Deploy hardening: CORS (#15) --------------------------------------------
# Origin frontend yang boleh memanggil API lintas-origin, dipisah koma. Diperketat
# dari `*` (dev lama) menjadi daftar spesifik. Tiga kasus:
#   - KOSONG → default origin dev Vite (localhost:5173) — dev `npm run dev` tetap
#     jalan tanpa konfigurasi, TAPI sudah tak lagi `*`.
#   - "*"    → izinkan semua (opt-in eksplisit; hanya untuk yang memang mau longgar).
#   - daftar → origin produksi, mis. "https://app.domain.com".
# Catatan penting: saat frontend disajikan SAME-ORIGIN oleh container (bawaan image
# ini), CORS tak terpakai sama sekali — jadi produksi same-origin tak perlu menyetel
# apa pun. CORS baru relevan kalau frontend dilayani dari origin BERBEDA.
def _list_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


CORS_ALLOW_ORIGINS = _list_env(
    "CORS_ALLOW_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
)

