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

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/github/callback")
