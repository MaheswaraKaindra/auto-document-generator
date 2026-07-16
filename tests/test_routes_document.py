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
from app.domain.exceptions import ContextWindowExceededError
from app.main import app
from app.services import job_store

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "dummy_data"

_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001"
    "08060000001f15c489000000104944415478da6360000002"
    "0001000500010d0a2db40000000049454e44ae426082"
)


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated_job_db(tmp_path, monkeypatch):
    """Arahkan SQLite ke tmp_path, jangan sentuh data/jobs.db milik pengembang."""
    monkeypatch.setattr(job_store, "DB_PATH", tmp_path / "jobs.db")
    job_store.init_db()


@pytest.fixture
def client():
    return TestClient(app)


def _generate(client, **body) -> dict:
    """POST /documents/generate lalu ambil status job-nya.

    TestClient menjalankan BackgroundTasks SESUDAH response terkirim tapi SEBELUM
    client.post() balik — jadi begitu baris ini selesai, job-nya sudah rampung.
    Itu yang bikin test async ini tetap deterministik tanpa sleep/polling.
    """
    response = client.post("/documents/generate", json={"repositories": [], **body})
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    return client.get(f"/documents/jobs/{job_id}").json()


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


def test_generate_returns_202_immediately_without_doing_the_work(client, mock_mermaid_ok):
    """Inti dari async: POST balik SEBELUM pipeline jalan.

    Versi lama menahan seluruh pipeline (terukur 191 detik pada repo nyata) di
    satu request HTTP, sementara proxy umumnya memutus di 30-60 detik.
    """
    content = _load_fixture("document_content_sdd.json")

    with patch.object(
        routes_document._llm_service, "generate_document_content", return_value=content
    ):
        response = client.post(
            "/documents/generate", json={"document_type": "SDD", "repositories": []}
        )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["status_url"] == f"/documents/jobs/{body['job_id']}"


def test_llm_failure_lands_on_the_job_not_the_request(client):
    """Kegagalan pipeline tidak lagi bisa dikembalikan sebagai status HTTP request
    — requestnya sudah balik lama. Harus mendarat di job."""
    with patch.object(
        routes_document._llm_service,
        "generate_document_content",
        side_effect=RuntimeError("LLM gagal"),
    ):
        job = _generate(client, document_type="SDD")

    assert job["status"] == "failed"
    assert job["error_status"] == 502
    assert "coba lagi" in job["error"].lower()  # sebab tak dikenal: mengulang memang masuk akal


def test_context_window_failure_keeps_its_413_after_going_async(client):
    """Penjaga regresi paling penting dari perpindahan ke async: pemetaan
    exception -> kode HTTP tidak boleh HILANG hanya karena kegagalannya sekarang
    terjadi di latar belakang. Repo kebesaran itu PERMANEN — pengguna harus tetap
    bisa membedakannya dari 502 'coba lagi'. Kalau semua kegagalan job dilaporkan
    sama, kita balik ke penyamaran yang sudah tiga kali diperbaiki."""
    with patch.object(
        routes_document._llm_service,
        "generate_document_content",
        side_effect=ContextWindowExceededError(
            "Repo ini terlalu besar untuk model claude-sonnet-5: metadata kodenya "
            "1,224,476 token, sementara model ini cuma memuat 1,000,000."
        ),
    ):
        job = _generate(client, document_type="SDD")

    assert job["status"] == "failed"
    assert job["error_status"] == 413
    assert "1,224,476" in job["error"]  # sebab aslinya diteruskan, bukan disamarkan
    assert "coba lagi" not in job["error"].lower()


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


def test_form_metadata_survives_the_whole_async_round_trip(client, mock_mermaid_ok, tmp_path):
    """Jalur yang benar-benar dipakai end user, sekarang tiga langkah: isian form
    harus menembus POST -> background task -> compiler -> template -> DB -> lalu
    keluar utuh di docx yang diunduh lewat /jobs/{id}/download."""
    content = _load_fixture("document_content_sdd.json")

    with patch.object(
        routes_document._llm_service, "generate_document_content", return_value=content
    ):
        job = _generate(
            client,
            document_type="SDD",
            document_metadata={
                "rfc_number": "RFC-2026-088",
                "business_requestor": "Divisi Operasional",
            },
        )

    assert job["status"] == "done"
    download = client.get(job["download_url"])
    assert download.status_code == 200
    text = _docx_text_from_response(download, tmp_path)
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


def test_generate_works_without_metadata(client, mock_mermaid_ok, tmp_path):
    """document_metadata opsional -- request tanpa field ini harus tetap jalan
    dan menghasilkan dokumen berpenanda seperti sebelumnya."""
    content = _load_fixture("document_content_sdd.json")

    with patch.object(
        routes_document._llm_service, "generate_document_content", return_value=content
    ):
        job = _generate(client, document_type="SDD")

    assert job["status"] == "done"
    download = client.get(job["download_url"])
    assert "(diisi manual)" in _docx_text_from_response(download, tmp_path)


def test_download_before_finished_says_not_ready_not_not_found(client):
    """409, bukan 404: job-nya ADA, cuma belum siap. 404 bikin klien mengira
    job_id-nya salah lalu berhenti polling."""
    job_id = job_store.create_job(document_type="SDD", project_name=None)

    response = client.get(f"/documents/jobs/{job_id}/download")

    assert response.status_code == 409
    assert "belum selesai" in response.json()["detail"]


def test_unknown_job_returns_404(client):
    assert client.get("/documents/jobs/tidak-ada").status_code == 404
    assert client.get("/documents/jobs/tidak-ada/download").status_code == 404


def test_bad_document_type_rejected_synchronously_without_creating_a_job(client):
    """Validasi murah tetap sinkron: request salah bentuk harus ditolak SEKARANG,
    bukan jadi job yang gagal tiga menit kemudian."""
    response = client.post(
        "/documents/generate", json={"document_type": "INVALID", "repositories": []}
    )

    assert response.status_code == 422
    assert "job_id" not in response.json()


def test_cors_exposes_content_disposition():
    """Tanpa `expose_headers`, browser MENYEMBUNYIKAN Content-Disposition dari
    JavaScript — diam-diam, tanpa error. Akibatnya frontend jatuh ke nama
    cadangan dan SETIAP pengguna mengunduh "dokumen.docx" alih-alih
    "Solution_Design_Document.docx".

    `allow_headers=["*"]` TIDAK menutupi ini: itu untuk header REQUEST.

    Bug ini ketahuan di gladi bersih demo — dari nama file yang terunduh, bukan
    dari test. Test tidak bisa menangkapnya sebelumnya karena TestClient tidak
    menegakkan CORS sama sekali: dia bukan browser. Jadi yang diperiksa di sini
    KONFIGURASINYA, dan batas itu harus jujur diakui — hanya browser sungguhan
    yang membuktikan filenya terunduh dengan nama benar."""
    from app.main import app

    cors = next(
        (m for m in app.user_middleware if "CORS" in str(m.cls)),
        None,
    )

    assert cors is not None, "CORS middleware hilang"
    exposed = cors.kwargs.get("expose_headers", [])
    assert "Content-Disposition" in exposed
