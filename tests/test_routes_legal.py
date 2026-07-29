"""Halaman /privacy & /terms (#16).

Isi hukumnya bukan urusan test — itu tinjauan manusia. Yang dikunci di sini tiga
hal yang MEMANG bisa salah secara teknis: halamannya tersaji, ia terbuka tanpa
login, dan spanduk "draf"-nya benar-benar mengikuti isi dokumen (bukan sesuatu
yang harus diingat seseorang untuk dipasang/dihapus).
"""

import pytest
from fastapi.testclient import TestClient

from app.api import routes_legal
from app.core import config
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_halaman_tersaji(client, path):
    response = client.get(path)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert "<h1>" in response.text


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_terbuka_tanpa_login_walau_auth_aktif(client, monkeypatch, path):
    """Orang harus bisa membaca apa yang terjadi pada datanya SEBELUM
    menyerahkan data apa pun. Halaman privasi di balik login adalah cacat
    desain, bukan pengamanan."""
    monkeypatch.setattr(config, "SUPABASE_URL", "https://proj.supabase.co")

    assert client.get(path).status_code == 200


def test_spanduk_draf_muncul_selama_penanda_belum_diisi(client):
    """Draf yang belum diisi harus MENGATAKANNYA sendiri."""
    body = client.get("/privacy").text

    assert "[ISI:" in body, "draf ini seharusnya masih punya penanda"
    assert "masih draf" in body


def test_spanduk_hilang_sendiri_saat_penanda_terakhir_diisi(tmp_path, monkeypatch):
    """Inti rancangannya: spanduk diturunkan dari ISI dokumen, bukan dipasang
    manual. Spanduk manual punya dua cara gagal yang dua-duanya memalukan — lupa
    memasang saat masih draf, atau lupa menghapus sesudah final. Test ini
    membuktikan kedua kegagalan itu mustahil."""
    monkeypatch.setattr(routes_legal, "_LEGAL_DIR", tmp_path)
    (tmp_path / "privacy.html").write_text(
        "<html><body><!--DRAF--><h1>Kebijakan Privasi</h1>"
        "<p>PT Contoh Sejahtera, Jakarta.</p></body></html>",
        encoding="utf-8")

    body = TestClient(app).get("/privacy").text

    assert "masih draf" not in body
    assert "<!--DRAF-->" not in body, "penanda slot bocor ke halaman"
    assert "PT Contoh Sejahtera" in body


def test_berkas_hilang_dijawab_404_bukan_500(tmp_path, monkeypatch):
    """Kalau berkas legal tak ikut ter-copy ke image, gejalanya harus jawaban
    yang bisa dibaca — bukan stack trace."""
    monkeypatch.setattr(routes_legal, "_LEGAL_DIR", tmp_path)

    response = TestClient(app).get("/terms")

    assert response.status_code == 404
    assert "terms.html" in response.json()["detail"]
