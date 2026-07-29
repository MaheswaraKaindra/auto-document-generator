"""Endpoint `/me/export` & `/me/data` (#16) — lapisan HTTP-nya.

Yang diuji di sini cuma penerjemahan boundary: siapa yang boleh, status code apa,
dan bahwa data pengguna lain tak pernah ikut. Perilaku penyapunya sendiri diuji
di `test_user_data_service.py` — dipisah supaya kegagalan menunjuk ke satu lapisan
saja, bukan ke "salah satu dari dua".
"""

import time
import zipfile
from io import BytesIO

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.services import billing_service, compiler_service, job_store

_SECRET = "rahasia-test-yang-cukup-panjang-tiga-puluh-dua"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _tmp_store(tmp_path, monkeypatch):
    db_file = tmp_path / "jobs.db"
    monkeypatch.setattr(job_store, "DB_PATH", db_file)
    monkeypatch.setattr(billing_service, "DB_PATH", db_file)
    monkeypatch.setattr(compiler_service, "TEMPLATES_STORE", tmp_path / "templates")
    job_store.init_db()
    billing_service.init_billing_db()


def _token(monkeypatch, sub):
    """Aktifkan auth Supabase (HS256) + kembalikan header Bearer untuk `sub`."""
    monkeypatch.setattr(config, "SUPABASE_URL", "https://proj.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_JWT_SECRET", _SECRET)
    monkeypatch.setattr(config, "SUPABASE_JWT_AUD", "authenticated")
    token = jwt.encode({"sub": sub, "aud": "authenticated",
                        "exp": int(time.time()) + 3600}, _SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _job_selesai(owner, tmp_path, nama="dok.docx"):
    job_id = job_store.create_job("SDD", "Proyek Uji", owner=owner)
    sumber = tmp_path / f"sumber_{job_id}_{nama}"
    sumber.write_bytes(b"PK\x03\x04 docx palsu")
    job_store.mark_done(job_id, str(sumber))
    return job_id


# --- Mode dev ----------------------------------------------------------------

def test_mode_dev_menolak_dengan_409_dan_menjelaskan_kenapa(client, monkeypatch):
    """409, bukan 401/403 — dan pesannya harus MENJELASKAN, bukan cuma menolak.

    Di instance tanpa auth tidak ada yang bisa di-login-i, jadi 401 ("login
    dulu") justru mengirim pengguna mengejar sesuatu yang tak ada."""
    monkeypatch.setattr(config, "SUPABASE_URL", None)

    for response in (client.get("/me/export"), client.delete("/me/data")):
        assert response.status_code == 409, response.text
        assert "autentikasi" in response.json()["detail"].lower()


# --- Ekspor ------------------------------------------------------------------

def test_ekspor_mengembalikan_zip_berisi_data(client, monkeypatch, tmp_path):
    headers = _token(monkeypatch, "alice")
    _job_selesai("alice", tmp_path)

    response = client.get("/me/export", headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        assert "data.json" in zf.namelist()
        assert "BACA-SAYA.txt" in zf.namelist()


def test_ekspor_hanya_data_pemanggil(client, monkeypatch, tmp_path):
    _job_selesai("bob", tmp_path, "punya-bob.docx")
    headers = _token(monkeypatch, "alice")

    response = client.get("/me/export", headers=headers)

    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        isi = zf.read("data.json").decode()
    assert '"bob"' not in isi
    assert isi.count('"jobs"') == 1
    assert "[]" in isi   # alice belum punya job


def test_ekspor_tanpa_token_saat_auth_aktif_401(client, monkeypatch):
    _token(monkeypatch, "alice")   # aktifkan auth, tapi jangan kirim header

    assert client.get("/me/export").status_code == 401


# --- Hapus -------------------------------------------------------------------

def test_hapus_mengembalikan_ringkasan(client, monkeypatch, tmp_path):
    headers = _token(monkeypatch, "alice")
    job_id = _job_selesai("alice", tmp_path)

    response = client.delete("/me/data", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["owner"] == "alice"
    assert body["jobs_deleted"] == 1
    assert body["documents_deleted"] == 1
    assert job_store.get_job(job_id) is None


def test_hapus_tak_menyentuh_pengguna_lain(client, monkeypatch, tmp_path):
    job_bob = _job_selesai("bob", tmp_path)
    headers = _token(monkeypatch, "alice")
    _job_selesai("alice", tmp_path)

    client.delete("/me/data", headers=headers)

    assert job_store.get_job(job_bob) is not None


def test_hapus_tanpa_token_saat_auth_aktif_401(client, monkeypatch, tmp_path):
    """Penghapusan tanpa identitas tak boleh sampai ke service sama sekali."""
    _token(monkeypatch, "alice")
    job_id = _job_selesai("alice", tmp_path)

    assert client.delete("/me/data").status_code == 401
    assert job_store.get_job(job_id) is not None
