"""Test compiler_service.py (Peran 3) — render Jinja2 + Mermaid + export docx.

Mermaid.ink selalu di-mock supaya test tidak bergantung pada koneksi internet
atau layanan pihak ketiga yang tidak stabil.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from docx import Document

from app.services import compiler_service

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "dummy_data"

# PNG 1x1 minimal yang valid, supaya pandoc bisa benar-benar embed gambarnya
# ke docx (bukan cuma byte sembarang).
_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "08060000001f15c489000000104944415478da6360000002"
    "0001000500010d0a2db40000000049454e44ae426082"
)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def mock_mermaid_ok():
    response = Mock()
    response.content = _MINIMAL_PNG
    response.raise_for_status = Mock()
    with patch("app.services.compiler_service.requests.get", return_value=response) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def redirect_output_dir(tmp_path, monkeypatch):
    """Jangan tulis file test ke system temp asli, pakai folder sementara pytest."""
    monkeypatch.setattr(compiler_service, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(compiler_service, "IMAGES_DIR", tmp_path / "images")


def test_generate_docx_sdd_produces_valid_docx(mock_mermaid_ok):
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Test Project")

    assert Path(output_path).exists()
    doc = Document(output_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Solution Design Document" in full_text
    assert data["app_description"] in full_text


def test_generate_docx_uat_produces_valid_docx(mock_mermaid_ok):
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx("UAT", data, project_name="Test Project")

    assert Path(output_path).exists()
    doc = Document(output_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "User Acceptance Testing" in full_text


def test_generate_docx_lowercase_type_still_works(mock_mermaid_ok):
    """document_type harus case-insensitive ('sdd' == 'SDD')."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("sdd", data)

    assert Path(output_path).exists()


def test_generate_docx_invalid_type_raises_value_error():
    data = _load_fixture("document_content_sdd.json")

    with pytest.raises(ValueError):
        compiler_service.generate_docx("BUKAN_TIPE_VALID", data)


def test_mermaid_render_failure_propagates_as_request_exception():
    data = _load_fixture("document_content_sdd.json")

    with patch(
        "app.services.compiler_service.requests.get",
        side_effect=requests.ConnectionError("mermaid.ink tidak terjangkau"),
    ):
        with pytest.raises(requests.RequestException):
            compiler_service.generate_docx("SDD", data)
