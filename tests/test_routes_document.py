"""Test routes_document.py (Peran 3) — endpoint /documents/sdd, /uat, /generate.

Mermaid.ink dan pemanggilan LLM (Claude) selalu di-mock supaya test tidak
bergantung pada koneksi internet, API key, atau kuota.
"""

import json
import re
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from docx import Document
from fastapi.testclient import TestClient

from app.api import routes_document
from app.api.schemas_document import DocumentMetadata
from app.main import app

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "dummy_data"

_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "08060000001f15c489000000104944415478da6360000002"
    "0001000500010d0a2db40000000049454e44ae426082"
)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_mermaid_ok():
    response = Mock()
    response.content = _MINIMAL_PNG
    response.raise_for_status = Mock()
    with patch("app.services.compiler_service.requests.get", return_value=response) as mocked:
        yield mocked


def test_generate_sdd_from_content_returns_docx(client, mock_mermaid_ok):
    data = _load_fixture("document_content_sdd.json")

    response = client.post("/documents/sdd", json=data)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_generate_uat_from_content_returns_docx(client, mock_mermaid_ok):
    data = _load_fixture("document_content_uat.json")

    response = client.post("/documents/uat", json=data)

    assert response.status_code == 200


def test_generate_sdd_missing_field_returns_422(client):
    """DocumentContent divalidasi Pydantic -- body tidak lengkap harus ditolak,
    bukan diproses setengah jalan."""
    response = client.post("/documents/sdd", json={"document_type": "SDD"})

    assert response.status_code == 422


def test_generate_sdd_returns_502_when_mermaid_fails(client):
    data = _load_fixture("document_content_sdd.json")

    with patch(
        "app.services.compiler_service.requests.get",
        side_effect=requests.ConnectionError("boom"),
    ):
        response = client.post("/documents/sdd", json=data)

    assert response.status_code == 502


def test_generate_full_pipeline_rejects_invalid_document_type(client):
    response = client.post(
        "/documents/generate",
        json={"document_type": "INVALID", "repositories": []},
    )

    assert response.status_code == 422


def test_generate_full_pipeline_returns_502_when_llm_fails(client):
    with patch.object(
        routes_document._llm_service,
        "generate_document_content",
        side_effect=RuntimeError("LLM gagal"),
    ):
        response = client.post(
            "/documents/generate",
            json={"document_type": "SDD", "repositories": []},
        )

    assert response.status_code == 502


def _docx_text_from_response(response, tmp_path) -> str:
    """Baca docx yang benar-benar dikirim ke klien. Sel tabel ikut diambil --
    hampir semua metadata mendarat di tabel, dan doc.paragraphs melewatkannya."""
    path = tmp_path / "response.docx"
    path.write_bytes(response.content)
    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


def test_generate_full_pipeline_puts_form_metadata_into_docx(client, mock_mermaid_ok, tmp_path):
    """Jalur yang benar-benar dipakai end user: isian form harus menembus
    request -> route -> compiler -> template dan muncul di docx yang diunduh."""
    content = _load_fixture("document_content_sdd.json")

    with patch.object(
        routes_document._llm_service, "generate_document_content", return_value=content
    ):
        response = client.post(
            "/documents/generate",
            json={
                "document_type": "SDD",
                "repositories": [],
                "document_metadata": {
                    "rfc_number": "RFC-2026-088",
                    "business_requestor": "Divisi Operasional",
                },
            },
        )

    assert response.status_code == 200
    text = _docx_text_from_response(response, tmp_path)
    assert "RFC-2026-088" in text
    assert "Divisi Operasional" in text


def test_every_meta_field_in_templates_exists_in_schema():
    """Penjaga untuk sisi buruk desain fail-open di _MetadataDict.__missing__:
    field yang tidak dikenal TIDAK error, cuma diam-diam keluar sebagai
    *(diisi manual)*. Artinya salah ketik di template (mis. meta.rfc_numbr)
    tidak akan pernah ketahuan saat runtime -- sel-nya cuma kosong selamanya.
    Test ini yang menangkapnya."""
    known_fields = set(DocumentMetadata.model_fields)
    templates_dir = Path(__file__).resolve().parent.parent / "app" / "templates"

    for template in ("sdd_template.md", "uat_template.md"):
        used = set(re.findall(r"meta\.([a-z_]+)", (templates_dir / template).read_text(encoding="utf-8")))
        unknown = used - known_fields
        assert not unknown, f"{template} memakai field yang tidak ada di DocumentMetadata: {sorted(unknown)}"


def test_generate_full_pipeline_works_without_metadata(client, mock_mermaid_ok, tmp_path):
    """document_metadata opsional -- request lama (tanpa field ini) harus tetap
    jalan dan menghasilkan dokumen berpenanda seperti sebelumnya."""
    content = _load_fixture("document_content_sdd.json")

    with patch.object(
        routes_document._llm_service, "generate_document_content", return_value=content
    ):
        response = client.post(
            "/documents/generate",
            json={"document_type": "SDD", "repositories": []},
        )

    assert response.status_code == 200
    assert "(diisi manual)" in _docx_text_from_response(response, tmp_path)
