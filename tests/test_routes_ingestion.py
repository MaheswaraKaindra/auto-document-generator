"""Test endpoint /ingest/* (Peran 1) — jalur ZIP, sepenuhnya di memori.

Dua endpoint ini adalah SATU-SATUNYA jalur masuk ZIP ke produk, dan sampai
2026-07-16 keduanya nol test — ketahuan saat audit menyeluruh. Jalur GitHub-nya
sudah ter-cover di test_github_provider.py (level provider); yang diuji di sini
adalah lapisan HTTP-nya: multipart parsing, pemasangan file<->tag, dan pemetaan
error ke kode HTTP.
"""

import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_zip_upload_returns_contract_a():
    """Jalur penuh ZIP -> Contract A: upload multipart, dapat ParsedRepoContext
    dengan endpoint Flask yang terdeteksi dari isi ZIP-nya."""
    archive = _zip_bytes(
        {
            "app.py": (
                "from flask import Flask\n"
                "app = Flask(__name__)\n"
                '@app.route("/health")\n'
                "def health():\n"
                '    return "ok"\n'
            )
        }
    )

    response = client.post(
        "/ingest/zip",
        files=[("files", ("backend.zip", archive, "application/zip"))],
        data={"repo_tags": "Backend"},
    )

    assert response.status_code == 200
    context = response.json()
    assert context["repositories"][0]["repo_tag"] == "Backend"
    endpoints = [
        e
        for f in context["repositories"][0]["files"]
        for e in f["api_endpoints"]
    ]
    assert {(e["method"], e["path"]) for e in endpoints} == {("GET", "/health")}


def test_zip_upload_mismatched_tags_is_422():
    """Dua file, satu tag -> tolak SEBELUM menyentuh isi arsip. Pemasangan
    file<->tag berdasarkan urutan, jadi jumlah yang beda = request ambigu."""
    archive = _zip_bytes({"a.py": "x = 1"})

    response = client.post(
        "/ingest/zip",
        files=[
            ("files", ("satu.zip", archive, "application/zip")),
            ("files", ("dua.zip", archive, "application/zip")),
        ],
        data={"repo_tags": "Backend"},
    )

    assert response.status_code == 422


def test_zip_upload_corrupt_archive_is_422_not_500():
    """Bytes yang bukan ZIP harus jadi 422 (input pengguna salah), bukan 500
    (salah kita). SourceProviderError -> 422 adalah kontrak error endpoint ini."""
    response = client.post(
        "/ingest/zip",
        files=[("files", ("rusak.zip", b"ini bukan zip", "application/zip"))],
        data={"repo_tags": "Backend"},
    )

    assert response.status_code == 422
