import os
from dotenv import load_dotenv

load_dotenv()

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
