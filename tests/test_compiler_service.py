"""Test compiler_service.py (Peran 3) — render Jinja2 + Mermaid + export docx.

Mermaid.ink selalu di-mock supaya test tidak bergantung pada koneksi internet
atau layanan pihak ketiga yang tidak stabil.
"""

import base64
import json
import uuid
import zlib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from docx import Document

from app.domain.exceptions import DiagramRenderError
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


def _docx_text(path: str) -> str:
    """Semua teks docx, TERMASUK isi tabel.

    doc.paragraphs saja tidak cukup: hampir semua metadata mendarat di sel tabel
    (Informasi Dokumen, Demografi, checklist Security), dan sel tabel tidak ikut
    di doc.paragraphs -- assertion-nya akan hijau palsu.
    """
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells)
    return "\n".join(parts)


# Penanda *(diisi manual)* itu Markdown italic -- pandoc mengubah bintangnya jadi
# format, jadi yang tersisa di docx cuma teksnya.
_PLACEHOLDER_IN_DOCX = "(diisi manual)"

# Semua field metadata yang dipakai template SDD (17) dan UAT (8). Sengaja ditulis
# lengkap: test "tidak ada lubang tersisa" di bawah cuma bermakna kalau daftar ini
# memang utuh.
_FULL_SDD_METADATA = {
    "solution_design_no": "SD-2026-014",
    "rfc_number": "RFC-2026-088",
    "version": "1.2",
    "document_classification": "Internal",
    "dev_system_type": "NON ERP",
    "business_requestor": "Divisi Operasional",
    "business_user": "Tim Gudang",
    "projected_user_number": "120 pengguna",
    "value_rp": "Rp 450.000.000",
    "coverage_area": "Nasional",
    "collaboration_profile": "Internal + vendor",
    "technology_capability": "Web + mobile",
    "how_to_access": "https://inventaris.internal/login",
    "infrastructure_capacity": "3 VM, 8 vCPU, 16 GB RAM",
    "security_penetration_test": "Sudah, 2026-06-30",
    "security_secure_coding": "Mengikuti OWASP ASVS L2",
    "security_reverse_proxy": "Nginx",
}

_FULL_UAT_METADATA = {
    "related_rfc_number": "RFC-2026-088",
    "related_work_order": "WO-2026-451",
    "change_owner": "Budi Santoso",
    "prepared_by": "Siti Rahma",
    "preparation_date": "2026-07-10",
    "reviewed_by": "Andi Wijaya",
    "review_date": "2026-07-12",
    "distribution_list": "Tim QA, Tim Operasional",
}


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


def test_mermaid_unreachable_raises_diagram_render_error():
    data = _load_fixture("document_content_sdd.json")

    with patch(
        "app.services.compiler_service.requests.get",
        side_effect=requests.ConnectionError("mermaid.ink tidak terjangkau"),
    ):
        with pytest.raises(DiagramRenderError, match="tidak merespons"):
            compiler_service.generate_docx("SDD", data)


def _decode_pako_url(url: str) -> str:
    """Balik URL 'pako:' jadi script Mermaid aslinya, untuk verifikasi test."""
    payload = url.split("/img/pako:", 1)[1]
    return json.loads(zlib.decompress(base64.urlsafe_b64decode(payload)))["code"]


def test_mermaid_url_uses_pako_and_round_trips(mock_mermaid_ok):
    """Encoding harus 'pako:' (terkompresi), dan script harus bisa dibalik utuh.

    Ini yang menahan URL di bawah batas ~8KB mermaid.ink; encoding base64 polos
    sebelumnya menembus batas itu pada repo besar dan dijawab HTTP 414.
    """
    data = _load_fixture("document_content_sdd.json")

    compiler_service.generate_docx("SDD", data)

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert "/img/pako:" in url
    assert _decode_pako_url(url) == data["diagrams"]["system_architecture"]


def test_pako_keeps_large_diagram_under_url_limit(mock_mermaid_ok):
    """Diagram besar yang dulu bikin 414 harus lolos batas panjang URL."""
    big_script = "graph LR\n" + "\n".join(
        f"N{i}[Service Node Number {i}]-->N{i + 1}[Service Node Number {i + 1}]"
        for i in range(120)
    )
    plain_b64_len = len(base64.urlsafe_b64encode(big_script.encode()))

    compiler_service._render_mermaid_to_image(big_script, compiler_service.IMAGES_DIR)

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert plain_b64_len > compiler_service._MERMAID_URL_LIMIT  # dulu: 414
    assert len(url) < compiler_service._MERMAID_URL_LIMIT  # sekarang: muat


def test_oversized_diagram_fails_before_hitting_network(mock_mermaid_ok):
    """Kalau tetap kebesaran walau dikompresi, gagal dengan pesan jelas dan
    jangan buang-buang request ke mermaid.ink."""
    # Teks acak supaya tidak bisa dikompresi -- meniru diagram yang benar-benar besar.
    incompressible = "graph LR\n" + "\n".join(uuid.uuid4().hex for _ in range(600))

    with pytest.raises(DiagramRenderError, match="terlalu besar"):
        compiler_service._render_mermaid_to_image(incompressible, compiler_service.IMAGES_DIR)

    mock_mermaid_ok.assert_not_called()


def test_http_error_message_names_the_real_status():
    """Sebab asli (mis. 414) harus tersebut, bukan diratakan jadi 'tidak merespons'
    -- persis penyamaran itu yang dulu bikin bug ini lama tak terdiagnosis."""
    response = Mock(status_code=414)
    error = requests.HTTPError("414 Client Error", response=response)
    response.raise_for_status = Mock(side_effect=error)

    with patch("app.services.compiler_service.requests.get", return_value=response):
        with pytest.raises(DiagramRenderError, match="414"):
            compiler_service._render_mermaid_to_image("graph LR\nA-->B", compiler_service.IMAGES_DIR)


def test_code_fence_is_stripped_before_encoding(mock_mermaid_ok):
    """LLM kadang membungkus script dengan ```mermaid -- fence bikin 400."""
    compiler_service._render_mermaid_to_image(
        "```mermaid\ngraph LR\nA-->B\n```", compiler_service.IMAGES_DIR
    )

    url = mock_mermaid_ok.call_args_list[0].args[0]
    assert _decode_pako_url(url) == "graph LR\nA-->B"


# --- Metadata dokumen (isian manusia dari form) ---


def test_sdd_metadata_leaves_no_manual_placeholder(mock_mermaid_ok):
    """Inti dari fitur ini: 17 field form harus menutup SEMUA lubang SDD yang
    bukan tanda tangan. Kalau ada field template yang lupa dipetakan ke form,
    penandanya akan tersisa dan test ini merah."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, project_name="Test Project", document_metadata=_FULL_SDD_METADATA
    )

    assert _PLACEHOLDER_IN_DOCX not in _docx_text(output_path)


def test_uat_metadata_leaves_no_manual_placeholder(mock_mermaid_ok):
    """Pasangan test di atas untuk UAT: 8 field menutup 8 lubang non-tanda-tangan."""
    data = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx(
        "UAT", data, project_name="Test Project", document_metadata=_FULL_UAT_METADATA
    )

    assert _PLACEHOLDER_IN_DOCX not in _docx_text(output_path)


def test_metadata_values_appear_in_docx(mock_mermaid_ok):
    """Field tidak cuma menghapus penanda -- isinya harus benar-benar mendarat,
    termasuk yang di dalam sel tabel (Demografi, checklist Security)."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD", data, document_metadata=_FULL_SDD_METADATA
    )

    text = _docx_text(output_path)
    for value in _FULL_SDD_METADATA.values():
        assert value in text, f"metadata {value!r} tidak muncul di docx"


def test_without_metadata_falls_back_to_old_behaviour(mock_mermaid_ok):
    """Perilaku lama adalah LANTAI, bukan langit: tidak mengisi form sama sekali
    harus menghasilkan dokumen seperti sebelum form ini ada, bukan error atau
    sel kosong melompong."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx("SDD", data, project_name="Test Project")

    assert _PLACEHOLDER_IN_DOCX in _docx_text(output_path)


def test_blank_metadata_fields_treated_as_unfilled(mock_mermaid_ok):
    """Form mengirim string kosong untuk input yang tidak disentuh (dan Pydantic
    mengirim None untuk field yang absen). Keduanya harus jatuh ke penanda --
    bukan bikin sel tabel kosong yang terbaca seperti bug."""
    data = _load_fixture("document_content_sdd.json")

    output_path = compiler_service.generate_docx(
        "SDD",
        data,
        document_metadata={"rfc_number": "   ", "version": "", "document_classification": None},
    )

    assert _PLACEHOLDER_IN_DOCX in _docx_text(output_path)


def test_signature_blocks_survive_full_metadata(mock_mermaid_ok):
    """Blok tanda tangan & sertifikasi hasil sengaja TIDAK ditanyakan di form:
    tanda tangan bukan data yang diketik, dan hasil Lolos/Gagal belum ada saat
    generate. Metadata selengkap apa pun tidak boleh menghapusnya."""
    uat = _load_fixture("document_content_uat.json")

    output_path = compiler_service.generate_docx(
        "UAT", uat, document_metadata=_FULL_UAT_METADATA
    )

    text = _docx_text(output_path)
    assert "tanda tangan" in text.lower()
    assert "Sertifikasi Keberhasilan Pelaksanaan Pengujian" in text
