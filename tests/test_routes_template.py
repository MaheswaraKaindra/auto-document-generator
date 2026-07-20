"""Tes endpoint /templates (V2 upload template). Docx sintetis (python-docx),
store di-redirect ke tmp — tanpa LLM, tanpa docx vendor. build_reference memakai
pandoc asli (seperti test compiler lain)."""
import io

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.services import compiler_service

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Jangan tulis template ke data/ asli — redirect store ke tmp pytest."""
    monkeypatch.setattr(compiler_service, "TEMPLATES_STORE", tmp_path / "templates")


@pytest.fixture
def client():
    return TestClient(app)


def _docx_bytes(headings):
    doc = Document()
    doc.add_paragraph("Judul Dokumen", style="Title")
    for h in headings:
        doc.add_paragraph(h, style="Heading 1")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_compiles_registers_and_is_usable_in_generate(client):
    data = _docx_bytes(["Deskripsi Aplikasi", "Use Case", "Lampiran"])
    resp = client.post(
        "/templates",
        files={"file": ("vendor_sdd.docx", data, DOCX_MIME)},
        data={"name": "Vendor SDD", "doc_types": "SDD"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    tid = body["manifest"]["template_id"]
    assert tid == "vendor-sdd"
    assert body["manifest"]["doc_types"] == {"SDD": "SDD.md"}

    # rencana peta ikut di respons (untuk ditinjau)
    bindings = {m["text"]: m["binding"] for m in body["mappings"]["SDD"]}
    assert bindings["Deskripsi Aplikasi"] == "app_description"
    assert bindings["Use Case"] == "use_cases"
    assert bindings["Lampiran"] == "manual"          # tak dikenali → placeholder jujur

    # terdaftar, muncul di daftar (dengan doc_types), DAN lolos validasi generate
    listed = client.get("/templates").json()["templates"]
    entry = next(t for t in listed if t["id"] == tid)
    assert entry["doc_types"] == ["SDD"]
    assert entry["source"] == "compiled"
    compiler_service.validate_template(tid, "SDD")   # tak melempar = bisa dipakai generate

    detail = client.get(f"/templates/{tid}")
    assert detail.status_code == 200
    assert detail.json()["manifest"]["template_id"] == tid


def test_upload_with_llm_mapping_opt_in(client, monkeypatch):
    """use_llm_mapping=true meng-opt-in pemeta LLM (di-mock di boundary, $0). Bab
    asing yang heuristik tandai 'manual' kini terpetakan lewat jawaban LLM."""
    import app.services.llm_mapping_service as lm
    monkeypatch.setattr(
        lm, "_request_bindings",
        lambda outline, doc_type: {0: "skip", 1: "app_description", 2: "feature_requirements"},
    )
    data = _docx_bytes(["Vision Statement", "Business Capabilities"])
    resp = client.post(
        "/templates",
        files={"file": ("dynamics.docx", data, DOCX_MIME)},
        data={"doc_types": "SDD", "use_llm_mapping": "true"},
    )
    assert resp.status_code == 201, resp.text
    bindings = {m["text"]: m["binding"] for m in resp.json()["mappings"]["SDD"]}
    assert bindings["Vision Statement"] == "app_description"
    assert bindings["Business Capabilities"] == "feature_requirements"


def test_upload_rejects_doc_and_non_docx(client):
    doc = client.post("/templates", files={"file": ("lama.doc", b"\xd0\xcf", "application/msword")})
    assert doc.status_code == 422
    assert ".docx" in doc.json()["detail"]

    txt = client.post("/templates", files={"file": ("catatan.txt", b"halo", "text/plain")})
    assert txt.status_code == 422


def test_upload_rejects_garbage_and_empty(client):
    garbage = client.post(
        "/templates", files={"file": ("palsu.docx", b"ini bukan docx sama sekali", DOCX_MIME)})
    assert garbage.status_code == 422          # PackageNotFoundError → 422, bukan 500

    empty = client.post("/templates", files={"file": ("kosong.docx", b"", DOCX_MIME)})
    assert empty.status_code == 422


def test_list_templates_includes_builtins_with_doc_types(client):
    templates = client.get("/templates").json()["templates"]
    by_id = {t["id"]: t for t in templates}
    assert by_id["default"]["doc_types"] == ["SDD", "UAT"]
    assert by_id["default"]["source"] == "builtin"
    # premco kini menyediakan SDD DAN UAT — frontend membaca ini, bukan hardcode
    assert by_id["premco"]["doc_types"] == ["SDD", "UAT"]


def test_get_unknown_template_is_404(client):
    assert client.get("/templates/tidak-ada").status_code == 404
