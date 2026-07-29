"""Tes CORS diperketat (#15): dari `*` ke daftar origin dari env.

`app` dibuat saat import dengan `config.CORS_ALLOW_ORIGINS` yang dibaca saat itu,
jadi tes perilaku memakai NILAI DEFAULT (origin dev Vite) — bukan mem-patch config
lalu berharap middleware yang sudah ter-wire ikut berubah. Parsing env diuji
terpisah di level fungsi.
"""

from fastapi.testclient import TestClient

from app.core import config
from app.main import app

client = TestClient(app)


def test_default_bukan_bintang():
    """Regression guard: default TIDAK boleh kembali ke '*'. Inti #15 adalah
    berhenti mengizinkan semua origin secara diam-diam."""
    assert config.CORS_ALLOW_ORIGINS != ["*"]
    assert "http://localhost:5173" in config.CORS_ALLOW_ORIGINS


def test_list_env_parsing(monkeypatch):
    monkeypatch.setenv("X_CORS", "  https://a.com , https://b.com ,, ")
    assert config._list_env("X_CORS", []) == ["https://a.com", "https://b.com"]


def test_list_env_kosong_pakai_default(monkeypatch):
    monkeypatch.delenv("X_CORS", raising=False)
    assert config._list_env("X_CORS", ["def"]) == ["def"]


def test_list_env_bintang_eksplisit(monkeypatch):
    """'*' tetap mungkin, tapi harus DIPILIH eksplisit — bukan default."""
    monkeypatch.setenv("X_CORS", "*")
    assert config._list_env("X_CORS", ["def"]) == ["*"]


def test_origin_diizinkan_dapat_header():
    resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_origin_asing_tak_dapat_header():
    """Origin yang tak terdaftar tak boleh dipantulkan — itu yang membedakan
    daftar spesifik dari '*'."""
    resp = client.get("/health", headers={"Origin": "http://evil.example.com"})
    assert resp.headers.get("access-control-allow-origin") != "http://evil.example.com"
