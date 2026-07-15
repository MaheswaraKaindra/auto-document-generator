"""Test routes_document.py (Peran 3) — endpoint /documents/sdd, /uat, /generate.

Mermaid.ink dan pemanggilan LLM (Gemini) selalu di-mock supaya test tidak
bergantung pada koneksi internet, API key, atau kuota.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from app.api import routes_document
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
